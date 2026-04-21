# Extreme Weather Handling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect extreme weather from ECMWF forecast data, apply post-processing corrections to wind power predictions, and inject alerts into the existing alarm system.

**Architecture:** Two independent service classes (`ExtremeWeatherDetector` and `PredictionCorrector`) inserted into the prediction pipeline. A Flask blueprint exposes REST endpoints. Frontend overlays extreme weather bands on prediction charts and adds a status card.

**Tech Stack:** Python 3.10+, dataclasses, numpy, pandas, Flask, SQLAlchemy, Vue 3, ECharts

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `backend-autopredict/services/extreme_weather_detector.py` | `WeatherCondition` dataclass + `ExtremeWeatherDetector` class |
| `backend-autopredict/services/prediction_corrector.py` | `PredictionCorrector` class |
| `backend-autopredict/routes/extreme_weather_router.py` | Flask blueprint with 4 endpoints |
| `backend-autopredict/tests/test_extreme_weather_detector.py` | Detector unit tests |
| `backend-autopredict/tests/test_prediction_corrector.py` | Corrector unit tests |
| `backend-autopredict/tests/test_extreme_weather_api.py` | API integration tests |
| `frontend/src/api/extremeWeatherApi.js` | API client |
| `frontend/src/components/ExtremeWeatherCard.vue` | Dashboard status card |

### Modified files
| File | Change |
|------|--------|
| `backend-autopredict/app.py:76-87` | Register `extreme_weather_bp` blueprint |
| `backend-autopredict/auto_scripts/scripts/auto_pre_train_base.py` | Call detector + corrector after prediction, inject alarms |

---

## Task 1: WeatherCondition dataclass + ExtremeWeatherDetector

**Files:**
- Create: `backend-autopredict/services/extreme_weather_detector.py`
- Test: `backend-autopredict/tests/test_extreme_weather_detector.py`

- [ ] **Step 1: Write failing tests for WeatherCondition and detection rules**

Create `D:\Wind-power-microserver\wind-power-forecast\backend-autopredict\tests\test_extreme_weather_detector.py`:

```python
"""Tests for ExtremeWeatherDetector."""
import pytest
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestWeatherCondition:
    """Test WeatherCondition dataclass."""

    def test_normal_condition(self):
        from services.extreme_weather_detector import WeatherCondition
        wc = WeatherCondition(
            condition_type="normal", severity="info",
            details={}, correction_hint="none",
        )
        assert wc.condition_type == "normal"
        assert wc.correction_hint == "none"


class TestDetectorHighWind:
    """Test high wind detection (ws100 >= 25 m/s)."""

    def test_high_wind_detected(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 28.0, "ws10_avg": 10.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0}
        result = det.detect(row)
        assert result.condition_type == "high_wind"
        assert result.severity == "warning"
        assert result.correction_hint == "clamp_zero"

    def test_high_wind_boundary(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 25.0, "ws10_avg": 10.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0}
        result = det.detect(row)
        assert result.condition_type == "high_wind"

    def test_just_below_high_wind(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 24.9, "ws10_avg": 10.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0}
        result = det.detect(row)
        assert result.condition_type == "normal"


class TestDetectorTyphoon:
    """Test typhoon detection (ws100 >= 32 m/s, overrides high_wind)."""

    def test_typhoon_detected(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 35.0, "ws10_avg": 15.0, "temp_2t_avg": 20.0, "tcwv_avg": 8.0}
        result = det.detect(row)
        assert result.condition_type == "typhoon"
        assert result.severity == "danger"
        assert result.correction_hint == "clamp_zero"


class TestDetectorCalmWind:
    """Test calm wind detection (ws100 < 3 m/s)."""

    def test_calm_wind_detected(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 2.0, "ws10_avg": 1.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0}
        result = det.detect(row)
        assert result.condition_type == "calm_wind"
        assert result.severity == "info"
        assert result.correction_hint == "clamp_zero"

    def test_calm_wind_boundary(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 2.99, "ws10_avg": 1.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0}
        result = det.detect(row)
        assert result.condition_type == "calm_wind"


class TestDetectorColdWave:
    """Test cold wave detection (temp <= -5C AND 24h drop > 8C)."""

    def test_cold_wave_detected(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": -8.0, "tcwv_avg": 5.0, "temp_24h_drop": 10.0}
        result = det.detect(row)
        assert result.condition_type == "cold_wave"
        assert result.severity == "warning"
        assert result.correction_hint == "apply_decay"

    def test_cold_temp_no_drop(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": -8.0, "tcwv_avg": 5.0, "temp_24h_drop": 3.0}
        result = det.detect(row)
        assert result.condition_type == "normal"

    def test_warm_temp_with_drop(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": 5.0, "tcwv_avg": 5.0, "temp_24h_drop": 10.0}
        result = det.detect(row)
        assert result.condition_type == "normal"


class TestDetectorIcing:
    """Test icing detection (temp in [-5, 2]C AND tcwv > 15)."""

    def test_icing_detected(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": -2.0, "tcwv_avg": 18.0}
        result = det.detect(row)
        assert result.condition_type == "icing"
        assert result.severity == "warning"
        assert result.correction_hint == "apply_decay"

    def test_icing_boundary_temp_high(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": 2.0, "tcwv_avg": 18.0}
        result = det.detect(row)
        assert result.condition_type == "icing"

    def test_icing_no_moisture(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": -2.0, "tcwv_avg": 10.0}
        result = det.detect(row)
        assert result.condition_type == "normal"


class TestDetectorPriority:
    """Test priority order: typhoon > high_wind > cold_wave > icing > calm_wind > normal."""

    def test_typhoon_over_high_wind(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 33.0, "ws10_avg": 15.0, "temp_2t_avg": -8.0, "tcwv_avg": 18.0, "temp_24h_drop": 10.0}
        result = det.detect(row)
        assert result.condition_type == "typhoon"

    def test_high_wind_over_cold_wave(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {"ws100_avg": 27.0, "ws10_avg": 12.0, "temp_2t_avg": -8.0, "tcwv_avg": 5.0, "temp_24h_drop": 10.0}
        result = det.detect(row)
        assert result.condition_type == "high_wind"


class TestDetectorBatch:
    """Test batch detection on DataFrame."""

    def test_batch_returns_list(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        df = pd.DataFrame([
            {"ws100_avg": 28.0, "ws10_avg": 10.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},
            {"ws100_avg": 2.0, "ws10_avg": 1.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},
            {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},
        ])
        results = det.detect_batch(df)
        assert len(results) == 3
        assert results[0].condition_type == "high_wind"
        assert results[1].condition_type == "calm_wind"
        assert results[2].condition_type == "normal"

    def test_get_active_conditions(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector, WeatherCondition
        det = ExtremeWeatherDetector()
        conditions = [
            WeatherCondition("normal", "info", {}, "none"),
            WeatherCondition("high_wind", "warning", {}, "clamp_zero"),
            WeatherCondition("normal", "info", {}, "none"),
        ]
        active = det.get_active_conditions(conditions)
        assert len(active) == 1
        assert active[0].condition_type == "high_wind"


class TestDetectorCustomThresholds:
    """Test custom threshold override."""

    def test_custom_high_wind_threshold(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector(thresholds={"high_wind_speed": 20.0, "typhoon_speed": 32.0, "calm_wind_speed": 3.0})
        row = {"ws100_avg": 22.0, "ws10_avg": 10.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0}
        result = det.detect(row)
        assert result.condition_type == "high_wind"

    def test_missing_fields_default_normal(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        det = ExtremeWeatherDetector()
        row = {}
        result = det.detect(row)
        assert result.condition_type == "normal"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/test_extreme_weather_detector.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement ExtremeWeatherDetector**

Create `D:\Wind-power-microserver\wind-power-forecast\backend-autopredict\services\extreme_weather_detector.py`:

```python
"""Extreme weather detection from ECMWF forecast data."""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "high_wind_speed": 25.0,
    "typhoon_speed": 32.0,
    "calm_wind_speed": 3.0,
    "cold_wave_temp": -5.0,
    "cold_wave_drop_24h": 8.0,
    "icing_temp_low": -5.0,
    "icing_temp_high": 2.0,
    "icing_tcwv": 15.0,
}


