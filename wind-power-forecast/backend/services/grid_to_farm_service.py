"""
每场独立格点数据查询服务

直接查询 ecmwf_grid_{farm_code} 表，无需空间过滤。
将长格式 JSONB 数据转换为前端期望的宽表格式。
"""

import json
import logging
from datetime import datetime, time
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from db_models.ecmwf_grid_model import ecmwf_grid_table_name
from utils.db_partition_utils import table_exists as _table_exists

logger = logging.getLogger(__name__)

VARIABLES = ['100u', '100v', '10u', '10v', '2t', '2d']


def _farm_table(session: Session, farm_code: str) -> Optional[str]:
    """返回场站表名，若表不存在则返回 None"""
    table = ecmwf_grid_table_name(farm_code)
    if not _table_exists(session, table):
        return None
    return table


def _latest_forecast_source(session: Session, table: str, start_time: datetime, end_time: datetime) -> Optional[datetime]:
    return session.execute(
        text(
            f"SELECT MAX(forecast_source) FROM {table} "
            f"WHERE forecast_time BETWEEN :start AND :end"
        ),
        {"start": start_time, "end": end_time},
    ).scalar()


def query_grid_data_as_wide(
    session: Session,
    farm_code: str,
    start_time: datetime,
    end_time: datetime,
    data_type: str = "DQ",
    limit: int = 1000,
) -> pd.DataFrame:
    """查询场站格点数据并转换为宽表格式

    返回 DataFrame，列名格式为 {variable}_{lat}_{lon}（如 100u_26.0_103.3），
    与前端期望的格式一致。每个 forecast_time 一行，每个格点的每个变量一列。
    """
    table = _farm_table(session, farm_code)
    if not table:
        return pd.DataFrame()

    latest_source = _latest_forecast_source(session, table, start_time, end_time)
    if not latest_source:
        return pd.DataFrame()

    rows = session.execute(
        text(
            f"SELECT forecast_time, latitude, longitude, features "
            f"FROM {table} "
            f"WHERE forecast_source = :source "
            f"  AND forecast_time BETWEEN :start AND :end "
            f"ORDER BY forecast_time, latitude, longitude"
        ),
        {
            "source": latest_source,
            "start": start_time,
            "end": end_time,
        },
    ).fetchall()

    if not rows:
        return pd.DataFrame()

    records: dict[datetime, dict] = {}
    for ft, lat_g, lon_g, features in rows:
        if ft not in records:
            records[ft] = {"timestamp": ft}
        feat = features if isinstance(features, dict) else json.loads(features) if features else {}
        for var in VARIABLES:
            val = feat.get(var)
            col_name = f"{var}_{lat_g}_{lon_g}"
            records[ft][col_name] = float(val) if val is not None else None

    df = pd.DataFrame(list(records.values()))
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)

    if limit and limit > 0:
        df = df.head(limit)

    return df


def get_grid_latest_timestamp(session: Session, farm_code: str) -> Optional[datetime]:
    """获取场站最近的格点数据预报时刻"""
    table = _farm_table(session, farm_code)
    if not table:
        return None

    return session.execute(
        text(f"SELECT MAX(forecast_time) FROM {table}")
    ).scalar()


def get_grid_availability(session: Session, farm_code: str, target_date) -> dict:
    """获取指定日期的格点数据可用性"""
    table = _farm_table(session, farm_code)
    if not table:
        return {}

    start = datetime.combine(target_date, time.min)
    end = datetime.combine(target_date, time.max)

    row = session.execute(
        text(
            f"SELECT COUNT(*) as cnt, "
            f"       MIN(forecast_time) as min_ts, "
            f"       MAX(forecast_time) as max_ts "
            f"FROM {table} "
            f"WHERE forecast_time BETWEEN :start AND :end"
        ),
        {"start": start, "end": end},
    ).fetchone()

    if row and row[0] > 0:
        return {"DQ": {"count": row[0], "min_timestamp": row[1], "max_timestamp": row[2]}}
    return {}
