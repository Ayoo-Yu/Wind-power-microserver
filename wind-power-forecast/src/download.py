"""Chunked, parallel download from ECMWF MARS archive.

Design:
  - Split large requests by step range (short/medium/long chunks)
  - Prioritize by production need (P0=12Z+18Z short, P1=00Z+medium, P2=rest)
  - Parallel workers (default 2) via ThreadPoolExecutor
  - Resume via skip-existing and status tracking

Usage:
    python -m src.download hres --start 2023-01-01 --end 2023-03-31 --all-params
    python -m src.download hres --start 2023-01-01 --end 2023-01-31 --priority P0
    python -m src.download hres-pl --start 2023-01-01 --end 2023-03-31 --workers 3
    python -m src.download era5 --start 2023-01-01 --end 2023-03-31
    python -m src.download ens --start 2023-01-01 --end 2023-03-31 --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

from ecmwfapi import ECMWFService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"
DEFAULT_AREA = [29.3, 97.2, 20.9, 107.2]


def load_configs():
    variables = json.loads((CONFIG_DIR / "mars_variables.json").read_text(encoding="utf-8"))
    settings = json.loads((CONFIG_DIR / "download_settings.json").read_text(encoding="utf-8"))
    return variables, settings


def get_params_for_tier(product: str, tier: int, variables: dict) -> list[str]:
    if product == "era5":
        surface = variables["era5_variables"]["surface"]
    elif product == "hres":
        surface = variables["hres_variables"]["surface"]
    elif product == "ens":
        return variables["ens_variables"]["surface"]["core"]
    else:
        return []
    params = []
    for t in ["tier1", "tier2", "tier3"]:
        if tier == 0 or ["tier1", "tier2", "tier3"].index(t) < tier:
            params.extend(surface.get(t, []))
    return params


# ---------------------------------------------------------------------------
# Step chunk definitions
# ---------------------------------------------------------------------------

def get_chunks_for_cycle(product: str, cycle: int, settings: dict) -> list[dict]:
    """Get step chunks for a specific product and cycle."""
    if product == "hres":
        stream = "scda" if cycle in (6, 18) else "oper"
        chunks_cfg = settings["hres"]["step_chunks"]
        return chunks_cfg[stream]
    elif product == "hres_pl":
        return None  # no chunking for PL
    elif product in ("ens", "ens_pl"):
        return settings["ens"].get("step_chunks", None)
    return None


# ---------------------------------------------------------------------------
# Request builders
# ---------------------------------------------------------------------------

PL_PARAM_MAP = {
    "u": "131", "v": "132", "t": "130", "z": "129",
    "q": "133", "r": "135", "vo": "138", "d": "155", "w": "119",
}


def build_hres_request(params, date, cycle, steps, area, grid="0.1/0.1", all_params=False):
    stream = "scda" if cycle in (6, 18) else "oper"
    return {
        "class": "od", "stream": stream, "type": "fc", "expver": "1",
        "levtype": "sfc",
        "param": "ALL PARAM" if all_params else "/".join(params),
        "date": date, "time": f"{cycle:02d}", "step": steps,
        "area": area, "grid": grid, "format": "netcdf",
    }


def build_hres_pl_request(variables, levels, date, cycle, steps, area, grid="0.1/0.1"):
    stream = "scda" if cycle in (6, 18) else "oper"
    param_ids = [PL_PARAM_MAP[v] for v in variables if v in PL_PARAM_MAP]
    return {
        "class": "od", "stream": stream, "type": "fc", "expver": "1",
        "levtype": "pl", "levelist": levels, "param": "/".join(param_ids),
        "date": date, "time": f"{cycle:02d}", "step": steps,
        "area": area, "grid": grid, "format": "netcdf",
    }


def build_ens_request(params, date, steps, number, area, grid="0.2/0.2"):
    return {
        "class": "od", "stream": "enfo", "type": "pf", "expver": "1",
        "levtype": "sfc", "param": "/".join(params),
        "date": date, "time": "00", "step": steps, "number": number,
        "area": area, "grid": grid, "format": "netcdf",
    }


def build_ens_pl_request(variables, levels, date, steps, number, area, grid="0.2/0.2"):
    param_ids = [PL_PARAM_MAP[v] for v in variables if v in PL_PARAM_MAP]
    return {
        "class": "od", "stream": "enfo", "type": "pf", "expver": "1",
        "levtype": "pl", "levelist": levels, "param": "/".join(param_ids),
        "date": date, "time": "00", "step": steps, "number": number,
        "area": area, "grid": grid, "format": "netcdf",
    }


# ---------------------------------------------------------------------------
# MARS/CDS retrieve with resume + status tracking
# ---------------------------------------------------------------------------

STATUS_FILE = Path(__file__).parent.parent / "data" / "download_status.json"
_status_lock = threading.Lock()


def load_status() -> dict:
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "failed": []}


def save_status(status: dict):
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")


def _mark_status(job_id: str, field: str):
    """Thread-safe status update."""
    with _status_lock:
        status = load_status()
        status.setdefault(field, []).append(job_id)
        save_status(status)


def mars_retrieve(request: dict, target: Path, job_id: str = "",
                  retries: int = 3, delay: int = 300) -> Path | None:
    """Execute a MARS retrieval with retry and resume."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and target.stat().st_size > 10000:
        logger.info("Skip existing: %s (%.1f MB)", target.name, target.stat().st_size / 1e6)
        return target

    status = load_status()
    if job_id and job_id in status.get("completed", []):
        logger.info("Skip completed: %s", job_id)
        return target

    for attempt in range(1, retries + 1):
        try:
            logger.info("MARS -> %s (attempt %d/%d) [%s]",
                        target.name, attempt, retries, job_id)
            server = ECMWFService("mars")
            server.execute(request, str(target))
            size_mb = target.stat().st_size / 1e6
            logger.info("DONE: %s (%.1f MB)", target.name, size_mb)
            if job_id:
                _mark_status(job_id, "completed")
            return target
        except Exception as e:
            logger.warning("FAIL %s attempt %d: %s", target.name, attempt, e)
            if attempt < retries:
                logger.info("Retry in %ds...", delay)
                time.sleep(delay)
            else:
                if job_id:
                    _mark_status(job_id, "failed")
                return None


