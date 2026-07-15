"""可靠上报发件箱服务。"""

from __future__ import annotations

import hashlib
import json
import logging
import socket
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable
from urllib.parse import urlparse

import requests
from sqlalchemy.exc import IntegrityError

from db_models import ReportConfig, ReportLog, ReportOutbox


logger = logging.getLogger(__name__)

RETRYABLE_HTTP_CODES = {408, 425, 429}
ACTIVE_STATUSES = ("pending", "retry")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class EnqueueResult:
    outbox_id: int
    idempotency_key: str
    created: bool
    status: str


@dataclass(frozen=True)
class DispatchResult:
    status: str
    outbox_id: int | None = None
    attempt_count: int = 0
    response_code: int | None = None
    response_body: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class _Envelope:
    outbox_id: int
    target_url: str
    payload_json: str
    payload_sha256: str
    headers: dict[str, str]
    timeout_seconds: int
    idempotency_key: str
    attempt_count: int


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"不支持 JSON 序列化的数据类型: {type(value).__name__}")


def canonical_json(payload: dict) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def make_idempotency_key(
    *,
    config_id: int,
    farm_code: str,
    report_type: str,
    logical_time: datetime,
    scope: str = "scheduled",
) -> str:
    if scope == "manual":
        logical_value = f"{logical_time.isoformat()}:{uuid.uuid4().hex}"
    else:
        logical_value = logical_time.replace(second=0, microsecond=0).isoformat()
    source = f"{scope}:{config_id}:{farm_code}:{report_type}:{logical_value}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def report_target_url(config: ReportConfig) -> str:
    target_path = getattr(config, "target_path", "/receive-data") or "/receive-data"
    if not str(target_path).startswith("/"):
        target_path = f"/{target_path}"
    url = f"http://{config.target_ip}:{config.target_port}{target_path}"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("上报目标地址无效")
    return url


def build_report_payload(config: ReportConfig, data: list, farm_code: str) -> dict:
    return {
        "report_type": config.report_type,
        "timestamp": datetime.now().isoformat(),
        "farm_code": farm_code,
        "data": data,
    }


def enqueue_report(
    session,
    *,
    config: ReportConfig,
    farm_code: str,
    payload: dict,
    idempotency_key: str,
    data_completeness_rate: float | None = None,
    is_on_time: bool | None = None,
    headers: dict[str, str] | None = None,
) -> EnqueueResult:
    """在当前事务中幂等创建上报任务。"""

    existing = session.query(ReportOutbox).filter_by(idempotency_key=idempotency_key).first()
    if existing:
        return EnqueueResult(existing.id, idempotency_key, False, existing.status)

    serialized = canonical_json(payload)
    row = ReportOutbox(
        idempotency_key=idempotency_key,
        config_id=config.id,
        farm_code=farm_code,
        report_type=config.report_type,
        target_url=report_target_url(config),
        payload_json=serialized,
        payload_sha256=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        headers_json=canonical_json(headers or {"Content-Type": "application/json"}),
        timeout_seconds=max(1, int(config.timeout_seconds or 30)),
        data_count=len(payload.get("data") or []),
        data_completeness_rate=data_completeness_rate,
        is_on_time=is_on_time,
        status="pending",
        attempt_count=0,
        max_attempts=max(1, int(config.retry_count or 0) + 1),
        next_attempt_at=_utc_now(),
    )
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError:
        existing = session.query(ReportOutbox).filter_by(idempotency_key=idempotency_key).first()
        if not existing:
            raise
        return EnqueueResult(existing.id, idempotency_key, False, existing.status)
    return EnqueueResult(row.id, idempotency_key, True, row.status)


def recover_stale_processing(
    session_scope,
    *,
    stale_after_seconds: int = 300,
) -> dict[str, int]:
    threshold = _utc_now() - timedelta(seconds=stale_after_seconds)
    recovered = 0
    dead = 0
    with session_scope() as session:
        rows = session.query(ReportOutbox).filter(
            ReportOutbox.status == "processing",
            ReportOutbox.locked_at < threshold,
        ).with_for_update(skip_locked=True).all()
        for row in rows:
            row.locked_at = None
            row.locked_by = None
            row.updated_at = _utc_now()
            row.last_error = "发送进程中断，任务已由恢复机制接管"
            if row.attempt_count >= row.max_attempts:
                row.status = "dead"
                row.next_attempt_at = None
                _add_final_failure_log(session, row)
                dead += 1
            else:
                row.status = "retry"
                row.next_attempt_at = _utc_now()
                recovered += 1
    return {"recovered": recovered, "dead": dead}


