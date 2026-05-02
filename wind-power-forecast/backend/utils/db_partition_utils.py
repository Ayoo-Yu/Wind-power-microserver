"""Shared database utility functions for partitioning, retention, and import."""

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import text


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def table_exists(connection, table_name: str) -> bool:
    return bool(
        connection.execute(
            text("SELECT to_regclass(:table_name) IS NOT NULL"),
            {"table_name": table_name},
        ).scalar()
    )


def is_partitioned(connection, table_name: str) -> bool:
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


def month_start(value: datetime) -> datetime:
    return datetime(value.year, value.month, 1)


def add_month(value: datetime) -> datetime:
    if value.month == 12:
        return datetime(value.year + 1, 1, 1)
    return datetime(value.year, value.month + 1, 1)


def iter_months(start: datetime, count: int) -> Iterable[datetime]:
    current = month_start(start)
    for _ in range(count):
        yield current
        current = add_month(current)


def iter_months_range(start: datetime, end: datetime) -> Iterable[datetime]:
    current = month_start(start)
    stop = month_start(end)
    while current <= stop:
        yield current
        current = add_month(current)


def date_literal(value: datetime) -> str:
    return value.strftime("%Y-%m-%d 00:00:00")


def parse_timestamp(value) -> datetime:
    """Parse ECMWF-style timestamps from various formats."""
    if isinstance(value, datetime):
        return value
    import pandas as pd
    raw = str(int(value)) if isinstance(value, float) else str(value).strip()
    for fmt in ("%Y%m%d%H%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    parsed = pd.to_datetime(raw, errors="coerce")
    if not pd.isna(parsed):
        return parsed.to_pydatetime()
    raise ValueError(f"cannot parse timestamp: {value}")


def get_table_columns(connection, table_name: str) -> list[str]:
    rows = connection.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :table_name "
            "ORDER BY ordinal_position"
        ),
        {"table_name": table_name},
    ).fetchall()
    return [row[0] for row in rows]
