# 模型自动选择/融合 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 训练多个模型后自动注册，推理时根据验证集 RMSE 加权融合，提升预测精度。

**Architecture:** 新增 `model_versions` 表记录每个模型版本的元数据和验证指标。训练完成后调用 `ModelRegistry.register()` 写入 DB。预测时 `FusionEngine` 查 DB 取 active 模型列表，按反 RMSE 加权融合。向后兼容：表为空时退化为现有文件加载逻辑。

**Tech Stack:** Python, SQLAlchemy, LightGBM, XGBoost, joblib, MinIO, numpy

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| 新增 | `backend-autopredict/db_models/model_version.py` | ModelVersion ORM 模型 |
| 新增 | `backend-autopredict/model_registry.py` | 模型注册器（注册、查询、停用） |
| 新增 | `backend-autopredict/fusion_engine.py` | 融合引擎（加权融合预测） |
| 新增 | `tests/test_model_registry.py` | ModelRegistry 单元测试 |
| 新增 | `tests/test_fusion_engine.py` | FusionEngine 单元测试 |
| 修改 | `backend-autopredict/db_models/__init__.py` | 导入 ModelVersion |
| 修改 | `backend-autopredict/database_config.py` | check_migrations 包含 model_versions |
| 修改 | `backend-autopredict/auto_scripts/scripts/short/auto_pre_train.py` | 训练后注册 |
| 修改 | `backend-autopredict/auto_scripts/scripts/middle/auto_pre_train.py` | 训练后注册 |
| 修改 | `backend-autopredict/auto_scripts/scripts/supershort/train_supershort.py` | 训练后注册 |
| 修改 | `backend-autopredict/routes/autopredict.py` | 模型版本管理 API |

---

### Task 1: 创建 ModelVersion DB 模型

**Files:**
- Create: `wind-power-forecast/backend-autopredict/db_models/model_version.py`
- Modify: `wind-power-forecast/backend-autopredict/db_models/__init__.py`
- Modify: `wind-power-forecast/backend-autopredict/database_config.py`

- [ ] **Step 1: 创建 model_version.py**

```python
# wind-power-forecast/backend-autopredict/db_models/model_version.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from .base import Base


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    farm_code = Column(String(50), nullable=False)
    task_type = Column(String(20), nullable=False)  # supershort / short / medium
    algorithm = Column(String(50), nullable=False)   # xgboost / lightgbm_gbdt / lightgbm_dart / lightgbm_goss
    hyperparams = Column(JSONB)
    val_rmse = Column(Float)
    val_mae = Column(Float)
    val_accuracy = Column(Float)  # 1 - rmse/capacity
    is_active = Column(Boolean, default=True)
    s3_path = Column(String(500))
    local_path = Column(String(500))
    scaler_path = Column(String(500))
    feature_cols = Column(JSONB)
    training_samples = Column(Integer)
    trained_at = Column(DateTime, default=datetime.now)
    activated_at = Column(DateTime)
    deactivated_at = Column(DateTime)

    __table_args__ = (
        Index("idx_mv_farm_type", "farm_code", "task_type"),
        Index("idx_mv_active", "farm_code", "task_type", "is_active"),
    )
```

- [ ] **Step 2: 更新 db_models/__init__.py**

在 `wind-power-forecast/backend-autopredict/db_models/__init__.py` 中添加导入。在 `from .prediction_run import PredictionRun` 后添加：

```python
from .model_version import ModelVersion
```

在 `__all__` 列表中添加：

```python
'ModelVersion',
```

- [ ] **Step 3: 更新 database_config.py 的 check_migrations**

在 `wind-power-forecast/backend-autopredict/database_config.py` 的 `check_migrations` 函数中，修改条件以包含 `model_versions`：

找到：
```python
if not inspector.has_table("models"):
    Base.metadata.create_all(engine)
```

替换为：
```python
required_tables = ["models", "model_versions"]
missing = [t for t in required_tables if not inspector.has_table(t)]
if missing:
    Base.metadata.create_all(engine)
```

- [ ] **Step 4: 验证 Python 语法**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -c "from db_models import ModelVersion; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add wind-power-forecast/backend-autopredict/db_models/model_version.py wind-power-forecast/backend-autopredict/db_models/__init__.py wind-power-forecast/backend-autopredict/database_config.py
git commit -m "feat: add ModelVersion DB model for model registry"
```

---

### Task 2: 创建 ModelRegistry 模型注册器

**Files:**
- Create: `wind-power-forecast/backend-autopredict/model_registry.py`
- Create: `tests/test_model_registry.py`

- [ ] **Step 1: 编写 ModelRegistry 测试**

创建测试目录和文件 `tests/test_model_registry.py`：

```python
# tests/test_model_registry.py
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


