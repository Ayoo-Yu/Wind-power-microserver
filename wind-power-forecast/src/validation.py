"""Data quality validation for MARS pipeline.

Checks physical ranges, temporal continuity, missing data blocks,
spatial consistency, and cross-source agreement.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    product: str
    n_rows: int = 0
    n_columns: int = 0
    time_range: tuple[str, str] = ("", "")
    nan_pct: dict[str, float] = field(default_factory=dict)
    range_violations: dict[str, int] = field(default_factory=dict)
    temporal_gaps: list[str] = field(default_factory=list)
    duplicate_timestamps: int = 0
    spatial_outliers: int = 0
    passed: bool = True

    def summary(self) -> str:
        lines = [f"=== Quality Report: {self.product} ==="]
        lines.append(f"Rows: {self.n_rows}, Columns: {self.n_columns}")
        lines.append(f"Time range: {self.time_range[0]} → {self.time_range[1]}")
        if self.duplicate_timestamps:
            lines.append(f"WARN: {self.duplicate_timestamps} duplicate timestamps")
        if self.temporal_gaps:
            lines.append(f"WARN: {len(self.temporal_gaps)} temporal gaps")
        if self.range_violations:
            lines.append(f"WARN: range violations: {self.range_violations}")
        high_nan = {k: v for k, v in self.nan_pct.items() if v > 5.0}
        if high_nan:
            lines.append(f"WARN: high NaN%: {high_nan}")
        lines.append(f"PASS: {self.passed}")
        return "\n".join(lines)


PHYSICAL_RANGES: dict[str, tuple[float, float]] = {
    "wind_speed_100m": (0, 80),
    "wind_speed_10m": (0, 60),
    "wind_speed_200m": (0, 90),
    "wind_u_100m": (-60, 60),
    "wind_v_100m": (-60, 60),
    "wind_u_10m": (-50, 50),
    "wind_v_10m": (-50, 50),
    "temperature_2m": (180, 340),
    "dewpoint_2m": (180, 340),
    "surface_pressure": (80000, 110000),
    "mean_sea_level_pressure": (90000, 110000),
    "boundary_layer_height": (0, 5000),
    "total_precipitation": (0, 500),
    "relative_humidity": (0, 105),
    "specific_humidity_2m": (0, 0.05),
    "cape": (0, 10000),
    "total_cloud_cover": (0, 105),
    "friction_velocity": (0, 10),
    "wind_gust_10m": (0, 100),
    "air_density": (0.8, 1.5),
    "wind_shear_index": (-2, 5),
}


def validate_physical_range(
    df: pd.DataFrame,
    column: str,
    min_val: float,
    max_val: float,
) -> int:
    if column not in df.columns:
        return 0
    vals = df[column].dropna()
    violations = int(((vals < min_val) | (vals > max_val)).sum())
    if violations > 0:
        logger.warning("Physical range violation: %s (%d rows outside [%s, %s])",
                       column, violations, min_val, max_val)
    return violations


def validate_monotonic_time(
    df: pd.DataFrame,
    time_col: str = "valid_time",
) -> tuple[bool, int]:
    if time_col not in df.columns:
        return True, 0
    times = pd.to_datetime(df[time_col])
    is_monotonic = bool(times.is_monotonic_increasing)
    duplicates = int(times.duplicated().sum())
    if duplicates > 0:
        logger.warning("Duplicate timestamps: %d", duplicates)
    if not is_monotonic:
        logger.warning("Timestamps not monotonically increasing")
    return is_monotonic, duplicates


def validate_no_missing_blocks(
    df: pd.DataFrame,
    columns: list[str],
    time_col: str = "valid_time",
    max_gap_rows: int = 6,
) -> list[str]:
    if time_col not in df.columns:
        return []
    gaps = []
    for col in columns:
        if col not in df.columns:
            continue
        is_nan = df[col].isna()
        block_lengths = _consecutive_true_lengths(is_nan)
        max_block = max(block_lengths) if block_lengths else 0
        if max_block > max_gap_rows:
            gaps.append(f"{col}: max NaN block = {max_block} rows")
    return gaps


def validate_spatial_consistency(
    df: pd.DataFrame,
    variable: str,
    lat_col: str = "point_lat",
    lon_col: str = "point_lon",
    time_col: str = "valid_time",
    zscore_threshold: float = 4.0,
) -> int:
    required = [variable, lat_col, lon_col, time_col]
    if not all(c in df.columns for c in required):
        return 0
    outliers = 0
    for _, group in df.groupby(time_col):
        vals = group[variable].dropna()
        if len(vals) < 3:
            continue
        mean = vals.mean()
        std = vals.std()
        if std < 1e-10:
            continue
        z = (vals - mean).abs() / std
        outliers += int((z > zscore_threshold).sum())
    return outliers


def validate_forecast_steps(
    df: pd.DataFrame,
    expected_steps: list[int],
    step_col: str = "step",
) -> tuple[bool, list[int]]:
    if step_col not in df.columns:
        return True, []
    actual = set(df[step_col].dropna().unique().astype(int))
    missing = [s for s in expected_steps if s not in actual]
    if missing:
        logger.warning("Missing forecast steps: %s", missing)
    return len(missing) == 0, missing


def validate_cross_source_agreement(
    hres_df: pd.DataFrame,
    era5_df: pd.DataFrame,
    variables: list[str],
    time_col: str = "valid_time",
    sigma_threshold: float = 5.0,
) -> dict[str, float]:
    if time_col not in hres_df.columns or time_col not in era5_df.columns:
        return {}
    hres_idx = hres_df.set_index(time_col)
    era5_idx = era5_df.set_index(time_col)
    common_idx = hres_idx.index.intersection(era5_idx.index)
    results = {}
    for var in variables:
        if var not in hres_idx.columns or var not in era5_idx.columns:
            continue
        diff = hres_idx.loc[common_idx, var] - era5_idx.loc[common_idx, var]
        diff = diff.dropna()
        if len(diff) < 10:
            continue
        mean_bias = float(diff.mean())
        std_diff = float(diff.std())
        n_extreme = int((diff.abs() > sigma_threshold * std_diff).sum())
        results[var] = {
            "mean_bias": mean_bias,
            "std_diff": std_diff,
            "extreme_count": n_extreme,
        }
    return results


def generate_quality_report(
    df: pd.DataFrame,
    product_name: str,
    time_col: str = "valid_time",
) -> QualityReport:
    report = QualityReport(product=product_name)
    report.n_rows = len(df)
    report.n_columns = len(df.columns)

    if time_col in df.columns:
        times = pd.to_datetime(df[time_col])
        report.time_range = (str(times.min()), str(times.max()))
        _, report.duplicate_timestamps = validate_monotonic_time(df, time_col)

    # NaN percentage
    for col in df.columns:
        pct = float(df[col].isna().mean() * 100)
        if pct > 0:
            report.nan_pct[col] = round(pct, 2)

    # Physical range checks
    for col, (lo, hi) in PHYSICAL_RANGES.items():
        violations = validate_physical_range(df, col, lo, hi)
        if violations > 0:
            report.range_violations[col] = violations

    # Temporal gaps in key columns
    key_cols = [c for c in df.columns if any(
        k in c for k in ["wind_speed", "temperature", "pressure"])]
    report.temporal_gaps = validate_no_missing_blocks(df, key_cols, time_col)

    # Overall pass/fail
    has_issues = (
        report.duplicate_timestamps > 0
        or len(report.temporal_gaps) > 0
        or any(v > report.n_rows * 0.01 for v in report.range_violations.values())
    )
    report.passed = not has_issues
    return report


def _consecutive_true_lengths(mask: pd.Series) -> list[int]:
    if not mask.any():
        return []
    groups = (mask != mask.shift()).cumsum()
    lengths = mask.groupby(groups).sum()
    return [int(l) for l in lengths[mask.groupby(groups).first()] if l > 0]
