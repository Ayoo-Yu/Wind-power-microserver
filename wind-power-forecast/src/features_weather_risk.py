"""Weather risk features for wind power forecasting.

Icing risk, storm front detection, extreme event flags.
Uses downloaded but previously unused variables: precipitation_type,
snow_depth, cape, convective_inhibition, cloud_base_height, etc.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_icing_risk(
    temperature: np.ndarray,
    dewpoint: np.ndarray,
    wind_speed: np.ndarray,
    precipitation_type: np.ndarray | None = None,
    snow_depth: np.ndarray | None = None,
) -> np.ndarray:
    """Compute icing risk index (0-3 scale).

    0 = no risk, 1 = low, 2 = moderate, 3 = high.
    Based on temperature near freezing, high humidity, and precipitation.
    """
    # Temperature-humidity component
    rh = 100.0 * np.exp(
        (17.625 * dewpoint) / (243.04 + dewpoint)
        - (17.625 * temperature) / (243.04 + temperature)
    )
    rh = np.clip(rh, 0, 100)

    # Near-freezing band (-10 to +2 C)
    in_freezing_band = (temperature >= -10.0) & (temperature <= 2.0)

    # Base risk from temperature and humidity
    risk = np.zeros_like(temperature)
    risk[in_freezing_band] = 1.0

    # Higher risk when very humid (>90%) and near freezing
    high_humid = in_freezing_band & (rh > 90.0)
    risk[high_humid] = 2.0

    # Precipitation type boost (1=rain, 3=freezing rain, 5=snow, 6=wet snow)
    if precipitation_type is not None:
        frozen_precip = np.isin(precipitation_type, [3, 5, 6, 7])
        risk[in_freezing_band & frozen_precip] = 3.0

    # Snow depth boost
    if snow_depth is not None:
        has_snow = snow_depth > 0.01
        risk[in_freezing_band & has_snow & (rh > 80.0)] = np.maximum(
            risk[in_freezing_band & has_snow & (rh > 80.0)], 2.5)

    # Wind speed amplification (icing accretes faster with wind)
    wind_boost = np.where(
        in_freezing_band & (wind_speed > 5.0),
        0.5 * (wind_speed / 10.0), 0.0)
    risk = risk + wind_boost

    return np.clip(risk, 0, 3)


def compute_storm_front_features(
    pressure: np.ndarray,
    pressure_change_3h: np.ndarray | None = None,
    wind_gust: np.ndarray | None = None,
    cape: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Detect storm front indicators.

    Returns dict of arrays: rapid_pressure_drop, convective_storm_risk,
    wind_gust_hazard.
    """
    result: dict[str, np.ndarray] = {}
    n = len(pressure)
    fill = np.zeros(n)

    # Rapid pressure drop (> 4 hPa in 3h = active front)
    if pressure_change_3h is not None:
        result["rapid_pressure_drop"] = (pressure_change_3h < -4.0).astype(float)
        result["severe_pressure_drop"] = (pressure_change_3h < -8.0).astype(float)
    else:
        # Approximate from raw pressure if 3h change not available
        p_change = np.diff(pressure, prepend=pressure[0])
        result["rapid_pressure_drop"] = (p_change < -1.0).astype(float)

    # Convective storm risk (high CAPE + gusty winds)
    if cape is not None and wind_gust is not None:
        cape_risk = np.clip(cape / 3000.0, 0, 1)
        gust_factor = np.clip(wind_gust / 30.0, 0, 1)
        result["convective_storm_risk"] = (cape_risk * gust_factor)
    elif cape is not None:
        result["convective_storm_risk"] = np.clip(cape / 3000.0, 0, 1)
    else:
        result["convective_storm_risk"] = fill

    # Wind gust hazard (> 25 m/s = operational hazard)
    if wind_gust is not None:
        result["wind_gust_hazard"] = np.clip(
            (wind_gust - 20.0) / 15.0, 0, 1)
    else:
        result["wind_gust_hazard"] = fill

    return result


def compute_precipitation_risk(
    precipitation_type: np.ndarray,
    total_precipitation: np.ndarray,
    temperature: np.ndarray,
) -> dict[str, np.ndarray]:
    """Classify precipitation risk for turbine operations.

    Returns flags for freezing_rain, wet_snow, heavy_precip.
    """
    result: dict[str, np.ndarray] = {}

    # Freezing rain: ptype=3 or (rain + near-freezing)
    result["is_freezing_rain"] = np.isin(precipitation_type, [3, 7]).astype(float)
    near_freeze_rain = (precipitation_type == 1) & (temperature < 1.0)
    result["is_freezing_rain"] = np.maximum(
        result["is_freezing_rain"], near_freeze_rain.astype(float))

    # Wet snow: ptype=6 or (snow + above-freezing)
    result["is_wet_snow"] = np.isin(precipitation_type, [5, 6]).astype(float)
    wet_snow_temp = np.isin(precipitation_type, [5]) & (temperature > 0.0) & (temperature < 3.0)
    result["is_wet_snow"] = np.maximum(
        result["is_wet_snow"], wet_snow_temp.astype(float))

    # Heavy precipitation (> 10mm in timestep)
    result["is_heavy_precip"] = (total_precipitation > 10.0).astype(float)

    return result


