"""Batch convert downloaded NetCDF files to compressed Parquet.

Handles step-chunked downloads: merges _short/_medium/_long chunks
into a single Parquet per date+cycle before converting.

Usage:
    python src/convert.py --all
    python src/convert.py --product hres
    python src/convert.py --product era5 --dry-run
"""
from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import pandas as pd
import xarray as xr

from src.processor import standardize_column_names

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


def find_nc_files(product: str) -> list[Path]:
    """Find all NetCDF files for a product, sorted by name."""
    pattern = RAW_DIR / product / "*.nc"
    return sorted(f for f in pattern.parent.glob(pattern.name)
                  if not f.name.startswith(("test_", "_")))


_CHUNK_RE = re.compile(r"(.+_\d{8}_\d{2}z)(?:_\w+)?\.nc$")


def _group_chunks(nc_files: list[Path]) -> dict[str, list[Path]]:
    """Group chunk files by base name (date+cycle).

    hres_20230106_12z_short.nc + hres_20230106_12z_medium.nc
      → key: "hres_20230106_12z", value: [short, medium, ...]
    """
    groups: dict[str, list[Path]] = {}
    for f in nc_files:
        m = _CHUNK_RE.match(f.name)
        base = m.group(1) if m else f.stem
        groups.setdefault(base, []).append(f)
    return groups


def _extract_if_zip(nc_path: Path) -> list[Path]:
    """If file is a ZIP archive (CDS API format), extract and return NC paths."""
    with open(nc_path, "rb") as f:
        header = f.read(4)
    if header[:2] == b"PK":
        import tempfile
        import zipfile
        extract_dir = nc_path.parent / f"_extracted_{nc_path.stem}"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(nc_path) as zf:
            zf.extractall(extract_dir)
        return sorted(extract_dir.glob("*.nc"))
    return [nc_path]


def nc_to_parquet(
    nc_path: Path,
    output_dir: Path,
    rename_columns: bool = True,
) -> Path | None:
    """Convert a single NetCDF file to Parquet.

    Handles ZIP archives from CDS API (ERA5), surface and pressure level data.
    Surface: one row per (time, latitude, longitude).
    Pressure levels: pivots isobaricInhPa into columns with level suffix.
    """
    stem = nc_path.stem
    out_path = output_dir / f"{stem}.parquet"

    if out_path.exists():
        logger.info("Skip existing: %s", out_path.name)
        return out_path

    # Handle ZIP archives from CDS API
    actual_paths = _extract_if_zip(nc_path)

    try:
        if len(actual_paths) == 1:
            ds = xr.open_dataset(actual_paths[0])
        else:
            # Merge multiple extracted NC files (e.g. instant + accum)
            datasets = []
            for p in actual_paths:
                datasets.append(xr.open_dataset(p))
            ds = xr.merge(datasets, compat="override")

        is_pl = "isobaricInhPa" in ds.dims or "level" in ds.dims

        if is_pl:
            df = _convert_pressure_levels(ds, rename_columns)
        else:
            df = _convert_surface(ds, rename_columns)

        ds.close()

        if df.empty:
            logger.warning("Empty dataframe from %s", nc_path.name)
            return None

        size_mb, nrows = _clean_and_save(df, out_path, output_dir, nc_path.name)
        logger.info("Converted: %s → %s (%.1f MB, %d rows)",
                    nc_path.name, out_path.name, size_mb, nrows)
        return out_path

    except Exception as e:
        logger.error("Failed to convert %s: %s", nc_path.name, e)
        return None


def _merge_chunks_to_parquet(
    chunk_files: list[Path],
    base_name: str,
    output_dir: Path,
    rename_columns: bool = True,
) -> Path | None:
    """Merge multiple step-chunk files into a single Parquet."""
    out_path = output_dir / f"{base_name}.parquet"
    if out_path.exists():
        logger.info("Skip existing: %s", out_path.name)
        return out_path

    datasets = []
    for f in sorted(chunk_files):
        actual = _extract_if_zip(f)
        for p in actual:
            try:
                datasets.append(xr.open_dataset(p))
            except Exception as e:
                logger.warning("Skip chunk %s: %s", f.name, e)

    if not datasets:
        logger.error("No valid chunks for %s", base_name)
        return None

    try:
        merged = xr.merge(datasets, compat="override") if len(datasets) > 1 else datasets[0]
        is_pl = "isobaricInhPa" in merged.dims or "level" in merged.dims
        if is_pl:
            df = _convert_pressure_levels(merged, rename_columns)
        else:
            df = _convert_surface(merged, rename_columns)

        for ds in datasets:
            ds.close()

        if df.empty:
            logger.warning("Empty dataframe from merged chunks %s", base_name)
            return None

        size_mb, nrows = _clean_and_save(df, out_path, output_dir, base_name)
        logger.info("Merged %d chunks → %s (%.1f MB, %d rows)",
                    len(datasets), out_path.name, size_mb, nrows)
        return out_path

    except Exception as e:
        logger.error("Failed to merge chunks for %s: %s", base_name, e)
        return None


