"""partition actual_power by farm then month

Revision ID: g20260502
Revises: f20260502
Create Date: 2026-05-02 20:00:00
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable

from alembic import op
from sqlalchemy import text


revision = "g20260502"
down_revision = "f20260502"
branch_labels = None
depends_on = None


TABLE_NAME = "actual_power"
LEGACY_NAME = "actual_power_legacy_before_farm_partition"
UNIQUE_INDEX = "uq_actual_power_farm_timestamp_farm_part"
FARM_INDEX = "ix_actual_power_farm_code_farm_part"
FARM_TIMESTAMP_INDEX = "ix_actual_power_farm_timestamp_farm_part"
TIMESTAMP_INDEX = "ix_actual_power_timestamp_farm_part"


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


def _partition_key(connection, table_name: str) -> str | None:
    return connection.execute(
        text(
            "SELECT pg_get_partkeydef(c.oid) "
            "FROM pg_class c "
            "JOIN pg_partitioned_table p ON p.partrelid = c.oid "
            "WHERE c.relname = :table_name"
        ),
        {"table_name": table_name},
    ).scalar()


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


def _safe_partition_token(farm_code: str) -> str:
    token = re.sub(r"[^0-9a-zA-Z]+", "_", farm_code.strip().lower()).strip("_")
    return token or "unknown"


def _distinct_farm_codes(connection, source_table: str) -> list[str]:
    rows = connection.execute(
        text(
            f"SELECT DISTINCT farm_code FROM {_q(source_table)} "
            "WHERE farm_code IS NOT NULL AND LENGTH(TRIM(farm_code)) > 0 "
            "ORDER BY farm_code"
        )
    ).fetchall()
    codes = [row[0] for row in rows]
    if _table_exists(connection, "wind_farms"):
        farm_rows = connection.execute(
            text(
                "SELECT farm_code FROM wind_farms "
                "WHERE farm_code IS NOT NULL AND LENGTH(TRIM(farm_code)) > 0 "
                "ORDER BY farm_code"
            )
        ).fetchall()
        codes.extend(row[0] for row in farm_rows)
    result = []
    seen = set()
    for code in codes:
        key = str(code).lower()
        if key not in seen:
            seen.add(key)
            result.append(str(code))
    return result


def _min_max(connection, table_name: str) -> tuple[datetime | None, datetime | None]:
    row = connection.execute(
        text(f"SELECT MIN({_q('timestamp')}), MAX({_q('timestamp')}) FROM {_q(table_name)}")
    ).fetchone()
    return row[0], row[1]


def _month_bounds(connection, source_table: str) -> list[datetime]:
    min_value, max_value = _min_max(connection, source_table)
    months = []
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


def _farm_partition_name(farm_code: str) -> str:
    return f"{TABLE_NAME}_p{_safe_partition_token(farm_code)}"


def _create_farm_partition(connection, farm_code: str) -> str:
    partition_name = _farm_partition_name(farm_code)
    if not _table_exists(connection, partition_name):
        literal = farm_code.replace("'", "''")
        connection.execute(
            text(
                f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(TABLE_NAME)} "
                f"FOR VALUES IN ('{literal}') PARTITION BY RANGE ({_q('timestamp')})"
            )
        )
    return partition_name


def _create_default_farm_partition(connection) -> str:
    partition_name = f"{TABLE_NAME}_pf_default"
    if not _table_exists(connection, partition_name):
        connection.execute(
            text(
                f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(TABLE_NAME)} "
                f"DEFAULT PARTITION BY RANGE ({_q('timestamp')})"
            )
        )
    return partition_name


def _drop_default_farm_partition(connection):
    partition_name = f"{TABLE_NAME}_pf_default"
    if _table_exists(connection, partition_name):
        connection.execute(text(f"DROP TABLE {_q(partition_name)} CASCADE"))


def _create_month_partition(connection, parent_name: str, month: datetime):
    next_month = _add_month(month)
    partition_name = f"{parent_name}_p{month:%Y%m}"
    if _table_exists(connection, partition_name):
        return
    connection.execute(
        text(
            f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(parent_name)} "
            f"FOR VALUES FROM ('{_date_literal(month)}') TO ('{_date_literal(next_month)}')"
        )
    )


def _create_default_month_partition(connection, parent_name: str):
    partition_name = f"{parent_name}_p_default"
    if _table_exists(connection, partition_name):
        return
    connection.execute(
        text(f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(parent_name)} DEFAULT")
    )


def _drop_default_month_partition(connection, parent_name: str):
    partition_name = f"{parent_name}_p_default"
    if _table_exists(connection, partition_name):
        connection.execute(text(f"DROP TABLE {_q(partition_name)}"))


def _create_indexes(connection):
    connection.execute(
        text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {_q(UNIQUE_INDEX)} "
            f"ON {_q(TABLE_NAME)} ({_q('farm_code')}, {_q('timestamp')})"
        )
    )
    connection.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS {_q(FARM_INDEX)} "
            f"ON {_q(TABLE_NAME)} ({_q('farm_code')})"
        )
    )
    connection.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS {_q(FARM_TIMESTAMP_INDEX)} "
            f"ON {_q(TABLE_NAME)} ({_q('farm_code')}, {_q('timestamp')})"
        )
    )
    connection.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS {_q(TIMESTAMP_INDEX)} "
            f"ON {_q(TABLE_NAME)} ({_q('timestamp')})"
        )
    )


def _dedupe_select_sql(source_table: str, columns: list[str]) -> str:
    column_sql = ", ".join(_q(col) for col in columns)
    order_tail = f"{_q('id')} DESC" if "id" in columns else "1"
    return (
        f"SELECT {column_sql} FROM ("
        f"SELECT {column_sql}, ROW_NUMBER() OVER ("
        f"PARTITION BY {_q('farm_code')}, {_q('timestamp')} "
        f"ORDER BY {_q('farm_code')}, {_q('timestamp')}, {order_tail}"
        f") AS rn FROM {_q(source_table)} "
        f"WHERE farm_code IS NOT NULL AND LENGTH(TRIM(farm_code)) > 0"
        f") AS ranked WHERE rn = 1"
    )


def _copy_missing_rows(connection, source_table: str, columns: list[str]):
    column_sql = ", ".join(_q(col) for col in columns)
    select_sql = _dedupe_select_sql(source_table, columns)
    connection.execute(
        text(
            f"INSERT INTO {_q(TABLE_NAME)} ({column_sql}) "
            f"SELECT {column_sql} FROM ({select_sql}) AS src "
            "WHERE NOT EXISTS ("
            f"SELECT 1 FROM {_q(TABLE_NAME)} dst "
            f"WHERE dst.{_q('farm_code')} = src.{_q('farm_code')} "
            f"AND dst.{_q('timestamp')} = src.{_q('timestamp')})"
        )
    )

    if "id" in columns:
        seq_name = f"{TABLE_NAME}_id_seq"
        connection.execute(
            text(
                f"SELECT setval('{seq_name}', "
                f"GREATEST(COALESCE((SELECT MAX(id) FROM {_q(TABLE_NAME)}), 1), 1), true)"
            )
        )


def _ensure_farm_month_partitions(connection, source_table: str):
    months = _month_bounds(connection, source_table)
    for farm_code in _distinct_farm_codes(connection, source_table):
        farm_partition = _create_farm_partition(connection, farm_code)
        for month in months:
            _create_month_partition(connection, farm_partition, month)
        _drop_default_month_partition(connection, farm_partition)

    _drop_default_farm_partition(connection)


def upgrade() -> None:
    connection = op.get_bind()
    if not _table_exists(connection, TABLE_NAME):
        return

    if _is_partitioned(connection, TABLE_NAME):
        partkey = _partition_key(connection, TABLE_NAME) or ""
        if partkey.upper().startswith("LIST") and "farm_code" in partkey:
            source_table = LEGACY_NAME if _table_exists(connection, LEGACY_NAME) else TABLE_NAME
            _ensure_farm_month_partitions(connection, source_table)
            if _table_exists(connection, LEGACY_NAME):
                _copy_missing_rows(connection, LEGACY_NAME, _columns(connection, LEGACY_NAME))
            _create_indexes(connection)
            return

    if _table_exists(connection, LEGACY_NAME):
        raise RuntimeError(
            f"{LEGACY_NAME} already exists. Review it before rerunning this migration."
        )

    columns = _columns(connection, TABLE_NAME)
    if "farm_code" not in columns or "timestamp" not in columns:
        return

    connection.execute(text(f"ALTER TABLE {_q(TABLE_NAME)} RENAME TO {_q(LEGACY_NAME)}"))
    connection.execute(
        text(
            f"CREATE TABLE {_q(TABLE_NAME)} "
            f"(LIKE {_q(LEGACY_NAME)} INCLUDING DEFAULTS) "
            f"PARTITION BY LIST ({_q('farm_code')})"
        )
    )

    if "id" in columns:
        seq_name = f"{TABLE_NAME}_id_seq"
        connection.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {_q(seq_name)}"))
        connection.execute(
            text(
                f"ALTER TABLE {_q(TABLE_NAME)} ALTER COLUMN id "
                f"SET DEFAULT nextval('{seq_name}')"
            )
        )

    _ensure_farm_month_partitions(connection, LEGACY_NAME)
    _copy_missing_rows(connection, LEGACY_NAME, columns)
    _create_indexes(connection)


def downgrade() -> None:
    connection = op.get_bind()
    if _table_exists(connection, LEGACY_NAME) and _table_exists(connection, TABLE_NAME):
        connection.execute(text(f"DROP TABLE {_q(TABLE_NAME)} CASCADE"))
        connection.execute(text(f"ALTER TABLE {_q(LEGACY_NAME)} RENAME TO {_q(TABLE_NAME)}"))
