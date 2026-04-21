# Sub-Project D: Extreme Weather Handling — Design Spec

**Date**: 2026-04-19
**Status**: Approved
**Depends on**: Sub-projects A (probability prediction), B (model fusion), C (power curve anomaly)

---

## Goal

Detect extreme weather conditions from ECMWF forecast data, inject alerts into the existing alarm system, and apply post-processing corrections to wind power predictions. This ensures predictions remain physically plausible during typhoons, cold waves, icing events, and calm wind periods.

## Architecture

**Approach B: Independent Detector + Post-Processor**. Two standalone classes (`ExtremeWeatherDetector` and `PredictionCorrector`) inserted into the prediction pipeline without modifying existing model training code. Alerts are injected into the existing `AlarmRecord` system.

---

## Component 1: ExtremeWeatherDetector

**File**: `backend-autopredict/services/extreme_weather_detector.py`

Input: ECMWF data row (dict or DataFrame row).
Output: `WeatherCondition` label + severity + correction hint.

### Data class

```python
@dataclass
class WeatherCondition:
    condition_type: str   # "high_wind", "typhoon", "cold_wave", "icing", "calm_wind", "normal"
    severity: str         # "info", "warning", "danger"
    details: dict         # {"wind_speed": 28.5, "threshold": 25.0, ...}
    correction_hint: str  # "clamp_zero", "apply_decay", "none"
```

### Detection rules

| Condition | ECMWF fields | Threshold | Label | Severity | Correction hint |
|-----------|-------------|-----------|-------|----------|----------------|
| High wind | ws100 (100m wind speed) | >= 25 m/s | `high_wind` | warning | `clamp_zero` |
| Typhoon | ws100 | >= 32 m/s | `typhoon` | danger | `clamp_zero` |
| Cold wave | 2t (2m temp), 24h delta | 2t <= -5C AND 24h drop > 8C | `cold_wave` | warning | `apply_decay` |
| Icing risk | 2t, tcwv (total column water vapor) | 2t in [-5, 2]C AND tcwv > 15 | `icing` | warning | `apply_decay` |
| Calm wind | ws100 | < 3 m/s | `calm_wind` | info | `clamp_zero` |
| Normal | — | none of the above | `normal` | info | `none` |

Priority order (first match wins): typhoon > high_wind > cold_wave > icing > calm_wind > normal.

### Interface

```python
class ExtremeWeatherDetector:
    def __init__(self, thresholds: dict | None = None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    def detect(self, ecmwf_row: dict) -> WeatherCondition: ...
    def detect_batch(self, ecmwf_df: pd.DataFrame) -> list[WeatherCondition]: ...
    def get_active_conditions(self, conditions: list[WeatherCondition]) -> list[WeatherCondition]: ...
```

Thresholds are configurable via environment variables or a `extreme_weather_thresholds` database table, with defaults as shown above.

### Threshold defaults

```python
DEFAULT_THRESHOLDS = {
    "high_wind_speed": 25.0,      # m/s (turbine cut-out)
    "typhoon_speed": 32.0,        # m/s
    "calm_wind_speed": 3.0,       # m/s (turbine cut-in)
    "cold_wave_temp": -5.0,       # Celsius
    "cold_wave_drop_24h": 8.0,    # Celsius drop in 24h
    "icing_temp_low": -5.0,       # Celsius
    "icing_temp_high": 2.0,       # Celsius
    "icing_tcwv": 15.0,           # kg/m^2
}
```

---

## Component 2: PredictionCorrector

**File**: `backend-autopredict/services/prediction_corrector.py`

Input: prediction array + weather condition list + capacity.
Output: corrected prediction array (new ndarray, input unchanged).

### Correction rules

| Condition | Action | Formula |
|-----------|--------|---------|
| `high_wind` / `typhoon` | Clamp to 0 | `pred = 0` |
| `calm_wind` | Clamp to 0 | `pred = 0` |
| `cold_wave` | Dynamic decay | `decay = max(0.3, 0.7 - (abs(t) - 5) * 0.05)` |
| `icing` | Dynamic decay | `decay = max(0.3, 0.6 - (tcwv - 10) * 0.02)` |
| `normal` | No correction | `pred = pred` |

After correction: clamp all values to `[0, capacity]`.

### Interface

```python
class PredictionCorrector:
    def __init__(self, config: dict | None = None):
        self.config = config or DEFAULT_CORRECTION_CONFIG

    def correct(
        self,
        predictions: np.ndarray,
        conditions: list[WeatherCondition],
        capacity: float,
    ) -> tuple[np.ndarray, list[dict]]: ...
        # Returns (corrected_predictions, correction_records)

    def get_correction_summary(self, correction_records: list[dict]) -> dict: ...
```

`correction_records` is a list of dicts: `{"index": int, "type": str, "before": float, "after": float, "reason": str}`.

