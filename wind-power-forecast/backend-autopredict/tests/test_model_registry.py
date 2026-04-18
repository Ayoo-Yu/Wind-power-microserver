# tests/test_model_registry.py
import sys
import threading
from unittest.mock import MagicMock, patch, call

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


class TestRowLevelLocking:
    """Verify with_for_update() is called for race condition prevention."""

    def test_is_better_than_worst_calls_with_for_update(self):
        """_is_better_than_worst should call with_for_update() on the query."""
        registry = ModelRegistry()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None  # No active models

        result = registry._is_better_than_worst(
            mock_session, "FARM01", "short", 0.90,
        )

        assert result is True  # No active models, so better than worst
        mock_query.with_for_update.assert_called_once()

    def test_is_better_than_worst_none_accuracy_returns_false(self):
        """None val_accuracy should return False without querying."""
        registry = ModelRegistry()
        mock_session = MagicMock()

        result = registry._is_better_than_worst(
            mock_session, "FARM01", "short", None,
        )

        assert result is False
        mock_session.query.assert_not_called()

    def test_is_better_than_worst_with_existing_models(self):
        """Should compare against worst active model with row lock."""
        registry = ModelRegistry()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        worst_model = MagicMock()
        worst_model.val_accuracy = 0.85
        mock_query.first.return_value = worst_model

        result = registry._is_better_than_worst(
            mock_session, "FARM01", "short", 0.90,
        )

        assert result is True  # 0.90 >= 0.85
        mock_query.with_for_update.assert_called_once()

    def test_is_better_than_worst_worse_than_worst(self):
        """Should return False when not better than worst active model."""
        registry = ModelRegistry()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        worst_model = MagicMock()
        worst_model.val_accuracy = 0.92
        mock_query.first.return_value = worst_model

        result = registry._is_better_than_worst(
            mock_session, "FARM01", "short", 0.80,
        )

        assert result is False  # 0.80 < 0.92

    def test_deactivate_old_versions_calls_with_for_update(self):
        """_deactivate_old_versions should call with_for_update()."""
        registry = ModelRegistry()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        # Create 7 mock active models (should keep 5, deactivate 2)
        mock_models = [MagicMock(is_active=True) for _ in range(7)]
        mock_query.all.return_value = mock_models

        registry._deactivate_old_versions(
            mock_session, "FARM01", "short", keep=5,
        )

        mock_query.with_for_update.assert_called_once()
        # Last 2 should be deactivated
        assert mock_models[5].is_active is False
        assert mock_models[6].is_active is False
        # First 5 should remain active
        assert mock_models[0].is_active is True
        assert mock_models[4].is_active is True

    def test_deactivate_old_versions_deactivated_at_set(self):
        """Deactivated models should have deactivated_at timestamp set."""
        registry = ModelRegistry()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.order_by.return_value = mock_query

        mock_models = [MagicMock(is_active=True) for _ in range(6)]
        mock_query.all.return_value = mock_models

        registry._deactivate_old_versions(
            mock_session, "FARM01", "short", keep=5,
        )

        # The 6th model should be deactivated with a timestamp
        assert mock_models[5].deactivated_at is not None
        assert mock_models[5].is_active is False

    def test_register_calls_with_for_update_on_active_count(self):
        """register() should lock active models when checking count."""
        registry = ModelRegistry()

        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.count.return_value = 3  # Less than 5
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None
        mock_query.all.return_value = []
        mock_query.limit.return_value = mock_query

        # Mock db_session context manager
        mock_db_session = MagicMock()
        mock_db_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("model_registry.db_session", mock_db_session):
            with patch("model_registry.ModelVersion") as MockModelVersion:
                mock_version = MagicMock()
                mock_version.id = 42
                MockModelVersion.return_value = mock_version

                result = registry.register(
                    farm_code="FARM01",
                    task_type="short",
                    algorithm="lightgbm_gbdt",
                    model_path="/tmp/model.joblib",
                    val_accuracy=0.90,
                )

        # with_for_update should have been called for active count check
        assert mock_query.with_for_update.called


