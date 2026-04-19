# tests/test_prediction_corrector.py
"""Comprehensive tests for PredictionCorrector.

Covers: clamp_zero corrections, dynamic decay formulas, decay floor,
immutability, capacity clamping, normal passthrough, correction records,
summary generation, and mixed conditions.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.extreme_weather_detector import WeatherCondition
from services.prediction_corrector import PredictionCorrector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conditions(count: int, condition_type: str, hint: str,
                     severity: str = "warning", **details) -> list[WeatherCondition]:
    """Build a list of identical WeatherCondition instances."""
    return [
        WeatherCondition(
            condition_type=condition_type,
            severity=severity,
            details=dict(details),
            correction_hint=hint,
        )
        for _ in range(count)
    ]


# ---------------------------------------------------------------------------
# 1. Clamp-zero corrections
# ---------------------------------------------------------------------------

class TestClampZero:
    """high_wind, typhoon, calm_wind with clamp_zero should set predictions to 0."""

    def test_high_wind_clamps_to_zero(self):
        corrector = PredictionCorrector()
        preds = np.array([100.0, 200.0, 150.0])
        conditions = _make_conditions(3, "high_wind", "clamp_zero")

        corrected, records = corrector.correct(preds, conditions, capacity=300.0)

        np.testing.assert_array_equal(corrected, np.array([0.0, 0.0, 0.0]))
        assert len(records) == 3

    def test_typhoon_clamps_to_zero(self):
        corrector = PredictionCorrector()
        preds = np.array([50.0, 80.0])
        conditions = _make_conditions(2, "typhoon", "clamp_zero", severity="danger")

        corrected, records = corrector.correct(preds, conditions, capacity=100.0)

        np.testing.assert_array_equal(corrected, np.array([0.0, 0.0]))
        assert len(records) == 2

    def test_calm_wind_clamps_to_zero(self):
        corrector = PredictionCorrector()
        preds = np.array([10.0, 20.0])
        conditions = _make_conditions(2, "calm_wind", "clamp_zero", severity="info")

        corrected, records = corrector.correct(preds, conditions, capacity=100.0)

        np.testing.assert_array_equal(corrected, np.array([0.0, 0.0]))
        assert len(records) == 2

    def test_clamp_zero_already_zero_no_record(self):
        """If prediction is already 0, no record should be emitted."""
        corrector = PredictionCorrector()
        preds = np.array([0.0])
        conditions = _make_conditions(1, "calm_wind", "clamp_zero", severity="info")

        corrected, records = corrector.correct(preds, conditions, capacity=100.0)

        np.testing.assert_array_equal(corrected, np.array([0.0]))
        assert len(records) == 0


# ---------------------------------------------------------------------------
# 2. Dynamic decay: cold_wave
# ---------------------------------------------------------------------------

class TestColdWaveDecay:
    """cold_wave uses decay = max(0.3, 0.7 - (abs(temp) - 5) * 0.05)."""

    def test_cold_wave_decay_formula(self):
        """temp=-8 => decay = max(0.3, 0.7 - (8 - 5) * 0.05) = 0.55."""
        corrector = PredictionCorrector()
        preds = np.array([100.0])
        conditions = [
            WeatherCondition(
                condition_type="cold_wave",
                severity="warning",
                details={"temp_2t_avg": -8.0, "temp_24h_drop": 10.0},
                correction_hint="apply_decay",
            ),
        ]

        corrected, records = corrector.correct(preds, conditions, capacity=200.0)

        expected = 100.0 * 0.55  # 55.0
        np.testing.assert_allclose(corrected, np.array([expected]), atol=1e-6)
        assert len(records) == 1
        assert records[0]["after"] == pytest.approx(expected, abs=0.01)

    def test_cold_wave_mild_temp(self):
        """temp=-5 => decay = max(0.3, 0.7 - (5 - 5) * 0.05) = 0.7."""
        corrector = PredictionCorrector()
        preds = np.array([100.0])
        conditions = [
            WeatherCondition(
                condition_type="cold_wave",
                severity="warning",
                details={"temp_2t_avg": -5.0},
                correction_hint="apply_decay",
            ),
        ]

        corrected, _ = corrector.correct(preds, conditions, capacity=200.0)

        np.testing.assert_allclose(corrected, np.array([70.0]), atol=1e-6)


# ---------------------------------------------------------------------------
# 3. Dynamic decay: icing
# ---------------------------------------------------------------------------

class TestIcingDecay:
    """icing uses decay = max(0.3, 0.6 - (tcwv - 10) * 0.02)."""

    def test_icing_decay_formula(self):
        """tcwv=18 => decay = max(0.3, 0.6 - (18 - 10) * 0.02) = 0.44."""
        corrector = PredictionCorrector()
        preds = np.array([100.0])
        conditions = [
            WeatherCondition(
                condition_type="icing",
                severity="warning",
                details={"temp_2t_avg": -2.0, "tcwv_avg": 18.0},
                correction_hint="apply_decay",
            ),
        ]

        corrected, records = corrector.correct(preds, conditions, capacity=200.0)

        expected = 100.0 * 0.44  # 44.0
        np.testing.assert_allclose(corrected, np.array([expected]), atol=1e-6)
        assert len(records) == 1
        assert records[0]["after"] == pytest.approx(expected, abs=0.01)

    def test_icing_low_tcwv(self):
        """tcwv=10 => decay = max(0.3, 0.6 - (10 - 10) * 0.02) = 0.6."""
        corrector = PredictionCorrector()
        preds = np.array([100.0])
        conditions = [
            WeatherCondition(
                condition_type="icing",
                severity="warning",
                details={"tcwv_avg": 10.0},
                correction_hint="apply_decay",
            ),
        ]

        corrected, _ = corrector.correct(preds, conditions, capacity=200.0)

        np.testing.assert_allclose(corrected, np.array([60.0]), atol=1e-6)


# ---------------------------------------------------------------------------
# 4. Decay floor at 0.3
# ---------------------------------------------------------------------------

class TestDecayFloor:
    """Decay should never go below 0.3 regardless of input values."""

    def test_cold_wave_extreme_temp_hits_floor(self):
        """Very low temp should still produce decay >= 0.3."""
        corrector = PredictionCorrector()
        preds = np.array([100.0])
        # abs(-100) - 5 = 95 => 0.7 - 95*0.05 = -4.05, clamped to 0.3
        conditions = [
            WeatherCondition(
                condition_type="cold_wave",
                severity="warning",
                details={"temp_2t_avg": -100.0},
                correction_hint="apply_decay",
            ),
        ]

        corrected, _ = corrector.correct(preds, conditions, capacity=200.0)

        expected = 100.0 * 0.3  # 30.0
        np.testing.assert_allclose(corrected, np.array([expected]), atol=1e-6)

    def test_icing_extreme_tcwv_hits_floor(self):
        """Very high tcwv should still produce decay >= 0.3."""
        corrector = PredictionCorrector()
        preds = np.array([100.0])
        # tcwv=100 => 0.6 - (100-10)*0.02 = -1.2, clamped to 0.3
        conditions = [
            WeatherCondition(
                condition_type="icing",
                severity="warning",
                details={"tcwv_avg": 100.0},
                correction_hint="apply_decay",
            ),
        ]

        corrected, _ = corrector.correct(preds, conditions, capacity=200.0)

        expected = 100.0 * 0.3  # 30.0
        np.testing.assert_allclose(corrected, np.array([expected]), atol=1e-6)


# ---------------------------------------------------------------------------
# 5. Immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    """Input array must never be modified by correct()."""

    def test_input_unchanged_after_clamp(self):
        corrector = PredictionCorrector()
        preds = np.array([100.0, 200.0])
        original = preds.copy()
        conditions = _make_conditions(2, "high_wind", "clamp_zero")

        corrector.correct(preds, conditions, capacity=300.0)

        np.testing.assert_array_equal(preds, original)

    def test_input_unchanged_after_decay(self):
        corrector = PredictionCorrector()
        preds = np.array([100.0])
        original = preds.copy()
        conditions = [
            WeatherCondition("cold_wave", "warning", {"temp_2t_avg": -8.0}, "apply_decay"),
        ]

        corrector.correct(preds, conditions, capacity=200.0)

        np.testing.assert_array_equal(preds, original)

    def test_returns_new_array(self):
        """The returned array must be a different object from the input."""
        corrector = PredictionCorrector()
        preds = np.array([50.0])
        conditions = [WeatherCondition("normal", "info", {}, "none")]

        corrected, _ = corrector.correct(preds, conditions, capacity=100.0)

        assert corrected is not preds


# ---------------------------------------------------------------------------
# 6. Capacity clamp
# ---------------------------------------------------------------------------

class TestCapacityClamp:
    """Predictions exceeding capacity must be clamped to [0, capacity]."""

    def test_upper_capacity_clamp(self):
        corrector = PredictionCorrector()
        preds = np.array([150.0])
        conditions = [WeatherCondition("normal", "info", {}, "none")]

        corrected, records = corrector.correct(preds, conditions, capacity=100.0)

        assert corrected[0] == 100.0
        assert len(records) == 1
        assert records[0]["type"] == "capacity_clamp"

    def test_negative_values_clamped_to_zero(self):
        corrector = PredictionCorrector()
        preds = np.array([-50.0])
        conditions = [WeatherCondition("normal", "info", {}, "none")]

        corrected, records = corrector.correct(preds, conditions, capacity=100.0)

        assert corrected[0] == 0.0
        assert len(records) == 1
        assert records[0]["type"] == "capacity_clamp"

    def test_exact_capacity_no_record(self):
        """Prediction exactly at capacity should not generate a record."""
        corrector = PredictionCorrector()
        preds = np.array([100.0])
        conditions = [WeatherCondition("normal", "info", {}, "none")]

        corrected, records = corrector.correct(preds, conditions, capacity=100.0)

        assert corrected[0] == 100.0
        assert len(records) == 0

    def test_capacity_clamp_after_weather_correction(self):
        """Decay can produce values within range; no capacity clamp needed."""
        corrector = PredictionCorrector()
        preds = np.array([50.0])
        conditions = [
            WeatherCondition("cold_wave", "warning", {"temp_2t_avg": -8.0}, "apply_decay"),
        ]

        corrected, records = corrector.correct(preds, conditions, capacity=200.0)

        # 50 * 0.55 = 27.5, well within capacity
        assert corrected[0] == pytest.approx(27.5)
        # Only decay record, no capacity clamp record
        assert all(r["type"] != "capacity_clamp" for r in records)


# ---------------------------------------------------------------------------
# 7. Normal conditions: no change, no records
# ---------------------------------------------------------------------------

class TestNormalConditions:
    """normal (correction_hint="none") should pass predictions unchanged."""

    def test_normal_no_change(self):
        corrector = PredictionCorrector()
        preds = np.array([50.0, 75.0, 100.0])
        conditions = _make_conditions(3, "normal", "none", severity="info")

        corrected, records = corrector.correct(preds, conditions, capacity=200.0)

        np.testing.assert_array_equal(corrected, preds)
        assert len(records) == 0

    def test_normal_within_capacity_no_records(self):
        corrector = PredictionCorrector()
        preds = np.array([50.0])
        conditions = [WeatherCondition("normal", "info", {}, "none")]

        corrected, records = corrector.correct(preds, conditions, capacity=100.0)

        assert corrected[0] == 50.0
        assert len(records) == 0


# ---------------------------------------------------------------------------
# 8. Correction records structure
# ---------------------------------------------------------------------------

class TestCorrectionRecords:
    """Each correction record must have index, type, before, after, reason."""

    def test_record_has_required_fields(self):
        corrector = PredictionCorrector()
        preds = np.array([100.0])
        conditions = [
            WeatherCondition("high_wind", "warning", {"ws100_avg": 26.0}, "clamp_zero"),
        ]

        _, records = corrector.correct(preds, conditions, capacity=200.0)

        assert len(records) == 1
        record = records[0]
        assert "index" in record
        assert "type" in record
        assert "before" in record
        assert "after" in record
        assert "reason" in record

    def test_record_index_matches_prediction(self):
        corrector = PredictionCorrector()
        preds = np.array([10.0, 20.0, 30.0])
        conditions = [
            WeatherCondition("normal", "info", {}, "none"),
            WeatherCondition("high_wind", "warning", {}, "clamp_zero"),
            WeatherCondition("normal", "info", {}, "none"),
        ]

        _, records = corrector.correct(preds, conditions, capacity=100.0)

        assert len(records) == 1
        assert records[0]["index"] == 1
        assert records[0]["before"] == 20.0
        assert records[0]["after"] == 0.0

    def test_record_only_when_change_exceeds_tolerance(self):
        """Records only emitted when |before - after| > 0.01."""
        corrector = PredictionCorrector()
        preds = np.array([0.005])
        conditions = [
            WeatherCondition("high_wind", "warning", {}, "clamp_zero"),
        ]

        _, records = corrector.correct(preds, conditions, capacity=100.0)

        # before=0.005, after=0.0, diff=0.005 < 0.01 => no record
        assert len(records) == 0

    def test_reason_strings(self):
        """Verify reason strings for each condition type."""
        expected_reasons = {
            "high_wind": "超大风停机",
            "typhoon": "台风停机",
            "calm_wind": "无风停机",
            "cold_wave": "寒潮衰减",
            "icing": "结冰衰减",
        }
        corrector = PredictionCorrector()

        for condition_type, expected_reason in expected_reasons.items():
            hint = "apply_decay" if condition_type in ("cold_wave", "icing") else "clamp_zero"
            details = {}
            if condition_type == "cold_wave":
                details = {"temp_2t_avg": -8.0}
            elif condition_type == "icing":
                details = {"tcwv_avg": 18.0}

            preds = np.array([100.0])
            conditions = [
                WeatherCondition(condition_type, "warning", details, hint),
            ]

            _, records = corrector.correct(preds, conditions, capacity=200.0)
            assert len(records) >= 1, f"No record for {condition_type}"
            assert records[0]["reason"] == expected_reason, (
                f"Wrong reason for {condition_type}: {records[0]['reason']}"
            )


# ---------------------------------------------------------------------------
# 9. get_correction_summary
# ---------------------------------------------------------------------------

class TestCorrectionSummary:
    """get_correction_summary aggregates counts by type."""

    def test_summary_counts_by_type(self):
        corrector = PredictionCorrector()
        records = [
            {"index": 0, "type": "high_wind", "before": 100.0, "after": 0.0, "reason": "超大风停机"},
            {"index": 1, "type": "high_wind", "before": 200.0, "after": 0.0, "reason": "超大风停机"},
            {"index": 2, "type": "cold_wave", "before": 100.0, "after": 55.0, "reason": "寒潮衰减"},
        ]

        summary = corrector.get_correction_summary(records)

        assert summary["total_corrections"] == 3
        assert summary["by_type"]["high_wind"] == 2
        assert summary["by_type"]["cold_wave"] == 1

    def test_summary_empty_records(self):
        corrector = PredictionCorrector()

        summary = corrector.get_correction_summary([])

        assert summary["total_corrections"] == 0
        assert summary["by_type"] == {}

    def test_summary_single_type(self):
        corrector = PredictionCorrector()
        records = [
            {"index": 0, "type": "icing", "before": 100.0, "after": 44.0, "reason": "结冰衰减"},
        ]

        summary = corrector.get_correction_summary(records)

        assert summary["total_corrections"] == 1
        assert summary["by_type"]["icing"] == 1

    def test_summary_includes_capacity_clamp(self):
        corrector = PredictionCorrector()
        records = [
            {"index": 0, "type": "capacity_clamp", "before": 150.0, "after": 100.0, "reason": "超出装机容量"},
        ]

        summary = corrector.get_correction_summary(records)

        assert summary["total_corrections"] == 1
        assert summary["by_type"]["capacity_clamp"] == 1


# ---------------------------------------------------------------------------
# 10. Mixed conditions
# ---------------------------------------------------------------------------

class TestMixedConditions:
    """A batch with clamp, decay, and normal conditions together."""

    def test_mixed_conditions(self):
        corrector = PredictionCorrector()
        preds = np.array([100.0, 80.0, 50.0, 200.0, 150.0])
        conditions = [
            WeatherCondition("high_wind", "warning", {}, "clamp_zero"),       # clamp to 0
            WeatherCondition("cold_wave", "warning", {"temp_2t_avg": -8.0}, "apply_decay"),  # decay 0.55
            WeatherCondition("normal", "info", {}, "none"),                   # no change
            WeatherCondition("typhoon", "danger", {}, "clamp_zero"),          # clamp to 0
            WeatherCondition("icing", "warning", {"tcwv_avg": 18.0}, "apply_decay"),  # decay 0.44
        ]

        corrected, records = corrector.correct(preds, conditions, capacity=200.0)

        # index 0: high_wind clamp to 0
        assert corrected[0] == 0.0
        # index 1: cold_wave 80 * 0.55 = 44.0
        np.testing.assert_allclose([corrected[1]], [44.0], atol=1e-6)
        # index 2: normal, no change
        assert corrected[2] == 50.0
        # index 3: typhoon clamp to 0
        assert corrected[3] == 0.0
        # index 4: icing 150 * 0.44 = 66.0
        np.testing.assert_allclose([corrected[4]], [66.0], atol=1e-6)

        # Should have records for all non-normal corrections
        types = [r["type"] for r in records]
        assert "high_wind" in types
        assert "cold_wave" in types
        assert "typhoon" in types
        assert "icing" in types
        assert "normal" not in types

    def test_mixed_with_capacity_clamp(self):
        """A normal prediction exceeding capacity should still be clamped."""
        corrector = PredictionCorrector()
        preds = np.array([100.0, 250.0])
        conditions = [
            WeatherCondition("normal", "info", {}, "none"),
            WeatherCondition("normal", "info", {}, "none"),
        ]

        corrected, records = corrector.correct(preds, conditions, capacity=200.0)

        assert corrected[0] == 100.0
        assert corrected[1] == 200.0
        assert len(records) == 1
        assert records[0]["type"] == "capacity_clamp"
        assert records[0]["index"] == 1


# ---------------------------------------------------------------------------
# 11. Config acceptance
# ---------------------------------------------------------------------------

class TestConfig:
    """PredictionCorrector accepts optional config dict."""

    def test_none_config(self):
        corrector = PredictionCorrector(config=None)
        preds = np.array([50.0])
        conditions = [WeatherCondition("normal", "info", {}, "none")]

        corrected, records = corrector.correct(preds, conditions, capacity=100.0)

        assert corrected[0] == 50.0

    def test_empty_config(self):
        corrector = PredictionCorrector(config={})
        preds = np.array([50.0])
        conditions = [WeatherCondition("normal", "info", {}, "none")]

        corrected, records = corrector.correct(preds, conditions, capacity=100.0)

        assert corrected[0] == 50.0


# ---------------------------------------------------------------------------
# 12. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Boundary and edge-case inputs."""

    def test_empty_predictions(self):
        corrector = PredictionCorrector()
        preds = np.array([])
        conditions = []

        corrected, records = corrector.correct(preds, conditions, capacity=100.0)

        assert len(corrected) == 0
        assert len(records) == 0

    def test_single_prediction(self):
        corrector = PredictionCorrector()
        preds = np.array([42.0])
        conditions = [WeatherCondition("normal", "info", {}, "none")]

        corrected, records = corrector.correct(preds, conditions, capacity=100.0)

        assert corrected[0] == 42.0
        assert len(records) == 0

    def test_zero_capacity(self):
        """Zero capacity should clamp everything to 0."""
        corrector = PredictionCorrector()
        preds = np.array([50.0])
        conditions = [WeatherCondition("normal", "info", {}, "none")]

        corrected, records = corrector.correct(preds, conditions, capacity=0.0)

        assert corrected[0] == 0.0
        assert len(records) == 1

    def test_mismatched_lengths_raises(self):
        """predictions and conditions length mismatch should raise ValueError."""
        corrector = PredictionCorrector()
        preds = np.array([1.0, 2.0])
        conditions = [WeatherCondition("normal", "info", {}, "none")]

        with pytest.raises(ValueError):
            corrector.correct(preds, conditions, capacity=100.0)
