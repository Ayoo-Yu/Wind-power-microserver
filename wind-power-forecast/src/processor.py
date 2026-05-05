"""Data processing: raw ECMWF output -> clean, standardized Parquet."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd


COLUMN_MAP = {
    # Wind components
    "u100": "wind_u_100m", "v100": "wind_v_100m",
    "u10": "wind_u_10m", "v10": "wind_v_10m",
    "u200": "wind_u_200m", "v200": "wind_v_200m",
    "u10n": "wind_u_10m_neutral", "v10n": "wind_v_10m_neutral",
    # Wind speed / gust
    "si200": "wind_speed_200m",
    "i10fg": "wind_gust_10m", "fg10": "wind_gust_10m", "10fg": "wind_gust_10m",
    # Temperature & moisture
    "t2m": "temperature_2m", "d2m": "dewpoint_2m",
    "skt": "skin_temperature",
    "sh2": "specific_humidity_2m",
    "mx2t": "max_temperature_2m", "mn2t": "min_temperature_2m",
    # Pressure
    "sp": "surface_pressure", "msl": "mean_sea_level_pressure",
    # Boundary layer & turbulence
    "blh": "boundary_layer_height",
    "bld": "boundary_layer_dissipation",
    "zust": "friction_velocity",
    "fsr": "forecast_surface_roughness",
    "chnk": "charnock_parameter",
    "gwd": "gravity_wave_dissipation",
    "mld": "mixed_layer_depth",
    # Heat fluxes
    "sshf": "surface_sensible_heat_flux",
    "slhf": "surface_latent_heat_flux",
    "ishf": "instantaneous_sensible_heat_flux",
    "ie": "instantaneous_moisture_flux",
    # Surface stress
    "iews": "instantaneous_eastward_stress",
    "inss": "instantaneous_northward_stress",
    "ewss": "eastward_turbulent_stress",
    "nsss": "northward_turbulent_stress",
    "lgws": "eastward_gravity_wave_stress",
    "mgws": "northward_gravity_wave_stress",
    # Cloud
    "tcc": "total_cloud_cover", "lcc": "low_cloud_cover",
    "mcc": "medium_cloud_cover", "hcc": "high_cloud_cover",
    "cbh": "cloud_base_height",
    "ceil": "ceiling",
    "vis": "visibility",
    "hcct": "convective_cloud_top_height",
    # Precipitation
    "tp": "total_precipitation", "cp": "convective_precipitation",
    "ptype": "precipitation_type",
    "sf": "snowfall",
    "crr": "convective_rain_rate",
    "lsrr": "large_scale_rain_rate",
    "lsp": "large_scale_precipitation",
    "tprate": "total_precipitation_rate",
    "lspr": "large_scale_precipitation_rate",
    "csfr": "convective_snowfall_rate",
    "lssfr": "large_scale_snowfall_rate",
    "fzra": "freezing_rain",
    "lspf": "large_scale_precipitation_fraction",
    "ilspf": "instantaneous_large_scale_precipitation_fraction",
    # Convection
    "cape": "cape", "cin": "convective_inhibition",
    "capes": "cape_shear",
    "mlcape100": "mixed_layer_cape_100hpa",
    "mlcin100": "mixed_layer_cin_100hpa",
    "mlcape50": "mixed_layer_cape_50hpa",
    "mlcin50": "mixed_layer_cin_50hpa",
    "mucape": "most_unstable_cape",
    "mudlp": "most_unstable_departure_level_pressure",
    "kx": "k_index", "totalx": "total_totals_index",
    "litoti": "lightning_flash_density",
    "litota1": "lightning_flash_density_1h",
    # Column-integrated
    "tcwv": "total_column_water_vapour",
    "tcw": "total_column_water",
    "tclw": "total_column_liquid_water",
    "tciw": "total_column_ice_water",
    "tcrw": "total_column_rain_water",
    "tcsw": "total_column_snow_water",
    "tcslw": "total_column_supercooled_liquid_water",
    "tco3": "total_column_ozone",
    "vimd": "vertically_integrated_moisture_divergence",
    "viwve": "column_eastward_water_vapour_flux",
    "viwvn": "column_northward_water_vapour_flux",
    # Radiation
    "ssrd": "surface_solar_radiation_downwards",
    "ssr": "surface_net_solar_radiation",
    "strd": "surface_thermal_radiation_downwards",
    "str": "surface_net_thermal_radiation",
    "fdir": "surface_direct_solar_radiation",
    "cdir": "surface_direct_solar_radiation_clear_sky",
    "ssrc": "surface_net_solar_radiation_clear_sky",
    "strc": "surface_net_thermal_radiation_clear_sky",
    "dsrp": "surface_direct_normal_solar_radiation",
    "tisr": "toa_incident_solar_radiation",
    "tsr": "top_net_solar_radiation",
    "tsrc": "top_net_solar_radiation_clear_sky",
    "ttr": "top_net_thermal_radiation",
    "ttrc": "top_net_thermal_radiation_clear_sky",
    "sund": "sunshine_duration",
    "uvb": "surface_uv_radiation",
    "par": "photosynthetically_active_radiation",
    # Surface properties
    "sd": "snow_depth", "asn": "snow_albedo",
    "rsn": "snow_density", "tsn": "snow_temperature",
    "smlt": "snowmelt", "sf": "snowfall",
    "lsm": "land_sea_mask",
    "z": "geopotential",
    "fal": "forecast_albedo",
    "flsr": "forecast_log_roughness_heat",
    "src": "skin_reservoir_content",
    "ro": "runoff", "sro": "surface_runoff", "ssro": "subsurface_runoff",
    "e": "evaporation", "es": "snow_evaporation", "pev": "potential_evaporation",
    "swvl1": "soil_moisture_layer1", "swvl2": "soil_moisture_layer2",
    "swvl3": "soil_moisture_layer3", "swvl4": "soil_moisture_layer4",
    "stl1": "soil_temperature_layer1", "stl2": "soil_temperature_layer2",
    "stl3": "soil_temperature_layer3", "stl4": "soil_temperature_layer4",
    "istl1": "ice_temperature_layer1", "istl2": "ice_temperature_layer2",
    "istl3": "ice_temperature_layer3", "istl4": "ice_temperature_layer4",
    # Wet-bulb / isothermal heights
    "deg0l": "zero_degree_level_height",
    "degm10l": "minus_10_degree_level_height",
    "hwbt0": "zero_wet_bulb_height",
    "hwbt1": "one_degree_wet_bulb_height",
    "trpp": "tropopause_pressure",
    # CDS-style long names (ERA5 via CDS API)
    "10m_u_component_of_wind": "wind_u_10m",
    "10m_v_component_of_wind": "wind_v_10m",
    "100m_u_component_of_wind": "wind_u_100m",
    "100m_v_component_of_wind": "wind_v_100m",
    "2m_temperature": "temperature_2m",
    "2m_dewpoint_temperature": "dewpoint_2m",
    "surface_pressure": "surface_pressure",
    "mean_sea_level_pressure": "mean_sea_level_pressure",
    "boundary_layer_height": "boundary_layer_height",
    "surface_sensible_heat_flux": "surface_sensible_heat_flux",
    "surface_latent_heat_flux": "surface_latent_heat_flux",
    "friction_velocity": "friction_velocity",
    "instantaneous_10m_wind_gust": "wind_gust_10m",
    "total_cloud_cover": "total_cloud_cover",
    "low_cloud_cover": "low_cloud_cover",
    "medium_cloud_cover": "medium_cloud_cover",
    "high_cloud_cover": "high_cloud_cover",
    "total_precipitation": "total_precipitation",
    "total_column_water_vapour": "total_column_water_vapour",
    "convective_available_potential_energy": "cape",
    "forecast_surface_roughness": "forecast_surface_roughness",
    "snow_depth": "snow_depth",
    "surface_solar_radiation_downwards": "surface_solar_radiation_downwards",
    # Pressure level variables (paramId-based names from numeric download)
    "t": "temperature", "u": "wind_u", "v": "wind_v",
    "z": "geopotential", "q": "specific_humidity",
    "r": "relative_humidity", "vo": "relative_vorticity",
    "d": "divergence", "w": "vertical_velocity",
}


def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Rename ECMWF short/long names to consistent human-readable names."""
    rename = {}
    seen_targets = set()
    for col in df.columns:
        lower = col.lower().replace(" ", "_")
        target = COLUMN_MAP.get(lower) or COLUMN_MAP.get(col)
        if target is None:
            continue
        if target in seen_targets:
            rename[col] = f"_dup_{target}_{col}"
        else:
            rename[col] = target
            seen_targets.add(target)
    return df.rename(columns=rename)


