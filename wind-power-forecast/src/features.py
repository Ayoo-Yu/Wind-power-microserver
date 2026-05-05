"""Four-layer feature engineering for wind power forecasting.

Layer 1: Direct physical variables (Tier 1 ECMWF)
Layer 2: Derived physical features (wind shear, air density, vector change)
Layer 3: Stability features (BLH, heat flux, friction velocity)
Layer 4: ENS ensemble statistics (in ens_stats.py)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

R_DRY_AIR = 287.05
RATIO_MW = 0.622  # molecular weight ratio water vapor / dry air


def compute_wind_speed(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    return np.sqrt(u**2 + v**2)


def compute_wind_direction(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    return (270.0 - np.degrees(np.arctan2(v, u))) % 360.0


def compute_wind_shear_index(
    w_upper: np.ndarray, w_lower: np.ndarray,
    z_upper: float = 100.0, z_lower: float = 10.0,
) -> np.ndarray:
    ratio = np.maximum(w_upper, 1e-10) / np.maximum(w_lower, 1e-10)
    return np.log(ratio) / np.log(z_upper / z_lower)


def compute_air_density(pressure_pa: np.ndarray, temperature_k: np.ndarray) -> np.ndarray:
    return pressure_pa / (R_DRY_AIR * temperature_k)


def compute_moist_air_density(
    pressure_pa: np.ndarray, temperature_k: np.ndarray, specific_humidity: np.ndarray,
) -> np.ndarray:
    virtual_temp = temperature_k * (1.0 + 0.608 * specific_humidity)
    return pressure_pa / (R_DRY_AIR * virtual_temp)


def compute_specific_humidity(
    temperature_k: np.ndarray, dewpoint_k: np.ndarray,
    pressure_pa: np.ndarray,
) -> np.ndarray:
    """Compute specific humidity from temperature, dewpoint, and pressure.

    Uses the Magnus formula for saturation vapor pressure:
    e_sat = 610.78 * exp(17.27 * (Td - 273.15) / (Td - 273.15 + 237.3))
    """
    td_c = dewpoint_k - 273.15
    e_sat = 610.78 * np.exp(17.27 * td_c / (td_c + 237.3))
    q = RATIO_MW * e_sat / (pressure_pa - (1 - RATIO_MW) * e_sat)
    return np.clip(q, 0.0, 0.05)


def compute_wind_vector_change(
    u: np.ndarray, v: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    dudt = np.zeros_like(u)
    dvdt = np.zeros_like(v)
    dudt[1:] = np.diff(u)
    dvdt[1:] = np.diff(v)
    dudt[0] = dudt[1]
    dvdt[0] = dvdt[1]
    return dudt, dvdt


def compute_stability_index(blh: np.ndarray, sshf: np.ndarray) -> np.ndarray:
    return blh / np.maximum(np.abs(sshf), 1e-10)


def classify_stability(index: np.ndarray) -> np.ndarray:
    labels = np.full(index.shape, "neutral", dtype=object)
    labels[index < 5.0] = "unstable"
    labels[index > 20.0] = "stable"
    return labels


def build_tier1_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "wind_u_100m" in out.columns and "wind_v_100m" in out.columns:
        out["wind_speed_100m"] = compute_wind_speed(out["wind_u_100m"].to_numpy(), out["wind_v_100m"].to_numpy())
        out["wind_dir_100m"] = compute_wind_direction(out["wind_u_100m"].to_numpy(), out["wind_v_100m"].to_numpy())
    if "wind_u_10m" in out.columns and "wind_v_10m" in out.columns:
        out["wind_speed_10m"] = compute_wind_speed(out["wind_u_10m"].to_numpy(), out["wind_v_10m"].to_numpy())
        out["wind_dir_10m"] = compute_wind_direction(out["wind_u_10m"].to_numpy(), out["wind_v_10m"].to_numpy())
    if "wind_u_200m" in out.columns and "wind_v_200m" in out.columns:
        out["wind_speed_200m"] = compute_wind_speed(out["wind_u_200m"].to_numpy(), out["wind_v_200m"].to_numpy())
        out["wind_dir_200m"] = compute_wind_direction(out["wind_u_200m"].to_numpy(), out["wind_v_200m"].to_numpy())
    return out


def build_tier2_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "wind_speed_100m" in out.columns and "wind_speed_10m" in out.columns:
        out["wind_shear_index"] = compute_wind_shear_index(
            out["wind_speed_100m"].to_numpy(), out["wind_speed_10m"].to_numpy())
    if "wind_speed_200m" in out.columns and "wind_speed_100m" in out.columns:
        out["wind_shear_200_100"] = compute_wind_shear_index(
            out["wind_speed_200m"].to_numpy(), out["wind_speed_100m"].to_numpy(),
            z_upper=200.0, z_lower=100.0)
    if "surface_pressure" in out.columns and "temperature_2m" in out.columns:
        if "specific_humidity_2m" not in out.columns and "dewpoint_2m" in out.columns:
            out["specific_humidity_2m"] = compute_specific_humidity(
                out["temperature_2m"].to_numpy(),
                out["dewpoint_2m"].to_numpy(),
                out["surface_pressure"].to_numpy())
        if "specific_humidity_2m" in out.columns:
            out["air_density"] = compute_moist_air_density(
                out["surface_pressure"].to_numpy(),
                out["temperature_2m"].to_numpy(),
                out["specific_humidity_2m"].to_numpy())
        else:
            out["air_density"] = compute_air_density(
                out["surface_pressure"].to_numpy(), out["temperature_2m"].to_numpy())
    if "wind_u_100m" in out.columns and "wind_v_100m" in out.columns:
        dudt, dvdt = compute_wind_vector_change(
            out["wind_u_100m"].to_numpy(), out["wind_v_100m"].to_numpy())
        out["wind_u_change_100m"] = dudt
        out["wind_v_change_100m"] = dvdt
        out["wind_speed_change_100m"] = compute_wind_speed(dudt, dvdt)
    return out


def build_tier3_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "boundary_layer_height" in out.columns and "surface_sensible_heat_flux" in out.columns:
        out["stability_index"] = compute_stability_index(
            out["boundary_layer_height"].to_numpy(),
            out["surface_sensible_heat_flux"].to_numpy())
        out["stability_class"] = classify_stability(out["stability_index"].to_numpy())
    if "friction_velocity" in out.columns:
        out["turbulence_proxy"] = out["friction_velocity"] ** 2
    cloud_cols = [c for c in ["total_cloud_cover", "low_cloud_cover", "medium_cloud_cover", "high_cloud_cover"]
                  if c in out.columns]
    if cloud_cols:
        out["cloud_cover_combined"] = out[cloud_cols].mean(axis=1)
    if "boundary_layer_dissipation" in out.columns and "wind_speed_100m" in out.columns:
        out["bl_dissipation_ratio"] = (
            out["boundary_layer_dissipation"].to_numpy()
            / np.maximum(out["wind_speed_100m"].to_numpy() ** 3, 1e-10))
    if "instantaneous_eastward_stress" in out.columns and "instantaneous_northward_stress" in out.columns:
        out["total_surface_stress"] = compute_wind_speed(
            out["instantaneous_eastward_stress"].to_numpy(),
            out["instantaneous_northward_stress"].to_numpy())
    if "convective_inhibition" in out.columns and "cape" in out.columns:
        out["cape_cin_ratio"] = out["cape"].to_numpy() / np.maximum(np.abs(out["convective_inhibition"].to_numpy()), 1e-10)
    return out


def build_all_features(df: pd.DataFrame) -> pd.DataFrame:
    df = build_tier1_features(df)
    df = build_tier2_features(df)
    df = build_tier3_features(df)
    return df
