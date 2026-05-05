"""Wind power specific features.

Computes features directly relevant to wind turbine power output:
- Wind power density (theoretical extractable energy)
- Vertical wind profile extrapolation (power law to hub height)
- Wind direction sector encoding (12-sector + polar embedding)
- Power curve proxy (simplified cubic curve)
- Interaction features (speed × density, shear × stability)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_wind_power_density(
    wind_speed: np.ndarray, air_density: np.ndarray,
) -> np.ndarray:
    """Theoretical wind power density: 0.5 * rho * v^3 (W/m^2)."""
    return 0.5 * air_density * wind_speed ** 3


def compute_power_law_extrapolation(
    wind_speed_ref: np.ndarray,
    z_ref: float,
    z_target: float,
    shear_alpha: np.ndarray | float = 0.14,
) -> np.ndarray:
    """Extrapolate wind speed from z_ref to z_target using power law.

    v(z) = v(z_ref) * (z / z_ref)^alpha
    Default alpha=0.14 is typical for neutral stability over flat terrain.
    """
    return wind_speed_ref * (z_target / z_ref) ** shear_alpha


def compute_wind_direction_sectors(
    wind_dir: np.ndarray, n_sectors: int = 12,
) -> np.ndarray:
    """Classify wind direction into n_sectors sectors (0-indexed).

    12 sectors: N=0, NNE=1, ..., NNW=11
    """
    return (np.round(wind_dir / (360.0 / n_sectors)) % n_sectors).astype(int)


def compute_wind_dir_polar(
    wind_dir_deg: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Sin/cos polar embedding of wind direction for ML models."""
    rad = np.radians(wind_dir_deg)
    return np.sin(rad), np.cos(rad)


def compute_directional_change(
    wind_dir: np.ndarray,
) -> np.ndarray:
    """Signed direction change in degrees, handling wrap-around.

    Positive = clockwise rotation, negative = counter-clockwise.
    """
    diff = np.diff(wind_dir)
    # Wrap to [-180, 180]
    diff = (diff + 180.0) % 360.0 - 180.0
    result = np.empty_like(wind_dir)
    result[0] = diff[0]
    result[1:] = diff
    return result


def compute_power_curve_proxy(
    wind_speed: np.ndarray,
    cut_in: float = 3.0,
    rated: float = 12.0,
    cut_out: float = 25.0,
) -> np.ndarray:
    """Simplified power curve proxy (0 to 1 normalized).

    Cubic between cut-in and rated, 1.0 at rated, drops to 0 at cut-out.
    Real power curves are turbine-specific; this gives a generic shape.
    """
    power = np.zeros_like(wind_speed)
    # Below cut-in or above cut-out: 0
    # Between cut-in and rated: cubic
    mask_operating = (wind_speed >= cut_in) & (wind_speed <= rated)
    normalized = (wind_speed[mask_operating] - cut_in) / (rated - cut_in)
    power[mask_operating] = normalized ** 3
    # Rated to cut-out: 1.0 (simplified, no derating)
    mask_rated = (wind_speed > rated) & (wind_speed <= cut_out)
    power[mask_rated] = 1.0
    return power


def compute_turbulence_intensity(
    wind_gust: np.ndarray, wind_speed: np.ndarray,
) -> np.ndarray:
    """Turbulence intensity proxy: (gust - mean) / mean."""
    return (wind_gust - wind_speed) / np.maximum(wind_speed, 0.1)


def compute_wind_speed_at_hub_height(
    df: pd.DataFrame,
    hub_height: float = 100.0,
) -> pd.DataFrame:
    """Extrapolate wind speed to arbitrary hub height.

    Uses available levels (10m, 100m, 200m) and power law.
    If hub_height == 100, uses measured 100m directly.
    """
    out = df.copy()

    if hub_height == 100.0 and "wind_speed_100m" in out.columns:
        out["wind_speed_hub"] = out["wind_speed_100m"].to_numpy()
        return out

    # Use wind_shear_index if available, else default alpha
    if "wind_shear_index" in out.columns:
        alpha = out["wind_shear_index"].to_numpy()
    else:
        alpha = 0.14

    # Pick best available reference height
    if "wind_speed_100m" in out.columns:
        ref_speed = out["wind_speed_100m"].to_numpy()
        z_ref = 100.0
    elif "wind_speed_10m" in out.columns:
        ref_speed = out["wind_speed_10m"].to_numpy()
        z_ref = 10.0
    else:
        return out

    out["wind_speed_hub"] = compute_power_law_extrapolation(
        ref_speed, z_ref, hub_height, alpha)
    return out


