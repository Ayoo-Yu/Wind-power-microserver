"""ENS ensemble statistics - Layer 4 features."""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from scipy.stats import skew, kurtosis


def compute_ensemble_stats(
    ens_df: pd.DataFrame,
    variable: str,
    time_col: str = "valid_time",
    member_col: str = "number",
) -> pd.DataFrame:
    """Compute ensemble statistics for a single variable across members."""
    grouped = ens_df.groupby(time_col)[variable]
    stats = pd.DataFrame({
        f"{variable}_ens_mean": grouped.mean(),
        f"{variable}_ens_std": grouped.std(),
        f"{variable}_ens_p10": grouped.quantile(0.10),
        f"{variable}_ens_p25": grouped.quantile(0.25),
        f"{variable}_ens_p50": grouped.quantile(0.50),
        f"{variable}_ens_p75": grouped.quantile(0.75),
        f"{variable}_ens_p90": grouped.quantile(0.90),
        f"{variable}_ens_range": grouped.max() - grouped.min(),
    })
    skew_vals = grouped.apply(lambda x: float(skew(x, nan_policy="omit")) if len(x) > 2 else 0.0)
    kurt_vals = grouped.apply(lambda x: float(kurtosis(x, nan_policy="omit", fisher=True)) if len(x) > 2 else 0.0)
    stats[f"{variable}_ens_skew"] = skew_vals.values
    stats[f"{variable}_ens_kurt"] = kurt_vals.values
    return stats.reset_index()


def build_tier4_features(
    ens_df: pd.DataFrame,
    variables: List[str],
    time_col: str = "valid_time",
    member_col: str = "number",
) -> pd.DataFrame:
    """Build all ENS ensemble features (Layer 4) for multiple variables."""
    results = []
    for var in variables:
        if var not in ens_df.columns:
            continue
        stats = compute_ensemble_stats(ens_df, var, time_col, member_col)
        results.append(stats)
    if not results:
        return pd.DataFrame()
    merged = results[0]
    for df in results[1:]:
        merged = merged.merge(df, on=time_col, how="outer")
    return merged


def compute_ensemble_spread_skill(
    ens_std: np.ndarray,
    forecast_error: np.ndarray,
) -> dict:
    """Evaluate spread-skill relationship."""
    abs_error = np.abs(forecast_error)
    correlation = float(np.corrcoef(ens_std, abs_error)[0, 1])
    spread_skill_ratio = float(np.mean(ens_std) / max(np.mean(abs_error), 1e-10))
    return {
        "spread_error_correlation": correlation,
        "spread_skill_ratio": spread_skill_ratio,
        "mean_spread": float(np.mean(ens_std)),
        "mean_abs_error": float(np.mean(abs_error)),
    }


def build_pl_ensemble_stats(
    ens_pl_df: pd.DataFrame,
    levels: list[int],
    variables: list[str],
    time_col: str = "valid_time",
    member_col: str = "number",
) -> pd.DataFrame:
    """Build ensemble statistics for pressure level variables.

    Variables are expected as {var}_{level}hPa columns (post-convert format).
    """
    target_cols = []
    for var in variables:
        for level in levels:
            col = f"{var}_{level}hPa"
            if col in ens_pl_df.columns:
                target_cols.append(col)
            # Also try raw variable names (pre-standardize)
            elif var in ens_pl_df.columns:
                pass  # skip, will be handled by build_tier4_features
    if not target_cols:
        return pd.DataFrame()
    return build_tier4_features(ens_pl_df, target_cols, time_col, member_col)
