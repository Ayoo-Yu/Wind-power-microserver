# Ultra-Short-Term Forecasting System Design

**Date:** 2026-05-05
**Scope:** Add ultra-short-term (超短期) forecasting to the existing daily prediction system

---

## 1. Overview

Integrate ultra-short-term prediction into `forecast_service.py` (Approach A — extend existing module), matching the algorithm from `scripts/forecast_ultrashort.py`.

**Key difference from short/mid-term:** 16 shift models, each predicting one future point every 15 minutes, using latest SCADA data as baseline.

### Comparison with short/mid-term

| | Short/Mid-term | Ultra-short-term |
|--|---------------|-----------------|
| Models | 1 ensemble | 16 shift sub-models |
| Target variable | Absolute power | Delta = P[t] - P[t-s] |
| Key features | NWP + temporal encoding | NWP + **latest actual power** + lag/rolling/trend |
| Prediction frequency | 1x/day | Every 15 min (at :14,:29,:44,:59) |
| Prediction range | 96 points (T+1d) | 16 points (T+15min ~ T+4h) |
| Training data source | `train_pre_short_xxx` JOIN `actual_power` | Same (shared with short-term) |
| Result table | `shortl_power` / `mid_power` | `supershortl_power` (wp_pred2~wp_pred17) |

---

## 2. Architecture

### New functions in `forecast_service.py`

- `identify_grid_columns(df)` — Parse multi-grid-point NWP column names to `(variable, grid_index)` mapping
- `build_features_ultrashort(df, grid_map, cap)` — Ultra-short-term feature engineering
- `get_feature_cols_ultrashort(df, train_feat)` — Determine feature column list
- `prepare_shift_features(df, shift, cap)` — Build per-shift power history features + delta target
- `train_ultrashort_ensemble(train_df, val_df, test_df, cap)` — Train 16 shift models
- `run_ultrashort_monthly_training(farm_code, model_manager, session)` — Monthly training entry point
- `run_ultrashort_prediction(farm_code, model_manager, calibration_manager, session)` — Single 15-min prediction entry point
- `run_ultrashort_calibration(farm_code, calibration_manager, session)` — Daily calibration entry point

### Modified files

- **`forecast_service.py`** — Add all ultra-short functions above
- **`celery_app/tasks.py`** — Change `run_supershort_predict` from subprocess to direct Python call
- **`celery_app/scheduler.py`** — Add supershort calibration schedule
- **`farm_registry/farms_config.py`** — Add `supershort_table` field per farm
- **`seed_prediction_tasks.py`** — Add supershort records for 5 farms

---

## 3. Feature Engineering

Must match `forecast_ultrashort.py` exactly. Three stages:

### Stage 1: NWP grid-point features (`build_features` equivalent)

1. **Grid identification** — `identify_grid_columns(df)`: Parse column names like `100u_23.8_103.2` to `(variable, grid_index)`
2. **Wind speed/direction** — Per grid point u/v → `ws100_1`, `ws100_2`, ... `ws100_15`, `ws10_N`, `ws200_N`
3. **Spatial diffs** — `ws100_diff_1` = `ws100_2 - ws100_1` (adjacent grid points)
4. **Temporal diffs** — `ws100_1_diff_prev1` = `ws100_1[t] - ws100_1[t-1]` (shift 1,2,3)
5. **Time encoding** — `hour_sin`, `hour_cos`, `is_daytime`
6. **Wind power domain** — `ws100_mean_cubed`, `ws100_mean_sigmoid`, `ws100_mean_pc`
7. **Physics** — `wind_shear`, `air_density`, `power_density`
8. **NWP forecast tendency** — `nwp_ws100_trend_{1,2,4,8}h`, `nwp_ws100_ramp_4h`, `nwp_ws100_rising_{1,4}h`

### Stage 2: Power history features (`prepare` function, per-shift)

For each shift s (1~16):

- `power_actual_at_t_minus_s` — Shifted actual power (baseline)
- `phist_mean/std/min/max/range_{4,8,16}` — Rolling statistics before baseline
- `ptrend_{1,4,8,16}` — Power differences vs earlier values
- `paccel` — Power acceleration (velocity differential)

### Stage 3: Target variable

- `target = P[t] - P[t-s]` (power change delta)
- Final prediction: `P_pred = clip(delta_pred + P_baseline, 0, cap)`

---

## 4. 16-Shift Ensemble Training

### Training flow

**Input:** train_df (70%), val_df (15%), test_df (15%) from `train_pre_short_xxx` JOIN `actual_power`

1. `identify_grid_columns(df)` on full dataset
2. `build_features_ultrashort()` on train/val/test separately
3. `get_feature_cols_ultrashort()` to get static feature column list
4. For each shift s (1~16):
   - `prepare_shift_features(df, s, cap)` — build power history + delta target
   - Train LightGBM-DART (n_estimators=200, lr=0.1) + XGBoost (n_estimators=500, lr=0.05, early_stopping on val) + CatBoost (iterations=500, lr=0.05, early_stopping on val)
   - Ensemble: `delta_pred = mean(dart, xgb, cb)`, `P_pred = clip(delta_pred + baseline, 0, cap)`
   - Evaluate on val and test sets
