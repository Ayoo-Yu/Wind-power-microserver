# Daily Forecast Training & Prediction System Design

**Date**: 2026-05-04
**Scope**: Multi-farm short-term (T+1) and mid-term (T+3) daily automated prediction, model training, and calibration

---

## 1. Problem Statement

The system needs automated daily predictions for 5 wind farms across two timescales:

| Type | Target Day | Table | Deadline | Points |
|------|-----------|-------|----------|--------|
| Short-term | T+1 (next day) | shortl_power | 09:00 CST | 96 (15min) |
| Mid-term | T+3 (3 days out) | mid_power | 09:00 CST | 96 (15min) |

Key constraints:
- NWP data arrives daily between 08:40-08:55 via E-text pipeline
- Models must be trained monthly; calibrators updated daily
- Algorithm is identical for both timescales (from forecast_shortterm.py)
- Data sources differ: train_pre_short_{farm} vs train_pre_middle_{farm}

## 2. Architecture

**Approach**: Modular service within Flask process, scheduled by existing APScheduler.

```
backend/services/
  forecast_service.py      # Core training + prediction engine
  model_manager.py         # Model file I/O (3 models + feature list + meta)
  calibration_manager.py   # Calibrator parameter I/O + rolling update

backend/config/
  farms_config.py          # Farm configuration (code, capacity, NWP grid)

File system:
  models/
    {farm_code}/
      short/  mid/
        lgb_model.pkl, xgb_model.pkl, cb_model.pkl
        feature_columns.json
        meta.json
  calibration/
    {farm_code}/
      short/  mid/
        params.json  # {alpha, beta, window_days, last_updated}
```

## 3. Schedule

| Task | Cron (CST) | Condition |
|------|-----------|-----------|
| Monthly model training | 0 2 1 * * | 1st of each month |
| Daily calibration update | 3 3 * * * | Every day |
| Daily short-term predict | 50 8 * * * | Check NWP data ready |
| Daily mid-term predict | 50 8 * * * | Check NWP data ready |

Short-term and mid-term predictions run in parallel across all 5 farms (10 tasks total).

## 4. Data Flow: Model Training (Monthly)

1. Read full historical data from `train_pre_short_{farm_code}` (or `train_pre_middle_{farm_code}`)
2. LEFT JOIN `actual_power` ON `(farm_code, Timestamp)` to get `wp_true` as target
3. Rename `wp_true` to `Total_Power`
4. Sort by Timestamp, split 85% train / 15% calibrate (chronological)
5. `build_features()` - feature engineering (temporal, wind physics, lag/rolling, etc.)
6. Train ensemble: LightGBM-DART + XGBoost + CatBoost
7. Evaluate on calibrate set, record scores
8. Save: 3 model files + feature_columns.json + meta.json to filesystem

## 5. Data Flow: Daily Prediction (08:50 CST)

1. **Check NWP readiness**: Verify target-day NWP data exists in `train_pre_short_{farm_code}` / `train_pre_middle_{farm_code}`
   - Short-term target: tomorrow 00:00 - 23:45
   - Mid-term target: T+3 day 00:00 - 23:45
2. **Load data**:
   - Target day NWP data (96 rows, 300+ feature columns)
   - Past 7 days `actual_power` for lag/rolling feature engineering
3. **Build features**: Concatenate historical actual_power + target NWP, run `build_features()`
4. **Load models**: Read 3 saved models + feature_columns from filesystem
5. **Predict**: 3-model ensemble average, clip(0, cap)
6. **Calibrate**: Load params.json, apply affine: `pred = alpha * raw + beta`, clip(0, cap)
7. **Write results**: Insert into `shortl_power` / `mid_power` with pre_at=now, pre_num=sequence

## 6. Data Flow: Daily Calibration Update (03:03 CST)

1. Read last 14 days from DB:
   - Prediction values from `shortl_power` / `mid_power` (wp_pred)
   - Actual values from `actual_power` (wp_true)
   - JOIN on `(farm_code, timestamp)`
2. For each farm x type, run `fit_affine()` grid search for optimal (alpha, beta)
3. Save to `calibration/{farm_code}/{type}/params.json`

## 7. Farm Configuration

Config-driven (no hardcoded farms). Each farm entry contains:
- `farm_code`: DB identifier (e.g., "bnj", "cf", "sds", "dplz", "zyx")
- `capacity_mw`: Installed capacity
- `short_table`: `train_pre_short_{farm_code}`
- `mid_table`: `train_pre_middle_{farm_code}`
- `calibrate_enabled`: Whether affine calibration applies (Cap <= 200MW)

Initial farms:
| farm_code | Name | Capacity | Calibrate |
|-----------|------|----------|-----------|
| dplz | doupoliangzi | 47.5 MW | Yes |
| sds | shidongshan | 193.5 MW | Yes |
| zyx | zhuyuanxi | 453.5 MW | No |
| cf | cangfang | 48.0 MW | Yes |
| bnj | bainijing | 32.0 MW | Yes |

## 8. Error Handling

- **NWP not ready at 08:50**: Retry every 2 minutes until 08:58, then log error and skip
- **Model files missing**: Fall back to raw ensemble (no calibration), log warning
- **DB read failure**: Retry 3 times with exponential backoff, then alert via logging
- **Training failure**: Keep previous month's model, log error with full traceback

## 9. Integration Points

- **scheduler_service.py**: Add 4 new APScheduler jobs (train, calibrate, predict_short, predict_mid)
- **E-text pipeline**: No changes needed; prediction reads from tables that E-text already populates
- **Database**: Uses existing tables (train_pre_short_xxx, train_pre_middle_xxx, actual_power, shortl_power, mid_power)
- **File system**: New directories for models/ and calibration/ (created on first run)

## 10. Algorithm (from forecast_shortterm.py)

Ensemble of 3 gradient boosting models:
1. **LightGBM-DART**: dart boosting, 63 leaves, lr=0.05, 800 estimators
2. **XGBoost**: 2000 estimators, depth=6, lr=0.03, weighted samples
3. **CatBoost**: 2000 iterations, depth=6, lr=0.03

Feature engineering:
- Temporal: hour/month sin/cos, day-of-year sin/cos, is_daytime
- Lag: 1d/2d/3d/7d power lags, yesterday mean/max/min/std, recent 6h/12h
- Wind physics: wind speed/direction at 10m/100m/200m, shear index, air density, power density
- NWP-derived: cubed wind, sigmoid, power curve proxy

Calibration (for Cap <= 200MW):
- Dynamic rolling affine: `pred_cal = clip(alpha * raw_pred + beta, 0, cap)`
- Grid search over alpha [0.60, 1.20], beta [-0.25*cap, 0.20*cap]
- 14-day rolling window for parameter fitting
