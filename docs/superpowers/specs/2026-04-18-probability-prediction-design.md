# 概率预测（预测区间）设计文档

**日期**: 2026-04-18
**子项目**: A（概率预测）
**目标**: 让系统输出 90% 预测区间，辅助调度决策并量化模型可信度

---

## 1. 概述

当前系统只输出点预测（单一值），无法表达预测的不确定性。本功能通过分位数回归生成 90% 预测区间（5%/95% 分位数），覆盖超短期、短期、中期三个时间尺度。

**核心目标**：
1. **辅助调度决策** — 调度员看到预测不确定性范围，在高不确定性时更谨慎地安排备用容量
2. **量化模型可信度** — 系统内部用不确定性指标指导模型选择和触发重新训练

**非目标**（不在本子项目范围）：
- 满足电网考核中的置信区间要求
- 概率密度函数完整输出
- 多层级分位数（25%/50%/75% 等）

---

## 2. 技术路线

**选择**: LightGBM / XGBoost 原生分位数回归

- 短期/中期：LightGBM `objective='quantile'`，`alpha=0.05` 和 `alpha=0.95`
- 超短期：XGBoost `objective='reg:quantileerror'`，同上分位数
- 与现有训练框架一致，共用相同的特征工程和训练数据

**未选择方案及原因**：
- 融合模型方差：两种不确定性来源叠加难以校准
- Conformal Prediction：零训练成本但区间宽 20-30%，对异方差场景捕捉不够

---

## 3. 训练层改动

### 3.1 模型配置

在 `models_short.py` 和 `models_middle.py` 中新增分位数模型配置：

```python
# 与对应变体参数一致，仅修改 objective 和 alpha
QUANTILE_CONFIGS = {
    "q05": {"objective": "quantile", "alpha": 0.05},
    "q95": {"objective": "quantile", "alpha": 0.95},
}
```

对于每个算法变体（GBDT/DART/GOSS），额外训练 2 个分位数模型。训练参数（叶子数、学习率等）与点预测模型完全一致。

### 3.2 训练流程

`train_short.py` / `train_middle.py` 的 `train_model_for_dataset()` 新增参数：

```python
def train_model_for_dataset(..., quantiles=[0.05, 0.95]):
    # 1. 训练常规点预测模型（现有逻辑不变）
    # 2. 用相同数据和特征，额外训练分位数模型
    for q in quantiles:
        params = base_params.copy()
        params["objective"] = "quantile"
        params["alpha"] = q
        model_q = lgb.train(params, train_data, ...)
        joblib.dump(model_q, f"production_model_q{int(q*100):02d}.joblib")
```

**保存文件**（以短期为例）：
- `best_models/production_model.joblib` — 点预测（现有）
- `best_models/production_model_q05.joblib` — 5% 分位数
- `best_models/production_model_q95.joblib` — 95% 分位数

### 3.3 超短期训练

`train_supershort.py` 中 16 个 shift 模型，每个 shift 额外训练 2 个分位数模型：
- `shift_N/model_q05.joblib`
- `shift_N/model_q95.joblib`

XGBoost 使用 `objective='reg:quantileerror'`。

### 3.4 模型注册

分位数模型也注册到 `model_versions` 表：
- `algorithm` 字段标记为 `lightgbm_goss_q05`、`xgboost_q95` 等
- 与点预测模型通过相同的 `farm_code` + `task_type` + `trained_at` 关联

---

## 4. 预测输出与存储

### 4.1 预测流程

预测脚本加载三个模型（点预测 + q05 + q95），对同一批特征分别推理：

```python
pred = model.predict(X)
pred_lower = model_q05.predict(X)
pred_upper = model_q95.predict(X)
# 保证 lower <= pred <= upper
pred_lower = np.minimum(pred_lower, pred)
pred_upper = np.maximum(pred_upper, pred)
# 限制在 [0, capacity] 范围内
pred_lower = np.clip(pred_lower, 0, capacity)
pred_upper = np.clip(pred_upper, 0, capacity)
```

### 4.2 输出格式

CSV 从两列变为四列：

```
Timestamp, Predicted_Power, Lower_90, Upper_90
2026-04-19 00:00, 450.2, 380.5, 510.8
```

### 4.3 数据库改动

**shortl_power 表**：

| 新增列 | 类型 | 默认值 | 含义 |
|--------|------|--------|------|
| `wp_pred_lower` | Float | NULL | 90% 区间下限 |
| `wp_pred_upper` | Float | NULL | 90% 区间上限 |

**mid_power 表**：同 shortl_power，新增 `wp_pred_lower`、`wp_pred_upper`。

