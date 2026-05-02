"""Optimized ensemble models for short and ultra-short forecasting.

The implementation is adapted from the local benchmark scripts while keeping
the production pipeline contracts:
* model artifacts are saved under the existing model folders;
* prediction CSV columns stay compatible with the upload APIs;
* input data can use either raw ECMWF names or existing ws10/ws100/ws200 names.
"""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from datetime import date

import joblib
import numpy as np
import pandas as pd
import lightgbm as lgb
from xgboost import XGBRegressor

try:
    from catboost import CatBoostRegressor
except Exception:  # pragma: no cover - runtime dependency may be optional locally
    CatBoostRegressor = None

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)


TIME_COL = "Timestamp"
SHORT_BUNDLE_NAME = "optimized_shortterm_ensemble.joblib"
ULTRA_BUNDLE_NAME = "optimized_ultrashort_ensemble.joblib"
DEFAULT_CAPACITY = 453.5
ROLLING_CALIBRATION_DAYS = 14


def _target_col(df: pd.DataFrame) -> str:
    if "Total_Power" in df.columns:
        return "Total_Power"
    if "wp_true" in df.columns:
        return "wp_true"
    if "power" in df.columns:
        return "power"
    raise ValueError("training data must contain Total_Power, wp_true, or power")


def _capacity(capacity: float | None = None) -> float:
    return float(capacity or DEFAULT_CAPACITY)


