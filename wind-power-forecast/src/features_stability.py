"""Advanced stability and convection indices from pressure level data.

Standard meteorological indices computed from multi-level atmospheric data:
- Showalter Index (SI)
- Total Totals Index (TT)
- Cross Totals Index (CT)
- K Index (KI)
- Lifted Index (LI)
- SWEAT Index (severe weather threat)
- Equivalent potential temperature gradient
- Wind direction shear (veering/backing)
- Moisture convergence
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_dewpoint_from_rh(
    temperature_k: np.ndarray, rh_percent: np.ndarray,
) -> np.ndarray:
    """Dewpoint from temperature and relative humidity (Magnus formula inverse)."""
    t_c = temperature_k - 273.15
    gamma = 17.27 * t_c / (t_c + 237.3)
    rh_frac = np.clip(rh_percent / 100.0, 0.01, 1.0)
    dewpoint_c = 237.3 * (gamma + np.log(rh_frac)) / (17.27 - gamma - np.log(rh_frac))
    return dewpoint_c + 273.15


def compute_showalter_index(
    t_850: np.ndarray, td_850: np.ndarray, t_500: np.ndarray,
) -> np.ndarray:
    """Showalter Stability Index. SI = T500 - T_parcel_500.

    Parcel lifted from 850 hPa dry-adiabatically to LCL, then
    moist-adiabatically to 500 hPa. Approximation: use dry adiabat
    lapse rate with moisture correction.
    SI < 0: unstable, SI > 0: stable.
    """
    t_850_c = t_850 - 273.15
    td_850_c = td_850 - 273.15
    # LCL temperature approximation (Bolton 1980)
    td_spread = t_850_c - td_850_c
    t_lcl = t_850_c - td_spread * (0.5 + 0.005 * td_spread)
    # Moist adiabatic lapse rate approximation ~6.5 K/km
    # Height difference 850→500 hPa ≈ 4500m
    dz = 4500.0
    lapse_dry = 9.8  # K/km dry adiabatic
    t_at_lcl = t_lcl + 273.15
    # Use weighted lapse: dry below LCL height, moist above
    lcl_height = (t_850 - t_at_lcl) / lapse_dry * 1000.0  # meters
    remaining = dz - lcl_height
    remaining = np.maximum(remaining, 0)
    # Moist adiabatic lapse: ~5-6.5 K/km, approximate as 6.0
    t_parcel_500 = t_at_lcl - 6.0 * remaining / 1000.0
    # Where LCL is above 500hPa (very dry), use dry adiabat
    dry_only = lcl_height >= dz
    t_parcel_500 = np.where(
        dry_only,
        t_850 - lapse_dry * dz / 1000.0,
        t_parcel_500,
    )
    return t_500 - t_parcel_500


def compute_total_totals(
    t_850: np.ndarray, td_850: np.ndarray, t_500: np.ndarray,
) -> np.ndarray:
    """Total Totals Index. TT = (T850 + Td850) - 2*T500.

    TT > 44: scattered thunderstorms
    TT > 50: widespread severe thunderstorms
    """
    t_850_c = t_850 - 273.15
    td_850_c = td_850 - 273.15
    t_500_c = t_500 - 273.15
    return (t_850_c + td_850_c) - 2.0 * t_500_c


def compute_cross_totals(
    td_850: np.ndarray, t_500: np.ndarray,
) -> np.ndarray:
    """Cross Totals. CT = Td850 - T500."""
    return (td_850 - 273.15) - (t_500 - 273.15)


def compute_k_index(
    t_850: np.ndarray, t_700: np.ndarray, t_500: np.ndarray,
    td_850: np.ndarray, td_700: np.ndarray,
) -> np.ndarray:
    """K Index. K = (T850-T500) + Td850 - (T700-Td700).

    K > 30: high thunderstorm probability
    K > 40: nearly 100% thunderstorm coverage
    """
    t_850_c = t_850 - 273.15
    t_700_c = t_700 - 273.15
    t_500_c = t_500 - 273.15
    td_850_c = td_850 - 273.15
    td_700_c = td_700 - 273.15
    return (t_850_c - t_500_c) + td_850_c - (t_700_c - td_700_c)


def compute_lifted_index(
    t_surface: np.ndarray, td_surface: np.ndarray,
    t_500: np.ndarray, p_surface_hpa: np.ndarray,
) -> np.ndarray:
    """Surface-based Lifted Index. LI = T500 - T_parcel_500.

    Lift surface parcel to 500 hPa. Approximation using dry-moist adiabat split.
    LI < -6: extremely unstable
    LI < 0: unstable
    LI > 0: stable
    """
    t_sfc_c = t_surface - 273.15
    td_sfc_c = td_surface - 273.15
    # LCL temperature
    spread = t_sfc_c - td_sfc_c
    t_lcl = t_sfc_c - spread * (0.5 + 0.005 * spread)
    t_lcl_k = t_lcl + 273.15
    # Height from surface to 500 hPa
    dz = (p_surface_hpa - 500.0) / p_surface_hpa * 8500.0  # rough scale height approx
    dz = np.maximum(dz, 0)
    # LCL height
    lcl_h = (t_surface - t_lcl_k) / 9.8 * 1000.0
    remaining = np.maximum(dz - lcl_h, 0)
    t_parcel_500 = t_lcl_k - 6.0 * remaining / 1000.0
    return t_500 - t_parcel_500


def compute_sweat_index(
    t_850: np.ndarray, td_850: np.ndarray,
    ws_850: np.ndarray, wd_850: np.ndarray,
    t_500: np.ndarray, ws_500: np.ndarray, wd_500: np.ndarray,
) -> np.ndarray:
    """Severe Weather Threat Index.

    SWEAT = 12*td850 + 20*(TT-49) + 2*ws850 + ws500 + 125*sin(wd500-wd850)
    """
    td_850_c = td_850 - 273.15
    tt = compute_total_totals(t_850, td_850, t_500)
    shear_term = 125.0 * np.sin(np.radians(wd_500 - wd_850))
    return (12.0 * np.maximum(td_850_c, 0)
            + 20.0 * np.maximum(tt - 49.0, 0)
            + 2.0 * ws_850
            + ws_500
            + shear_term)


def compute_theta_e_gradient(
    theta_e_850: np.ndarray, theta_e_500: np.ndarray,
) -> np.ndarray:
    """Equivalent potential temperature gradient. Negative = convectively unstable."""
    return theta_e_500 - theta_e_850


def compute_wind_direction_shear(
    wd_1000: np.ndarray, wd_850: np.ndarray, wd_700: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Wind direction change with height. Returns (veering_angle, classification).

    Veering (positive): warm advection
    Backing (negative): cold advection
    """
    angle_change = ((wd_850 - wd_1000 + 180) % 360) - 180
    total_change = ((wd_700 - wd_1000 + 180) % 360) - 180
    classification = np.full(angle_change.shape, "neutral", dtype=object)
    classification[angle_change > 30] = "veering_warm_advection"
    classification[angle_change < -30] = "backing_cold_advection"
    return total_change, classification


