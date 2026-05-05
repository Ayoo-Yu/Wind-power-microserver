"""Utilities for per-farm ECMWF grid tables."""

from datetime import datetime

from sqlalchemy import text


META_COLUMNS = {"forecast_source", "forecast_time", "latitude", "longitude"}

WIND_DERIVE_RULES = [
    ("10u", "10v", "ws10"),
    ("100u", "100v", "ws100"),
    ("200u", "200v", "ws200"),
]


def ecmwf_grid_table_name(farm_code: str) -> str:
    """Return the per-farm grid table name, for example ecmwf_grid_zyx."""
    return f"ecmwf_grid_{farm_code.lower()}"


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


def _month_start(value: datetime) -> datetime:
    return datetime(value.year, value.month, 1)


def _add_month(value: datetime) -> datetime:
    if value.month == 12:
        return datetime(value.year + 1, 1, 1)
    return datetime(value.year, value.month + 1, 1)


def _date_literal(value: datetime) -> str:
    return value.strftime("%Y-%m-%d 00:00:00")


def ensure_ecmwf_grid_month_partitions(connection, farm_code: str, forecast_sources) -> list[str]:
    """Create monthly partitions for the provided forecast source timestamps."""
    table = ecmwf_grid_table_name(farm_code)
    if not _table_exists(connection, table) or not _is_partitioned(connection, table):
        return []

    created = []
    months = sorted(
        {
            _month_start(value)
            for value in forecast_sources
            if isinstance(value, datetime)
        }
    )
    for month in months:
        next_month = _add_month(month)
        partition_name = f"{table}_p{month:%Y%m}"
        if _table_exists(connection, partition_name):
            continue
        connection.execute(
            text(
                f"CREATE TABLE {_q(partition_name)} PARTITION OF {_q(table)} "
                f"FOR VALUES FROM ('{_date_literal(month)}') TO ('{_date_literal(next_month)}')"
            )
        )
        created.append(partition_name)
    return created


def _constraint_exists(connection, table_name: str, constraint_name: str) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relname = :table_name AND c.conname = :constraint_name)"
            ),
            {"table_name": table_name, "constraint_name": constraint_name},
        ).scalar()
    )


def ensure_ecmwf_grid_table(connection, farm_code: str) -> str:
    """Ensure the per-farm grid table exists with the required UNIQUE constraint."""
    table = ecmwf_grid_table_name(farm_code)
    uq_name = f"uq_{table}_source_time_lat_lon"

    if _table_exists(connection, table):
        if not _constraint_exists(connection, table, uq_name):
            connection.execute(
                text(
                    f"ALTER TABLE {_q(table)} "
                    f"ADD CONSTRAINT {_q(uq_name)} "
                    f"UNIQUE (forecast_source, forecast_time, latitude, longitude)"
                )
            )
        return table

    connection.execute(
        text(
            f"CREATE TABLE {_q(table)} ("
            f"  id BIGSERIAL,"
            f"  forecast_source TIMESTAMP NOT NULL,"
            f"  forecast_time TIMESTAMP NOT NULL,"
            f"  latitude DOUBLE PRECISION NOT NULL,"
            f"  longitude DOUBLE PRECISION NOT NULL,"
            f"  features JSONB NOT NULL,"
            f"  CONSTRAINT {_q(uq_name)} "
            f"    UNIQUE (forecast_source, forecast_time, latitude, longitude)"
            f") PARTITION BY RANGE (forecast_source)"
        )
    )
    connection.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS {_q(f'ix_{table}_source_time')} "
            f"ON {_q(table)} (forecast_source, forecast_time)"
        )
    )
    connection.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS {_q(f'ix_{table}_forecast_time')} "
            f"ON {_q(table)} (forecast_time)"
        )
    )
    return table
