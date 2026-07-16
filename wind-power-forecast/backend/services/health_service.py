"""应用存活与数据库就绪探针。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text


logger = logging.getLogger(__name__)


def _checked_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_liveness_status() -> dict:
    """返回仅表示 Web 进程仍可响应的存活状态。"""

    return {
        "status": "ok",
        "service": "wind-power-backend",
        "liveness": "ok",
        "checked_at": _checked_at(),
    }


def _default_session_factory():
    from db_session import db_session

    return db_session()


def _default_schema_inspector(engine):
    from services.database_migration_service import inspect_schema_status

    return inspect_schema_status(engine)


def _default_schema_message(status: dict) -> str:
    from services.database_migration_service import schema_state_message

    return schema_state_message(status)


def _default_engine_invalidator() -> None:
    from database_config import invalidate_engine, _sync_legacy_refs

    invalidate_engine()
    _sync_legacy_refs()


def _invalidate_safely(callback) -> None:
    try:
        callback()
    except Exception:
        logger.exception("数据库健康探针清理失效连接池时出错")


def build_readiness_status(
    *,
    session_factory=None,
    schema_inspector=None,
    schema_message_builder=None,
    engine_invalidator=None,
) -> dict:
    """同时校验数据库连接和迁移版本，返回应用就绪状态。"""

    session_factory = session_factory or _default_session_factory
    schema_inspector = schema_inspector or _default_schema_inspector
    schema_message_builder = schema_message_builder or _default_schema_message
    engine_invalidator = engine_invalidator or _default_engine_invalidator

    status = build_liveness_status()
    status.update({
        "readiness": "error",
        "database": "unknown",
        "schema": "unknown",
        "schema_state": "unknown",
    })

    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
            engine = session.get_bind()
        if engine is None:
            raise RuntimeError("database engine unavailable")
        status["database"] = "ok"
    except Exception as exc:
        _invalidate_safely(engine_invalidator)
        status.update({
            "status": "error",
            "database": "error",
            "reason": "database_unavailable",
            "message": "数据库连接尚未就绪",
        })
        logger.warning("数据库就绪探针失败: %s", exc)
        return status

    try:
        schema_status = schema_inspector(engine)
    except Exception as exc:
        _invalidate_safely(engine_invalidator)
        status.update({
            "status": "error",
            "schema": "error",
            "reason": "schema_probe_failed",
            "message": "数据库结构状态检查失败",
        })
        logger.warning("数据库结构就绪探针失败: %s", exc)
        return status

    schema_state = str(schema_status.get("state") or "unknown")
    status["schema_state"] = schema_state
    if not schema_status.get("ready"):
        status.update({
            "status": "error",
            "schema": "error",
            "reason": f"schema_{schema_state}",
            "message": schema_message_builder(schema_status),
        })
        return status

    status.update({
        "status": "ok",
        "readiness": "ok",
        "schema": "ok",
        "message": "服务已就绪",
    })
    return status


def is_ready(status: dict) -> bool:
    """判断探针结果是否可以接收业务流量。"""

    return status.get("readiness") == "ok"
