"""Ultra-short-term (超短期) power forecasting benchmark.

Best method: LGBM-DART + XGBoost + CatBoost ensemble, delta target.
Split: 70/15/15 temporal.
Southern Grid NEW formula: P_Pi = mean of 16 rolling predictions.
Expected accuracy: ~77.5%.

Features:
  - NWP wind speed (raw + spatial/temporal diffs)
  - Time encoding, wind domain features
  - NWP forecast tendency (wind speed trend over next 1-8h)
  - Power history stats relative to P(t-N): mean/std/min/max/range over 4/8/16 steps,
    trend (1/4/8/16 step rate of change), acceleration
"""
from __future__ import annotations
import sys, io, warnings, time
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
N_SHIFTS = 16


def calc_accuracy(y_true, y_pred, cap=CAP):
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


def averaged_predictions(shift_preds: dict, y_true: np.ndarray):
    n = len(y_true)
    start_idx = N_SHIFTS
    avg = np.full(n, np.nan)
    for i in range(start_idx, n):
        avg[i] = np.mean([shift_preds[s][i] for s in range(1, N_SHIFTS + 1)])
    valid = ~np.isnan(avg)
    return avg[valid], y_true[valid]


def identify_grid_columns(df):
    var_points = {}
    for col in df.columns:
        if col in [TIME_COL, TARGET]:
            continue
        for prefix in ['100u', '100v', '10u', '10v', '200u', '200v',
                        '2t', '2d', 'sp', 'msl', 'ssrd', 'tcc', 'tcwv']:
            if col.startswith(prefix + '_') or (col.startswith(prefix) and '_' in col):
                parts = col.split('_')
                if len(parts) >= 3:
                    var_part = parts[0]
                    lat_lon = '_'.join(parts[1:])
                    if var_part not in var_points:
                        var_points[var_part] = []
                    var_points[var_part].append((col, lat_lon))
                break

    grid_map = {}
    for var, points in var_points.items():
        points_sorted = sorted(points, key=lambda x: x[1])
        for i, (col, _) in enumerate(points_sorted):
            grid_map[col] = (var, i + 1)
    return grid_map