def _clean_and_save(df: pd.DataFrame, out_path: Path, output_dir: Path,
                    label: str) -> Path:
    """Drop all-NaN rows, sort, and write Parquet."""
    skip = {"point_lat", "point_lon", "valid_time", "step", "number"}
    data_cols = [c for c in df.columns if c not in skip]
    if data_cols:
        df = df.dropna(subset=data_cols, how="all")
    sort_col = "valid_time" if "valid_time" in df.columns else df.columns[0]
    df = df.sort_values([sort_col]).reset_index(drop=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, engine="pyarrow", compression="snappy")
    size_mb = out_path.stat().st_size / 1e6
    return size_mb, len(df)


def _deduplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicate columns, keeping first occurrence."""
    seen = set()
    keep = []
    for col in df.columns:
        if col not in seen:
            seen.add(col)
            keep.append(col)
    return df.loc[:, keep]


def _convert_surface(ds: xr.Dataset, rename_columns: bool) -> pd.DataFrame:
    """Convert surface-level NetCDF: flat (time, lat, lon) rows."""
    df = ds.to_dataframe().reset_index()
    df = _deduplicate_columns(df)
    if rename_columns:
        df = standardize_column_names(df)
    df = _rename_spatial_cols(df)
    return df


def _convert_pressure_levels(ds: xr.Dataset, rename_columns: bool) -> pd.DataFrame:
    """Convert pressure-level NetCDF: pivot levels into suffixed columns.

    Input dimensions: (time, isobaricInhPa, latitude, longitude)
    Output: one row per (time, lat, lon), columns named {var}_{level}hPa.
    """
    level_dim = "isobaricInhPa" if "isobaricInhPa" in ds.dims else "level"
    levels = ds[level_dim].values

    all_dfs = []
    for level in levels:
        ds_level = ds.sel({level_dim: level}).drop_vars([level_dim], errors="ignore")
        df_level = ds_level.to_dataframe().reset_index()
        if rename_columns:
            df_level = standardize_column_names(df_level)
        # Suffix data columns with level
        skip = {"time", "latitude", "longitude", "valid_time", "step", "number",
                "surface", "isobaricInhPa", "level", "point_lat", "point_lon"}
        for col in list(df_level.columns):
            if col not in skip:
                df_level = df_level.rename(
                    columns={col: f"{col}_{int(level)}hPa"})
        all_dfs.append(df_level)

    if not all_dfs:
        return pd.DataFrame()

    # Merge all levels on spatial/time keys
    result = all_dfs[0]
    for df in all_dfs[1:]:
        merge_cols = [c for c in result.columns if c in df.columns]
        if len(merge_cols) >= 2:
            result = result.merge(df, on=merge_cols, how="outer")

    result = _rename_spatial_cols(result)
    return result


def _rename_spatial_cols(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    if "latitude" in df.columns:
        col_map["latitude"] = "point_lat"
    if "longitude" in df.columns:
        col_map["longitude"] = "point_lon"
    if "time" in df.columns and "valid_time" not in df.columns:
        col_map["time"] = "valid_time"
    return df.rename(columns=col_map)


def convert_product(product: str, dry_run: bool = False) -> list[Path]:
    """Convert all NetCDF files for a given product.

    Groups step-chunked files (e.g. _short/_medium/_long) and merges
    them into a single Parquet output per date+cycle.
    """
    nc_files = find_nc_files(product)
    if not nc_files:
        logger.warning("No NetCDF files found for %s", product)
        return []

    groups = _group_chunks(nc_files)
    logger.info("Found %d files in %d groups for %s", len(nc_files), len(groups), product)

    if dry_run:
        for base, files in sorted(groups.items()):
            chunk_info = f" ({len(files)} chunks)" if len(files) > 1 else ""
            print(f"  {base}.nc{chunk_info}")
        return []

    output_dir = PROCESSED_DIR / product
    results = []
    for base, files in sorted(groups.items()):
        if len(files) == 1:
            result = nc_to_parquet(files[0], output_dir)
        else:
            result = _merge_chunks_to_parquet(files, base, output_dir)
        if result:
            results.append(result)
    return results


def convert_all(dry_run: bool = False) -> dict[str, list[Path]]:
    """Convert all products."""
    results = {}
    for product in ("era5", "era5_pl", "hres", "hres_pl", "ens", "ens_pl"):
        results[product] = convert_product(product, dry_run)
    return results


def main():
    parser = argparse.ArgumentParser(description="Convert NetCDF to Parquet")
    parser.add_argument("--product",
                        choices=["era5", "era5_pl", "hres", "hres_pl", "ens", "ens_pl"],
                        help="Convert specific product only")
    parser.add_argument("--all", action="store_true", dest="convert_all",
                        help="Convert all products")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show files without converting")
    args = parser.parse_args()

    if args.product:
        convert_product(args.product, args.dry_run)
    elif args.convert_all:
        convert_all(args.dry_run)
    else:
        parser.error("Specify --product <name> or --all")


if __name__ == "__main__":
    main()