def cds_retrieve(dataset: str, request: dict, out_file: Path, job_id: str):
    """CDS API retrieve with auto-unzip and retry."""
    import cdsapi
    import zipfile
    out_file.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 4):
        logger.info("CDS -> %s (attempt %d/3) [%s]", out_file.name, attempt, job_id)
        try:
            c = cdsapi.Client(quiet=True)
            c.retrieve(dataset, request, str(out_file))
            with open(out_file, "rb") as f:
                is_zip = f.read(2) == b"PK"
            if is_zip:
                tmp_zip = out_file.with_suffix(".zip")
                out_file.rename(tmp_zip)
                with zipfile.ZipFile(tmp_zip) as zf:
                    nc_names = [n for n in zf.namelist() if n.endswith(".nc")]
                    if nc_names:
                        zf.extractall(out_file.parent)
                tmp_zip.unlink()
                logger.info("Extracted ZIP -> %d NC files [%s]", len(nc_names), job_id)
            else:
                logger.info("DONE: %s (%.1f MB) [%s]",
                            out_file.name, out_file.stat().st_size / 1e6, job_id)
            if job_id:
                _mark_status(job_id, "completed")
            return out_file
        except Exception as e:
            logger.warning("CDS FAIL %s attempt %d: %s", out_file.name, attempt, e)
            if attempt < 3:
                time.sleep(300)
    logger.error("CDS FAILED after 3 attempts: %s", job_id)
    if job_id:
        _mark_status(job_id, "failed")
    return None