def _safe_numeric_frame(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    out = df.reindex(columns=feature_cols, fill_value=0).copy()
    for col in out.columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.fillna(0).replace([np.inf, -np.inf], 0)


def identify_grid_columns(df: pd.DataFrame) -> dict[str, tuple[str, int]]:
    var_points: dict[str, list[tuple[str, str]]] = {}
    prefixes = [
        "100u", "100v", "10u", "10v", "200u", "200v",
        "2t", "2d", "sp", "msl", "ssrd", "tcc", "tcwv",
    ]
    for col in df.columns:
        if col in {TIME_COL, "Total_Power", "wp_true", "power"}:
            continue
        for prefix in prefixes:
            if col.startswith(prefix + "_") or (col.startswith(prefix) and "_" in col):
                parts = col.split("_")
                if len(parts) >= 3:
                    var_points.setdefault(parts[0], []).append((col, "_".join(parts[1:])))
                break

    grid_map: dict[str, tuple[str, int]] = {}
    for var, points in var_points.items():
        for idx, (col, _) in enumerate(sorted(points, key=lambda x: x[1]), start=1):
            grid_map[col] = (var, idx)
    return grid_map


def _ensure_wind_speed_features(out: pd.DataFrame, grid_map: dict[str, tuple[str, int]]) -> None:
    wind_cols: dict[tuple[str, int], str] = {}

    for height in ["100", "10", "200"]:
        existing = [f"ws{height}_{i}" for i in range(1, 16) if f"ws{height}_{i}" in out.columns]
        for col in existing:
            idx = int(col.rsplit("_", 1)[1])
            wind_cols[(height, idx)] = col

        u_cols = sorted(
            [(idx, col) for col, (var, idx) in grid_map.items() if var == f"{height}u"],
            key=lambda x: x[0],
        )
        v_cols = sorted(
            [(idx, col) for col, (var, idx) in grid_map.items() if var == f"{height}v"],
            key=lambda x: x[0],
        )
        for (u_idx, u_col), (v_idx, v_col) in zip(u_cols, v_cols):
            if u_idx != v_idx:
                continue
            ws_name = f"ws{height}_{u_idx}"
            out[ws_name] = np.sqrt(
                pd.to_numeric(out[u_col], errors="coerce") ** 2
                + pd.to_numeric(out[v_col], errors="coerce") ** 2
            )
            wind_cols[(height, u_idx)] = ws_name

    for height in ["100", "10", "200"]:
        for i in range(1, 15):
            c1 = wind_cols.get((height, i))
            c2 = wind_cols.get((height, i + 1))
            if c1 and c2:
                out[f"ws{height}_diff_{i}"] = pd.to_numeric(out[c2], errors="coerce") - pd.to_numeric(out[c1], errors="coerce")

        for i in range(1, 16):
            ws_name = wind_cols.get((height, i))
            if ws_name:
                ws = pd.to_numeric(out[ws_name], errors="coerce")
                for lag in [1, 2, 3]:
                    out[f"{ws_name}_diff_prev{lag}"] = ws - ws.shift(lag)


def _first_existing_col(df: pd.DataFrame, names: list[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def _ensure_single_point_weather_features(out: pd.DataFrame, grid_map: dict[str, tuple[str, int]]) -> None:
    alias_map = {
        "wind_u_100m": ["100u", "wind_u_100m"],
        "wind_v_100m": ["100v", "wind_v_100m"],
        "wind_u_10m": ["10u", "wind_u_10m"],
        "wind_v_10m": ["10v", "wind_v_10m"],
        "wind_u_200m": ["200u", "wind_u_200m"],
        "wind_v_200m": ["200v", "wind_v_200m"],
        "temperature_2m": ["2t", "temperature_2m"],
        "dewpoint_2m": ["2d", "dewpoint_2m"],
        "surface_pressure": ["sp", "surface_pressure"],
        "mean_sea_level_pressure": ["msl", "mean_sea_level_pressure"],
        "surface_solar_radiation_downwards": ["ssrd", "surface_solar_radiation_downwards"],
        "total_cloud_cover": ["tcc", "total_cloud_cover"],
        "total_column_water_vapour": ["tcwv", "total_column_water_vapour"],
    }
    for alias, candidates in alias_map.items():
        src = _first_existing_col(out, candidates)
        if src and alias not in out.columns:
            out[alias] = pd.to_numeric(out[src], errors="coerce")

    for height in ["100", "10", "200"]:
        u_col = _first_existing_col(out, [f"wind_u_{height}m", f"{height}u"])
        v_col = _first_existing_col(out, [f"wind_v_{height}m", f"{height}v"])
        if u_col is None or v_col is None:
            u_grid = [col for col, (var, _) in grid_map.items() if var == f"{height}u"]
            v_grid = [col for col, (var, _) in grid_map.items() if var == f"{height}v"]
            if u_grid and v_grid:
                u = out[u_grid].apply(pd.to_numeric, errors="coerce").mean(axis=1)
                v = out[v_grid].apply(pd.to_numeric, errors="coerce").mean(axis=1)
            else:
                continue
        else:
            u = pd.to_numeric(out[u_col], errors="coerce")
            v = pd.to_numeric(out[v_col], errors="coerce")
        out[f"wind_speed_{height}m"] = np.sqrt(u ** 2 + v ** 2)
        out[f"wind_dir_{height}m"] = (270 - np.degrees(np.arctan2(v, u))) % 360


def _add_optional_feature_modules(out: pd.DataFrame) -> pd.DataFrame:
    try:
        from src.features import build_all_features
        from src.features_temporal import build_temporal_features
        from src.features_wind_power import build_wind_power_features
        from src.features_weather_risk import build_weather_risk_features
    except ImportError:
        return out

    try:
        enriched = build_all_features(out)
        enriched = build_wind_power_features(enriched, hub_height=100.0)
        enriched = build_weather_risk_features(enriched)
        enriched = enriched.rename(columns={TIME_COL: "valid_time"})
        enriched = build_temporal_features(enriched)
        return enriched.rename(columns={"valid_time": TIME_COL})
    except Exception:
        return out


def build_wind_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if TIME_COL in out.columns:
        out[TIME_COL] = pd.to_datetime(out[TIME_COL], errors="coerce")
    else:
        out[TIME_COL] = pd.RangeIndex(len(out))

    grid_map = identify_grid_columns(out)
    _ensure_wind_speed_features(out, grid_map)
    _ensure_single_point_weather_features(out, grid_map)

    ts = pd.to_datetime(out[TIME_COL], errors="coerce")
    hour = ts.dt.hour.fillna(0)
    month = ts.dt.month.fillna(1)
    doy = ts.dt.dayofyear.fillna(1)
    out["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    out["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    out["month_sin"] = np.sin(2 * np.pi * month / 12)
    out["month_cos"] = np.cos(2 * np.pi * month / 12)
    out["sin_doy"] = np.sin(2 * np.pi * doy / 365)
    out["cos_doy"] = np.cos(2 * np.pi * doy / 365)
    out["is_daytime"] = ((hour >= 6) & (hour <= 18)).astype(int)

    target = None
    for candidate in ["Total_Power", "wp_true", "power"]:
        if candidate in out.columns:
            target = pd.to_numeric(out[candidate], errors="coerce")
            break
    if target is not None:
        out["power_lag_1d"] = target.shift(96)
        out["power_lag_2d"] = target.shift(192)
        out["power_lag_3d"] = target.shift(288)
        out["power_lag_7d"] = target.shift(672)
        out["power_yesterday_mean"] = target.shift(96).rolling(96, min_periods=1).mean()
        out["power_yesterday_max"] = target.shift(96).rolling(96, min_periods=1).max()
        out["power_yesterday_min"] = target.shift(96).rolling(96, min_periods=1).min()
        out["power_yesterday_std"] = target.shift(96).rolling(96, min_periods=1).std()
        out["power_recent_6h"] = target.shift(24)
        out["power_recent_12h"] = target.shift(48)

    ws100_cols = [f"ws100_{i}" for i in range(1, 16) if f"ws100_{i}" in out.columns]
    ws10_cols = [f"ws10_{i}" for i in range(1, 16) if f"ws10_{i}" in out.columns]
    if ws100_cols:
        ws100_mean = out[ws100_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1)
        out["ws100_mean_cubed"] = ws100_mean ** 3
        out["ws100_mean_sigmoid"] = 1.0 / (1.0 + np.exp(-0.5 * (ws100_mean - 5)))
        out["ws100_mean_pc"] = np.clip((ws100_mean - 3) / 9, 0, 1) * np.clip((25 - ws100_mean) / 5, 0, 1)
        for horizon in [1, 2, 4, 8]:
            out[f"nwp_ws100_trend_{horizon}h"] = ws100_mean.shift(-horizon) - ws100_mean
        future_changes = pd.DataFrame({
            horizon: ws100_mean.shift(-horizon) - ws100_mean
            for horizon in [1, 2, 3, 4]
        })
        out["nwp_ws100_ramp_4h"] = future_changes.max(axis=1) - future_changes.min(axis=1)
        out["nwp_ws100_rising_1h"] = (out["nwp_ws100_trend_1h"] > 0).astype(int)
        out["nwp_ws100_rising_4h"] = (out["nwp_ws100_trend_4h"] > 0).astype(int)

    if ws100_cols and ws10_cols:
        ws100_mean = out[ws100_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1)
        ws10_mean = out[ws10_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1).replace(0, np.nan)
        out["wind_shear"] = np.log(ws100_mean / ws10_mean) / np.log(10)

    sp_cols = [col for col, (var, _) in grid_map.items() if var == "sp"]
    t2_cols = [col for col, (var, _) in grid_map.items() if var == "2t"]
    if sp_cols and t2_cols:
        sp_mean = out[sp_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1)
        t2_mean = out[t2_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1)
        out["air_density"] = sp_mean / (287.05 * t2_mean)
        if ws100_cols:
            out["power_density"] = 0.5 * out["air_density"] * out[ws100_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1) ** 3

    if "air_density" not in out.columns and "surface_pressure" in out.columns and "temperature_2m" in out.columns:
        out["air_density"] = (
            pd.to_numeric(out["surface_pressure"], errors="coerce")
            / (287.05 * pd.to_numeric(out["temperature_2m"], errors="coerce"))
        )

    if "wind_speed_100m" in out.columns and "wind_speed_10m" in out.columns:
        ws10 = pd.to_numeric(out["wind_speed_10m"], errors="coerce").replace(0, np.nan)
        out["wind_shear_index"] = np.log(pd.to_numeric(out["wind_speed_100m"], errors="coerce") / ws10) / np.log(10)

    for ws_col in [col for col in out.columns if col.startswith("wind_speed_")]:
        ws = pd.to_numeric(out[ws_col], errors="coerce")
        out[f"{ws_col}_cubed"] = ws ** 3
        out[f"{ws_col}_sigmoid"] = 1.0 / (1.0 + np.exp(-0.5 * (ws - 5)))
        out[f"{ws_col}_pc"] = np.clip((ws - 3) / 9, 0, 1) * np.clip((25 - ws) / 5, 0, 1)

    if "wind_speed_100m" in out.columns and "air_density" in out.columns:
        out["power_density_100m"] = 0.5 * out["air_density"] * pd.to_numeric(out["wind_speed_100m"], errors="coerce") ** 3

    return _add_optional_feature_modules(out)


def _numeric_feature_cols(df: pd.DataFrame, target_col: str) -> list[str]:
    skip = {TIME_COL, target_col, "Total_Power", "wp_true", "power"}
    cols = []
    for col in df.columns:
        if col in skip:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            cols.append(col)
    return cols


def _add_ultrashort_shift_features(
    feat: pd.DataFrame,
    power: pd.Series,
    shift: int,
) -> tuple[pd.Series, str]:
    p_shifted = pd.to_numeric(power, errors="coerce").shift(shift)
    power_feature = f"power_actual_at_t_minus_{shift}"
    feat[power_feature] = p_shifted

    history_base = pd.to_numeric(power, errors="coerce").shift(shift + 1)
    for window in [4, 8, 16]:
        hist = history_base.rolling(window, min_periods=1)
        feat[f"phist_mean_{window}"] = hist.mean()
        feat[f"phist_std_{window}"] = hist.std()
        feat[f"phist_min_{window}"] = hist.min()
        feat[f"phist_max_{window}"] = hist.max()
        feat[f"phist_range_{window}"] = feat[f"phist_max_{window}"] - feat[f"phist_min_{window}"]

    feat["ptrend_1"] = p_shifted - pd.to_numeric(power, errors="coerce").shift(shift + 1)
    feat["ptrend_4"] = p_shifted - pd.to_numeric(power, errors="coerce").shift(shift + 4)
    feat["ptrend_8"] = p_shifted - pd.to_numeric(power, errors="coerce").shift(shift + 8)
    feat["ptrend_16"] = p_shifted - pd.to_numeric(power, errors="coerce").shift(shift + 16)
    velocity_1 = p_shifted - pd.to_numeric(power, errors="coerce").shift(shift + 1)
    velocity_2 = pd.to_numeric(power, errors="coerce").shift(shift + 1) - pd.to_numeric(power, errors="coerce").shift(shift + 2)
    feat["paccel"] = velocity_1 - velocity_2
    return p_shifted, power_feature


def _fit_models(X_tr, y_tr, X_va=None, y_va=None, *, weighted=False) -> dict[str, object]:
    models: dict[str, object] = {}

    dart = lgb.LGBMRegressor(
        boosting_type="dart",
        objective="regression",
        num_leaves=63,
        learning_rate=0.05 if weighted else 0.1,
        n_estimators=800 if weighted else 200,
        min_child_samples=30 if weighted else 20,
        feature_fraction=0.7,
        bagging_fraction=0.8,
        bagging_freq=5,
        verbose=-1,
        drop_rate=0.15 if weighted else 0.1,
        reg_alpha=0.1,
        reg_lambda=0.1,
    )
    dart.fit(X_tr, y_tr)
    models["dart"] = dart

    xgb_kwargs = dict(
        n_estimators=2000 if weighted else 500,
        max_depth=6,
        learning_rate=0.03 if weighted else 0.05,
        subsample=0.8,
        colsample_bytree=0.7,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
    )
    if X_va is not None and y_va is not None and len(X_va) > 0:
        xgb_kwargs["early_stopping_rounds"] = 100 if weighted else 50
    xgb_model = XGBRegressor(**xgb_kwargs)
    sample_weight = None
    if weighted:
        sample_weight = np.where(y_tr > 150, 4.0, np.where(y_tr > 50, 1.5, 1.0))
    if "early_stopping_rounds" in xgb_kwargs:
        xgb_model.fit(X_tr, y_tr, sample_weight=sample_weight, eval_set=[(X_va, y_va)], verbose=False)
    else:
        xgb_model.fit(X_tr, y_tr, sample_weight=sample_weight, verbose=False)
    models["xgb_w" if weighted else "xgb"] = xgb_model

    if CatBoostRegressor is not None:
        cb = CatBoostRegressor(
            iterations=2000 if weighted else 500,
            depth=6,
            learning_rate=0.03 if weighted else 0.05,
            random_seed=42,
            verbose=0,
            early_stopping_rounds=100 if weighted else 50,
            l2_leaf_reg=3.0,
            subsample=0.8,
        )
        if X_va is not None and y_va is not None and len(X_va) > 0:
            cb.fit(X_tr, y_tr, eval_set=(X_va, y_va), verbose=0)
        else:
            cb.fit(X_tr, y_tr, verbose=0)
        models["catboost"] = cb

    return models


def _predict_model_dict(models: dict[str, object], X: pd.DataFrame) -> np.ndarray:
    preds = [np.asarray(model.predict(X), dtype=float) for model in models.values()]
    return np.mean(preds, axis=0)


def _weighted_rmse(y_true: np.ndarray, y_pred: np.ndarray, cap: float) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    denom = np.maximum(y, 0.2 * cap)
    return float(np.sqrt(np.mean(((y - p) / denom) ** 2)))


def _fit_affine_calibration(y_true: np.ndarray, raw_pred: np.ndarray, cap: float) -> dict[str, float | bool | int]:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(raw_pred, dtype=float)
    valid = np.isfinite(y) & np.isfinite(p)
    y = y[valid]
    p = p[valid]
    if len(y) < 8:
        return {"enabled": False, "a": 1.0, "b": 0.0, "samples": int(len(y))}

    raw_loss = _weighted_rmse(y, np.clip(p, 0, cap), cap)
    best_loss, best_a, best_b = raw_loss, 1.0, 0.0
    for a in np.linspace(0.60, 1.20, 61):
        for b in np.linspace(-0.25 * cap, 0.20 * cap, 46):
            calibrated = np.clip(a * p + b, 0, cap)
            loss = _weighted_rmse(y, calibrated, cap)
            if loss < best_loss:
                best_loss = loss
                best_a = float(a)
                best_b = float(b)

    return {
        "enabled": bool(best_loss < raw_loss),
        "a": best_a,
        "b": best_b,
        "samples": int(len(y)),
        "raw_weighted_rmse": float(raw_loss),
        "calibrated_weighted_rmse": float(best_loss),
    }


def _apply_affine_calibration(pred: np.ndarray, calibration: dict | None, cap: float) -> np.ndarray:
    if not calibration or not calibration.get("enabled"):
        return np.clip(pred, 0, cap)
    a = float(calibration.get("a", 1.0))
    b = float(calibration.get("b", 0.0))
    return np.clip(a * pred + b, 0, cap)


def _today_key() -> str:
    return date.today().isoformat()


def _filter_recent_calibration_rows(df: pd.DataFrame, target_col: str, recent_days: int) -> pd.DataFrame:
    if TIME_COL not in df.columns or target_col not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    out[TIME_COL] = pd.to_datetime(out[TIME_COL], errors="coerce")
    out[target_col] = pd.to_numeric(out[target_col], errors="coerce")
    out = out.dropna(subset=[TIME_COL, target_col]).sort_values(TIME_COL).reset_index(drop=True)
    if out.empty:
        return out
    cutoff = out[TIME_COL].max() - pd.Timedelta(days=recent_days)
    return out[out[TIME_COL] >= cutoff].reset_index(drop=True)


def _infer_training_csv(models_dir: str, task: str) -> str | None:
    cur = os.path.abspath(models_dir)
    parts = cur.split(os.sep)
    if task == "ultrashort":
        while parts and parts[-1] != "supershort":
            parts.pop()
        if not parts:
            return None
        return os.path.join(os.sep.join(parts), "datasets", "training_data_supershort.csv")

    while parts and parts[-1] != "models":
        parts.pop()
    if not parts:
        return None
    model_root = os.sep.join(parts)
    variant_dir = os.path.dirname(model_root)
    datasets_dir = os.path.join(variant_dir, "datasets")
    folder_name = os.path.basename(os.path.abspath(models_dir))
    if task == "middle":
        return os.path.join(datasets_dir, "training_data_medium.csv")
    farm_code = None
    if "_" in folder_name:
        farm_code = folder_name.split("_", 1)[1]
    if farm_code:
        return os.path.join(datasets_dir, f"training_data_short_{farm_code}.csv")
    return os.path.join(datasets_dir, "training_data_short_DEFAULT_FARM.csv")


def _save_shortterm_bundle(bundle: dict, models_dir: str, bundle_path: str) -> None:
    best_dir = os.path.join(models_dir, "best_models")
    os.makedirs(best_dir, exist_ok=True)
    joblib.dump(bundle, bundle_path)
    joblib.dump(bundle, os.path.join(best_dir, SHORT_BUNDLE_NAME))
    joblib.dump(bundle, os.path.join(best_dir, "production_model.joblib"))
    joblib.dump(bundle, os.path.join(models_dir, "model.joblib"))


def refresh_shortterm_calibration(
    models_dir: str,
    calibration_data_file: str | None = None,
    recent_days: int = ROLLING_CALIBRATION_DAYS,
    force: bool = False,
) -> dict | None:
    bundle_path = os.path.join(models_dir, "best_models", SHORT_BUNDLE_NAME)
    if not os.path.exists(bundle_path):
        bundle_path = os.path.join(models_dir, "best_models", "production_model.joblib")
    if not os.path.exists(bundle_path):
        return None

    bundle = joblib.load(bundle_path)
    if not isinstance(bundle, dict) or bundle.get("kind") != "optimized_shortterm_ensemble":
        return None
    calibration = bundle.get("calibration") or {}
    today_key = _today_key()
    if not force and calibration.get("updated_for_date") == today_key:
        return calibration

    data_file = calibration_data_file or _infer_training_csv(models_dir, "middle" if "middle" in models_dir.lower() else "short")
    if not data_file or not os.path.exists(data_file):
        return calibration

    df = pd.read_csv(data_file, low_memory=False)
    target_col = bundle.get("target_col") if bundle.get("target_col") in df.columns else _target_col(df)
    recent = _filter_recent_calibration_rows(df, target_col, recent_days)
    if len(recent) < 8:
        return calibration

    feat = build_wind_features(recent)
    X = _safe_numeric_frame(feat, bundle["feature_cols"])
    cap = _capacity(bundle.get("capacity"))
    raw_pred = np.clip(_predict_model_dict(bundle["models"], X), 0, cap)
    y_true = pd.to_numeric(feat[target_col], errors="coerce").to_numpy(dtype=float)
    new_calibration = _fit_affine_calibration(y_true, raw_pred, cap)
    new_calibration.update({
        "mode": "rolling_14d",
        "recent_days": int(recent_days),
        "updated_for_date": today_key,
        "data_file": data_file,
        "data_start": str(recent[TIME_COL].min()),
        "data_end": str(recent[TIME_COL].max()),
    })
    bundle["calibration"] = new_calibration
    bundle["rolling_calibration"] = {"enabled": True, "recent_days": int(recent_days)}
    _save_shortterm_bundle(bundle, models_dir, bundle_path)
    return new_calibration


def refresh_ultrashort_calibration(
    model_dir: str,
    calibration_data_file: str | None = None,
    recent_days: int = ROLLING_CALIBRATION_DAYS,
    force: bool = False,
) -> dict | None:
    bundle_path = os.path.join(model_dir, ULTRA_BUNDLE_NAME)
    if not os.path.exists(bundle_path):
        bundle_path = os.path.join(model_dir, "model.joblib")
    if not os.path.exists(bundle_path):
        return None

    bundle = joblib.load(bundle_path)
    if not isinstance(bundle, dict) or bundle.get("kind") != "optimized_ultrashort_ensemble":
        return None
    calibration = bundle.get("calibration") or {}
    today_key = _today_key()
    if not force and calibration.get("updated_for_date") == today_key:
        return calibration

    data_file = calibration_data_file or _infer_training_csv(model_dir, "ultrashort")
    if not data_file or not os.path.exists(data_file):
        return calibration

    df = pd.read_csv(data_file, low_memory=False)
    target_col = bundle.get("target_col") if bundle.get("target_col") in df.columns else _target_col(df)
    recent = _filter_recent_calibration_rows(df, target_col, recent_days)
    if len(recent) < 8:
        return calibration

    feat = build_wind_features(recent)
    shift = int(bundle["shift"])
    power = pd.to_numeric(feat[target_col], errors="coerce")
    _, generated_power_feature = _add_ultrashort_shift_features(feat, power, shift)
    power_feature = bundle.get("power_feature", generated_power_feature)
    if generated_power_feature != power_feature:
        feat[power_feature] = feat[generated_power_feature]

    X = _safe_numeric_frame(feat, bundle["feature_cols"])
    cap = _capacity(bundle.get("capacity"))
    delta = _predict_model_dict(bundle["models"], X)
    base = pd.to_numeric(feat[power_feature], errors="coerce").to_numpy(dtype=float)
    raw_pred = np.clip(delta + base, 0, cap)
    y_true = power.to_numpy(dtype=float)
    valid = np.isfinite(y_true) & np.isfinite(raw_pred) & np.isfinite(base)
    if valid.sum() < 8:
        return calibration

    new_calibration = _fit_affine_calibration(y_true[valid], raw_pred[valid], cap)
    new_calibration.update({
        "mode": "rolling_14d",
        "recent_days": int(recent_days),
        "updated_for_date": today_key,
        "data_file": data_file,
        "data_start": str(recent[TIME_COL].min()),
        "data_end": str(recent[TIME_COL].max()),
    })
    bundle["calibration"] = new_calibration
    bundle["rolling_calibration"] = {"enabled": True, "recent_days": int(recent_days)}
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(bundle, os.path.join(model_dir, ULTRA_BUNDLE_NAME))
    joblib.dump(bundle, os.path.join(model_dir, "model.joblib"))
    return new_calibration


def fit_shortterm_ensemble(data: pd.DataFrame, model_folder: str, capacity: float | None = None) -> dict:
    cap = _capacity(capacity)
    target_col = _target_col(data)
    df = data.copy()
    df[TIME_COL] = pd.to_datetime(df[TIME_COL], errors="coerce")
    df = df.sort_values(TIME_COL).reset_index(drop=True)

    features = build_wind_features(df)
    n = len(features)
    if n < 20:
        raise ValueError("not enough rows to train short-term ensemble")

    feature_cols = _numeric_feature_cols(features, target_col)
    X_all = _safe_numeric_frame(features, feature_cols)
    y_all = pd.to_numeric(features[target_col], errors="coerce")
    valid = y_all.notna()
    X_all = X_all[valid].reset_index(drop=True)
    y_all = y_all[valid].reset_index(drop=True)
    if len(X_all) < 20:
        raise ValueError("not enough valid rows to train short-term ensemble")

    train_end = max(1, int(len(X_all) * 0.85))
    X_tr = X_all.iloc[:train_end]
    y_tr = y_all.iloc[:train_end]
    X_va = X_all.iloc[train_end:]
    y_va = y_all.iloc[train_end:]

    if X_va.empty:
        X_va = X_tr.tail(max(1, min(96, len(X_tr))))
        y_va = y_tr.tail(len(X_va))

    models = _fit_models(X_tr, y_tr, X_va, y_va, weighted=True)
    cal_raw_pred = np.clip(_predict_model_dict(models, X_va), 0, cap)
    calibration = _fit_affine_calibration(y_va.to_numpy(dtype=float), cal_raw_pred, cap)
    bundle = {
        "kind": "optimized_shortterm_ensemble",
        "models": models,
        "feature_cols": feature_cols,
        "target_col": target_col,
        "capacity": cap,
        "split": {"train_ratio": 0.85, "calibration_ratio": 0.15},
        "calibration": calibration,
    }

    best_dir = os.path.join(model_folder, "best_models")
    os.makedirs(best_dir, exist_ok=True)
    for name, model in models.items():
        joblib.dump(model, os.path.join(best_dir, f"{name}.joblib"))
    bundle_path = os.path.join(best_dir, SHORT_BUNDLE_NAME)
    joblib.dump(bundle, bundle_path)
    joblib.dump(bundle, os.path.join(best_dir, "production_model.joblib"))
    joblib.dump(bundle, os.path.join(model_folder, "model.joblib"))
    with open(os.path.join(model_folder, "best_model_type.txt"), "w", encoding="utf-8") as f:
        f.write("production_model")
    return {
        "bundle": bundle,
        "bundle_path": bundle_path,
        "score": 0.0,
        "training_samples": int(len(X_tr)),
    }


def predict_shortterm_ensemble(input_file: str, models_dir: str, output_file: str) -> tuple[np.ndarray, pd.Series] | None:
    bundle_path = os.path.join(models_dir, "best_models", SHORT_BUNDLE_NAME)
    if not os.path.exists(bundle_path):
        prod_path = os.path.join(models_dir, "best_models", "production_model.joblib")
        if not os.path.exists(prod_path):
            return None
        bundle_path = prod_path
    try:
        refresh_shortterm_calibration(models_dir)
    except Exception:
        pass
    bundle = joblib.load(bundle_path)
    if not isinstance(bundle, dict) or bundle.get("kind") != "optimized_shortterm_ensemble":
        return None

    df = pd.read_csv(input_file)
    df[TIME_COL] = pd.to_datetime(df[TIME_COL], errors="coerce")
    feat = build_wind_features(df)
    X = _safe_numeric_frame(feat, bundle["feature_cols"])
    cap = _capacity(bundle.get("capacity"))
    raw_pred = np.clip(_predict_model_dict(bundle["models"], X), 0, cap)
    pred = _apply_affine_calibration(raw_pred, bundle.get("calibration"), cap)
    timestamps = feat[TIME_COL]

    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    pd.DataFrame({
        "Timestamp": timestamps,
        "Predicted_Power": pred,
    }).to_csv(output_file, index=False)
    return pred, timestamps


def fit_ultrashort_shift(data: pd.DataFrame, shift: int, model_dir: str, capacity: float | None = None) -> dict:
    cap = _capacity(capacity)
    target_col = _target_col(data)
    df = data.copy()
    df[TIME_COL] = pd.to_datetime(df[TIME_COL], errors="coerce")
    df = df.sort_values(TIME_COL).reset_index(drop=True)
    feat = build_wind_features(df)

    power = pd.to_numeric(feat[target_col], errors="coerce")
    p_shifted, power_feature = _add_ultrashort_shift_features(feat, power, shift)
    target = power - p_shifted

    feature_cols = _numeric_feature_cols(feat, target_col)
    if power_feature not in feature_cols:
        feature_cols.append(power_feature)
    X = _safe_numeric_frame(feat, feature_cols)
    y = target
    valid = y.notna() & p_shifted.notna()
    actual = power[valid].reset_index(drop=True)
    base = p_shifted[valid].reset_index(drop=True)
    X = X[valid].reset_index(drop=True)
    y = y[valid].reset_index(drop=True)
    if len(X) < 20:
        raise ValueError(f"not enough rows to train ultra-short shift {shift}")

    split = max(1, int(len(X) * 0.85))
    X_tr, y_tr = X.iloc[:split], y.iloc[:split]
    X_va, y_va = X.iloc[split:], y.iloc[split:]
    actual_va = actual.iloc[split:]
    base_va = base.iloc[split:]
    if X_va.empty:
        X_va, y_va = X_tr.tail(min(96, len(X_tr))), y_tr.tail(min(96, len(y_tr)))
        actual_va = actual.tail(len(X_va))
        base_va = base.tail(len(X_va))

    models = _fit_models(X_tr, y_tr, X_va, y_va, weighted=False)
    raw_delta_va = _predict_model_dict(models, X_va)
    raw_power_va = np.clip(raw_delta_va + base_va.to_numpy(dtype=float), 0, cap)
    calibration = _fit_affine_calibration(actual_va.to_numpy(dtype=float), raw_power_va, cap)
    bundle = {
        "kind": "optimized_ultrashort_ensemble",
        "shift": shift,
        "models": models,
        "feature_cols": feature_cols,
        "target_col": target_col,
        "power_feature": power_feature,
        "feature_version": "ultrashort_v2",
        "capacity": cap,
        "split": {"train_ratio": 0.85, "calibration_ratio": 0.15},
        "calibration": calibration,
    }

    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(bundle, os.path.join(model_dir, ULTRA_BUNDLE_NAME))
    joblib.dump(feature_cols, os.path.join(model_dir, "numeric_features.joblib"))
    joblib.dump({"n_shift_saved": shift, "feature_power_t_minus_N_col_name": power_feature}, os.path.join(model_dir, "predictor_config.joblib"))
    joblib.dump(bundle, os.path.join(model_dir, "model.joblib"))
    return bundle


def predict_ultrashort_shift(data: pd.DataFrame, model_dir: str) -> pd.Series:
    bundle_path = os.path.join(model_dir, ULTRA_BUNDLE_NAME)
    if not os.path.exists(bundle_path):
        bundle_path = os.path.join(model_dir, "model.joblib")
    try:
        refresh_ultrashort_calibration(model_dir)
    except Exception:
        pass
    bundle = joblib.load(bundle_path)
    if not isinstance(bundle, dict) or bundle.get("kind") != "optimized_ultrashort_ensemble":
        raise ValueError(f"optimized ultra-short bundle not found in {model_dir}")

    df = data.copy()
    df[TIME_COL] = pd.to_datetime(df[TIME_COL], errors="coerce")
    target_col = bundle["target_col"]
    if target_col not in df.columns and "wp_true" in df.columns:
        target_col = "wp_true"
    feat = build_wind_features(df)
    shift = int(bundle["shift"])
    power_feature = bundle["power_feature"]
    if target_col in feat.columns:
        power = pd.to_numeric(feat[target_col], errors="coerce")
    elif "wp_true" in feat.columns:
        power = pd.to_numeric(feat["wp_true"], errors="coerce")
    else:
        power = pd.Series(np.nan, index=feat.index)
    _, generated_power_feature = _add_ultrashort_shift_features(feat, power, shift)
    if generated_power_feature != power_feature:
        feat[power_feature] = feat[generated_power_feature]

    X = _safe_numeric_frame(feat, bundle["feature_cols"])
    delta = _predict_model_dict(bundle["models"], X)
    base = pd.to_numeric(feat[power_feature], errors="coerce").to_numpy()
    pred = np.clip(delta + base, 0, _capacity(bundle.get("capacity")))
    pred = _apply_affine_calibration(pred, bundle.get("calibration"), _capacity(bundle.get("capacity")))
    pred[np.isnan(base)] = np.nan
    return pd.Series(pred, index=data.index)
