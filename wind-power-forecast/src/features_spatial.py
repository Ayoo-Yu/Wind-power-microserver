"""Spatial gradient features from multi-point grid data.

Computes geopotential gradient → geostrophic wind, temperature gradient,
pressure tendency, and spatial variance before farm-level aggregation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

OMEGA = 7.2921e-5
G = 9.80665
R_EARTH = 6371000.0


def compute_dx_dy(lats: np.ndarray, lons: np.ndarray) -> tuple[float, float]:
    """Approximate grid spacing in metres at mean latitude."""
    mean_lat = np.mean(lats)
    lat_rad = np.radians(mean_lat)
    if len(np.unique(lats)) <= 1 and len(np.unique(lons)) <= 1:
        return 1.0, 1.0
    dlat = np.median(np.diff(np.sort(np.unique(lats)))) if len(np.unique(lats)) > 1 else 0.1
    dlon = np.median(np.diff(np.sort(np.unique(lons)))) if len(np.unique(lons)) > 1 else 0.1
    dx = dlon * np.pi / 180.0 * R_EARTH * np.cos(lat_rad)
    dy = dlat * np.pi / 180.0 * R_EARTH
    return max(dx, 1.0), max(dy, 1.0)


def compute_geopotential_gradient(
    gph: np.ndarray, lats: np.ndarray, lons: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Central-difference gradient of geopotential height field.

    Returns (dz/dx, dz/dy) arrays same shape as input.
    """
    dx, dy = compute_dx_dy(lats, lons)
    # Reshape to 2D if needed (lat × lon grid)
    n = len(lats)
    dzdx = np.zeros(n)
    dzdy = np.zeros(n)
    for i in range(n):
        east_mask = (lons > lons[i]) & (np.abs(lats - lats[i]) < 0.01)
        west_mask = (lons < lons[i]) & (np.abs(lats - lats[i]) < 0.01)
        north_mask = (lats > lats[i]) & (np.abs(lons - lons[i]) < 0.01)
        south_mask = (lats < lats[i]) & (np.abs(lons - lons[i]) < 0.01)
        if east_mask.any() and west_mask.any():
            dzdx[i] = (gph[east_mask].mean() - gph[west_mask].mean()) / (2 * dx)
        elif east_mask.any():
            dzdx[i] = (gph[east_mask].mean() - gph[i]) / dx
        elif west_mask.any():
            dzdx[i] = (gph[i] - gph[west_mask].mean()) / dx
        if north_mask.any() and south_mask.any():
            dzdy[i] = (gph[north_mask].mean() - gph[south_mask].mean()) / (2 * dy)
        elif north_mask.any():
            dzdy[i] = (gph[north_mask].mean() - gph[i]) / dy
        elif south_mask.any():
            dzdy[i] = (gph[i] - gph[south_mask].mean()) / dy
    return dzdx, dzdy


def compute_geostrophic_wind(
    dzdx: np.ndarray, dzdy: np.ndarray, lat: np.ndarray | float,
) -> tuple[np.ndarray, np.ndarray]:
    """Geostrophic wind from geopotential height gradient.

    ug = -(g/f) * dz/dy
    vg = (g/f) * dz/dx
    """
    f = 2.0 * OMEGA * np.sin(np.radians(lat))
    f = np.where(np.abs(f) < 1e-10, 1e-10 * np.sign(f + 1e-20), f)
    ug = -(G / f) * dzdy
    vg = (G / f) * dzdx
    return ug, vg


def compute_pressure_tendency(
    msl: np.ndarray, dt_hours: float = 1.0,
) -> np.ndarray:
    """Pressure change rate (Pa/hour). Needs time-sequential input."""
    tendency = np.zeros_like(msl)
    if len(msl) > 1:
        tendency[1:] = np.diff(msl) / dt_hours
        tendency[0] = tendency[1]
    return tendency


def compute_spatial_variance(values: np.ndarray) -> float:
    """Spatial variance across grid points."""
    return float(np.var(values))


def build_spatial_features(
    df: pd.DataFrame,
    lat_col: str = "point_lat",
    lon_col: str = "point_lon",
    time_col: str = "valid_time",
) -> pd.DataFrame:
    """Compute spatial gradient features for each timestep.

    Operates on pre-aggregation multi-point data. Returns farm-level
    features (one row per timestep).
    """
    if time_col not in df.columns:
        return pd.DataFrame()
    if lat_col not in df.columns or lon_col not in df.columns:
        return pd.DataFrame()

    results = []
    for t, group in df.groupby(time_col):
        row = {time_col: t}
        lats = group[lat_col].to_numpy()
        lons = group[lon_col].to_numpy()

        for level in [850, 700, 500]:
            gph_col = f"geopotential_{level}hPa"
            if gph_col in group.columns:
                gph = group[gph_col].to_numpy()
                dzdx, dzdy = compute_geopotential_gradient(gph, lats, lons)
                ug, vg = compute_geostrophic_wind(dzdx, dzdy, np.mean(lats))
                row[f"geostrophic_u_{level}hPa"] = float(np.mean(ug))
                row[f"geostrophic_v_{level}hPa"] = float(np.mean(vg))
                row[f"geostrophic_speed_{level}hPa"] = float(
                    np.sqrt(np.mean(ug)**2 + np.mean(vg)**2))

            # Spatial variance of wind speed
            ws_col = f"wind_speed_{level}hPa"
            if ws_col in group.columns:
                row[f"wind_speed_{level}hPa_spatial_var"] = compute_spatial_variance(
                    group[ws_col].to_numpy())

        # Spatial variance of surface variables
        for var in ["wind_speed_100m", "temperature_2m", "surface_pressure"]:
            if var in group.columns:
                row[f"{var}_spatial_var"] = compute_spatial_variance(
                    group[var].to_numpy())

        results.append(row)

    return pd.DataFrame(results)