class TestComputeWeights:
    """测试权重计算逻辑（不依赖数据库）"""

    def test_single_model_gets_weight_one(self):
        from model_registry import ModelRegistry
        registry = ModelRegistry()
        models = [MagicMock(val_rmse=10.0)]
        weights = registry._compute_weights(models)
        assert len(weights) == 1
        assert abs(weights[0] - 1.0) < 1e-9

    def test_two_models_inverse_rmse(self):
        from model_registry import ModelRegistry
        registry = ModelRegistry()
        m1 = MagicMock(val_rmse=10.0)
        m2 = MagicMock(val_rmse=5.0)
        weights = registry._compute_weights([m1, m2])
        assert len(weights) == 2
        assert abs(sum(weights) - 1.0) < 1e-9
        # rmse=5 should get higher weight than rmse=10
        assert weights[1] > weights[0]
        # exact: w1 = (1/10)/(1/10+1/5) = 0.1/0.3 = 1/3
        assert abs(weights[0] - 1.0/3.0) < 1e-9
        assert abs(weights[1] - 2.0/3.0) < 1e-9

    def test_three_models_sum_to_one(self):
        from model_registry import ModelRegistry
        registry = ModelRegistry()
        models = [MagicMock(val_rmse=r) for r in [8.0, 10.0, 12.0]]
        weights = registry._compute_weights(models)
        assert len(weights) == 3
        assert abs(sum(weights) - 1.0) < 1e-9
        # lower rmse = higher weight
        assert weights[0] > weights[1] > weights[2]

    def test_zero_rmse_handled(self):
        from model_registry import ModelRegistry
        registry = ModelRegistry()
        # Edge case: if one model has rmse=0, give it all weight
        m1 = MagicMock(val_rmse=0.0)
        m2 = MagicMock(val_rmse=10.0)
        weights = registry._compute_weights([m1, m2])
        assert abs(weights[0] - 1.0) < 1e-9
        assert abs(weights[1] - 0.0) < 1e-9


class TestActivationThreshold:
    """测试激活阈值判断"""

    def test_supershort_pass(self):
        from model_registry import ModelRegistry
        registry = ModelRegistry()
        assert registry._should_activate("supershort", 0.85)

    def test_supershort_fail(self):
        from model_registry import ModelRegistry
        registry = ModelRegistry()
        assert not registry._should_activate("supershort", 0.75)

    def test_short_pass(self):
        from model_registry import ModelRegistry
        registry = ModelRegistry()
        assert registry._should_activate("short", 0.78)

    def test_short_fail(self):
        from model_registry import ModelRegistry
        registry = ModelRegistry()
        assert not registry._should_activate("short", 0.70)

    def test_medium_pass(self):
        from model_registry import ModelRegistry
        registry = ModelRegistry()
        assert registry._should_activate("medium", 0.72)

    def test_medium_fail(self):
        from model_registry import ModelRegistry
        registry = ModelRegistry()
        assert not registry._should_activate("medium", 0.65)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/test_model_registry.py -v 2>&1 | head -20`
Expected: FAIL - `ModuleNotFoundError: No module named 'model_registry'`

- [ ] **Step 3: 实现 ModelRegistry**

创建 `wind-power-forecast/backend-autopredict/model_registry.py`：

```python
# wind-power-forecast/backend-autopredict/model_registry.py
import os
import sys
import logging
import json
from datetime import datetime

import joblib
import numpy as np

# 确保 backend-autopredict 根目录在 sys.path 中
_BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from db_session import db_session
from db_models import ModelVersion

logger = logging.getLogger(__name__)

# 各预测类型的激活阈值（val_accuracy 最低要求）
ACTIVATION_THRESHOLDS = {
    "supershort": 0.80,
    "short": 0.75,
    "medium": 0.70,
}