def build_wind_power_features(
    df: pd.DataFrame,
    hub_height: float = 100.0,
    cut_in: float = 3.0,
    rated_speed: float = 12.0,
    cut_out: float = 25.0,
) -> pd.DataFrame:
    """Build all wind power specific features."""
    out = df.copy()

    # Hub height wind speed
    out = compute_wind_speed_at_hub_height(out, hub_height)

    # Wind power density (at 100m and hub height if different)
    if "wind_speed_100m" in out.columns and "air_density" in out.columns:
        out["wind_power_density_100m"] = compute_wind_power_density(
            out["wind_speed_100m"].to_numpy(), out["air_density"].to_numpy())
    if "wind_speed_hub" in out.columns and "air_density" in out.columns:
        out["wind_power_density_hub"] = compute_wind_power_density(
            out["wind_speed_hub"].to_numpy(), out["air_density"].to_numpy())

    # Power curve proxy
    if "wind_speed_100m" in out.columns:
        out["power_curve_proxy_100m"] = compute_power_curve_proxy(
            out["wind_speed_100m"].to_numpy(),
            cut_in=cut_in, rated=rated_speed, cut_out=cut_out)
    if "wind_speed_hub" in out.columns:
        out["power_curve_proxy_hub"] = compute_power_curve_proxy(
            out["wind_speed_hub"].to_numpy(),
            cut_in=cut_in, rated=rated_speed, cut_out=cut_out)

    # Wind direction features
    if "wind_dir_100m" in out.columns:
        dir_vals = out["wind_dir_100m"].to_numpy()
        out["wind_sector_12"] = compute_wind_direction_sectors(dir_vals, 12)
        sin_d, cos_d = compute_wind_dir_polar(dir_vals)
        out["wind_dir_100m_sin"] = sin_d
        out["wind_dir_100m_cos"] = cos_d
        out["wind_dir_change_100m"] = compute_directional_change(dir_vals)

    if "wind_dir_10m" in out.columns:
        out["wind_dir_change_10m"] = compute_directional_change(
            out["wind_dir_10m"].to_numpy())

    # Direction shear (veering/backing)
    if "wind_dir_100m" in out.columns and "wind_dir_10m" in out.columns:
        diff = (out["wind_dir_100m"] - out["wind_dir_10m"] + 180) % 360 - 180
        out["wind_dir_shear_100_10"] = diff.to_numpy()

    # Turbulence intensity
    if "wind_gust_10m" in out.columns and "wind_speed_10m" in out.columns:
        out["turbulence_intensity_10m"] = compute_turbulence_intensity(
            out["wind_gust_10m"].to_numpy(), out["wind_speed_10m"].to_numpy())

    # Interaction features
    if "wind_speed_100m" in out.columns and "air_density" in out.columns:
        out["speed_density_product"] = (
            out["wind_speed_100m"].to_numpy() * out["air_density"].to_numpy())
    if "wind_shear_index" in out.columns and "stability_class" in out.columns:
        # Encode stability class for interaction
        stab_map = {"unstable": -1, "neutral": 0, "stable": 1}
        stab_num = out["stability_class"].map(stab_map).fillna(0).to_numpy()
        out["shear_stability_interaction"] = (
            out["wind_shear_index"].to_numpy() * stab_num)
    if "wind_speed_100m" in out.columns and "boundary_layer_height" in out.columns:
        out["speed_blh_ratio"] = (
            out["wind_speed_100m"].to_numpy()
            / np.maximum(out["boundary_layer_height"].to_numpy(), 1.0))

    # Extreme wind flags
    if "wind_speed_100m" in out.columns:
        out["is_high_wind_100m"] = (out["wind_speed_100m"] > 20.0).astype(int)
        out["is_calm_100m"] = (out["wind_speed_100m"] < 3.0).astype(int)

    return out
