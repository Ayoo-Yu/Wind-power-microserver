"""Forecast engine: feature engineering, ensemble training, prediction, and DB I/O.

Ported from scripts/forecast_shortterm.py for production use inside the Flask
backend.  All pure-computation functions are free of Flask / SQLAlchemy imports
so they can be unit-tested without a running server.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from farm_registry.farms_config import get_farm

logger = logging.getLogger(__name__)

TIME_COL = "Timestamp"
TARGET = "Total_Power"

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

def split_train_calibrate(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological 85/15 split."""
    n = len(df)
    split = int(n * 0.85)
    return df.iloc[:split].reset_index(drop=True), df.iloc[split:].reset_index(drop=True)


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
    cal_df: pd.DataFrame,
    cap: float,
) -> Tuple[Dict[str, object], List[str], Dict]:
    """Train LightGBM-DART + XGBoost + CatBoost ensemble.

    Returns (models_dict, feature_columns, meta).
    """
    import lightgbm as lgb
    from xgboost import XGBRegressor
    from catboost import CatBoostRegressor

    train_featured = build_features(train_df, cap)
    cal_featured = build_features(cal_df, cap)

    X_tr, y_tr, feats = prepare_xy(train_featured)
    X_ca, y_ca, _ = prepare_xy(cal_featured)
    common = [c for c in feats if c in X_ca.columns]
    X_tr, X_ca = X_tr[common], X_ca[common]

    models: Dict[str, object] = {}
    cal_preds: List[np.ndarray] = []

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
    cal_preds.append(m_lgb.predict(X_ca))

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
    m_xgb.fit(X_tr, y_tr, sample_weight=weights, eval_set=[(X_ca, y_ca)], verbose=False)
    models["xgb"] = m_xgb
    cal_preds.append(m_xgb.predict(X_ca))

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
    m_cb.fit(X_tr, y_tr, eval_set=(X_ca, y_ca), verbose=0)
    models["cb"] = m_cb
    cal_preds.append(m_cb.predict(X_ca))

    # --- ensemble calibration metrics ---
    raw_ensemble = np.clip(np.mean(cal_preds, axis=0), 0, cap)
    cal_metrics = score(y_ca.to_numpy(float), raw_ensemble, cap)

    meta = {
        "train_date": datetime.now().isoformat(),
        "n_samples": int(len(X_tr)),
        "n_features": int(len(common)),
        "cal_accuracy": cal_metrics,
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
        WHERE f.farm_code = :farm_code
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
        WHERE farm_code = :farm_code
          AND "Timestamp" >= :start_ts
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
) -> int:
    """Write predictions to shortl_power or mid_power using ORM merge."""
    from db_models.power import ShortlPower, MidPower

    model_cls = ShortlPower if table_name == "shortl_power" else MidPower
    count = 0
    for i, (ts, pred) in enumerate(zip(timestamps, predictions)):
        obj = model_cls(
            timestamp=ts,
            farm_code=farm_code,
            wp_pred=float(pred),
            pre_at=pre_at,
            pre_num=i + 1,
        )
        session.merge(obj)
        count += 1
    session.flush()
    return count


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

    train_df, cal_df = split_train_calibrate(df)
    models, feature_columns, meta = train_ensemble(train_df, cal_df, cap)

    model_manager.save(farm_code, forecast_type, models, feature_columns, meta)

    return {
        "status": "ok",
        "farm_code": farm_code,
        "forecast_type": forecast_type,
        "n_rows": len(df),
        "meta": meta,
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
        SELECT p.timestamp, p.wp_pred, a.wp_true
        FROM "{pred_table}" p
        JOIN actual_power a
          ON a.farm_code = p.farm_code AND a.timestamp = p.timestamp
        WHERE p.farm_code = :farm_code
          AND p.timestamp >= :cutoff
          AND a.wp_true IS NOT NULL
          AND p.wp_pred IS NOT NULL
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

    # Calibrate if enabled
    if farm.get("calibrate_enabled", False):
        raw_preds = calibration_manager.apply(farm_code, forecast_type, raw_preds, cap)

    # Write to DB
    timestamps = predict_df[TIME_COL].tolist()
    pre_at = datetime.now()
    n_written = write_predictions_to_db(
        session, pred_table, farm_code, raw_preds, timestamps, pre_at
    )

    return {
        "status": "ok",
        "farm_code": farm_code,
        "forecast_type": forecast_type,
        "target_date": target_date.isoformat(),
        "n_predictions": n_written,
    }