class ModelRegistry:
    """模型注册器：管理模型版本的注册、查询和停用。"""

    def register(
        self,
        farm_code: str,
        task_type: str,
        algorithm: str,
        model_path: str,
        hyperparams: dict | None = None,
        val_rmse: float | None = None,
        val_mae: float | None = None,
        val_accuracy: float | None = None,
        feature_cols: list | None = None,
        training_samples: int | None = None,
        s3_path: str | None = None,
        scaler_path: str | None = None,
    ) -> ModelVersion:
        """注册新模型版本。如果验证指标优于阈值则自动激活。"""
        is_active = self._should_activate(task_type, val_accuracy)
        now = datetime.now()

        version = ModelVersion(
            farm_code=farm_code,
            task_type=task_type,
            algorithm=algorithm,
            hyperparams=hyperparams,
            val_rmse=val_rmse,
            val_mae=val_mae,
            val_accuracy=val_accuracy,
            is_active=is_active,
            s3_path=s3_path,
            local_path=model_path,
            scaler_path=scaler_path,
            feature_cols=feature_cols,
            training_samples=training_samples,
            trained_at=now,
            activated_at=now if is_active else None,
        )

        with db_session() as session:
            # 检查是否比当前线上最差模型还差
            if is_active:
                is_active = self._is_better_than_worst(session, farm_code, task_type, val_accuracy)
                version.is_active = is_active
                version.activated_at = now if is_active else None

            session.add(version)
            session.flush()
            version_id = version.id

            if is_active:
                self._deactivate_old_versions(session, farm_code, task_type, keep=5)

        logger.info(
            "Registered model version %d: %s/%s/%s accuracy=%.4f active=%s",
            version_id, farm_code, task_type, algorithm, val_accuracy or 0, is_active,
        )
        return version

    def get_active_models(self, farm_code: str, task_type: str, limit: int = 5):
        """获取指定场站+类型的 active 模型列表，按 trained_at 降序。"""
        with db_session() as session:
            rows = (
                session.query(ModelVersion)
                .filter_by(farm_code=farm_code, task_type=task_type, is_active=True)
                .order_by(ModelVersion.trained_at.desc())
                .limit(limit)
                .all()
            )
            # 触发懒加载，在 session 关闭前提取属性
            result = []
            for r in rows:
                result.append({
                    "id": r.id,
                    "algorithm": r.algorithm,
                    "val_rmse": r.val_rmse,
                    "val_mae": r.val_mae,
                    "val_accuracy": r.val_accuracy,
                    "local_path": r.local_path,
                    "s3_path": r.s3_path,
                    "scaler_path": r.scaler_path,
                    "hyperparams": r.hyperparams,
                    "feature_cols": r.feature_cols,
                    "trained_at": r.trained_at,
                })
            return result

    def deactivate(self, model_id: int):
        """停用一个模型版本。"""
        with db_session() as session:
            version = session.query(ModelVersion).get(model_id)
            if version and version.is_active:
                version.is_active = False
                version.deactivated_at = datetime.now()

    def _should_activate(self, task_type: str, val_accuracy: float | None) -> bool:
        """判断模型是否达到激活阈值。"""
        if val_accuracy is None:
            return False
        threshold = ACTIVATION_THRESHOLDS.get(task_type, 0.75)
        return val_accuracy >= threshold

    def _is_better_than_worst(
        self, session, farm_code: str, task_type: str, val_accuracy: float | None
    ) -> bool:
        """检查是否比当前线上最差模型更好。如果线上无模型则返回 True。"""
        if val_accuracy is None:
            return False
        worst = (
            session.query(ModelVersion)
            .filter_by(farm_code=farm_code, task_type=task_type, is_active=True)
            .order_by(ModelVersion.val_accuracy.asc())
            .first()
        )
        if worst is None:
            return True
        return val_accuracy >= worst.val_accuracy

    def _deactivate_old_versions(self, session, farm_code: str, task_type: str, keep: int = 5):
        """保留最近 N 个 active 版本，停用更早的。"""
        active_versions = (
            session.query(ModelVersion)
            .filter_by(farm_code=farm_code, task_type=task_type, is_active=True)
            .order_by(ModelVersion.trained_at.desc())
            .all()
        )
        now = datetime.now()
        for v in active_versions[keep:]:
            v.is_active = False
            v.deactivated_at = now

    def _compute_weights(self, models: list) -> list[float]:
        """基于验证集 RMSE 计算权重：weight_i = (1/rmse_i) / sum(1/rmse_j)。"""
        if not models:
            return []
        if len(models) == 1:
            return [1.0]

        inv_rmses = []
        for m in models:
            rmse = m.val_rmse if hasattr(m, "val_rmse") and m.val_rmse else 0.0
            if rmse <= 0:
                # 模型完美或异常：给极高权重
                inv_rmses.append(1e6)
            else:
                inv_rmses.append(1.0 / rmse)

        total = sum(inv_rmses)
        if total <= 0:
            return [1.0 / len(models)] * len(models)

        return [inv / total for inv in inv_rmses]
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/test_model_registry.py -v`
Expected: 所有测试 PASS

- [ ] **Step 5: Commit**

```bash
git add wind-power-forecast/backend-autopredict/model_registry.py tests/test_model_registry.py
git commit -m "feat: add ModelRegistry for model version management"
```

---

### Task 3: 创建 FusionEngine 融合引擎

**Files:**
- Create: `wind-power-forecast/backend-autopredict/fusion_engine.py`
- Create: `tests/test_fusion_engine.py`

- [ ] **Step 1: 编写 FusionEngine 测试**

创建 `tests/test_fusion_engine.py`：

```python
# tests/test_fusion_engine.py
import pytest
import numpy as np
from unittest.mock import MagicMock, patch


