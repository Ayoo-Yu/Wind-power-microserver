# tests/test_extreme_weather_detector.py
"""Comprehensive tests for ExtremeWeatherDetector.

Covers: each detection rule, boundary values, priority ordering,
batch detection, get_active_conditions filtering, custom thresholds,
and missing-field defaults.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.extreme_weather_detector import (
    DEFAULT_THRESHOLDS,
    ExtremeWeatherDetector,
    WeatherCondition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(**overrides: float) -> dict:
    """Build an ECMWF row with safe defaults, overridden by *overrides*."""
    defaults = {
        "ws100_avg": 10.0,
        "temp_2t_avg": 15.0,
        "tcwv_avg": 10.0,
        "temp_24h_drop": 0.0,
    }
    return {**defaults, **overrides}


# ---------------------------------------------------------------------------
# 1. WeatherCondition dataclass basics
# ---------------------------------------------------------------------------

class TestWeatherConditionDataclass:
    """Verify the WeatherCondition dataclass shape."""

    def test_fields_present(self):
        cond = WeatherCondition(
            condition_type="normal",
            severity="info",
            details={"ws100_avg": 1.0},
            correction_hint="none",
        )
        assert cond.condition_type == "normal"
        assert cond.severity == "info"
        assert cond.details == {"ws100_avg": 1.0}
        assert cond.correction_hint == "none"

    def test_details_default_factory(self):
        cond = WeatherCondition(condition_type="normal", severity="info")
        assert cond.details == {}

    def test_correction_hint_default(self):
        cond = WeatherCondition(condition_type="normal", severity="info")
        assert cond.correction_hint == "none"

    def test_details_isolation(self):
        """Each instance should get its own details dict."""
        c1 = WeatherCondition(condition_type="a", severity="info")
        c2 = WeatherCondition(condition_type="b", severity="info")
        c1.details["x"] = 1
        assert "x" not in c2.details


# ---------------------------------------------------------------------------
# 2. Individual detection rules
# ---------------------------------------------------------------------------

class TestHighWindDetection:
    """ws100_avg >= 25 triggers high_wind (warning, clamp_zero)."""

    def test_above_threshold(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=26.0))
        assert result.condition_type == "high_wind"
        assert result.severity == "warning"
        assert result.correction_hint == "clamp_zero"

    def test_at_threshold(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=25.0))
        assert result.condition_type == "high_wind"

    def test_below_threshold(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=24.9))
        assert result.condition_type != "high_wind"


class TestTyphoonDetection:
    """ws100_avg >= 32 triggers typhoon (danger, clamp_zero)."""

    def test_above_threshold(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=33.0))
        assert result.condition_type == "typhoon"
        assert result.severity == "danger"
        assert result.correction_hint == "clamp_zero"

    def test_at_threshold(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=32.0))
        assert result.condition_type == "typhoon"

    def test_below_threshold_is_high_wind(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=31.9))
        assert result.condition_type == "high_wind"


class TestColdWaveDetection:
    """temp <= -5 AND 24h drop > 8 triggers cold_wave (warning, apply_decay)."""

    def test_meets_both_criteria(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=-6.0, temp_24h_drop=9.0))
        assert result.condition_type == "cold_wave"
        assert result.severity == "warning"
        assert result.correction_hint == "apply_decay"

    def test_cold_but_no_drop(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=-10.0, temp_24h_drop=7.0))
        assert result.condition_type != "cold_wave"

    def test_big_drop_but_not_cold(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=0.0, temp_24h_drop=10.0))
        assert result.condition_type != "cold_wave"

    def test_temp_at_boundary_drop_above(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=-5.0, temp_24h_drop=8.1))
        assert result.condition_type == "cold_wave"

    def test_temp_at_boundary_drop_at(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=-5.0, temp_24h_drop=8.0))
        assert result.condition_type != "cold_wave"


class TestIcingDetection:
    """temp in [-5, 2] AND tcwv > 15 triggers icing (warning, apply_decay)."""

    def test_meets_both_criteria(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=-2.0, tcwv_avg=16.0))
        assert result.condition_type == "icing"
        assert result.severity == "warning"
        assert result.correction_hint == "apply_decay"

    def test_in_temp_range_low_tcwv(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=-2.0, tcwv_avg=14.0))
        assert result.condition_type != "icing"

    def test_high_tcwv_warm_temp(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=10.0, tcwv_avg=20.0))
        assert result.condition_type != "icing"

    def test_temp_at_low_boundary(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=-5.0, tcwv_avg=16.0))
        assert result.condition_type == "icing"

    def test_temp_at_high_boundary(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=2.0, tcwv_avg=16.0))
        assert result.condition_type == "icing"

    def test_temp_just_below_range(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=-5.1, tcwv_avg=16.0))
        assert result.condition_type != "icing"

    def test_temp_just_above_range(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=2.1, tcwv_avg=16.0))
        assert result.condition_type != "icing"

    def test_tcwv_at_boundary(self):
        """tcwv must be > 15, so tcwv == 15 should NOT trigger icing."""
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=0.0, tcwv_avg=15.0))
        assert result.condition_type != "icing"


class TestCalmWindDetection:
    """ws100_avg < 3 triggers calm_wind (info, clamp_zero)."""

    def test_below_threshold(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=2.0))
        assert result.condition_type == "calm_wind"
        assert result.severity == "info"
        assert result.correction_hint == "clamp_zero"

    def test_at_threshold_not_triggered(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=3.0))
        assert result.condition_type != "calm_wind"

    def test_zero_wind(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=0.0))
        assert result.condition_type == "calm_wind"


class TestNormalDetection:
    """When no extreme condition is met, return normal."""

    def test_moderate_conditions(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=10.0, temp_2t_avg=15.0))
        assert result.condition_type == "normal"
        assert result.severity == "info"
        assert result.correction_hint == "none"


# ---------------------------------------------------------------------------
# 3. Priority order (first match wins)
# ---------------------------------------------------------------------------

class TestPriorityOrder:
    """typhoon > high_wind > cold_wave > icing > calm_wind > normal."""

    def test_typhoon_overrides_high_wind(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=35.0))
        assert result.condition_type == "typhoon"

    def test_high_wind_overrides_cold_wave(self):
        """ws100 >= 25 with cold+drop should still be high_wind."""
        det = ExtremeWeatherDetector()
        result = det.detect(
            _row(ws100_avg=26.0, temp_2t_avg=-6.0, temp_24h_drop=9.0)
        )
        assert result.condition_type == "high_wind"

    def test_cold_wave_overrides_icing(self):
        """temp=-6, drop=9 meets cold_wave AND temp=-6 with tcwv=16 meets icing.
        cold_wave should win."""
        det = ExtremeWeatherDetector()
        result = det.detect(
            _row(temp_2t_avg=-5.0, temp_24h_drop=9.0, tcwv_avg=16.0, ws100_avg=10.0)
        )
        assert result.condition_type == "cold_wave"

    def test_icing_overrides_calm_wind(self):
        """ws100 < 3 (calm) AND icing criteria met => icing wins."""
        det = ExtremeWeatherDetector()
        result = det.detect(
            _row(ws100_avg=2.0, temp_2t_avg=-2.0, tcwv_avg=16.0)
        )
        assert result.condition_type == "icing"

    def test_calm_wind_when_no_higher_priority(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=2.0, temp_2t_avg=15.0, tcwv_avg=5.0))
        assert result.condition_type == "calm_wind"


# ---------------------------------------------------------------------------
# 4. Missing fields default to safe values
# ---------------------------------------------------------------------------

class TestMissingFields:
    """Missing fields should default so that the result is 'normal'."""

    def test_empty_dict(self):
        det = ExtremeWeatherDetector()
        result = det.detect({})
        assert result.condition_type == "normal"

    def test_missing_ws100(self):
        det = ExtremeWeatherDetector()
        result = det.detect({"temp_2t_avg": 15.0})
        assert result.condition_type == "normal"

    def test_missing_temp(self):
        det = ExtremeWeatherDetector()
        result = det.detect({"ws100_avg": 10.0})
        assert result.condition_type == "normal"

    def test_missing_all_ecmwf_fields(self):
        det = ExtremeWeatherDetector()
        result = det.detect({"some_other_field": 42.0})
        assert result.condition_type == "normal"

    def test_none_values_treated_as_missing(self):
        det = ExtremeWeatherDetector()
        result = det.detect({"ws100_avg": None, "temp_2t_avg": None})
        assert result.condition_type == "normal"


# ---------------------------------------------------------------------------
# 5. Batch detection on DataFrame
# ---------------------------------------------------------------------------

class TestBatchDetection:
    """detect_batch should process a DataFrame and return a list."""

    def test_batch_returns_list(self):
        det = ExtremeWeatherDetector()
        df = pd.DataFrame([
            {"ws100_avg": 35.0, "temp_2t_avg": 20.0, "tcwv_avg": 5.0, "temp_24h_drop": 0.0},
            {"ws100_avg": 2.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0, "temp_24h_drop": 0.0},
            {"ws100_avg": 10.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0, "temp_24h_drop": 0.0},
        ])
        results = det.detect_batch(df)
        assert len(results) == 3
        assert results[0].condition_type == "typhoon"
        assert results[1].condition_type == "calm_wind"
        assert results[2].condition_type == "normal"

    def test_batch_empty_dataframe(self):
        det = ExtremeWeatherDetector()
        df = pd.DataFrame()
        results = det.detect_batch(df)
        assert results == []

    def test_batch_with_missing_columns(self):
        det = ExtremeWeatherDetector()
        df = pd.DataFrame([{"ws100_avg": 10.0}])
        results = det.detect_batch(df)
        assert len(results) == 1
        assert results[0].condition_type == "normal"

    def test_batch_preserves_order(self):
        det = ExtremeWeatherDetector()
        df = pd.DataFrame([
            {"ws100_avg": 10.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0, "temp_24h_drop": 0.0},
            {"ws100_avg": 33.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0, "temp_24h_drop": 0.0},
        ])
        results = det.detect_batch(df)
        assert results[0].condition_type == "normal"
        assert results[1].condition_type == "typhoon"


# ---------------------------------------------------------------------------
# 6. get_active_conditions filtering
# ---------------------------------------------------------------------------

class TestGetActiveConditions:
    """get_active_conditions filters out 'normal' conditions."""

    def test_filters_normal(self):
        det = ExtremeWeatherDetector()
        conditions = [
            WeatherCondition("normal", "info", {}, "none"),
            WeatherCondition("high_wind", "warning", {}, "clamp_zero"),
            WeatherCondition("normal", "info", {}, "none"),
        ]
        active = det.get_active_conditions(conditions)
        assert len(active) == 1
        assert active[0].condition_type == "high_wind"

    def test_empty_list(self):
        det = ExtremeWeatherDetector()
        assert det.get_active_conditions([]) == []

    def test_all_normal(self):
        det = ExtremeWeatherDetector()
        conditions = [
            WeatherCondition("normal", "info", {}, "none"),
            WeatherCondition("normal", "info", {}, "none"),
        ]
        assert det.get_active_conditions(conditions) == []

    def test_all_active(self):
        det = ExtremeWeatherDetector()
        conditions = [
            WeatherCondition("typhoon", "danger", {}, "clamp_zero"),
            WeatherCondition("icing", "warning", {}, "apply_decay"),
        ]
        active = det.get_active_conditions(conditions)
        assert len(active) == 2

    def test_preserves_details(self):
        det = ExtremeWeatherDetector()
        conditions = [
            WeatherCondition("high_wind", "warning", {"ws100_avg": 26.0}, "clamp_zero"),
        ]
        active = det.get_active_conditions(conditions)
        assert active[0].details == {"ws100_avg": 26.0}


# ---------------------------------------------------------------------------
# 7. Custom threshold override
# ---------------------------------------------------------------------------

class TestCustomThresholds:
    """Constructor accepts custom thresholds that override defaults."""

    def test_lower_high_wind_threshold(self):
        det = ExtremeWeatherDetector(thresholds={"high_wind_speed": 20.0})
        result = det.detect(_row(ws100_avg=21.0))
        assert result.condition_type == "high_wind"

    def test_higher_typhoon_threshold(self):
        det = ExtremeWeatherDetector(thresholds={"typhoon_speed": 40.0})
        result = det.detect(_row(ws100_avg=35.0))
        assert result.condition_type == "high_wind"

    def test_custom_calm_wind_threshold(self):
        det = ExtremeWeatherDetector(thresholds={"calm_wind_speed": 5.0})
        result = det.detect(_row(ws100_avg=4.0))
        assert result.condition_type == "calm_wind"

    def test_custom_cold_wave_temp(self):
        det = ExtremeWeatherDetector(thresholds={"cold_wave_temp": 0.0})
        result = det.detect(_row(temp_2t_avg=-1.0, temp_24h_drop=9.0))
        assert result.condition_type == "cold_wave"

    def test_custom_icing_tcwv(self):
        det = ExtremeWeatherDetector(thresholds={"icing_tcwv": 10.0})
        result = det.detect(_row(temp_2t_avg=0.0, tcwv_avg=11.0))
        assert result.condition_type == "icing"

    def test_default_thresholds_unchanged(self):
        """Custom thresholds should not mutate DEFAULT_THRESHOLDS."""
        original = dict(DEFAULT_THRESHOLDS)
        ExtremeWeatherDetector(thresholds={"high_wind_speed": 99.0})
        assert DEFAULT_THRESHOLDS == original


# ---------------------------------------------------------------------------
# 8. Details populated correctly
# ---------------------------------------------------------------------------

class TestDetailsPopulated:
    """The details dict should contain relevant field values."""

    def test_high_wind_details(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(ws100_avg=26.0))
        assert "ws100_avg" in result.details
        assert result.details["ws100_avg"] == 26.0

    def test_cold_wave_details(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=-6.0, temp_24h_drop=9.0))
        assert "temp_2t_avg" in result.details
        assert "temp_24h_drop" in result.details

    def test_icing_details(self):
        det = ExtremeWeatherDetector()
        result = det.detect(_row(temp_2t_avg=-2.0, tcwv_avg=16.0))
        assert "temp_2t_avg" in result.details
        assert "tcwv_avg" in result.details
