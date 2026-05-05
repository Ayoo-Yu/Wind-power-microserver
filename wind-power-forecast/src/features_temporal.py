"""Temporal feature engineering for wind power forecasting.

All time-dimension features: lag, rolling statistics, rate of change,
diurnal encoding, cumulative sums, ramp detection, autocorrelation.

Input: time-indexed DataFrame (sorted by valid_time).
Output: DataFrame with new temporal feature columns appended.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_lag_features(
    df: pd.DataFrame,
    columns: list[str],
    lag_hours: list[int] = (1, 3, 6, 12, 24),
    time_col: str = "valid_time",
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    group_cols = group_cols or _detect_group_cols(df, time_col)
    for col in columns:
        if col not in out.columns:
            continue
        grouped = out.groupby(group_cols)[col] if group_cols else out[col]
        for h in lag_hours:
            out[f"{col}_lag_{h}h"] = grouped.shift(h)
    return out


def compute_rolling_features(
    df: pd.DataFrame,
    columns: list[str],
    windows: list[int] = (3, 6, 12, 24),
    funcs: list[str] = ("mean", "std"),
    time_col: str = "valid_time",
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    group_cols = group_cols or _detect_group_cols(df, time_col)
    for col in columns:
        if col not in out.columns:
            continue
        for w in windows:
            grouped = out.groupby(group_cols)[col] if group_cols else out[col]
            rolled = grouped.rolling(window=w, min_periods=1)
            for func in funcs:
                result = rolled.agg(func).reset_index(drop=True)
                out[f"{col}_roll_{func}_{w}h"] = result
    return out


def compute_rate_of_change(
    df: pd.DataFrame,
    columns: list[str],
    deltas: list[int] = (1, 3, 6),
    time_col: str = "valid_time",
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    group_cols = group_cols or _detect_group_cols(df, time_col)
    for col in columns:
        if col not in out.columns:
            continue
        grouped = out.groupby(group_cols)[col] if group_cols else out[col]
        for d in deltas:
            out[f"{col}_roc_{d}h"] = grouped.diff(d)
    return out


def compute_diurnal_features(
    df: pd.DataFrame,
    time_col: str = "valid_time",
) -> pd.DataFrame:
    out = df.copy()
    if time_col not in out.columns:
        return out
    hours = pd.to_datetime(out[time_col]).dt.hour
    out["hour_of_day"] = hours
    out["sin_hour"] = np.sin(2.0 * np.pi * hours / 24.0)
    out["cos_hour"] = np.cos(2.0 * np.pi * hours / 24.0)
    out["is_daytime"] = ((hours >= 6) & (hours <= 18)).astype(int)
    return out


def compute_season_features(
    df: pd.DataFrame,
    time_col: str = "valid_time",
) -> pd.DataFrame:
    out = df.copy()
    if time_col not in out.columns:
        return out
    ts = pd.to_datetime(out[time_col])
    month = ts.dt.month
    day_of_year = ts.dt.dayofyear

    # Season classification: 0=DJF, 1=MAM, 2=JJA, 3=SON
    out["season"] = (month % 12 // 3).astype(int)

    # Sin/cos encoding for smooth cyclical season representation
    out["sin_season"] = np.sin(2.0 * np.pi * day_of_year / 365.0)
    out["cos_season"] = np.cos(2.0 * np.pi * day_of_year / 365.0)

    # Day of year polar encoding (captures annual cycle)
    out["sin_doy"] = np.sin(2.0 * np.pi * day_of_year / 365.0)
    out["cos_doy"] = np.cos(2.0 * np.pi * day_of_year / 365.0)

    # Month polar encoding
    out["sin_month"] = np.sin(2.0 * np.pi * month / 12.0)
    out["cos_month"] = np.cos(2.0 * np.pi * month / 12.0)

    return out


def compute_forecast_step_features(
    df: pd.DataFrame,
    step_col: str = "step",
    time_col: str = "valid_time",
) -> pd.DataFrame:
    out = df.copy()

    if step_col in out.columns:
        step = pd.to_numeric(out[step_col], errors="coerce").fillna(0).astype(float)
        out["forecast_step_hours"] = step
        out["sin_step_daily"] = np.sin(2.0 * np.pi * step / 24.0)
        out["cos_step_daily"] = np.cos(2.0 * np.pi * step / 24.0)
        # Forecast horizon bins: short(0-48h), medium(49-144h), long(145-240h)
        out["forecast_horizon"] = pd.cut(
            step, bins=[-1, 48, 144, 1000],
            labels=[0, 1, 2]).astype(float)

    # Forecast age: hours since first valid_time (within each run)
    if time_col in out.columns:
        times = pd.to_datetime(out[time_col])
        out["forecast_age_hours"] = (times - times.min()).dt.total_seconds() / 3600.0

    return out


def compute_multi_step_ramp(
    df: pd.DataFrame,
    columns: list[str],
    deltas: list[int] = (1, 3, 6, 12, 24),
    time_col: str = "valid_time",
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    group_cols = group_cols or _detect_group_cols(df, time_col)
    for col in columns:
        if col not in out.columns:
            continue
        grouped = out.groupby(group_cols)[col] if group_cols else out[col]
        for d in deltas:
            diff = grouped.diff(d).reset_index(drop=True)
            out[f"{col}_change_{d}h"] = diff
            out[f"{col}_abs_change_{d}h"] = diff.abs()
            out[f"{col}_pct_change_{d}h"] = diff / out[col].replace(0, np.nan).abs()
    return out


def compute_cumulative_features(
    df: pd.DataFrame,
    columns: list[str],
    windows: list[int] = (6, 12, 24),
    time_col: str = "valid_time",
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    group_cols = group_cols or _detect_group_cols(df, time_col)
    for col in columns:
        if col not in out.columns:
            continue
        grouped = out.groupby(group_cols)[col] if group_cols else out[col]
        for w in windows:
            out[f"{col}_cumsum_{w}h"] = grouped.rolling(
                window=w, min_periods=1).sum().reset_index(drop=True)
    return out


def compute_ramp_features(
    df: pd.DataFrame,
    columns: list[str],
    thresholds: list[float] = (3.0, 5.0, 10.0),
    delta: int = 1,
    time_col: str = "valid_time",
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    group_cols = group_cols or _detect_group_cols(df, time_col)
    for col in columns:
        if col not in out.columns:
            continue
        grouped = out.groupby(group_cols)[col] if group_cols else out[col]
        diff = grouped.diff(delta).abs().reset_index(drop=True)
        for t in thresholds:
            out[f"{col}_ramp_gt{t:.0f}_{delta}h"] = (diff > t).astype(int)
    return out


def compute_autocorrelation(
    df: pd.DataFrame,
    columns: list[str],
    lag: int = 24,
    window: int = 72,
    time_col: str = "valid_time",
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    group_cols = group_cols or _detect_group_cols(df, time_col)
    for col in columns:
        if col not in out.columns:
            continue

        def _rolling_autocorr(s: pd.Series) -> pd.Series:
            return s.rolling(window=window, min_periods=lag + 1).apply(
                lambda x: float(x.autocorr(lag=lag)) if len(x) > lag else np.nan,
                raw=False,
            )

        grouped = out.groupby(group_cols)[col] if group_cols else out[col]
        out[f"{col}_autocorr_{lag}h"] = _rolling_autocorr(
            grouped.apply(lambda x: x.reset_index(drop=True))
            if group_cols else out[col]
        )
    return out


def build_temporal_features(
    df: pd.DataFrame,
    time_col: str = "valid_time",
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Build all temporal features with sensible defaults."""
    out = df.copy()
    group_cols = group_cols or _detect_group_cols(df, time_col)

    # Ensure sorted by time within groups
    out = out.sort_values(time_col).reset_index(drop=True)

    # Diurnal — always available
    out = compute_diurnal_features(out, time_col)

    # Season and annual cycle
    out = compute_season_features(out, time_col)

    # Forecast step / horizon
    out = compute_forecast_step_features(out, time_col=time_col)

    # Key wind variables for lag/rolling/ramp
    wind_cols = [c for c in [
        "wind_speed_100m", "wind_dir_100m", "wind_speed_10m",
        "wind_speed_200m", "wind_u_100m", "wind_v_100m",
    ] if c in out.columns]
    thermo_cols = [c for c in [
        "temperature_2m", "surface_pressure", "boundary_layer_height",
        "wind_shear_index", "air_density", "stability_index",
    ] if c in out.columns]

    target_cols = wind_cols + thermo_cols

    if target_cols:
        out = compute_lag_features(out, target_cols, time_col=time_col,
                                   group_cols=group_cols)
        out = compute_rolling_features(out, wind_cols, time_col=time_col,
                                       group_cols=group_cols)
        out = compute_rate_of_change(out, wind_cols, time_col=time_col,
                                     group_cols=group_cols)
        out = compute_ramp_features(out, ["wind_speed_100m", "wind_speed_10m"],
                                    time_col=time_col, group_cols=group_cols)
        # Multi-step ramp with signed/absolute/percentage change
        ramp_cols = [c for c in wind_cols if c in out.columns]
        if ramp_cols:
            out = compute_multi_step_ramp(out, ramp_cols, time_col=time_col,
                                          group_cols=group_cols)

    # Cumulative for precipitation and radiation
    accum_cols = [c for c in [
        "total_precipitation", "surface_solar_radiation_downwards",
        "surface_sensible_heat_flux", "surface_latent_heat_flux",
    ] if c in out.columns]
    if accum_cols:
        out = compute_cumulative_features(out, accum_cols, time_col=time_col,
                                          group_cols=group_cols)

    # Autocorrelation for main wind speed (expensive, only key column)
    if "wind_speed_100m" in out.columns:
        try:
            out = compute_autocorrelation(
                out, ["wind_speed_100m"], time_col=time_col, group_cols=group_cols)
        except Exception:
            pass  # skip if insufficient data

    return out


def _detect_group_cols(df: pd.DataFrame, time_col: str) -> list[str] | None:
    """Auto-detect spatial group columns for group-aware shifting."""
    candidates = ["point_lat", "point_lon"]
    found = [c for c in candidates if c in df.columns]
    if len(found) == 2:
        return found
    return None