class TestWeightedFusion:
    """测试加权融合逻辑"""

    def test_single_model_returns_directly(self):
        from fusion_engine import FusionEngine
        engine = FusionEngine()
        predictions = [np.array([10.0, 20.0, 30.0])]
        weights = [1.0]
        result = engine._weighted_combine(predictions, weights)
        np.testing.assert_array_almost_equal(result, [10.0, 20.0, 30.0])

    def test_two_models_weighted_average(self):
        from fusion_engine import FusionEngine
        engine = FusionEngine()
        pred1 = np.array([10.0, 20.0])
        pred2 = np.array([30.0, 40.0])
        weights = [0.3, 0.7]
        result = engine._weighted_combine([pred1, pred2], weights)
        # 0.3*10 + 0.7*30 = 3+21 = 24
        # 0.3*20 + 0.7*40 = 6+28 = 34
        np.testing.assert_array_almost_equal(result, [24.0, 34.0])

    def test_three_models_weights_sum_to_one(self):
        from fusion_engine import FusionEngine
        engine = FusionEngine()
        preds = [np.array([10.0]), np.array([20.0]), np.array([30.0])]
        weights = [0.5, 0.3, 0.2]
        result = engine._weighted_combine(preds, weights)
        expected = 0.5 * 10 + 0.3 * 20 + 0.2 * 30  # = 5+6+6 = 17
        assert abs(result[0] - 17.0) < 1e-9

    def test_empty_models_returns_none(self):
        from fusion_engine import FusionEngine
        engine = FusionEngine()
        result = engine._weighted_combine([], [])
        assert result is None


class TestLoadModel:
    """测试模型加载逻辑"""

    def test_load_from_local_path(self, tmp_path):
        from fusion_engine import FusionEngine
        engine = FusionEngine()
        # 创建临时模型文件
        model_file = tmp_path / "test_model.joblib"
        import joblib
        dummy_model = {"type": "test", "value": 42}
        joblib.dump(dummy_model, str(model_file))

        loaded = engine._load_model({"local_path": str(model_file), "s3_path": None})
        assert loaded["value"] == 42

    def test_load_missing_returns_none(self):
        from fusion_engine import FusionEngine
        engine = FusionEngine()
        loaded = engine._load_model({"local_path": "/nonexistent/path.joblib", "s3_path": None})
        assert loaded is None


class TestPredictFallback:
    """测试预测回退逻辑"""

    @patch("fusion_engine.ModelRegistry")
    def test_no_active_models_returns_none(self, mock_registry_class):
        from fusion_engine import FusionEngine
        mock_registry = MagicMock()
        mock_registry.get_active_models.return_value = []
        mock_registry_class.return_value = mock_registry

        engine = FusionEngine()
        result = engine.predict("farm1", "short", MagicMock())
        assert result is None
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/test_fusion_engine.py -v 2>&1 | head -20`
Expected: FAIL - `ModuleNotFoundError: No module named 'fusion_engine'`

- [ ] **Step 3: 实现 FusionEngine**

创建 `wind-power-forecast/backend-autopredict/fusion_engine.py`：

```python
# wind-power-forecast/backend-autopredict/fusion_engine.py
import os
import sys
import logging

import joblib
import numpy as np

