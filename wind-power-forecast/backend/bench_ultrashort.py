"""Benchmark ultra-short training to find bottleneck."""
import time
import os
import numpy as np
import pandas as pd

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from database_config import engine
from db_session import db_session
from services.forecast_service import (
    load_training_data_from_db, split_train_calibrate,
    build_features_ultrashort, get_feature_cols_ultrashort,
    prepare_shift_features, identify_grid_columns, fit_affine,
    score, N_SHIFTS,
)

FARM = "ZYX"
TABLE = "train_pre_short_zyx"

with db_session() as session:
    df = load_training_data_from_db(session, TABLE, FARM)
print(f"Data: {len(df)} rows")

df = df.dropna(subset=["Total_Power"]).reset_index(drop=True)
print(f"After dropna: {len(df)} rows")

train_df, val_df, test_df = split_train_calibrate(df)
print(f"Split: train={len(train_df)} val={len(val_df)} test={len(test_df)}")

# Feature engineering
full_df = pd.concat([train_df, val_df, test_df], ignore_index=True)
t0 = time.time()
grid_map = identify_grid_columns(full_df)
train_feat = build_features_ultrashort(train_df, grid_map)
val_feat = build_features_ultrashort(val_df, grid_map)
test_feat = build_features_ultrashort(test_df, grid_map)
feat_cols = get_feature_cols_ultrashort(full_df, train_feat)
t_feat = time.time() - t0
print(f"Feature eng: {t_feat:.1f}s, {len(feat_cols)} features")

# Prepare features for shift 1
t0 = time.time()
X_tr, y_tr, _ = prepare_shift_features(train_feat, 1, feat_cols)
X_va, y_va, _ = prepare_shift_features(val_feat, 1, feat_cols)
X_te, y_te, p_base = prepare_shift_features(test_feat, 1, feat_cols)
common = [c for c in X_tr.columns if c in X_va.columns and c in X_te.columns]
X_tr, X_va, X_te = X_tr[common], X_va[common], X_te[common]
mask_tr = ~np.isnan(y_tr)
mask_va = ~np.isnan(y_va)
X_tr_c, y_tr_c = X_tr[mask_tr], y_tr[mask_tr]
X_va_c, y_va_c = X_va[mask_va], y_va[mask_va]
t_prep = time.time() - t0
print(f"Prepare shift: {t_prep:.1f}s, X_tr={X_tr_c.shape}")

# Train 3 models
import lightgbm as lgb
from xgboost import XGBRegressor
from catboost import CatBoostRegressor

t0 = time.time()
m = lgb.LGBMRegressor(boosting_type="dart", objective="regression", num_leaves=63,
    learning_rate=0.1, n_estimators=200, min_child_samples=20,
    feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=5,
    verbose=-1, drop_rate=0.1, reg_alpha=0.1, reg_lambda=0.1, n_jobs=1)
m.fit(X_tr_c, y_tr_c)
t_lgb = time.time() - t0

t0 = time.time()
m = XGBRegressor(n_estimators=500, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.7, reg_alpha=0.1, reg_lambda=1.0,
    random_state=42, early_stopping_rounds=50, n_jobs=1)
m.fit(X_tr_c, y_tr_c, eval_set=[(X_va_c, y_va_c)], verbose=False)
t_xgb = time.time() - t0

t0 = time.time()
m = CatBoostRegressor(iterations=500, depth=6, learning_rate=0.05,
    random_seed=42, verbose=0, early_stopping_rounds=50,
    l2_leaf_reg=3.0, subsample=0.8, thread_count=1)
m.fit(X_tr_c, y_tr_c, eval_set=(X_va_c, y_va_c), verbose=0)
t_cb = time.time() - t0

t_shift = t_lgb + t_xgb + t_cb
print(f"\nPer shift: LGB={t_lgb:.1f}s  XGB={t_xgb:.1f}s  CB={t_cb:.1f}s  Total={t_shift:.1f}s")
print(f"16 shifts sequential: {t_feat + 16*(t_prep + t_shift):.0f}s")
print(f"16 shifts parallel (ideal): {t_feat + t_prep + t_shift:.0f}s + calibration")

# Calibration timing
y_test_full = test_feat["Total_Power"].to_numpy(float)
t0 = time.time()
for s in range(1, 17):
    fit_affine(y_test_full, y_test_full, 453.5)
t_cal = time.time() - t0
print(f"Calibration (16 shifts): {t_cal:.1f}s")

print(f"\n=== TOTAL ESTIMATE ===")
print(f"Sequential: {t_feat + 16*(t_prep + t_shift) + t_cal:.0f}s")
print(f"Parallel:   {t_feat + t_prep + t_shift + t_cal:.0f}s (best case)")
