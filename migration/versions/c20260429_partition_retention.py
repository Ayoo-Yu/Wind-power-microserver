"""add monthly partitions and retention support

Revision ID: c20260429
Revises: bb635354c66d
Create Date: 2026-04-29 11:30:00
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from alembic import op
from sqlalchemy import text


revision = "c20260429"
down_revision = "bb635354c66d"
branch_labels = None
depends_on = None


PARTITIONED_TABLES = [
    {
        "table": "actual_power",
        "partition_col": "timestamp",
        "unique_name": "uq_actual_power_farm_timestamp",
        "unique_cols": ["farm_code", "timestamp"],
        "indexes": [
            ("ix_actual_power_timestamp_part", ["timestamp"]),
            ("ix_actual_power_farm_timestamp_part", ["farm_code", "timestamp"]),
        ],
    },
    {
        "table": "supershortl_power",
        "partition_col": "timestamp",
        "unique_name": "uq_supershortl_power_farm_timestamp",
        "unique_cols": ["farm_code", "timestamp"],
        "indexes": [
            ("ix_supershortl_power_timestamp_part", ["timestamp"]),
            ("ix_supershortl_power_farm_timestamp_part", ["farm_code", "timestamp"]),
        ],
    },
    {
        "table": "shortl_power",
        "partition_col": "timestamp",
        "unique_name": "uq_shortl_power_farm_timestamp_pre",
        "unique_cols": ["farm_code", "timestamp", "pre_at", "pre_num"],
        "indexes": [
            ("ix_shortl_power_timestamp_part", ["timestamp"]),
            ("ix_shortl_power_farm_timestamp_part", ["farm_code", "timestamp"]),
        ],
    },
    {
        "table": "mid_power",
        "partition_col": "timestamp",
        "unique_name": "uq_mid_power_farm_timestamp_pre",
        "unique_cols": ["farm_code", "timestamp", "pre_at", "pre_num"],
        "indexes": [
            ("ix_mid_power_timestamp_part", ["timestamp"]),
            ("ix_mid_power_farm_timestamp_part", ["farm_code", "timestamp"]),
        ],
    },
    {
        "table": "ecmwf_grid_data",
        "partition_col": "forecast_source",
        "unique_name": "uq_ecmwf_grid_source_time_lat_lon_part",
        "unique_cols": ["forecast_source", "forecast_time", "latitude", "longitude"],
        "indexes": [
            ("ix_ecmwf_grid_forecast_time_part", ["forecast_time"]),
            ("ix_ecmwf_grid_source_time_part", ["forecast_source", "forecast_time"]),
        ],
        "jsonb_gin": ("ix_ecmwf_grid_features_part", "features"),
    },
    {
        "table": "ecmwf_meteorological_data",
        "partition_col": "timestamp",
        "unique_name": "uq_ecmwf_met_ts_farm_type_part",
        "unique_cols": ["timestamp", "farm_code", "data_type"],
        "indexes": [
            ("ix_ecmwf_met_timestamp_part", ["timestamp"]),
            ("ix_ecmwf_met_farm_timestamp_part", ["farm_code", "timestamp"]),
        ],
    },
]


def _q(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _table_exists(connection, table_name: str) -> bool:
    return bool(
        connection.execute(
            text("SELECT to_regclass(:table_name) IS NOT NULL"),
            {"table_name": table_name},
        ).scalar()
    )


def _is_partitioned(connection, table_name: str) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM pg_partitioned_table p "
                "JOIN pg_class c ON c.oid = p.partrelid "
                "WHERE c.relname = :table_name)"
            ),
            {"table_name": table_name},
        ).scalar()
    )


def _columns(connection, table_name: str) -> list[str]:
    rows = connection.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :table_name "
            "ORDER BY ordinal_position"
        ),
        {"table_name": table_name},
    ).fetchall()
    return [row[0] for row in rows]


def _month_start(value: datetime) -> datetime:
    return datetime(value.year, value.month, 1)


def _add_month(value: datetime) -> datetime:
    if value.month == 12:
        return datetime(value.year + 1, 1, 1)
    return datetime(value.year, value.month + 1, 1)


def _iter_months(start: datetime, end: datetime) -> Iterable[datetime]:
    current = _month_start(start)
    stop = _month_start(end)
    while current <= stop:
        yield current
        current = _add_month(current)


def _date_literal(value: datetime) -> str:
    return value.strftime("%Y-%m-%d 00:00:00")


def _create_month_partition(connection, table_name: str, partition_col: str, month: datetime):
    next_month = _add_month(month)
    partition_name = f"{table_name}_p{month:%Y%m}"
    if _table_exists(connection, partition_name):
        return
    connection.execute(
        text(
            f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(table_name)} "
            f"FOR VALUES FROM ('{_date_literal(month)}') TO ('{_date_literal(next_month)}')"
        )
    )


def _create_default_partition(connection, table_name: str):
    partition_name = f"{table_name}_p_default"
    if _table_exists(connection, partition_name):
        return
    connection.execute(
        text(
            f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(table_name)} DEFAULT"
        )
    )


def _create_indexes(connection, config: dict):
    table_name = config["table"]
    unique_cols = ", ".join(_q(col) for col in config["unique_cols"])
    connection.execute(
        text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {_q(config['unique_name'])} "
            f"ON {_q(table_name)} ({unique_cols})"
        )
    )
    for index_name, columns in config.get("indexes", []):
        column_sql = ", ".join(_q(col) for col in columns)
        connection.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {_q(index_name)} "
                f"ON {_q(table_name)} ({column_sql})"
            )
        )
    # JSONB GIN indexes are intentionally created outside this structural migration.
    # On KingBase/PostgreSQL compatible deployments they can be expensive and should
    # be created during a separate maintenance window if feature-key queries need it.


def _dedupe_select_sql(table_name: str, columns: list[str], unique_cols: list[str]) -> str:
    column_sql = ", ".join(_q(col) for col in columns)
    partition_sql = ", ".join(_q(col) for col in unique_cols)
    order_cols = ", ".join(_q(col) for col in unique_cols)
    order_tail = f"{_q('id')} DESC" if "id" in columns else "1"
    return (
        f"SELECT {column_sql} FROM ("
        f"SELECT {column_sql}, ROW_NUMBER() OVER ("
        f"PARTITION BY {partition_sql} ORDER BY {order_cols}, {order_tail}"
        f") AS rn FROM {_q(table_name)}"
        f") AS ranked WHERE rn = 1"
    )


def _min_max(connection, table_name: str, partition_col: str) -> tuple[Optional[datetime], Optional[datetime]]:
    row = connection.execute(
        text(
            f"SELECT MIN({_q(partition_col)}), MAX({_q(partition_col)}) "
            f"FROM {_q(table_name)}"
        )
    ).fetchone()
    return row[0], row[1]


def _partition_table(connection, config: dict):
    table_name = config["table"]
    partition_col = config["partition_col"]
    if not _table_exists(connection, table_name):
        return
    if _is_partitioned(connection, table_name):
        _create_default_partition(connection, table_name)
        _create_indexes(connection, config)
        return

    legacy_name = f"{table_name}_legacy_before_partition"
    if _table_exists(connection, legacy_name):
        raise RuntimeError(
            f"{legacy_name} already exists. Review it before rerunning this migration."
        )

    min_value, max_value = _min_max(connection, table_name, partition_col)
    columns = _columns(connection, table_name)
    if partition_col not in columns:
        return

    connection.execute(text(f"ALTER TABLE {_q(table_name)} RENAME TO {_q(legacy_name)}"))
    connection.execute(
        text(
            f"CREATE TABLE {_q(table_name)} "
            f"(LIKE {_q(legacy_name)} INCLUDING DEFAULTS) "
            f"PARTITION BY RANGE ({_q(partition_col)})"
        )
    )

    # LIKE ... INCLUDING DEFAULTS may not preserve SERIAL sequences on
    # partitioned tables.  Re-attach the id sequence if the column exists.
    if "id" in columns:
        seq_name = f"{table_name}_id_seq"
        connection.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name}"))
        connection.execute(
            text(f"ALTER TABLE {_q(table_name)} ALTER COLUMN id SET DEFAULT nextval('{seq_name}')")
        )

    if min_value and max_value:
        for month in _iter_months(min_value, _add_month(max_value)):
            _create_month_partition(connection, table_name, partition_col, month)
    today = datetime.now(timezone.utc).replace(tzinfo=None)
    for month in _iter_months(_month_start(today), _add_month(_add_month(today))):
        _create_month_partition(connection, table_name, partition_col, month)
    _create_default_partition(connection, table_name)

    column_sql = ", ".join(_q(col) for col in columns)
    select_sql = _dedupe_select_sql(legacy_name, columns, config["unique_cols"])
    connection.execute(
        text(f"INSERT INTO {_q(table_name)} ({column_sql}) {select_sql}")
    )
    _create_indexes(connection, config)


def upgrade() -> None:
    connection = op.get_bind()
    for config in PARTITIONED_TABLES:
        _partition_table(connection, config)


def downgrade() -> None:
    connection = op.get_bind()
    for config in reversed(PARTITIONED_TABLES):
        table_name = config["table"]
        legacy_name = f"{table_name}_legacy_before_partition"
        if _table_exists(connection, legacy_name) and _table_exists(connection, table_name):
            connection.execute(text(f"DROP TABLE {_q(table_name)} CASCADE"))
            connection.execute(text(f"ALTER TABLE {_q(legacy_name)} RENAME TO {_q(table_name)}"))