def dispatch_one(
    session_scope,
    *,
    outbox_id: int | None = None,
    sender: Callable | None = None,
    worker_id: str | None = None,
    retry_base_seconds: int = 5,
    retry_max_seconds: int = 300,
) -> DispatchResult:
    sender = sender or requests.post
    worker_id = worker_id or f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"
    envelope, terminal = _claim(
        session_scope,
        outbox_id=outbox_id,
        worker_id=worker_id,
    )
    if terminal is not None:
        return terminal
    if envelope is None:
        return DispatchResult(status="idle")

    payload_bytes = envelope.payload_json.encode("utf-8")
    actual_digest = hashlib.sha256(payload_bytes).hexdigest()
    if actual_digest != envelope.payload_sha256:
        return _mark_failed(
            session_scope,
            envelope,
            "发件箱载荷完整性校验失败，已停止发送",
            permanent=True,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
        )

    headers = dict(envelope.headers)
    headers["Content-Type"] = "application/json"
    headers["Idempotency-Key"] = envelope.idempotency_key
    try:
        response = sender(
            envelope.target_url,
            data=payload_bytes,
            headers=headers,
            timeout=envelope.timeout_seconds,
        )
        response_code = int(response.status_code)
        response_body = str(getattr(response, "text", ""))[:2000]
        if 200 <= response_code < 300:
            return _mark_sent(session_scope, envelope, response_code, response_body)

        retryable = response_code >= 500 or response_code in RETRYABLE_HTTP_CODES
        error = f"目标服务返回 HTTP {response_code}"
        return _mark_failed(
            session_scope,
            envelope,
            error,
            response_code=response_code,
            response_body=response_body,
            permanent=not retryable,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
        )
    except Exception as exc:
        return _mark_failed(
            session_scope,
            envelope,
            str(exc),
            permanent=False,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
        )


def dispatch_batch(
    session_scope,
    *,
    limit: int = 20,
    sender: Callable | None = None,
    worker_id: str | None = None,
) -> dict[str, int]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    recovered = recover_stale_processing(session_scope)
    counts = {"sent": 0, "retry": 0, "dead": 0, "idle": 0}
    for _ in range(limit):
        result = dispatch_one(session_scope, sender=sender, worker_id=worker_id)
        if result.status == "idle":
            counts["idle"] += 1
            break
        counts[result.status] = counts.get(result.status, 0) + 1
    counts.update({f"recovery_{key}": value for key, value in recovered.items()})
    return counts


def retry_dead_letter(session, outbox_id: int) -> bool:
    row = session.query(ReportOutbox).filter_by(id=outbox_id).with_for_update().first()
    if not row or row.status != "dead":
        return False
    row.status = "retry"
    row.attempt_count = 0
    row.next_attempt_at = _utc_now()
    row.locked_at = None
    row.locked_by = None
    row.last_error = None
    row.updated_at = _utc_now()
    return True


def _claim(session_scope, *, outbox_id: int | None, worker_id: str):
    now = _utc_now()
    with session_scope() as session:
        query = session.query(ReportOutbox)
        if outbox_id is not None:
            query = query.filter(ReportOutbox.id == outbox_id)
        else:
            query = query.filter(
                ReportOutbox.status.in_(ACTIVE_STATUSES),
                ReportOutbox.next_attempt_at <= now,
            ).order_by(ReportOutbox.next_attempt_at, ReportOutbox.id)
        row = query.with_for_update(skip_locked=True).first()
        if row is None:
            return None, None

        if row.status == "sent":
            return None, DispatchResult(
                status="sent",
                outbox_id=row.id,
                attempt_count=row.attempt_count,
                response_code=row.last_response_code,
                response_body=row.last_response_body,
            )
        if row.status == "dead":
            return None, DispatchResult(
                status="dead",
                outbox_id=row.id,
                attempt_count=row.attempt_count,
                response_code=row.last_response_code,
                error=row.last_error,
            )
        if row.status == "processing":
            return None, DispatchResult(
                status="busy",
                outbox_id=row.id,
                attempt_count=row.attempt_count,
            )
        if row.next_attempt_at and row.next_attempt_at > now:
            return None, DispatchResult(
                status="retry",
                outbox_id=row.id,
                attempt_count=row.attempt_count,
                error=row.last_error,
            )

        row.status = "processing"
        row.attempt_count += 1
        row.locked_at = now
        row.locked_by = worker_id
        row.updated_at = now
        session.flush()
        envelope = _Envelope(
            outbox_id=row.id,
            target_url=row.target_url,
            payload_json=row.payload_json,
            payload_sha256=row.payload_sha256,
            headers=json.loads(row.headers_json or "{}"),
            timeout_seconds=row.timeout_seconds,
            idempotency_key=row.idempotency_key,
            attempt_count=row.attempt_count,
        )
    return envelope, None


