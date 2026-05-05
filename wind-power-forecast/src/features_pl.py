"""Pressure level feature engineering for wind power forecasting.

Derives physically meaningful features from multi-level atmospheric data:
- Wind shear between pressure levels
- Temperature lapse rate (static stability)
- Geostrophic wind from geopotential gradient
- Thermal wind (vertical wind shear from temperature gradient)
- Vorticity/divergence diagnostics
- Bulk Richardson number
- Potential temperature and equivalent potential temperature
"""
from __future__ import annotations

import numpy as np
import pandas as pd

OMEGA = 7.2921e-5  # Earth angular velocity rad/s
R_DRY = 287.05     # J/(kg·K)
G = 9.80665        # m/s²
CP = 1004.0        # J/(kg·K) specific heat at constant pressure


def compute_potential_temperature(
    temperature_k: np.ndarray, pressure_hpa: np.ndarray,
) -> np.ndarray:
    """Potential temperature (theta) using Poisson equation."""
    return temperature_k * (1000.0 / pressure_hpa) ** (R_DRY / CP)


def compute_equivalent_potential_temperature(
    temperature_k: np.ndarray, pressure_hpa: np.ndarray,
    dewpoint_k: np.ndarray,
) -> np.ndarray:
    """Equivalent potential temperature (theta-e)."""
    td_c = dewpoint_k - 273.15
    e = 6.112 * np.exp(17.67 * td_c / (td_c + 243.5))
    w = 0.622 * e / np.maximum(pressure_hpa - e, 1e-6)
    theta = compute_potential_temperature(temperature_k, pressure_hpa)
    return theta * np.exp((2.675e3 * w) / np.maximum(temperature_k, 1e-6))


def compute_wind_shear_layer(
    u_upper: np.ndarray, v_upper: np.ndarray,
    u_lower: np.ndarray, v_lower: np.ndarray,
    z_upper_m: np.ndarray | float, z_lower_m: np.ndarray | float,
) -> tuple[np.ndarray, np.ndarray]:
    """Wind shear between two layers: returns (shear_magnitude, shear_direction)."""
    du = u_upper - u_lower
    dv = v_upper - v_lower
    dz = np.asarray(z_upper_m - z_lower_m, dtype=float)
    shear_mag = np.sqrt(du**2 + dv**2) / np.maximum(np.abs(dz), 1e-6)
    shear_dir = (270.0 - np.degrees(np.arctan2(dv, du))) % 360.0
    return shear_mag, shear_dir


def compute_lapse_rate(
    t_upper: np.ndarray, t_lower: np.ndarray,
    z_upper_m: np.ndarray | float, z_lower_m: np.ndarray | float,
) -> np.ndarray:
    """Temperature lapse rate (K/km). Negative = temperature decreases with height."""
    dz = np.asarray(z_upper_m - z_lower_m, dtype=float)
    return (t_upper - t_lower) / np.maximum(dz, 1e-6) * 1000.0


