"""partition power and train tables by farm then month

Revision ID: h20260502
Revises: g20260502
Create Date: 2026-05-02 21:30:00
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Iterable

from alembic import op
from sqlalchemy import text


revision = "h20260502"
down_revision = "g20260502"
branch_labels = None
depends_on = None


TABLE_CONFIGS = [
    {
        "table": "supershortl_power",
        "time_col": "timestamp",
        "id_col": "id",
        "unique_cols": ["farm_code", "timestamp"],
        "indexes": [
            ("uq_supershortl_power_farm_timestamp_farm_part", ["farm_code", "timestamp"], True),
            ("ix_supershortl_power_farm_code_farm_part", ["farm_code"], False),
            ("ix_supershortl_power_farm_timestamp_farm_part", ["farm_code", "timestamp"], False),
            ("ix_supershortl_power_timestamp_farm_part", ["timestamp"], False),
        ],
    },
    {
        "table": "shortl_power",
        "time_col": "timestamp",
        "id_col": "id",
        "unique_cols": ["farm_code", "timestamp", "pre_at", "pre_num"],
        "indexes": [
            ("uq_shortl_power_farm_timestamp_pre_farm_part", ["farm_code", "timestamp", "pre_at", "pre_num"], True),
            ("ix_shortl_power_farm_code_farm_part", ["farm_code"], False),
            ("ix_shortl_power_farm_timestamp_farm_part", ["farm_code", "timestamp"], False),
            ("ix_shortl_power_timestamp_farm_part", ["timestamp"], False),
        ],
    },
    {
        "table": "mid_power",
        "time_col": "timestamp",
        "id_col": "id",
        "unique_cols": ["farm_code", "timestamp", "pre_at", "pre_num"],
        "indexes": [
            ("uq_mid_power_farm_timestamp_pre_farm_part", ["farm_code", "timestamp", "pre_at", "pre_num"], True),
            ("ix_mid_power_farm_code_farm_part", ["farm_code"], False),
            ("ix_mid_power_farm_timestamp_farm_part", ["farm_code", "timestamp"], False),
            ("ix_mid_power_timestamp_farm_part", ["timestamp"], False),
        ],
    },
    {
        "table": "train_pre_middle",
        "time_col": "Timestamp",
        "id_col": "record_id",
        "unique_cols": ["farm_code", "Timestamp"],
        "indexes": [
            ("ix_train_pre_middle_farm_code_farm_part", ["farm_code"], False),
            ("ix_train_pre_middle_farm_timestamp_farm_part", ["farm_code", "Timestamp"], False),
            ("ix_train_pre_middle_timestamp_farm_part", ["Timestamp"], False),
        ],
    },
    {
        "table": "train_pre_short",
        "time_col": "Timestamp",
        "id_col": "record_id",
        "unique_cols": ["farm_code", "Timestamp"],
        "indexes": [
            ("ix_train_pre_short_farm_code_farm_part", ["farm_code"], False),
            ("ix_train_pre_short_farm_timestamp_farm_part", ["farm_code", "Timestamp"], False),
            ("ix_train_pre_short_timestamp_farm_part", ["Timestamp"], False),
        ],
    },
    {
        "table": "train_pre_supershort",
        "time_col": "Timestamp",
        "id_col": "record_id",
        "unique_cols": ["farm_code", "Timestamp"],
        "indexes": [
            ("ix_train_pre_supershort_farm_code_farm_part", ["farm_code"], False),
            ("ix_train_pre_supershort_farm_timestamp_farm_part", ["farm_code", "Timestamp"], False),
            ("ix_train_pre_supershort_timestamp_farm_part", ["Timestamp"], False),
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


def _safe_partition_token(value: str) -> str:
    token = re.sub(r"[^0-9a-zA-Z]+", "_", str(value).strip().lower()).strip("_")
    return token or "unknown"


def _farm_partition_name(table_name: str, farm_code: str) -> str:
    return f"{table_name}_p{_safe_partition_token(farm_code)}"


def _distinct_farm_codes(connection, source_table: str) -> list[str]:
    codes = []
    if _table_exists(connection, source_table) and "farm_code" in _columns(connection, source_table):
        rows = connection.execute(
            text(
                f"SELECT DISTINCT farm_code FROM {_q(source_table)} "
                "WHERE farm_code IS NOT NULL AND LENGTH(TRIM(farm_code)) > 0 "
                "ORDER BY farm_code"
            )
        ).fetchall()
        codes.extend(row[0] for row in rows)

    if _table_exists(connection, "wind_farms"):
        rows = connection.execute(
            text(
                "SELECT farm_code FROM wind_farms "
                "WHERE farm_code IS NOT NULL AND LENGTH(TRIM(farm_code)) > 0 "
                "ORDER BY farm_code"
            )
        ).fetchall()
        codes.extend(row[0] for row in rows)

    result = []
    seen = set()
    for code in codes:
        key = str(code).lower()
        if key not in seen:
            seen.add(key)
            result.append(str(code))
    return result


def _min_max(connection, table_name: str, time_col: str) -> tuple[datetime | None, datetime | None]:
    row = connection.execute(
        text(f"SELECT MIN({_q(time_col)}), MAX({_q(time_col)}) FROM {_q(table_name)}")
    ).fetchone()
    return row[0], row[1]


def _month_bounds(connection, source_table: str, time_col: str) -> list[datetime]:
    months = []
    if _table_exists(connection, source_table) and time_col in _columns(connection, source_table):
        min_value, max_value = _min_max(connection, source_table, time_col)
        if min_value and max_value:
            months.extend(_iter_months(min_value, _add_month(max_value)))

    today = datetime.now(timezone.utc).replace(tzinfo=None)
    months.extend(_iter_months(_month_start(today), _add_month(_add_month(today))))

    unique = []
    seen = set()
    for month in months:
        key = month.strftime("%Y%m")
        if key not in seen:
            seen.add(key)
            unique.append(month)
    return unique


def _ensure_farm_code_column(connection, table_name: str):
    columns = _columns(connection, table_name)
    if "farm_code" in columns:
        return

    row_count = int(connection.execute(text(f"SELECT COUNT(*) FROM {_q(table_name)}")).scalar() or 0)
    connection.execute(text(f"ALTER TABLE {_q(table_name)} ADD COLUMN farm_code VARCHAR(50)"))
    if row_count:
        default_farm = os.environ.get("DEFAULT_FARM_CODE", "").strip()
        if not default_farm:
            raise RuntimeError(f"{table_name} has rows but no farm_code column")
        connection.execute(
            text(f"UPDATE {_q(table_name)} SET farm_code = :farm_code WHERE farm_code IS NULL"),
            {"farm_code": default_farm},
        )
    connection.execute(text(f"ALTER TABLE {_q(table_name)} ALTER COLUMN farm_code SET NOT NULL"))


def _create_farm_partition(connection, table_name: str, time_col: str, farm_code: str) -> str:
    partition_name = _farm_partition_name(table_name, farm_code)
    if not _table_exists(connection, partition_name):
        literal = farm_code.replace("'", "''")
        connection.execute(
            text(
                f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(table_name)} "
                f"FOR VALUES IN ('{literal}') PARTITION BY RANGE ({_q(time_col)})"
            )
        )
    return partition_name


def _create_month_partition(connection, parent_name: str, month: datetime):
    partition_name = f"{parent_name}_p{month:%Y%m}"
    if _table_exists(connection, partition_name):
        return
    connection.execute(
        text(
            f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(parent_name)} "
            f"FOR VALUES FROM ('{_date_literal(month)}') TO ('{_date_literal(_add_month(month))}')"
        )
    )


def _drop_default_partition(connection, table_name: str):
    partition_name = f"{table_name}_p_default"
    if _table_exists(connection, partition_name):
        connection.execute(text(f"DROP TABLE {_q(partition_name)} CASCADE"))


def _ensure_partitions(connection, config: dict, source_table: str):
    months = _month_bounds(connection, source_table, config["time_col"])
    for farm_code in _distinct_farm_codes(connection, source_table):
        farm_partition = _create_farm_partition(
            connection, config["table"], config["time_col"], farm_code
        )
        for month in months:
            _create_month_partition(connection, farm_partition, month)
        _drop_default_partition(connection, farm_partition)
    _drop_default_partition(connection, config["table"])


def _create_indexes(connection, config: dict):
    table_name = config["table"]
    for index_name, columns, is_unique in config["indexes"]:
        column_sql = ", ".join(_q(column) for column in columns)
        unique_sql = "UNIQUE " if is_unique else ""
        connection.execute(
            text(
                f"CREATE {unique_sql}INDEX IF NOT EXISTS {_q(index_name)} "
                f"ON {_q(table_name)} ({column_sql})"
            )
        )


def _dedupe_select_sql(source_table: str, columns: list[str], unique_cols: list[str]) -> str:
    column_sql = ", ".join(_q(col) for col in columns)
    partition_sql = ", ".join(_q(col) for col in unique_cols)
    order_sql = ", ".join(_q(col) for col in unique_cols)
    order_tail = _q("id") + " DESC" if "id" in columns else _q("record_id") + " DESC" if "record_id" in columns else "1"
    return (
        f"SELECT {column_sql} FROM ("
        f"SELECT {column_sql}, ROW_NUMBER() OVER ("
        f"PARTITION BY {partition_sql} ORDER BY {order_sql}, {order_tail}"
        f") AS rn FROM {_q(source_table)} "
        "WHERE farm_code IS NOT NULL AND LENGTH(TRIM(farm_code)) > 0"
        f") AS ranked WHERE rn = 1"
    )


def _copy_missing_rows(connection, config: dict, source_table: str):
    columns = _columns(connection, source_table)
    column_sql = ", ".join(_q(col) for col in columns)
    select_sql = _dedupe_select_sql(source_table, columns, config["unique_cols"])
    exists_predicate = " AND ".join(
        f"dst.{_q(col)} = src.{_q(col)}" for col in config["unique_cols"]
    )
    connection.execute(
        text(
            f"INSERT INTO {_q(config['table'])} ({column_sql}) "
            f"SELECT {column_sql} FROM ({select_sql}) AS src "
            f"WHERE NOT EXISTS (SELECT 1 FROM {_q(config['table'])} dst WHERE {exists_predicate})"
        )
    )

    id_col = config.get("id_col")
    if id_col and id_col in columns:
        seq_name = f"{config['table']}_{id_col}_seq"
        connection.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {_q(seq_name)}"))
        connection.execute(
            text(
                f"SELECT setval('{seq_name}', "
                f"GREATEST(COALESCE((SELECT MAX({_q(id_col)}) FROM {_q(config['table'])}), 1), 1), true)"
            )
        )


def _convert_table(connection, config: dict):
    table_name = config["table"]
    legacy_name = f"{table_name}_legacy_before_farm_partition"
    if not _table_exists(connection, table_name):
        return

    if _is_partitioned(connection, table_name):
        partkey = _partition_key(connection, table_name)
        if partkey.upper().startswith("LIST") and "farm_code" in partkey:
            source_table = legacy_name if _table_exists(connection, legacy_name) else table_name
            _ensure_partitions(connection, config, source_table)
            if _table_exists(connection, legacy_name):
                _copy_missing_rows(connection, config, legacy_name)
            _create_indexes(connection, config)
            return

    if _table_exists(connection, legacy_name):
        raise RuntimeError(f"{legacy_name} already exists. Review it before rerunning this migration.")

    _ensure_farm_code_column(connection, table_name)
    columns = _columns(connection, table_name)
    if "farm_code" not in columns or config["time_col"] not in columns:
        return

    connection.execute(text(f"ALTER TABLE {_q(table_name)} RENAME TO {_q(legacy_name)}"))
    connection.execute(
        text(
            f"CREATE TABLE {_q(table_name)} "
            f"(LIKE {_q(legacy_name)} INCLUDING DEFAULTS) "
            "PARTITION BY LIST (farm_code)"
        )
    )

    id_col = config.get("id_col")
    if id_col and id_col in columns:
        seq_name = f"{table_name}_{id_col}_seq"
        connection.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {_q(seq_name)}"))
        connection.execute(
            text(
                f"ALTER TABLE {_q(table_name)} ALTER COLUMN {_q(id_col)} "
                f"SET DEFAULT nextval('{seq_name}')"
            )
        )

    _ensure_partitions(connection, config, legacy_name)
    _copy_missing_rows(connection, config, legacy_name)
    _create_indexes(connection, config)


def upgrade() -> None:
    connection = op.get_bind()
    for config in TABLE_CONFIGS:
        _convert_table(connection, config)


def downgrade() -> None:
    connection = op.get_bind()
    for config in reversed(TABLE_CONFIGS):
        table_name = config["table"]
        legacy_name = f"{table_name}_legacy_before_farm_partition"
        if _table_exists(connection, legacy_name) and _table_exists(connection, table_name):
            connection.execute(text(f"DROP TABLE {_q(table_name)} CASCADE"))
            connection.execute(text(f"ALTER TABLE {_q(legacy_name)} RENAME TO {_q(table_name)}"))