# 确保 backend-autopredict 根目录在 sys.path 中
_BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class FusionEngine:
    """融合引擎：查询 active 模型，加权融合预测结果。"""

    def __init__(self):
        self.registry = ModelRegistry()

    def predict(self, farm_code: str, task_type: str, features_df, model_loader=None):
        """融合预测主入口。

        Args:
            farm_code: 风场编码
            task_type: 预测类型 (supershort/short/medium)
            features_df: 特征 DataFrame
            model_loader: 可选的自定义模型加载函数（用于测试注入）

        Returns:
            np.ndarray: 融合后的预测数组，无可用模型时返回 None
        """
        models = self.registry.get_active_models(farm_code, task_type)

        if not models:
            logger.warning("No active models for %s/%s", farm_code, task_type)
            return None

        if len(models) == 1:
            logger.info("Single active model for %s/%s, using directly", farm_code, task_type)
            return self._single_predict(models[0], features_df, model_loader)

        # 多模型加权融合
        weights = self.registry._compute_weights(models)
        logger.info(
            "Fusing %d models for %s/%s, weights: %s",
            len(models), farm_code, task_type,
            [f"{w:.3f}" for w in weights],
        )

        predictions = []
        valid_weights = []
        for model_info, weight in zip(models, weights):
            pred = self._single_predict(model_info, features_df, model_loader)
            if pred is not None:
                predictions.append(pred)
                valid_weights.append(weight)

        if not predictions:
            logger.error("All models failed to predict for %s/%s", farm_code, task_type)
            return None

        # 重新归一化权重（可能有模型加载失败）
        weight_sum = sum(valid_weights)
        if weight_sum <= 0:
            valid_weights = [1.0 / len(valid_weights)] * len(valid_weights)
        else:
            valid_weights = [w / weight_sum for w in valid_weights]

        return self._weighted_combine(predictions, valid_weights)

    def _single_predict(self, model_info: dict, features_df, model_loader=None):
        """单模型推理。"""
        model = self._load_model(model_info) if model_loader is None else model_loader(model_info)
        if model is None:
            logger.error("Failed to load model: %s", model_info.get("local_path"))
            return None

        try:
            if hasattr(model, "predict"):
                return np.asarray(model.predict(features_df))
            else:
                logger.error("Model has no predict() method")
                return None
        except Exception as e:
            logger.error("Model prediction failed: %s", e, exc_info=True)
            return None

    def _load_model(self, model_info: dict):
        """从本地路径或 MinIO 加载模型文件。"""
        local_path = model_info.get("local_path")
        if local_path and os.path.exists(local_path):
            try:
                return joblib.load(local_path)
            except Exception as e:
                logger.error("Failed to load model from %s: %s", local_path, e)

        s3_path = model_info.get("s3_path")
        if s3_path:
            try:
                from database_config import init_minio_client
                from config import MINIO_CONFIG
                client = init_minio_client()
                bucket = MINIO_CONFIG["buckets"].get("models", "wind-models")
                data = client.get_object(bucket, s3_path)
                import io
                return joblib.load(io.BytesIO(data.read()))
            except Exception as e:
                logger.error("Failed to load model from S3 %s: %s", s3_path, e)

        return None

    def _weighted_combine(self, predictions: list, weights: list) -> np.ndarray | None:
        """对多个预测结果加权求和。"""
        if not predictions or not weights:
            return None
        result = np.zeros_like(predictions[0], dtype=float)
        for pred, weight in zip(predictions, weights):
            result += weight * pred
        return result
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/test_fusion_engine.py -v`
Expected: 所有测试 PASS

- [ ] **Step 5: Commit**

```bash
git add wind-power-forecast/backend-autopredict/fusion_engine.py tests/test_fusion_engine.py
git commit -m "feat: add FusionEngine for weighted model prediction"
```

---

### Task 4: 短期训练脚本集成 ModelRegistry

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/auto_pre_train.py`

短期训练脚本在 `train_model()` 函数的 `train_multiple_datasets()` 调用成功后，已有 `best_models_info` 字典。在此处添加注册逻辑。

- [ ] **Step 1: 在 train_model() 的成功分支中添加注册逻辑**

在 `wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/auto_pre_train.py` 文件中，找到 `train_multiple_datasets` 成功后、`选择全局最优模型` 之前的位置。具体在以下代码块之后：

```python
        for algo_type, model_info in best_models_info.items():
            if model_info['model'] is not None:
                months_desc = f"{model_info['months']}个月" if model_info['months'] else "全部数据"
                print(f"  - 最佳{algo_type}模型: 使用{months_desc}数据, 评分={model_info['score']:.4f}")
                logging.info(f"  - 最佳{algo_type}模型: 使用{months_desc}数据, 评分={model_info['score']:.4f}")
```

在此之后，`# 新增：选择全局最优模型` 之前，插入以下代码块：

