# Ultra-Short-Term Forecasting System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ultra-short-term (超短期) 16-shift rolling prediction to the existing forecast system, matching the algorithm from `scripts/forecast_ultrashort.py`.

**Architecture:** Extend `forecast_service.py` with ultra-short-specific functions. 16 independent shift models, each predicting one target time point per 15-min cycle. Training uses `train_pre_short_xxx` (shared with short-term). Results write to `supershortl_power` (wp_pred2~wp_pred17). Celery triggers prediction at :14,:29,:44,:59, training monthly, calibration daily.

**Tech Stack:** Python, LightGBM, XGBoost, CatBoost, SQLAlchemy, Celery, PostgreSQL

**Key reference:** `scripts/forecast_ultrashort.py` — all algorithms must match this file exactly.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/farm_registry/farms_config.py` | Modify | Add `supershort_table` per farm |
| `backend/services/forecast_service.py` | Modify | Add ~8 ultra-short functions |
| `backend/services/ultrashort_model_manager.py` | Create | Save/load 16 shift models |
| `backend/celery_app/tasks.py` | Modify | Fix `run_supershort_predict` to call Python directly |
| `backend/celery_app/scheduler.py` | Modify | Add supershort calibration schedule |
| `backend/seed_prediction_tasks.py` | Modify | Add supershort seed records |
| `backend/run_test_train_ultrashort.py` | Create | Test training end-to-end |
| `backend/run_test_predict_ultrashort.py` | Create | Test prediction end-to-end |

---

### Task 1: Config changes — farms_config.py + seed_prediction_tasks.py

**Files:**
- Modify: `backend/farm_registry/farms_config.py`
- Modify: `backend/seed_prediction_tasks.py`

- [ ] **Step 1: Add `supershort_table` to each farm in farms_config.py**

```python
# In FARMS dict, add supershort_table to every farm entry.
# Value is the same as short_table (shared NWP data).
"dplz": {
    "farm_code": "dplz",
    "name": "doupoliangzi",
    "capacity_mw": 47.5,
    "short_table": "train_pre_short_dplz",
    "mid_table": "train_pre_middle_dplz",
    "supershort_table": "train_pre_short_dplz",
    "calibrate_enabled": True,
},
"sds": {
    "farm_code": "sds",
    "name": "shidongshan",
    "capacity_mw": 193.5,
    "short_table": "train_pre_short_sds",
    "mid_table": "train_pre_middle_sds",
    "supershort_table": "train_pre_short_sds",
    "calibrate_enabled": True,
},
"zyx": {
    "farm_code": "zyx",
    "name": "zhuyuanxi",
    "capacity_mw": 453.5,
    "short_table": "train_pre_short_zyx",
    "mid_table": "train_pre_middle_zyx",
    "supershort_table": "train_pre_short_zyx",
    "calibrate_enabled": False,
},
"cf": {
    "farm_code": "cf",
    "name": "cangfang",
    "capacity_mw": 48.0,
    "short_table": "train_pre_short_cf",
    "mid_table": "train_pre_middle_cf",
    "supershort_table": "train_pre_short_cf",
    "calibrate_enabled": True,
},
"bnj": {
    "farm_code": "bnj",
    "name": "bainijing",
    "capacity_mw": 32.0,
    "short_table": "train_pre_short_bnj",
    "mid_table": "train_pre_middle_bnj",
    "supershort_table": "train_pre_short_bnj",
    "calibrate_enabled": True,
},
```

- [ ] **Step 2: Add supershort to DEFAULT_SCHEDULES in scheduler.py**

In `celery_app/scheduler.py`, update the `DEFAULT_SCHEDULES` dict to add a calibration time for supershort:

```python
DEFAULT_SCHEDULES = {
    "short": {"train": "03:00", "predict": "08:50", "calibrate": "03:03"},
    "medium": {"train": "02:00", "predict": "08:50", "calibrate": "03:03"},
    "supershort": {"train": "04:30", "predict_cron": "14,29,44,59", "calibrate": "04:33"},
}
```

- [ ] **Step 3: Update seed_prediction_tasks.py to include supershort**

Add supershort entries to the TASKS list in `seed_prediction_tasks.py`:

```python
TASKS = [
    # ... existing short/medium entries ...
    # Supershort
    {"farm_code": "dplz", "task_type": "supershort", "train_schedule": "04:30"},
    {"farm_code": "sds",   "task_type": "supershort", "train_schedule": "04:30"},
    {"farm_code": "zyx",   "task_type": "supershort", "train_schedule": "04:30"},
    {"farm_code": "cf",    "task_type": "supershort", "train_schedule": "04:30"},
    {"farm_code": "bnj",   "task_type": "supershort", "train_schedule": "04:30"},
]
```

- [ ] **Step 4: Commit**

```bash
git add backend/farm_registry/farms_config.py backend/seed_prediction_tasks.py backend/celery_app/scheduler.py
git commit -m "feat: add supershort config to farms, seed data, and scheduler defaults"
```

---

### Task 2: Ultra-short model manager

**Files:**
- Create: `backend/services/ultrashort_model_manager.py`

The existing `ModelManager` stores one {lgb, xgb, cb} set per farm/type. For supershort we need 16 shift sub-directories.

- [ ] **Step 1: Create ultrashort_model_manager.py**

```python
"""Save and load 16 shift models for ultra-short-term forecasting.

Layout:
  {base_dir}/{farm_code}/supershort/
    shift_01/
      dart_model.pkl, xgb_model.pkl, cb_model.pkl
      feature_columns.json
    shift_02/
      ...
    shift_16/
      ...
    meta.json   -- {train_date, n_features, test_accuracy, grid_map, n_shifts}
"""
from __future__ import annotations