def _mark_sent(
    session_scope,
    envelope: _Envelope,
    response_code: int,
    response_body: str,
) -> DispatchResult:
    with session_scope() as session:
        row = session.query(ReportOutbox).filter_by(id=envelope.outbox_id).with_for_update().first()
        if not row:
            return DispatchResult(status="dead", outbox_id=envelope.outbox_id, error="发件箱记录不存在")
        if row.status == "sent":
            return DispatchResult(
                status="sent",
                outbox_id=row.id,
                attempt_count=row.attempt_count,
                response_code=row.last_response_code,
                response_body=row.last_response_body,
            )
        if row.status == "dead":
            return DispatchResult(
                status="dead",
                outbox_id=row.id,
                attempt_count=row.attempt_count,
                response_code=row.last_response_code,
                error=row.last_error,
            )
        if row.status != "processing" or row.attempt_count != envelope.attempt_count:
            return DispatchResult(
                status=row.status,
                outbox_id=row.id,
                attempt_count=row.attempt_count,
                response_code=row.last_response_code,
                response_body=row.last_response_body,
                error=row.last_error,
            )
        row.status = "sent"
        row.sent_at = _utc_now()
        row.updated_at = _utc_now()
        row.next_attempt_at = None
        row.locked_at = None
        row.locked_by = None
        row.last_response_code = response_code
        row.last_response_body = response_body
        row.last_error = None
        config = session.query(ReportConfig).filter_by(id=row.config_id).first()
        if config:
            config.last_report_time = row.sent_at
        session.add(
            ReportLog(
                config_id=row.config_id,
                farm_code=row.farm_code,
                report_type=row.report_type,
                report_time=row.sent_at,
                data_count=row.data_count,
                data_completeness_rate=row.data_completeness_rate,
                status="success",
                response_code=response_code,
                response_message=response_body[:500] if response_body else None,
                execution_time=(row.sent_at - row.created_at).total_seconds(),
            )
        )
        attempt_count = row.attempt_count
    return DispatchResult(
        status="sent",
        outbox_id=envelope.outbox_id,
        attempt_count=attempt_count,
        response_code=response_code,
        response_body=response_body,
    )


def _mark_failed(
    session_scope,
    envelope: _Envelope,
    error: str,
    *,
    response_code: int | None = None,
    response_body: str | None = None,
    permanent: bool,
    retry_base_seconds: int,
    retry_max_seconds: int,
) -> DispatchResult:
    with session_scope() as session:
        row = session.query(ReportOutbox).filter_by(id=envelope.outbox_id).with_for_update().first()
        if not row:
            return DispatchResult(status="dead", outbox_id=envelope.outbox_id, error="发件箱记录不存在")
        if row.status in {"sent", "dead"}:
            return DispatchResult(
                status=row.status,
                outbox_id=row.id,
                attempt_count=row.attempt_count,
                response_code=row.last_response_code,
                response_body=row.last_response_body,
                error=row.last_error,
            )
        if row.status != "processing" or row.attempt_count != envelope.attempt_count:
            return DispatchResult(
                status=row.status,
                outbox_id=row.id,
                attempt_count=row.attempt_count,
                response_code=row.last_response_code,
                response_body=row.last_response_body,
                error=row.last_error,
            )
        row.updated_at = _utc_now()
        row.locked_at = None
        row.locked_by = None
        row.last_response_code = response_code
        row.last_response_body = response_body
        row.last_error = error[:2000]

        should_stop = permanent or row.attempt_count >= row.max_attempts
        if should_stop:
            row.status = "dead"
            row.next_attempt_at = None
            _add_final_failure_log(session, row)
        else:
            delay = min(
                retry_max_seconds,
                retry_base_seconds * (2 ** max(0, row.attempt_count - 1)),
            )
            row.status = "retry"
            row.next_attempt_at = _utc_now() + timedelta(seconds=delay)
        status = row.status
        attempt_count = row.attempt_count
    return DispatchResult(
        status=status,
        outbox_id=envelope.outbox_id,
        attempt_count=attempt_count,
        response_code=response_code,
        response_body=response_body,
        error=error,
    )


def _add_final_failure_log(session, row: ReportOutbox) -> None:
    session.add(
        ReportLog(
            config_id=row.config_id,
            farm_code=row.farm_code,
            report_type=row.report_type,
            report_time=_utc_now(),
            data_count=row.data_count,
            data_completeness_rate=row.data_completeness_rate,
            status="failed",
            response_code=row.last_response_code,
            response_message=(row.last_response_body or "")[:500] or None,
            error_message=(row.last_error or "")[:500] or None,
            execution_time=(_utc_now() - row.created_at).total_seconds(),
        )
    )