# ---------------------------------------------------------------------------
# Download job — single request descriptor
# ---------------------------------------------------------------------------

class DownloadJob:
    __slots__ = ("product", "date", "cycle", "chunk_name", "priority",
                 "request", "target", "job_id")

    def __init__(self, product, date, cycle, chunk_name, priority, request, target, job_id):
        self.product = product
        self.date = date
        self.cycle = cycle
        self.chunk_name = chunk_name
        self.priority = priority
        self.request = request
        self.target = target
        self.job_id = job_id

    def __lt__(self, other):
        return (self.priority, self.date, self.cycle) < (other.priority, other.date, other.cycle)


def _run_job(job: DownloadJob, retries: int = 3) -> DownloadJob:
    """Execute a single download job."""
    if "cds_dataset" in job.request:
        cds_retrieve(
            job.request["cds_dataset"], job.request, job.target, job.job_id)
    else:
        mars_retrieve(job.request, job.target, job.job_id, retries=retries)
    return job


# ---------------------------------------------------------------------------
# Job builders — create all DownloadJob objects for a product+date range
# ---------------------------------------------------------------------------

def build_hres_jobs(start, end, area, tier, output_dir, all_params=False,
                    priority_filter=None, settings=None, variables=None):
    if settings is None or variables is None:
        variables, settings = load_configs()
    params = get_params_for_tier("hres", tier, variables)
    if not params and not all_params:
        return []

    p0_cycles = settings["hres"].get("priority_cycles", {}).get("P0", ["12", "18"])
    cycles = settings["hres"]["cycles"]
    jobs = []
    d = start
    while d <= end:
        date_str = d.strftime("%Y-%m-%d")
        date_compact = d.strftime("%Y%m%d")
        for cycle_str in cycles:
            cycle = int(cycle_str)
            chunks = get_chunks_for_cycle("hres", cycle, settings)
            if chunks:
                for chunk in chunks:
                    # 12Z/18Z keep chunk priority; 00Z/06Z bumped by 1
                    prio = chunk["priority"] + (0 if cycle_str in p0_cycles else 1)
                    if priority_filter is not None and prio != priority_filter:
                        continue
                    suffix = f"_{chunk['name']}" if len(chunks) > 1 else ""
                    target = output_dir / "hres" / f"hres_{date_compact}_{cycle_str}z{suffix}.nc"
                    job_id = f"hres_{date_compact}_{cycle_str}z{suffix}"
                    req = build_hres_request(params, date_str, cycle, chunk["steps"],
                                            area, all_params=all_params)
                    jobs.append(DownloadJob("hres", date_str, cycle, chunk["name"],
                                           prio, req, target, job_id))
            else:
                target = output_dir / "hres" / f"hres_{date_compact}_{cycle_str}z.nc"
                job_id = f"hres_{date_compact}_{cycle_str}z"
                req = build_hres_request(params, date_str, cycle,
                                        settings["hres"]["step_chunks"]["oper"][0]["steps"],
                                        area, all_params=all_params)
                jobs.append(DownloadJob("hres", date_str, cycle, "", 0, req, target, job_id))
        d += timedelta(days=1)
    return jobs


