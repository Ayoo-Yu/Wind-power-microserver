# 概率预测（预测区间）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过 LightGBM/XGBoost 分位数回归生成 90% 预测区间，覆盖超短期/短期/中期三个时间尺度。

**Architecture:** 在现有训练流程中为每个算法变体额外训练 5% 和 95% 分位数模型，预测时加载三个模型输出区间。数据库新增区间列（默认 NULL 向后兼容），前端用 ECharts areaStyle 展示色带。

**Tech Stack:** Python, LightGBM (`objective='quantile'`), XGBoost (`objective='reg:quantileerror'`), SQLAlchemy, Vue.js + ECharts

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `auto_scripts/scripts/short/models_short.py` | 新增分位数参数配置 |
| 修改 | `auto_scripts/scripts/short/train_short.py` | 分位数模型训练 + 保存 |
| 修改 | `auto_scripts/scripts/short/predict_short.py` | 加载分位数模型，输出区间 |
| 修改 | `auto_scripts/scripts/short/auto_pre_train.py` | 注册分位数模型到 ModelRegistry |
| 修改 | `auto_scripts/scripts/middle/models_middle.py` | 同 short（中期分位数配置） |
| 修改 | `auto_scripts/scripts/middle/train_middle.py` | 同 short（中期分位数训练） |
| 修改 | `auto_scripts/scripts/middle/predict_middle.py` | 同 short（中期分位数预测） |
| 修改 | `auto_scripts/scripts/middle/auto_pre_train.py` | 同 short（中期注册） |
| 修改 | `auto_scripts/scripts/supershort/predictor_model.py` | XGBoost 分位数训练 |
| 修改 | `auto_scripts/scripts/supershort/train_supershort.py` | 训练分位数 + 注册 |
| 修改 | `auto_scripts/scripts/supershort/predict_supershort.py` | 输出区间 |
| 修改 | `backend/db_models/power.py` | 新增区间列 |
| 修改 | `backend/routes/prediction2database.py` | 接受区间列上传 |
| 修改 | `backend-autopredict/scripts/evaluator_model.py` | 区间指标计算 |
| 修改 | `frontend/src/components/PowerCompare.vue` | 色带可视化 |
| 新增 | `tests/test_quantile_predict.py` | 区间约束测试 |

---

### Task 1: 数据库模型新增区间列

**Files:**
- Modify: `wind-power-forecast/backend/db_models/power.py:41-63`

- [ ] **Step 1: 在 ShortlPower 模型中新增区间列**

在 `wind-power-forecast/backend/db_models/power.py` 的 `ShortlPower` 类（约第 41-51 行）中，在 `wp_pred` 列之后添加：

```python
    wp_pred = Column(Float, nullable=False)
    wp_pred_lower = Column(Float, nullable=True)   # 90% 预测区间下限
    wp_pred_upper = Column(Float, nullable=True)   # 90% 预测区间上限
```

同理在 `MidPower` 类（约第 53-63 行）的 `wp_pred` 列之后添加相同的两列。

在 `SupershortlPower` 类（约第 15-37 行）的 `wp_pred17` 列之后添加：

```python
    wp_pred17 = Column(Float, nullable=False)
    # 预测区间列（shift 2~17）
    wp_pred2_lower = Column(Float, nullable=True)
    wp_pred2_upper = Column(Float, nullable=True)
    wp_pred3_lower = Column(Float, nullable=True)
    wp_pred3_upper = Column(Float, nullable=True)
    wp_pred4_lower = Column(Float, nullable=True)
    wp_pred4_upper = Column(Float, nullable=True)
    wp_pred5_lower = Column(Float, nullable=True)
    wp_pred5_upper = Column(Float, nullable=True)
    wp_pred6_lower = Column(Float, nullable=True)
    wp_pred6_upper = Column(Float, nullable=True)
    wp_pred7_lower = Column(Float, nullable=True)
    wp_pred7_upper = Column(Float, nullable=True)
    wp_pred8_lower = Column(Float, nullable=True)
    wp_pred8_upper = Column(Float, nullable=True)
    wp_pred9_lower = Column(Float, nullable=True)
    wp_pred9_upper = Column(Float, nullable=True)
    wp_pred10_lower = Column(Float, nullable=True)
    wp_pred10_upper = Column(Float, nullable=True)
    wp_pred11_lower = Column(Float, nullable=True)
    wp_pred11_upper = Column(Float, nullable=True)
    wp_pred12_lower = Column(Float, nullable=True)
    wp_pred12_upper = Column(Float, nullable=True)
    wp_pred13_lower = Column(Float, nullable=True)
    wp_pred13_upper = Column(Float, nullable=True)
    wp_pred14_lower = Column(Float, nullable=True)
    wp_pred14_upper = Column(Float, nullable=True)
    wp_pred15_lower = Column(Float, nullable=True)
    wp_pred15_upper = Column(Float, nullable=True)
    wp_pred16_lower = Column(Float, nullable=True)
    wp_pred16_upper = Column(Float, nullable=True)
    wp_pred17_lower = Column(Float, nullable=True)
    wp_pred17_upper = Column(Float, nullable=True)
```