import json
import logging
import os
import pickle
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "forecast_models",
)

N_SHIFTS = 16


class UltrashortModelManager:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or DEFAULT_BASE_DIR

    def _base(self, farm_code: str) -> str:
        return os.path.join(self.base_dir, farm_code, "supershort")

    def save_shift(
        self,
        farm_code: str,
        shift: int,
        models: Dict[str, object],
        feature_columns: List[str],
    ) -> None:
        d = os.path.join(self._base(farm_code), f"shift_{shift:02d}")
        os.makedirs(d, exist_ok=True)
        model_files = {"dart": "dart_model.pkl", "xgb": "xgb_model.pkl", "cb": "cb_model.pkl"}
        for key, filename in model_files.items():
            if key in models:
                with open(os.path.join(d, filename), "wb") as f:
                    pickle.dump(models[key], f)
        with open(os.path.join(d, "feature_columns.json"), "w", encoding="utf-8") as f:
            json.dump(feature_columns, f, ensure_ascii=False, indent=2)
        logger.info("Saved shift %d models for %s/supershort", shift, farm_code)

    def load_shift(self, farm_code: str, shift: int) -> Optional[Dict]:
        d = os.path.join(self._base(farm_code), f"shift_{shift:02d}")
        if not os.path.isdir(d):
            return None
        result: Dict = {}
        model_files = {"dart": "dart_model.pkl", "xgb": "xgb_model.pkl", "cb": "cb_model.pkl"}
        for key, filename in model_files.items():
            path = os.path.join(d, filename)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    result[key] = pickle.load(f)
        fc_path = os.path.join(d, "feature_columns.json")
        if os.path.exists(fc_path):
            with open(fc_path, "r", encoding="utf-8") as f:
                result["feature_columns"] = json.load(f)
        if not any(k in result for k in ("dart", "xgb", "cb")):
            return None
        return result

    def save_meta(self, farm_code: str, meta: dict) -> None:
        d = self._base(farm_code)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, default=str)

    def load_meta(self, farm_code: str) -> Optional[dict]:
        p = os.path.join(self._base(farm_code), "meta.json")
        if not os.path.exists(p):
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_all_shifts(self, farm_code: str) -> Dict[int, Dict]:
        result = {}
        for s in range(1, N_SHIFTS + 1):
            loaded = self.load_shift(farm_code, s)
            if loaded is not None:
                result[s] = loaded
        return result
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/ultrashort_model_manager.py
git commit -m "feat: add UltrashortModelManager for 16-shift model storage"
```

---

### Task 3: Ultra-short feature engineering + training in forecast_service.py

**Files:**
- Modify: `backend/services/forecast_service.py`

Port the core algorithm functions from `scripts/forecast_ultrashort.py`. Add these functions BEFORE the existing `# Orchestration` section (around line 460).

- [ ] **Step 1: Add ultra-short constants and feature functions**

Add the following at the end of the imports/constants section (after `TARGET = "Total_Power"` and before the short/mid feature engineering):

```python
N_SHIFTS = 16
```

Then add these functions BEFORE the existing `build_features()` function (they are ultrashort-specific, separate from the short/mid `build_features`):