Constraints:
- Immutable: returns new ndarray, never modifies input.
- Capacity-clamped: `0 <= pred <= capacity` after all corrections.
- Traceable: every correction is recorded.

---

## Component 3: Alert Integration

No new alarm infrastructure. Reuse existing `AlarmRecord` model and `AlarmCenter.vue`.

### Auto-injected alerts

When `detect_batch()` returns conditions with severity `warning` or `danger`, create alarm records:

```python
for cond in active_conditions:
    if cond.severity in ("warning", "danger"):
        create_alarm_record(
            source="extreme_weather",
            farm_code=farm_code,
            module="prediction",
            level=cond.severity,
            message=f"检测到极端天气 [{cond.condition_type}]：{cond.details}",
        )
```

### Default alarm rules (seeded on first run)

- "极端天气预警"：keyword `extreme_weather`, level `warning`, module `prediction`
- "台风告警"：keyword `typhoon`, level `danger`, module `prediction`

---

## Component 4: API Endpoints

**File**: `backend-autopredict/routes/extreme_weather_router.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/extreme-weather/status` | GET | Current weather condition for the active farm |
| `/api/extreme-weather/thresholds` | GET | View current detection thresholds |
| `/api/extreme-weather/thresholds` | PUT | Update detection thresholds |
| `/api/extreme-weather/history` | GET | Historical extreme weather events (paginated) |

### Status response format

```json
{
  "farm_code": "zyx01",
  "current_condition": {
    "type": "high_wind",
    "severity": "warning",
    "details": {"wind_speed": 28.5, "threshold": 25.0}
  },
  "active_alerts": 2,
  "last_checked": "2026-04-19T14:30:00"
}
```

---

## Component 5: Frontend Changes

### PowerCompare.vue — Weather overlay

- Fetch extreme weather status alongside prediction data
- When corrections exist, render ECharts `markArea` bands in red/orange over affected time periods
- Hover tooltip shows correction details (before/after values, reason)

### HomePage.vue — Status card

- New "极端天气" status card in the dashboard
- Shows current condition label and severity
- Card background color: green (normal), yellow (info), orange (warning), red (danger)
- Links to AlarmCenter for details

### ExtremeWeather.vue — Threshold management (new page, optional)

- Table view of all thresholds with inline editing
- Save calls PUT `/api/extreme-weather/thresholds`
- Route at `/extreme-weather` under "分析与报表" sidebar group

---

## Data Flow

```
ECMWF forecast data (from DB)
    │
    ▼
ExtremeWeatherDetector.detect_batch()
    │
    ├──► WeatherCondition list
    │       │
    │       ├──► (severity >= warning) ──► AlarmRecord.create()
    │       │
    │       └──► PredictionCorrector.correct(predictions, conditions, capacity)
    │                   │
    │                   ├──► corrected predictions (np.ndarray)
    │                   └──► correction_records (list[dict])
    │
    ▼
Output to prediction tables + API response includes corrections
```

---

## Testing

### Unit tests

- `test_extreme_weather_detector.py`: Each detection rule, threshold override, priority order, batch detection, edge cases (boundary values).
- `test_prediction_corrector.py`: Each correction rule, dynamic decay formulas, immutability, capacity clamping, empty/normal input.

### Integration tests

- `test_extreme_weather_api.py`: API endpoints with mocked detector/corrector.
- `test_extreme_weather_pipeline.py`: End-to-end detection → correction → alarm injection with mock ECMWF data.

---

## Files Summary

### New files

| File | Purpose | Est. lines |
|------|---------|-----------|
| `backend-autopredict/services/extreme_weather_detector.py` | Weather condition detection | ~150 |
| `backend-autopredict/services/prediction_corrector.py` | Prediction post-processing | ~100 |
| `backend-autopredict/routes/extreme_weather_router.py` | API endpoints | ~120 |
| `backend-autopredict/tests/test_extreme_weather_detector.py` | Detector unit tests | ~150 |
| `backend-autopredict/tests/test_prediction_corrector.py` | Corrector unit tests | ~120 |
| `backend-autopredict/tests/test_extreme_weather_api.py` | API integration tests | ~100 |

### Modified files

| File | Change |
|------|--------|
| `auto_scripts/scripts/auto_pre_train_base.py` | Call detector + corrector after prediction |
| `backend-autopredict/app.py` | Register extreme_weather_bp blueprint |
| `frontend/src/components/PowerCompare.vue` | Add weather overlay bands |
| `frontend/src/components/HomePage.vue` | Add weather status card |
| `frontend/src/router/index.js` | Add extreme-weather route (optional threshold page) |
| `frontend/src/components/AppLayout.vue` | Add sidebar entry (optional) |
| `frontend/src/api/` | New API client module for extreme weather |

---

## Out of Scope

- Machine learning-based extreme weather classification (no labeled dataset available)
- Specialized extreme weather model training (sample size too small)
- Real-time weather alert push notifications (future enhancement)
- External weather alert API integration (e.g., CMA typhoon tracks)