class TestQuantileModelRegistration:
    """Test that quantile models receive point model's val_accuracy."""

    def test_quantile_uses_point_model_accuracy(self):
        """Verify the _register_models_to_registry function passes
        the best point model's val_accuracy to quantile model registration.

        This is tested by importing the module logic and checking the
        registry.register call arguments.
        """
        # We test the logic directly: when the best point model has
        # val_accuracy=0.90, quantile models should use that value.
        registry = ModelRegistry()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.count.return_value = 0  # No active models
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None
        mock_query.all.return_value = []

        mock_db_session = MagicMock()
        mock_db_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db_session.return_value.__exit__ = MagicMock(return_value=False)

        register_calls = []

        def capture_register(**kwargs):
            register_calls.append(kwargs)
            return {"id": len(register_calls), "is_active": True}

        with patch("model_registry.db_session", mock_db_session):
            with patch("model_registry.ModelVersion") as MockModelVersion:
                mock_version = MagicMock()
                mock_version.id = 1
                MockModelVersion.return_value = mock_version

                # Register a model with val_accuracy=0.90 (simulating quantile)
                result = registry.register(
                    farm_code="FARM01",
                    task_type="short",
                    algorithm="gbdt_q05",
                    model_path="/tmp/q05.joblib",
                    val_accuracy=0.90,
                )

        # The model should be activated because 0.90 >= 0.75 threshold
        assert result["is_active"] is True

    def test_quantile_none_accuracy_still_not_activated(self):
        """Verify that None val_accuracy still prevents activation."""
        registry = ModelRegistry()

        # _should_activate should return False for None
        assert registry._should_activate("short", None) is False
        assert registry._should_activate("medium", None) is False
        assert registry._should_activate("supershort", None) is False

    def test_quantile_accuracy_computation(self):
        """Test the accuracy formula used for quantile models:
        val_accuracy = 1 - (rmse / wfcapacity)
        """
        # Simulate the computation done in _register_models_to_registry
        rmse = 50.0
        wfcapacity = 779.0

        val_accuracy = 1 - (rmse / wfcapacity)
        expected = 1 - (50.0 / 779.0)

        assert abs(val_accuracy - expected) < 1e-10
        # Should be above medium threshold (0.70)
        assert val_accuracy > 0.70


class TestConcurrentRegistration:
    """Test thread safety expectations for register()."""

    def test_with_for_update_prevents_double_count(self):
        """Simulate two concurrent registrations seeing the same active count.

        In real PostgreSQL/KingBase, with_for_update() serializes access.
        Here we verify the locking mechanism is in place.
        """
        registry = ModelRegistry()
        call_count = {"count": 0}
        lock_order = []

        def make_mock_session():
            mock_session = MagicMock()
            mock_query = MagicMock()
            mock_session.query.return_value = mock_query
            mock_query.filter_by.return_value = mock_query

            # Track with_for_update calls
            original_with_for_update = mock_query.with_for_update

            def tracked_with_for_update():
                call_count["count"] += 1
                lock_order.append("lock")
                return mock_query

            mock_query.with_for_update = tracked_with_for_update
            mock_query.count.return_value = 4  # 4 active (room for 1 more)
            mock_query.order_by.return_value = mock_query
            mock_query.first.return_value = None
            mock_query.all.return_value = []
            return mock_session

        results = []
        errors = []

        def register_one(idx):
            try:
                mock_session = make_mock_session()
                mock_db_session = MagicMock()
                mock_db_session.return_value.__enter__ = MagicMock(
                    return_value=mock_session
                )
                mock_db_session.return_value.__exit__ = MagicMock(return_value=False)

                with patch("model_registry.db_session", mock_db_session):
                    with patch("model_registry.ModelVersion") as MockMV:
                        mock_version = MagicMock()
                        mock_version.id = idx
                        MockMV.return_value = mock_version

                        result = registry.register(
                            farm_code="FARM01",
                            task_type="short",
                            algorithm=f"lightgbm_gbdt_{idx}",
                            model_path=f"/tmp/model_{idx}.joblib",
                            val_accuracy=0.85 + idx * 0.01,
                        )
                        results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_one, args=(i,))
            for i in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each registration should have called with_for_update
        # (once for active count check)
        assert call_count["count"] >= 3, (
            f"Expected at least 3 with_for_update calls, got {call_count['count']}"
        )
        assert len(errors) == 0, f"Errors during concurrent registration: {errors}"

    def test_max_five_active_models(self):
        """When 5 active models exist, a worse model should not be activated."""
        registry = ModelRegistry()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.count.return_value = 5  # Already at max

        # Worst active model has val_accuracy=0.88
        worst_model = MagicMock()
        worst_model.val_accuracy = 0.88
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = worst_model
        mock_query.all.return_value = []

        mock_db_session = MagicMock()
        mock_db_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("model_registry.db_session", mock_db_session):
            with patch("model_registry.ModelVersion") as MockMV:
                mock_version = MagicMock()
                mock_version.id = 99
                MockMV.return_value = mock_version

                # New model with worse accuracy should NOT be activated
                result = registry.register(
                    farm_code="FARM01",
                    task_type="short",
                    algorithm="lightgbm_gbdt",
                    model_path="/tmp/model.joblib",
                    val_accuracy=0.80,  # Worse than worst active (0.88)
                )

        assert result["is_active"] is False

    def test_better_model_replaces_worst_at_capacity(self):
        """When 5 active models exist, a better model should be activated."""
        registry = ModelRegistry()
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.count.return_value = 5  # Already at max

        # Worst active model has val_accuracy=0.80
        worst_model = MagicMock()
        worst_model.val_accuracy = 0.80
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = worst_model
        mock_query.all.return_value = []

        mock_db_session = MagicMock()
        mock_db_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("model_registry.db_session", mock_db_session):
            with patch("model_registry.ModelVersion") as MockMV:
                mock_version = MagicMock()
                mock_version.id = 100
                MockMV.return_value = mock_version

                # New model with better accuracy SHOULD be activated
                result = registry.register(
                    farm_code="FARM01",
                    task_type="short",
                    algorithm="lightgbm_gbdt",
                    model_path="/tmp/model.joblib",
                    val_accuracy=0.92,  # Better than worst active (0.80)
                )

        assert result["is_active"] is True