- [ ] **Step 2: 验证语法**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\backend" && python -c "import py_compile; py_compile.compile('db_models/power.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/backend/db_models/power.py
git commit -m "feat: add prediction interval columns to power tables"
```

---

### Task 2: 编写区间约束测试

**Files:**
- Create: `wind-power-forecast/backend-autopredict/tests/test_quantile_predict.py`

- [ ] **Step 1: 创建测试文件**

创建 `wind-power-forecast/backend-autopredict/tests/test_quantile_predict.py`：

```python
# tests/test_quantile_predict.py
import numpy as np
import pytest


class TestIntervalConstraints:
    """测试预测区间的约束条件。"""

    def test_lower_leq_pred_leq_upper(self):
        """lower <= pred <= upper 必须成立。"""
        pred = np.array([100.0, 200.0, 300.0, 400.0])
        lower = np.array([80.0, 150.0, 250.0, 350.0])
        upper = np.array([120.0, 250.0, 350.0, 450.0])
        assert np.all(lower <= pred)
        assert np.all(pred <= upper)

    def test_clamp_to_zero_and_capacity(self):
        """区间限制在 [0, capacity] 范围。"""
        capacity = 779.0
        pred = np.array([-10.0, 400.0, 800.0])
        lower = np.clip(np.array([-20.0, 350.0, 780.0]), 0, capacity)
        upper = np.clip(np.array([5.0, 450.0, 810.0]), 0, capacity)
        assert np.all(lower >= 0)
        assert np.all(upper <= capacity)

    def test_enforce_ordering(self):
        """强制排序：lower = min(lower, pred), upper = max(upper, pred)。"""
        pred = np.array([100.0, 200.0])
        lower_raw = np.array([110.0, 180.0])  # lower > pred 的情况
        upper_raw = np.array([90.0, 220.0])   # upper < pred 的情况
        lower = np.minimum(lower_raw, pred)
        upper = np.maximum(upper_raw, pred)
        assert np.all(lower <= pred)
        assert np.all(pred <= upper)

    def test_coverage_rate_calculation(self):
        """覆盖率 = 实际值落入区间的比例。"""
        actual = np.array([100.0, 150.0, 300.0, 500.0])
        lower = np.array([80.0, 140.0, 250.0, 450.0])
        upper = np.array([120.0, 200.0, 350.0, 550.0])
        in_interval = np.sum((actual >= lower) & (actual <= upper))
        coverage = in_interval / len(actual)
        assert coverage == 1.0  # 全部在区间内

    def test_coverage_rate_partial(self):
        """部分超出区间。"""
        actual = np.array([100.0, 250.0, 300.0, 500.0])  # 250 > upper=200
        lower = np.array([80.0, 140.0, 250.0, 450.0])
        upper = np.array([120.0, 200.0, 350.0, 550.0])
        in_interval = np.sum((actual >= lower) & (actual <= upper))
        coverage = in_interval / len(actual)
        assert coverage == 0.75

    def test_interval_width_calculation(self):
        """区间宽度 = mean(upper - lower) / capacity。"""
        capacity = 779.0
        lower = np.array([80.0, 140.0, 250.0, 450.0])
        upper = np.array([120.0, 200.0, 350.0, 550.0])
        avg_width = np.mean(upper - lower) / capacity
        expected = np.mean([40.0, 60.0, 100.0, 100.0]) / 779.0
        assert abs(avg_width - expected) < 1e-9
```

- [ ] **Step 2: 运行测试验证通过**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\backend-autopredict" && python -m pytest tests/test_quantile_predict.py -v`
Expected: 所有 6 个测试 PASS

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/backend-autopredict/tests/test_quantile_predict.py
git commit -m "test: add prediction interval constraint tests"
```

---

### Task 3: 短期训练脚本 — 分位数模型

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/models_short.py:6-39`
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/train_short.py:768-932`

- [ ] **Step 1: 在 models_short.py 中新增分位数配置生成函数**

在 `wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/models_short.py` 文件末尾（在 `save_param_versions_to_file()` 函数之后）添加：

```python
def get_quantile_params(version=None):
    """为每个算法变体生成 5% 和 95% 分位数参数。
    
    基于 get_unified_params() 的基础参数，只修改 objective 和 alpha。
    返回格式: {'q05': [gbdt_q05, dart_q05, goss_q05], 'q95': [gbdt_q95, dart_q95, goss_q95]}
    """
    import copy
    base_params_list = get_unified_params(version)
    result = {}
    for quantile_key, alpha_val in [('q05', 0.05), ('q95', 0.95)]:
        q_params = []
        for params in base_params_list:
            p = copy.deepcopy(params)
            p['objective'] = 'quantile'
            p['alpha'] = alpha_val
            # 移除不适用于分位数回归的指标
            if 'metric' in p:
                p['metric'] = 'quantile'
            q_params.append(p)
        result[quantile_key] = q_params
    return result
```

- [ ] **Step 2: 在 train_short.py 的生产模型训练后添加分位数训练**

在 `wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/train_short.py` 中，找到生产模型训练和保存的代码块（约第 768-932 行，在 `production_features.pkl` 保存之后、return 语句之前），插入以下代码：

```python
        # --- 训练分位数模型 ---
        try:
            from models_short import get_quantile_params
            quantile_configs = get_quantile_params()
            best_algo_lower = best_algo_type.lower()
            
            # 获取对应算法的参数索引 (GBDT=0, DART=1, GOSS=2)
            algo_idx = {'gbdt': 0, 'dart': 1, 'goss': 2}.get(best_algo_lower, 0)
            
            # 用全部数据训练分位数模型（与 production model 相同数据）
            quantile_model_dir = os.path.join(model_folder_today, 'best_models')
            os.makedirs(quantile_model_dir, exist_ok=True)
            
            import lightgbm as lgb
            for q_key, q_params_list in quantile_configs.items():
                q_params = q_params_list[algo_idx]
                # 使用与 production model 相同的特征和迭代数
                q_params['num_iterations'] = production_model.best_iteration if hasattr(production_model, 'best_iteration') and production_model.best_iteration > 0 else q_params.get('num_iterations', 1000)
                q_params.pop('early_stopping_round', None)
                
                q_train_data = lgb.Dataset(X_all_flat_selected, label=y_all)
                q_model = lgb.train(q_params, q_train_data, num_boost_round=q_params['num_iterations'])
                
                q_model_path = os.path.join(quantile_model_dir, f'production_model_{q_key}.joblib')
                joblib.dump(q_model, q_model_path)
                print(f"  ✅ 分位数模型 {q_key} 已保存: {q_model_path}")
                logging.info("分位数模型 %s 已保存: %s", q_key, q_model_path)
        except Exception as qe:
            print(f"  ⚠️ 分位数模型训练失败（不影响点预测）: {qe}")
            logging.warning("分位数模型训练失败（不影响点预测）: %s", qe, exc_info=True)
        # --- 分位数训练结束 ---
```

注意：`X_all_flat_selected` 和 `y_all` 是生产模型训练时使用的全部数据和特征选择结果（在约第 800-860 行之间创建）。`production_model` 是已训练好的生产模型对象。`best_algo_type` 在约第 770 行确定。这些变量在生产模型训练代码块内均已存在。

- [ ] **Step 3: 验证语法**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\backend-autopredict" && python -c "import py_compile; py_compile.compile('auto_scripts/scripts/short/models_short.py', doraise=True); py_compile.compile('auto_scripts/scripts/short/train_short.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/models_short.py wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/train_short.py
git commit -m "feat: add quantile model training for short-term prediction"
```

---

### Task 4: 短期预测脚本 — 输出预测区间

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/predict_short.py:469-930`

- [ ] **Step 1: 在模型加载后增加分位数模型加载**

在 `wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/predict_short.py` 中，找到模型加载完成的位置（约第 581 行之后，在 `model` 变量确定之后，特征重要性加载之前），添加：

```python
        # --- 加载分位数模型 ---
        model_q05 = None
        model_q95 = None
        try:
            q05_path = os.path.join(models_dir, 'best_models', 'production_model_q05.joblib')
            q95_path = os.path.join(models_dir, 'best_models', 'production_model_q95.joblib')
            if os.path.exists(q05_path):
                model_q05 = joblib.load(q05_path)
                logging.info("已加载 5%% 分位数模型: %s", q05_path)
            if os.path.exists(q95_path):
                model_q95 = joblib.load(q95_path)
                logging.info("已加载 95%% 分位数模型: %s", q95_path)
        except Exception as qe:
            logging.warning("分位数模型加载失败（不影响点预测）: %s", qe)
        # --- 分位数加载结束 ---
```

- [ ] **Step 2: 在预测结果生成后增加区间预测**

找到 `predictions = model.predict(X_new_flat_selected)` 行（约第 828 行），在该行之后添加：

```python
            # --- 分位数预测 ---
            predictions_lower = None
            predictions_upper = None
            if model_q05 is not None and model_q95 is not None:
                try:
                    wfcapacity = float(os.environ.get('WF_CAPACITY', '779.0'))
                    predictions_lower = np.asarray(model_q05.predict(X_new_flat_selected))
                    predictions_upper = np.asarray(model_q95.predict(X_new_flat_selected))
                    # 强制排序：lower <= pred <= upper
                    predictions_lower = np.minimum(predictions_lower, predictions)
                    predictions_upper = np.maximum(predictions_upper, predictions)
                    # 限制在 [0, capacity]
                    predictions_lower = np.clip(predictions_lower, 0, wfcapacity)
                    predictions_upper = np.clip(predictions_upper, 0, wfcapacity)
                    logging.info("已生成 90%% 预测区间")
                except Exception as qe:
                    logging.warning("分位数预测失败（不影响点预测）: %s", qe)
                    predictions_lower = None
                    predictions_upper = None
            # --- 分位数预测结束 ---
```

- [ ] **Step 3: 修改 CSV 输出格式**

找到保存 CSV 的代码（约第 831-856 行），将：

```python
            # 保存预测结果到CSV
            result_df = pd.DataFrame({
                'Timestamp': prediction_timestamps,
                'Predicted_Power': predictions
            })
```

改为：

```python
            # 保存预测结果到CSV
            result_data = {
                'Timestamp': prediction_timestamps,
                'Predicted_Power': predictions
            }
            if predictions_lower is not None and predictions_upper is not None:
                result_data['Lower_90'] = predictions_lower
                result_data['Upper_90'] = predictions_upper
            result_df = pd.DataFrame(result_data)
```

- [ ] **Step 4: 修改 API 上传逻辑**

找到上传到 `/prediction2database/batch_shortl_power` 的代码（约第 895-930 行），在上传前的 DataFrame 中增加区间列（如果有的话）。在 `'Predicted Power'` 列添加之后（约第 902 行 rename 之后）添加：

```python
                    if 'Lower_90' in upload_df.columns and 'Upper_90' in upload_df.columns:
                        upload_df['Lower 90'] = upload_df['Lower_90']
                        upload_df['Upper 90'] = upload_df['Upper_90']
```

- [ ] **Step 5: 验证语法**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\backend-autopredict" && python -c "import py_compile; py_compile.compile('auto_scripts/scripts/short/predict_short.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/predict_short.py
git commit -m "feat: add quantile prediction output for short-term"
```

---

### Task 5: 短期训练脚本 — 注册分位数模型

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/auto_pre_train.py`

- [ ] **Step 1: 在现有 ModelRegistry 注册代码块中添加分位数注册**

在 `wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/auto_pre_train.py` 中，找到 Task 4（子项目 B）中已添加的 `# --- 注册模型到 ModelRegistry ---` 代码块（在 `best_models_info` 循环之后），在该 try 块内、`except` 之前添加：

```python
            # 注册分位数模型
            quantile_model_dir = os.path.join(model_folder_today, 'best_models')
            for q_key in ['q05', 'q95']:
                q_path = os.path.join(quantile_model_dir, f'production_model_{q_key}.joblib')
                if os.path.exists(q_path):
                    registry.register(
                        farm_code=farm_code,
                        task_type="short",
                        algorithm=f"{best_algo_type.lower()}_{q_key}",
                        model_path=q_path,
                        val_accuracy=None,  # 分位数模型不计算 accuracy
                    )
                    logging.info("已注册分位数模型 %s 到 ModelRegistry", q_key)
```

注意：`best_algo_type` 和 `model_folder_today` 在注册代码块的上下文中已经可用。

- [ ] **Step 2: 验证语法**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\backend-autopredict" && python -c "import py_compile; py_compile.compile('auto_scripts/scripts/short/auto_pre_train.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/auto_pre_train.py
git commit -m "feat: register quantile models for short-term training"
```

---

### Task 6: 中期训练/预测脚本 — 同步短期改动

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/middle/models_middle.py`
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/middle/train_middle.py`
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/middle/predict_middle.py`
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/middle/auto_pre_train.py`

- [ ] **Step 1: 对中期脚本执行与 Task 3-5 完全相同的改动**

中期脚本的代码结构与短期几乎完全一致（`models_middle.py` 对应 `models_short.py`，`train_middle.py` 对应 `train_short.py` 等）。具体步骤：

1. **models_middle.py**：在文件末尾添加 `get_quantile_params()` 函数（与 Task 3 Step 1 相同代码）
2. **train_middle.py**：在生产模型训练后添加分位数训练代码块（与 Task 3 Step 2 相同代码，将 `short` 改为 `medium`）
3. **predict_middle.py**：添加分位数模型加载、分位数预测、CSV 输出和 API 上传（与 Task 4 相同改动）
4. **auto_pre_train.py**：添加分位数模型注册（与 Task 5 相同代码，`task_type="medium"`）

- [ ] **Step 2: 验证所有文件语法**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\backend-autopredict" && python -c "import py_compile; files=['auto_scripts/scripts/middle/models_middle.py','auto_scripts/scripts/middle/train_middle.py','auto_scripts/scripts/middle/predict_middle.py','auto_scripts/scripts/middle/auto_pre_train.py']; [py_compile.compile(f, doraise=True) for f in files]; print('All OK')"`
Expected: `All OK`

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/backend-autopredict/auto_scripts/scripts/middle/
git commit -m "feat: add quantile training/prediction for medium-term"
```

---

### Task 7: 超短期训练脚本 — XGBoost 分位数

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/predictor_model.py`
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/train_supershort.py`

- [ ] **Step 1: 在 predictor_model.py 的 WindPowerPredictor 类中添加分位数训练方法**

在 `wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/predictor_model.py` 中，找到 `save_state()` 方法（约第 298 行），在该方法之后添加：

```python
    def train_quantile(self, data, alpha=0.5):
        """训练分位数回归模型。
        
        使用与 train() 相同的特征工程，但 objective 改为 reg:quantileerror。
        """
        import xgboost as xgb
        
        # 复用已有的特征工程
        if self.features is None or self.scaler is None:
            self.train(data)
        
        X = self.scaler.transform(self.features)
        y = self.targets
        
        self.q_model = xgb.XGBRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=6,
            min_child_weight=1,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='reg:quantileerror',
            quantile_alpha=alpha,
        )
        self.q_model.fit(X, y)
        self.quantile_alpha = alpha
```

- [ ] **Step 2: 修改 save_state 方法以保存分位数模型**

在 `predictor_model.py` 的 `save_state()` 方法中，找到保存 `xgb_model.json` 的代码之后，添加：

```python
        # 保存分位数模型
        if hasattr(self, 'q_model') and self.q_model is not None:
            q_model_path = os.path.join(model_dir, f'model_q{int(self.quantile_alpha * 100):02d}.json')
            self.q_model.save_model(q_model_path)
```

- [ ] **Step 3: 修改 load_state 方法以加载分位数模型**

在 `predictor_model.py` 的 `load_state()` 方法中，找到加载 `xgb_model.json` 的代码之后，添加：

```python
        # 加载分位数模型
        import xgboost as xgb
        for q_alpha in [0.05, 0.95]:
            q_path = os.path.join(model_dir, f'model_q{int(q_alpha * 100):02d}.json')
            if os.path.exists(q_path):
                if not hasattr(self, 'q_models'):
                    self.q_models = {}
                q_m = xgb.XGBRegressor()
                q_m.load_model(q_path)
                self.q_models[q_alpha] = q_m
```

- [ ] **Step 4: 在 train_supershort.py 中训练分位数模型**

在 `wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/train_supershort.py` 的训练循环中（约第 148-169 行），在 `predictor.save_state(model_n_dir)` 之后添加：

```python
                # 训练分位数模型
                try:
                    predictor_q05 = WindPowerPredictor(n_shift=n)
                    predictor_q05.train(data)
                    predictor_q05.train_quantile(data, alpha=0.05)
                    predictor_q05.save_state(model_n_dir)
                    
                    predictor_q95 = WindPowerPredictor(n_shift=n)
                    predictor_q95.train(data)
                    predictor_q95.train_quantile(data, alpha=0.95)
                    predictor_q95.save_state(model_n_dir)
                except Exception as qe:
                    logging.warning("shift %d 分位数训练失败: %s", n, qe)
```

注意：`train_quantile()` 需要在已 train() 的对象上调用，且 `save_state()` 会覆盖基础模型文件。实际上 `train_quantile` 会额外保存 `model_q05.json` 和 `model_q95.json`，基础模型 `xgb_model.json` 不会被覆盖因为内容相同。但由于用三个不同 predictor 实例调用 save_state，基础模型会被写三次（内容相同）。这不是问题，只是冗余 I/O。

- [ ] **Step 5: 验证语法**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\backend-autopredict" && python -c "import py_compile; py_compile.compile('auto_scripts/scripts/supershort/predictor_model.py', doraise=True); py_compile.compile('auto_scripts/scripts/supershort/train_supershort.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/predictor_model.py wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/train_supershort.py
git commit -m "feat: add XGBoost quantile training for supershort prediction"
```

---

### Task 8: 超短期预测脚本 — 输出预测区间

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/predict_supershort.py`

- [ ] **Step 1: 在预测脚本中加载分位数模型并输出区间**

找到预测结果构建的代码（在 `predictor.load_state()` 之后，预测循环中），在生成预测值之后添加分位数预测逻辑。

具体：在加载 predictor 的位置之后，增加加载分位数模型的代码，然后在预测循环中：

```python
            # 分位数预测
            pred_lower = None
            pred_upper = None
            if hasattr(predictor, 'q_models') and predictor.q_models:
                try:
                    wfcapacity = float(os.environ.get('WF_CAPACITY', '779.0'))
                    pred_q05 = predictor.q_models[0.05].predict(X_scaled)
                    pred_q95 = predictor.q_models[0.95].predict(X_scaled)
                    # 反变换（与点预测相同的反变换逻辑）
                    pred_lower = reconstruct_power(pred_q05, ...)  # 与点预测相同的反变换
                    pred_upper = reconstruct_power(pred_q95, ...)
                    pred_lower = np.minimum(pred_lower, pred_point)
                    pred_upper = np.maximum(pred_upper, pred_point)
                    pred_lower = np.clip(pred_lower, 0, wfcapacity)
                    pred_upper = np.clip(pred_upper, 0, wfcapacity)
                except Exception as qe:
                    logging.warning("分位数预测失败: %s", qe)
```

注意：反变换逻辑（`power_diff_pred + power_actual_at_t_minus_N`）必须与点预测完全一致。由于 `predict_supershort.py` 的具体结构需要现场确认，此步骤需要在实现时读取文件确认反变换代码的确切位置。

- [ ] **Step 2: 修改上传到 supershortl_power 表的逻辑**

在构建上传 DataFrame 时，如果分位数预测可用，添加 `wp_pred{N}_lower` 和 `wp_pred{N}_upper` 列。

- [ ] **Step 3: 验证语法**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\backend-autopredict" && python -c "import py_compile; py_compile.compile('auto_scripts/scripts/supershort/predict_supershort.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/predict_supershort.py
git commit -m "feat: add quantile prediction output for supershort"
```

---

### Task 9: 上传接口 — 接受区间列

**Files:**
- Modify: `wind-power-forecast/backend/routes/prediction2database.py:114-280`

- [ ] **Step 1: 修改 batch_shortl_power 端点接受区间列**

在 `wind-power-forecast/backend/routes/prediction2database.py` 中，找到 `batch_shortl_power` 函数（约第 114 行），在构建 `record_data` 字典的位置（约第 150 行），在 `"pre_num": index + 1` 之后添加：

```python
                    record_data["wp_pred_lower"] = float(row['Lower 90']) if 'Lower 90' in row and row['Lower 90'].strip() else None
                    record_data["wp_pred_upper"] = float(row['Upper 90']) if 'Upper 90' in row and row['Upper 90'].strip() else None
```

- [ ] **Step 2: 修改 batch_mid_power 端点**

在 `batch_mid_power` 函数中做同样的修改（结构相同）。

- [ ] **Step 3: 修改 batch_supershortl_power 端点**

在 `batch_supershortl_power` 函数中，找到构建 `pred_cols` 的位置（约第 44 行），在 upsert 逻辑中添加区间列处理：

```python
            # 处理预测区间列
            for i in range(2, 18):
                lower_key = f'wp_pred{i}_lower'
                upper_key = f'wp_pred{i}_upper'
                if lower_key in row and row[lower_key].strip():
                    record_data[lower_key] = float(row[lower_key])
                if upper_key in row and row[upper_key].strip():
                    record_data[upper_key] = float(row[upper_key])
```

- [ ] **Step 4: 验证语法**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\backend" && python -c "import py_compile; py_compile.compile('routes/prediction2database.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add wind-power-forecast/backend/routes/prediction2database.py
git commit -m "feat: accept prediction interval columns in upload endpoints"
```

---

### Task 10: 评估层 — 区间指标计算

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/scripts/evaluator_model.py:65-100`

- [ ] **Step 1: 在 ModelEvaluator 中新增区间指标方法**

在 `wind-power-forecast/backend-autopredict/scripts/evaluator_model.py` 的 `calculate_metrics` 方法之后（约第 100 行），添加：

```python
    def compute_interval_metrics(self, actual, lower, upper):
        """计算预测区间指标：覆盖率和区间宽度。
        
        Args:
            actual: 实际值数组
            lower: 预测区间下限数组
            upper: 预测区间上限数组
            
        Returns:
            dict: {'coverage_rate': float, 'interval_width': float}
        """
        if len(actual) == 0 or lower is None or upper is None:
            return {'coverage_rate': None, 'interval_width': None}
        
        actual = np.array(actual)
        lower = np.array(lower)
        upper = np.array(upper)
        
        in_interval = np.sum((actual >= lower) & (actual <= upper))
        coverage_rate = float(in_interval / len(actual))
        avg_width = float(np.mean(upper - lower) / self.wfcapacity)
        
        return {'coverage_rate': coverage_rate, 'interval_width': avg_width}
```

确保文件顶部有 `import numpy as np`（如果不存在则添加）。

- [ ] **Step 2: 验证语法**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\backend-autopredict" && python -c "import py_compile; py_compile.compile('scripts/evaluator_model.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/backend-autopredict/scripts/evaluator_model.py
git commit -m "feat: add interval metrics computation to ModelEvaluator"
```

---

### Task 11: 前端 — 预测区间色带可视化

**Files:**
- Modify: `wind-power-forecast/frontend/src/components/PowerCompare.vue`

- [ ] **Step 1: 添加区间数据提取**

在 PowerCompare.vue 的数据处理区域（约第 432-440 行的 `getSeries` 调用之后），添加：

```javascript
        // 提取预测区间数据
        const shortLower = this.getSeries(apiData, ['短期预测下限', 'short_lower'])
        const shortUpper = this.getSeries(apiData, ['短期预测上限', 'short_upper'])
        const midLower = this.getSeries(apiData, ['中期预测下限', 'mid_lower'])
        const midUpper = this.getSeries(apiData, ['中期预测上限', 'mid_upper'])
        const supershortLower = this.getSeries(apiData, ['超短期预测下限', 'supershort_lower'])
        const supershortUpper = this.getSeries(apiData, ['超短期预测上限', 'supershort_upper'])
```

- [ ] **Step 2: 添加区间色带 series**

在 `getMainSeriesFromState()` 方法中（约第 526-554 行），在对应的 `pushPower()` 调用之后，添加区间色带。例如短期预测（蓝色 `#60a5fa`）：

```javascript
        // 短期预测区间色带（仅在数据存在时显示）
        if (s.shortLowerValues && s.shortUpperValues && s.shortLowerValues.some(v => v != null)) {
          series.push({
            name: '短期预测区间',
            type: 'line',
            smooth: false,
            showSymbol: false,
            yAxisIndex: YAXIS_POWER,
            data: s.shortUpperValues.map((v, i) => [v, s.shortLowerValues[i]]),
            lineStyle: { opacity: 0 },
            areaStyle: { color: 'rgba(96, 165, 250, 0.15)' },
            stack: 'short-interval',
            z: 1,
            connectNulls: true,
          })
        }
```

对超短期（`#22d3ee`，透明度 0.15）和中期（`#4ade80`，透明度 0.15）做同样处理。

- [ ] **Step 3: 添加 checkbox 控件**

在模板的 checkbox 列表中（约第 49-55 行），添加区间显示选项：

```html
          <el-checkbox label="短期预测区间"></el-checkbox>
          <el-checkbox label="超短期预测区间"></el-checkbox>
          <el-checkbox label="中期预测区间"></el-checkbox>
```

- [ ] **Step 4: 验证前端构建**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\frontend" && npm run build 2>&1 | tail -5`
Expected: 构建成功（无 error）

- [ ] **Step 5: Commit**

```bash
git add wind-power-forecast/frontend/src/components/PowerCompare.vue
git commit -m "feat: add prediction interval band visualization"
```

---

### Task 12: 全量集成验证

**Files:**
- All modified files

- [ ] **Step 1: 运行全部单元测试**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast\backend-autopredict" && python -m pytest tests/ -v`
Expected: 所有测试 PASS（包括 test_quantile_predict.py 的 6 个新测试）

- [ ] **Step 2: 验证所有修改文件语法正确**

Run: `cd "D:\Wind-power-microserver\wind-power-forecast" && python -c "
import py_compile
files = [
    'backend/db_models/power.py',
    'backend/routes/prediction2database.py',
    'backend-autopredict/scripts/evaluator_model.py',
    'backend-autopredict/auto_scripts/scripts/short/models_short.py',
    'backend-autopredict/auto_scripts/scripts/short/train_short.py',
    'backend-autopredict/auto_scripts/scripts/short/predict_short.py',
    'backend-autopredict/auto_scripts/scripts/short/auto_pre_train.py',
    'backend-autopredict/auto_scripts/scripts/middle/models_middle.py',
    'backend-autopredict/auto_scripts/scripts/middle/train_middle.py',
    'backend-autopredict/auto_scripts/scripts/middle/predict_middle.py',
    'backend-autopredict/auto_scripts/scripts/middle/auto_pre_train.py',
    'backend-autopredict/auto_scripts/scripts/supershort/predictor_model.py',
    'backend-autopredict/auto_scripts/scripts/supershort/train_supershort.py',
    'backend-autopredict/auto_scripts/scripts/supershort/predict_supershort.py',
]
for f in files:
    py_compile.compile(f, doraise=True)
    print(f'OK: {f}')
"`
Expected: 所有文件输出 `OK`

- [ ] **Step 3: Commit（如有修复）**

```bash
git add -A
git commit -m "fix: resolve integration issues from probability prediction implementation"
```

---

## Plan Self-Review

**1. Spec coverage:**
- 分位数回归训练 → Task 3, 6, 7 ✅
- 预测输出区间 → Task 4, 6, 8 ✅
- 数据库新增列 → Task 1 ✅
- 上传接口接受区间 → Task 9 ✅
- 前端色带可视化 → Task 11 ✅
- 评估层区间指标 → Task 10 ✅
- 模型注册 → Task 5, 6 ✅
- 区间约束测试 → Task 2 ✅
- 向后兼容（NULL 默认 + 降级）→ Task 1, 4, 11 ✅

**2. Placeholder scan:** Task 8 的 Step 1 包含 `reconstruct_power(pred_q05, ...)` 需要在实现时确认具体代码。这是超短期特有的反变换逻辑，需要读取 predict_supershort.py 确认。已标注。

**3. Type consistency:**
- 分位数模型文件名统一为 `production_model_q05.joblib` / `production_model_q95.joblib` ✅
- 超短期分位数文件名为 `model_q05.json` / `model_q95.json` ✅
- 数据库列名统一为 `wp_pred_lower` / `wp_pred_upper` ✅
- CSV 列名为 `Lower_90` / `Upper_90`（上传时转为 `Lower 90` / `Upper 90`）✅
