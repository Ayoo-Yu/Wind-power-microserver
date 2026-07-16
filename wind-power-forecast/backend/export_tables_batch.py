#!/usr/bin/env python3
r"""Batch export database tables to CSV files.

Examples:
    python export_tables_batch.py D:\exports --pattern "train_pre_short_%" --pattern "train_pre_middle_%"
    python export_tables_batch.py D:\exports --table train_pre_short_zyx --table train_pre_middle_zyx
"""

from __future__ import annotations

import argparse
import os
import sys

from export_table import connect, export_table, row_count, validate_identifier


DEFAULT_PATTERNS = [
    "train_pre_short_%",
    "train_pre_middle_%",
]


def list_tables(conn, schema: str, patterns: list[str], explicit_tables: list[str]) -> list[str]:
    validate_identifier(schema, "schema")
    tables = set()

    with conn.cursor() as cur:
        for pattern in patterns:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                  AND table_name LIKE %s
                ORDER BY table_name
                """,
                (schema, pattern),
            )
            tables.update(row[0] for row in cur.fetchall())

        for table in explicit_tables:
            validate_identifier(table, "table")
            cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
                """,
                (schema, table),
            )
            if cur.fetchone() is None:
                raise ValueError(f"Table not found: {schema}.{table}")
            tables.add(table)

    return sorted(tables)


def export_tables(
    output_dir: str,
    *,
    schema: str = "public",
    patterns: list[str] | None = None,
    tables: list[str] | None = None,
    skip_empty: bool = True,
    where: str | None = None,
    order_by: str | None = None,
    limit: int | None = None,
    batch_size: int = 5000,
    encoding: str = "utf-8-sig",
) -> list[dict]:
    patterns = patterns if patterns is not None else DEFAULT_PATTERNS
    tables = tables or []
    os.makedirs(output_dir, exist_ok=True)

    conn = connect()
    try:
        selected = list_tables(conn, schema, patterns, tables)
        print(f"Selected {len(selected)} tables")

        results = []
        for table in selected:
            count = row_count(conn, schema, table, where)
            if skip_empty and count == 0:
                print(f"Skip empty table: {schema}.{table}")
                continue

            output_path = os.path.join(output_dir, f"{schema}.{table}.csv")
            print(f"Exporting {schema}.{table} ({count} rows) -> {output_path}")
            result = export_table(
                table,
                output_path,
                schema=schema,
                where=where,
                order_by=order_by,
                limit=limit,
                batch_size=batch_size,
                encoding=encoding,
            )
            results.append(result)

        return results
    finally:
        conn.close()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Batch export database tables to CSV files.")
    parser.add_argument("output_dir", help="Directory for exported CSV files")
    parser.add_argument("--schema", default="public", help="Schema name")
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        help="SQL LIKE table-name pattern. Can be specified more than once.",
    )
    parser.add_argument(
        "--table",
        action="append",
        dest="tables",
        default=[],
        help="Explicit table name. Can be specified more than once.",
    )
    parser.add_argument("--include-empty", action="store_true", help="Export empty tables too")
    parser.add_argument("--where", default=None, help="Raw SQL WHERE clause applied to every exported table")
    parser.add_argument(
        "--order-by",
        default=None,
        help='Raw SQL ORDER BY expression. Default uses "Timestamp" when present. Pass empty string to disable.',
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit per table")
    parser.add_argument("--batch-size", type=int, default=5000, help="Rows fetched per batch")
    parser.add_argument("--encoding", default="utf-8-sig", help="CSV encoding")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    patterns = args.patterns
    if patterns is None and args.tables:
        patterns = []
    results = export_tables(
        args.output_dir,
        schema=args.schema,
        patterns=patterns,
        tables=args.tables,
        skip_empty=not args.include_empty,
        where=args.where,
        order_by=args.order_by,
        limit=args.limit,
        batch_size=args.batch_size,
        encoding=args.encoding,
    )
    print(f"Done: exported {len(results)} tables")
    for result in results:
        print(f"  {result['table']}: {result['rows']} rows -> {result['output_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