def build_hres_pl_jobs(start, end, area, output_dir,
                       priority_filter=None, settings=None, variables=None):
    if settings is None or variables is None:
        variables, settings = load_configs()
    pl_config = variables["hres_variables"]["pressure_levels"]
    pl_vars, pl_levels = pl_config["variables"], pl_config["levels_hpa"]

    cycles = settings["hres"]["cycles"]
    jobs = []
    d = start
    while d <= end:
        date_str = d.strftime("%Y-%m-%d")
        date_compact = d.strftime("%Y%m%d")
        for cycle_str in cycles:
            cycle = int(cycle_str)
            chunks = get_chunks_for_cycle("hres_pl", cycle, settings)
            if chunks is None:
                # PL not chunked — use full step range
                stream_key = "scda" if cycle in (6, 18) else "oper"
                full_steps = settings["hres"]["step_chunks"][stream_key]
                all_steps = []
                for c in full_steps:
                    all_steps.extend(c["steps"])
                target = output_dir / "hres_pl" / f"hres_pl_{date_compact}_{cycle_str}z.nc"
                job_id = f"hres_pl_{date_compact}_{cycle_str}z"
                req = build_hres_pl_request(pl_vars, pl_levels, date_str, cycle,
                                            all_steps, area)
                prio = 0 if cycle in (12, 18) else 1
                if priority_filter is not None and prio != priority_filter:
                    continue
                jobs.append(DownloadJob("hres_pl", date_str, cycle, "",
                                       prio, req, target, job_id))
        d += timedelta(days=1)
    return jobs


def build_ens_jobs(start, end, area, output_dir,
                   settings=None, variables=None):
    if settings is None or variables is None:
        variables, settings = load_configs()
    params = get_params_for_tier("ens", 0, variables)
    number = settings["ens"]["number"]
    chunks = settings["ens"].get("step_chunks", None)

    jobs = []
    d = start
    while d <= end:
        date_str = d.strftime("%Y-%m-%d")
        date_compact = d.strftime("%Y%m%d")
        if chunks:
            for chunk in chunks:
                suffix = f"_{chunk['name']}" if isinstance(chunks, list) and len(chunks) > 1 else ""
                target = output_dir / "ens" / f"ens_{date_compact}_00z{suffix}.nc"
                job_id = f"ens_{date_compact}_00z{suffix}"
                req = build_ens_request(params, date_str, chunk["steps"], number, area)
                jobs.append(DownloadJob("ens", date_str, 0, chunk.get("name", ""),
                                       chunk.get("priority", 1), req, target, job_id))
        else:
            target = output_dir / "ens" / f"ens_{date_compact}_00z.nc"
            job_id = f"ens_{date_compact}_00z"
            req = build_ens_request(params, date_str,
                                    settings["ens"]["step_chunks"][0]["steps"], number, area)
            jobs.append(DownloadJob("ens", date_str, 0, "", 1, req, target, job_id))
        d += timedelta(days=1)
    return jobs


def build_ens_pl_jobs(start, end, area, output_dir,
                      settings=None, variables=None):
    if settings is None or variables is None:
        variables, settings = load_configs()
    pl_config = variables["ens_variables"]["pressure_levels"]
    pl_vars, pl_levels = pl_config["variables"], pl_config["levels_hpa"]
    number = settings["ens"]["number"]
    chunks = settings["ens"].get("step_chunks", None)

    jobs = []
    d = start
    while d <= end:
        date_str = d.strftime("%Y-%m-%d")
        date_compact = d.strftime("%Y%m%d")
        if chunks:
            for chunk in chunks:
                suffix = f"_{chunk['name']}" if isinstance(chunks, list) and len(chunks) > 1 else ""
                target = output_dir / "ens_pl" / f"ens_pl_{date_compact}_00z{suffix}.nc"
                job_id = f"ens_pl_{date_compact}_00z{suffix}"
                req = build_ens_pl_request(pl_vars, pl_levels, date_str,
                                           chunk["steps"], number, area)
                jobs.append(DownloadJob("ens_pl", date_str, 0, chunk.get("name", ""),
                                       chunk.get("priority", 2), req, target, job_id))
        d += timedelta(days=1)
    return jobs