@dataclass
class WeatherCondition:
    condition_type: str
    severity: str
    details: dict = field(default_factory=dict)
    correction_hint: str = "none"


class ExtremeWeatherDetector:
    """Detects extreme weather conditions from ECMWF data rows."""

    def __init__(self, thresholds: dict | None = None):
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def detect(self, ecmwf_row: dict) -> WeatherCondition:
        """Detect extreme weather from a single ECMWF data row.

        Expects keys: ws100_avg, temp_2t_avg, tcwv_avg, temp_24h_drop (optional).
        Returns normal if required fields are missing.
        """
        ws = ecmwf_row.get("ws100_avg", float("inf"))
        temp = ecmwf_row.get("temp_2t_avg", float("inf"))
        tcwv = ecmwf_row.get("tcwv_avg", 0.0)
        drop = ecmwf_row.get("temp_24h_drop", 0.0)

        if ws >= self.thresholds["typhoon_speed"]:
            return WeatherCondition("typhoon", "danger",
                                    {"wind_speed": ws, "threshold": self.thresholds["typhoon_speed"]},
                                    "clamp_zero")

        if ws >= self.thresholds["high_wind_speed"]:
            return WeatherCondition("high_wind", "warning",
                                    {"wind_speed": ws, "threshold": self.thresholds["high_wind_speed"]},
                                    "clamp_zero")

        if temp <= self.thresholds["cold_wave_temp"] and drop > self.thresholds["cold_wave_drop_24h"]:
            return WeatherCondition("cold_wave", "warning",
                                    {"temperature": temp, "drop_24h": drop, "threshold": self.thresholds["cold_wave_temp"]},
                                    "apply_decay")

        if (self.thresholds["icing_temp_low"] <= temp <= self.thresholds["icing_temp_high"]
                and tcwv > self.thresholds["icing_tcwv"]):
            return WeatherCondition("icing", "warning",
                                    {"temperature": temp, "tcwv": tcwv, "tcwv_threshold": self.thresholds["icing_tcwv"]},
                                    "apply_decay")

        if ws < self.thresholds["calm_wind_speed"]:
            return WeatherCondition("calm_wind", "info",
                                    {"wind_speed": ws, "threshold": self.thresholds["calm_wind_speed"]},
                                    "clamp_zero")

        return WeatherCondition("normal", "info", {}, "none")

    def detect_batch(self, ecmwf_df) -> list[WeatherCondition]:
        """Detect extreme weather for each row in a DataFrame."""
        results = []
        for _, row in ecmwf_df.iterrows():
            results.append(self.detect(row.to_dict()))
        return results

    def get_active_conditions(self, conditions: list[WeatherCondition]) -> list[WeatherCondition]:
        """Filter out normal conditions, returning only active alerts."""
        return [c for c in conditions if c.condition_type != "normal"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/test_extreme_weather_detector.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend-autopredict/services/extreme_weather_detector.py backend-autopredict/tests/test_extreme_weather_detector.py
git commit -m "feat: add ExtremeWeatherDetector with threshold-based detection"
```

---

## Task 2: PredictionCorrector

**Files:**
- Create: `backend-autopredict/services/prediction_corrector.py`
- Test: `backend-autopredict/tests/test_prediction_corrector.py`

- [ ] **Step 1: Write failing tests for PredictionCorrector**

Create `D:\Wind-power-microserver\wind-power-forecast\backend-autopredict\tests\test_prediction_corrector.py`:

```python
"""Tests for PredictionCorrector."""
import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _make_condition(cond_type, details=None):
    from services.extreme_weather_detector import WeatherCondition
    return WeatherCondition(
        condition_type=cond_type,
        severity="warning" if cond_type not in ("normal", "calm_wind") else "info",
        details=details or {},
        correction_hint="clamp_zero" if cond_type in ("high_wind", "typhoon", "calm_wind") else "apply_decay" if cond_type in ("cold_wave", "icing") else "none",
    )


class TestClampZero:
    """High wind, typhoon, calm wind → clamp to 0."""

    def test_high_wind_clamps_to_zero(self):
        from services.prediction_corrector import PredictionCorrector
        corr = PredictionCorrector()
        preds = np.array([100.0, 200.0, 300.0])
        conditions = [_make_condition("high_wind")] * 3
        corrected, records = corr.correct(preds, conditions, capacity=500.0)
        assert np.all(corrected == 0.0)
        assert len(records) == 3

    def test_typhoon_clamps_to_zero(self):
        from services.prediction_corrector import PredictionCorrector
        corr = PredictionCorrector()
        preds = np.array([50.0])
        conditions = [_make_condition("typhoon")]
        corrected, records = corr.correct(preds, conditions, capacity=500.0)
        assert corrected[0] == 0.0

    def test_calm_wind_clamps_to_zero(self):
        from services.prediction_corrector import PredictionCorrector
        corr = PredictionCorrector()
        preds = np.array([10.0, 20.0])
        conditions = [_make_condition("calm_wind")] * 2
        corrected, _ = corr.correct(preds, conditions, capacity=500.0)
        assert np.all(corrected == 0.0)


class TestApplyDecay:
    """Cold wave and icing → dynamic decay."""

    def test_cold_wave_decay(self):
        from services.prediction_corrector import PredictionCorrector
        corr = PredictionCorrector()
        preds = np.array([100.0])
        cond = _make_condition("cold_wave", {"temperature": -8.0})
        conditions = [cond]
        corrected, _ = corr.correct(preds, conditions, capacity=500.0)
        # decay = max(0.3, 0.7 - (abs(-8) - 5) * 0.05) = max(0.3, 0.7 - 0.15) = 0.55
        assert abs(corrected[0] - 55.0) < 0.01

    def test_icing_decay(self):
        from services.prediction_corrector import PredictionCorrector
        corr = PredictionCorrector()
        preds = np.array([100.0])
        cond = _make_condition("icing", {"tcwv": 18.0})
        conditions = [cond]
        corrected, _ = corr.correct(preds, conditions, capacity=500.0)
        # decay = max(0.3, 0.6 - (18 - 10) * 0.02) = max(0.3, 0.6 - 0.16) = 0.44
        assert abs(corrected[0] - 44.0) < 0.01

    def test_decay_floor_at_0_3(self):
        from services.prediction_corrector import PredictionCorrector
        corr = PredictionCorrector()
        preds = np.array([100.0])
        cond = _make_condition("cold_wave", {"temperature": -25.0})
        conditions = [cond]
        corrected, _ = corr.correct(preds, conditions, capacity=500.0)
        # decay = max(0.3, 0.7 - (25 - 5) * 0.05) = max(0.3, -0.3) = 0.3
        assert abs(corrected[0] - 30.0) < 0.01


class TestImmutability:
    """Corrector must not modify input array."""

    def test_input_unchanged(self):
        from services.prediction_corrector import PredictionCorrector
        corr = PredictionCorrector()
        preds = np.array([100.0, 200.0])
        preds_copy = preds.copy()
        conditions = [_make_condition("high_wind"), _make_condition("normal")]
        corr.correct(preds, conditions, capacity=500.0)
        assert np.array_equal(preds, preds_copy)


class TestCapacityClamp:
    """Corrected values stay within [0, capacity]."""

    def test_capacity_clamp(self):
        from services.prediction_corrector import PredictionCorrector
        corr = PredictionCorrector()
        preds = np.array([600.0, 500.0])
        conditions = [_make_condition("normal"), _make_condition("normal")]
        corrected, _ = corr.correct(preds, conditions, capacity=500.0)
        assert corrected[0] == 500.0
        assert corrected[1] == 500.0


class TestNormalNoCorrection:
    """Normal conditions should not change predictions."""

    def test_normal_no_change(self):
        from services.prediction_corrector import PredictionCorrector
        corr = PredictionCorrector()
        preds = np.array([100.0, 200.0])
        conditions = [_make_condition("normal")] * 2
        corrected, records = corr.correct(preds, conditions, capacity=500.0)
        assert np.array_equal(corrected, preds)
        assert len(records) == 0


class TestCorrectionRecords:
    """Each correction should be recorded with before/after/reason."""

    def test_records_have_required_fields(self):
        from services.prediction_corrector import PredictionCorrector
        corr = PredictionCorrector()
        preds = np.array([100.0])
        conditions = [_make_condition("high_wind")]
        _, records = corr.correct(preds, conditions, capacity=500.0)
        assert len(records) == 1
        rec = records[0]
        assert rec["index"] == 0
        assert rec["type"] == "high_wind"
        assert rec["before"] == 100.0
        assert rec["after"] == 0.0
        assert "reason" in rec


class TestCorrectionSummary:
    """Test get_correction_summary aggregation."""

    def test_summary_counts(self):
        from services.prediction_corrector import PredictionCorrector
        corr = PredictionCorrector()
        records = [
            {"index": 0, "type": "high_wind", "before": 100.0, "after": 0.0, "reason": "clamp"},
            {"index": 1, "type": "cold_wave", "before": 200.0, "after": 110.0, "reason": "decay"},
        ]
        summary = corr.get_correction_summary(records)
        assert summary["total_corrections"] == 2
        assert summary["by_type"]["high_wind"] == 1
        assert summary["by_type"]["cold_wave"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/test_prediction_corrector.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement PredictionCorrector**

Create `D:\Wind-power-microserver\wind-power-forecast\backend-autopredict\services\prediction_corrector.py`:

```python
"""Post-processing corrections for wind power predictions under extreme weather."""
import logging
import numpy as np

from services.extreme_weather_detector import WeatherCondition

logger = logging.getLogger(__name__)


class PredictionCorrector:
    """Applies post-processing corrections to predictions based on weather conditions."""

    def correct(
        self,
        predictions: np.ndarray,
        conditions: list[WeatherCondition],
        capacity: float,
    ) -> tuple[np.ndarray, list[dict]]:
        """Correct predictions based on weather conditions.

        Returns (corrected_predictions, correction_records).
        Input array is never modified.
        """
        corrected = predictions.copy()
        records = []

        for i, cond in enumerate(conditions):
            if i >= len(corrected):
                break

            before = float(corrected[i])

            if cond.correction_hint == "clamp_zero":
                corrected[i] = 0.0
            elif cond.correction_hint == "apply_decay":
                decay = self._compute_decay(cond)
                corrected[i] *= decay

            # Capacity clamp
            corrected[i] = np.clip(corrected[i], 0.0, capacity)

            after = float(corrected[i])
            if abs(after - before) > 0.01:
                records.append({
                    "index": i,
                    "type": cond.condition_type,
                    "before": before,
                    "after": after,
                    "reason": self._describe_correction(cond),
                })

        return corrected, records

    def get_correction_summary(self, correction_records: list[dict]) -> dict:
        """Aggregate correction records into a summary."""
        by_type: dict[str, int] = {}
        for rec in correction_records:
            t = rec["type"]
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_corrections": len(correction_records),
            "by_type": by_type,
        }

    def _compute_decay(self, cond: WeatherCondition) -> float:
        """Compute dynamic decay factor for cold_wave and icing."""
        if cond.condition_type == "cold_wave":
            temp = abs(cond.details.get("temperature", -5.0))
            return max(0.3, 0.7 - (temp - 5.0) * 0.05)
        elif cond.condition_type == "icing":
            tcwv = cond.details.get("tcwv", 15.0)
            return max(0.3, 0.6 - (tcwv - 10.0) * 0.02)
        return 1.0

    def _describe_correction(self, cond: WeatherCondition) -> str:
        reasons = {
            "high_wind": "超大风停机",
            "typhoon": "台风停机",
            "calm_wind": "无风停机",
            "cold_wave": "寒潮衰减",
            "icing": "结冰衰减",
        }
        return reasons.get(cond.condition_type, cond.condition_type)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/test_prediction_corrector.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend-autopredict/services/prediction_corrector.py backend-autopredict/tests/test_prediction_corrector.py
git commit -m "feat: add PredictionCorrector with dynamic decay and clamp logic"
```

---

## Task 3: API Blueprint + Blueprint Registration

**Files:**
- Create: `backend-autopredict/routes/extreme_weather_router.py`
- Modify: `backend-autopredict/app.py:76-87`
- Test: `backend-autopredict/tests/test_extreme_weather_api.py`

- [ ] **Step 1: Write failing API tests**

Create `D:\Wind-power-microserver\wind-power-forecast\backend-autopredict\tests\test_extreme_weather_api.py`:

```python
"""Integration tests for extreme weather API endpoints."""
import pytest
import sys
import os
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestThresholdEndpoints:
    """Test GET/PUT /api/extreme-weather/thresholds."""

    def test_get_thresholds(self):
        from routes.extreme_weather_router import extreme_weather_bp
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(extreme_weather_bp, url_prefix="/api/extreme-weather")
        with app.test_client() as client:
            resp = client.get("/api/extreme-weather/thresholds")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "high_wind_speed" in data
            assert data["high_wind_speed"] == 25.0

    def test_put_thresholds(self):
        from routes.extreme_weather_router import extreme_weather_bp
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(extreme_weather_bp, url_prefix="/api/extreme-weather")
        with app.test_client() as client:
            resp = client.put(
                "/api/extreme-weather/thresholds",
                json={"high_wind_speed": 20.0},
                content_type="application/json",
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["high_wind_speed"] == 20.0


class TestStatusEndpoint:
    """Test GET /api/extreme-weather/status."""

    def test_status_with_farm_code(self):
        from routes.extreme_weather_router import extreme_weather_bp
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(extreme_weather_bp, url_prefix="/api/extreme-weather")
        with app.test_client() as client:
            resp = client.get("/api/extreme-weather/status?farm_code=zyx01")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "farm_code" in data
            assert "current_condition" in data

    def test_status_missing_farm_defaults(self):
        from routes.extreme_weather_router import extreme_weather_bp
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(extreme_weather_bp, url_prefix="/api/extreme-weather")
        with app.test_client() as client:
            resp = client.get("/api/extreme-weather/status")
            assert resp.status_code == 200


class TestHistoryEndpoint:
    """Test GET /api/extreme-weather/history."""

    def test_history_returns_list(self):
        from routes.extreme_weather_router import extreme_weather_bp
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(extreme_weather_bp, url_prefix="/api/extreme-weather")
        with app.test_client() as client:
            with patch("routes.extreme_weather_router._get_alarm_history") as mock_hist:
                mock_hist.return_value = []
                resp = client.get("/api/extreme-weather/history?farm_code=zyx01")
                assert resp.status_code == 200
                data = resp.get_json()
                assert "events" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/test_extreme_weather_api.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement extreme_weather_router.py**

Create `D:\Wind-power-microserver\wind-power-forecast\backend-autopredict\routes\extreme_weather_router.py`:

```python
"""Extreme weather detection and prediction correction API."""
import logging
from flask import Blueprint, request, jsonify

from services.extreme_weather_detector import ExtremeWeatherDetector, DEFAULT_THRESHOLDS

logger = logging.getLogger(__name__)

extreme_weather_bp = Blueprint("extreme_weather", __name__)

_detector = ExtremeWeatherDetector()


@extreme_weather_bp.route("/thresholds", methods=["GET"])
def get_thresholds():
    return jsonify(_detector.thresholds)


@extreme_weather_bp.route("/thresholds", methods=["PUT"])
def update_thresholds():
    updates = request.get_json(silent=True) or {}
    for key, value in updates.items():
        if key in _detector.thresholds:
            _detector.thresholds[key] = float(value)
    logger.info("Updated extreme weather thresholds: %s", updates)
    return jsonify(_detector.thresholds)


@extreme_weather_bp.route("/status", methods=["GET"])
def get_status():
    farm_code = request.args.get("farm_code", "DEFAULT_FARM")
    try:
        condition = _get_current_condition(farm_code)
    except Exception:
        condition = {"type": "normal", "severity": "info", "details": {}}
    return jsonify({
        "farm_code": farm_code,
        "current_condition": condition,
        "active_alerts": 0,
        "last_checked": None,
    })


@extreme_weather_bp.route("/history", methods=["GET"])
def get_history():
    farm_code = request.args.get("farm_code", "DEFAULT_FARM")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    events = _get_alarm_history(farm_code, page, per_page)
    return jsonify({"events": events, "page": page, "per_page": per_page})


def _get_current_condition(farm_code: str) -> dict:
    """Query latest ECMWF data and detect conditions. Returns dict."""
    return {"type": "normal", "severity": "info", "details": {}}


def _get_alarm_history(farm_code: str, page: int, per_page: int) -> list:
    """Query alarm records for extreme weather events. Returns list."""
    return []
```

- [ ] **Step 4: Register blueprint in app.py**

In `D:\Wind-power-microserver\wind-power-forecast\backend-autopredict\app.py`, add after line 83 (`app.register_blueprint(modeltrain_bp, ...)`) :

```python
from routes.extreme_weather_router import extreme_weather_bp
app.register_blueprint(extreme_weather_bp, url_prefix='/api/extreme-weather')
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/test_extreme_weather_api.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend-autopredict/routes/extreme_weather_router.py backend-autopredict/app.py backend-autopredict/tests/test_extreme_weather_api.py
git commit -m "feat: add extreme weather API endpoints (status, thresholds, history)"
```

---

## Task 4: Pipeline Integration — Detector + Corrector + Alarm Injection

**Files:**
- Modify: `backend-autopredict/auto_scripts/scripts/auto_pre_train_base.py`

This task inserts the detector + corrector into the prediction output flow. The key integration point is in `monitor_prediction()` where predictions are generated and saved. After the model produces predictions, we:

1. Convert ECMWF input data to detector-compatible format (extract ws100_avg, temp_2t_avg, tcwv_avg)
2. Run `detect_batch()` on the input rows
3. Run `correct()` on the prediction output
4. Save corrected predictions (replacing original)
5. Inject alarm records for warning/danger conditions

- [ ] **Step 1: Read auto_pre_train_base.py to find the prediction output insertion point**

Read `D:\Wind-power-microserver\wind-power-forecast\backend-autopredict\auto_scripts\scripts\auto_pre_train_base.py` and locate the `monitor_prediction` function. Find where `predict()` is called and where results are saved. The integration should happen between prediction and save.

- [ ] **Step 2: Add import and helper function**

At the top of `auto_pre_train_base.py`, add imports:

```python
from services.extreme_weather_detector import ExtremeWeatherDetector
from services.prediction_corrector import PredictionCorrector
```

Add a helper function to extract averaged ECMWF fields from the prediction input DataFrame:

```python
def _extract_ecmwf_features_for_detection(input_df):
    """Extract ws100_avg, temp_2t_avg, tcwv_avg from prediction input DataFrame.

    The DataFrame has columns like ws100_1..ws100_15, 2t_23.8_103.2..2t_24.2_103.4, etc.
    We average across grid points to get representative values.
    """
    rows = []
    for _, row in input_df.iterrows():
        d = {}

        # Average ws100 columns (ws100_1..ws100_15)
        ws100_cols = [c for c in input_df.columns if c.startswith("ws100_") and c[6:].isdigit()]
        if ws100_cols:
            vals = [row[c] for c in ws100_cols if row[c] is not None and not (isinstance(row[c], float) and row[c] != row[c])]
            d["ws100_avg"] = sum(vals) / len(vals) if vals else 0.0
        else:
            d["ws100_avg"] = 0.0

        # Average 2t columns
        temp_cols = [c for c in input_df.columns if c.startswith("2t_")]
        if temp_cols:
            vals = [row[c] for c in temp_cols if row[c] is not None and not (isinstance(row[c], float) and row[c] != row[c])]
            d["temp_2t_avg"] = sum(vals) / len(vals) if vals else 20.0
        else:
            d["temp_2t_avg"] = 20.0

        # Average tcwv columns
        tcwv_cols = [c for c in input_df.columns if c.startswith("tcwv_")]
        if tcwv_cols:
            vals = [row[c] for c in tcwv_cols if row[c] is not None and not (isinstance(row[c], float) and row[c] != row[c])]
            d["tcwv_avg"] = sum(vals) / len(vals) if vals else 0.0
        else:
            d["tcwv_avg"] = 0.0

        rows.append(d)
    return rows
```

- [ ] **Step 3: Insert detection + correction into the prediction flow**

In `monitor_prediction()`, after `predict()` returns the predictions array and before saving results, add:

```python
            # --- Extreme weather detection and correction ---
            detector = ExtremeWeatherDetector()
            corrector = PredictionCorrector()

            ecmwf_features = _extract_ecmwf_features_for_detection(input_df_for_pred)
            conditions = [detector.detect(f) for f in ecmwf_features]
            active_conditions = detector.get_active_conditions(conditions)

            if active_conditions:
                capacity = float(os.environ.get("WF_CAPACITY", 779.0))
                predictions, correction_records = corrector.correct(
                    predictions, conditions, capacity,
                )
                logging.info(
                    "%s极端天气修正: %d/%d 点被修正",
                    VARIANT["LOG_PREFIX"], len(correction_records), len(predictions),
                )
                for rec in correction_records:
                    logging.info(
                        "  修正 #%d: %s %.1f→%.1f (%s)",
                        rec["index"], rec["type"], rec["before"], rec["after"], rec["reason"],
                    )

                # Inject alarms for warning/danger conditions
                _inject_extreme_weather_alarms(active_conditions, farm_code)
```

Add the alarm injection helper:

```python
def _inject_extreme_weather_alarms(conditions, farm_code):
    """Create AlarmRecord entries for warning/danger extreme weather conditions."""
    try:
        from db_session import db_session
        from db_models import AlarmRecord
        from datetime import datetime

        for cond in conditions:
            if cond.severity not in ("warning", "danger"):
                continue
            with db_session() as session:
                alarm = AlarmRecord(
                    source="extreme_weather",
                    farm_code=farm_code,
                    module="prediction",
                    level=cond.severity,
                    message=f"检测到极端天气 [{cond.condition_type}]：{cond.details}",
                    status="open",
                    occurred_at=datetime.now(),
                )
                session.add(alarm)
    except Exception as e:
        logging.warning("Failed to inject extreme weather alarm: %s", e)
```

- [ ] **Step 4: Verify import works**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -c "from services.extreme_weather_detector import ExtremeWeatherDetector; from services.prediction_corrector import PredictionCorrector; print('OK')"`

- [ ] **Step 5: Run all tests**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend-autopredict/auto_scripts/scripts/auto_pre_train_base.py
git commit -m "feat: integrate extreme weather detection into prediction pipeline"
```

---

## Task 5: Frontend — Status Card + Weather Overlay

**Files:**
- Create: `frontend/src/api/extremeWeatherApi.js`
- Create: `frontend/src/components/ExtremeWeatherCard.vue`
- Modify: `frontend/src/components/HomePage.vue`
- Modify: `frontend/src/components/PowerCompare.vue`

- [ ] **Step 1: Create API client**

Create `D:\Wind-power-microserver\wind-power-forecast\frontend\src\api\extremeWeatherApi.js`:

```javascript
import axios from './axios'

const BASE = '/api/extreme-weather'

export function getWeatherStatus(farmCode) {
  return axios.get(`${BASE}/status`, { params: { farm_code: farmCode } })
}

export function getThresholds() {
  return axios.get(`${BASE}/thresholds`)
}

export function updateThresholds(thresholds) {
  return axios.put(`${BASE}/thresholds`, thresholds)
}

export function getWeatherHistory(farmCode, page = 1) {
  return axios.get(`${BASE}/history`, { params: { farm_code: farmCode, page } })
}
```

- [ ] **Step 2: Create ExtremeWeatherCard.vue**

Create `D:\Wind-power-microserver\wind-power-forecast\frontend\src\components\ExtremeWeatherCard.vue`:

```vue
<template>
  <div class="extreme-weather-card" :class="severityClass" @click="goToAlarmCenter">
    <div class="ewc-icon">
      <i :class="iconClass"></i>
    </div>
    <div class="ewc-info">
      <div class="ewc-title">极端天气</div>
      <div class="ewc-status">{{ statusLabel }}</div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { getWeatherStatus } from '@/api/extremeWeatherApi'
import farmService from '@/utils/farmService'

const SEVERITY_MAP = {
  normal: { label: '正常', class: 'ewc-normal', icon: 'el-icon-sunny' },
  info: { label: '注意', class: 'ewc-info-severity', icon: 'el-icon-warning-outline' },
  warning: { label: '预警', class: 'ewc-warning', icon: 'el-icon-warning' },
  danger: { label: '警报', class: 'ewc-danger', icon: 'el-icon-error' },
}

export default {
  name: 'ExtremeWeatherCard',
  setup() {
    const condition = ref({ type: 'normal', severity: 'info', details: {} })

    const severityClass = computed(() =>
      SEVERITY_MAP[condition.value.severity]?.class || 'ewc-normal'
    )
    const statusLabel = computed(() =>
      SEVERITY_MAP[condition.value.severity]?.label || '正常'
    )
    const iconClass = computed(() =>
      SEVERITY_MAP[condition.value.severity]?.icon || 'el-icon-sunny'
    )

    async function fetchStatus() {
      try {
        const farm = farmService.getCurrentFarm()
        const { data } = await getWeatherStatus(farm?.code || 'DEFAULT_FARM')
        if (data?.current_condition) {
          condition.value = data.current_condition
        }
      } catch { /* ignore */ }
    }

    function goToAlarmCenter() {
      window.location.hash = '#/alarm'
    }

    onMounted(fetchStatus)
    watch(() => farmService.getCurrentFarm(), fetchStatus)

    return { condition, severityClass, statusLabel, iconClass, goToAlarmCenter }
  },
}
</script>

<style scoped>
.extreme-weather-card {
  display: flex; align-items: center; gap: 12px;
  padding: 16px; border-radius: 8px; cursor: pointer;
  transition: background 0.3s;
}
.ewc-normal { background: #f0f9eb; }
.ewc-info-severity { background: #fdf6ec; }
.ewc-warning { background: #faecd8; }
.ewc-danger { background: #fef0f0; }
.ewc-icon { font-size: 28px; }
.ewc-normal .ewc-icon { color: #67c23a; }
.ewc-info-severity .ewc-icon { color: #e6a23c; }
.ewc-warning .ewc-icon { color: #e6a23c; }
.ewc-danger .ewc-icon { color: #f56c6c; }
.ewc-title { font-size: 14px; color: #909399; }
.ewc-status { font-size: 18px; font-weight: 600; margin-top: 4px; }
</style>
```

- [ ] **Step 3: Add ExtremeWeatherCard to HomePage.vue**

In `D:\Wind-power-microserver\wind-power-forecast\frontend\src\components\HomePage.vue`:
- Import `ExtremeWeatherCard`
- Add `<ExtremeWeatherCard />` in the dashboard KPI cards row

- [ ] **Step 4: Add weather overlay to PowerCompare.vue**

In `D:\Wind-power-microserver\wind-power-forecast\frontend\src\components\PowerCompare.vue`:
- Import `getWeatherStatus` from extremeWeatherApi
- After loading prediction data, also fetch weather status
- If corrections exist, add ECharts `markArea` to the prediction series with red/orange bands
- The overlay should only render when there are active extreme weather conditions

- [ ] **Step 5: Verify frontend builds**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\frontend && npm run build`
Expected: BUILD SUCCESS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/extremeWeatherApi.js frontend/src/components/ExtremeWeatherCard.vue frontend/src/components/HomePage.vue frontend/src/components/PowerCompare.vue
git commit -m "feat: add extreme weather status card and prediction overlay in frontend"
```

---

## Task 6: Full Integration Test

**Files:**
- Create: `backend-autopredict/tests/test_extreme_weather_pipeline.py`

- [ ] **Step 1: Write end-to-end pipeline test**

Create `D:\Wind-power-microserver\wind-power-forecast\backend-autopredict\tests\test_extreme_weather_pipeline.py`:

```python
"""End-to-end test: ECMWF data → detect → correct → alarm."""
import pytest
import sys
import os
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestFullPipeline:
    """Test the complete detection → correction → alarm flow."""

    def test_high_wind_pipeline(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        from services.prediction_corrector import PredictionCorrector

        # Simulate ECMWF input with high wind
        ecmwf_rows = [
            {"ws100_avg": 28.0, "ws10_avg": 12.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},
            {"ws100_avg": 26.0, "ws10_avg": 11.0, "temp_2t_avg": 14.0, "tcwv_avg": 4.0},
            {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},
        ]
        predictions = np.array([200.0, 180.0, 100.0])

        detector = ExtremeWeatherDetector()
        corrector = PredictionCorrector()

        conditions = [detector.detect(r) for r in ecmwf_rows]
        active = detector.get_active_conditions(conditions)
        corrected, records = corrector.correct(predictions, conditions, 500.0)

        assert len(active) == 2  # rows 0 and 1 are high wind
        assert corrected[0] == 0.0
        assert corrected[1] == 0.0
        assert corrected[2] == 100.0  # normal, unchanged
        assert len(records) == 2

    def test_cold_wave_with_decay_pipeline(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        from services.prediction_corrector import PredictionCorrector

        ecmwf_rows = [
            {"ws100_avg": 8.0, "ws10_avg": 4.0, "temp_2t_avg": -10.0, "tcwv_avg": 5.0, "temp_24h_drop": 12.0},
        ]
        predictions = np.array([300.0])

        detector = ExtremeWeatherDetector()
        corrector = PredictionCorrector()

        conditions = [detector.detect(r) for r in ecmwf_rows]
        corrected, records = corrector.correct(predictions, conditions, 500.0)

        # decay = max(0.3, 0.7 - (10 - 5) * 0.05) = max(0.3, 0.45) = 0.45
        assert abs(corrected[0] - 135.0) < 0.01
        assert len(records) == 1
        assert records[0]["type"] == "cold_wave"

    def test_mixed_conditions_pipeline(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        from services.prediction_corrector import PredictionCorrector

        ecmwf_rows = [
            {"ws100_avg": 35.0, "ws10_avg": 15.0, "temp_2t_avg": 20.0, "tcwv_avg": 5.0},   # typhoon
            {"ws100_avg": 2.0, "ws10_avg": 1.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},     # calm
            {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": -2.0, "tcwv_avg": 18.0},    # icing
            {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},     # normal
        ]
        predictions = np.array([400.0, 50.0, 250.0, 100.0])

        detector = ExtremeWeatherDetector()
        corrector = PredictionCorrector()

        conditions = [detector.detect(r) for r in ecmwf_rows]
        corrected, records = corrector.correct(predictions, conditions, 500.0)

        assert corrected[0] == 0.0     # typhoon → clamp
        assert corrected[1] == 0.0     # calm → clamp
        assert corrected[2] < 250.0    # icing → decay
        assert corrected[2] > 0.0
        assert corrected[3] == 100.0   # normal → unchanged
        assert len(records) == 3

    def test_alarm_injection(self):
        """Verify alarm creation for warning/danger conditions."""
        from services.extreme_weather_detector import ExtremeWeatherDetector

        detector = ExtremeWeatherDetector()
        ecmwf_rows = [
            {"ws100_avg": 35.0, "ws10_avg": 15.0, "temp_2t_avg": 20.0, "tcwv_avg": 5.0},
        ]
        conditions = [detector.detect(r) for r in ecmwf_rows]
        active = detector.get_active_conditions(conditions)

        assert len(active) == 1
        assert active[0].severity == "danger"
        assert active[0].condition_type == "typhoon"

    def test_no_false_positives(self):
        from services.extreme_weather_detector import ExtremeWeatherDetector
        from services.prediction_corrector import PredictionCorrector

        ecmwf_rows = [
            {"ws100_avg": 10.0, "ws10_avg": 5.0, "temp_2t_avg": 15.0, "tcwv_avg": 5.0},
        ] * 10
        predictions = np.array([100.0] * 10)

        detector = ExtremeWeatherDetector()
        corrector = PredictionCorrector()

        conditions = [detector.detect(r) for r in ecmwf_rows]
        active = detector.get_active_conditions(conditions)
        corrected, records = corrector.correct(predictions, conditions, 500.0)

        assert len(active) == 0
        assert len(records) == 0
        assert np.array_equal(corrected, predictions)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

- [ ] **Step 2: Run all tests**

Run: `cd D:\Wind-power-microserver\wind-power-forecast\backend-autopredict && python -m pytest tests/ -v`
Expected: ALL PASS (should be ~130+ total tests)

- [ ] **Step 3: Commit**

```bash
git add backend-autopredict/tests/test_extreme_weather_pipeline.py
git commit -m "test: add end-to-end extreme weather pipeline integration tests"
```

---

## Execution Order

```
Task 1 (Detector) → Task 2 (Corrector) → Task 3 (API) → Task 4 (Pipeline) → Task 5 (Frontend) → Task 6 (Integration tests)
```

Tasks 1 and 2 are independent and can be parallelized. Task 3 depends on Task 1. Task 4 depends on Tasks 1 and 2. Task 5 depends on Task 3. Task 6 depends on all prior tasks.

## Verification

After all tasks complete:
1. `python -m pytest tests/ -v` — all backend tests pass
2. `cd frontend && npm run build` — frontend builds successfully
3. `python -c "from routes.extreme_weather_router import extreme_weather_bp"` — blueprint importable
4. Manual: start Flask server, hit `/api/extreme-weather/status` — returns JSON