```python
# ---------------------------------------------------------------------------
# Ultra-short-term: grid identification, features, per-shift preparation
# (ported from scripts/forecast_ultrashort.py)
# ---------------------------------------------------------------------------

def identify_grid_columns(df: pd.DataFrame) -> dict:
    """Parse multi-grid-point NWP column names to (variable, grid_index) mapping."""
    var_points: Dict[str, list] = {}
    for col in df.columns:
        if col in [TIME_COL, TARGET]:
            continue
        for prefix in ["100u", "100v", "10u", "10v", "200u", "200v",
                        "2t", "2d", "sp", "msl", "ssrd", "tcc", "tcwv"]:
            if col.startswith(prefix + "_") or (col.startswith(prefix) and "_" in col):
                parts = col.split("_")
                if len(parts) >= 3:
                    var_part = parts[0]
                    lat_lon = "_".join(parts[1:])
                    var_points.setdefault(var_part, []).append((col, lat_lon))
                break

    grid_map: Dict[str, tuple] = {}
    for var, points in var_points.items():
        for i, (col, _) in enumerate(sorted(points, key=lambda x: x[1])):
            grid_map[col] = (var, i + 1)
    return grid_map


def build_features_ultrashort(
    df: pd.DataFrame, grid_map: dict, cap: float,
) -> pd.DataFrame:
    """Ultra-short-term feature engineering. Ported from forecast_ultrashort.py."""
    out = df.copy()
    out[TIME_COL] = pd.to_datetime(out[TIME_COL])

    # Wind speed from u/v per grid point
    wind_cols: Dict[tuple, str] = {}
    for height in ["100", "10", "200"]:
        u_cols = sorted(
            [(idx, c) for c, (v, idx) in grid_map.items() if v == f"{height}u"],
            key=lambda x: x[0],
        )
        v_cols = sorted(
            [(idx, c) for c, (v, idx) in grid_map.items() if v == f"{height}v"],
            key=lambda x: x[0],
        )
        for (ui, uc), (vi, vc) in zip(u_cols, v_cols):
            ws_name = f"ws{height}_{ui}"
            out[ws_name] = np.sqrt(
                out[uc].astype(float) ** 2 + out[vc].astype(float) ** 2
            )
            wind_cols[(height, ui)] = ws_name

    # Spatial diffs between adjacent grid points
    for height in ["100", "10", "200"]:
        for i in range(1, 16):
            c1 = wind_cols.get((height, i))
            c2 = wind_cols.get((height, i + 1))
            if c1 and c2:
                out[f"ws{height}_diff_{i}"] = out[c2].astype(float) - out[c1].astype(float)

    # Temporal diffs (shift 1, 2, 3)
    for height in ["100", "10", "200"]:
        for i in range(1, 16):
            ws_name = wind_cols.get((height, i))
            if ws_name:
                ws = out[ws_name].astype(float)
                for lag in [1, 2, 3]:
                    out[f"{ws_name}_diff_prev{lag}"] = ws - ws.shift(lag)

    # Time encoding
    hour = out[TIME_COL].dt.hour
    out["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    out["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    out["is_daytime"] = ((hour >= 6) & (hour <= 18)).astype(int)

    # Wind power domain features
    ws100_cols = [f"ws100_{i}" for i in range(1, 16) if f"ws100_{i}" in out.columns]
    ws10_cols = [f"ws10_{i}" for i in range(1, 16) if f"ws10_{i}" in out.columns]

    if ws100_cols:
        ws100_mean = out[ws100_cols].mean(axis=1).astype(float)
        out["ws100_mean_cubed"] = ws100_mean ** 3
        out["ws100_mean_sigmoid"] = 1.0 / (1.0 + np.exp(-0.5 * (ws100_mean - 5)))
        out["ws100_mean_pc"] = (
            np.clip((ws100_mean - 3) / (12 - 3), 0, 1)
            * np.clip((25 - ws100_mean) / (25 - 20), 0, 1)
        )

    if ws100_cols and ws10_cols:
        out["wind_shear"] = (
            np.log(
                out[ws100_cols].mean(axis=1).astype(float)
                / out[ws10_cols].mean(axis=1).astype(float).replace(0, np.nan)
            ) / np.log(10)
        )

    sp_cols = [c for c, (v, _) in grid_map.items() if v == "sp"]
    t2_cols = [c for c, (v, _) in grid_map.items() if v == "2t"]
    if sp_cols and t2_cols:
        out["air_density"] = (
            out[sp_cols].mean(axis=1).astype(float)
            / (287.05 * out[t2_cols].mean(axis=1).astype(float))
        )
        if ws100_cols:
            out["power_density"] = (
                0.5 * out["air_density"] * out[ws100_cols].mean(axis=1).astype(float) ** 3
            )

    # NWP forecast tendency
    if ws100_cols:
        ws100_mean = out[ws100_cols].mean(axis=1).astype(float)
        for horizon in [1, 2, 4, 8]:
            out[f"nwp_ws100_trend_{horizon}h"] = ws100_mean.shift(-horizon) - ws100_mean
        future_changes = pd.DataFrame(
            {h: ws100_mean.shift(-h) - ws100_mean for h in [1, 2, 3, 4]}
        )
        out["nwp_ws100_ramp_4h"] = future_changes.max(axis=1) - future_changes.min(axis=1)
        out["nwp_ws100_rising_1h"] = (out["nwp_ws100_trend_1h"] > 0).astype(int)
        out["nwp_ws100_rising_4h"] = (out["nwp_ws100_trend_4h"] > 0).astype(int)

    return out


def get_feature_cols_ultrashort(
    df: pd.DataFrame, train_feat: pd.DataFrame,
) -> List[str]:
    """Get feature column names for ultra-short-term model."""
    raw_nwp = [c for c in df.columns if c not in [TIME_COL, TARGET]]
    ws_derived: List[str] = []
    for height in ["100", "10", "200"]:
        for i in range(1, 16):
            ws_derived.append(f"ws{height}_{i}")
        for i in range(1, 15):
            ws_derived.append(f"ws{height}_diff_{i}")
        for i in range(1, 16):
            for lag in [1, 2, 3]:
                ws_derived.append(f"ws{height}_{i}_diff_prev{lag}")
    extra = [
        "hour_sin", "hour_cos", "is_daytime",
        "ws100_mean_cubed", "ws100_mean_sigmoid", "ws100_mean_pc",
        "wind_shear", "air_density", "power_density",
        "nwp_ws100_trend_1h", "nwp_ws100_trend_2h",
        "nwp_ws100_trend_4h", "nwp_ws100_trend_8h",
        "nwp_ws100_ramp_4h", "nwp_ws100_rising_1h", "nwp_ws100_rising_4h",
    ]
    return list(dict.fromkeys(
        [c for c in raw_nwp + ws_derived + extra if c in train_feat.columns]
    ))
```

- [ ] **Step 2: Add per-shift feature preparation and training function**

Add after `get_feature_cols_ultrashort`:

```python
def prepare_shift_features(
    df: pd.DataFrame, shift: int, feat_cols: List[str],
) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Build per-shift power history features and delta target.

    Returns (X, y_delta, baseline_power).
    """
    power = df[TARGET].astype(float)
    p_shifted = power.shift(shift)
    target = power - p_shifted

    skip = {TIME_COL, TARGET}
    avail = [c for c in feat_cols if c in df.columns and c not in skip]
    X = df[avail].copy()

    power_feat = f"power_actual_at_t_minus_{shift}"
    X[power_feat] = p_shifted.values

    for window in [4, 8, 16]:
        hist = power.shift(shift + 1).rolling(window, min_periods=1)
        X[f"phist_mean_{window}"] = hist.mean().values
        X[f"phist_std_{window}"] = hist.std().values
        X[f"phist_min_{window}"] = hist.min().values
        X[f"phist_max_{window}"] = hist.max().values
        X[f"phist_range_{window}"] = (hist.max() - hist.min()).values

    X["ptrend_1"] = (p_shifted - power.shift(shift + 1)).values
    X["ptrend_4"] = (p_shifted - power.shift(shift + 4)).values
    X["ptrend_8"] = (p_shifted - power.shift(shift + 8)).values
    X["ptrend_16"] = (p_shifted - power.shift(shift + 16)).values
    vel1 = p_shifted - power.shift(shift + 1)
    vel2 = power.shift(shift + 1) - power.shift(shift + 2)
    X["paccel"] = (vel1 - vel2).values

    X = X.fillna(0).replace([np.inf, -np.inf], 0)
    return X, target.values, p_shifted.values


def train_ultrashort_ensemble(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    cap: float,
) -> Tuple[Dict[int, Dict], dict]:
    """Train 16 shift sub-models. Returns (shift_models, meta).

    Each shift model: {dart, xgb, cb, feature_columns}.
    meta: {train_date, n_features, test_accuracy_per_shift, test_accuracy_averaged, grid_map}.
    """
    import lightgbm as lgb
    from xgboost import XGBRegressor
    from catboost import CatBoostRegressor

    full_df = pd.concat([train_df, val_df, test_df], ignore_index=True)
    grid_map = identify_grid_columns(full_df)

    train_feat = build_features_ultrashort(train_df, grid_map, cap)
    val_feat = build_features_ultrashort(val_df, grid_map, cap)
    test_feat = build_features_ultrashort(test_df, grid_map, cap)
    feat_cols = get_feature_cols_ultrashort(full_df, train_feat)

    shift_models: Dict[int, Dict] = {}
    shift_test_preds: Dict[int, np.ndarray] = {}

    for s in range(1, N_SHIFTS + 1):
        X_tr, y_tr, _ = prepare_shift_features(train_feat, s, feat_cols)
        X_va, y_va, _ = prepare_shift_features(val_feat, s, feat_cols)
        X_te, y_te, p_base_te = prepare_shift_features(test_feat, s, feat_cols)

        common = [c for c in X_tr.columns if c in X_va.columns and c in X_te.columns]
        X_tr, X_va, X_te = X_tr[common], X_va[common], X_te[common]

        train_mask = ~np.isnan(y_tr)
        val_mask = ~np.isnan(y_va)
        X_tr_c, y_tr_c = X_tr[train_mask], y_tr[train_mask]
        X_va_c, y_va_c = X_va[val_mask], y_va[val_mask]

        models: Dict[str, object] = {}

        m = lgb.LGBMRegressor(
            boosting_type="dart", objective="regression", num_leaves=63,
            learning_rate=0.1, n_estimators=200, min_child_samples=20,
            feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=5,
            verbose=-1, drop_rate=0.1, reg_alpha=0.1, reg_lambda=0.1,
        )
        m.fit(X_tr_c, y_tr_c)
        models["dart"] = m
        preds_dart = m.predict(X_te)

        m = XGBRegressor(
            n_estimators=500, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.7, reg_alpha=0.1, reg_lambda=1.0,
            random_state=42, early_stopping_rounds=50,
        )
        m.fit(X_tr_c, y_tr_c, eval_set=[(X_va_c, y_va_c)], verbose=False)
        models["xgb"] = m
        preds_xgb = m.predict(X_te)

        m = CatBoostRegressor(
            iterations=500, depth=6, learning_rate=0.05,
            random_seed=42, verbose=0, early_stopping_rounds=50,
            l2_leaf_reg=3.0, subsample=0.8,
        )
        m.fit(X_tr_c, y_tr_c, eval_set=(X_va_c, y_va_c), verbose=0)
        models["cb"] = m
        preds_cb = m.predict(X_te)

        delta_pred = np.mean([preds_dart, preds_xgb, preds_cb], axis=0)
        pred_power = np.clip(delta_pred + p_base_te, 0, cap)
        pred_power[:s] = np.nan

        shift_models[s] = {
            "dart": models["dart"],
            "xgb": models["xgb"],
            "cb": models["cb"],
            "feature_columns": common,
        }
        shift_test_preds[s] = pred_power

        valid = ~np.isnan(pred_power)
        if valid.any():
            acc = score(test_feat[TARGET].to_numpy(float)[valid], pred_power[valid], cap)
            logger.info("  shift %2d (%3dmin): Acc=%.2f%%", s, s * 15, acc["accuracy_percent"])

    # Averaged predictions for evaluation only
    y_test = test_feat[TARGET].to_numpy(float)
    avg = np.full(len(y_test), np.nan)
    for i in range(N_SHIFTS, len(y_test)):
        vals = [shift_test_preds[s][i] for s in range(1, N_SHIFTS + 1)]
        vals = [v for v in vals if not np.isnan(v)]
        if vals:
            avg[i] = np.mean(vals)
    valid_avg = ~np.isnan(avg)
    avg_metrics = score(y_test[valid_avg], avg[valid_avg], cap) if valid_avg.any() else {}

    meta = {
        "train_date": datetime.now().isoformat(),
        "n_features": len(feat_cols),
        "n_shifts": N_SHIFTS,
        "averaged_test_accuracy": avg_metrics,
    }
    return shift_models, meta
```

- [ ] **Step 3: Commit**

```bash
git add backend/services/forecast_service.py
git commit -m "feat: add ultrashort feature engineering and training functions to forecast_service"
```

---

### Task 4: Training orchestration + test script

