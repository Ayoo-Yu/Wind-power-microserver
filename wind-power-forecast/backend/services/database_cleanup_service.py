"""数据库中动态生成结构的安全清理服务。"""

from __future__ import annotations

import os
import re
from typing import Any

from sqlalchemy import text


NWP_TABLE_PATTERN = re.compile(r"^ecmwf_grid_[a-z0-9_]+$")


def _nwp_ingestion_enabled() -> bool:
    return os.environ.get("NWP_INGESTION_ENABLED", "false").lower() == "true"


def _load_nwp_tables(connection) -> list[dict[str, Any]]:
    rows = connection.execute(text("""
        SELECT
            c.relname AS table_name,
            pg_total_relation_size(c.oid)::BIGINT AS total_size_bytes,
            EXISTS (
                SELECT 1 FROM pg_inherits parent_link
                WHERE parent_link.inhrelid = c.oid
            ) AS is_partition
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND c.relname LIKE 'ecmwf_grid_%'
        ORDER BY is_partition DESC, c.relname
    """)).mappings().all()

    quote_identifier = connection.dialect.identifier_preparer.quote
    tables = []
    for row in rows:
        table_name = str(row["table_name"])
        if not NWP_TABLE_PATTERN.fullmatch(table_name):
            continue
        quoted_table = quote_identifier(table_name)
        has_data = bool(
            connection.execute(
                text(f"SELECT EXISTS (SELECT 1 FROM {quoted_table} LIMIT 1)")
            ).scalar()
        )
        tables.append({
            "table_name": table_name,
            "is_partition": bool(row["is_partition"]),
            "has_data": has_data,
            "total_size_bytes": int(row["total_size_bytes"] or 0),
        })
    return tables


def plan_empty_nwp_cleanup(engine) -> dict[str, Any]:
    """生成空 NWP 动态表清理计划，不修改数据库。"""
    with engine.connect() as connection:
        tables = _load_nwp_tables(connection)

    data_tables = [item["table_name"] for item in tables if item["has_data"]]
    enabled = _nwp_ingestion_enabled()
    allowed = bool(tables) and not enabled and not data_tables
    if enabled:
        reason = "NWP 数据接入当前已启用，拒绝清理动态表"
    elif data_tables:
        reason = "存在包含数据的 NWP 表，拒绝自动清理"
    elif not tables:
        reason = "当前没有可清理的 NWP 动态表"
    else:
        reason = "全部 NWP 动态表为空，可以执行清理"

    return {
        "allowed": allowed,
        "reason": reason,
        "nwp_ingestion_enabled": enabled,
        "table_count": len(tables),
        "partition_count": sum(1 for item in tables if item["is_partition"]),
        "parent_count": sum(1 for item in tables if not item["is_partition"]),
        "total_size_bytes": sum(item["total_size_bytes"] for item in tables),
        "data_tables": data_tables,
        "tables": tables,
    }


def cleanup_empty_nwp_tables(engine, *, apply: bool = False) -> dict[str, Any]:
    """在显式确认后，以单事务清理全部空 NWP 动态表。"""
    plan = plan_empty_nwp_cleanup(engine)
    if not apply:
        return {**plan, "applied": False, "dropped_tables": []}
    if not plan["allowed"]:
        raise RuntimeError(plan["reason"])

    with engine.begin() as connection:
        fresh_tables = _load_nwp_tables(connection)
        if any(item["has_data"] for item in fresh_tables):
            raise RuntimeError("清理前检测到 NWP 表已有数据，操作已取消")
        fresh_names = {item["table_name"] for item in fresh_tables}
        planned_names = {item["table_name"] for item in plan["tables"]}
        if fresh_names != planned_names:
            raise RuntimeError("NWP 表清单在确认后发生变化，操作已取消")

        quote_identifier = connection.dialect.identifier_preparer.quote
        dropped_tables = []
        for item in fresh_tables:
            table_name = item["table_name"]
            connection.execute(text(f"DROP TABLE {quote_identifier(table_name)}"))
            dropped_tables.append(table_name)

    return {**plan, "applied": True, "dropped_tables": dropped_tables}
