"""根据真实运行数据生成 SCADA 健康快照。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping

from db_models.power import ActualPower
from db_models.prediction_task import PredictionTask
from db_models.report_config import ReportConfig, WindFarm
from db_models.report_outbox import ReportOutbox
from db_models.scada_connection import ScadaConnection
from db_models.scada_ingest_record import ScadaIngestRecord


BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_naive_beijing(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(BEIJING_TZ).replace(tzinfo=None)
    return value


def _iso(value: datetime | None) -> str | None:
    value = _as_naive_beijing(value)
    return value.isoformat() if value is not None else None


def _age_seconds(now: datetime, value: datetime | None) -> int | None:
    value = _as_naive_beijing(value)
    if value is None:
        return None
    return max(0, int((now - value).total_seconds()))


def assess_connection_health(
    connection,
    *,
    deployment_enabled: bool,
    stale_after_seconds: int,
    latest_event=None,
    now: datetime | None = None,
) -> dict:
    """使用连接状态、最后有效样本和最近质量结果判断健康度。"""

    checked_at = _as_naive_beijing(now) or datetime.now()
    last_data_at = _as_naive_beijing(getattr(connection, "last_data_at", None))
    data_age = _age_seconds(checked_at, last_data_at)
    worker_status = str(getattr(connection, "status", "unknown") or "unknown")
    enabled = bool(getattr(connection, "is_enabled", False))

    if not deployment_enabled:
        status = "deployment_disabled"
        reason = "当前部署未启用 SCADA 实时接入"
    elif not enabled:
        status = "disabled"
        reason = "连接配置已停用"
    elif worker_status == "error":
        status = "error"
        reason = getattr(connection, "last_error", None) or "采集 Worker 报告异常"
    elif worker_status == "stopped":
        status = "stopped"
        reason = "采集 Worker 已停止"
    elif worker_status in {"connecting", "stopping", "restart_requested"}:
        status = "connecting"
        reason = "SCADA 管理器正在执行连接状态变更"
    elif worker_status != "running":
        status = "unknown"
        reason = f"无法识别 Worker 状态: {worker_status}"
    elif last_data_at is None:
        status = "no_data"
        reason = "Worker 已运行，尚未收到有效样本"
    elif data_age is not None and data_age > stale_after_seconds:
        status = "stale"
        reason = f"最后有效样本已超过 {stale_after_seconds} 秒"
    elif (
        latest_event is not None
        and getattr(latest_event, "outcome", None) == "rejected"
        and _as_naive_beijing(getattr(latest_event, "received_at", None))
        >= last_data_at
    ):
        status = "degraded"
        reason = getattr(latest_event, "message", None) or "最近样本未通过质量校验"
    else:
        status = "healthy"
        reason = "Worker、数据新鲜度和最近质量结果均正常"

    return {
        "status": status,
        "reason": reason,
        "worker_status": worker_status,
        "data_age_seconds": data_age,
        "stale_after_seconds": stale_after_seconds,
        "last_data_at": _iso(last_data_at),
        "latest_quality": getattr(latest_event, "quality", None) if latest_event else None,
        "latest_outcome": getattr(latest_event, "outcome", None) if latest_event else None,
    }


def _prediction_summary(tasks: Iterable, latest_actual_at: datetime | None) -> dict:
    task_rows = list(tasks)
    if not task_rows:
        return {
            "state": "not_configured",
            "reason": "当前场站没有启用预测任务",
            "tasks": [],
        }

    details = []
    states = []
    latest_actual_at = _as_naive_beijing(latest_actual_at)
    for task in task_rows:
        last_predict_at = _as_naive_beijing(getattr(task, "last_predict_at", None))
        last_status = str(getattr(task, "last_predict_status", "") or "unknown")
        if last_status == "failed":
            state = "failed"
        elif latest_actual_at is None:
            state = "waiting_for_data"
        elif last_predict_at is None or last_predict_at < latest_actual_at:
            state = "pending"
        elif last_status in {"success", "skipped"}:
            state = "current"
        else:
            state = "running" if last_status == "running" else "unknown"
        states.append(state)
        details.append({
            "task_type": task.task_type,
            "state": state,
            "last_predict_status": last_status,
            "last_predict_at": _iso(last_predict_at),
        })

    if "failed" in states:
        state = "failed"
        reason = "至少一个预测任务最近执行失败"
    elif "pending" in states or "waiting_for_data" in states:
        state = "pending"
        reason = "最新实际功率尚未被全部预测任务消费"
    elif "running" in states:
        state = "running"
        reason = "预测任务正在处理最新数据"
    elif all(item == "current" for item in states):
        state = "current"
        reason = "最新实际功率已进入预测任务"
    else:
        state = "unknown"
        reason = "预测任务状态不足以判断闭环进度"

    return {"state": state, "reason": reason, "tasks": details}


def _report_summary(configs: Iterable, latest_outbox) -> dict:
    config_rows = list(configs)
    if not config_rows:
        return {
            "state": "not_configured",
            "reason": "当前场站没有启用实际功率上报",
            "latest_status": None,
        }
    if latest_outbox is None:
        return {
            "state": "idle",
            "reason": "上报配置已启用，发件箱尚无实际功率任务",
            "latest_status": None,
        }
    latest_status = str(latest_outbox.status or "unknown")
    if latest_status == "sent":
        state = "sent"
        reason = "最近一次实际功率任务已发送"
    elif latest_status in {"pending", "retry", "processing"}:
        state = "pending"
        reason = "实际功率任务正在可靠上报队列中处理"
    elif latest_status in {"dead", "failed"}:
        state = "failed"
        reason = latest_outbox.last_error or "最近一次实际功率上报失败"
    else:
        state = "unknown"
        reason = f"无法识别上报状态: {latest_status}"
    return {
        "state": state,
        "reason": reason,
        "latest_status": latest_status,
        "latest_created_at": _iso(latest_outbox.created_at),
        "latest_sent_at": _iso(latest_outbox.sent_at),
    }


def build_scada_health_snapshot(
    session,
    config: Mapping,
    *,
    now: datetime | None = None,
) -> dict:
    """查询所有场站的采集、预测和实际功率上报闭环状态。"""

    checked_at = _as_naive_beijing(now) or datetime.now()
    deployment_enabled = _as_bool(config.get("SCADA_REALTIME_ENABLED", False))
    try:
        stale_after_seconds = max(
            30, int(config.get("SCADA_DATA_STALE_AFTER_SECONDS", 1200))
        )
    except (TypeError, ValueError):
        stale_after_seconds = 1200

    connections = session.query(ScadaConnection).order_by(ScadaConnection.id).all()
    items = []
    for connection in connections:
        latest_event = session.query(ScadaIngestRecord).filter(
            ScadaIngestRecord.connection_id == connection.id
        ).order_by(ScadaIngestRecord.received_at.desc(), ScadaIngestRecord.id.desc()).first()
        latest_actual = session.query(ActualPower).filter(
            ActualPower.farm_code == connection.farm_code
        ).order_by(ActualPower.timestamp.desc()).first()
        tasks = session.query(PredictionTask).filter(
            PredictionTask.farm_code == connection.farm_code,
            PredictionTask.enabled.is_(True),
        ).order_by(PredictionTask.task_type).all()

        farm = session.query(WindFarm).filter(
            WindFarm.farm_code == connection.farm_code
        ).first()
        report_configs = []
        if farm is not None:
            report_configs = session.query(ReportConfig).filter(
                ReportConfig.farm_id == farm.id,
                ReportConfig.report_type == "actual",
                ReportConfig.is_enabled.is_(True),
            ).all()
        latest_outbox = session.query(ReportOutbox).filter(
            ReportOutbox.farm_code == connection.farm_code,
            ReportOutbox.report_type == "actual",
        ).order_by(ReportOutbox.created_at.desc(), ReportOutbox.id.desc()).first()

        health = assess_connection_health(
            connection,
            deployment_enabled=deployment_enabled,
            stale_after_seconds=stale_after_seconds,
            latest_event=latest_event,
            now=checked_at,
        )
        health.update({
            "connection_id": connection.id,
            "farm_code": connection.farm_code,
            "name": connection.name,
            "latest_actual_timestamp": _iso(
                latest_actual.timestamp if latest_actual is not None else None
            ),
            "latest_actual_power_mw": (
                float(latest_actual.wp_true)
                if latest_actual is not None and latest_actual.wp_true is not None
                else None
            ),
            "prediction": _prediction_summary(
                tasks,
                latest_actual.timestamp if latest_actual is not None else None,
            ),
            "report": _report_summary(report_configs, latest_outbox),
        })
        items.append(health)

    enabled_items = [
        item for item, connection in zip(items, connections) if connection.is_enabled
    ]
    healthy_count = sum(item["status"] == "healthy" for item in enabled_items)
    degraded_count = sum(item["status"] == "degraded" for item in enabled_items)

    if not deployment_enabled:
        availability = "config_required"
        reason = "当前部署未启用 SCADA 实时接入"
    elif not enabled_items:
        availability = "config_required"
        reason = "尚未配置并启用 SCADA 数据源"
    elif healthy_count == len(enabled_items):
        availability = "available"
        reason = f"{healthy_count}/{len(enabled_items)} 个 SCADA 数据源运行正常"
    elif healthy_count > 0 or degraded_count > 0:
        availability = "degraded"
        reason = (
            f"{healthy_count}/{len(enabled_items)} 个数据源健康，"
            f"{degraded_count} 个数据源质量降级"
        )
    else:
        availability = "unavailable"
        reason = f"{len(enabled_items)} 个已启用数据源均未达到健康标准"

    counts = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    return {
        "availability": availability,
        "reason": reason,
        "deployment_enabled": deployment_enabled,
        "generated_at": checked_at.isoformat(),
        "stale_after_seconds": stale_after_seconds,
        "counts": counts,
        "connections": items,
    }
