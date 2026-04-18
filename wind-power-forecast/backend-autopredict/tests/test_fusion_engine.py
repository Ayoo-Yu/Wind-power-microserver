# tests/test_fusion_engine.py
"""Integration tests for the FusionEngine model fusion pipeline.

Tests cover:
- Weighted combine logic (unit-level)
- Local and S3 model loading with mocked MinIO
- File extension validation (.joblib, .pkl, .model only)
- Fallback behavior when no models are available
- Partial model failure with weight renormalization
- End-to-end predict() flow with mocked registry
"""
import io
import pickle
import sys
from unittest.mock import MagicMock, patch

import joblib
import numpy as np
import pytest

# Mock the heavy DB import chain before importing fusion_engine.
# fusion_engine imports model_registry -> db_session -> database_config -> config,
# which requires DB_PASSWORD at module level.  We patch those modules so the
# import succeeds without a real database connection.
_MOCK_MODULES = (
    "database_config",
    "db_session",
    "db_models",
    "db_models.base",
    "db_models.model_version",
    "config",
)
for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from fusion_engine import FusionEngine


def _serialize_model(model_obj):
    """Serialize a model object to bytes using pickle (joblib.loads compatible)."""
    return pickle.dumps(model_obj)


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


class TestS3ModelLoading:
    """Integration tests for loading models from S3/MinIO with mocked client."""

    def _make_mock_minio(self, model_bytes):
        """Build a mocked MinIO client and config that returns model_bytes."""
        mock_s3_response = MagicMock()
        mock_s3_response.read.return_value = model_bytes
        mock_minio_client = MagicMock()
        mock_minio_client.get_object.return_value = mock_s3_response
        return mock_minio_client

    def test_load_from_s3_joblib(self, tmp_path):
        """Loading a .joblib model from S3 via mocked MinIO client."""
        dummy_model = {"type": "s3_model", "version": 2}
        model_bytes = _serialize_model(dummy_model)

        engine = FusionEngine()
        mock_minio = self._make_mock_minio(model_bytes)
        mock_db_config = sys.modules["database_config"]
        mock_cfg = sys.modules["config"]

        with patch.object(mock_db_config, "init_minio_client", return_value=mock_minio):
            with patch.object(mock_cfg, "MINIO_CONFIG", {"buckets": {"models": "wind-models"}}):
                model_info = {"s3_path": "models/farm01/model.joblib"}
                loaded = engine._load_model(model_info)

        assert loaded is not None
        assert loaded["type"] == "s3_model"
        assert loaded["version"] == 2

    def test_load_from_s3_pkl(self):
        """Loading a .pkl model from S3 succeeds."""
        dummy_model = {"algo": "dart"}
        model_bytes = _serialize_model(dummy_model)

        engine = FusionEngine()
        mock_minio = self._make_mock_minio(model_bytes)
        mock_db_config = sys.modules["database_config"]
        mock_cfg = sys.modules["config"]

        with patch.object(mock_db_config, "init_minio_client", return_value=mock_minio):
            with patch.object(mock_cfg, "MINIO_CONFIG", {"buckets": {"models": "wind-models"}}):
                loaded = engine._load_model({"s3_path": "models/model.pkl"})

        assert loaded is not None
        assert loaded["algo"] == "dart"

    def test_load_from_s3_model_extension(self):
        """Loading a .model file from S3 succeeds."""
        dummy_model = {"algo": "goss"}
        model_bytes = _serialize_model(dummy_model)

        engine = FusionEngine()
        mock_minio = self._make_mock_minio(model_bytes)
        mock_db_config = sys.modules["database_config"]
        mock_cfg = sys.modules["config"]

        with patch.object(mock_db_config, "init_minio_client", return_value=mock_minio):
            with patch.object(mock_cfg, "MINIO_CONFIG", {"buckets": {"models": "wind-models"}}):
                loaded = engine._load_model({"s3_path": "models/model.model"})

        assert loaded is not None
        assert loaded["algo"] == "goss"


class TestFileExtensionValidation:
    """Test that only .joblib, .pkl, .model extensions are accepted for S3 paths."""

    def _mock_s3_setup(self, s3_path, response_data=b"fake data", side_effect=None):
        """Common setup for S3 file extension tests."""
        engine = FusionEngine()
        mock_minio_client = MagicMock()
        mock_s3_response = MagicMock()
        mock_s3_response.read.return_value = response_data
        if side_effect:
            mock_minio_client.get_object.side_effect = side_effect
        else:
            mock_minio_client.get_object.return_value = mock_s3_response
        mock_db_config = sys.modules["database_config"]
        mock_cfg = sys.modules["config"]
        return engine, mock_minio_client, mock_db_config, mock_cfg

    def test_invalid_extension_py_returns_none(self):
        """A .py file extension is rejected and returns None."""
        engine, mock_minio, mock_db, mock_cfg = self._mock_s3_setup("models/script.py")

        with patch.object(mock_db, "init_minio_client", return_value=mock_minio):
            with patch.object(mock_cfg, "MINIO_CONFIG", {"buckets": {"models": "wind-models"}}):
                loaded = engine._load_model({"s3_path": "models/script.py"})

        assert loaded is None

    def test_invalid_extension_txt_returns_none(self):
        """A .txt file extension is rejected."""
        engine, mock_minio, mock_db, mock_cfg = self._mock_s3_setup("models/readme.txt")

        with patch.object(mock_db, "init_minio_client", return_value=mock_minio):
            with patch.object(mock_cfg, "MINIO_CONFIG", {"buckets": {"models": "wind-models"}}):
                loaded = engine._load_model({"s3_path": "models/readme.txt"})

        assert loaded is None

    def test_invalid_extension_exe_returns_none(self):
        """A .exe file extension is rejected."""
        engine, mock_minio, mock_db, mock_cfg = self._mock_s3_setup("models/binary.exe")

        with patch.object(mock_db, "init_minio_client", return_value=mock_minio):
            with patch.object(mock_cfg, "MINIO_CONFIG", {"buckets": {"models": "wind-models"}}):
                loaded = engine._load_model({"s3_path": "models/binary.exe"})

        assert loaded is None

    def test_s3_connection_failure_returns_none(self):
        """If MinIO client raises an exception, _load_model returns None."""
        engine, mock_minio, mock_db, mock_cfg = self._mock_s3_setup(
            "models/model.joblib",
            side_effect=Exception("connection refused"),
        )

        with patch.object(mock_db, "init_minio_client", return_value=mock_minio):
            with patch.object(mock_cfg, "MINIO_CONFIG", {"buckets": {"models": "wind-models"}}):
                loaded = engine._load_model({"s3_path": "models/model.joblib"})

        assert loaded is None


