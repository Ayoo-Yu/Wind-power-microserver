"""预测运行的排队、跨进程认领和终态更新。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from db_models import PredictionRun, PredictionTask


_BJ_TZ = timezone(timedelta(hours=8))
_ACTIVE_STATUSES = {"queued", "running"}
_TERMINAL_STATUSES = {"success", "failed", "skipped", "interrupted"}


def _now() -> datetime:
    return datetime.now(_BJ_TZ).replace(tzinfo=None)


class PredictionTaskMissing(ValueError):
    """场站与预测尺度没有对应的任务配置。"""


class PredictionRunConflict(RuntimeError):
    """同一场站、尺度和动作已有排队或运行中的任务。"""

    def __init__(self, active_run: PredictionRun):
        self.active_run_id = active_run.id
        self.celery_task_id = active_run.celery_task_id
        super().__init__(f"已有运行中的同类任务，运行编号 {active_run.id}")


@dataclass(frozen=True)
class PredictionRunClaim:
    run_id: int
    task_id: int
    celery_task_id: str
    should_execute: bool
    status: str
    reason: str
    active_run_id: int | None = None


def _lock_task(session, farm_code: str, task_type: str) -> PredictionTask:
    task = (
        session.query(PredictionTask)
        .filter(
            PredictionTask.farm_code == farm_code,
            PredictionTask.task_type == task_type,
        )
        .with_for_update()
        .first()
    )
    if task is None:
        raise PredictionTaskMissing(f"未找到预测任务配置: {farm_code}/{task_type}")
    return task


def _find_by_celery_id(session, celery_task_id: str) -> PredictionRun | None:
    return (
        session.query(PredictionRun)
        .filter(PredictionRun.celery_task_id == celery_task_id)
        .with_for_update()
        .first()
    )


def _active_run(session, task_id: int) -> PredictionRun | None:
    return (
        session.query(PredictionRun)
        .filter(
            PredictionRun.task_id == task_id,
            PredictionRun.status.in_(_ACTIVE_STATUSES),
        )
        .order_by(PredictionRun.id.desc())
        .first()
    )


def _mark_task_running(task: PredictionTask, action: str, now: datetime) -> None:
    if action == "train":
        task.last_train_status = "running"
    elif action in {"predict", "merge", "calibrate"}:
        task.last_predict_status = "running"
    task.updated_at = now


def reserve_prediction_run(
    session,
    *,
    farm_code: str,
    task_type: str,
    action: str,
    celery_task_id: str,
    requested_by: str,
    trigger_source: str,
    request_id: str | None,
) -> PredictionRunClaim:
    """在向消息队列发送任务前创建可查询的排队记录。"""

    if not celery_task_id:
        raise ValueError("celery_task_id 不能为空")
    task = _lock_task(session, farm_code, task_type)
    existing = _find_by_celery_id(session, celery_task_id)
    if existing is not None:
        if existing.task_id != task.id or existing.action != action:
            raise ValueError("celery_task_id 已绑定到其他预测任务")
        return PredictionRunClaim(
            run_id=existing.id,
            task_id=task.id,
            celery_task_id=celery_task_id,
            should_execute=False,
            status=existing.status,
            reason="idempotent_replay",
        )

    active = _active_run(session, task.id)
    if active is not None:
        raise PredictionRunConflict(active)

    run = PredictionRun(
        task_id=task.id,
        celery_task_id=celery_task_id,
        action=action,
        status="queued",
        requested_by=str(requested_by or "unknown")[:100],
        trigger_source=str(trigger_source or "manual_api")[:32],
        request_id=str(request_id)[:100] if request_id else None,
        attempt_count=0,
    )
    session.add(run)
    session.flush()
    return PredictionRunClaim(
        run_id=run.id,
        task_id=task.id,
        celery_task_id=celery_task_id,
        should_execute=False,
        status="queued",
        reason="reserved",
    )


def claim_prediction_run(
    session,
    *,
    farm_code: str,
    task_type: str,
    action: str,
    celery_task_id: str,
    attempt_number: int,
    requested_by: str = "system",
    trigger_source: str = "scheduler",
) -> PredictionRunClaim:
    """通过任务配置行锁保证同类任务只被一个 Worker 执行。"""

    if not celery_task_id:
        raise ValueError("celery_task_id 不能为空")
    if int(attempt_number) <= 0:
        raise ValueError("attempt_number 必须大于 0")

    task = _lock_task(session, farm_code, task_type)
    existing = _find_by_celery_id(session, celery_task_id)
    if existing is not None:
        if existing.task_id != task.id or existing.action != action:
            raise ValueError("celery_task_id 已绑定到其他预测任务")
        if int(attempt_number) <= int(existing.attempt_count or 0):
            return PredictionRunClaim(
                run_id=existing.id,
                task_id=task.id,
                celery_task_id=celery_task_id,
                should_execute=False,
                status=existing.status,
                reason="duplicate_delivery",
            )
        if existing.status in {"success", "skipped", "interrupted"}:
            return PredictionRunClaim(
                run_id=existing.id,
                task_id=task.id,
                celery_task_id=celery_task_id,
                should_execute=False,
                status=existing.status,
                reason="terminal_run",
            )

        now = _now()
        existing.status = "running"
        existing.attempt_count = int(attempt_number)
        existing.started_at = existing.started_at or now
        existing.last_heartbeat_at = now
        existing.finished_at = None
        existing.duration_sec = None
        existing.error_message = None
        existing.result_json = None
        _mark_task_running(task, action, now)
        session.flush()
        return PredictionRunClaim(
            run_id=existing.id,
            task_id=task.id,
            celery_task_id=celery_task_id,
            should_execute=True,
            status="running",
            reason="claimed_existing",
        )

    active = _active_run(session, task.id)
    now = _now()
    if active is not None:
        skipped = PredictionRun(
            task_id=task.id,
            celery_task_id=celery_task_id,
            action=action,
            status="skipped",
            requested_by=str(requested_by or "system")[:100],
            trigger_source=str(trigger_source or "scheduler")[:32],
            attempt_count=int(attempt_number),
            started_at=now,
            last_heartbeat_at=now,
            finished_at=now,
            duration_sec=0,
            error_message=f"已有运行中的同类任务，运行编号 {active.id}",
        )
        session.add(skipped)
        session.flush()
        return PredictionRunClaim(
            run_id=skipped.id,
            task_id=task.id,
            celery_task_id=celery_task_id,
            should_execute=False,
            status="skipped",
            reason="active_run_exists",
            active_run_id=active.id,
        )

    run = PredictionRun(
        task_id=task.id,
        celery_task_id=celery_task_id,
        action=action,
        status="running",
        requested_by=str(requested_by or "system")[:100],
        trigger_source=str(trigger_source or "scheduler")[:32],
        attempt_count=int(attempt_number),
        started_at=now,
        last_heartbeat_at=now,
    )
    _mark_task_running(task, action, now)
    session.add(run)
    session.flush()
    return PredictionRunClaim(
        run_id=run.id,
        task_id=task.id,
        celery_task_id=celery_task_id,
        should_execute=True,
        status="running",
        reason="claimed_new",
    )


def finish_prediction_run(
    session,
    *,
    run_id: int,
    attempt_number: int,
    status: str,
    error_message: str | None = None,
    result_data=None,
) -> bool:
    """仅允许当前认领尝试写入终态，并同步任务摘要。"""

    if status not in _TERMINAL_STATUSES:
        raise ValueError(f"不支持的预测运行终态: {status}")
    task_id = (
        session.query(PredictionRun.task_id)
        .filter(PredictionRun.id == run_id)
        .scalar()
    )
    if task_id is None:
        return False
    task = (
        session.query(PredictionTask)
        .filter(PredictionTask.id == task_id)
        .with_for_update()
        .first()
    )
    run = (
        session.query(PredictionRun)
        .filter(PredictionRun.id == run_id)
        .with_for_update()
        .first()
    )
    if run is None:
        return False
    if run.status != "running" or int(run.attempt_count or 0) != int(attempt_number):
        return False

    now = _now()
    run.status = status
    run.last_heartbeat_at = now
    run.finished_at = now
    if run.started_at:
        run.duration_sec = max(0, int((now - run.started_at).total_seconds()))
    run.error_message = str(error_message) if error_message else None
    if result_data is not None:
        run.result_json = json.dumps(result_data, default=str, ensure_ascii=False)

    if task is not None:
        if run.action == "train":
            task.last_train_status = status
            task.last_train_at = now
        elif run.action in {"predict", "merge", "calibrate"}:
            task.last_predict_status = status
            task.last_predict_at = now
        task.last_error = str(error_message) if error_message else None
        task.updated_at = now
    return True


def mark_prediction_dispatch_failed(
    session,
    *,
    run_id: int,
    error_message: str,
) -> bool:
    """消息尚未进入队列时，把排队记录转换为失败终态。"""

    run = (
        session.query(PredictionRun)
        .filter(PredictionRun.id == run_id)
        .with_for_update()
        .first()
    )
    if run is None or run.status != "queued":
        return False
    now = _now()
    run.status = "failed"
    run.finished_at = now
    run.duration_sec = 0
    run.error_message = str(error_message)
    return True
