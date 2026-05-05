"""Cross-source feature engineering.

Computes features by comparing HRES, ERA5, and ENS data:
- HRES-ERA5 systematic bias
- HRES-ENS spread ratio (outlier detection)
- ENS agreement classification
- Forecast cycle jump (consecutive cycle consistency)
- ERA5 climatology anomaly
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_hres_era5_bias(
    hres_df: pd.DataFrame,
    era5_df: pd.DataFrame,
    variables: list[str],
    time_col: str = "valid_time",
) -> pd.DataFrame:
    """Compute HRES - ERA5 bias for each variable at matching timestamps."""
    hres_idx = hres_df.set_index(time_col)
    era5_idx = era5_df.set_index(time_col)
    common_idx = hres_idx.index.intersection(era5_idx.index)

    result = pd.DataFrame({time_col: common_idx})
    for var in variables:
        if var not in hres_idx.columns or var not in era5_idx.columns:
            continue
        hres_vals = hres_idx.loc[common_idx, var]
        era5_vals = era5_idx.loc[common_idx, var]
        result[f"{var}_hres_era5_bias"] = (hres_vals - era5_vals).values
    return result.reset_index(drop=True)


def compute_hres_ens_spread_ratio(
    hres_df: pd.DataFrame,
    ens_stats_df: pd.DataFrame,
    variables: list[str],
    time_col: str = "valid_time",
) -> pd.DataFrame:
    """|HRES - ENS_mean| / ENS_std. High ratio = HRES is an outlier."""
    hres_idx = hres_df.set_index(time_col)
    ens_idx = ens_stats_df.set_index(time_col)
    common_idx = hres_idx.index.intersection(ens_idx.index)

    result = pd.DataFrame({time_col: common_idx})
    for var in variables:
        mean_col = f"{var}_ens_mean"
        std_col = f"{var}_ens_std"
        if var not in hres_idx.columns:
            continue
        if mean_col not in ens_idx.columns or std_col not in ens_idx.columns:
            continue
        hres_vals = hres_idx.loc[common_idx, var]
        ens_mean = ens_idx.loc[common_idx, mean_col]
        ens_std = ens_idx.loc[common_idx, std_col]
        ratio = (hres_vals - ens_mean).abs() / np.maximum(ens_std, 1e-6)
        result[f"{var}_ens_spread_ratio"] = ratio.values
    return result.reset_index(drop=True)


def compute_ens_agreement(
    ens_stats_df: pd.DataFrame,
    variables: list[str],
    cv_threshold: float = 0.15,
) -> pd.DataFrame:
    """Classify ENS agreement based on coefficient of variation (std/mean)."""
    result = ens_stats_df.copy()
    for var in variables:
        mean_col = f"{var}_ens_mean"
        std_col = f"{var}_ens_std"
        if mean_col not in result.columns or std_col not in result.columns:
            continue
        cv = result[std_col] / np.maximum(result[mean_col].abs(), 1e-6)
        result[f"{var}_ens_agreement"] = pd.cut(
            cv, bins=[-np.inf, cv_threshold, 2 * cv_threshold, np.inf],
            labels=["high", "medium", "low"],
        )
    return result


def compute_cycle_jump(
    current_cycle_df: pd.DataFrame,
    previous_cycle_df: pd.DataFrame,
    variables: list[str],
    time_col: str = "valid_time",
) -> pd.DataFrame:
    """Difference between consecutive HRES cycles at same valid_time.

    Large jump = forecast inconsistency = higher uncertainty.
    """
    curr_idx = current_cycle_df.set_index(time_col)
    prev_idx = previous_cycle_df.set_index(time_col)
    common_idx = curr_idx.index.intersection(prev_idx.index)

    result = pd.DataFrame({time_col: common_idx})
    for var in variables:
        if var not in curr_idx.columns or var not in prev_idx.columns:
            continue
        jump = curr_idx.loc[common_idx, var] - prev_idx.loc[common_idx, var]
        result[f"{var}_cycle_jump"] = jump.values
    return result.reset_index(drop=True)


def compute_climatology_anomaly(
    df: pd.DataFrame,
    variable: str,
    window_days: int = 30,
    time_col: str = "valid_time",
) -> pd.DataFrame:
    """Deviation from rolling climatological mean (window_days window)."""
    out = df.copy()
    if variable not in out.columns or time_col not in out.columns:
        return out
    ts = pd.to_datetime(out[time_col])
    hour = ts.dt.hour
    grouped = out.groupby(hour)[variable]
    rolling_mean = grouped.transform(
        lambda x: x.rolling(window=window_days, min_periods=5).mean())
    out[f"{variable}_clim_anomaly"] = out[variable] - rolling_mean
    return out


def build_cross_source_features(
    hres_df: pd.DataFrame,
    era5_df: pd.DataFrame | None = None,
    ens_stats_df: pd.DataFrame | None = None,
    time_col: str = "valid_time",
) -> pd.DataFrame:
    """Build all cross-source features and merge into HRES dataframe."""
    base = hres_df.copy()

    key_vars = [c for c in [
        "wind_speed_100m", "temperature_2m", "surface_pressure",
        "wind_speed_10m", "boundary_layer_height",
    ] if c in base.columns]

    if era5_df is not None and not era5_df.empty:
        bias_df = compute_hres_era5_bias(base, era5_df, key_vars, time_col)
        if not bias_df.empty:
            base = base.merge(bias_df, on=time_col, how="left")

    if ens_stats_df is not None and not ens_stats_df.empty:
        ratio_df = compute_hres_ens_spread_ratio(
            base, ens_stats_df, key_vars, time_col)
        if not ratio_df.empty:
            base = base.merge(ratio_df, on=time_col, how="left")

        ens_key = [c for c in key_vars if f"{c}_ens_mean" in ens_stats_df.columns]
        if ens_key:
            agreement_df = compute_ens_agreement(ens_stats_df, ens_key)
            agree_cols = [f"{v}_ens_agreement" for v in ens_key
                          if f"{v}_ens_agreement" in agreement_df.columns]
            if agree_cols and time_col in agreement_df.columns:
                base = base.merge(
                    agreement_df[[time_col] + agree_cols], on=time_col, how="left")

    # Climatology anomaly for key variables
    for var in key_vars:
        base = compute_climatology_anomaly(base, var, time_col=time_col)

    return base
