# 模型自动选择/融合 设计方案

**日期**: 2026-04-18
**状态**: 待实施
**优先级**: B（四个子项目中第一个）
**后续子项目**: A.概率预测 → C.功率曲线异常检测 → D.极端天气事件预测

## 目标

训练多个模型（现有 LightGBM GBDT/DART/GOSS + XGBoost），根据近7天验证集准确率自动加权融合，提升预测精度。架构可插拔，后续添加新算法（CatBoost/RF/LSTM）无需改框架。

## 现有基础

- 超短期：XGBoost (XGBRegressor) + StandardScaler
- 短期/中期：LightGBM 三种变体（GBDT, DART, GOSS）+ RandomizedSearchCV
- 模型存储：MinIO (S3) + 本地 `saved_models/` 目录
- DB 模型：`Model` 表记录模型元数据（name, path, accuracy, version, is_production）
- 训练调度：Celery Worker 定时调用 `auto_pre_train.py`

## 架构

```
训练时:
  auto_pre_train.py → 训练模型 → 验证集评估 → ModelRegistry.register() → MinIO + DB

推理时:
  FusionEngine.predict() → 查 DB 取 active 模型 → 按权重加载 → 并行预测 → 加权融合
```

## 数据模型

### model_versions（新增表）

```sql
CREATE TABLE model_versions (
    id                SERIAL PRIMARY KEY,
    farm_code         VARCHAR(50) NOT NULL,
    task_type         VARCHAR(20) NOT NULL,   -- supershort / short / medium
    algorithm         VARCHAR(50) NOT NULL,   -- xgboost / lightgbm_gbdt / lightgbm_dart / lightgbm_goss
    hyperparams       JSONB,                  -- {"learning_rate": 0.05, "n_estimators": 500, ...}
    val_rmse          FLOAT,
    val_mae           FLOAT,
    val_accuracy      FLOAT,                  -- 1 - rmse/capacity 百分比
    is_active         BOOLEAN DEFAULT TRUE,
    s3_path           VARCHAR(500),           -- MinIO 对象路径
    local_path        VARCHAR(500),           -- 本地文件路径（兼容现有）
    scaler_path       VARCHAR(500),           -- 超短期 scaler 路径
    feature_cols      JSONB,                  -- ["ws10", "ws100", "t2m", ...]
    training_samples  INTEGER,
    trained_at        TIMESTAMP DEFAULT NOW(),
    activated_at      TIMESTAMP,
    deactivated_at    TIMESTAMP
);

CREATE INDEX idx_mv_farm_type ON model_versions(farm_code, task_type);
CREATE INDEX idx_mv_active ON model_versions(farm_code, task_type, is_active) WHERE is_active = TRUE;
```

## 三个核心组件

### 1. ModelRegistry（模型注册器）

位置：`backend-autopredict/model_registry.py`

```python
class ModelRegistry:
    def register(self, farm_code, task_type, algorithm, model_path,
                 hyperparams, val_rmse, val_mae, feature_cols, ...):
        """注册新模型版本。如果验证指标优于阈值则激活。"""
        # 1. 上传模型文件到 MinIO
        # 2. 写入 model_versions 表
        # 3. 如果 val_rmse 优于阈值 → is_active=True
        # 4. 清理：保留最近 5 个 active 版本，更早的 deactivate

    def get_active_models(self, farm_code, task_type, limit=5):
        """获取指定场站+类型的所有 active 模型，按 trained_at 降序。"""

    def deactivate(self, model_id):
        """停用一个模型版本。"""

    def deactivate_old_versions(self, farm_code, task_type, keep=5):
        """保留最近 N 个 active 版本，停用更早的。"""
```

激活阈值：
- 超短期：`val_accuracy >= 0.80`（RMSE <= 20% 装机容量）
- 短期：`val_accuracy >= 0.75`
- 中期：`val_accuracy >= 0.70`
- 如果比当前线上最差模型还差，也不激活

### 2. FusionEngine（融合引擎）

位置：`backend-autopredict/fusion_engine.py`

```python
class FusionEngine:
    def predict(self, farm_code, task_type, features_df):
        """融合预测主入口。"""
        # 1. 查 model_versions → 取 active 模型列表
        # 2. 如果只有 1 个模型 → 单模型预测（向后兼容）
        # 3. 如果有多个模型 → 加权融合

    def _compute_weights(self, models):
        """基于验证集 RMSE 计算权重：weight_i = (1/rmse_i) / sum(1/rmse_j)"""
        # 反 RMSE 加权，归一化到 sum=1

    def _load_model(self, model_record):
        """从 MinIO 或本地加载模型文件（joblib）。"""

    def _single_predict(self, model, features_df):
        """单模型推理，返回预测数组。"""
```

加权策略：
- 默认：反 RMSE 加权 `w_i = (1/rmse_i) / Σ(1/rmse_j)`
- 退化为单模型时：权重为 1.0
- 最少 1 个模型可用（不能报错）

### 3. AutoTrainer 增强（改造现有训练脚本）

改造 `auto_pre_train.py`（short/middle 各一份），在训练完成后：

```python
# 现有训练逻辑不变
model = train_lightgbm(X_train, y_train, variant="gbdt")

# 新增：验证集评估
val_pred = model.predict(X_val)
val_rmse = np.sqrt(mean_squared_error(y_val, val_pred))
val_mae = mean_absolute_error(y_val, val_pred)

# 新增：注册到 ModelRegistry
registry = ModelRegistry()
registry.register(
    farm_code=farm_code,
    task_type="short",
    algorithm="lightgbm_gbdt",
    model_path=model_save_path,
    hyperparams=model.get_params(),
    val_rmse=val_rmse,
    val_mae=val_mae,
    feature_cols=list(X_train.columns),
    training_samples=len(X_train),
)
```

同理改造超短期训练脚本 `train_supershort.py`。

### Celery 任务调整

`celery_app/tasks.py` 中 `run_prediction` 任务改造：

```python
# 现有：加载固定模型文件预测
# 改为：
from fusion_engine import FusionEngine
engine = FusionEngine()
result = engine.predict(farm_code, task_type, features_df)
```

## 可扩展性设计

添加新模型只需三步：

1. **编写训练脚本**：产出 `joblib` 模型文件
2. **调用注册**：`ModelRegistry.register(algorithm="catboost", ...)`
3. **自动生效**：FusionEngine 查 DB 时自动纳入新模型

不需要修改 FusionEngine 或预测脚本。algorithm 字段是自由字符串，不做枚举限制。

## 向后兼容

- 如果 `model_versions` 表为空（新部署），退化为现有逻辑：从 `saved_models/` 目录加载模型
- 现有 `Model` 表保持不变，不影响其他功能
- 单模型预测时，FusionEngine 行为与直接 `model.predict()` 完全一致

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend-autopredict/model_registry.py` | 模型注册器 |
| 新增 | `backend-autopredict/fusion_engine.py` | 融合引擎 |
| 新增 | `backend-autopredict/db_models/model_version.py` | DB 模型 |
| 修改 | `backend-autopredict/db_models/__init__.py` | 导入新模型 |
| 修改 | `backend-autopredict/auto_scripts/scripts/short/auto_pre_train.py` | 训练后注册 |
| 修改 | `backend-autopredict/auto_scripts/scripts/middle/auto_pre_train.py` | 训练后注册 |
| 修改 | `backend-autopredict/auto_scripts/scripts/supershort/train_supershort.py` | 训练后注册 |
| 修改 | `celery_app/tasks.py` | run_prediction 使用 FusionEngine |
| 修改 | `scripts/init_prediction_tasks.py` | 初始化 model_versions 表 |