def compute_moisture_convergence_proxy(
    q_850: np.ndarray, ws_850: np.ndarray,
) -> np.ndarray:
    """Simplified moisture convergence proxy at 850 hPa.

    Full version needs spatial gradients; this uses specific humidity
    and wind speed as a proxy: q * ws represents moisture flux magnitude.
    """
    return q_850 * ws_850


def build_stability_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build all stability/convection indices from pressure level data.

    Expects columns: temperature_{level}hPa, relative_humidity_{level}hPa,
    wind_u_{level}hPa, wind_v_{level}hPa, specific_humidity_{level}hPa.
    """
    out = df.copy()

    # Derive dewpoint at 850 and 700 from RH + temperature
    for level in [850, 700]:
        t_col = f"temperature_{level}hPa"
        rh_col = f"relative_humidity_{level}hPa"
        if all(c in out.columns for c in [t_col, rh_col]):
            out[f"dewpoint_{level}hPa"] = compute_dewpoint_from_rh(
                out[t_col].to_numpy(), out[rh_col].to_numpy())

    # Derive wind speed/direction at needed levels
    for level in [1000, 850, 700, 500]:
        u_col = f"wind_u_{level}hPa"
        v_col = f"wind_v_{level}hPa"
        ws_col = f"wind_speed_{level}hPa"
        wd_col = f"wind_dir_{level}hPa"
        if all(c in out.columns for c in [u_col, v_col]):
            if ws_col not in out.columns:
                out[ws_col] = np.sqrt(out[u_col].to_numpy()**2 + out[v_col].to_numpy()**2)
            if wd_col not in out.columns:
                out[wd_col] = (270.0 - np.degrees(np.arctan2(
                    out[v_col].to_numpy(), out[u_col].to_numpy()))) % 360.0

    t850 = out.get("temperature_850hPa")
    t700 = out.get("temperature_700hPa")
    t500 = out.get("temperature_500hPa")
    td850 = out.get("dewpoint_850hPa")
    td700 = out.get("dewpoint_700hPa")

    # Showalter Index
    if all(v is not None for v in [t850, td850, t500]):
        out["showalter_index"] = compute_showalter_index(
            t850.to_numpy(), td850.to_numpy(), t500.to_numpy())

    # Total Totals
    if all(v is not None for v in [t850, td850, t500]):
        out["total_totals_index"] = compute_total_totals(
            t850.to_numpy(), td850.to_numpy(), t500.to_numpy())

    # Cross Totals
    if all(v is not None for v in [td850, t500]):
        out["cross_totals_index"] = compute_cross_totals(
            td850.to_numpy(), t500.to_numpy())

    # K Index
    if all(v is not None for v in [t850, t700, t500, td850, td700]):
        out["k_index"] = compute_k_index(
            t850.to_numpy(), t700.to_numpy(), t500.to_numpy(),
            td850.to_numpy(), td700.to_numpy())

    # Lifted Index (surface-based)
    t_sfc = out.get("temperature_2m")
    td_sfc = out.get("dewpoint_2m")
    sp = out.get("surface_pressure")
    if all(v is not None for v in [t_sfc, td_sfc, t500, sp]):
        out["lifted_index"] = compute_lifted_index(
            t_sfc.to_numpy(), td_sfc.to_numpy(),
            t500.to_numpy(), sp.to_numpy() / 100.0)

    # SWEAT Index
    ws850 = out.get("wind_speed_850hPa")
    wd850 = out.get("wind_dir_850hPa")
    ws500 = out.get("wind_speed_500hPa")
    wd500 = out.get("wind_dir_500hPa")
    if all(v is not None for v in [t850, td850, ws850, wd850, t500, ws500, wd500]):
        out["sweat_index"] = compute_sweat_index(
            t850.to_numpy(), td850.to_numpy(),
            ws850.to_numpy(), wd850.to_numpy(),
            t500.to_numpy(), ws500.to_numpy(), wd500.to_numpy())

    # Theta-e gradient (850-500)
    theta_e_850 = out.get("theta_e_850hPa")
    theta_e_500 = out.get("theta_e_500hPa")
    if theta_e_850 is not None and theta_e_500 is not None:
        out["theta_e_gradient_850_500"] = compute_theta_e_gradient(
            theta_e_850.to_numpy(), theta_e_500.to_numpy())
    elif all(v is not None for v in [t850, td850, t500]):
        from src.features_pl import compute_equivalent_potential_temperature
        q850 = out.get("specific_humidity_850hPa")
        if q850 is not None:
            te850 = compute_equivalent_potential_temperature(t850.to_numpy(), np.full_like(t850.to_numpy(), 850.0), td850.to_numpy())
            te500 = compute_equivalent_potential_temperature(t500.to_numpy(), np.full_like(t500.to_numpy(), 500.0), td850.to_numpy())
            out["theta_e_gradient_850_500"] = te500 - te850

    # Wind direction shear (1000-850-700)
    wd1000 = out.get("wind_dir_1000hPa")
    wd850v = out.get("wind_dir_850hPa")
    wd700 = out.get("wind_dir_700hPa")
    if all(v is not None for v in [wd1000, wd850v, wd700]):
        angle, advection_class = compute_wind_direction_shear(
            wd1000.to_numpy(), wd850v.to_numpy(), wd700.to_numpy())
        out["wind_direction_shear_1000_700"] = angle
        out["thermal_advection_type"] = advection_class

    # Moisture convergence proxy at 850
    q850 = out.get("specific_humidity_850hPa")
    if q850 is not None and ws850 is not None:
        out["moisture_flux_850hPa"] = compute_moisture_convergence_proxy(
            q850.to_numpy(), ws850.to_numpy())

    return out