**Files:**
- Modify: `backend/services/forecast_service.py` (add orchestration function)
- Create: `backend/run_test_train_ultrashort.py`

- [ ] **Step 1: Add `run_ultrashort_monthly_training` to forecast_service.py**

Add in the Orchestration section, after `run_monthly_training`:

```python
def run_ultrashort_monthly_training(
    farm_code: str,
    model_manager,  # not used, UltrashortModelManager handles storage
    session,
) -> Dict:
    """Load training data, train 16 shift models, save via UltrashortModelManager."""
    from services.ultrashort_model_manager import UltrashortModelManager

    farm = get_farm(farm_code)
    cap = farm["capacity_mw"]
    feature_table = farm["supershort_table"]

    logger.info("Ultra-short monthly training: %s from %s", farm_code, feature_table)

    df = load_training_data_from_db(session, feature_table, farm_code)
    if df.empty:
        return {"status": "error", "message": f"No data in {feature_table}"}

    df = df.dropna(subset=[TARGET]).reset_index(drop=True)
    if len(df) < 100:
        return {"status": "error", "message": f"Insufficient data ({len(df)} rows)"}

    train_df, val_df, test_df = split_train_calibrate(df)
    shift_models, meta = train_ultrashort_ensemble(train_df, val_df, test_df, cap)

    usmm = UltrashortModelManager()
    for s, sdata in shift_models.items():
        usmm.save_shift(farm_code, s, sdata, sdata["feature_columns"])
    usmm.save_meta(farm_code, meta)

    return {
        "status": "ok",
        "farm_code": farm_code,
        "forecast_type": "supershort",
        "n_rows": len(df),
        "n_shifts": len(shift_models),
        "meta": meta,
    }
```

- [ ] **Step 2: Create run_test_train_ultrashort.py**

```python
"""Run monthly ultra-short-term training for one farm.

Usage:  python run_test_train_ultrashort.py bnj
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
)

from db_session import db_session
from services.forecast_service import run_ultrashort_monthly_training
from services.model_manager import ModelManager

farm_code = sys.argv[1] if len(sys.argv) > 1 else 'bnj'

print(f"=== Training {farm_code} supershort ===")
mm = ModelManager()

with db_session() as session:
    result = run_ultrashort_monthly_training(farm_code, mm, session)

print(f"\nResult: {result}")
```

- [ ] **Step 3: Run training test**

Run: `cd backend && python run_test_train_ultrashort.py bnj`

Expected: `status: ok`, 16 shift models saved to `forecast_models/bnj/supershort/shift_01/` through `shift_16/`, meta.json with averaged accuracy.

- [ ] **Step 4: Commit**

```bash
git add backend/services/forecast_service.py backend/run_test_train_ultrashort.py
git commit -m "feat: add ultrashort training orchestration and test script"
```

---

### Task 5: Prediction function + test script

**Files:**
- Modify: `backend/services/forecast_service.py` (add prediction function)
- Create: `backend/run_test_predict_ultrashort.py`

- [ ] **Step 1: Add `run_ultrashort_prediction` to forecast_service.py**

Add in the Orchestration section, after `run_daily_prediction`:

