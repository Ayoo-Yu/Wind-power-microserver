#!/usr/bin/env python3
r"""Stream database tables to CSV files.

Examples:
    python export_table.py train_pre_short_zyx D:\exports\train_pre_short_zyx.csv
    python export_table.py train_pre_short_zyx D:\exports\zyx_202605.csv --where "\"Timestamp\" >= '2026-05-01' AND \"Timestamp\" < '2026-06-01'"
"""

import argparse
import csv
import os
import re
import sys
from typing import Iterable, Optional

import psycopg2
from psycopg2 import sql

from config import KINGBASE_CONFIG


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def connect():
    return psycopg2.connect(
        host=KINGBASE_CONFIG["host"],
        port=int(KINGBASE_CONFIG["port"]),
        user=KINGBASE_CONFIG["user"],
        password=KINGBASE_CONFIG["password"],
        database=KINGBASE_CONFIG["database"],
        connect_timeout=10,
    )


def validate_identifier(value: str, label: str) -> str:
    if not IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def table_exists(conn, schema: str, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
            """,
            (schema, table),
        )
        return cur.fetchone() is not None


def get_table_columns(conn, schema: str, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        return [row[0] for row in cur.fetchall()]


def row_count(conn, schema: str, table: str, where: Optional[str] = None) -> int:
    stmt = sql.SQL("SELECT count(*) FROM {}.{}").format(
        sql.Identifier(schema),
        sql.Identifier(table),
    )
    if where:
        stmt += sql.SQL(" WHERE ") + sql.SQL(where)
    with conn.cursor() as cur:
        cur.execute(stmt)
        return int(cur.fetchone()[0])


def build_order_by(columns: Iterable[str], requested: Optional[str]) -> Optional[sql.SQL]:
    if requested == "":
        return None
    if requested:
        return sql.SQL(requested)
    if "Timestamp" in columns:
        return sql.Identifier("Timestamp")
    if "timestamp" in columns:
        return sql.Identifier("timestamp")
    return None


def export_table(
    table: str,
    output_path: str,
    *,
    schema: str = "public",
    where: Optional[str] = None,
    order_by: Optional[str] = None,
    limit: Optional[int] = None,
    batch_size: int = 5000,
    encoding: str = "utf-8-sig",
    delimiter: str = ",",
) -> dict:
    validate_identifier(schema, "schema")
    validate_identifier(table, "table")
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0")
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

    conn = connect()
    try:
        if not table_exists(conn, schema, table):
            raise ValueError(f"Table not found: {schema}.{table}")

        columns = get_table_columns(conn, schema, table)
        if not columns:
            raise ValueError(f"Table has no columns: {schema}.{table}")

        total_rows = row_count(conn, schema, table, where)
        if limit is not None:
            total_rows = min(total_rows, limit)

        stmt = sql.SQL("SELECT * FROM {}.{}").format(
            sql.Identifier(schema),
            sql.Identifier(table),
        )
        if where:
            stmt += sql.SQL(" WHERE ") + sql.SQL(where)
        order_sql = build_order_by(columns, order_by)
        if order_sql is not None:
            stmt += sql.SQL(" ORDER BY ") + order_sql
        if limit is not None:
            stmt += sql.SQL(" LIMIT {}").format(sql.Literal(limit))

        cursor_name = f"export_{table[:40]}"
        cur = conn.cursor(name=cursor_name)
        cur.itersize = batch_size
        cur.execute(stmt)

        written = 0
        with open(output_path, "w", newline="", encoding=encoding) as f:
            writer = csv.writer(f, delimiter=delimiter, lineterminator="\n")
            writer.writerow(columns)
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                writer.writerows(rows)
                written += len(rows)
                print(f"{table}: exported {written}/{total_rows} rows", flush=True)

        cur.close()
        return {
            "schema": schema,
            "table": table,
            "output_path": os.path.abspath(output_path),
            "rows": written,
            "columns": len(columns),
        }
    finally:
        conn.close()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Stream a database table to CSV.")
    parser.add_argument("table", help="Table name, for example train_pre_short_zyx")
    parser.add_argument("output", help="Output CSV path")
    parser.add_argument("--schema", default="public", help="Schema name")
    parser.add_argument("--where", default=None, help="Raw SQL WHERE clause without the WHERE keyword")
    parser.add_argument(
        "--order-by",
        default=None,
        help='Raw SQL ORDER BY expression. Default uses "Timestamp" when present. Pass empty string to disable.',
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit")
    parser.add_argument("--batch-size", type=int, default=5000, help="Rows fetched per batch")
    parser.add_argument("--encoding", default="utf-8-sig", help="CSV encoding")
    parser.add_argument("--delimiter", default=",", help="CSV delimiter")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    result = export_table(
        args.table,
        args.output,
        schema=args.schema,
        where=args.where,
        order_by=args.order_by,
        limit=args.limit,
        batch_size=args.batch_size,
        encoding=args.encoding,
        delimiter=args.delimiter,
    )
    print(
        f"Done: {result['schema']}.{result['table']} -> {result['output_path']} "
        f"({result['rows']} rows, {result['columns']} columns)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