**supershortl_power 表**：新增 32 列（16 个偏移 × 上下限）：

| 新增列 | 类型 | 含义 |
|--------|------|------|
| `wp_pred2_lower` | Float | shift=2 的 90% 下限 |
| `wp_pred2_upper` | Float | shift=2 的 90% 上限 |
| ... | ... | 至 wp_pred17 |

**向后兼容**：新增列默认 NULL，旧数据不受影响。前端无区间数据时只画点预测线。

### 4.4 上传接口改动

`/prediction2database/batch_shortl_power`、`batch_mid_power`、`batch_supershortl_power` 接口：
- 接受可选的 `Lower_90`、`Upper_90` 列
- 缺失时存 NULL
- 不破坏现有 CSV 上传格式（只有 2 列也能正常上传）

---

## 5. 前端可视化

### 5.1 图表展示（PowerCompare.vue）

在现有预测线基础上，用 ECharts 添加预测区间色带：

- **色带**：上下限之间的半透明填充区域，颜色与预测类型一致，透明度 0.15-0.2
- **边界线**：同色虚线标注上限和下限
- **图例**：新增"90%预测区间"条目
- **降级**：数据中没有区间列时，自动隐藏色带，只显示点预测线（向后兼容）

实现方式：为每个预测类型新增一个 `areastyle` series，数据为 `[lower, upper]` 区间。

### 5.2 模型可信度指标

在 AccuracyReport 页面新增展示：

| 指标 | 含义 | 告警规则 |
|------|------|----------|
| `coverage_rate` | 实际功率落入预测区间的比例 | < 75% 或 > 95% 触发告警 |
| `interval_width` | 平均区间宽度 / 装机容量 | > 40% 建议重新训练 |
| 综合评级 | 覆盖率 85-95% 且宽度 < 30% | 可信度高 |

---

## 6. 评估层改动

### 6.1 数据库

`evaluation_metrics` 表新增列：

| 新增列 | 类型 | 含义 |
|--------|------|------|
| `coverage_rate` | Float | 覆盖率 |
| `interval_width` | Float | 区间宽度（占容量百分比） |

### 6.2 计算逻辑

在 `evaluator_model.py` 的 `ModelEvaluator` 中新增方法：

```python
def compute_interval_metrics(self, actual, lower, upper, capacity):
    in_interval = np.sum((actual >= lower) & (actual <= upper))
    coverage_rate = in_interval / len(actual)
    avg_width = np.mean(upper - lower) / capacity
    return {"coverage_rate": coverage_rate, "interval_width": avg_width}
```

当评估数据中没有区间信息时，跳过计算，字段存 NULL。

---

## 7. 文件结构总览

| 操作 | 文件 | 改动 |
|------|------|------|
| 修改 | `auto_scripts/scripts/short/models_short.py` | 新增分位数配置 |
| 修改 | `auto_scripts/scripts/short/train_short.py` | 分位数模型训练 |
| 修改 | `auto_scripts/scripts/short/predict_short.py` | 加载分位数模型，输出区间 |
| 修改 | `auto_scripts/scripts/short/auto_pre_train.py` | 注册分位数模型 |
| 修改 | `auto_scripts/scripts/middle/models_middle.py` | 同 short |
| 修改 | `auto_scripts/scripts/middle/train_middle.py` | 同 short |
| 修改 | `auto_scripts/scripts/middle/predict_middle.py` | 同 short |
| 修改 | `auto_scripts/scripts/middle/auto_pre_train.py` | 同 short |
| 修改 | `auto_scripts/scripts/supershort/train_supershort.py` | XGBoost 分位数 |
| 修改 | `auto_scripts/scripts/supershort/predict_supershort.py` | 输出区间 |
| 修改 | `backend/db_models/power.py` | 新增区间列 |
| 修改 | `backend/routes/prediction2database.py` | 接受区间列 |
| 修改 | `backend-autopredict/scripts/evaluator_model.py` | 计算区间指标 |
| 修改 | `backend-autopredict/db_models/` | evaluation_metrics 新增列 |
| 修改 | `frontend/src/components/PowerCompare.vue` | 色带可视化 |
| 修改 | `frontend/src/components/AccuracyReport.vue` | 展示可信度指标 |

---

## 8. 约束与边界

- 分位数模型与点预测模型使用完全相同的特征工程和训练数据
- 预测区间限制在 `[0, capacity]` 范围内
- `lower <= pred <= upper` 强制约束
- 新增列全部默认 NULL，不破坏现有数据
- 分位数模型训练失败不阻塞点预测（try/except 包裹）
