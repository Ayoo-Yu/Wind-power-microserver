"""可信操作审计记录。"""

from __future__ import annotations

import json
from datetime import datetime

from db_models import OperationAuditLog


_VALID_SOURCES = {"server", "client", "legacy"}
_VALID_RESULTS = {"成功", "警告", "失败"}


def _limited(value, limit: int, fallback: str = "") -> str:
    text = str(value or fallback).strip()
    return text[:limit]


def _details_text(details) -> str:
    if isinstance(details, str):
        return details
    return json.dumps(
        details or {},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def add_operation_audit(
    session,
    *,
    operator: str,
    module: str,
    operation_type: str,
    details=None,
    result: str = "成功",
    source: str = "server",
    ip_address: str | None = None,
    request_id: str | None = None,
    operation_time: datetime | None = None,
) -> OperationAuditLog:
    """在调用方事务内写入一条来源明确的操作审计。"""

    normalised_source = source if source in _VALID_SOURCES else "server"
    normalised_result = result if result in _VALID_RESULTS else "警告"
    row = OperationAuditLog(
        operation_time=operation_time or datetime.now(),
        operator=_limited(operator, 100, "unknown"),
        ip_address=_limited(ip_address, 50) or None,
        module=_limited(module, 100, "系统"),
        operation_type=_limited(operation_type, 100, "操作"),
        details=_details_text(details),
        result=normalised_result,
        source=normalised_source,
        request_id=_limited(request_id, 100) or None,
    )
    session.add(row)
    return row