def aggregate_to_farm_level(
    df: pd.DataFrame,
    center_lat: float,
    center_lon: float,
    value_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Aggregate multi-point data to farm-level time series using IDW."""
    from src.spatial import interpolate_to_point

    if value_cols is None:
        skip_cols = {"time", "valid_time", "timestamp", "point_lat", "point_lon",
                     "latitude", "longitude", "step", "number", "time_step", "expver"}
        value_cols = [c for c in df.columns
                      if c not in skip_cols and pd.api.types.is_numeric_dtype(df[c])]

    time_col = _find_time_col(df)
    results = []
    for t, group in df.groupby(time_col):
        row = {time_col: t}
        lat_col = "point_lat" if "point_lat" in group.columns else "latitude"
        lon_col = "point_lon" if "point_lon" in group.columns else "longitude"
        lats = group[lat_col].to_numpy()
        lons = group[lon_col].to_numpy()
        for col in value_cols:
            vals = group[col].to_numpy()
            row[col] = interpolate_to_point(vals, lats, lons, center_lat, center_lon)
            row[f"{col}_std"] = float(np.std(vals))
        results.append(row)
    return pd.DataFrame(results)


def validate_timestamps(ts: pd.Series) -> bool:
    """Check if timestamps are evenly spaced with no gaps."""
    if len(ts) < 2:
        return True
    diffs = ts.diff().dropna()
    return bool((diffs == diffs.iloc[0]).all())


def build_forecast_error_pairs(
    era5_df: pd.DataFrame,
    hres_df: pd.DataFrame,
    time_col: str = "valid_time",
) -> pd.DataFrame:
    """Merge ERA5 truth and HRES forecast on valid_time, compute errors."""
    era5 = era5_df.set_index(time_col)
    hres = hres_df.set_index(time_col)
    merged = era5.join(hres, rsuffix="_forecast", how="inner")
    result = merged.copy()
    value_cols = [c for c in era5.columns if c in hres.columns]
    for col in value_cols:
        result[f"{col}_truth"] = era5[col]
        result[f"{col}_forecast"] = hres[col]
        result[f"{col}_error"] = hres[col] - era5[col]
    return result.reset_index()


def _find_time_col(df: pd.DataFrame) -> str:
    for candidate in ["valid_time", "time", "timestamp"]:
        if candidate in df.columns:
            return candidate
    raise KeyError(f"No time column found in {df.columns.tolist()}")
