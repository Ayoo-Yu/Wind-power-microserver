"""Bridge between MARS data pipeline and 0427 prediction framework."""
from __future__ import annotations

from typing import Optional

import pandas as pd


def mars_to_0427_format(df: pd.DataFrame) -> pd.DataFrame:
    """Rename feature columns to feature_* convention used in 0427 framework."""
    out = df.copy()
    rename_map = {}
    skip_cols = {"timestamp", "target", "valid_time", "time", "split",
                 "stability_class", "stability_class_richardson",
                 "thermal_advection_type",
                 "point_lat", "point_lon"}
    for col in out.columns:
        if col in skip_cols:
            continue
        if not col.startswith("feature_"):
            rename_map[col] = f"feature_{col}"
    return out.rename(columns=rename_map)


def build_feature_dataset(
    hres_df: pd.DataFrame,
    hres_pl_df: Optional[pd.DataFrame] = None,
    ens_df: Optional[pd.DataFrame] = None,
    ens_pl_df: Optional[pd.DataFrame] = None,
    era5_df: Optional[pd.DataFrame] = None,
    horizon: int = 1,
    time_col: str = "valid_time",
) -> pd.DataFrame:
    """Build final feature dataset from HRES + optional pressure levels + ENS + ERA5."""
    base = hres_df.copy()

    if hres_pl_df is not None and not hres_pl_df.empty:
        pl_cols = [c for c in hres_pl_df.columns if c != time_col]
        base = base.merge(hres_pl_df[[time_col] + pl_cols], on=time_col, how="left")

    if ens_df is not None and not ens_df.empty:
        ens_cols = [c for c in ens_df.columns if c != time_col]
        base = base.merge(ens_df[[time_col] + ens_cols], on=time_col, how="left")

    if ens_pl_df is not None and not ens_pl_df.empty:
        ens_pl_cols = [c for c in ens_pl_df.columns if c != time_col]
        base = base.merge(ens_pl_df[[time_col] + ens_pl_cols], on=time_col, how="left")

    if era5_df is not None and not era5_df.empty:
        era5_indexed = era5_df.set_index(time_col)
        common_cols = [c for c in era5_indexed.columns if "_truth" in c]
        for col in common_cols:
            base_name = col.replace("_truth", "")
            if base_name in base.columns:
                error_name = f"{base_name}_forecast_error"
                base[error_name] = (base[base_name] - era5_indexed[col].reindex(base[time_col]).values)
    base = base.rename(columns={time_col: "timestamp"})
    return mars_to_0427_format(base)
