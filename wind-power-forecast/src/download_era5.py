"""Batch download ERA5 reanalysis data via CDS API.

Usage:
    python src/download_era5.py --farm zone1 [--start 2020-01] [--end 2025-12]
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from src.mars_client import MarsClient, build_era5_request
from src.spatial import farm_area_from_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_configs():
    farms = json.loads((CONFIG_DIR / "wind_farms.json").read_text(encoding="utf-8"))
    variables = json.loads((CONFIG_DIR / "mars_variables.json").read_text(encoding="utf-8"))
    settings = json.loads((CONFIG_DIR / "download_settings.json").read_text(encoding="utf-8"))
    return farms, variables, settings


def download_era5_surface(
    farm_name: str,
    farm_cfg: dict,
    variables_list: list[str],
    start: datetime,
    end: datetime,
    output_dir: Path,
    chunk_months: int = 6,
):
    """Download ERA5 surface variables in monthly chunks."""
    client = MarsClient(api_type="cds")
    area = farm_area_from_config(farm_cfg, grid_res=0.25)

    from dateutil.relativedelta import relativedelta
    current = start
    while current <= end:
        chunk_end = min(current + relativedelta(months=chunk_months), end)
        for var in variables_list:
            out_file = output_dir / f"era5_sfc_{var}_{farm_name}_{current.strftime('%Y%m')}-{chunk_end.strftime('%Y%m')}.nc"
            if out_file.exists():
                logger.info("Skip existing: %s", out_file)
                continue
            request = build_era5_request(variable=var, year=current.year, month=current.month, area=area)
            client.retrieve(dataset="reanalysis-era5-single-levels", request=request, target=out_file)
        current = chunk_end + relativedelta(months=1)


def main():
    parser = argparse.ArgumentParser(description="Download ERA5 reanalysis data")
    parser.add_argument("--farm", required=True, help="Wind farm name")
    parser.add_argument("--start", default="2020-01", help="Start month YYYY-MM")
    parser.add_argument("--end", default="2025-12", help="End month YYYY-MM")
    parser.add_argument("--tier", type=int, default=0, help="Variable tier filter (1,2,3 or 0 for all)")
    args = parser.parse_args()

    farms, variables, settings = load_configs()
    farm_cfg = farms["wind_farms"][args.farm]
    start = datetime.strptime(args.start, "%Y-%m")
    end = datetime.strptime(args.end, "%Y-%m")

    tier = args.tier
    all_vars = []
    for tier_name, tier_vars in variables["era5_variables"]["surface"].items():
        if tier == 0 or (tier == 1 and tier_name == "tier1") or \
           (tier == 2 and tier_name in ("tier1", "tier2")) or \
           (tier == 3):
            all_vars.extend(tier_vars)

    output_dir = Path(settings["storage"]["raw_dir"]) / "era5" / args.farm
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading ERA5 for %s: %d variables, %s to %s", args.farm, len(all_vars), args.start, args.end)
    download_era5_surface(args.farm, farm_cfg, all_vars, start, end, output_dir,
                          chunk_months=settings["download"]["chunk_months"])


if __name__ == "__main__":
    main()
