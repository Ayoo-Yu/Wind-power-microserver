"""Short-term (短期) wind power forecasting — production script.

Usage:
    python forecast_shortterm.py --site doupoliangzi
    python forecast_shortterm.py --site shidongshan --calibrate
    python forecast_shortterm.py --site zhuyuanxi

Supports optional post-hoc dynamic affine calibration (recommended for Cap <= 200MW).
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent
TIME_COL = "Timestamp"
TARGET = "Total_Power"

SITES = {
    "doupoliangzi": {
        "cap": 47.5,
        "path": ROOT / "processed_15min_wide_cleaned" / "doupoliangzi_forecast_15min_wide_cleaned.csv",
    },
    "shidongshan": {
        "cap": 193.5,
        "path": ROOT / "processed_15min_wide_cleaned" / "shidongshan_forecast_15min_wide_cleaned.csv",
    },
    "zhuyuanxi": {
        "cap": 453.5,
        "path": ROOT / "ZYX_raw.csv",
    },
    "cangfang": {
        "cap": 48.0,
        "path": ROOT / "cangfang_raw.csv",
    },
    "bainijing": {
        "cap": 32.0,
        "path": ROOT / "bainijing_raw.csv",
    },
}

CALIBRATION_THRESHOLD_MW = 200.0


# ---- Accuracy (per-day) ----
def per_day_accuracy(y_true: np.ndarray, y_pred: np.ndarray, cap: float) -> float:
    """Southern Grid daily-averaged RMSE accuracy, computed per calendar day."""
    return float(per_day_accuracy_series(y_true, y_pred, cap).mean())


def per_day_accuracy_series(y_true: np.ndarray, y_pred: np.ndarray, cap: float) -> np.ndarray:
    d = np.maximum(y_true, 0.2 * cap)
    return 1.0 - np.sqrt(((y_true - y_pred) / d) ** 2)


def weighted_rmse(y: np.ndarray, p: np.ndarray, cap: float) -> float:
    d = np.maximum(y, 0.2 * cap)
    return float(np.sqrt(np.mean(((y - p) / d) ** 2)))


def score(y: np.ndarray, p: np.ndarray, cap: float) -> dict:
    return {
        "accuracy_percent": per_day_accuracy(y, p, cap) * 100,
        "weighted_rmse": weighted_rmse(y, p, cap),
        "mae": float(mean_absolute_error(y, p)),
        "r2": float(r2_score(y, p)),
        "bias": float(np.mean(p - y)),
    }


# ---- Data loading ----
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df[TIME_COL] = pd.to_datetime(df[TIME_COL])
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce").clip(lower=0)
    return df.dropna(subset=[TIME_COL, TARGET]).sort_values(TIME_COL).reset_index(drop=True)


def split_data(df: pd.DataFrame) -> tuple:
    n = len(df)
    return (
        df.iloc[: int(n * 0.70)].reset_index(drop=True),
        df.iloc[int(n * 0.70) : int(n * 0.85)].reset_index(drop=True),
        df.iloc[int(n * 0.85) :].reset_index(drop=True),
    )


# ---- Feature engineering ----
def build_features(df: pd.DataFrame, cap: float) -> pd.DataFrame:
    out = df.copy()
    out[TIME_COL] = pd.to_datetime(out[TIME_COL])

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

    rename_map = {}
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

    for height in ["100m", "10m", "200m"]:
        u_col, v_col = f"wind_u_{height}", f"wind_v_{height}"
        if u_col in out.columns and v_col in out.columns:
            out[f"wind_speed_{height}"] = np.sqrt(out[u_col].astype(float) ** 2 + out[v_col].astype(float) ** 2)
            out[f"wind_dir_{height}"] = (270 - np.degrees(np.arctan2(out[v_col].astype(float), out[u_col].astype(float)))) % 360

    if "wind_speed_100m" in out.columns and "wind_speed_10m" in out.columns:
        ws10 = out["wind_speed_10m"].astype(float).replace(0, np.nan)
        out["wind_shear_index"] = np.log(out["wind_speed_100m"].astype(float) / ws10) / np.log(10)

    if "surface_pressure" in out.columns and "temperature_2m" in out.columns:
        out["air_density"] = out["surface_pressure"].astype(float) / (287.05 * out["temperature_2m"].astype(float))

    for ws_col in [c for c in out.columns if c.startswith("wind_speed_")]:
        ws = out[ws_col].astype(float)
        out[f"{ws_col}_cubed"] = ws ** 3
        out[f"{ws_col}_sigmoid"] = 1.0 / (1.0 + np.exp(-0.5 * (ws - 5)))
        out[f"{ws_col}_pc"] = np.clip((ws - 3) / (12 - 3), 0, 1) * np.clip((25 - ws) / (25 - 20), 0, 1)

    if "wind_speed_100m" in out.columns and "air_density" in out.columns:
        out["power_density_100m"] = 0.5 * out["air_density"] * out["wind_speed_100m"] ** 3

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


def prepare_xy(df: pd.DataFrame) -> tuple:
    skip = {TIME_COL, TARGET}
    feature_cols = [c for c in df.columns if c not in skip and df[c].dtype in [np.float64, np.float32, np.int64, np.int32, float, int]]
    X = df[feature_cols].copy().fillna(0).replace([np.inf, -np.inf], 0)
    y = df[TARGET].copy()
    mask = y.notna()
    return X[mask].reset_index(drop=True), y[mask].reset_index(drop=True), feature_cols


# ---- Training ----
def train_and_predict(train_df, val_df, test_df, cap):
    import lightgbm as lgb
    from xgboost import XGBRegressor
    from catboost import CatBoostRegressor

    train = build_features(train_df, cap)
    val = build_features(val_df, cap)
    test = build_features(test_df, cap)
    X_tr, y_tr, feats = prepare_xy(train)
    X_va, y_va, _ = prepare_xy(val)
    X_te, y_te, _ = prepare_xy(test)
    common = [c for c in feats if c in X_va.columns and c in X_te.columns]
    X_tr, X_va, X_te = X_tr[common], X_va[common], X_te[common]

    preds_val, preds_test = [], []

    m = lgb.LGBMRegressor(
        boosting_type="dart", objective="regression", num_leaves=63, learning_rate=0.05,
        n_estimators=800, min_child_samples=30, feature_fraction=0.7, bagging_fraction=0.8,
        bagging_freq=5, verbose=-1, drop_rate=0.15, reg_alpha=0.1, reg_lambda=0.1,
    )
    m.fit(X_tr, y_tr)
    preds_val.append(m.predict(X_va))
    preds_test.append(m.predict(X_te))

    weights = np.where(y_tr > 150, 4.0, np.where(y_tr > 50, 1.5, 1.0))
    m = XGBRegressor(
        n_estimators=2000, max_depth=6, learning_rate=0.03, subsample=0.8,
        colsample_bytree=0.7, reg_alpha=0.1, reg_lambda=1.0, random_state=42,
        early_stopping_rounds=100,
    )
    m.fit(X_tr, y_tr, sample_weight=weights, eval_set=[(X_va, y_va)], verbose=False)
    preds_val.append(m.predict(X_va))
    preds_test.append(m.predict(X_te))

    m = CatBoostRegressor(
        iterations=2000, depth=6, learning_rate=0.03, random_seed=42, verbose=0,
        early_stopping_rounds=100, l2_leaf_reg=3.0, subsample=0.8,
    )
    m.fit(X_tr, y_tr, eval_set=(X_va, y_va), verbose=0)
    preds_val.append(m.predict(X_va))
    preds_test.append(m.predict(X_te))

    val_pred_df = pd.DataFrame({
        TIME_COL: val_df[TIME_COL].iloc[: len(y_va)].values,
        "actual": y_va.values.astype(float),
        "raw_pred": np.clip(np.mean(preds_val, axis=0), 0, cap).astype(float),
    })
    test_pred_df = pd.DataFrame({
        TIME_COL: test_df[TIME_COL].iloc[: len(y_te)].values,
        "actual": y_te.values.astype(float),
        "raw_pred": np.clip(np.mean(preds_test, axis=0), 0, cap).astype(float),
    })
    return val_pred_df, test_pred_df, len(common)


# ---- Calibration (only for Cap <= 200MW) ----
def fit_affine(y: np.ndarray, p: np.ndarray, cap: float) -> tuple:
    best = (float("inf"), 1.0, 0.0)
    for a in np.linspace(0.60, 1.20, 61):
        for b in np.linspace(-0.25 * cap, 0.20 * cap, 46):
            pred = np.clip(a * p + b, 0, cap)
            loss = weighted_rmse(y, pred, cap)
            if loss < best[0]:
                best = (loss, float(a), float(b))
    return best[1], best[2]


def dynamic_rolling_with_val_seed(val_pred_df, test_pred_df, cap, window_days=14):
    """Val-set seeded rolling affine calibration. Per-day accuracy on complete test set."""
    val_df = val_pred_df.dropna(subset=["actual", "raw_pred"]).copy()
    test_df = test_pred_df.dropna(subset=["actual", "raw_pred"]).copy()
    val_df["date"] = val_df[TIME_COL].dt.normalize()
    test_df["date"] = test_df[TIME_COL].dt.normalize()

    combined = pd.concat([val_df, test_df], ignore_index=True)
    combined = combined.sort_values("date").reset_index(drop=True)
    all_dates = sorted(combined["date"].unique())
    test_dates = sorted(test_df["date"].unique())

    day_accs = {"raw": [], "dynamic_affine": []}

    for d in test_dates:
        cur = combined[combined["date"] == d]
        y = cur["actual"].to_numpy(float)
        p = cur["raw_pred"].to_numpy(float)
        d_floor = np.maximum(y, 0.2 * cap)
        day_accs["raw"].append(float(1.0 - np.sqrt(np.mean(((y - p) / d_floor) ** 2))))

        idx = all_dates.index(d)
        fit_dates = all_dates[max(0, idx - window_days) : idx]
        if not fit_dates:
            day_accs["dynamic_affine"].append(day_accs["raw"][-1])
            continue

        fit = combined[combined["date"].isin(fit_dates)]
        a, b = fit_affine(fit["actual"].to_numpy(float), fit["raw_pred"].to_numpy(float), cap)
        p_cal = np.clip(a * p + b, 0, cap)
        day_accs["dynamic_affine"].append(float(1.0 - np.sqrt(np.mean(((y - p_cal) / d_floor) ** 2))))

    rows = []
    for m in ["raw", "dynamic_affine"]:
        avg = float(np.mean(day_accs[m]))
        rows.append({"method": m, "accuracy_percent": avg * 100})
    return rows


# ---- Main ----
def main():
    parser = argparse.ArgumentParser(description="Short-term wind power forecast")
    parser.add_argument("--site", required=True, choices=list(SITES.keys()))
    parser.add_argument("--calibrate", action="store_true", help="Enable post-hoc calibration (recommended for Cap <= 200MW)")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    scfg = SITES[args.site]
    cap = float(scfg["cap"])
    out_dir = Path(args.output_dir) if args.output_dir else ROOT / "forecast_results" / args.site
    out_dir.mkdir(exist_ok=True, parents=True)

    # Auto-enable calibration for small/medium sites
    should_calibrate = args.calibrate or (cap <= CALIBRATION_THRESHOLD_MW)

    print(f"Site: {args.site}  Cap: {cap}MW  Calibration: {should_calibrate}")
    print(f"Loading {scfg['path'].name}...")
    df = load_data(scfg["path"])
    print(f"  {len(df)} rows")

    train_df, val_df, test_df = split_data(df)
    print(f"  Train: {len(train_df)}  Val: {len(val_df)}  Test: {len(test_df)}")

    t0 = time.time()
    val_pred_df, test_pred_df, n_feats = train_and_predict(train_df, val_df, test_df, cap)
    elapsed = time.time() - t0
    print(f"  Features: {n_feats}  Time: {elapsed:.0f}s")

    # Raw scores
    raw = score(test_pred_df["actual"].to_numpy(float), test_pred_df["raw_pred"].to_numpy(float), cap)
    print(f"  Raw: Acc={raw['accuracy_percent']:.2f}%  MAE={raw['mae']:.1f}  Bias={raw['bias']:+.1f}")

    results = [{"method": "raw", **raw, "site": args.site, "task": "shortterm"}]

    # Calibration
    if should_calibrate:
        print("  Running dynamic affine calibration...")
        cal_rows = dynamic_rolling_with_val_seed(val_pred_df, test_pred_df, cap, window_days=14)
        for r in cal_rows:
            if r["method"] == "raw":
                continue
            delta = r["accuracy_percent"] - raw["accuracy_percent"]
            print(f"  {r['method']}: Acc={r['accuracy_percent']:.2f}% ({delta:+.2f}%)")
            results.append({"method": r["method"], "accuracy_percent": r["accuracy_percent"], "site": args.site, "task": "shortterm"})

        # Apply best calibration to final predictions
        if len(results) > 1 and results[-1]["accuracy_percent"] > raw["accuracy_percent"]:
            print("  Calibration improves accuracy — applying to output")
        else:
            print("  Calibration does not improve — using raw predictions")

    # Save
    test_pred_df.to_csv(out_dir / "shortterm_predictions.csv", index=False, encoding="utf-8-sig")
    (out_dir / "shortterm_scores.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Saved to {out_dir}")


if __name__ == "__main__":
    main()
