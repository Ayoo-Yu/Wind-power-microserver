import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text

from database_config import engine
from utils.db_partition_utils import (
    quote_identifier as _q,
    table_exists,
    is_partitioned,
    month_start,
    add_month,
    iter_months,
    date_literal,
    get_table_columns,
)
from db_models.ecmwf_grid_model import ecmwf_grid_table_name
from db_models.ecmwf_grid_model import ensure_ecmwf_grid_table


logger = logging.getLogger(__name__)

PARTITION_MONTHS_AHEAD = int(os.environ.get("PARTITION_MONTHS_AHEAD", "6"))
NWP_INGESTION_ENABLED = os.environ.get("NWP_INGESTION_ENABLED", "false").lower() == "true"


@dataclass(frozen=True)
class PartitionedTable:
    table_name: str
    partition_column: str


FARM_MONTH_TABLES = [
    PartitionedTable("actual_power", "timestamp"),
    PartitionedTable("supershortl_power", "timestamp"),
    PartitionedTable("shortl_power", "timestamp"),
    PartitionedTable("mid_power", "timestamp"),
    PartitionedTable("train_pre_middle", "Timestamp"),
    PartitionedTable("train_pre_short", "Timestamp"),
    PartitionedTable("train_pre_supershort", "Timestamp"),
]


def _create_month_partition(connection, table_name: str, month: datetime) -> bool:
    next_month = add_month(month)
    partition_name = f"{table_name}_p{month:%Y%m}"
    if table_exists(connection, partition_name):
        return False
    connection.execute(
        text(
            f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(table_name)} "
            f"FOR VALUES FROM ('{date_literal(month)}') TO ('{date_literal(next_month)}')"
        )
    )
    return True


def _safe_partition_token(value: str) -> str:
    token = re.sub(r"[^0-9a-zA-Z]+", "_", str(value).strip().lower()).strip("_")
    return token or "unknown"


def _farm_partition_name(table_name: str, farm_code: str) -> str:
    return f"{table_name}_p{_safe_partition_token(farm_code)}"


def _partition_key(connection, table_name: str) -> str:
    return str(
        connection.execute(
            text(
                "SELECT pg_get_partkeydef(c.oid) "
                "FROM pg_class c "
                "JOIN pg_partitioned_table p ON p.partrelid = c.oid "
                "WHERE c.relname = :table_name"
            ),
            {"table_name": table_name},
        ).scalar()
        or ""
    )


def _create_farm_partition(connection, table: PartitionedTable, farm_code: str) -> str:
    partition_name = _farm_partition_name(table.table_name, farm_code)
    if not table_exists(connection, partition_name):
        literal = str(farm_code).replace("'", "''")
        connection.execute(
            text(
                f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(table.table_name)} "
                f"FOR VALUES IN ('{literal}') PARTITION BY RANGE ({_q(table.partition_column)})"
            )
        )
    return partition_name


def _drop_farm_default_partition(connection, table_name: str):
    partition_name = f"{table_name}_pf_default"
    if table_exists(connection, partition_name):
        connection.execute(text(f"DROP TABLE {_q(partition_name)} CASCADE"))


def _active_farm_codes(connection) -> list[str]:
    if not table_exists(connection, "wind_farms"):
        return []
    rows = connection.execute(
        text(
            "SELECT farm_code FROM wind_farms "
            "WHERE COALESCE(is_active, TRUE) = TRUE "
            "AND farm_code IS NOT NULL AND LENGTH(TRIM(farm_code)) > 0 "
            "ORDER BY farm_code"
        )
    ).fetchall()
    return [str(row[0]) for row in rows]


def _create_farm_month_future_partitions(
    connection,
    table: PartitionedTable,
    farm_codes: list[str],
    months: list[datetime],
) -> dict:
    if not table_exists(connection, table.table_name):
        return {"table": table.table_name, "skipped": "table_missing"}
    if not is_partitioned(connection, table.table_name):
        return {"table": table.table_name, "skipped": "not_partitioned"}

    partkey = _partition_key(connection, table.table_name)
    if not partkey.upper().startswith("LIST") or "farm_code" not in partkey:
        return {"table": table.table_name, "skipped": "not_farm_partitioned"}

    created = []
    moved_default_rows = 0
    for farm_code in farm_codes:
        farm_partition = _create_farm_partition(connection, table, farm_code)
        for month in months:
            if _create_month_partition(connection, farm_partition, month):
                created.append(f"{farm_partition}_p{month:%Y%m}")
        _drop_default_partition(connection, farm_partition)

    _drop_farm_default_partition(connection, table.table_name)

    return {
        "table": table.table_name,
        "created_partitions": created,
        "moved_default_rows": moved_default_rows,
        "skipped": None,
    }


