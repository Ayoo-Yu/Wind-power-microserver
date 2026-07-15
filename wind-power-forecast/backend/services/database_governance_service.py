"""数据库治理概览服务。"""

import os
import re
from datetime import datetime
from typing import Any

from sqlalchemy import text

from services.database_migration_service import inspect_schema_status, model_table_names


NWP_PARTITION_PATTERN = re.compile(r"^ecmwf_grid_.+_p\d{6}$")
NWP_PARENT_PATTERN = re.compile(r"^ecmwf_grid_.+$")


def classify_table(table_name: str, managed_tables: set[str]) -> str:
    """按照结构来源对数据库表分类。"""
    if NWP_PARTITION_PATTERN.match(table_name):
        return "nwp_partition"
    if NWP_PARENT_PATTERN.match(table_name):
        return "nwp_parent"
    if table_name in managed_tables:
        return "managed"
    return "unmanaged"


def _load_table_metrics(connection, managed_tables: set[str]) -> list[dict[str, Any]]:
    rows = connection.execute(text("""
        SELECT
            c.relname AS table_name,
            c.relkind AS relation_kind,
            COALESCE(s.n_live_tup, GREATEST(c.reltuples, 0), 0)::BIGINT AS estimated_rows,
            pg_total_relation_size(c.oid)::BIGINT AS total_size_bytes,
            EXISTS (
                SELECT 1 FROM pg_index pk
                WHERE pk.indrelid = c.oid AND pk.indisprimary
            ) AS has_primary_key,
            EXISTS (
                SELECT 1 FROM pg_partitioned_table pt
                WHERE pt.partrelid = c.oid
            ) AS is_partitioned,
            EXISTS (
                SELECT 1 FROM pg_inherits child
                WHERE child.inhrelid = c.oid
            ) AS is_partition
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND c.relname <> 'alembic_version'
        ORDER BY pg_total_relation_size(c.oid) DESC, c.relname
    """)).mappings().all()

    metrics = []
    quote_identifier = connection.dialect.identifier_preparer.quote
    for row in rows:
        table_name = str(row["table_name"])
        estimated_rows = int(row["estimated_rows"] or 0)
        has_data = estimated_rows > 0
        if not has_data:
            quoted_table = quote_identifier(table_name)
            has_data = bool(
                connection.execute(
                    text(f"SELECT EXISTS (SELECT 1 FROM {quoted_table} LIMIT 1)")
                ).scalar()
            )
        metrics.append({
            "table_name": table_name,
            "category": classify_table(table_name, managed_tables),
            "estimated_rows": estimated_rows,
            "total_size_bytes": int(row["total_size_bytes"] or 0),
            "has_primary_key": bool(row["has_primary_key"]),
            "is_partitioned": bool(row["is_partitioned"]),
            "is_partition": bool(row["is_partition"]),
            "has_data": has_data,
            "row_estimate_available": estimated_rows > 0,
            "empty_estimate": not has_data,
        })
    return metrics


def _load_duplicate_indexes(connection) -> list[dict[str, Any]]:
    rows = connection.execute(text("""
        SELECT
            t.relname AS table_name,
            ARRAY_AGG(i.relname ORDER BY i.relname) AS index_names,
            ix.indkey::TEXT AS column_key
        FROM pg_index ix
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'public'
          AND ix.indisvalid = TRUE
        GROUP BY
            t.relname,
            ix.indrelid,
            ix.indkey::TEXT,
            COALESCE(pg_get_expr(ix.indexprs, ix.indrelid), ''),
            COALESCE(pg_get_expr(ix.indpred, ix.indrelid), '')
        HAVING COUNT(*) > 1
        ORDER BY t.relname
    """)).mappings().all()

    return [
        {
            "table_name": str(row["table_name"]),
            "index_names": list(row["index_names"] or []),
            "column_key": str(row["column_key"] or ""),
        }
        for row in rows
    ]


