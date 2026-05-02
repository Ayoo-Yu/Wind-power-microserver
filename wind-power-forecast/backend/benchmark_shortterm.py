"""Short-term (短期) power forecasting benchmark.

Best method: LGBM-DART + XGBoost-Weighted(4x) + CatBoost ensemble.
Split: 70/15/15 temporal.
Southern Grid formula: daily RMSE, D_i = max(P_Mi, 0.2*Cap).
Expected accuracy: ~66.3%.
"""
from __future__ import annotations
import sys, io, warnings
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
import lightgbm as lgb
from xgboost import XGBRegressor
from catboost import CatBoostRegressor

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

TARGET = "Total_Power"
TIME_COL = "Timestamp"
CAP = 453.5


def calc_accuracy(y_true, y_pred, cap=CAP):
    """Daily-averaged RMSE accuracy (Southern Grid formula)."""
    n_per_day = 96
    n_days = len(y_true) // n_per_day
    if n_days == 0:
        d = np.maximum(y_true, 0.2 * cap)
        return 1.0 - np.sqrt(np.mean(((y_true - y_pred) / d) ** 2))
    accs = []
    for day in range(n_days):
        s, e = day * n_per_day, (day + 1) * n_per_day
        pm, pp = y_true[s:e], y_pred[s:e]
        d = np.maximum(pm, 0.2 * cap)
        accs.append(1.0 - np.sqrt(np.mean(((pm - pp) / d) ** 2)))
    return float(np.mean(accs))


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    from src.features import build_all_features
    from src.features_temporal import build_temporal_features
    from src.features_wind_power import build_wind_power_features
    from src.features_weather_risk import build_weather_risk_features

    out = df.copy()
    out[TIME_COL] = pd.to_datetime(out[TIME_COL])

    out["Hour"] = out[TIME_COL].dt.hour
    out["Month"] = out[TIME_COL].dt.month
    out["hour_sin"] = np.sin(2 * np.pi * out["Hour"] / 24)
    out["hour_cos"] = np.cos(2 * np.pi * out["Hour"] / 24)
    out["month_sin"] = np.sin(2 * np.pi * out["Month"] / 12)
    out["month_cos"] = np.cos(2 * np.pi * out["Month"] / 12)
    doy = out[TIME_COL].dt.dayofyear
    out["sin_doy"] = np.sin(2 * np.pi * doy / 365)
    out["cos_doy"] = np.cos(2 * np.pi * doy / 365)
    out["is_daytime"] = ((out["Hour"] >= 6) & (out["Hour"] <= 18)).astype(int)

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
        if c.startswith("100u"): rename_map[c] = c.replace("100u", "wind_u_100m")
        elif c.startswith("100v"): rename_map[c] = c.replace("100v", "wind_v_100m")
        elif c.startswith("10u") and not c.startswith("100"): rename_map[c] = c.replace("10u", "wind_u_10m")
        elif c.startswith("10v") and not c.startswith("100"): rename_map[c] = c.replace("10v", "wind_v_10m")
        elif c.startswith("200u"): rename_map[c] = c.replace("200u", "wind_u_200m")
        elif c.startswith("200v"): rename_map[c] = c.replace("200v", "wind_v_200m")
        elif c.startswith("2t_"): rename_map[c] = c.replace("2t", "temperature_2m")
        elif c.startswith("2d_"): rename_map[c] = c.replace("2d", "dewpoint_2m")
        elif c.startswith("sp_"): rename_map[c] = c.replace("sp", "surface_pressure")
        elif c.startswith("msl"): rename_map[c] = c.replace("msl", "mean_sea_level_pressure")
        elif c.startswith("ssrd"): rename_map[c] = c.replace("ssrd", "surface_solar_radiation_downwards")
        elif c.startswith("tcc"): rename_map[c] = c.replace("tcc", "total_cloud_cover")
        elif c.startswith("tcwv"): rename_map[c] = c.replace("tcwv", "total_column_water_vapour")
    out = out.rename(columns=rename_map)

    for height in ["100m", "10m", "200m"]:
        u_col, v_col = f"wind_u_{height}", f"wind_v_{height}"
        if u_col in out.columns and v_col in out.columns:
            out[f"wind_speed_{height}"] = np.sqrt(out[u_col].astype(float)**2 + out[v_col].astype(float)**2)
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

    out = build_all_features(out)
    out = build_wind_power_features(out, hub_height=100.0)
    out = build_weather_risk_features(out)
    out = out.rename(columns={TIME_COL: "valid_time"})
    out = build_temporal_features(out)
    out = out.rename(columns={"valid_time": TIME_COL})
    return out


def prepare_xy(df):
    skip = {TIME_COL, TARGET}
    feature_cols = [c for c in df.columns
                    if c not in skip and df[c].dtype in [np.float64, np.float32, np.int64, np.int32, float, int]]
    X = df[feature_cols].copy().fillna(0).replace([np.inf, -np.inf], 0)
    y = df[TARGET].copy()
    mask = y.notna()
    return X[mask].reset_index(drop=True), y[mask].reset_index(drop=True), feature_cols