def build_era5_jobs(start, end, area, tier, output_dir, all_params=False, variables=None):
    if variables is None:
        variables, _ = load_configs()
    params = get_params_for_tier("era5", tier, variables)

    mars_to_cds = {
        "10u": "10m_u_component_of_wind", "10v": "10m_v_component_of_wind",
        "100u": "100m_u_component_of_wind", "100v": "100m_v_component_of_wind",
        "2t": "2m_temperature", "2d": "2m_dewpoint_temperature",
        "blh": "boundary_layer_height", "sshf": "surface_sensible_heat_flux",
        "slhf": "surface_latent_heat_flux", "zust": "friction_velocity",
        "i10fg": "instantaneous_10m_wind_gust", "tcc": "total_cloud_cover",
        "lcc": "low_cloud_cover", "mcc": "medium_cloud_cover",
        "hcc": "high_cloud_cover", "msl": "mean_sea_level_pressure",
        "sp": "surface_pressure", "tp": "total_precipitation",
        "tcwv": "total_column_water_vapour", "cape": "convective_available_potential_energy",
        "fsr": "forecast_surface_roughness", "168": "total_precipitation",
        "sd": "snow_depth", "ssrd": "surface_solar_radiation_downwards",
    }
    cds_vars = list(dict.fromkeys(mars_to_cds[p] for p in params if p in mars_to_cds))
    if not cds_vars:
        return []

    jobs = []
    d = start
    while d <= end:
        date_compact = d.strftime("%Y%m%d")
        out_file = output_dir / "era5" / f"era5_sfc_all_{date_compact}.nc"
        job_id = f"era5_sfc_{date_compact}"
        request = {
            "cds_dataset": "reanalysis-era5-single-levels",
            "product_type": "reanalysis", "variable": cds_vars,
            "year": d.strftime("%Y"), "month": d.strftime("%m"), "day": d.strftime("%d"),
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": area, "format": "netcdf",
        }
        jobs.append(DownloadJob("era5", d.strftime("%Y-%m-%d"), 0, "", 0,
                                request, out_file, job_id))
        d += timedelta(days=1)
    return jobs


def build_era5_pl_jobs(start, end, area, output_dir, variables=None):
    if variables is None:
        variables, _ = load_configs()
    pl_config = variables["era5_variables"]["pressure_levels"]
    pl_vars, pl_levels = pl_config["variables"], pl_config["levels_hpa"]
    cds_map = {
        "u": "u_component_of_wind", "v": "v_component_of_wind",
        "t": "temperature", "z": "geopotential",
        "q": "specific_humidity", "r": "relative_humidity",
    }
    cds_vars = [cds_map[v] for v in pl_vars if v in cds_map]

    jobs = []
    d = start
    while d <= end:
        date_compact = d.strftime("%Y%m%d")
        out_file = output_dir / "era5_pl" / f"era5_pl_{date_compact}.nc"
        job_id = f"era5_pl_{date_compact}"
        request = {
            "cds_dataset": "reanalysis-era5-pressure-levels",
            "product_type": "reanalysis", "variable": cds_vars,
            "pressure_level": pl_levels,
            "year": d.strftime("%Y"), "month": d.strftime("%m"), "day": d.strftime("%d"),
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": area, "format": "netcdf",
        }
        jobs.append(DownloadJob("era5_pl", d.strftime("%Y-%m-%d"), 0, "", 1,
                                request, out_file, job_id))
        d += timedelta(days=1)
    return jobs


# ---------------------------------------------------------------------------
# Parallel executor
# ---------------------------------------------------------------------------

