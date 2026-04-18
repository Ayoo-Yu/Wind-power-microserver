# tests/test_fusion_engine.py
import sys
from unittest.mock import MagicMock, patch

import joblib
import numpy as np
import pytest

# Mock the heavy DB import chain before importing fusion_engine.
# fusion_engine imports model_registry -> db_session -> database_config -> config,
# which requires DB_PASSWORD at module level.  We patch those modules so the
# import succeeds without a real database connection.
for _mod in (
    "database_config",
    "db_session",
    "db_models",
    "db_models.base",
    "db_models.model_version",
):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from fusion_engine import FusionEngine


class TestWeightedCombine:
    """测试 _weighted_combine 加权融合逻辑。"""

    def test_single_model_returns_directly(self):
        engine = FusionEngine()
        pred = np.array([1.0, 2.0, 3.0])
        result = engine._weighted_combine([pred], [1.0])
        np.testing.assert_array_almost_equal(result, [1.0, 2.0, 3.0])

    def test_two_models_weighted_average(self):
        engine = FusionEngine()
        p1 = np.array([10.0, 20.0])
        p2 = np.array([30.0, 40.0])
        w1, w2 = 0.3, 0.7
        result = engine._weighted_combine([p1, p2], [w1, w2])
        expected = np.array([0.3 * 10.0 + 0.7 * 30.0, 0.3 * 20.0 + 0.7 * 40.0])
        np.testing.assert_array_almost_equal(result, expected)

    def test_three_models_weights_sum_to_one(self):
        engine = FusionEngine()
        p1 = np.array([1.0])
        p2 = np.array([2.0])
        p3 = np.array([3.0])
        weights = [0.5, 0.3, 0.2]
        result = engine._weighted_combine([p1, p2, p3], weights)
        expected = np.array([0.5 * 1.0 + 0.3 * 2.0 + 0.2 * 3.0])
        np.testing.assert_array_almost_equal(result, expected)

    def test_empty_models_returns_none(self):
        engine = FusionEngine()
        assert engine._weighted_combine([], []) is None

    def test_empty_predictions_returns_none(self):
        engine = FusionEngine()
        assert engine._weighted_combine([], [0.5, 0.5]) is None

    def test_empty_weights_returns_none(self):
        engine = FusionEngine()
        assert engine._weighted_combine([np.array([1.0])], []) is None


class TestLoadModel:
    """测试 _load_model 模型加载逻辑。"""

    def test_load_from_local_path(self, tmp_path):
        """从本地文件加载 joblib 序列化的模型。"""
        # Use a simple pickle-able object instead of MagicMock
        model_file = tmp_path / "model.joblib"
        dummy_model = {"type": "test_model", "weights": [1.0, 2.0, 3.0]}
        joblib.dump(dummy_model, model_file)

        engine = FusionEngine()
        model_info = {"local_path": str(model_file)}
        loaded = engine._load_model(model_info)
        assert loaded is not None
        assert loaded["type"] == "test_model"
        assert loaded["weights"] == [1.0, 2.0, 3.0]

    def test_load_missing_returns_none(self):
        """local_path 不存在且无 s3_path 时返回 None。"""
        engine = FusionEngine()
        model_info = {"local_path": "/nonexistent/path/model.joblib"}
        assert engine._load_model(model_info) is None

    def test_load_no_paths_returns_none(self):
        """既没有 local_path 也没有 s3_path 时返回 None。"""
        engine = FusionEngine()
        model_info = {}
        assert engine._load_model(model_info) is None


class TestPredictFallback:
    """测试 predict 方法的回退和边界情况。"""

    def test_no_active_models_returns_none(self):
        """当 get_active_models 返回空列表时，predict 返回 None。"""
        engine = FusionEngine()
        with patch.object(engine.registry, "get_active_models", return_value=[]):
            result = engine.predict("FARM01", "short", MagicMock())
        assert result is None

    def test_single_model_returns_prediction_directly(self):
        """只有单个 active 模型时，直接返回该模型的预测。"""
        engine = FusionEngine()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([5.0, 6.0])

        def mock_loader(model_info):
            return mock_model

        # get_active_models returns dicts, single model skips _compute_weights
        model_info = [{"local_path": "/fake/model.joblib", "val_rmse": 10.0}]

        with patch.object(engine.registry, "get_active_models", return_value=model_info):
            result = engine.predict("FARM01", "short", MagicMock(), model_loader=mock_loader)

        np.testing.assert_array_almost_equal(result, [5.0, 6.0])

    def test_multi_model_fusion(self):
        """多个 active 模型时，加权融合返回正确结果。"""
        engine = FusionEngine()

        m1 = MagicMock()
        m1.predict.return_value = np.array([10.0])
        m2 = MagicMock()
        m2.predict.return_value = np.array([20.0])

        loaders = iter([m1, m2])

        def mock_loader(model_info):
            return next(loaders)

        # _compute_weights accesses m.val_rmse on ORM-like objects.
        # Use MagicMock objects with val_rmse attributes so weights are computed correctly.
        # val_rmse=10 -> inv=0.1, val_rmse=5 -> inv=0.2
        # weights: [0.1/0.3, 0.2/0.3] = [1/3, 2/3]
        model_info = [
            MagicMock(local_path="/fake/m1.joblib", val_rmse=10.0),
            MagicMock(local_path="/fake/m2.joblib", val_rmse=5.0),
        ]

        with patch.object(engine.registry, "get_active_models", return_value=model_info):
            result = engine.predict("FARM01", "short", MagicMock(), model_loader=mock_loader)

        # expected: 1/3 * 10 + 2/3 * 20 = 10/3 + 40/3 = 50/3 ~ 16.667
        np.testing.assert_array_almost_equal(result, [50.0 / 3.0])

    def test_all_models_fail_returns_none(self):
        """所有模型加载失败时返回 None。"""
        engine = FusionEngine()

        def failing_loader(model_info):
            return None

        model_info = [
            MagicMock(local_path="/fake/m1.joblib", val_rmse=10.0),
            MagicMock(local_path="/fake/m2.joblib", val_rmse=5.0),
        ]

        with patch.object(engine.registry, "get_active_models", return_value=model_info):
            result = engine.predict("FARM01", "short", MagicMock(), model_loader=failing_loader)

        assert result is None
