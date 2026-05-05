"""Batch download ENS ensemble forecast archive from MARS.

Usage:
    python src/download_ens.py --farm zone1 --start 2020-01-01 --end 2020-01-31
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from src.mars_client import MarsClient, build_ens_request
from src.spatial import farm_area_from_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_configs():
    farms = json.loads((CONFIG_DIR / "wind_farms.json").read_text(encoding="utf-8"))
    variables = json.loads((CONFIG_DIR / "mars_variables.json").read_text(encoding="utf-8"))
    settings = json.loads((CONFIG_DIR / "download_settings.json").read_text(encoding="utf-8"))
    return farms, variables, settings


def download_ens_day(farm_name, farm_cfg, params, date, steps, number, output_dir, grid="0.2/0.2"):
    client = MarsClient(api_type="mars")
    area = farm_area_from_config(farm_cfg, grid_res=0.2)
    for param in params:
        out_file = output_dir / f"ens_{param}_{farm_name}_{date}_00z.grib"
        if out_file.exists():
            logger.info("Skip existing: %s", out_file)
            continue
        request = build_ens_request(param=param, date=date, time=0, steps=steps, number=number, area=area, grid=grid)
        client.retrieve(dataset="mars", request=request, target=out_file)


def main():
    parser = argparse.ArgumentParser(description="Download ENS ensemble data")
    parser.add_argument("--farm", required=True)
    parser.add_argument("--date", help="Single date YYYY-MM-DD")
    parser.add_argument("--start", help="Start date")
    parser.add_argument("--end", help="End date")
    args = parser.parse_args()

    farms, variables, settings = load_configs()
    farm_cfg = farms["wind_farms"][args.farm]

    if args.date:
        dates = [args.date]
    elif args.start and args.end:
        start = datetime.strptime(args.start, "%Y-%m-%d")
        end = datetime.strptime(args.end, "%Y-%m-%d")
        dates = [(start + timedelta(days=d)).strftime("%Y-%m-%d") for d in range((end - start).days + 1)]
    else:
        parser.error("Provide --date or --start/--end")

    ens_params = variables["ens_variables"]["surface"]["core"]
    output_dir = Path(settings["storage"]["raw_dir"]) / "ens" / args.farm
    output_dir.mkdir(parents=True, exist_ok=True)

    for date in dates:
        download_ens_day(args.farm, farm_cfg, ens_params, date,
                         settings["ens"]["steps"], settings["ens"]["number"], output_dir, settings["ens"]["grid"])


if __name__ == "__main__":
    main()