5. `averaged_predictions` — For each test time point, average across all 16 shifts (for accuracy evaluation ONLY)
6. Save test accuracy to meta

### Model storage

```
forecast_models/{farm_code}/supershort/
  shift_01.pkl  — {lgb, xgb, cb, feat_cols}
  shift_02.pkl
  ...
  shift_16.pkl
  meta.json     — {train_date, n_features, test_accuracy, grid_map}
```

---

## 5. Prediction Flow

Triggered every 15 minutes at :14, :29, :44, :59 via Celery.

### SCADA timing

SCADA rounds data to 15-min boundaries. At 7:14, SCADA writes actual power with timestamp=7:15 to `actual_power`. So at prediction time (7:14), the latest actual power at T=7:15 is already available.

### Steps

1. **Anchor time T** = next 15-min boundary from current time (e.g., 7:15 when triggered at 7:14)
2. **Load actual power** from `actual_power`: recent ~5h up to T (for shift-16 baseline window + rolling stats)
3. **Load NWP** from `train_pre_short_xxx`: T-1h ~ T+12h (temporal diffs need 3 prior rows; NWP tendency needs 8h forward)
4. **Combine** actual power history + NWP data
5. **Build features** with `build_features_ultrashort()` on the combined set
6. **For each shift s (1~16)**:
   - Load shift-s model
   - Build per-shift features via `prepare_shift_features()`
   - For the target row at T+s*15min:
     - Baseline = actual_power[T] (same for all shifts since T+s*15min - s*15min = T)
     - Predict delta, compute `P_pred = clip(delta + baseline, 0, cap)`
   - Apply calibration if enabled: `clip(alpha * P_pred + beta, 0, cap)`
7. **Write to `supershortl_power`**:
   - `timestamp` = T (anchor time, e.g., 7:15)
   - `wp_pred{s+1}` = shift s's prediction for T+s*15min
   - Confidence intervals: NULL for now

### Column mapping

| shift | DB column | Target time |
|-------|----------|------------|
| 1 | wp_pred2 | T+15min |
| 2 | wp_pred3 | T+30min |
| ... | ... | ... |
| 16 | wp_pred17 | T+4h |

Formula: `wp_predS` = prediction for `T + (S-1)*15min`

---

## 6. Each Point Predicted 16 Times

Each target time point gets predicted by 16 different submission cycles:

| Submission T | Shift used | Target 8:00 as |
|-------------|-----------|---------------|
| 7:45 | shift 1 | T+15min |
| 7:30 | shift 2 | T+30min |
| 7:15 | shift 3 | T+45min |
| ... | ... | ... |
| 4:00 | shift 16 | T+4h |

The individual predictions are stored independently in `supershortl_power` (one row per submission). Averaging across 16 submissions is ONLY done for post-hoc accuracy evaluation, matching `forecast_ultrashort.py`'s `averaged_predictions` function.

---

## 7. Daily Calibration

### Flow

1. For each target time t in the past 14 days:
   - Find 16 submission rows in `supershortl_power`:
     - Submission at t-15min → read `wp_pred2`
     - Submission at t-30min → read `wp_pred3`
     - ...
     - Submission at t-4h → read `wp_pred17`
   - Average the 16 values as `raw_pred`
2. `raw_pred` vs `actual_power.wp_true` → `fit_affine(y, p, cap)`
3. Save `(alpha, beta)` via CalibrationManager

---

## 8. Scheduling

### Celery tasks

| Task | Schedule | Action |
|------|----------|--------|
| `run_supershort_predict` | `crontab(minute="14,29,44,59")` | Direct call to `forecast_service.run_ultrashort_prediction()` |
| `train_model(supershort)` | `crontab(minute=m, hour=h)` from prediction_tasks | Direct call to `forecast_service.run_ultrashort_monthly_training()` |
| `run_calibration(supershort)` | `crontab(minute=m, hour=h)` from prediction_tasks | Direct call to `forecast_service.run_ultrashort_calibration()` |

### Scheduler changes

- `scheduler.py`: Add supershort calibration schedule (similar to short/mid pattern)
- `tasks.py`: Change `run_supershort_predict` from subprocess to Python call; ensure `train_model` and `run_calibration` support `supershort` type

### farms_config.py changes

Add `supershort_table` to each farm, value same as `short_table`:

```python
"bnj": {
    ...
    "short_table": "train_pre_short_bnj",
    "supershort_table": "train_pre_short_bnj",  # shared with short-term
    ...
}
```

### seed_prediction_tasks.py

Add supershort records for 5 farms with default train_schedule=`04:30`.
