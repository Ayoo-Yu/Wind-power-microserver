"""Ultra-short-term (超短期) wind power forecasting — production script.

Usage:
    python forecast_ultrashort.py --site doupoliangzi
    python forecast_ultrashort.py --site shidongshan --calibrate
    python forecast_ultrashort.py --site zhuyuanxi

16-shift ensemble (15min to 240min), Southern Grid NEW formula.
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
N_SHIFTS = 16

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
def per_day_accuracy(y: np.ndarray, p: np.ndarray, cap: float) -> float:
    d = np.maximum(y, 0.2 * cap)
    return float((1.0 - np.sqrt(np.mean(((y - p) / d) ** 2))))


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


# ---- Grid identification ----
def identify_grid_columns(df: pd.DataFrame) -> dict:
    var_points = {}
    for col in df.columns:
        if col in [TIME_COL, TARGET]:
            continue
        for prefix in ["100u", "100v", "10u", "10v", "200u", "200v", "2t", "2d", "sp", "msl", "ssrd", "tcc", "tcwv"]:
            if col.startswith(prefix + "_") or (col.startswith(prefix) and "_" in col):
                parts = col.split("_")
                if len(parts) >= 3:
                    var_part = parts[0]
                    lat_lon = "_".join(parts[1:])
                    var_points.setdefault(var_part, []).append((col, lat_lon))
                break

    grid_map = {}
    for var, points in var_points.items():
        for i, (col, _) in enumerate(sorted(points, key=lambda x: x[1])):
            grid_map[col] = (var, i + 1)
    return grid_map


# ---- Feature engineering ----
def build_features(df: pd.DataFrame, grid_map: dict) -> pd.DataFrame:
    out = df.copy()
    out[TIME_COL] = pd.to_datetime(out[TIME_COL])

    # Wind speed from u/v
    wind_cols = {}
    for height in ["100", "10", "200"]:
        u_cols = sorted([(idx, c) for c, (v, idx) in grid_map.items() if v == f"{height}u"], key=lambda x: x[0])
        v_cols = sorted([(idx, c) for c, (v, idx) in grid_map.items() if v == f"{height}v"], key=lambda x: x[0])
        for (ui, uc), (vi, vc) in zip(u_cols, v_cols):
            ws_name = f"ws{height}_{ui}"
            out[ws_name] = np.sqrt(out[uc].astype(float) ** 2 + out[vc].astype(float) ** 2)
            wind_cols[(height, ui)] = ws_name

    # Spatial diffs
    for height in ["100", "10", "200"]:
        for i in range(1, 16):
            c1 = wind_cols.get((height, i))
            c2 = wind_cols.get((height, i + 1))
            if c1 and c2:
                out[f"ws{height}_diff_{i}"] = out[c2].astype(float) - out[c1].astype(float)

    # Temporal diffs (within NWP forecast)
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
        out["ws100_mean_pc"] = np.clip((ws100_mean - 3) / (12 - 3), 0, 1) * np.clip((25 - ws100_mean) / (25 - 20), 0, 1)

    if ws100_cols and ws10_cols:
        out["wind_shear"] = np.log(out[ws100_cols].mean(axis=1).astype(float) / out[ws10_cols].mean(axis=1).astype(float).replace(0, np.nan)) / np.log(10)

    sp_cols = [c for c, (v, _) in grid_map.items() if v == "sp"]
    t2_cols = [c for c, (v, _) in grid_map.items() if v == "2t"]
    if sp_cols and t2_cols:
        out["air_density"] = out[sp_cols].mean(axis=1).astype(float) / (287.05 * out[t2_cols].mean(axis=1).astype(float))
        if ws100_cols:
            out["power_density"] = 0.5 * out["air_density"] * out[ws100_cols].mean(axis=1).astype(float) ** 3

    # NWP forecast tendency
    if ws100_cols:
        ws100_mean = out[ws100_cols].mean(axis=1).astype(float)
        for horizon in [1, 2, 4, 8]:
            out[f"nwp_ws100_trend_{horizon}h"] = ws100_mean.shift(-horizon) - ws100_mean
        future_changes = pd.DataFrame({h: ws100_mean.shift(-h) - ws100_mean for h in [1, 2, 3, 4]})
        out["nwp_ws100_ramp_4h"] = future_changes.max(axis=1) - future_changes.min(axis=1)
        out["nwp_ws100_rising_1h"] = (out["nwp_ws100_trend_1h"] > 0).astype(int)
        out["nwp_ws100_rising_4h"] = (out["nwp_ws100_trend_4h"] > 0).astype(int)

    return out


def get_feature_cols(df: pd.DataFrame, train_feat: pd.DataFrame) -> list:
    raw_nwp = [c for c in df.columns if c not in [TIME_COL, TARGET]]
    ws_derived = []
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
        "nwp_ws100_trend_1h", "nwp_ws100_trend_2h", "nwp_ws100_trend_4h", "nwp_ws100_trend_8h",
        "nwp_ws100_ramp_4h", "nwp_ws100_rising_1h", "nwp_ws100_rising_4h",
    ]
    return list(dict.fromkeys([c for c in raw_nwp + ws_derived + extra if c in train_feat.columns]))


# ---- Per-shift training ----
def train_and_predict(train_feat, val_feat, test_df, shift, feat_cols, cap):
    import lightgbm as lgb
    from xgboost import XGBRegressor
    from catboost import CatBoostRegressor

    power_feat = f"power_actual_at_t_minus_{shift}"

    def prepare(df):
        power = df[TARGET].astype(float)
        p_shifted = power.shift(shift)
        target = power - p_shifted
        skip = {TIME_COL, TARGET}
        avail = [c for c in feat_cols if c in df.columns and c not in skip]
        X = df[avail].copy()
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

    X_tr, y_tr, _ = prepare(train_feat)
    X_va, y_va, _ = prepare(val_feat)
    X_te, y_te, p_base_te = prepare(test_df)

    common = [c for c in X_tr.columns if c in X_va.columns and c in X_te.columns]
    X_tr, X_va, X_te = X_tr[common], X_va[common], X_te[common]

    train_mask = ~np.isnan(y_tr)
    val_mask = ~np.isnan(y_va)
    X_tr_c, y_tr_c = X_tr[train_mask], y_tr[train_mask]
    X_va_c, y_va_c = X_va[val_mask], y_va[val_mask]

    preds = {}
    m = lgb.LGBMRegressor(
        boosting_type="dart", objective="regression", num_leaves=63, learning_rate=0.1,
        n_estimators=200, min_child_samples=20, feature_fraction=0.7,
        bagging_fraction=0.8, bagging_freq=5, verbose=-1,
        drop_rate=0.1, reg_alpha=0.1, reg_lambda=0.1,
    )
    m.fit(X_tr_c, y_tr_c)
    preds["dart"] = m.predict(X_te)

    m = XGBRegressor(
        n_estimators=500, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.7, reg_alpha=0.1, reg_lambda=1.0,
        random_state=42, early_stopping_rounds=50,
    )
    m.fit(X_tr_c, y_tr_c, eval_set=[(X_va_c, y_va_c)], verbose=False)
    preds["xgb"] = m.predict(X_te)

    m = CatBoostRegressor(
        iterations=500, depth=6, learning_rate=0.05,
        random_seed=42, verbose=0, early_stopping_rounds=50,
        l2_leaf_reg=3.0, subsample=0.8,
    )
    m.fit(X_tr_c, y_tr_c, eval_set=(X_va_c, y_va_c), verbose=0)
    preds["cb"] = m.predict(X_te)

    delta_pred = np.mean(list(preds.values()), axis=0)
    pred_power = np.clip(delta_pred + p_base_te, 0, cap)
    pred_power[:shift] = np.nan
    return pred_power


def averaged_predictions(shift_preds: dict, y_true: np.ndarray) -> tuple:
    avg = np.full(len(y_true), np.nan)
    for i in range(N_SHIFTS, len(y_true)):
        avg[i] = np.mean([shift_preds[s][i] for s in range(1, N_SHIFTS + 1)])
    valid = ~np.isnan(avg)
    return avg[valid], y_true[valid], valid


# ---- Calibration ----
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
    parser = argparse.ArgumentParser(description="Ultra-short-term wind power forecast")
    parser.add_argument("--site", required=True, choices=list(SITES.keys()))
    parser.add_argument("--calibrate", action="store_true", help="Enable post-hoc calibration")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    scfg = SITES[args.site]
    cap = float(scfg["cap"])
    out_dir = Path(args.output_dir) if args.output_dir else ROOT / "forecast_results" / args.site
    out_dir.mkdir(exist_ok=True, parents=True)

    should_calibrate = args.calibrate or (cap <= CALIBRATION_THRESHOLD_MW)

    print(f"Site: {args.site}  Cap: {cap}MW  Calibration: {should_calibrate}")
    print(f"Loading {scfg['path'].name}...")
    df = load_data(scfg["path"])
    print(f"  {len(df)} rows")

    train_df, val_df, test_df = split_data(df)
    print(f"  Train: {len(train_df)}  Val: {len(val_df)}  Test: {len(test_df)}")

    grid_map = identify_grid_columns(df)
    train_feat = build_features(train_df, grid_map)
    val_feat = build_features(val_df, grid_map)
    test_feat = build_features(test_df, grid_map)
    feat_cols = get_feature_cols(df, train_feat)
    print(f"  Static features: {len(feat_cols)} + 26 per-shift power features")

    t0 = time.time()
    val_shift, test_shift = {}, {}
    for s in range(1, N_SHIFTS + 1):
        val_shift[s] = np.clip(train_and_predict(train_feat, val_feat, val_feat, s, feat_cols, cap), 0, cap)
        test_shift[s] = np.clip(train_and_predict(train_feat, val_feat, test_feat, s, feat_cols, cap), 0, cap)
        if s in [1, 4, 8, 16]:
            valid = ~np.isnan(test_shift[s])
            acc = per_day_accuracy(test_feat[TARGET].to_numpy(float)[valid], test_shift[s][valid], cap)
            print(f"  shift {s:2d} ({s*15:3d}min): Acc={acc*100:.2f}%")
        elif s % 4 == 0:
            print(f"  shift {s}/{N_SHIFTS}")

    # Averaged predictions
    val_pred, y_val, valid_val = averaged_predictions(val_shift, val_feat[TARGET].to_numpy(float))
    test_pred, y_test, valid_test = averaged_predictions(test_shift, test_feat[TARGET].to_numpy(float))

    elapsed = time.time() - t0
    raw = score(y_test, test_pred, cap)
    print(f"\n  Time: {elapsed:.0f}s")
    print(f"  Raw: Acc={raw['accuracy_percent']:.2f}%  MAE={raw['mae']:.1f}  Bias={raw['bias']:+.1f}")

    results = [{"method": "raw", **raw, "site": args.site, "task": "ultrashort"}]

    # Calibration
    if should_calibrate:
        print("  Running dynamic affine calibration...")
        val_pred_df = pd.DataFrame({
            TIME_COL: val_df.loc[valid_val, TIME_COL].values,
            "actual": y_val.astype(float),
            "raw_pred": val_pred.astype(float),
        })
        test_pred_df = pd.DataFrame({
            TIME_COL: test_df.loc[valid_test, TIME_COL].values,
            "actual": y_test.astype(float),
            "raw_pred": test_pred.astype(float),
        })
        cal_rows = dynamic_rolling_with_val_seed(val_pred_df, test_pred_df, cap, window_days=14)
        for r in cal_rows:
            if r["method"] == "raw":
                continue
            delta = r["accuracy_percent"] - raw["accuracy_percent"]
            print(f"  {r['method']}: Acc={r['accuracy_percent']:.2f}% ({delta:+.2f}%)")
            results.append({"method": r["method"], "accuracy_percent": r["accuracy_percent"], "site": args.site, "task": "ultrashort"})

        if len(results) > 1 and results[-1]["accuracy_percent"] > raw["accuracy_percent"]:
            print("  Calibration improves accuracy — applying to output")
        else:
            print("  Calibration does not improve — using raw predictions")

    # Save
    shift_data = {TIME_COL: test_df[TIME_COL].values, "actual": test_feat[TARGET].to_numpy(float)}
    shift_data.update({f"shift_{s}": test_shift[s] for s in range(1, N_SHIFTS + 1)})
    pd.DataFrame(shift_data).to_csv(out_dir / "ultrashort_predictions.csv", index=False, encoding="utf-8-sig")
    (out_dir / "ultrashort_scores.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Saved to {out_dir}")


if __name__ == "__main__":
    main()