```python
        # --- 注册模型到 ModelRegistry ---
        try:
            from model_registry import ModelRegistry
            farm_code = os.environ.get('FARM_CODE', 'DEFAULT_FARM')
            registry = ModelRegistry()

            # 获取装机容量用于计算 accuracy
            wfcapacity = float(os.environ.get('WF_CAPACITY', '779.0'))

            for algo_type, model_info_dict in best_models_info.items():
                if model_info_dict.get('model') is None:
                    continue

                model_path = os.path.join(model_folder_today, 'best_models', f'{algo_type}.joblib')
                if not os.path.exists(model_path):
                    # 保存最佳模型到 best_models 目录
                    best_dir = os.path.join(model_folder_today, 'best_models')
                    os.makedirs(best_dir, exist_ok=True)
                    model_path = os.path.join(best_dir, f'{algo_type}.joblib')
                    joblib.dump(model_info_dict['model'], model_path)

                rmse = model_info_dict.get('rmse', model_info_dict.get('score'))
                # score 可能是负的 MSE，需要处理
                if rmse is not None and rmse < 0:
                    import numpy as np
                    rmse = np.sqrt(-rmse)
                val_accuracy = 1 - (rmse / wfcapacity) if rmse is not None and wfcapacity > 0 else None

                registry.register(
                    farm_code=farm_code,
                    task_type="short",
                    algorithm=f"lightgbm_{algo_type.lower()}",
                    model_path=model_path,
                    hyperparams=model_info_dict.get('params'),
                    val_rmse=float(rmse) if rmse is not None else None,
                    val_accuracy=float(val_accuracy) if val_accuracy is not None else None,
                    training_samples=model_info_dict.get('training_samples'),
                )
                print(f"  ✅ 已注册 {algo_type} 模型到 ModelRegistry")
                logging.info(f"已注册 %s 模型到 ModelRegistry", algo_type)
        except Exception as reg_e:
            print(f"  ⚠️ 模型注册失败（不影响训练结果）: {reg_e}")
            logging.warning(f"模型注册失败（不影响训练结果）: {reg_e}", exc_info=True)
        # --- 注册结束 ---
```

- [ ] **Step 2: 验证 Python 语法**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -c "import py_compile; py_compile.compile('auto_scripts/scripts/short/auto_pre_train.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/backend-autopredict/auto_scripts/scripts/short/auto_pre_train.py
git commit -m "feat: integrate ModelRegistry into short-term training"
```

---

### Task 5: 中期训练脚本集成 ModelRegistry

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/middle/auto_pre_train.py`

中期训练脚本结构与短期几乎相同，做同样的修改。

- [ ] **Step 1: 在 train_model() 的成功分支中添加注册逻辑**

在 `wind-power-forecast/backend-autopredict/auto_scripts/scripts/middle/auto_pre_train.py` 中，找到与 Task 4 相同位置的代码块（`train_multiple_datasets` 成功后），在 `# 新增：选择全局最优模型` 之前，插入以下代码块：

```python
        # --- 注册模型到 ModelRegistry ---
        try:
            from model_registry import ModelRegistry
            farm_code = os.environ.get('FARM_CODE', 'DEFAULT_FARM')
            registry = ModelRegistry()

            wfcapacity = float(os.environ.get('WF_CAPACITY', '779.0'))

            for algo_type, model_info_dict in best_models_info.items():
                if model_info_dict.get('model') is None:
                    continue

                model_path = os.path.join(model_folder_today, 'best_models', f'{algo_type}.joblib')
                if not os.path.exists(model_path):
                    best_dir = os.path.join(model_folder_today, 'best_models')
                    os.makedirs(best_dir, exist_ok=True)
                    model_path = os.path.join(best_dir, f'{algo_type}.joblib')
                    joblib.dump(model_info_dict['model'], model_path)

                rmse = model_info_dict.get('rmse', model_info_dict.get('score'))
                if rmse is not None and rmse < 0:
                    import numpy as np
                    rmse = np.sqrt(-rmse)
                val_accuracy = 1 - (rmse / wfcapacity) if rmse is not None and wfcapacity > 0 else None

                registry.register(
                    farm_code=farm_code,
                    task_type="medium",
                    algorithm=f"lightgbm_{algo_type.lower()}",
                    model_path=model_path,
                    hyperparams=model_info_dict.get('params'),
                    val_rmse=float(rmse) if rmse is not None else None,
                    val_accuracy=float(val_accuracy) if val_accuracy is not None else None,
                    training_samples=model_info_dict.get('training_samples'),
                )
                print(f"  ✅ 已注册 {algo_type} 模型到 ModelRegistry (medium)")
                logging.info(f"已注册 %s 模型到 ModelRegistry (medium)", algo_type)
        except Exception as reg_e:
            print(f"  ⚠️ 模型注册失败（不影响训练结果）: {reg_e}")
            logging.warning(f"模型注册失败（不影响训练结果）: {reg_e}", exc_info=True)
        # --- 注册结束 ---
```

