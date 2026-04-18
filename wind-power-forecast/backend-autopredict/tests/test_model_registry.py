# tests/test_model_registry.py
import sys
from unittest.mock import MagicMock

# Mock the heavy DB import chain before importing model_registry.
# model_registry imports db_session -> database_config -> config, which requires
# DB_PASSWORD at module level.  We patch those modules so the import succeeds
# without a real database connection.
for _mod in (
    "database_config",
    "db_session",
    "db_models",
    "db_models.base",
    "db_models.model_version",
):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from model_registry import ModelRegistry, ACTIVATION_THRESHOLDS


class TestComputeWeights:
    """测试权重计算逻辑（不依赖数据库）"""

    def test_single_model_gets_weight_one(self):
        registry = ModelRegistry()
        models = [MagicMock(val_rmse=10.0)]
        weights = registry._compute_weights(models)
        assert len(weights) == 1
        assert abs(weights[0] - 1.0) < 1e-9

    def test_two_models_inverse_rmse(self):
        registry = ModelRegistry()
        m1 = MagicMock(val_rmse=10.0)
        m2 = MagicMock(val_rmse=5.0)
        weights = registry._compute_weights([m1, m2])
        assert len(weights) == 2
        assert abs(sum(weights) - 1.0) < 1e-9
        assert weights[1] > weights[0]
        assert abs(weights[0] - 1.0 / 3.0) < 1e-9
        assert abs(weights[1] - 2.0 / 3.0) < 1e-9

    def test_three_models_sum_to_one(self):
        registry = ModelRegistry()
        models = [MagicMock(val_rmse=r) for r in [8.0, 10.0, 12.0]]
        weights = registry._compute_weights(models)
        assert len(weights) == 3
        assert abs(sum(weights) - 1.0) < 1e-9
        assert weights[0] > weights[1] > weights[2]

    def test_zero_rmse_handled(self):
        registry = ModelRegistry()
        m1 = MagicMock(val_rmse=0.0)
        m2 = MagicMock(val_rmse=10.0)
        weights = registry._compute_weights([m1, m2])
        # rmse=0 gets inv=1e6, rmse=10 gets inv=0.1
        # w[0] = 1e6/(1e6+0.1) ~ 0.9999999, w[1] ~ 1e-7
        assert abs(sum(weights) - 1.0) < 1e-9
        assert weights[0] > 0.999999
        assert weights[1] < 1e-5

    def test_empty_models_returns_empty(self):
        registry = ModelRegistry()
        weights = registry._compute_weights([])
        assert weights == []

    def test_model_without_val_rmse_attribute(self):
        registry = ModelRegistry()
        m = MagicMock(spec=[])  # no val_rmse attribute
        weights = registry._compute_weights([m])
        assert len(weights) == 1
        assert abs(weights[0] - 1.0) < 1e-9

    def test_model_with_none_val_rmse(self):
        registry = ModelRegistry()
        m = MagicMock(val_rmse=None)
        weights = registry._compute_weights([m])
        assert len(weights) == 1
        assert abs(weights[0] - 1.0) < 1e-9

    def test_dict_input_with_val_rmse(self):
        """_compute_weights should work with dict objects from get_active_models."""
        registry = ModelRegistry()
        models = [
            {"val_rmse": 10.0},
            {"val_rmse": 5.0},
        ]
        weights = registry._compute_weights(models)
        assert len(weights) == 2
        assert abs(sum(weights) - 1.0) < 1e-9
        # model with lower RMSE should get higher weight
        assert weights[1] > weights[0]

    def test_dict_input_without_val_rmse(self):
        """Dict without val_rmse key gets treated as zero RMSE."""
        registry = ModelRegistry()
        models = [{"algorithm": "xgboost"}]
        weights = registry._compute_weights(models)
        assert len(weights) == 1
        assert abs(weights[0] - 1.0) < 1e-9


class TestActivationThreshold:
    """测试激活阈值判断"""

    def test_supershort_pass(self):
        registry = ModelRegistry()
        assert registry._should_activate("supershort", 0.85)

    def test_supershort_fail(self):
        registry = ModelRegistry()
        assert not registry._should_activate("supershort", 0.75)

    def test_short_pass(self):
        registry = ModelRegistry()
        assert registry._should_activate("short", 0.78)

    def test_short_fail(self):
        registry = ModelRegistry()
        assert not registry._should_activate("short", 0.70)

    def test_medium_pass(self):
        registry = ModelRegistry()
        assert registry._should_activate("medium", 0.72)

    def test_medium_fail(self):
        registry = ModelRegistry()
        assert not registry._should_activate("medium", 0.65)

    def test_none_accuracy_fails(self):
        registry = ModelRegistry()
        assert not registry._should_activate("short", None)

    def test_unknown_task_type_uses_default(self):
        registry = ModelRegistry()
        # Unknown types default to 0.75 threshold
        assert registry._should_activate("unknown_type", 0.76)
        assert not registry._should_activate("unknown_type", 0.74)

    def test_exact_threshold_passes(self):
        registry = ModelRegistry()
        # Exact threshold value should pass (>= comparison)
        assert registry._should_activate("supershort", ACTIVATION_THRESHOLDS["supershort"])
        assert registry._should_activate("short", ACTIVATION_THRESHOLDS["short"])
        assert registry._should_activate("medium", ACTIVATION_THRESHOLDS["medium"])
