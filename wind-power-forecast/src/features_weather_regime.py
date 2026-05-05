"""Weather regime classification from pressure level geopotential.

Classifies synoptic-scale circulation patterns using 500 hPa geopotential
and 1000-500 hPa thickness. Captures large-scale patterns that modulate
wind power output (zonal flow, blocking, cyclonic, anticyclonic regimes).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_z500_anomaly(
    z500: np.ndarray,
    z500_clim: float = 5500.0,
) -> np.ndarray:
    """Anomaly of 500 hPa geopotential height from climatology (~5500m).

    Positive = ridge (higher than normal), negative = trough.
    """
    return z500 - z500_clim


def compute_thickness_gradient(
    thickness_1000_500: np.ndarray,
    lat_band: float = 5.0,
) -> np.ndarray:
    """Proxy for meridional temperature gradient from thickness.

    In practice, computed from adjacent grid points. Here we use the
    thickness value as a proxy — higher thickness = warmer column.
    """
    return thickness_1000_500


def classify_flow_regime(
    z500_anomaly: np.ndarray,
    thickness_1000_500: np.ndarray | None = None,
    z500_std: float = 200.0,
) -> np.ndarray:
    """Classify synoptic flow regime from 500 hPa pattern.

    Simplified classification:
    - zonal: near-normal height, strong thickness gradient
    - ridge: positive height anomaly (> 0.5 std)
    - trough: negative height anomaly (< -0.5 std)
    - blocking: strong positive anomaly (> 1.5 std)
    - cyclonic: strong negative anomaly (< -1.5 std)

    Returns integer labels: 0=zonal, 1=ridge, 2=trough, 3=blocking, 4=cyclonic.
    """
    n = len(z500_anomaly)
    regime = np.zeros(n, dtype=int)

    anomaly_abs = np.abs(z500_anomaly)

    # Zonal: anomaly < 0.5 std
    # Ridge: 0.5 std < anomaly < 1.5 std
    regime[(z500_anomaly > 0.5 * z500_std) & (z500_anomaly <= 1.5 * z500_std)] = 1
    # Trough: -1.5 std < anomaly < -0.5 std
    regime[(z500_anomaly < -0.5 * z500_std) & (z500_anomaly >= -1.5 * z500_std)] = 2
    # Blocking: strong positive anomaly
    regime[z500_anomaly > 1.5 * z500_std] = 3
    # Cyclonic: strong negative anomaly
    regime[z500_anomaly < -1.5 * z500_std] = 4

    return regime


def compute_jet_stream_features(
    wind_u_500: np.ndarray | None = None,
    wind_v_500: np.ndarray | None = None,
    wind_u_250: np.ndarray | None = None,
    wind_v_250: np.ndarray | None = None,
    wind_speed_500: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Jet stream features from upper-level wind components.

    Returns: jet_speed (max of available levels), is_jet_streak (> 40 m/s),
    jet_direction.
    """
    result: dict[str, np.ndarray] = {}

    # Use best available level
    ws_500 = wind_speed_500
    if ws_500 is None and wind_u_500 is not None and wind_v_500 is not None:
        ws_500 = np.sqrt(wind_u_500**2 + wind_v_500**2)

    if ws_500 is not None:
        result["jet_speed_500hPa"] = ws_500
        result["is_jet_streak"] = (ws_500 > 40.0).astype(float)
        result["jet_intensity"] = np.clip(ws_500 / 50.0, 0, 1)

        if wind_u_500 is not None and wind_v_500 is not None:
            result["jet_direction_500hPa"] = (
                270.0 - np.degrees(np.arctan2(wind_v_500, wind_u_500))) % 360.0

    return result


def compute_frontal_features(
    theta_850: np.ndarray | None = None,
    theta_1000: np.ndarray | None = None,
    wind_dir_850: np.ndarray | None = None,
    wind_dir_1000: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Frontal passage indicators from theta and wind direction changes.

    Strong theta gradient + wind veering = frontal zone.
    """
    result: dict[str, np.ndarray] = {}

    if theta_850 is not None and theta_1000 is not None:
        # Theta difference across layer (baroclinicity proxy)
        result["theta_gradient_1000_850"] = theta_850 - theta_1000
        # Warm core = theta_850 > theta_1000 (unstable)
        result["is_baroclinic"] = (
            np.abs(theta_850 - theta_1000) > 2.0).astype(float)

    if wind_dir_850 is not None and wind_dir_1000 is not None:
        # Wind veering with height (warm advection / frontal zone)
        veer = (wind_dir_850 - wind_dir_1000 + 180) % 360 - 180
        result["wind_veer_1000_850"] = veer
        result["is_warm_advection"] = (veer > 10.0).astype(float)
        result["is_cold_advection"] = (veer < -10.0).astype(float)

    return result


REGIME_NAMES = {0: "zonal", 1: "ridge", 2: "trough", 3: "blocking", 4: "cyclonic"}


def build_weather_regime_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build all weather regime classification features."""
    out = df.copy()

    # --- 500 hPa Geopotential Classification ---
    z500_col = "geopotential_500hPa"
    if z500_col in out.columns:
        z500 = out[z500_col].to_numpy()
        z500_height = z500 / 9.80665  # Convert geopotential to height in metres
        z500_anomaly = compute_z500_anomaly(z500_height)
        out["z500_height_m"] = z500_height
        out["z500_anomaly"] = z500_anomaly

        # Use std of data for local normalization if enough data
        z500_std = max(np.std(z500_anomaly), 50.0)
        out["flow_regime"] = classify_flow_regime(z500_anomaly, z500_std=z500_std)
        out["flow_regime_name"] = pd.Categorical(
            [REGIME_NAMES.get(int(r), "zonal") for r in out["flow_regime"]])

    # --- Thickness-based features ---
    thick_col = "thickness_1000_500hPa"
    if thick_col in out.columns:
        thick = out[thick_col].to_numpy()
        out["column_warmth_index"] = np.clip(
            (thick - 5200.0) / 600.0, 0, 1)  # Normalize around 5400m
        out["is_warm_column"] = (thick > 5500.0).astype(int)
        out["is_cold_column"] = (thick < 5200.0).astype(int)

    # --- Jet stream features ---
    ws_500 = out["wind_speed_500hPa"].to_numpy() if "wind_speed_500hPa" in out.columns else None
    u_500 = out["wind_u_500hPa"].to_numpy() if "wind_u_500hPa" in out.columns else None
    v_500 = out["wind_v_500hPa"].to_numpy() if "wind_v_500hPa" in out.columns else None

    jet = compute_jet_stream_features(
        wind_u_500=u_500, wind_v_500=v_500, wind_speed_500=ws_500)
    for key, vals in jet.items():
        out[key] = vals

    # --- Frontal features ---
    theta_850 = out["theta_850hPa"].to_numpy() if "theta_850hPa" in out.columns else None
    theta_1000 = out["theta_1000hPa"].to_numpy() if "theta_1000hPa" in out.columns else None
    wd_850 = out["wind_dir_850hPa"].to_numpy() if "wind_dir_850hPa" in out.columns else None
    wd_1000 = out["wind_dir_1000hPa"].to_numpy() if "wind_dir_1000hPa" in out.columns else None

    frontal = compute_frontal_features(theta_850, theta_1000, wd_850, wd_1000)
    for key, vals in frontal.items():
        out[key] = vals

    return out