```python
def run_ultrashort_prediction(
    farm_code: str,
    model_manager,  # unused, kept for interface consistency
    calibration_manager,
    session,
) -> Dict:
    """Predict 16 future points (T+15min to T+4h) for one 15-min cycle.

    Triggered at :14,:29,:44,:59. Anchor T = next 15-min boundary.
    Writes one row to supershortl_power with wp_pred2~wp_pred17.
    """
    from services.ultrashort_model_manager import UltrashortModelManager
    from db_models.power import SupershortlPower

    farm = get_farm(farm_code)
    cap = farm["capacity_mw"]
    feature_table = farm["supershort_table"]

    # Anchor time: next 15-min boundary
    now = datetime.now()
    minute = now.minute
    remainder = minute % 15
    if remainder == 0:
        T = now.replace(second=0, microsecond=0)
    else:
        target_min = (minute // 15 + 1) * 15
        add_hour = target_min >= 60
        T = now.replace(
            hour=now.hour + (1 if add_hour else 0),
            minute=target_min % 60,
            second=0,
            microsecond=0,
        )

    # Load recent actual power (5h to cover shift-16 baseline + rolling stats)
    cutoff = T - timedelta(hours=5)
    actual_df = load_recent_actual_power(session, farm_code, days=1)
    if not actual_df.empty:
        actual_df = actual_df[actual_df[TIME_COL] >= cutoff].reset_index(drop=True)

    # Load NWP: T-1h to T+12h (feature engineering needs temporal context)
    nwp_start = T - timedelta(hours=1)
    nwp_end = T + timedelta(hours=12)
    nwp_df = load_prediction_nwp_range(session, feature_table, farm_code, nwp_start, nwp_end)
    if nwp_df.empty:
        return {"status": "error", "message": f"No NWP data around {T.isoformat()}"}

    # Combine: actuals (for power history) then NWP (for future features)
    if TARGET in nwp_df.columns:
        nwp_df = nwp_df.drop(columns=[TARGET])
    nwp_df[TARGET] = np.nan

    if not actual_df.empty:
        # Ensure no column overlap issues
        common_cols = [c for c in actual_df.columns if c in nwp_df.columns]
        combined = pd.concat([actual_df, nwp_df], ignore_index=True, sort=False)
        combined = combined.sort_values(TIME_COL).drop_duplicates(
            subset=[TIME_COL], keep="last"
        ).reset_index(drop=True)
    else:
        combined = nwp_df.copy()

    # Load models
    usmm = UltrashortModelManager()
    all_shifts = usmm.load_all_shifts(farm_code)
    if not all_shifts:
        return {"status": "error", "message": f"No supershort models for {farm_code}"}
    meta = usmm.load_meta(farm_code) or {}

    # Build NWP features on the combined set
    grid_map = meta.get("grid_map", None)
    if grid_map is None:
        grid_map = identify_grid_columns(combined)

    featured = build_features_ultrashort(combined, grid_map, cap)

    # Predict each shift's target point
    predictions: Dict[int, float] = {}
    for s in range(1, N_SHIFTS + 1):
        if s not in all_shifts:
            continue

        target_time = T + timedelta(minutes=s * 15)
        mask = featured[TIME_COL] == target_time
        if not mask.any():
            continue
        row = featured[mask].iloc[0:1]

        shift_data = all_shifts[s]
        feat_cols = shift_data.get("feature_columns", [])

        # Build power history features for this single row
        X = pd.DataFrame(0, index=row.index, columns=feat_cols)
        for col in feat_cols:
            if col in row.index and col in featured.columns:
                X.loc[X.index[0], col] = row[col]

        # Add per-shift power features
        power_feat = f"power_actual_at_t_minus_{s}"
        if not actual_df.empty:
            baseline_time = T  # All shifts use P[T] as baseline
            baseline_rows = actual_df[actual_df[TIME_COL] == baseline_time]
            baseline_val = float(baseline_rows.iloc[0][TARGET]) if len(baseline_rows) > 0 else 0.0
        else:
            baseline_val = 0.0

        if power_feat in X.columns:
            X.loc[X.index[0], power_feat] = baseline_val

        # Rolling stats from actual power history
        if not actual_df.empty:
            power_series = actual_df[TARGET].astype(float)
            # Get values before the baseline
            baseline_idx = actual_df[actual_df[TIME_COL] <= T].index
            if len(baseline_idx) > 0:
                hist_start = max(0, baseline_idx[-1] - 16)
                hist = power_series.iloc[hist_start:baseline_idx[-1]]
                for window in [4, 8, 16]:
                    h = hist.tail(window)
                    X.loc[X.index[0], f"phist_mean_{window}"] = h.mean() if len(h) > 0 else 0
                    X.loc[X.index[0], f"phist_std_{window}"] = h.std() if len(h) > 0 else 0
                    X.loc[X.index[0], f"phist_min_{window}"] = h.min() if len(h) > 0 else 0
                    X.loc[X.index[0], f"phist_max_{window}"] = h.max() if len(h) > 0 else 0
                    X.loc[X.index[0], f"phist_range_{window}"] = (h.max() - h.min()) if len(h) > 0 else 0

            for trend_n in [1, 4, 8, 16]:
                t_idx = baseline_idx[-1] - trend_n if len(baseline_idx) > 0 else -1
                val = float(power_series.iloc[t_idx]) if 0 <= t_idx < len(power_series) else 0
                X.loc[X.index[0], f"ptrend_{trend_n}"] = baseline_val - val
            X.loc[X.index[0], "paccel"] = 0.0

        X = X.fillna(0).replace([np.inf, -np.inf], 0)

        # Ensemble prediction
        preds = []
        for key in ("dart", "xgb", "cb"):
            if key in shift_data:
                preds.append(shift_data[key].predict(X)[0])
        if preds:
            delta_pred = np.mean(preds)
            pred_power = np.clip(delta_pred + baseline_val, 0, cap)
            predictions[s] = float(pred_power)

    if not predictions:
        return {"status": "error", "message": "No valid predictions produced"}

    # Apply calibration
    if farm.get("calibrate_enabled", False):
        cal_params = calibration_manager.load(farm_code, "supershort")
        if cal_params:
            for s in predictions:
                predictions[s] = float(np.clip(
                    cal_params["alpha"] * predictions[s] + cal_params["beta"], 0, cap
                ))

    # Write to supershortl_power
    obj = SupershortlPower(timestamp=T, farm_code=farm_code)
    for s in range(1, N_SHIFTS + 1):
        col_name = f"wp_pred{s + 1}"
        setattr(obj, col_name, predictions.get(s, 0.0))
    session.merge(obj)
    session.flush()

    return {
        "status": "ok",
        "farm_code": farm_code,
        "forecast_type": "supershort",
        "anchor_time": T.isoformat(),
        "n_predictions": len(predictions),
    }
```

- [ ] **Step 2: Add `load_prediction_nwp_range` helper**

Add near the other DB I/O helpers:

```python
def load_prediction_nwp_range(
    session,
    feature_table: str,
    farm_code: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Load NWP rows for a time range (wider than single day)."""
    from sqlalchemy import text

    sql = text(f"""
        SELECT *
        FROM "{feature_table}"
        WHERE "Timestamp" >= :start_ts
          AND "Timestamp" < :end_ts
        ORDER BY "Timestamp"
    """)
    rows = session.execute(sql, {
        "start_ts": start,
        "end_ts": end,
    }).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(row._mapping) for row in rows])
```

- [ ] **Step 3: Create run_test_predict_ultrashort.py**

```python
"""Run one ultra-short-term prediction for one farm.

Usage:  python run_test_predict_ultrashort.py bnj
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
)

from db_session import db_session
from services.forecast_service import run_ultrashort_prediction
from services.model_manager import ModelManager
from services.calibration_manager import CalibrationManager

farm_code = sys.argv[1] if len(sys.argv) > 1 else 'bnj'

print(f"=== Predicting {farm_code} supershort ===")
mm = ModelManager()
cm = CalibrationManager()

with db_session() as session:
    result = run_ultrashort_prediction(farm_code, mm, cm, session)

print(f"\nResult: {result}")
```