def build_features(df: pd.DataFrame, grid_map: dict) -> pd.DataFrame:
    out = df.copy()
    out[TIME_COL] = pd.to_datetime(out[TIME_COL])
    power = out[TARGET].astype(float)

    # === Wind speed from u/v ===
    wind_cols = {}
    for height in ['100', '10', '200']:
        u_cols = sorted([(idx, c) for c, (v, idx) in grid_map.items() if v == f'{height}u'], key=lambda x: x[0])
        v_cols = sorted([(idx, c) for c, (v, idx) in grid_map.items() if v == f'{height}v'], key=lambda x: x[0])
        for (ui, uc), (vi, vc) in zip(u_cols, v_cols):
            ws_name = f'ws{height}_{ui}'
            out[ws_name] = np.sqrt(out[uc].astype(float)**2 + out[vc].astype(float)**2)
            wind_cols[(height, ui)] = ws_name

    for height in ['100', '10', '200']:
        for i in range(1, 15):
            c1 = wind_cols.get((height, i))
            c2 = wind_cols.get((height, i + 1))
            if c1 and c2:
                out[f'ws{height}_diff_{i}'] = out[c2].astype(float) - out[c1].astype(float)

    for height in ['100', '10', '200']:
        for i in range(1, 16):
            ws_name = wind_cols.get((height, i))
            if ws_name:
                ws = out[ws_name].astype(float)
                for lag in [1, 2, 3]:
                    out[f'{ws_name}_diff_prev{lag}'] = ws - ws.shift(lag)

    # === Time encoding ===
    hour = out[TIME_COL].dt.hour
    out['hour_sin'] = np.sin(2 * np.pi * hour / 24)
    out['hour_cos'] = np.cos(2 * np.pi * hour / 24)
    out['is_daytime'] = ((hour >= 6) & (hour <= 18)).astype(int)

    # === Wind power domain features ===
    ws100_cols = [f'ws100_{i}' for i in range(1, 16) if f'ws100_{i}' in out.columns]
    ws10_cols = [f'ws10_{i}' for i in range(1, 16) if f'ws10_{i}' in out.columns]

    if ws100_cols:
        ws100_mean = out[ws100_cols].mean(axis=1).astype(float)
        out['ws100_mean_cubed'] = ws100_mean ** 3
        out['ws100_mean_sigmoid'] = 1.0 / (1.0 + np.exp(-0.5 * (ws100_mean - 5)))
        out['ws100_mean_pc'] = np.clip((ws100_mean - 3) / (12 - 3), 0, 1) * np.clip((25 - ws100_mean) / (25 - 20), 0, 1)

    if ws100_cols and ws10_cols:
        ws100_mean = out[ws100_cols].mean(axis=1).astype(float)
        ws10_mean = out[ws10_cols].mean(axis=1).astype(float)
        out['wind_shear'] = np.log(ws100_mean / ws10_mean.replace(0, np.nan)) / np.log(10)

    sp_cols = [c for c, (v, _) in grid_map.items() if v == 'sp']
    t2_cols = [c for c, (v, _) in grid_map.items() if v == '2t']
    if sp_cols and t2_cols:
        sp_mean = out[sp_cols].mean(axis=1).astype(float)
        t2_mean = out[t2_cols].mean(axis=1).astype(float)
        out['air_density'] = sp_mean / (287.05 * t2_mean)
        if ws100_cols:
            out['power_density'] = 0.5 * out['air_density'] * out[ws100_cols].mean(axis=1).astype(float) ** 3

    # === NWP forecast tendency (valid: same forecast cycle, all hours available) ===
    if ws100_cols:
        ws100_mean = out[ws100_cols].mean(axis=1).astype(float)
        for horizon in [1, 2, 4, 8]:
            out[f'nwp_ws100_trend_{horizon}h'] = ws100_mean.shift(-horizon) - ws100_mean
        future_changes = pd.DataFrame({
            h: ws100_mean.shift(-h) - ws100_mean for h in [1, 2, 3, 4]
        })
        out['nwp_ws100_ramp_4h'] = future_changes.max(axis=1) - future_changes.min(axis=1)
        out['nwp_ws100_rising_1h'] = (out['nwp_ws100_trend_1h'] > 0).astype(int)
        out['nwp_ws100_rising_4h'] = (out['nwp_ws100_trend_4h'] > 0).astype(int)

    # NOTE: power history features are NOT built here.
    # They must be computed per-shift inside train_and_predict,
    # using P(t-N), P(t-N-1), ... (only data available at prediction time).

    return out


