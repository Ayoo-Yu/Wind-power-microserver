"""End-to-end pipeline orchestrator.

Download → Convert → Spatial Features → Farm Aggregation →
Surface Features → Wind Power → PL Features → Stability →
Temporal → Weather Risk → ENS Stats → Cross-Source → Validation → Save.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.convert import convert_product, find_nc_files
from src.features import build_all_features
from src.features_cross import build_cross_source_features
from src.features_pl import build_pl_features
from src.features_spatial import build_spatial_features
from src.features_stability import build_stability_features
from src.features_temporal import build_temporal_features
from src.features_weather_risk import build_weather_risk_features
from src.features_weather_regime import build_weather_regime_features
from src.features_wind_power import build_wind_power_features
from src.processor import aggregate_to_farm_level, standardize_column_names
from src.validation import generate_quality_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_config() -> dict:
    variables = json.loads((CONFIG_DIR / "mars_variables.json").read_text())
    settings = json.loads((CONFIG_DIR / "download_settings.json").read_text())
    farms = json.loads((CONFIG_DIR / "wind_farms.json").read_text())
    return {"variables": variables, "settings": settings, "farms": farms}


def run_convert_stage(products: list[str] | None = None) -> dict[str, list]:
    products = products or ["hres", "hres_pl", "era5", "era5_pl", "ens", "ens_pl"]
    results = {}
    for product in products:
        files = find_nc_files(product)
        if files:
            logger.info("Converting %d files for %s", len(files), product)
            from src.convert import nc_to_parquet
            out_dir = Path(__file__).parent.parent / "data" / "processed" / product
            converted = [nc_to_parquet(f, out_dir) for f in files]
            results[product] = [r for r in converted if r is not None]
        else:
            logger.info("No files to convert for %s", product)
            results[product] = []
    return results


def run_feature_stage(
    farm_name: str,
    config: dict,
    features_dir: Path | None = None,
) -> pd.DataFrame | None:
    """Run full feature engineering pipeline for one wind farm."""
    farms = config["farms"]
    if "wind_farms" in farms:
        farms = farms["wind_farms"]
    farm_config = farms.get(farm_name)
    if not farm_config:
        logger.error("Farm '%s' not found in config", farm_name)
        return None

    center_lat = farm_config["center_lat"]
    center_lon = farm_config["center_lon"]
    features_dir = features_dir or Path(__file__).parent.parent / "data" / "features"
    features_dir.mkdir(parents=True, exist_ok=True)
    hub_height = farm_config.get("hub_height_m") or 100.0

    # Load processed parquet files
    processed_dir = Path(__file__).parent.parent / "data" / "processed"

    # --- HRES Surface ---
    hres_files = sorted(f for f in processed_dir.glob("hres/*.parquet")
                        if not f.name.startswith("test_"))
    if not hres_files:
        logger.warning("No HRES surface parquet files found")
        return None
    logger.info("Loading %d HRES surface files", len(hres_files))
    hres_df = pd.concat([pd.read_parquet(f) for f in hres_files], ignore_index=True)
    hres_df = standardize_column_names(hres_df)

    # Deduplicate raw multi-point data (keep last cycle per time)
    hres_df = hres_df.sort_values("valid_time").drop_duplicates(
        subset=["valid_time", "point_lat", "point_lon"], keep="last")

    # Spatial features on raw multi-point data, then aggregate
    hres_spatial = build_spatial_features(hres_df)
    hres_df = aggregate_to_farm_level(hres_df, center_lat, center_lon)
    hres_df = build_all_features(hres_df)

    # Merge spatial features
    if not hres_spatial.empty and "valid_time" in hres_df.columns:
        hres_df = hres_df.merge(hres_spatial, on="valid_time", how="left")

    # --- Wind Power Features ---
    hres_df = build_wind_power_features(hres_df, hub_height=hub_height)

    # --- HRES Pressure Levels ---
    pl_files = sorted(f for f in processed_dir.glob("hres_pl/*.parquet")
                      if not f.name.startswith("test_"))
    if pl_files:
        logger.info("Loading %d HRES PL files", len(pl_files))
        pl_df = pd.concat([pd.read_parquet(f) for f in pl_files], ignore_index=True)
        pl_df = standardize_column_names(pl_df)
        pl_df = aggregate_to_farm_level(pl_df, center_lat, center_lon)
        pl_features = build_pl_features(pl_df)
        pl_features = build_stability_features(pl_features)
        # Merge PL features into HRES
        if "valid_time" in hres_df.columns and "valid_time" in pl_features.columns:
            pl_merge_cols = [c for c in pl_features.columns if c != "valid_time"]
            hres_df = hres_df.merge(
                pl_features[["valid_time"] + pl_merge_cols],
                on="valid_time", how="left")

    # --- Weather Regime Classification (needs PL geopotential) ---
    hres_df = build_weather_regime_features(hres_df)

    # --- Temporal Features ---
    hres_df = build_temporal_features(hres_df)

    # --- Weather Risk Features ---
    hres_df = build_weather_risk_features(hres_df)

    # --- ERA5 ---
    era5_files = sorted(f for f in processed_dir.glob("era5/*.parquet")
                        if not f.name.startswith("test_"))
    era5_df = None
    if era5_files:
        logger.info("Loading %d ERA5 files", len(era5_files))
        era5_df = pd.concat([pd.read_parquet(f) for f in era5_files], ignore_index=True)
        era5_df = standardize_column_names(era5_df)
        era5_df = aggregate_to_farm_level(era5_df, center_lat, center_lon)
        era5_df = build_all_features(era5_df)

    # --- ENS ---
    ens_files = sorted(f for f in processed_dir.glob("ens/*.parquet")
                       if not f.name.startswith("test_"))
    ens_stats_df = None
    if ens_files:
        logger.info("Loading %d ENS files", len(ens_files))
        from src.ens_stats import build_tier4_features
        ens_df = pd.concat([pd.read_parquet(f) for f in ens_files], ignore_index=True)
        ens_df = standardize_column_names(ens_df)
        ens_vars = [c for c in ens_df.columns
                    if c not in {"valid_time", "point_lat", "point_lon", "step", "number"}]
        ens_stats_df = build_tier4_features(ens_df, ens_vars)

    # --- ENS PL Stats ---
    ens_pl_files = sorted(f for f in processed_dir.glob("ens_pl/*.parquet")
                          if not f.name.startswith("test_"))
    ens_pl_stats_df = None
    if ens_pl_files:
        logger.info("Loading %d ENS PL files", len(ens_pl_files))
        from src.ens_stats import build_pl_ensemble_stats
        ens_pl_df = pd.concat([pd.read_parquet(f) for f in ens_pl_files], ignore_index=True)
        ens_pl_df = standardize_column_names(ens_pl_df)
        ens_pl_levels = [1000, 925, 850, 700, 500]
        ens_pl_vars = ["wind_u", "wind_v", "temperature", "geopotential",
                       "relative_humidity"]
        ens_pl_stats_df = build_pl_ensemble_stats(
            ens_pl_df, ens_pl_levels, ens_pl_vars)
        # Merge PL ensemble stats into HRES if both exist
        if ens_pl_stats_df is not None and not ens_pl_stats_df.empty:
            if "valid_time" in hres_df.columns and "valid_time" in ens_pl_stats_df.columns:
                pl_ens_cols = [c for c in ens_pl_stats_df.columns if c != "valid_time"]
                hres_df = hres_df.merge(
                    ens_pl_stats_df[["valid_time"] + pl_ens_cols],
                    on="valid_time", how="left")

    # --- Cross-Source Features ---
    hres_df = build_cross_source_features(hres_df, era5_df, ens_stats_df)

    # --- Validation ---
    report = generate_quality_report(hres_df, f"hres_{farm_name}")
    logger.info(report.summary())

    # --- Cleanup duplicate-mapped columns ---
    dup_cols = [c for c in hres_df.columns if c.startswith("_dup_")]
    if dup_cols:
        hres_df = hres_df.drop(columns=dup_cols)

    # --- Save ---
    out_path = features_dir / farm_name / f"features_{farm_name}.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    hres_df.to_parquet(out_path, engine="pyarrow", compression="snappy")
    logger.info("Saved features: %s (%d rows, %d columns)",
                out_path, len(hres_df), len(hres_df.columns))

    return hres_df


def main():
    parser = argparse.ArgumentParser(description="MARS Data Pipeline")
    parser.add_argument("--farm", required=True, help="Wind farm name from config")
    parser.add_argument("--start", help="Start date YYYY-MM-DD (for download)")
    parser.add_argument("--end", help="End date YYYY-MM-DD (for download)")
    parser.add_argument("--stage", choices=["convert", "features", "all"],
                        default="all", help="Pipeline stage to run")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config()

    if args.stage in ("all",) and args.start and args.end:
        logger.info("=== Download Stage ===")
        logger.info("Use download_q1.bat for downloads")

    if args.stage in ("all", "convert"):
        logger.info("=== Convert Stage ===")
        run_convert_stage()

    if args.stage in ("all", "features"):
        logger.info("=== Feature Engineering Stage ===")
        result = run_feature_stage(args.farm, config)
        if result is not None:
            logger.info("Pipeline complete: %d rows, %d columns",
                        len(result), len(result.columns))


if __name__ == "__main__":
    main()