- [ ] **Step 4: Run prediction test**

Run: `cd backend && python run_test_predict_ultrashort.py bnj`

Expected: `status: ok`, `n_predictions: 16`, one row written to `supershortl_power` with wp_pred2~wp_pred17.

Verify: `SELECT * FROM supershortl_power WHERE farm_code = 'bnj' ORDER BY timestamp DESC LIMIT 1;`

- [ ] **Step 5: Commit**

```bash
git add backend/services/forecast_service.py backend/run_test_predict_ultrashort.py
git commit -m "feat: add ultrashort prediction function and test script"
```

---

### Task 6: Calibration function

**Files:**
- Modify: `backend/services/forecast_service.py`

- [ ] **Step 1: Add `run_ultrashort_calibration` to forecast_service.py**

Add in the Orchestration section, after `run_daily_calibration`:

```python
def run_ultrashort_calibration(
    farm_code: str,
    calibration_manager,
    session,
) -> Dict:
    """Daily affine calibration for ultra-short-term.

    Reconstructs averaged predictions from supershortl_power by finding
    the 16 submission records for each target time, then fits affine.
    """
    from sqlalchemy import text

    farm = get_farm(farm_code)
    cap = farm["capacity_mw"]

    cutoff = datetime.now() - timedelta(days=14)

    # Get all supershortl_power rows in the calibration window
    sql = text("""
        SELECT timestamp, farm_code,
               wp_pred2, wp_pred3, wp_pred4, wp_pred5,
               wp_pred6, wp_pred7, wp_pred8, wp_pred9,
               wp_pred10, wp_pred11, wp_pred12, wp_pred13,
               wp_pred14, wp_pred15, wp_pred16, wp_pred17
        FROM supershortl_power
        WHERE farm_code = :farm_code AND timestamp >= :cutoff
        ORDER BY timestamp
    """)
    rows = session.execute(sql, {"farm_code": farm_code, "cutoff": cutoff}).fetchall()
    if not rows:
        return {"status": "skipped", "message": "No supershort predictions in window"}

    # For each target time t, find predictions from 16 submission cycles
    raw_preds: List[float] = []
    actuals: List[float] = []

    for row in rows:
        submit_time = row[0]  # timestamp of submission
        for s in range(1, N_SHIFTS + 1):
            target_time = submit_time + timedelta(minutes=s * 15)
            pred_val = row[s + 1]  # wp_pred{s+1} columns start at index 2
            if pred_val is None:
                continue

            # Check if actual power exists for this target time
            actual_sql = text(
                "SELECT wp_true FROM actual_power "
                "WHERE farm_code = :fc AND timestamp = :ts"
            )
            actual_row = session.execute(actual_sql, {
                "fc": farm_code, "ts": target_time,
            }).fetchone()
            if actual_row and actual_row[0] is not None:
                raw_preds.append(float(pred_val))
                actuals.append(float(actual_row[0]))

    if len(raw_preds) < 20:
        return {"status": "skipped", "message": f"Too few aligned points ({len(raw_preds)})"}

    y = np.array(actuals)
    p = np.array(raw_preds)
    alpha, beta = fit_affine(y, p, cap)

    calibration_manager.save(farm_code, "supershort", alpha, beta)

    return {
        "status": "ok",
        "farm_code": farm_code,
        "forecast_type": "supershort",
        "alpha": alpha,
        "beta": beta,
        "n_points": len(raw_preds),
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/forecast_service.py
git commit -m "feat: add ultrashort daily calibration function"
```

---

### Task 7: Celery integration

**Files:**
- Modify: `backend/celery_app/tasks.py`
- Modify: `backend/celery_app/scheduler.py`

- [ ] **Step 1: Update `run_supershort_predict` in tasks.py**

Replace the existing subprocess-based implementation with a direct Python call:

```python
@celery_app.task(bind=True, max_retries=1, soft_time_limit=300)
def run_supershort_predict(self, farm_code):
    _validate_farm_code(farm_code)
    task_id = _get_task_id(farm_code, "supershort")
    run_id = _create_run_record(task_id, "predict", self.request.id) if task_id else None
    try:
        _update_task_running(task_id, "predict")
        from services.forecast_service import run_ultrashort_prediction
        from services.model_manager import ModelManager
        from services.calibration_manager import CalibrationManager

        model_mgr = ModelManager()
        cal_mgr = CalibrationManager()
        with db_session() as session:
            result = run_ultrashort_prediction(farm_code, model_mgr, cal_mgr, session)

        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "supershort prediction failed"))
        _finish_run_and_update_task(run_id, task_id, "predict", "success")
        return {"status": "success", "farm_code": farm_code}
    except Exception as exc:
        _finish_run_and_update_task(run_id, task_id, "predict", "failed", str(exc))
        raise self.retry(exc=exc, countdown=15)
```

- [ ] **Step 2: Update `train_model` in tasks.py to handle supershort**

Modify the `train_model` function to dispatch to `run_ultrashort_monthly_training` when `task_type == "supershort"`:

```python
@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800)
def train_model(self, farm_code, task_type):
    _validate_farm_code(farm_code)
    task_id = _get_task_id(farm_code, task_type)
    run_id = _create_run_record(task_id, "train", self.request.id) if task_id else None
    try:
        _update_task_running(task_id, "train")

        if task_type == "supershort":
            from services.forecast_service import run_ultrashort_monthly_training
            from services.model_manager import ModelManager
            mgr = ModelManager()
            with db_session() as session:
                result = run_ultrashort_monthly_training(farm_code, mgr, session)
        else:
            from services.forecast_service import run_monthly_training
            from services.model_manager import ModelManager
            ftype = _map_task_type(task_type)
            mgr = ModelManager()
            with db_session() as session:
                result = run_monthly_training(farm_code, ftype, mgr, session)

        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "training failed"))
        _finish_run_and_update_task(run_id, task_id, "train", "success")
        return {"status": "success", "farm_code": farm_code, "task_type": task_type}
    except Exception as exc:
        _finish_run_and_update_task(run_id, task_id, "train", "failed", str(exc))
        raise self.retry(exc=exc, countdown=60)
```

- [ ] **Step 3: Update `run_calibration` in tasks.py to handle supershort**

```python
@celery_app.task(bind=True, max_retries=1, soft_time_limit=300)
def run_calibration(self, farm_code, task_type):
    _validate_farm_code(farm_code)
    task_id = _get_task_id(farm_code, task_type)
    run_id = _create_run_record(task_id, "calibrate", self.request.id) if task_id else None
    try:
        _update_task_running(task_id, "calibrate")
        from services.calibration_manager import CalibrationManager
        cal_mgr = CalibrationManager()

        if task_type == "supershort":
            from services.forecast_service import run_ultrashort_calibration
            with db_session() as session:
                result = run_ultrashort_calibration(farm_code, cal_mgr, session)
        else:
            from services.forecast_service import run_daily_calibration
            ftype = _map_task_type(task_type)
            with db_session() as session:
                result = run_daily_calibration(farm_code, ftype, cal_mgr, session)

        status = "success" if result.get("status") == "ok" else "skipped"
        _finish_run_and_update_task(run_id, task_id, "calibrate", status)
        return {"status": status, "farm_code": farm_code, "task_type": task_type, **result}
    except Exception as exc:
        _finish_run_and_update_task(run_id, task_id, "calibrate", "failed", str(exc))
        raise self.retry(exc=exc, countdown=30)
```

- [ ] **Step 4: Add supershort calibration to scheduler.py**

In `build_beat_schedule()`, within the `if tt == "supershort":` block, add a calibration entry after the train entry:

```python
if tt == "supershort":
    schedule[f"{fc}_supershort_predict"] = {
        "task": "celery_app.tasks.run_supershort_predict",
        "args": (fc,),
        "schedule": crontab(minute="14,29,44,59"),
    }
    h, m = _parse_hhmm(
        t.train_schedule,
        DEFAULT_SCHEDULES["supershort"]["train"],
    )
    schedule[f"{fc}_supershort_train"] = {
        "task": "celery_app.tasks.train_model",
        "args": (fc, "supershort"),
        "schedule": crontab(minute=m, hour=h),
    }
    ch, cm = _parse_hhmm(
        getattr(t, "calibrate_schedule", None),
        DEFAULT_SCHEDULES["supershort"].get("calibrate", "04:33"),
    )
    schedule[f"{fc}_supershort_calibrate"] = {
        "task": "celery_app.tasks.run_calibration",
        "args": (fc, "supershort"),
        "schedule": crontab(minute=cm, hour=ch),
    }
```

- [ ] **Step 5: Commit**

```bash
git add backend/celery_app/tasks.py backend/celery_app/scheduler.py
git commit -m "feat: integrate supershort into Celery tasks and scheduler"
```

---

### Task 8: Seed prediction_tasks + end-to-end verification

**Files:**
- Modify: `backend/seed_prediction_tasks.py` (already done in Task 1, just run it here)

- [ ] **Step 1: Run seed script to create supershort prediction_tasks**

Run: `cd backend && python seed_prediction_tasks.py`

Expected: 5 new supershort records created (one per farm).

- [ ] **Step 2: Run full training for bnj**

Run: `cd backend && python run_test_train_ultrashort.py bnj`

Expected: 16 shift models trained and saved, averaged accuracy reported.

- [ ] **Step 3: Run prediction for bnj**

Run: `cd backend && python run_test_predict_ultrashort.py bnj`

Expected: 16 predictions written to `supershortl_power`.

- [ ] **Step 4: Verify DB entry**

Run SQL:
```sql
SELECT timestamp, farm_code, wp_pred2, wp_pred3, wp_pred10, wp_pred17
FROM supershortl_power
WHERE farm_code = 'bnj'
ORDER BY timestamp DESC LIMIT 1;
```

Expected: One row with anchor timestamp, wp_pred2~wp_pred17 populated.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete ultra-short-term forecasting system with 16-shift ensemble"
```

---

## Self-Review

### Spec coverage
- Section 2 (Feature Engineering): Task 3 ✓
- Section 3 (Training): Task 3 + Task 4 ✓
- Section 4 (Prediction): Task 5 ✓
- Section 5 (Each point predicted 16 times): Handled by supershortl_power schema + calibration reconstruction ✓
- Section 6 (Calibration): Task 6 ✓
- Section 7 (Scheduling): Task 7 ✓

### Placeholder scan
- No TBD/TODO found
- All code blocks contain complete implementations
- No "similar to Task N" shortcuts

### Type consistency
- `shift_models` Dict[int, Dict] consistent across train/save/load
- `UltrashortModelManager` interface: save_shift/load_shift/load_all_shifts used consistently
- `predictions` Dict[int, float] → wp_pred{s+1} mapping consistent
- All orchestration functions return Dict with status key
