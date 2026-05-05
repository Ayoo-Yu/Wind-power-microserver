"""Spatial sampling and interpolation for multi-point wind farm data."""
from __future__ import annotations

from typing import Dict, List

import numpy as np


def compute_grid_bounds(
    center_lat: float,
    center_lon: float,
    buffer_deg: float,
    grid_res: float,
) -> Dict[str, float]:
    """Compute ECMWF-style area bounds [N, W, S, E] around a wind farm center."""
    north = center_lat + buffer_deg
    south = center_lat - buffer_deg
    west = center_lon - buffer_deg
    east = center_lon + buffer_deg
    return {
        "north": round(north, 2),
        "south": round(south, 2),
        "west": round(west, 2),
        "east": round(east, 2),
        "area": [round(north, 2), round(west, 2), round(south, 2), round(east, 2)],
        "grid_res": grid_res,
    }


def farm_area_from_config(farm_config: dict, grid_res: float = 0.25) -> List[float]:
    """Extract [N, W, S, E] area list from a wind farm config dict."""
    bounds = compute_grid_bounds(
        center_lat=farm_config["center_lat"],
        center_lon=farm_config["center_lon"],
        buffer_deg=farm_config["buffer_deg"],
        grid_res=grid_res,
    )
    return bounds["area"]


def compute_distance_weights(
    lats: np.ndarray,
    lons: np.ndarray,
    center_lat: float,
    center_lon: float,
    power: float = 2.0,
) -> np.ndarray:
    """Inverse-distance weights from grid points to a target point."""
    dlat = lats - center_lat
    dlon = (lons - center_lon) * np.cos(np.radians(center_lat))
    dist = np.sqrt(dlat**2 + dlon**2)
    dist = np.maximum(dist, 1e-10)
    inv_dist = 1.0 / dist**power
    return inv_dist / inv_dist.sum()


def interpolate_to_point(
    values: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    center_lat: float,
    center_lon: float,
) -> float:
    """Inverse-distance weighted interpolation of values to a single point."""
    weights = compute_distance_weights(lats, lons, center_lat, center_lon)
    return float(np.dot(weights, values))