def _load_constraint_counts(connection) -> dict[str, int]:
    row = connection.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE con.contype = 'f') AS foreign_keys,
            COUNT(*) FILTER (WHERE con.contype = 'u') AS unique_constraints,
            COUNT(*) FILTER (WHERE con.contype = 'p') AS primary_keys
        FROM pg_constraint con
        JOIN pg_namespace n ON n.oid = con.connamespace
        JOIN pg_class relation ON relation.oid = con.conrelid
        WHERE n.nspname = 'public'
          AND relation.relname <> 'alembic_version'
    """)).mappings().one()
    return {
        "foreign_keys": int(row["foreign_keys"] or 0),
        "unique_constraints": int(row["unique_constraints"] or 0),
        "primary_keys": int(row["primary_keys"] or 0),
    }


def _load_scada_growth(connection) -> dict[str, Any]:
    exists = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'scada_ingest_records'
        )
    """)).scalar()
    if not exists:
        return {
            "available": False,
            "last_hour_rows": 0,
            "projected_30d_rows": 0,
            "latest_received_at": None,
        }

    row = connection.execute(text("""
        SELECT
            COUNT(*) AS last_hour_rows,
            MAX(received_at) AS latest_received_at
        FROM scada_ingest_records
        WHERE received_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
    """)).mappings().one()
    last_hour_rows = int(row["last_hour_rows"] or 0)
    latest = row["latest_received_at"]
    return {
        "available": True,
        "last_hour_rows": last_hour_rows,
        "projected_30d_rows": last_hour_rows * 24 * 30,
        "latest_received_at": latest.isoformat() if latest else None,
    }


def _recommendations(
    migration: dict[str, Any],
    tables: list[dict[str, Any]],
    duplicate_indexes: list[dict[str, Any]],
    scada_growth: dict[str, Any],
) -> list[dict[str, str]]:
    recommendations = []
    if not migration["ready"]:
        recommendations.append({
            "level": "error",
            "title": "数据库结构版本未就绪",
            "detail": "请在启动业务服务前执行数据库 prepare 或 upgrade。",
        })

    empty_nwp = sum(
        1
        for table in tables
        if table["category"] == "nwp_partition" and table["empty_estimate"]
    )
    nwp_enabled = os.environ.get("NWP_INGESTION_ENABLED", "false").lower() == "true"
    if empty_nwp and not nwp_enabled:
        recommendations.append({
            "level": "warning",
            "title": f"发现 {empty_nwp} 张空的 NWP 月分区",
            "detail": "NWP 接入当前关闭，系统已停止继续预建，历史空分区可在备份后分批清理。",
        })

    if duplicate_indexes:
        recommendations.append({
            "level": "info",
            "title": f"发现 {len(duplicate_indexes)} 组潜在重复索引",
            "detail": "删除前需要比较约束用途和查询计划，避免影响唯一性校验。",
        })

    if scada_growth["projected_30d_rows"] >= 1_000_000:
        recommendations.append({
            "level": "warning",
            "title": "SCADA 审计记录增长较快",
            "detail": "建议按接收时间分区，并对普通更新记录配置采样与保留策略。",
        })

    if not recommendations:
        recommendations.append({
            "level": "success",
            "title": "当前未发现需要立即处理的结构问题",
            "detail": "继续通过迁移文件管理所有结构变化。",
        })
    return recommendations


def build_database_overview(engine) -> dict[str, Any]:
    """生成供管理员页面展示的只读数据库治理概览。"""
    migration = inspect_schema_status(engine)
    managed_tables = model_table_names()
    with engine.connect() as connection:
        tables = _load_table_metrics(connection, managed_tables)
        duplicate_indexes = _load_duplicate_indexes(connection)
        constraints = _load_constraint_counts(connection)
        scada_growth = _load_scada_growth(connection)
        database_name = str(connection.execute(text("SELECT current_database()")).scalar() or "")

    total_size_bytes = sum(table["total_size_bytes"] for table in tables)
    empty_count = sum(1 for table in tables if table["empty_estimate"])
    without_primary_key = sum(1 for table in tables if not table["has_primary_key"])
    categories = {}
    for table in tables:
        categories[table["category"]] = categories.get(table["category"], 0) + 1

    return {
        "generated_at": datetime.now().isoformat(),
        "database": {
            "name": database_name,
            "schema": "public",
        },
        "migration": migration,
        "summary": {
            "total_tables": len(tables),
            "managed_tables": migration["model_table_count"],
            "dynamic_tables": categories.get("nwp_parent", 0) + categories.get("nwp_partition", 0),
            "empty_estimate_tables": empty_count,
            "without_primary_key_tables": without_primary_key,
            "total_size_bytes": total_size_bytes,
            "duplicate_index_groups": len(duplicate_indexes),
            **constraints,
        },
        "categories": categories,
        "scada_growth": scada_growth,
        "recommendations": _recommendations(
            migration,
            tables,
            duplicate_indexes,
            scada_growth,
        ),
        "duplicate_indexes": duplicate_indexes,
        "tables": tables,
    }