# ══════════════════════════════════════════════════════════════════════════════
# Load and split
# ══════════════════════════════════════════════════════════════════════════════
print("Loading ZYX_raw.csv...")
df = pd.read_csv("ZYX_raw.csv")
df[TIME_COL] = pd.to_datetime(df[TIME_COL])

n = len(df)
df_train = df.iloc[:int(n * 0.70)].reset_index(drop=True)
df_val = df.iloc[int(n * 0.70):int(n * 0.85)].reset_index(drop=True)
df_test = df.iloc[int(n * 0.85):].reset_index(drop=True)

print(f"Train: {len(df_train)}  Val: {len(df_val)}  Test: {len(df_test)}")
print(f"Test: {df_test[TIME_COL].iloc[0]} ~ {df_test[TIME_COL].iloc[-1]}")


# ══════════════════════════════════════════════════════════════════════════════
# Feature engineering
# ══════════════════════════════════════════════════════════════════════════════
print("\nBuilding features...")
train = build_features(df_train)
val = build_features(df_val)
test = build_features(df_test)

X_tr, y_tr, feats = prepare_xy(train)
X_va, y_va, _ = prepare_xy(val)
X_te, y_te, _ = prepare_xy(test)

common = [c for c in feats if c in X_va.columns and c in X_te.columns]
X_tr, X_va, X_te = X_tr[common], X_va[common], X_te[common]

y_te_arr = y_te.values
print(f"Features: {len(common)}")


def report(label, y_pred):
    acc = calc_accuracy(y_te_arr, y_pred)
    r2 = r2_score(y_te, y_pred)
    mae = mean_absolute_error(y_te, y_pred)
    hi_mask = y_te_arr >= 150
    hi_mae = np.abs(y_pred[hi_mask] - y_te_arr[hi_mask]).mean() if hi_mask.any() else 0
    print(f"  {label:55s} Acc={acc*100:.2f}%  R2={r2:.4f}  MAE={mae:.1f}  MAE_hi={hi_mae:.1f}")
    return acc


# ══════════════════════════════════════════════════════════════════════════════
# Train 3-model ensemble
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("ENSEMBLE: LGBM-DART + XGBoost-Weighted(4x) + CatBoost")
print("=" * 70)

preds = {}

# LGBM-DART (no early stopping, fixed rounds)
m = lgb.LGBMRegressor(
    boosting_type="dart", objective="regression",
    num_leaves=63, learning_rate=0.05, n_estimators=800,
    min_child_samples=30, feature_fraction=0.7,
    bagging_fraction=0.8, bagging_freq=5, verbose=-1,
    drop_rate=0.15, reg_alpha=0.1, reg_lambda=0.1,
)
m.fit(X_tr, y_tr)
preds["dart"] = np.clip(m.predict(X_te), 0, CAP)
report("LGBM-DART", preds["dart"])

# XGBoost-Weighted (with early stopping)
weights = np.where(y_tr > 150, 4.0, np.where(y_tr > 50, 1.5, 1.0))
m = XGBRegressor(
    n_estimators=2000, max_depth=6, learning_rate=0.03,
    subsample=0.8, colsample_bytree=0.7, reg_alpha=0.1, reg_lambda=1.0,
    random_state=42, early_stopping_rounds=100,
)
m.fit(X_tr, y_tr, sample_weight=weights, eval_set=[(X_va, y_va)], verbose=False)
preds["xgb_w"] = m.predict(X_te)
report(f"XGBoost-Weighted (best_iter={m.best_iteration})", preds["xgb_w"])

# CatBoost (with early stopping)
m = CatBoostRegressor(
    iterations=2000, depth=6, learning_rate=0.03,
    random_seed=42, verbose=0, early_stopping_rounds=100,
    l2_leaf_reg=3.0, subsample=0.8,
)
m.fit(X_tr, y_tr, eval_set=(X_va, y_va), verbose=0)
preds["catboost"] = m.predict(X_te)
report(f"CatBoost (best_iter={m.best_iteration_})", preds["catboost"])

# Ensemble
ens = np.clip(np.mean(list(preds.values()), axis=0), 0, CAP)
acc = report("ENSEMBLE", ens)


# ══════════════════════════════════════════════════════════════════════════════
# Report
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)

for label, lo, hi in [("Low(0-50)", 0, 50), ("Mid(50-150)", 50, 150),
                       ("High(150-250)", 150, 250), ("VHigh(250+)", 250, 9999)]:
    mask = (y_te_arr >= lo) & (y_te_arr < hi)
    if mask.any():
        mae = np.abs(ens[mask] - y_te_arr[mask]).mean()
        bias = (ens[mask] - y_te_arr[mask]).mean()
        print(f"  {label:15s}: MAE={mae:.1f}  Bias={bias:+.1f}  n={mask.sum()}")

pd.DataFrame({
    TIME_COL: df_test[TIME_COL].iloc[:len(y_te)].values,
    "actual": y_te_arr,
    "predicted": ens,
}).to_csv("benchmark_shortterm_results.csv", index=False)
print(f"\nSaved to benchmark_shortterm_results.csv")