def compute_visibility_risk(
    cloud_base_height: np.ndarray | None = None,
    total_cloud_cover: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Low visibility risk from cloud cover patterns."""
    result: dict[str, np.ndarray] = {}

    if cloud_base_height is not None:
        # Very low ceiling (< 200m = significant fog/low cloud)
        result["low_ceiling_risk"] = np.clip(
            1.0 - cloud_base_height / 200.0, 0, 1)

    if total_cloud_cover is not None:
        # Overcast conditions (> 95% cloud cover)
        result["is_overcast"] = (total_cloud_cover > 95.0).astype(float)

    return result


def compute_cold_weather_features(
    temperature: np.ndarray,
    wind_speed: np.ndarray,
) -> dict[str, np.ndarray]:
    """Wind chill and extreme cold features."""
    result: dict[str, np.ndarray] = {}

    # Wind chill (simplified formula, valid for T < 10C and wind > 1.3 m/s)
    mask = (temperature < 10.0) & (wind_speed > 1.3)
    wind_chill = np.full_like(temperature, np.nan)
    v16 = wind_speed[mask] ** 0.16
    wind_chill[mask] = (
        13.12 + 0.6215 * temperature[mask]
        - 11.37 * v16 * 10.0  # 10 km/h equivalent
        + 0.3965 * temperature[mask] * v16 * 10.0
    )
    result["wind_chill"] = np.nan_to_num(wind_chill, nan=temperature)

    # Extreme cold flag (< -20C wind chill)
    result["is_extreme_cold"] = (result["wind_chill"] < -20.0).astype(float)

    # Temperature range for turbine shutdown zones
    result["is_arctic_operating"] = (
        (temperature < -20.0) & (temperature >= -30.0)).astype(float)
    result["is_shutdown_cold"] = (temperature < -30.0).astype(float)

    return result


def build_weather_risk_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build all weather risk features."""
    out = df.copy()
    n = len(out)

    # --- Icing Risk ---
    has_icing_inputs = (
        "temperature_2m" in out.columns
        and "dewpoint_2m" in out.columns
        and "wind_speed_100m" in out.columns
    )
    if has_icing_inputs:
        ptype = out["precipitation_type"].to_numpy() if "precipitation_type" in out.columns else None
        snow = out["snow_depth"].to_numpy() if "snow_depth" in out.columns else None
        out["icing_risk_index"] = compute_icing_risk(
            out["temperature_2m"].to_numpy(),
            out["dewpoint_2m"].to_numpy(),
            out["wind_speed_100m"].to_numpy(),
            precipitation_type=ptype,
            snow_depth=snow,
        )
        out["is_icing"] = (out["icing_risk_index"] >= 2.0).astype(int)

    # --- Storm Front ---
    if "surface_pressure" in out.columns:
        p_change = None
        if "surface_pressure_roc_3h" in out.columns:
            p_change = out["surface_pressure_roc_3h"].to_numpy()
        elif "mean_sea_level_pressure_roc_3h" in out.columns:
            p_change = out["mean_sea_level_pressure_roc_3h"].to_numpy()

        cape = out["cape"].to_numpy() if "cape" in out.columns else None
        gust = out["wind_gust_10m"].to_numpy() if "wind_gust_10m" in out.columns else None

        storm = compute_storm_front_features(
            out["surface_pressure"].to_numpy(),
            pressure_change_3h=p_change, wind_gust=gust, cape=cape)
        for key, vals in storm.items():
            out[key] = vals

    # --- Precipitation Risk ---
    if "precipitation_type" in out.columns and "total_precipitation" in out.columns:
        precip_risk = compute_precipitation_risk(
            out["precipitation_type"].to_numpy(),
            out["total_precipitation"].to_numpy(),
            out["temperature_2m"].to_numpy() if "temperature_2m" in out.columns
            else np.zeros(n))
        for key, vals in precip_risk.items():
            out[key] = vals

    # --- Visibility Risk ---
    cbh = out["cloud_base_height"].to_numpy() if "cloud_base_height" in out.columns else None
    tcc = out["total_cloud_cover"].to_numpy() if "total_cloud_cover" in out.columns else None
    if cbh is not None or tcc is not None:
        vis_risk = compute_visibility_risk(cbh, tcc)
        for key, vals in vis_risk.items():
            out[key] = vals

    # --- Cold Weather ---
    if "temperature_2m" in out.columns and "wind_speed_100m" in out.columns:
        cold = compute_cold_weather_features(
            out["temperature_2m"].to_numpy(),
            out["wind_speed_100m"].to_numpy())
        for key, vals in cold.items():
            out[key] = vals

    return out