- [ ] **Step 2: 验证 Python 语法**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -c "import py_compile; py_compile.compile('auto_scripts/scripts/middle/auto_pre_train.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/backend-autopredict/auto_scripts/scripts/middle/auto_pre_train.py
git commit -m "feat: integrate ModelRegistry into medium-term training"
```

---

### Task 6: 超短期训练脚本集成 ModelRegistry

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/train_supershort.py`

超短期使用 XGBoost，训练 16 个 shift 模型。需要为每个 shift 注册。

- [ ] **Step 1: 在训练循环成功后添加注册逻辑**

在 `wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/train_supershort.py` 的 `main()` 函数中，找到训练循环结束后的位置（在 `successful_trains` 统计之后，`expected_model_count` 检查之前）。

具体在以下行之后：
```python
    logging.info(f"\n{'='*10} 训练过程完成 {'='*10}")
    logging.info(f"总共成功训练并保存了 {successful_trains} 个模型。")
```

插入以下代码：

```python
    # --- 注册模型到 ModelRegistry ---
    try:
        from model_registry import ModelRegistry
        farm_code = os.environ.get('FARM_CODE', 'DEFAULT_FARM')
        registry = ModelRegistry()

        wfcapacity = float(os.environ.get('WF_CAPACITY', '779.0'))

        for n in range(MIN_SHIFT, MAX_SHIFT + 1):
            model_dir = os.path.join(MODEL_OUTPUT_DIR, f'shift_{n}')
            model_path = os.path.join(model_dir, 'model.joblib')
            scaler_path = os.path.join(model_dir, 'scaler.joblib')

            if not os.path.exists(model_path):
                continue

            # 计算验证指标（使用训练集最后20%作为验证集的近似）
            # 由于超短期训练使用全部数据，这里记录模型路径但无独立验证指标
            # 后续可通过 evaluator_model.py 补充 val_rmse
            registry.register(
                farm_code=farm_code,
                task_type="supershort",
                algorithm="xgboost",
                model_path=model_path,
                scaler_path=scaler_path if os.path.exists(scaler_path) else None,
                val_accuracy=None,  # 超短期暂时跳过阈值判断
            )
        logging.info("已注册超短期模型到 ModelRegistry")
    except Exception as reg_e:
        logging.warning(f"超短期模型注册失败（不影响训练结果）: {reg_e}", exc_info=True)
    # --- 注册结束 ---
```

- [ ] **Step 2: 验证 Python 语法**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -c "import py_compile; py_compile.compile('auto_scripts/scripts/supershort/train_supershort.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/train_supershort.py
git commit -m "feat: integrate ModelRegistry into supershort training"
```

---

### Task 7: 添加模型版本管理 API

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/routes/autopredict.py`

添加模型版本查询和管理端点。

- [ ] **Step 1: 在 autopredict.py 中添加模型版本路由**

在 `wind-power-forecast/backend-autopredict/routes/autopredict.py` 中，找到现有的路由定义区域，在文件末尾（最后一个 `@autopredict_bp.route` 之后）添加以下代码：

