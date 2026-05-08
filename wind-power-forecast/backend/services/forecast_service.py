"""Forecast engine: feature engineering, ensemble training, prediction, and DB I/O.

Ported from scripts/forecast_shortterm.py for production use inside the Flask
backend.  All pure-computation functions are free of Flask / SQLAlchemy imports
so they can be unit-tested without a running server.
"""
from __future__ import annotations

import logging
import sys
import os
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
from sklearn.metrics import mean_absolute_error, r2_score

from farm_registry.farms_config import get_farm

# Allow importing src feature modules from the parent project directory
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logger = logging.getLogger(__name__)

TIME_COL = "Timestamp"
TARGET = "Total_Power"
N_SHIFTS = 16

# ---------------------------------------------------------------------------
# Feature engineering (ported from scripts/forecast_shortterm.py)
# ---------------------------------------------------------------------------

def build_features(df: pd.DataFrame, cap: float) -> pd.DataFrame:
    """Build temporal, lag, NWP-derived, and physics features.

    Power lag features are only added when the *Total_Power* column exists
    and contains non-null data (training mode).  In prediction mode the column
    may be absent or all-NaN, in which case lag features are skipped.
    """
    out = df.copy()
    out[TIME_COL] = pd.to_datetime(out[TIME_COL])

    # --- temporal ---
    hour = out[TIME_COL].dt.hour
    month = out[TIME_COL].dt.month
    doy = out[TIME_COL].dt.dayofyear
    out["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    out["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    out["month_sin"] = np.sin(2 * np.pi * month / 12)
    out["month_cos"] = np.cos(2 * np.pi * month / 12)
    out["sin_doy"] = np.sin(2 * np.pi * doy / 365)
    out["cos_doy"] = np.cos(2 * np.pi * doy / 365)
    out["is_daytime"] = ((hour >= 6) & (hour <= 18)).astype(int)

    # --- power lag features (conditional) ---
    if TARGET in out.columns and out[TARGET].notna().any():
        power = out[TARGET].astype(float)
        out["power_lag_1d"] = power.shift(96)
        out["power_lag_2d"] = power.shift(192)
        out["power_lag_3d"] = power.shift(288)
        out["power_lag_7d"] = power.shift(672)
        out["power_yesterday_mean"] = power.shift(96).rolling(96, min_periods=1).mean()
        out["power_yesterday_max"] = power.shift(96).rolling(96, min_periods=1).max()
        out["power_yesterday_min"] = power.shift(96).rolling(96, min_periods=1).min()
        out["power_yesterday_std"] = power.shift(96).rolling(96, min_periods=1).std()
        out["power_recent_6h"] = power.shift(24)
        out["power_recent_12h"] = power.shift(48)

    # --- rename NWP columns ---
    rename_map: Dict[str, str] = {}
    for c in out.columns:
        if c.startswith("100u"):
            rename_map[c] = c.replace("100u", "wind_u_100m")
        elif c.startswith("100v"):
            rename_map[c] = c.replace("100v", "wind_v_100m")
        elif c.startswith("10u") and not c.startswith("100"):
            rename_map[c] = c.replace("10u", "wind_u_10m")
        elif c.startswith("10v") and not c.startswith("100"):
            rename_map[c] = c.replace("10v", "wind_v_10m")
        elif c.startswith("200u"):
            rename_map[c] = c.replace("200u", "wind_u_200m")
        elif c.startswith("200v"):
            rename_map[c] = c.replace("200v", "wind_v_200m")
        elif c.startswith("2t_"):
            rename_map[c] = c.replace("2t", "temperature_2m")
        elif c.startswith("2d_"):
            rename_map[c] = c.replace("2d", "dewpoint_2m")
        elif c.startswith("sp_"):
            rename_map[c] = c.replace("sp", "surface_pressure")
        elif c.startswith("msl"):
            rename_map[c] = c.replace("msl", "mean_sea_level_pressure")
        elif c.startswith("ssrd"):
            rename_map[c] = c.replace("ssrd", "surface_solar_radiation_downwards")
        elif c.startswith("tcc"):
            rename_map[c] = c.replace("tcc", "total_cloud_cover")
        elif c.startswith("tcwv"):
            rename_map[c] = c.replace("tcwv", "total_column_water_vapour")
    out = out.rename(columns=rename_map)

    # --- wind speed / direction ---
    # Match by prefix so that suffixed columns (e.g. wind_u_100m_23.8_103.2)
    # are paired correctly.  For each u/v pair sharing the same suffix, derive
    # wind_speed and wind_dir columns with the same suffix.
    for height in ["100m", "10m", "200m"]:
        u_prefix, v_prefix = f"wind_u_{height}", f"wind_v_{height}"
        u_cols = sorted(c for c in out.columns if c == u_prefix or c.startswith(u_prefix + "_"))
        for u_col in u_cols:
            suffix = u_col[len(u_prefix):]
            v_col = v_prefix + suffix
            if v_col not in out.columns:
                continue
            speed_name = f"wind_speed_{height}{suffix}"
            dir_name = f"wind_dir_{height}{suffix}"
            out[speed_name] = np.sqrt(
                out[u_col].astype(float) ** 2 + out[v_col].astype(float) ** 2
            )
            out[dir_name] = (
                270 - np.degrees(np.arctan2(out[v_col].astype(float), out[u_col].astype(float)))
            ) % 360

    # Average wind speed across all grid points for shear / density features
    ws100_cols = [c for c in out.columns if c.startswith("wind_speed_100m")]
    ws10_cols = [c for c in out.columns if c.startswith("wind_speed_10m")]
    avg_ws100 = out[ws100_cols].mean(axis=1) if ws100_cols else None
    avg_ws10 = out[ws10_cols].mean(axis=1) if ws10_cols else None

    # --- wind shear (from averaged grid-point speeds) ---
    if avg_ws100 is not None and avg_ws10 is not None:
        ws10_safe = avg_ws10.replace(0, np.nan)
        out["wind_shear_index"] = np.log(avg_ws100 / ws10_safe) / np.log(10)

    # --- air density ---
    sp_cols = [c for c in out.columns if c.startswith("surface_pressure")]
    t2m_cols = [c for c in out.columns if c.startswith("temperature_2m")]
    if sp_cols and t2m_cols:
        avg_sp = out[sp_cols].mean(axis=1).astype(float)
        avg_t2m = out[t2m_cols].mean(axis=1).astype(float)
        out["air_density"] = avg_sp / (287.05 * avg_t2m)

    # --- cubed wind, sigmoid, power-curve proxy ---
    for ws_col in [c for c in out.columns if c.startswith("wind_speed_")]:
        ws = out[ws_col].astype(float)
        out[f"{ws_col}_cubed"] = ws ** 3
        out[f"{ws_col}_sigmoid"] = 1.0 / (1.0 + np.exp(-0.5 * (ws - 5)))
        out[f"{ws_col}_pc"] = (
            np.clip((ws - 3) / (12 - 3), 0, 1)
            * np.clip((25 - ws) / (25 - 20), 0, 1)
        )

    # --- power density (from averaged 100m speed) ---
    if avg_ws100 is not None and "air_density" in out.columns:
        out["power_density_100m"] = 0.5 * out["air_density"] * avg_ws100 ** 3

    # --- src feature modules (matching forecast_shortterm.py) ---
    try:
        from src.features import build_all_features
        from src.features_temporal import build_temporal_features
        from src.features_wind_power import build_wind_power_features
        from src.features_weather_risk import build_weather_risk_features

        out = build_all_features(out)
        out = build_wind_power_features(out, hub_height=100.0)
        out = build_weather_risk_features(out)
        out = out.rename(columns={TIME_COL: "valid_time"})
        out = build_temporal_features(out)
        out = out.rename(columns={"valid_time": TIME_COL})
    except ImportError:
        pass

    return out


# ---------------------------------------------------------------------------
# prepare_xy
# ---------------------------------------------------------------------------

def prepare_xy(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """Split a featured DataFrame into (X, y, feature_columns)."""
    skip = {TIME_COL, TARGET}
    feature_cols = [
        c
        for c in df.columns
        if c not in skip
        and df[c].dtype in [np.float64, np.float32, np.int64, np.int32, float, int]
    ]
    X = df[feature_cols].copy().fillna(0).replace([np.inf, -np.inf], 0)
    y = df[TARGET].copy()
    mask = y.notna()
    return X[mask].reset_index(drop=True), y[mask].reset_index(drop=True), feature_cols


# ---------------------------------------------------------------------------
# Train / calibration split
# ---------------------------------------------------------------------------

def split_train_calibrate(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Chronological 70/15/15 split → (train, val, test)."""
    n = len(df)
    s1 = int(n * 0.70)
    s2 = int(n * 0.85)
    return (
        df.iloc[:s1].reset_index(drop=True),
        df.iloc[s1:s2].reset_index(drop=True),
        df.iloc[s2:].reset_index(drop=True),
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def weighted_rmse(y: np.ndarray, p: np.ndarray, cap: float) -> float:
    """Southern-Grid weighted RMSE."""
    d = np.maximum(y, 0.2 * cap)
    return float(np.sqrt(np.mean(((y - p) / d) ** 2)))


def score(y: np.ndarray, p: np.ndarray, cap: float) -> Dict[str, float]:
    """Return a dict of accuracy metrics."""
    d = np.maximum(y, 0.2 * cap)
    accuracy_percent = float((1.0 - np.sqrt(np.mean(((y - p) / d) ** 2))) * 100)
    return {
        "accuracy_percent": accuracy_percent,
        "weighted_rmse": weighted_rmse(y, p, cap),
        "mae": float(mean_absolute_error(y, p)),
        "r2": float(r2_score(y, p)),
        "bias": float(np.mean(p - y)),
    }


# ---------------------------------------------------------------------------
# Affine calibration
# ---------------------------------------------------------------------------

def fit_affine(y: np.ndarray, p: np.ndarray, cap: float) -> Tuple[float, float]:
    """Grid-search affine calibration: best (alpha, beta) minimising weighted RMSE."""
    best = (float("inf"), 1.0, 0.0)
    for a in np.linspace(0.60, 1.20, 61):
        for b in np.linspace(-0.25 * cap, 0.20 * cap, 46):
            pred = np.clip(a * p + b, 0, cap)
            loss = weighted_rmse(y, pred, cap)
            if loss < best[0]:
                best = (loss, float(a), float(b))
    return best[1], best[2]


# ---------------------------------------------------------------------------
# Ensemble training
# ---------------------------------------------------------------------------

def train_ensemble(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    cap: float,
) -> Tuple[Dict[str, object], List[str], Dict]:
    """Train LightGBM-DART + XGBoost + CatBoost ensemble.

    Uses val for early stopping (XGBoost, CatBoost) and test for evaluation.
    Returns (models_dict, feature_columns, meta).
    """
    import lightgbm as lgb
    from xgboost import XGBRegressor
    from catboost import CatBoostRegressor

    train_featured = build_features(train_df, cap)
    val_featured = build_features(val_df, cap)
    test_featured = build_features(test_df, cap)

    X_tr, y_tr, feats = prepare_xy(train_featured)
    X_va, y_va, _ = prepare_xy(val_featured)
    X_te, y_te, _ = prepare_xy(test_featured)
    common = [c for c in feats if c in X_va.columns and c in X_te.columns]
    X_tr, X_va, X_te = X_tr[common], X_va[common], X_te[common]

    models: Dict[str, object] = {}
    preds_val: List[np.ndarray] = []
    preds_test: List[np.ndarray] = []

    # --- LightGBM-DART ---
    m_lgb = lgb.LGBMRegressor(
        boosting_type="dart",
        objective="regression",
        num_leaves=63,
        learning_rate=0.05,
        n_estimators=800,
        min_child_samples=30,
        feature_fraction=0.7,
        bagging_fraction=0.8,
        bagging_freq=5,
        verbose=-1,
        drop_rate=0.15,
        reg_alpha=0.1,
        reg_lambda=0.1,
    )
    m_lgb.fit(X_tr, y_tr)
    models["lgb"] = m_lgb
    preds_val.append(m_lgb.predict(X_va))
    preds_test.append(m_lgb.predict(X_te))

    # --- XGBoost ---
    weights = np.where(y_tr > 150, 4.0, np.where(y_tr > 50, 1.5, 1.0))
    m_xgb = XGBRegressor(
        n_estimators=2000,
        max_depth=6,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.7,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        early_stopping_rounds=100,
    )
    m_xgb.fit(X_tr, y_tr, sample_weight=weights, eval_set=[(X_va, y_va)], verbose=False)
    models["xgb"] = m_xgb
    preds_val.append(m_xgb.predict(X_va))
    preds_test.append(m_xgb.predict(X_te))

    # --- CatBoost ---
    m_cb = CatBoostRegressor(
        iterations=2000,
        depth=6,
        learning_rate=0.03,
        random_seed=42,
        verbose=0,
        early_stopping_rounds=100,
        l2_leaf_reg=3.0,
        subsample=0.8,
    )
    m_cb.fit(X_tr, y_tr, eval_set=(X_va, y_va), verbose=0)
    models["cb"] = m_cb
    preds_val.append(m_cb.predict(X_va))
    preds_test.append(m_cb.predict(X_te))

    # --- ensemble metrics on test set ---
    raw_ensemble = np.clip(np.mean(preds_test, axis=0), 0, cap)
    test_metrics = score(y_te.to_numpy(float), raw_ensemble, cap)

    # --- initial calibration from test set ---
    init_alpha, init_beta = fit_affine(y_te.to_numpy(float), raw_ensemble, cap)

    meta = {
        "train_date": datetime.now().isoformat(),
        "n_samples": int(len(X_tr)),
        "n_val_samples": int(len(X_va)),
        "n_test_samples": int(len(X_te)),
        "n_features": int(len(common)),
        "cal_accuracy": test_metrics,
        "init_calibration": {"alpha": init_alpha, "beta": init_beta},
    }

    return models, common, meta


# ---------------------------------------------------------------------------
# Ensemble prediction
# ---------------------------------------------------------------------------

def predict_with_ensemble(
    models: Dict[str, object],
    feature_columns: List[str],
    df: pd.DataFrame,
    cap: float,
) -> np.ndarray:
    """Return clipped ensemble predictions (mean of three models).

    Missing feature columns are filled with 0; extra columns are ignored.
    """
    preds: List[np.ndarray] = []

    # Build X with exact feature_columns order; fill missing with 0
    X = pd.DataFrame(0, index=df.index, columns=feature_columns)
    for col in feature_columns:
        if col in df.columns:
            X[col] = df[col].values
    X = X.fillna(0).replace([np.inf, -np.inf], 0)

    for key in ("lgb", "xgb", "cb"):
        if key in models:
            preds.append(models[key].predict(X))

    if not preds:
        return np.zeros(len(df))

    ensemble = np.clip(np.mean(preds, axis=0), 0, cap)
    return ensemble.astype(float)


# ---------------------------------------------------------------------------
# DB I/O helpers
# ---------------------------------------------------------------------------

def load_training_data_from_db(
    session,
    feature_table: str,
    farm_code: str,
) -> pd.DataFrame:
    """JOIN feature table with actual_power and return a DataFrame."""
    from sqlalchemy import text

    sql = text(f"""
        SELECT f.*, a.wp_true AS "Total_Power"
        FROM "{feature_table}" f
        LEFT JOIN actual_power a
            ON a.farm_code = :farm_code AND a.timestamp = f."Timestamp"
        ORDER BY f."Timestamp"
    """)
    rows = session.execute(sql, {"farm_code": farm_code}).fetchall()
    if not rows:
        return pd.DataFrame()
    cols = list(rows[0]._fields) if hasattr(rows[0], "_fields") else list(rows[0].keys())
    return pd.DataFrame([dict(row._mapping) for row in rows])


def load_prediction_nwp_from_db(
    session,
    feature_table: str,
    farm_code: str,
    target_date: datetime,
) -> pd.DataFrame:
    """Load NWP feature rows for a given target date."""
    from sqlalchemy import text

    next_day = target_date + timedelta(days=1)
    sql = text(f"""
        SELECT *
        FROM "{feature_table}"
        WHERE "Timestamp" >= :start_ts
          AND "Timestamp" < :end_ts
        ORDER BY "Timestamp"
    """)
    rows = session.execute(sql, {
        "farm_code": farm_code,
        "start_ts": target_date,
        "end_ts": next_day,
    }).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(row._mapping) for row in rows])


def load_recent_actual_power(
    session,
    farm_code: str,
    days: int = 7,
) -> pd.DataFrame:
    """Load recent actual power for lag feature construction."""
    from sqlalchemy import text

    cutoff = datetime.now() - timedelta(days=days)
    sql = text("""
        SELECT timestamp AS "Timestamp", wp_true AS "Total_Power"
        FROM actual_power
        WHERE farm_code = :farm_code
          AND timestamp >= :cutoff
        ORDER BY timestamp
    """)
    rows = session.execute(sql, {
        "farm_code": farm_code,
        "cutoff": cutoff,
    }).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(row._mapping) for row in rows])
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    return df


def write_predictions_to_db(
    session,
    table_name: str,
    farm_code: str,
    predictions: np.ndarray,
    timestamps: List[datetime],
    pre_at: datetime,
    raw_predictions: np.ndarray | None = None,
) -> int:
    """Upsert predictions: query by (farm_code, timestamp), update if exists, insert if not.

    predictions: calibrated values (written to wp_pred)
    raw_predictions: raw model output (written to wp_pred_raw, if provided)
    """
    from db_models.power import ShortlPower, MidPower

    model_cls = ShortlPower if table_name == "shortl_power" else MidPower

    # Batch query existing rows by (farm_code, timestamp range)
    ts_min, ts_max = min(timestamps), max(timestamps)
    existing_rows = session.query(model_cls).filter(
        model_cls.farm_code == farm_code,
        model_cls.timestamp >= ts_min,
        model_cls.timestamp <= ts_max,
    ).all()

    # Map timestamp -> existing row (keep latest id if duplicates exist)
    existing_map: Dict[datetime, object] = {}
    for r in existing_rows:
        if r.timestamp not in existing_map or r.id > existing_map[r.timestamp].id:
            existing_map[r.timestamp] = r

    # Remove duplicate rows (same timestamp, different pre_at)
    keep_ids = {r.id for r in existing_map.values()}
    dup_ids = [r.id for r in existing_rows if r.id not in keep_ids]
    if dup_ids:
        session.query(model_cls).filter(model_cls.id.in_(dup_ids)).delete(synchronize_session=False)

    count = 0
    for i, (ts, pred) in enumerate(zip(timestamps, predictions)):
        raw_val = float(raw_predictions[i]) if raw_predictions is not None else None

        if ts in existing_map:
            row = existing_map[ts]
            row.wp_pred = float(pred)
            row.pre_at = pre_at
            row.pre_num = i + 1
            row.wp_pred_raw = raw_val
        else:
            obj = model_cls(
                timestamp=ts,
                farm_code=farm_code,
                wp_pred=float(pred),
                pre_at=pre_at,
                pre_num=i + 1,
            )
            if raw_val is not None:
                obj.wp_pred_raw = raw_val
            session.add(obj)
        count += 1
    session.flush()
    return count
    return count


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
    df: pd.DataFrame, grid_map: dict,
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
    """Train 16 shift sub-models with joblib threading parallelism. Returns (shift_models, meta)."""
    full_df = pd.concat([train_df, val_df, test_df], ignore_index=True)
    grid_map = identify_grid_columns(full_df)

    train_feat = build_features_ultrashort(train_df, grid_map)
    val_feat = build_features_ultrashort(val_df, grid_map)
    test_feat = build_features_ultrashort(test_df, grid_map)
    feat_cols = get_feature_cols_ultrashort(full_df, train_feat)

    import lightgbm as lgb
    from xgboost import XGBRegressor
    from catboost import CatBoostRegressor
    from joblib import Parallel, delayed

    def _train_one_shift(s: int) -> Tuple[int, Dict, np.ndarray]:
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
            n_jobs=1,
        )
        m.fit(X_tr_c, y_tr_c)
        models["dart"] = m
        preds_dart = m.predict(X_te)

        m = XGBRegressor(
            n_estimators=500, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.7, reg_alpha=0.1, reg_lambda=1.0,
            random_state=42, early_stopping_rounds=50, n_jobs=1,
        )
        m.fit(X_tr_c, y_tr_c, eval_set=[(X_va_c, y_va_c)], verbose=False)
        models["xgb"] = m
        preds_xgb = m.predict(X_te)

        m = CatBoostRegressor(
            iterations=500, depth=6, learning_rate=0.05,
            random_seed=42, verbose=0, early_stopping_rounds=50,
            l2_leaf_reg=3.0, subsample=0.8, thread_count=1,
        )
        m.fit(X_tr_c, y_tr_c, eval_set=(X_va_c, y_va_c), verbose=0)
        models["cb"] = m
        preds_cb = m.predict(X_te)

        delta_pred = np.mean([preds_dart, preds_xgb, preds_cb], axis=0)
        pred_power = np.clip(delta_pred + p_base_te, 0, cap)
        pred_power[:s] = np.nan

        models["feature_columns"] = common
        return s, models, pred_power

    results = Parallel(n_jobs=4, backend="threading")(
        delayed(_train_one_shift)(s) for s in range(1, N_SHIFTS + 1)
    )

    shift_models: Dict[int, Dict] = {}
    shift_test_preds: Dict[int, np.ndarray] = {}
    for s, models, pred_power in results:
        shift_models[s] = models
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

    # --- per-shift initial calibration from test-set predictions ---
    y_test_full = test_feat[TARGET].to_numpy(float)
    init_shift_calibration: Dict[int, dict] = {}
    for s in range(1, N_SHIFTS + 1):
        pred_s = shift_test_preds[s]
        valid_s = ~np.isnan(pred_s) & ~np.isnan(y_test_full)
        if valid_s.any():
            a_s, b_s = fit_affine(y_test_full[valid_s], pred_s[valid_s], cap)
        else:
            a_s, b_s = 1.0, 0.0
        init_shift_calibration[s] = {"alpha": a_s, "beta": b_s}

    meta = {
        "train_date": datetime.now().isoformat(),
        "n_samples": int(len(train_feat)),
        "n_val_samples": int(len(val_feat)),
        "n_test_samples": int(len(test_feat)),
        "n_features": len(feat_cols),
        "n_shifts": N_SHIFTS,
        "cal_accuracy": avg_metrics,
        "averaged_test_accuracy": avg_metrics,
        "init_shift_calibration": init_shift_calibration,
    }
    return shift_models, meta


def load_prediction_nwp_range(
    session,
    feature_table: str,
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


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_monthly_training(
    farm_code: str,
    forecast_type: str,
    model_manager,
    session,
) -> Dict:
    """Load all training data, train ensemble, save via model_manager.

    Returns a result dict with status and metrics.
    """
    farm = get_farm(farm_code)
    cap = farm["capacity_mw"]
    feature_table = farm["short_table"] if forecast_type == "short" else farm["mid_table"]

    logger.info("Monthly training: %s/%s from %s", farm_code, forecast_type, feature_table)

    df = load_training_data_from_db(session, feature_table, farm_code)
    if df.empty:
        return {"status": "error", "message": f"No data in {feature_table}"}

    df = df.dropna(subset=[TARGET]).reset_index(drop=True)
    if len(df) < 100:
        return {"status": "error", "message": f"Insufficient data ({len(df)} rows)"}

    train_df, val_df, test_df = split_train_calibrate(df)
    models, feature_columns, meta = train_ensemble(train_df, val_df, test_df, cap)

    model_manager.save(farm_code, forecast_type, models, feature_columns, meta)

    # Save initial calibration from test set
    from services.calibration_manager import CalibrationManager
    init_cal = meta.get("init_calibration", {})
    if init_cal:
        cal_mgr = CalibrationManager()
        cal_mgr.save(farm_code, forecast_type, init_cal["alpha"], init_cal["beta"])

    return {
        "status": "ok",
        "farm_code": farm_code,
        "forecast_type": forecast_type,
        "n_rows": len(df),
        "meta": meta,
        "model_dir": model_manager._dir(farm_code, forecast_type),
    }


def run_ultrashort_monthly_training(
    farm_code: str,
    model_manager,
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

    # Save per-shift initial calibration from test set
    from services.calibration_manager import CalibrationManager
    init_shift_cal = meta.get("init_shift_calibration", {})
    if init_shift_cal:
        cal_mgr = CalibrationManager()
        cal_mgr.save_shifts(farm_code, init_shift_cal)

    return {
        "status": "ok",
        "farm_code": farm_code,
        "forecast_type": "supershort",
        "n_rows": len(df),
        "n_shifts": len(shift_models),
        "meta": meta,
        "model_dir": usmm._base(farm_code),
    }


def run_daily_calibration(
    farm_code: str,
    forecast_type: str,
    calibration_manager,
    session,
) -> Dict:
    """Load 14 days of predictions vs actuals, fit affine, save params."""
    from sqlalchemy import text

    farm = get_farm(farm_code)
    cap = farm["capacity_mw"]
    pred_table = "shortl_power" if forecast_type == "short" else "mid_power"

    cutoff = datetime.now() - timedelta(days=14)
    sql = text(f"""
        SELECT p.timestamp, p.wp_pred_raw, a.wp_true
        FROM "{pred_table}" p
        JOIN actual_power a
          ON a.farm_code = p.farm_code AND a.timestamp = p.timestamp
        WHERE p.farm_code = :farm_code
          AND p.timestamp >= :cutoff
          AND a.wp_true IS NOT NULL
          AND p.wp_pred_raw IS NOT NULL
        ORDER BY p.timestamp
    """)
    rows = session.execute(sql, {
        "farm_code": farm_code,
        "cutoff": cutoff,
    }).fetchall()

    if not rows:
        return {"status": "skipped", "message": "No calibration data"}

    y = np.array([float(r[2]) for r in rows])
    p = np.array([float(r[1]) for r in rows])
    alpha, beta = fit_affine(y, p, cap)

    calibration_manager.save(farm_code, forecast_type, alpha, beta)

    return {
        "status": "ok",
        "farm_code": farm_code,
        "forecast_type": forecast_type,
        "alpha": alpha,
        "beta": beta,
        "n_points": len(rows),
        "calib_dir": os.path.dirname(calibration_manager._path(farm_code, forecast_type)),
    }


def run_daily_prediction(
    farm_code: str,
    forecast_type: str,
    model_manager,
    calibration_manager,
    session,
) -> Dict:
    """Orchestrate a single day prediction: load NWP, predict, calibrate, write.

    Target day:
      short -> T+1 (tomorrow)
      mid   -> T+3 (3 days from now)
    """
    farm = get_farm(farm_code)
    cap = farm["capacity_mw"]
    feature_table = farm["short_table"] if forecast_type == "short" else farm["mid_table"]
    pred_table = "shortl_power" if forecast_type == "short" else "mid_power"

    if forecast_type == "short":
        target_date = (datetime.now() + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        target_date = (datetime.now() + timedelta(days=3)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    # Load NWP for target day
    nwp_df = load_prediction_nwp_from_db(session, feature_table, farm_code, target_date)
    if nwp_df.empty:
        return {"status": "error", "message": f"No NWP data for {target_date.date()}"}

    # Load recent actuals for lag features
    actual_df = load_recent_actual_power(session, farm_code, days=7)

    # Combine: actuals first (for lag history), then NWP rows
    if not actual_df.empty:
        # Ensure NWP columns don't have Total_Power already
        if TARGET in nwp_df.columns:
            nwp_df = nwp_df.drop(columns=[TARGET])
        nwp_df[TARGET] = np.nan
        combined = pd.concat([actual_df, nwp_df], ignore_index=True, sort=False)
        combined = combined.sort_values(TIME_COL).reset_index(drop=True)
    else:
        combined = nwp_df.copy()
        if TARGET not in combined.columns:
            combined[TARGET] = np.nan

    # Build features on the combined set
    featured = build_features(combined, cap)

    # Filter to only target-day rows for prediction
    target_next = target_date + timedelta(days=1)
    mask = (featured[TIME_COL] >= target_date) & (featured[TIME_COL] < target_next)
    predict_df = featured[mask].reset_index(drop=True)

    if predict_df.empty:
        return {"status": "error", "message": "No rows after feature engineering for target day"}

    # Load models
    saved = model_manager.load(farm_code, forecast_type)
    if saved is None:
        return {"status": "error", "message": f"No trained model for {farm_code}/{forecast_type}"}

    models = {k: saved[k] for k in ("lgb", "xgb", "cb") if k in saved}
    feature_columns = saved.get("feature_columns", [])

    raw_preds = predict_with_ensemble(models, feature_columns, predict_df, cap)
    calibrated_preds = raw_preds.copy()

    # Calibrate if enabled
    if farm.get("calibrate_enabled", False):
        calibrated_preds = calibration_manager.apply(farm_code, forecast_type, raw_preds, cap)

    # Write to DB: wp_pred = calibrated, wp_pred_raw = raw model output
    timestamps = predict_df[TIME_COL].tolist()
    pre_at = datetime.now()
    n_written = write_predictions_to_db(
        session, pred_table, farm_code, calibrated_preds, timestamps, pre_at,
        raw_predictions=raw_preds,
    )

    return {
        "status": "ok",
        "farm_code": farm_code,
        "forecast_type": forecast_type,
        "target_date": target_date.isoformat(),
        "n_predictions": n_written,
    }


def _predict_shift(
    shift: int,
    T: datetime,
    featured: pd.DataFrame,
    actual_df: pd.DataFrame,
    shift_data: Dict,
    cap: float,
) -> float | None:
    """Predict power for a single shift. Returns predicted power or None."""
    target_time = T + timedelta(minutes=shift * 15)
    mask = featured[TIME_COL] == target_time
    if not mask.any():
        return None
    row = featured[mask].iloc[0:1]

    feat_cols = shift_data.get("feature_columns", [])
    X = pd.DataFrame(0.0, index=row.index, columns=feat_cols)
    for col in feat_cols:
        if col in row.index and col in featured.columns:
            X.loc[X.index[0], col] = row[col]

    # Per-shift power baseline
    power_feat = f"power_actual_at_t_minus_{shift}"
    if not actual_df.empty:
        baseline_rows = actual_df[actual_df[TIME_COL] == T]
        baseline_val = float(baseline_rows.iloc[0][TARGET]) if len(baseline_rows) > 0 else 0.0
    else:
        baseline_val = 0.0

    if power_feat in X.columns:
        X.loc[X.index[0], power_feat] = baseline_val

    # Rolling stats from actual power history
    if not actual_df.empty:
        power_series = actual_df[TARGET].astype(float)
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
    if not preds:
        return None
    delta_pred = np.mean(preds)
    return float(np.clip(delta_pred + baseline_val, 0, cap))


def run_ultrashort_prediction(
    farm_code: str,
    model_manager,
    calibration_manager,
    session,
) -> Dict:
    """Predict 16 future points (T+15min to T+4h) for one 15-min cycle.

    Triggered at :14,:29,:44,:59. Anchor T = next 15-min boundary.
    Writes one row to supershortl_power with timestamp = first target time.
    In that table wp_pred2 is aligned to row timestamp, wp_pred17 is row timestamp + 225min.
    """
    from services.ultrashort_model_manager import UltrashortModelManager
    from db_models.power import SupershortlPower

    farm = get_farm(farm_code)
    cap = farm["capacity_mw"]
    feature_table = farm["supershort_table"]

    # Anchor time: next 15-min boundary
    now = datetime.now()
    remainder = now.minute % 15
    if remainder == 0:
        T = now.replace(second=0, microsecond=0)
    else:
        T = now.replace(second=0, microsecond=0) + timedelta(minutes=15 - remainder)

    # Load recent actual power (5h to cover shift-16 baseline + rolling stats)
    cutoff = T - timedelta(hours=5)
    actual_df = load_recent_actual_power(session, farm_code, days=1)
    if not actual_df.empty:
        actual_df = actual_df[actual_df[TIME_COL] >= cutoff].reset_index(drop=True)

    # Load NWP: T-1h to T+12h (feature engineering needs temporal context)
    nwp_start = T - timedelta(hours=1)
    nwp_end = T + timedelta(hours=12)
    nwp_df = load_prediction_nwp_range(session, feature_table, nwp_start, nwp_end)
    if nwp_df.empty:
        return {"status": "error", "message": f"No NWP data around {T.isoformat()}"}

    # Combine: actuals (for power history) then NWP (for future features)
    if TARGET in nwp_df.columns:
        nwp_df = nwp_df.drop(columns=[TARGET])
    nwp_df[TARGET] = np.nan

    if not actual_df.empty:
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

    featured = build_features_ultrashort(combined, grid_map)

    # Predict each shift's target point
    predictions: Dict[int, float] = {}
    for s in range(1, N_SHIFTS + 1):
        if s not in all_shifts:
            continue
        pred = _predict_shift(
            s, T, featured, actual_df, all_shifts[s], cap,
        )
        if pred is not None:
            predictions[s] = pred

    if not predictions:
        return {"status": "error", "message": "No valid predictions produced"}

    # Keep raw predictions before calibration
    raw_predictions = dict(predictions)

    # Apply per-shift calibration
    if farm.get("calibrate_enabled", False):
        for s in predictions:
            predictions[s] = calibration_manager.apply_shift(
                farm_code, s, predictions[s], cap,
            )

    prediction_start_time = T + timedelta(minutes=15)

    # Upsert supershortl_power: query by (farm_code, timestamp), update or insert.
    # The DB/API convention treats row timestamp as the time of wp_pred2.
    existing = session.query(SupershortlPower).filter_by(
        farm_code=farm_code, timestamp=prediction_start_time,
    ).first()
    if existing:
        obj = existing
    else:
        obj = SupershortlPower(timestamp=prediction_start_time, farm_code=farm_code)
        session.add(obj)
    for s in range(1, N_SHIFTS + 1):
        setattr(obj, f"wp_pred{s + 1}", predictions.get(s, 0.0))
        setattr(obj, f"wp_pred{s + 1}_raw", raw_predictions.get(s))
    session.flush()

    return {
        "status": "ok",
        "farm_code": farm_code,
        "forecast_type": "supershort",
        "anchor_time": T.isoformat(),
        "prediction_start_time": prediction_start_time.isoformat(),
        "n_predictions": len(predictions),
    }


def run_ultrashort_calibration(
    farm_code: str,
    calibration_manager,
    session,
) -> Dict:
    """Daily per-shift affine calibration for ultra-short-term.

    Each of the 16 shift models gets its own calibrator fitted independently.
    For each shift s: collect (raw_pred_s, actual) pairs from 14-day window,
    fit affine, save per-shift params.
    """
    from sqlalchemy import text

    farm = get_farm(farm_code)
    cap = farm["capacity_mw"]

    cutoff = datetime.now() - timedelta(days=14)

    # Column index mapping: row[1]=wp_pred2_raw, row[2]=wp_pred3_raw, ..., row[16]=wp_pred17_raw.
    # Row timestamp is the first predicted point, so shift 1 maps to timestamp + 0min.
    raw_cols = ", ".join(f"wp_pred{s + 1}_raw" for s in range(1, N_SHIFTS + 1))
    sql = text(f"""
        SELECT timestamp, {raw_cols}
        FROM supershortl_power
        WHERE farm_code = :farm_code AND timestamp >= :cutoff
        ORDER BY timestamp
    """)
    rows = session.execute(sql, {"farm_code": farm_code, "cutoff": cutoff}).fetchall()
    if not rows:
        return {"status": "skipped", "message": "No supershort predictions in window"}

    # Bulk-load actual_power for the entire calibration window
    all_targets_start = cutoff
    all_targets_end = max(
        row[0] + timedelta(minutes=N_SHIFTS * 15) for row in rows
    )
    actual_sql = text(
        "SELECT timestamp, wp_true FROM actual_power "
        "WHERE farm_code = :fc AND timestamp >= :start AND timestamp <= :end "
        "AND wp_true IS NOT NULL"
    )
    actual_rows = session.execute(actual_sql, {
        "fc": farm_code, "start": all_targets_start, "end": all_targets_end,
    }).fetchall()
    actual_map: Dict[datetime, float] = {r[0]: float(r[1]) for r in actual_rows}

    MIN_CALIBRATION_POINTS = 20
    shift_params: Dict[int, dict] = {}
    total_points = 0

    for s in range(1, N_SHIFTS + 1):
        col_idx = s  # row[1]=shift1, row[2]=shift2, ..., row[16]=shift16
        s_actuals: List[float] = []
        s_preds: List[float] = []

        for row in rows:
            submit_time = row[0]
            target_time = submit_time + timedelta(minutes=(s - 1) * 15)
            pred_val = row[col_idx]
            if pred_val is None:
                continue
            actual_val = actual_map.get(target_time)
            if actual_val is not None:
                s_preds.append(float(pred_val))
                s_actuals.append(actual_val)

        if len(s_preds) < MIN_CALIBRATION_POINTS:
            logger.info("  shift %d: skipped (%d points)", s, len(s_preds))
            continue

        y = np.array(s_actuals)
        p = np.array(s_preds)
        alpha, beta = fit_affine(y, p, cap)
        shift_params[s] = {"alpha": alpha, "beta": beta}
        total_points += len(s_preds)
        logger.info("  shift %2d (%3dmin): α=%.4f β=%+.2f (%d pts)", s, s * 15, alpha, beta, len(s_preds))

    if not shift_params:
        return {"status": "skipped", "message": "No shift had enough calibration points"}

    calibration_manager.save_shifts(farm_code, shift_params)

    return {
        "status": "ok",
        "farm_code": farm_code,
        "forecast_type": "supershort",
        "n_shifts_calibrated": len(shift_params),
        "n_total_points": total_points,
        "calib_dir": os.path.dirname(calibration_manager._shifts_path(farm_code)),
    }