def _default_partition_exists(connection, table_name: str) -> bool:
    return table_exists(connection, f"{table_name}_p_default")


def _drop_default_partition(connection, table_name: str):
    default_name = f"{table_name}_p_default"
    if table_exists(connection, default_name):
        connection.execute(text(f"DROP TABLE {_q(default_name)}"))


def _detach_default_partition(connection, table_name: str):
    default_name = f"{table_name}_p_default"
    connection.execute(
        text(f"ALTER TABLE {_q(table_name)} DETACH PARTITION {_q(default_name)}")
    )


def _attach_default_partition(connection, table_name: str):
    default_name = f"{table_name}_p_default"
    connection.execute(
        text(f"ALTER TABLE {_q(table_name)} ATTACH PARTITION {_q(default_name)} DEFAULT")
    )


def _move_default_rows(connection, table: PartitionedTable) -> int:
    default_name = f"{table.table_name}_p_default"
    if not _default_partition_exists(connection, table.table_name):
        return 0

    count = int(
        connection.execute(text(f"SELECT COUNT(*) FROM {_q(default_name)}")).scalar() or 0
    )
    if count == 0:
        return 0

    # Must detach default BEFORE creating partitions for its data,
    # otherwise PostgreSQL rejects: "updated partition constraint for
    # default partition would be violated by some row"
    _detach_default_partition(connection, table.table_name)
    try:
        # Discover which months exist in the default partition and create them
        col = _q(table.partition_column)
        months = connection.execute(
            text(
                f"SELECT DISTINCT date_trunc('month', {col})::date AS m "
                f"FROM {_q(default_name)}"
            )
        ).fetchall()
        for (month_val,) in months:
            if month_val is not None:
                _create_month_partition(connection, table.table_name, month_val)

        # Now move rows — they'll route to the correct monthly partitions
        columns = get_table_columns(connection, default_name)
        column_sql = ", ".join(_q(c) for c in columns)
        connection.execute(
            text(
                f"INSERT INTO {_q(table.table_name)} ({column_sql}) "
                f"SELECT {column_sql} FROM {_q(default_name)}"
            )
        )
        connection.execute(text(f"TRUNCATE TABLE {_q(default_name)}"))
    finally:
        _attach_default_partition(connection, table.table_name)

    return count


def ensure_future_partitions(
    months_ahead: int = PARTITION_MONTHS_AHEAD,
    now: Optional[datetime] = None,
) -> dict:
    now = now or datetime.now()
    month_count = max(1, months_ahead + 1)
    results = []

    with engine.begin() as connection:
        months = list(iter_months(now, month_count))
        farm_codes = _active_farm_codes(connection)
        for table in FARM_MONTH_TABLES:
            results.append(
                _create_farm_month_future_partitions(
                    connection,
                    table,
                    farm_codes,
                    months,
                )
            )

        # NWP 接入关闭时不创建任何 ECMWF 场站表和月分区。
        if NWP_INGESTION_ENABLED:
            for fc in farm_codes:
                ensure_ecmwf_grid_table(connection, fc)
                ecmwf_table = ecmwf_grid_table_name(fc)
                if not table_exists(connection, ecmwf_table):
                    results.append({"table": ecmwf_table, "skipped": "table_missing"})
                    continue
                if not is_partitioned(connection, ecmwf_table):
                    results.append({"table": ecmwf_table, "skipped": "not_partitioned"})
                    continue

                created = []
                for month in months:
                    if _create_month_partition(connection, ecmwf_table, month):
                        created.append(f"{ecmwf_table}_p{month:%Y%m}")

                ecmwf_pt = PartitionedTable(ecmwf_table, "forecast_source")
                moved_default_rows = _move_default_rows(connection, ecmwf_pt)
                results.append(
                    {
                        "table": ecmwf_table,
                        "created_partitions": created,
                        "moved_default_rows": moved_default_rows,
                        "skipped": None,
                    }
                )

    logger.info("Partition maintenance complete: %s", results)
    return {
        "months_ahead": months_ahead,
        "nwp_ingestion_enabled": NWP_INGESTION_ENABLED,
        "tables": results,
    }