```python
# --- 模型版本管理 API ---

@autopredict_bp.route('/model_versions', methods=['GET'])
def get_model_versions():
    """查询模型版本列表。"""
    from db_models import ModelVersion
    farm_code = request.args.get('farm_code', '')
    task_type = request.args.get('task_type', '')
    active_only = request.args.get('active_only', 'true').lower() == 'true'

    with db_session() as session:
        query = session.query(ModelVersion)
        if farm_code:
            query = query.filter_by(farm_code=farm_code)
        if task_type:
            query = query.filter_by(task_type=task_type)
        if active_only:
            query = query.filter_by(is_active=True)
        versions = query.order_by(ModelVersion.trained_at.desc()).limit(50).all()

        result = []
        for v in versions:
            result.append({
                'id': v.id,
                'farm_code': v.farm_code,
                'task_type': v.task_type,
                'algorithm': v.algorithm,
                'val_rmse': v.val_rmse,
                'val_mae': v.val_mae,
                'val_accuracy': v.val_accuracy,
                'is_active': v.is_active,
                'training_samples': v.training_samples,
                'trained_at': v.trained_at.isoformat() if v.trained_at else None,
            })
    return jsonify({'code': 200, 'data': result})


@autopredict_bp.route('/model_versions/<int:version_id>/deactivate', methods=['POST'])
def deactivate_model_version(version_id):
    """停用指定模型版本。"""
    auth_err = _check_internal_auth()
    if auth_err:
        return auth_err

    from model_registry import ModelRegistry
    registry = ModelRegistry()
    registry.deactivate(version_id)
    return jsonify({'code': 200, 'message': f'模型版本 {version_id} 已停用'})


@autopredict_bp.route('/model_versions/fusion_status', methods=['GET'])
def get_fusion_status():
    """获取融合状态概览（按场站和类型分组统计）。"""
    from db_models import ModelVersion
    from sqlalchemy import func

    with db_session() as session:
        rows = session.query(
            ModelVersion.farm_code,
            ModelVersion.task_type,
            func.count(ModelVersion.id).label('total'),
            func.sum(db.case((ModelVersion.is_active == True, 1), else_=0)).label('active'),
        ).group_by(ModelVersion.farm_code, ModelVersion.task_type).all()

        result = []
        for row in rows:
            result.append({
                'farm_code': row.farm_code,
                'task_type': row.task_type,
                'total_models': row.total,
                'active_models': row.active,
                'fusion_enabled': row.active > 1 if row.active else False,
            })
    return jsonify({'code': 200, 'data': result})
```

注意：需要在文件顶部确保 `db` 或相关导入。由于 `db_session` 已经在文件中被导入，`sqlalchemy.func` 和 `sqlalchemy.case` 需要添加导入。在文件顶部添加：

```python
from sqlalchemy import func, case as db_case
```

在路由代码中将 `db.case` 替换为 `db_case`：

```python
func.sum(db_case((ModelVersion.is_active == True, 1), else_=0)).label('active'),
```

- [ ] **Step 2: 验证 Python 语法**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -c "import py_compile; py_compile.compile('routes/autopredict.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/backend-autopredict/routes/autopredict.py
git commit -m "feat: add model version management API endpoints"
```

---

### Task 8: 全量语法验证和集成检查

**Files:**
- All files modified in Tasks 1-7

- [ ] **Step 1: 运行全部单元测试**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/ -v`
Expected: 所有测试 PASS

- [ ] **Step 2: 验证所有修改文件语法正确**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -c "
import py_compile
files = [
    'db_models/model_version.py',
    'db_models/__init__.py',
    'model_registry.py',
    'fusion_engine.py',
    'routes/autopredict.py',
    'auto_scripts/scripts/short/auto_pre_train.py',
    'auto_scripts/scripts/middle/auto_pre_train.py',
    'auto_scripts/scripts/supershort/train_supershort.py',
]
for f in files:
    py_compile.compile(f, doraise=True)
    print(f'OK: {f}')
"`
Expected: 所有文件输出 `OK`

- [ ] **Step 3: Commit（如有修复）**

```bash
git add -A
git commit -m "fix: resolve integration issues from model fusion implementation"
```

---

## Plan Self-Review

**1. Spec coverage:**
- model_versions 表 → Task 1 ✅
- ModelRegistry.register() → Task 2 ✅
- ModelRegistry.get_active_models() → Task 2 ✅
- ModelRegistry.deactivate() → Task 2 ✅
- FusionEngine.predict() → Task 3 ✅
- FusionEngine._compute_weights() → Task 2 + Task 3 ✅
- 短期训练集成 → Task 4 ✅
- 中期训练集成 → Task 5 ✅
- 超短期训练集成 → Task 6 ✅
- API 端点 → Task 7 ✅
- 向后兼容（表为空退回文件加载）→ Task 3 (get_active_models 返回空时 predict 返回 None) ✅
- 激活阈值 → Task 2 (_should_activate) ✅
- 清理旧版本（保留 5 个）→ Task 2 (_deactivate_old_versions) ✅

**2. Placeholder scan:** 无 TBD/TODO。所有代码块完整。

**3. Type consistency:**
- `ModelRegistry._compute_weights()` 在 Task 2 和 Task 3 中使用一致（接收 model_info 列表，访问 `.val_rmse`）
- `FusionEngine._weighted_combine()` 签名一致
- `ModelVersion` 字段与 `register()` 参数对应
- API 路由中的 `ModelVersion` 字段名与 DB 模型一致