def run_jobs(jobs: list[DownloadJob], workers: int = 2, dry_run: bool = False):
    """Execute download jobs in priority order with parallel workers."""
    jobs.sort()
    total = len(jobs)
    if total == 0:
        logger.info("No jobs to run")
        return

    logger.info("=== %d jobs, %d workers, priority order ===", total, workers)

    if dry_run:
        for i, j in enumerate(jobs):
            chunk = f" chunk={j.chunk_name}" if j.chunk_name else ""
            print(f"  [{i+1}/{total}] P{j.priority} {j.product} {j.date} {j.cycle:02d}Z{chunk}"
                  f" -> {j.target.name}")
        return

    completed = 0
    failed = 0
    retries = 3

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for job in jobs:
            # Check skip before submitting
            if job.target.exists() and job.target.stat().st_size > 10000:
                logger.info("Skip existing: %s", job.target.name)
                completed += 1
                continue
            status = load_status()
            if job.job_id in status.get("completed", []):
                logger.info("Skip completed: %s", job.job_id)
                completed += 1
                continue
            fut = pool.submit(_run_job, job, retries)
            futures[fut] = job

        for fut in as_completed(futures):
            job = futures[fut]
            try:
                result = fut.result()
                completed += 1
                logger.info("Progress: %d/%d completed, %d failed",
                            completed, total, failed)
            except Exception as e:
                failed += 1
                logger.error("FAILED: %s -> %s", job.job_id, e)

    logger.info("=== Done: %d completed, %d failed out of %d ===",
                completed, failed, total)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Download ECMWF data (chunked, parallel, priority-scheduled)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.download hres     --start 2023-01-01 --end 2023-03-31 --all-params
  python -m src.download hres     --start 2023-01-01 --end 2023-01-31 --priority 0
  python -m src.download hres-pl  --start 2023-01-01 --end 2023-03-31 --workers 3
  python -m src.download era5     --start 2023-01-01 --end 2023-03-31
  python -m src.download ens      --start 2023-01-01 --end 2023-01-31 --dry-run
        """,
    )
    parser.add_argument("product", choices=[
        "era5", "era5-pl", "hres", "hres-pl", "ens", "ens-pl", "all",
    ])
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--area", type=float, nargs=4, default=None)
    parser.add_argument("--tier", type=int, default=0)
    parser.add_argument("--output", default="D:/mars/data/raw")
    parser.add_argument("--workers", type=int, default=None,
                        help="Parallel workers (default: from config or 2)")
    parser.add_argument("--priority", type=int, default=None,
                        help="Only run jobs with this priority (0=P0, 1=P1, 2=P2)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all-params", action="store_true")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")
    area = args.area or DEFAULT_AREA
    output_dir = Path(args.output)
    variables, settings = load_configs()
    workers = args.workers or settings.get("download", {}).get("workers", 2)

    all_jobs = []

    if args.product in ("hres", "all"):
        jobs = build_hres_jobs(start, end, area, args.tier, output_dir,
                               all_params=args.all_params,
                               priority_filter=args.priority,
                               settings=settings, variables=variables)
        all_jobs.extend(jobs)
        logger.info("HRES: %d jobs", len(jobs))

    if args.product in ("hres-pl", "all"):
        jobs = build_hres_pl_jobs(start, end, area, output_dir,
                                  priority_filter=args.priority,
                                  settings=settings, variables=variables)
        all_jobs.extend(jobs)
        logger.info("HRES PL: %d jobs", len(jobs))

    if args.product in ("era5", "all"):
        jobs = build_era5_jobs(start, end, area, args.tier, output_dir,
                               all_params=args.all_params, variables=variables)
        all_jobs.extend(jobs)
        logger.info("ERA5: %d jobs", len(jobs))

    if args.product in ("era5-pl", "all"):
        jobs = build_era5_pl_jobs(start, end, area, output_dir, variables=variables)
        all_jobs.extend(jobs)
        logger.info("ERA5 PL: %d jobs", len(jobs))

    if args.product in ("ens", "all"):
        jobs = build_ens_jobs(start, end, area, output_dir,
                              settings=settings, variables=variables)
        all_jobs.extend(jobs)
        logger.info("ENS: %d jobs", len(jobs))

    if args.product in ("ens-pl", "all"):
        jobs = build_ens_pl_jobs(start, end, area, output_dir,
                                 settings=settings, variables=variables)
        all_jobs.extend(jobs)
        logger.info("ENS PL: %d jobs", len(jobs))

    run_jobs(all_jobs, workers=workers, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
