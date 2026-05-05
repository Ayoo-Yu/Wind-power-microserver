"""Unified MARS/CDS API client for ECMWF data downloads."""
from __future__ import annotations

import importlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def build_era5_request(
    variable: str,
    year: int,
    month: int,
    area: List[float],
    pressure_level: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a CDS API request dict for ERA5 single-level or pressure-level data."""
    base = {
        "product_type": "reanalysis",
        "variable": variable,
        "year": str(year),
        "month": f"{month:02d}",
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": area,
        "format": "netcdf",
    }
    if pressure_level is not None:
        base["pressure_level"] = str(pressure_level)
    return base


def build_hres_request(
    param: str,
    date: str,
    time: int,
    steps: List[int],
    area: List[float],
    grid: str = "0.1/0.1",
    pressure_level: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a MARS request dict for HRES deterministic forecast."""
    base = {
        "class": "od",
        "stream": "oper",
        "expver": "1",
        "type": "fc",
        "levtype": "pl" if pressure_level else "sfc",
        "param": param,
        "date": date,
        "time": f"{time:02d}",
        "step": steps,
        "area": area,
        "grid": grid,
    }
    if pressure_level is not None:
        base["levelist"] = str(pressure_level)
    return base


def build_ens_request(
    param: str,
    date: str,
    time: int,
    steps: List[int],
    number: List[int],
    area: List[float],
    grid: str = "0.2/0.2",
    pressure_level: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a MARS request dict for ENS ensemble forecast."""
    base = {
        "class": "od",
        "stream": "enfo",
        "expver": "1",
        "type": "pf",
        "levtype": "pl" if pressure_level else "sfc",
        "param": param,
        "date": date,
        "time": f"{time:02d}",
        "step": steps,
        "number": number,
        "area": area,
        "grid": grid,
    }
    if pressure_level is not None:
        base["levelist"] = str(pressure_level)
    return base


class MarsClient:
    """Unified client wrapping CDS API and ECMWF MARS API."""

    def __init__(self, api_type: str = "cds"):
        self.api_type = api_type
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return
        if self.api_type == "cds":
            cdsapi = importlib.import_module("cdsapi")
            self._client = cdsapi.Client()
        elif self.api_type == "mars":
            ecmwfapi = importlib.import_module("ecmwfapi")
            self._client = ecmwfapi.APIConnection(
                api="https://api.ecmwf.int/v1"
            )
        else:
            raise ValueError(f"Unknown api_type: {self.api_type}")

    def retrieve(
        self,
        dataset: str,
        request: Dict[str, Any],
        target: str | Path,
        retries: int = 3,
        delay: int = 60,
    ) -> Path:
        """Download data with retry logic."""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, retries + 1):
            try:
                self._ensure_client()
                logger.info(
                    "Downloading %s -> %s (attempt %d/%d)",
                    dataset, target, attempt, retries,
                )
                if self.api_type == "cds":
                    self._client.retrieve(dataset, request, str(target))
                else:
                    self._client.execute(
                        mars_request=request,
                        target=str(target),
                    )
                logger.info("Downloaded %s (%d bytes)", target, target.stat().st_size)
                return target
            except Exception as e:
                logger.warning("Attempt %d failed: %s", attempt, e)
                if attempt < retries:
                    time.sleep(delay)
                else:
                    raise

    def close(self):
        self._client = None