class TestPartialModelFailure:
    """Test weight renormalization when some models fail to load."""

    def test_one_of_two_models_fails_renormalizes(self):
        """When one of two models fails, the surviving model gets weight 1.0."""
        engine = FusionEngine()

        m1 = MagicMock()
        m1.predict.return_value = np.array([42.0])

        call_count = {"n": 0}

        def mock_loader(model_info):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return None  # first model fails
            return m1

        model_info = [
            MagicMock(local_path="/fake/m1.joblib", val_rmse=10.0),
            MagicMock(local_path="/fake/m2.joblib", val_rmse=5.0),
        ]

        with patch.object(engine.registry, "get_active_models", return_value=model_info):
            result = engine.predict("FARM01", "short", MagicMock(), model_loader=mock_loader)

        # Only m1's prediction [42.0] survives, weight renormalized to 1.0
        np.testing.assert_array_almost_equal(result, [42.0])

    def test_two_of_three_models_fail_renormalizes(self):
        """When two of three models fail, the surviving model gets full weight."""
        engine = FusionEngine()

        m3 = MagicMock()
        m3.predict.return_value = np.array([100.0])

        call_count = {"n": 0}

        def mock_loader(model_info):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return None
            return m3

        model_info = [
            MagicMock(local_path="/fake/m1.joblib", val_rmse=10.0),
            MagicMock(local_path="/fake/m2.joblib", val_rmse=5.0),
            MagicMock(local_path="/fake/m3.joblib", val_rmse=8.0),
        ]

        with patch.object(engine.registry, "get_active_models", return_value=model_info):
            result = engine.predict("FARM01", "short", MagicMock(), model_loader=mock_loader)

        np.testing.assert_array_almost_equal(result, [100.0])


class TestModelWithoutPredictMethod:
    """Test that a model object without a predict() method is handled gracefully."""

    def test_model_without_predict_returns_none(self):
        """A model object that has no predict() attribute causes _single_predict to return None."""
        engine = FusionEngine()

        # Object without predict method
        not_a_model = {"weights": [1, 2, 3]}

        model_info = [{"local_path": "/fake/model.joblib", "val_rmse": 5.0}]

        with patch.object(engine.registry, "get_active_models", return_value=model_info):
            result = engine.predict(
                "FARM01", "short", MagicMock(),
                model_loader=lambda info: not_a_model,
            )

        # Single model path: returns None because model lacks predict()
        assert result is None


class TestEndToEndFusionPipeline:
    """End-to-end integration test of the full predict() pipeline."""

    def test_full_pipeline_three_models(self):
        """Complete pipeline: registry returns 3 models, weights computed, fused."""
        engine = FusionEngine()

        m1 = MagicMock()
        m1.predict.return_value = np.array([10.0, 20.0])
        m2 = MagicMock()
        m2.predict.return_value = np.array([30.0, 40.0])
        m3 = MagicMock()
        m3.predict.return_value = np.array([50.0, 60.0])

        loaders = iter([m1, m2, m3])

        def mock_loader(model_info):
            return next(loaders)

        # val_rmse: 10, 5, 20 -> inv: 0.1, 0.2, 0.05 -> total=0.35
        # weights: 0.1/0.35, 0.2/0.35, 0.05/0.35
        model_info = [
            MagicMock(local_path="/fake/m1.joblib", val_rmse=10.0),
            MagicMock(local_path="/fake/m2.joblib", val_rmse=5.0),
            MagicMock(local_path="/fake/m3.joblib", val_rmse=20.0),
        ]

        with patch.object(engine.registry, "get_active_models", return_value=model_info):
            result = engine.predict("FARM01", "supershort", MagicMock(), model_loader=mock_loader)

        w1 = 0.1 / 0.35
        w2 = 0.2 / 0.35
        w3 = 0.05 / 0.35

        expected = np.array([
            w1 * 10.0 + w2 * 30.0 + w3 * 50.0,
            w1 * 20.0 + w2 * 40.0 + w3 * 60.0,
        ])
        np.testing.assert_array_almost_equal(result, expected)