def train_and_predict(train_df, val_df, test_df, shift, feature_cols):
    power_feat = f'power_actual_at_t_minus_{shift}'

    def prepare(df):
        power = df[TARGET].astype(float)
        p_shifted = power.shift(shift)
        target = power - p_shifted

        skip = {TIME_COL, TARGET}
        avail = [c for c in feature_cols if c in df.columns and c not in skip]
        X = df[avail].copy()
        X[power_feat] = p_shifted.values

        # === Power history relative to P(t-shift) ===
        # At prediction time for shift N, we know P(t-N), P(t-N-1), P(t-N-2), ...
        # These describe the power trajectory BEFORE the prediction point.
        for window in [4, 8, 16]:
            hist = power.shift(shift + 1).rolling(window, min_periods=1)
            X[f'phist_mean_{window}'] = hist.mean().values
            X[f'phist_std_{window}'] = hist.std().values
            X[f'phist_min_{window}'] = hist.min().values
            X[f'phist_max_{window}'] = hist.max().values
            X[f'phist_range_{window}'] = (hist.max() - hist.min()).values

        # Power trend: how P(t-N) compares to earlier values
        X['ptrend_1'] = (p_shifted - power.shift(shift + 1)).values
        X['ptrend_4'] = (p_shifted - power.shift(shift + 4)).values
        X['ptrend_8'] = (p_shifted - power.shift(shift + 8)).values
        X['ptrend_16'] = (p_shifted - power.shift(shift + 16)).values

        # Power acceleration
        vel1 = p_shifted - power.shift(shift + 1)
        vel2 = power.shift(shift + 1) - power.shift(shift + 2)
        X['paccel'] = (vel1 - vel2).values

        X = X.fillna(0).replace([np.inf, -np.inf], 0)
        return X, target.values, p_shifted.values

    X_tr, y_tr, _ = prepare(train_df)
    X_va, y_va, _ = prepare(val_df)
    X_te, y_te, p_base_te = prepare(test_df)

    common = [c for c in X_tr.columns if c in X_va.columns and c in X_te.columns]
    X_tr, X_va, X_te = X_tr[common], X_va[common], X_te[common]

    train_mask = ~np.isnan(y_tr)
    X_tr_c, y_tr_c = X_tr[train_mask], y_tr[train_mask]

    val_mask = ~np.isnan(y_va)
    X_va_c, y_va_c = X_va[val_mask], y_va[val_mask]

    preds = {}

    m = lgb.LGBMRegressor(
        boosting_type="dart", objective="regression",
        num_leaves=63, learning_rate=0.1, n_estimators=200,
        min_child_samples=20, feature_fraction=0.7,
        bagging_fraction=0.8, bagging_freq=5, verbose=-1,
        drop_rate=0.1, reg_alpha=0.1, reg_lambda=0.1,
    )
    m.fit(X_tr_c, y_tr_c)
    preds['dart'] = m.predict(X_te)

    m = XGBRegressor(
        n_estimators=500, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.7, reg_alpha=0.1, reg_lambda=1.0,
        random_state=42, early_stopping_rounds=50,
    )
    m.fit(X_tr_c, y_tr_c, eval_set=[(X_va_c, y_va_c)], verbose=False)
    preds['xgb'] = m.predict(X_te)

    m = CatBoostRegressor(
        iterations=500, depth=6, learning_rate=0.05,
        random_seed=42, verbose=0, early_stopping_rounds=50,
        l2_leaf_reg=3.0, subsample=0.8,
    )
    m.fit(X_tr_c, y_tr_c, eval_set=(X_va_c, y_va_c), verbose=0)
    preds['cb'] = m.predict(X_te)

    delta_pred = np.mean(list(preds.values()), axis=0)
    pred_power = np.clip(delta_pred + p_base_te, 0, CAP)
    pred_power[:shift] = np.nan

    return pred_power


# ══════════════════════════════════════════════════════════════════════════════
# Load and split
# ══════════════════════════════════════════════════════════════════════════════
print("Loading ZYX_raw.csv...")
df = pd.read_csv("ZYX_raw.csv")
df[TIME_COL] = pd.to_datetime(df[TIME_COL])

grid_map = identify_grid_columns(df)

n = len(df)
df_train = df.iloc[:int(n * 0.70)].reset_index(drop=True)
df_val = df.iloc[int(n * 0.70):int(n * 0.85)].reset_index(drop=True)
df_test = df.iloc[int(n * 0.85):].reset_index(drop=True)

print(f"Train: {len(df_train)}  Val: {len(df_val)}  Test: {len(df_test)}")

print("Building features...")
train_feat = build_features(df_train, grid_map)
val_feat = build_features(df_val, grid_map)
test_feat = build_features(df_test, grid_map)

# Feature columns (static features from build_features)
raw_nwp_cols = [c for c in df.columns if c not in [TIME_COL, TARGET]]
ws_derived = []
for height in ['100', '10', '200']:
    for i in range(1, 16):
        ws_derived.append(f'ws{height}_{i}')
    for i in range(1, 15):
        ws_derived.append(f'ws{height}_diff_{i}')
    for i in range(1, 16):
        for lag in [1, 2, 3]:
            ws_derived.append(f'ws{height}_{i}_diff_prev{lag}')

v1_extra = ['hour_sin', 'hour_cos', 'is_daytime',
            'ws100_mean_cubed', 'ws100_mean_sigmoid', 'ws100_mean_pc',
            'wind_shear', 'air_density', 'power_density']

