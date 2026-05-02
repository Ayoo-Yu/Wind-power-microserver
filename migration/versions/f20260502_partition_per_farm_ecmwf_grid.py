"""partition per-farm ECMWF grid tables

Revision ID: f20260502
Revises: e20260430
Create Date: 2026-05-02 00:00:00
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from alembic import op
from sqlalchemy import text


revision = "f20260502"
down_revision = "e20260430"
branch_labels = None
depends_on = None


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


def _min_max(connection, table_name: str) -> tuple[Optional[datetime], Optional[datetime]]:
    row = connection.execute(
        text(
            f"SELECT MIN(forecast_source), MAX(forecast_source) "
            f"FROM {_q(table_name)}"
        )
    ).fetchone()
    return row[0], row[1]


def _grid_tables(connection) -> list[str]:
    rows = connection.execute(
        text(
            "SELECT c.relname "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "LEFT JOIN pg_inherits i ON i.inhrelid = c.oid "
            "WHERE n.nspname = current_schema() "
            "AND c.relkind IN ('r', 'p') "
            "AND c.relname LIKE 'ecmwf_grid\\_%' ESCAPE '\\' "
            "AND c.relname NOT LIKE '%\\_legacy\\_before\\_partition' ESCAPE '\\' "
            "AND c.relname NOT LIKE '%\\_p\\_default' ESCAPE '\\' "
            "AND i.inhrelid IS NULL "
            "ORDER BY c.relname"
        )
    ).fetchall()
    return [row[0] for row in rows]


def _create_month_partition(connection, table_name: str, month: datetime):
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
        text(f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(table_name)} DEFAULT")
    )


def _create_indexes(connection, table_name: str):
    connection.execute(
        text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {_q(f'uq_{table_name}_source_time_lat_lon')} "
            f"ON {_q(table_name)} (forecast_source, forecast_time, latitude, longitude)"
        )
    )
    connection.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS {_q(f'ix_{table_name}_source_time')} "
            f"ON {_q(table_name)} (forecast_source, forecast_time)"
        )
    )
    connection.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS {_q(f'ix_{table_name}_forecast_time')} "
            f"ON {_q(table_name)} (forecast_time)"
        )
    )


def _dedupe_select_sql(table_name: str, columns: list[str]) -> str:
    column_sql = ", ".join(_q(col) for col in columns)
    order_tail = "id DESC" if "id" in columns else "1"
    return (
        f"SELECT {column_sql} FROM ("
        f"SELECT {column_sql}, ROW_NUMBER() OVER ("
        f"PARTITION BY forecast_source, forecast_time, latitude, longitude "
        f"ORDER BY forecast_source, forecast_time, latitude, longitude, {order_tail}"
        f") AS rn FROM {_q(table_name)}"
        f") AS ranked WHERE rn = 1"
    )


def _partition_grid_table(connection, table_name: str):
    columns = _columns(connection, table_name)
    required = {"forecast_source", "forecast_time", "latitude", "longitude", "features"}
    if not required.issubset(set(columns)):
        return

    if _is_partitioned(connection, table_name):
        _create_default_partition(connection, table_name)
        _create_indexes(connection, table_name)
        return

    legacy_name = f"{table_name}_legacy_before_partition"
    if _table_exists(connection, legacy_name):
        raise RuntimeError(
            f"{legacy_name} already exists. Review it before rerunning this migration."
        )

    min_value, max_value = _min_max(connection, table_name)
    connection.execute(text(f"ALTER TABLE {_q(table_name)} RENAME TO {_q(legacy_name)}"))
    connection.execute(
        text(
            f"CREATE TABLE {_q(table_name)} "
            f"(LIKE {_q(legacy_name)} INCLUDING DEFAULTS) "
            f"PARTITION BY RANGE (forecast_source)"
        )
    )

    if "id" in columns:
        seq_name = f"{table_name}_id_seq"
        connection.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {_q(seq_name)}"))
        connection.execute(
            text(
                f"ALTER TABLE {_q(table_name)} ALTER COLUMN id "
                f"SET DEFAULT nextval('{_q(seq_name)}'::regclass)"
            )
        )

    if min_value and max_value:
        for month in _iter_months(min_value, _add_month(max_value)):
            _create_month_partition(connection, table_name, month)

    today = datetime.now(timezone.utc).replace(tzinfo=None)
    for month in _iter_months(_month_start(today), _add_month(_add_month(today))):
        _create_month_partition(connection, table_name, month)

    _create_default_partition(connection, table_name)

    column_sql = ", ".join(_q(col) for col in columns)
    connection.execute(
        text(
            f"INSERT INTO {_q(table_name)} ({column_sql}) "
            f"{_dedupe_select_sql(legacy_name, columns)}"
        )
    )
    _create_indexes(connection, table_name)


def upgrade() -> None:
    connection = op.get_bind()
    for table_name in _grid_tables(connection):
        _partition_grid_table(connection, table_name)


def downgrade() -> None:
    connection = op.get_bind()
    for table_name in reversed(_grid_tables(connection)):
        legacy_name = f"{table_name}_legacy_before_partition"
        if _table_exists(connection, legacy_name) and _table_exists(connection, table_name):
            connection.execute(text(f"DROP TABLE {_q(table_name)} CASCADE"))
            connection.execute(text(f"ALTER TABLE {_q(legacy_name)} RENAME TO {_q(table_name)}"))