def compute_geostrophic_wind(
    z_upper_hPa: np.ndarray, z_lower_hPa: np.ndarray,
    lat: np.ndarray | float, dx_m: float, dy_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Geostrophic wind from geopotential height gradient.

    Uses central difference approximation on grid data.
    z values are geopotential height in metres (from geopotential / g).
    """
    dzdx = (z_upper_hPa - z_lower_hPa) / dx_m
    f = 2.0 * OMEGA * np.sin(np.radians(lat))
    f = np.maximum(np.abs(f), 1e-10) * np.sign(f + 1e-20)
    ug = -dzdx * G / f
    return ug, np.zeros_like(ug)


def compute_bulk_richardson(
    theta_v_surface: np.ndarray, theta_v_level: np.ndarray,
    wind_speed_surface: np.ndarray, wind_speed_level: np.ndarray,
    delta_z: np.ndarray | float,
) -> np.ndarray:
    """Bulk Richardson number for stability classification.

    Ri < 0: unstable (convective)
    0 < Ri < 0.25: mechanically turbulent (windy)
    Ri > 0.25: stable (suppressed mixing)
    Ri > 1.0: very stable (decoupled)
    """
    delta_theta = theta_v_level - theta_v_surface
    delta_v2 = wind_speed_level**2 - wind_speed_surface**2
    return G * delta_theta * np.asarray(delta_z) / (
        np.maximum(theta_v_surface, 1e-6)
        * np.maximum(np.abs(delta_v2), 1e-6)
    )


def compute_thermal_wind(
    t_east: np.ndarray, t_west: np.ndarray,
    z_lower_hPa: float, z_upper_hPa: float,
    lat: np.ndarray | float, dx_m: float,
) -> np.ndarray:
    """Thermal wind component — vertical wind shear from horizontal temperature gradient."""
    f = 2.0 * OMEGA * np.sin(np.radians(lat))
    f = np.maximum(np.abs(f), 1e-10) * np.sign(f + 1e-20)
    dtdx = (t_east - t_west) / dx_m
    dp = z_upper_hPa - z_lower_hPa
    return -R_DRY * dtdx * dp * 100.0 / (f * G)


def classify_stability_richardson(ri: np.ndarray) -> np.ndarray:
    labels = np.full(ri.shape, "neutral", dtype=object)
    labels[ri < 0] = "unstable"
    labels[(ri >= 0) & (ri < 0.25)] = "mechanically_turbulent"
    labels[(ri >= 0.25) & (ri < 1.0)] = "stable"
    labels[ri >= 1.0] = "very_stable"
    return labels


def compute_thickness(
    z_lower: np.ndarray, z_upper: np.ndarray,
) -> np.ndarray:
    """Layer thickness (geopotential height difference) in metres."""
    return z_upper - z_lower


def compute_warm_air_advection(
    u: np.ndarray, v: np.ndarray,
    t_upstream: np.ndarray, t_local: np.ndarray,
    dx_m: float,
) -> np.ndarray:
    """Warm/cold air advection proxy from wind direction and temperature gradient."""
    dt = t_local - t_upstream
    return u * dt / dx_m + v * dt / dx_m


def build_pl_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build all pressure level features from wide-form DataFrame.

    Expects columns named {var}_{level}hPa (output of convert.py pressure level processing).
    Levels used: 1000, 925, 850, 700, 500 hPa.
    """
    out = df.copy()

    # --- Wind shear between levels ---
    for z_upper, z_lower, dz_approx in [
        (850, 1000, 1487), (700, 850, 1563), (700, 1000, 3050),
    ]:
        u_up = f"wind_u_{z_upper}hPa"
        v_up = f"wind_v_{z_upper}hPa"
        u_lo = f"wind_u_{z_lower}hPa"
        v_lo = f"wind_v_{z_lower}hPa"
        if all(c in out.columns for c in [u_up, v_up, u_lo, v_lo]):
            shear_mag, shear_dir = compute_wind_shear_layer(
                out[u_up].to_numpy(), out[v_up].to_numpy(),
                out[u_lo].to_numpy(), out[v_lo].to_numpy(),
                dz_approx, 0,
            )
            out[f"wind_shear_{z_lower}_{z_upper}hPa"] = shear_mag
            out[f"wind_shear_dir_{z_lower}_{z_upper}hPa"] = shear_dir

    # --- Surface-to-1000hPa wind shear (100m vs 1000hPa) ---
    if "wind_speed_100m" in out.columns and "wind_u_1000hPa" in out.columns:
        ws_1000 = np.sqrt(
            out["wind_u_1000hPa"].to_numpy()**2 + out["wind_v_1000hPa"].to_numpy()**2)
        out["wind_ratio_100m_to_1000hPa"] = (
            out["wind_speed_100m"].to_numpy() / np.maximum(ws_1000, 1e-6))

    # --- Temperature lapse rate ---
    for z_upper, z_lower, dz_approx in [
        (850, 1000, 1487), (700, 850, 1563), (500, 700, 2625),
    ]:
        t_up = f"temperature_{z_upper}hPa"
        t_lo = f"temperature_{z_lower}hPa"
        if all(c in out.columns for c in [t_up, t_lo]):
            out[f"lapse_rate_{z_lower}_{z_upper}hPa"] = compute_lapse_rate(
                out[t_up].to_numpy(), out[t_lo].to_numpy(), dz_approx, 0)

    # --- Potential temperature at each level ---
    for level in [1000, 925, 850, 700, 500]:
        t_col = f"temperature_{level}hPa"
        if t_col in out.columns:
            out[f"theta_{level}hPa"] = compute_potential_temperature(
                out[t_col].to_numpy(), level)

    # --- Layer thickness (geopotential height difference) ---
    for z_upper, z_lower in [(850, 1000), (700, 850), (500, 700)]:
        z_up = f"geopotential_{z_upper}hPa"
        z_lo = f"geopotential_{z_lower}hPa"
        if all(c in out.columns for c in [z_up, z_lo]):
            out[f"thickness_{z_lower}_{z_upper}hPa"] = compute_thickness(
                out[z_lo].to_numpy(), out[z_up].to_numpy())

    # --- Bulk Richardson number (surface to 850 hPa) ---
    theta_sfc = out.get("temperature_2m")
    theta_850 = out.get("theta_850hPa")
    ws_sfc = out.get("wind_speed_10m")
    ws_850_col = "wind_u_850hPa"
    if all(v is not None for v in [theta_sfc, theta_850, ws_sfc]):
        if ws_850_col in out.columns:
            ws_850 = np.sqrt(
                out["wind_u_850hPa"].to_numpy()**2 + out["wind_v_850hPa"].to_numpy()**2)
            out["bulk_richardson_sfc_850"] = compute_bulk_richardson(
                theta_sfc.to_numpy(), theta_850.to_numpy(),
                ws_sfc.to_numpy(), ws_850, 1487,
            )
            out["stability_class_richardson"] = classify_stability_richardson(
                out["bulk_richardson_sfc_850"].to_numpy())

    # --- Vorticity diagnostics ---
    for level in [850, 700, 500]:
        vo_col = f"relative_vorticity_{level}hPa"
        if vo_col in out.columns:
            out[f"abs_vorticity_{level}hPa"] = np.abs(out[vo_col].to_numpy())

    # --- Low-level jet indicator ---
    # LLJ: wind speed at 850hPa > wind speed at both 1000hPa and 700hPa
    ws_cols = {}
    for level in [1000, 850, 700]:
        u_col = f"wind_u_{level}hPa"
        v_col = f"wind_v_{level}hPa"
        if all(c in out.columns for c in [u_col, v_col]):
            ws_cols[level] = np.sqrt(out[u_col].to_numpy()**2 + out[v_col].to_numpy()**2)
    if all(l in ws_cols for l in [1000, 850, 700]):
        out["llj_indicator"] = (
            (ws_cols[850] > ws_cols[1000]) & (ws_cols[850] > ws_cols[700])
        ).astype(int)
        out["llj_speed_850hPa"] = ws_cols[850]

    # --- Wind speed at each level ---
    for level in [1000, 925, 850, 700, 500]:
        u_col = f"wind_u_{level}hPa"
        v_col = f"wind_v_{level}hPa"
        if all(c in out.columns for c in [u_col, v_col]):
            out[f"wind_speed_{level}hPa"] = np.sqrt(
                out[u_col].to_numpy()**2 + out[v_col].to_numpy()**2)
            out[f"wind_dir_{level}hPa"] = (
                270.0 - np.degrees(np.arctan2(
                    out[v_col].to_numpy(), out[u_col].to_numpy()))) % 360.0

    return out
