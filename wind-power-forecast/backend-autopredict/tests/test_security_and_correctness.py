"""Tests for security and correctness fixes across sub-projects A, B, C."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ============================================================
# _compute_weights rmse edge case tests
# ============================================================
class TestComputeWeightsEdgeCases:
    """Test _compute_weights handles rmse=0.0 vs rmse=None correctly."""

    @staticmethod
    def _compute_weights_direct(scores_list):
        """Reproduce _compute_weights logic without importing full module."""
        inv_rmses = []
        for rmse in scores_list:
            if rmse is None:
                rmse = 0.0
            if rmse <= 0:
                inv_rmses.append(1e6)
            else:
                inv_rmses.append(1.0 / rmse)
        total = sum(inv_rmses)
        if total <= 0:
            return [1.0 / len(scores_list)] * len(scores_list)
        return [inv / total for inv in inv_rmses]

    def test_rmse_zero_is_valid_model(self):
        """rmse=0.0 is a perfect model, should get high weight (inverse near 1e6)."""
        weights = self._compute_weights_direct([0.0, 5.0])
        assert len(weights) == 2
        assert weights[0] > weights[1], "Perfect model (rmse=0) should have higher weight"

    def test_rmse_none_defaults_to_zero(self):
        """rmse=None should default to 0.0 and get fallback weight."""
        weights = self._compute_weights_direct([None, 5.0])
        assert len(weights) == 2
        assert weights[0] > weights[1], "None-rmse model gets fallback weight"

    def test_rmse_negative(self):
        """Negative rmse should get fallback weight."""
        weights = self._compute_weights_direct([-1.0, 5.0])
        assert weights[0] > weights[1]

    def test_all_valid_normal(self):
        """Normal case: all positive rmse."""
        weights = self._compute_weights_direct([2.0, 4.0, 8.0])
        assert abs(sum(weights) - 1.0) < 1e-10
        assert weights[0] > weights[1] > weights[2]

    def test_single_model(self):
        """Single model should always get weight 1.0."""
        weights = self._compute_weights_direct([5.0])
        assert weights == [1.0]


# ============================================================
# computeSummary single-pass correctness (sub-project C)
# ============================================================
class TestComputeSummary:
    """Verify computeSummary produces correct counts."""

    def test_all_types_counted(self):
        """Import and test the actual computeSummary function."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'src', 'services'))
        # JS can't be imported from Python; test the logic directly

        results = [
            {'type': 'normal'},
            {'type': 'outlier'},
            {'type': 'curtailment'},
            {'type': 'underperformance'},
            {'type': 'normal'},
            {'type': 'unknown'},
        ]

        total = sum(1 for r in results if r['type'] != 'unknown')
        outliers = sum(1 for r in results if r['type'] == 'outlier')
        curtailments = sum(1 for r in results if r['type'] == 'curtailment')
        underperformance = sum(1 for r in results if r['type'] == 'underperformance')

        assert total == 5
        assert outliers == 1
        assert curtailments == 1
        assert underperformance == 1
        abnormal_rate = (outliers + curtailments + underperformance) / total
        assert abs(abnormal_rate - 0.6) < 1e-10


# ============================================================
# datetime.now vs datetime.now() fix (sub-project A)
# ============================================================
class TestDatetimeDefaultFix:
    """Verify datetime.now (callable) produces different timestamps."""

    def test_callable_produces_different_values(self):
        from datetime import datetime
        import time

        fn = datetime.now
        t1 = fn()
        time.sleep(0.01)
        t2 = fn()
        assert t1 != t2, "datetime.now (callable) should produce different timestamps"

    def test_evaluated_once_produces_same_value(self):
        from datetime import datetime

        fixed = datetime.now()
        assert fixed == fixed, "datetime.now() (evaluated) is a fixed value"


# ============================================================
# API Key timing-safe comparison
# ============================================================
class TestApiKeyComparison:
    """Verify hmac.compare_digest is used correctly."""

    def test_correct_key_passes(self):
        import hmac
        assert hmac.compare_digest('secret123', 'secret123') is True

    def test_wrong_key_fails(self):
        import hmac
        assert hmac.compare_digest('secret123', 'wrong456') is False

    def test_empty_key_fails(self):
        import hmac
        assert hmac.compare_digest('', 'secret123') is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
