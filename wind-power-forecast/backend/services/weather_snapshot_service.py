"""Weather snapshot service for dashboard.

Retrieves current weather metrics from the most reliable available source:
1. ecmwf_grid_{farm} tables (preferred, but may be empty)
2. train_pre_short table (populated by E-text pipeline, always has data)
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _table_exists(session: Session, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = session.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_name = :name"
            ")"
        ),
        {"name": table_name},
    ).scalar()
    return bool(result)

VARIABLE_PATTERNS = {
    "hub_u": "100u",
    "hub_v": "100v",
    "surf_u": "10u",
    "surf_v": "10v",
    "temp": "2t",
    "dew": "2d",
    "pressure": "sp",
}


def _avg_columns(columns: list[str], row: dict) -> Optional[float]:
    """Average non-None values from columns matching the given prefix in a row dict."""
    vals = [row[c] for c in columns if row.get(c) is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _compute_metrics(avg: dict) -> list[dict]:
    """Convert averaged ECMWF variables into dashboard weather metrics."""
    metrics = []

    # Hub height wind speed (100m)
    hub_u, hub_v = avg.get("hub_u"), avg.get("hub_v")
    if hub_u is not None and hub_v is not None:
        ws100 = math.sqrt(hub_u ** 2 + hub_v ** 2)
        metrics.append({
            "label": "轮毂高度风速",
            "value": f"{ws100:.1f}",
            "unit": "m/s",
            "icon": "wind",
        })

        # Wind direction at 100m
        dir_rad = math.atan2(hub_u, hub_v)
        dir_deg = (dir_rad * 180 / math.pi + 360) % 360
        dir_name = _wind_dir_name(dir_deg)
        metrics.append({
            "label": "轮毂高度风向",
            "value": dir_name,
            "unit": f"{dir_deg:.0f}°",
            "icon": "compass",
        })

    # Surface wind speed (10m)
    surf_u, surf_v = avg.get("surf_u"), avg.get("surf_v")
    if surf_u is not None and surf_v is not None:
        ws10 = math.sqrt(surf_u ** 2 + surf_v ** 2)
        metrics.append({
            "label": "地面风速",
            "value": f"{ws10:.1f}",
            "unit": "m/s",
            "icon": "wind",
        })

    # Temperature (2m)
    temp_k = avg.get("temp")
    if temp_k is not None:
        temp_c = temp_k - 273.15
        metrics.append({
            "label": "气温",
            "value": f"{temp_c:.1f}",
            "unit": "°C",
            "icon": "temp",
        })

    # Humidity from dewpoint spread
    dew_k = avg.get("dew")
    if temp_k is not None and dew_k is not None:
        temp_c = temp_k - 273.15
        dew_c = dew_k - 273.15
        rh = _relative_humidity(temp_c, dew_c)
        metrics.append({
            "label": "湿度",
            "value": f"{rh:.0f}",
            "unit": "%",
            "icon": "drop",
        })

    # Surface pressure
    sp = avg.get("pressure")
    if sp is not None:
        hpa = sp / 100.0
        metrics.append({
            "label": "气压",
            "value": f"{hpa:.0f}",
            "unit": "hPa",
            "icon": "pressure",
        })

    return metrics


def _relative_humidity(temp_c: float, dew_c: float) -> float:
    """Compute relative humidity from temperature and dewpoint (Magnus formula)."""
    a, b = 17.27, 237.7
    gamma_t = (a * temp_c) / (b + temp_c)
    gamma_d = (a * dew_c) / (b + dew_c)
    rh = 100 * math.exp(gamma_d - gamma_t)
    return max(0.0, min(100.0, rh))


def _wind_dir_name(deg: float) -> str:
    """Convert wind direction in degrees to Chinese compass label."""
    dirs = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    idx = round(deg / 45) % 8
    return dirs[idx]


def _try_ecmwf_grid(session: Session, farm_code: str) -> Optional[dict]:
    """Try to get weather from ecmwf_grid_{farm} table."""
    from db_models.ecmwf_grid_model import ecmwf_grid_table_name
    from utils.db_partition_utils import table_exists

    table = ecmwf_grid_table_name(farm_code)
    if not table_exists(session, table):
        return None

    now = datetime.now()
    start = now - timedelta(hours=6)
    latest_source = session.execute(
        text(
            f"SELECT MAX(forecast_source) FROM {table} "
            f"WHERE forecast_time BETWEEN :s AND :e"
        ),
        {"s": start, "e": now},
    ).scalar()

    if not latest_source:
        return None

    rows = session.execute(
        text(
            f"SELECT latitude, longitude, features FROM {table} "
            f"WHERE forecast_source = :src "
            f"  AND forecast_time = ("
            f"    SELECT MIN(forecast_time) FROM {table} "
            f"    WHERE forecast_source = :src AND forecast_time >= :s"
            f"  )"
        ),
        {"src": latest_source, "s": start},
    ).fetchall()

    if not rows:
        return None

    # Average across grid points
    import json as _json
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for lat, lon, features in rows:
        feat = features if isinstance(features, dict) else _json.loads(features) if features else {}
        for key, val in feat.items():
            if val is not None:
                for pattern_name, pattern in VARIABLE_PATTERNS.items():
                    if key == pattern:
                        sums.setdefault(pattern_name, 0.0)
                        counts.setdefault(pattern_name, 0)
                        sums[pattern_name] += float(val)
                        counts[pattern_name] += 1
                        break

    avg = {k: sums[k] / counts[k] for k in sums if counts[k] > 0}
    if not avg:
        return None

    metrics = _compute_metrics(avg)
    if not metrics:
        return None

    return {"metrics": metrics, "updateTime": latest_source.isoformat(), "source": "ecmwf_grid"}


def _try_train_pre(session: Session, farm_code: str) -> Optional[dict]:
    """Try to get weather from train_pre_short_{farm} table (populated by E-text pipeline).

    E-text pipeline creates per-farm tables (e.g. train_pre_short_dplz),
    not the shared train_pre_short table.
    """
    fc = farm_code.lower()

    # Try per-farm table first (populated by E-text pipeline)
    per_farm_table = f"train_pre_short_{fc}"
    if not _table_exists(session, per_farm_table):
        # Fallback to shared table with farm_code column
        per_farm_table = "train_pre_short"

    # Get the latest row
    if per_farm_table == "train_pre_short":
        query = text(
            f'SELECT * FROM {per_farm_table} '
            f'WHERE farm_code = :fc '
            f'ORDER BY "Timestamp" DESC LIMIT 1'
        )
        row = session.execute(query, {"fc": fc}).fetchone()
    else:
        query = text(
            f'SELECT * FROM {per_farm_table} '
            f'ORDER BY "Timestamp" DESC LIMIT 1'
        )
        row = session.execute(query).fetchone()

    if not row:
        return None

    columns = list(row._fields)
    row_dict = dict(zip(columns, row))

    # Group columns by ECMWF variable prefix
    var_cols: dict[str, list[str]] = {k: [] for k in VARIABLE_PATTERNS}
    for col in columns:
        for pattern_name, prefix in VARIABLE_PATTERNS.items():
            if col.startswith(prefix + "_") or col == prefix:
                var_cols[pattern_name].append(col)
                break

    # Average across grid points for each variable
    avg: dict[str, float] = {}
    for var_name, cols in var_cols.items():
        val = _avg_columns(cols, row_dict)
        if val is not None:
            avg[var_name] = val

    if not avg:
        return None

    metrics = _compute_metrics(avg)
    if not metrics:
        return None

    ts = row_dict.get("Timestamp") or row_dict.get("timestamp")
    update_time = ts.isoformat() if ts else None

    return {"metrics": metrics, "updateTime": update_time, "source": f"train_pre_short ({per_farm_table})"}


def get_weather_snapshot(session: Session, farm_code: str) -> dict:
    """Get weather snapshot using the best available data source.

    Tries ecmwf_grid first, falls back to train_pre_short.
    Returns {"metrics": [...], "updateTime": "...", "source": "..."} or
             {"metrics": [], "updateTime": null, "source": null}.
    """
    # Source 1: ecmwf_grid (preferred, but often empty)
    try:
        result = _try_ecmwf_grid(session, farm_code)
        if result and result.get("metrics"):
            logger.info(f"Weather snapshot from ecmwf_grid for {farm_code}")
            return result
    except Exception as e:
        logger.warning(f"ecmwf_grid query failed for {farm_code}: {e}")

    # Source 2: train_pre_short (populated by E-text pipeline)
    try:
        result = _try_train_pre(session, farm_code)
        if result and result.get("metrics"):
            logger.info(f"Weather snapshot from train_pre_short for {farm_code}")
            return result
    except Exception as e:
        logger.warning(f"train_pre_short query failed for {farm_code}: {e}")

    logger.info(f"No weather data available for {farm_code}")
    return {"metrics": [], "updateTime": None, "source": None}