nwp_trend_cols = ['nwp_ws100_trend_1h', 'nwp_ws100_trend_2h',
                  'nwp_ws100_trend_4h', 'nwp_ws100_trend_8h',
                  'nwp_ws100_ramp_4h', 'nwp_ws100_rising_1h', 'nwp_ws100_rising_4h']

feat_cols = list(dict.fromkeys(
    [c for c in (raw_nwp_cols + ws_derived) if c in train_feat.columns] +
    [c for c in (v1_extra + nwp_trend_cols) if c in train_feat.columns]
))

n_static = len(feat_cols)
# +1 power_actual_at_t_minus_N + 25 power history features (computed per-shift in train_and_predict)
print(f"Static features: {n_static} + 26 per-shift power features")

y_test = test_feat[TARGET].values


# ══════════════════════════════════════════════════════════════════════════════
# Train 16 shift models
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("v2: LGBM-DART + XGBoost + CatBoost + power history + NWP tendency")
print("  Power history uses P(t-N) and earlier (no leakage)")
print("=" * 70)

t0 = time.time()
shift_preds = {}
for s in range(1, N_SHIFTS + 1):
    shift_preds[s] = train_and_predict(train_feat, val_feat, test_feat, s, feat_cols)
    if s in [1, 2, 4, 8, 12, 16]:
        valid = ~np.isnan(shift_preds[s])
        acc = calc_accuracy(y_test[valid], shift_preds[s][valid])
        mae = mean_absolute_error(y_test[valid], shift_preds[s][valid])
        print(f"  Shift {s:2d} ({s*15:3d}min): Acc={acc*100:.2f}%  MAE={mae:.1f}")

print(f"  Time: {time.time()-t0:.1f}s")


# ══════════════════════════════════════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("v2 RESULTS (Southern Grid Ultra-Short-Term NEW Formula)")
print("=" * 70)

avg_pred, true_val = averaged_predictions(shift_preds, y_test)

acc = calc_accuracy(true_val, avg_pred)
mae = mean_absolute_error(true_val, avg_pred)
r2 = r2_score(true_val, avg_pred)

print(f"\n  Accuracy: {acc*100:.2f}%")
print(f"  MAE:      {mae:.1f}")
print(f"  R2:       {r2:.4f}")

print(f"\n  Per power level:")
for label, lo, hi in [("Low(0-50)", 0, 50), ("Mid(50-150)", 50, 150),
                       ("High(150-250)", 150, 250), ("VHigh(250+)", 250, 9999)]:
    mask = (true_val >= lo) & (true_val < hi)
    if mask.any():
        print(f"  {label:15s}: MAE={np.abs(avg_pred[mask]-true_val[mask]).mean():.1f}  "
              f"Bias={(avg_pred[mask]-true_val[mask]).mean():+.1f}  n={mask.sum()}")

print(f"\n  vs v1 (76.55%):")
print(f"  Accuracy delta: {(acc - 0.7655)*100:+.2f}%")

print(f"\n  Per-shift comparison:")
print(f"  {'Shift':>8s}  {'v1':>8s}  {'v2':>8s}  {'Delta':>8s}")
v1_accs = {1: 91.63, 2: 86.12, 4: 79.04, 8: 71.98, 12: 68.20, 16: 66.73}
for s in [1, 2, 4, 8, 12, 16]:
    valid = ~np.isnan(shift_preds[s])
    a = calc_accuracy(y_test[valid], shift_preds[s][valid]) * 100
    delta = a - v1_accs[s]
    print(f"  {s:>2d} ({s*15:3d}m)  {v1_accs[s]:>7.2f}%  {a:>7.2f}%  {delta:>+7.2f}%")

pd.DataFrame({
    TIME_COL: df_test[TIME_COL].values,
    "actual": y_test,
    **{f"shift_{s}": shift_preds[s] for s in range(1, N_SHIFTS+1)},
}).to_csv("benchmark_ultrashort_v2_results.csv", index=False)
print(f"\nSaved to benchmark_ultrashort_v2_results.csv")
