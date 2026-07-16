"""汇总现场运行所需的数据链路、预测、上报和模型治理状态。"""

from __future__ import annotations

import os
import shutil
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db_models import (
    IngestionBatch,
    ForecastOutputPoint,
    ModelVersion,
    PredictionInputSnapshot,
    PredictionRun,
    PredictionTask,
    ReportOutbox,
    ScadaConnection,
    SourceObservation,
)
from services.scada_contract import REQUIRED_SCADA_METRICS, SCADA_METRICS


_BEIJING_TZ = timezone(timedelta(hours=8))


def _beijing_now() -> datetime:
    return datetime.now(_BEIJING_TZ).replace(tzinfo=None)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _age_seconds(now: datetime, value: datetime | None) -> int | None:
    if value is None:
        return None
    return max(0, int((now - value).total_seconds()))


def _storage_overview(storage_path: str | None) -> dict:
    target = Path(storage_path or os.getcwd()).resolve()
    probe = target
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    used_percent = round((usage.used / usage.total) * 100, 1) if usage.total else 0.0
    return {
        "path": str(target),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": used_percent,
    }


def _scada_overview(
    session,
    now: datetime,
    enabled: bool,
    required: bool,
    stale_after_seconds: int,
    farm_code: str | None,
) -> dict:
    connection_query = session.query(ScadaConnection)
    if farm_code:
        connection_query = connection_query.filter(ScadaConnection.farm_code == farm_code)
    connections = connection_query.order_by(ScadaConnection.farm_code).all()

    observation_query = session.query(SourceObservation).filter(
        SourceObservation.source_type == "scada",
        SourceObservation.metric.in_(REQUIRED_SCADA_METRICS),
    )
    if farm_code:
        observation_query = observation_query.filter(SourceObservation.farm_code == farm_code)
    observations = (
        observation_query.order_by(SourceObservation.event_time.desc())
        .limit(max(500, len(connections) * len(REQUIRED_SCADA_METRICS) * 5))
        .all()
    )
    latest = {}
    for item in observations:
        latest.setdefault((item.farm_code, item.metric), item)

    connection_items = []
    missing_metric_count = 0
    stale_metric_count = 0
    for connection in connections:
        metrics = []
        for metric in REQUIRED_SCADA_METRICS:
            observation = latest.get((connection.farm_code, metric))
            age = _age_seconds(now, observation.event_time if observation else None)
            if not connection.is_enabled:
                state = "disabled"
            elif observation is None:
                state = "missing"
                missing_metric_count += 1
            elif age is not None and age > stale_after_seconds:
                state = "stale"
                stale_metric_count += 1
            elif str(observation.quality).lower() not in {"good", "valid"}:
                state = "degraded"
            else:
                state = "fresh"
            metrics.append({
                "metric": metric,
                "label": SCADA_METRICS[metric]["label"],
                "unit": SCADA_METRICS[metric]["unit"],
                "state": state,
                "event_time": _iso(observation.event_time) if observation else None,
                "received_at": _iso(observation.received_at) if observation else None,
                "age_seconds": age,
                "quality": observation.quality if observation else None,
                "value": observation.value if observation else None,
            })
        connection_items.append({
            "id": connection.id,
            "farm_code": connection.farm_code,
            "name": connection.name,
            "protocol": connection.protocol,
            "enabled": bool(connection.is_enabled),
            "worker_status": connection.status,
            "status_message": connection.status_message,
            "last_data_at": _iso(connection.last_data_at),
            "point_catalog_version": connection.point_catalog_version,
            "metrics": metrics,
        })

    enabled_connections = [item for item in connections if item.is_enabled]
    if not enabled:
        state = "disabled"
    elif not enabled_connections:
        state = "missing"
    elif missing_metric_count:
        state = "missing"
    elif stale_metric_count:
        state = "stale"
    elif any(item.status not in {"running", "connected"} for item in enabled_connections):
        state = "degraded"
    else:
        state = "healthy"

    return {
        "enabled": enabled,
        "required": required,
        "state": state,
        "stale_after_seconds": stale_after_seconds,
        "connection_count": len(connections),
        "enabled_connection_count": len(enabled_connections),
        "missing_metric_count": missing_metric_count,
        "stale_metric_count": stale_metric_count,
        "connections": connection_items,
    }


def _nwp_overview(
    session,
    now: datetime,
    enabled: bool,
    required: bool,
    stale_after_seconds: int,
    farm_code: str | None,
) -> dict:
    query = session.query(IngestionBatch).filter(IngestionBatch.source_type == "nwp")
    if farm_code:
        query = query.filter(IngestionBatch.farm_code == farm_code)
    batches = query.order_by(IngestionBatch.received_at.desc()).limit(200).all()
    latest_completed = {}
    for batch in batches:
        if batch.status == "completed":
            latest_completed.setdefault(batch.farm_code, batch)

    latest_items = []
    stale_count = 0
    for batch in latest_completed.values():
        reference_time = batch.completed_at or batch.received_at or batch.event_time
        age = _age_seconds(now, reference_time)
        state = "fresh" if age is not None and age <= stale_after_seconds else "stale"
        if state == "stale":
            stale_count += 1
        latest_items.append({
            "id": batch.id,
            "farm_code": batch.farm_code,
            "message_id": batch.message_id,
            "schema_version": batch.schema_version,
            "event_time": _iso(batch.event_time),
            "completed_at": _iso(batch.completed_at),
            "age_seconds": age,
            "state": state,
            "quality_status": batch.quality_status,
            "accepted_count": batch.accepted_count,
            "rejected_count": batch.rejected_count,
        })

    if not enabled:
        state = "disabled"
    elif not latest_items:
        state = "missing"
    elif stale_count:
        state = "stale"
    elif any(item["quality_status"] != "good" for item in latest_items):
        state = "degraded"
    else:
        state = "healthy"

    return {
        "enabled": enabled,
        "required": required,
        "state": state,
        "stale_after_seconds": stale_after_seconds,
        "latest_batches": sorted(latest_items, key=lambda item: item["farm_code"]),
        "status_counts": dict(Counter(batch.status for batch in batches)),
        "stale_farm_count": stale_count,
    }


def _prediction_overview(session, now: datetime, farm_code: str | None) -> dict:
    since = now - timedelta(hours=24)
    query = (
        session.query(PredictionRun, PredictionTask)
        .join(PredictionTask, PredictionRun.task_id == PredictionTask.id)
        .filter(PredictionRun.created_at >= since)
    )
    if farm_code:
        query = query.filter(PredictionTask.farm_code == farm_code)
    rows = query.order_by(PredictionRun.created_at.desc()).limit(200).all()
    status_counts = Counter(str(run.status or "unknown").lower() for run, _ in rows)
    run_ids = [run.id for run, _ in rows]
    output_rows = []
    if run_ids:
        output_rows = session.query(ForecastOutputPoint).filter(
            ForecastOutputPoint.prediction_run_id.in_(run_ids)
        ).all()
    outputs_by_run = {}
    for output in output_rows:
        outputs_by_run.setdefault(output.prediction_run_id, []).append(output)

    latest_runs = []
    for run, task in rows[:12]:
        outputs = outputs_by_run.get(run.id, [])
        expected_count = 16 if task.task_type == "supershort" else 96
        if run.action != "predict":
            trace_status = "not_applicable"
        elif len(outputs) >= expected_count:
            trace_status = "complete"
        elif outputs:
            trace_status = "partial"
        else:
            trace_status = "missing"
        latest_runs.append({
            "id": run.id,
            "farm_code": task.farm_code,
            "task_type": task.task_type,
            "action": run.action,
            "status": run.status,
            "started_at": _iso(run.started_at),
            "finished_at": _iso(run.finished_at),
            "duration_sec": run.duration_sec,
            "error_message": run.error_message,
            "output_point_count": len(outputs),
            "output_trace_status": trace_status,
        })

    snapshot_query = session.query(PredictionInputSnapshot)
    if farm_code:
        snapshot_query = snapshot_query.filter(PredictionInputSnapshot.farm_code == farm_code)
    snapshots = snapshot_query.order_by(PredictionInputSnapshot.captured_at.desc()).limit(12).all()
    snapshot_run_ids = [item.prediction_run_id for item in snapshots]
    missing_output_run_ids = [run_id for run_id in snapshot_run_ids if run_id not in outputs_by_run]
    if missing_output_run_ids:
        for output in session.query(ForecastOutputPoint).filter(
            ForecastOutputPoint.prediction_run_id.in_(missing_output_run_ids)
        ).all():
            outputs_by_run.setdefault(output.prediction_run_id, []).append(output)
    snapshot_runs = {
        run.id: run
        for run in session.query(PredictionRun).filter(PredictionRun.id.in_(snapshot_run_ids)).all()
    } if snapshot_run_ids else {}
    snapshot_items = []
    for item in snapshots:
        outputs = outputs_by_run.get(item.prediction_run_id, [])
        run = snapshot_runs.get(item.prediction_run_id)
        output_manifest = None
        if run and run.result_json:
            try:
                output_manifest = (json.loads(run.result_json) or {}).get("output_manifest")
            except (TypeError, ValueError):
                output_manifest = None
        expected_count = 16 if item.task_type == "supershort" else 96
        snapshot_items.append({
            "id": item.id,
            "prediction_run_id": item.prediction_run_id,
            "farm_code": item.farm_code,
            "task_type": item.task_type,
            "captured_at": _iso(item.captured_at),
            "dataset_version": item.dataset_version,
            "model_version_id": item.model_version_id,
            "status": item.status,
            "missing_rate": item.missing_rate,
            "manifest_sha256": item.manifest_sha256,
            "output_point_count": len(outputs),
            "output_trace_status": (
                "complete" if len(outputs) >= expected_count else ("partial" if outputs else "missing")
            ),
            "output_target_start": _iso(min((row.target_time for row in outputs), default=None)),
            "output_target_end": _iso(max((row.target_time for row in outputs), default=None)),
            "output_sha256": output_manifest.get("output_sha256") if output_manifest else None,
            "regulatory_delivery_ready": (
                output_manifest.get("regulatory_delivery_ready") if output_manifest else False
            ),
        })
    successful_predict_runs = [
        run for run, _ in rows
        if run.action == "predict" and str(run.status).lower() == "success"
    ]
    missing_trace_count = sum(
        1 for run in successful_predict_runs if not outputs_by_run.get(run.id)
    )
    return {
        "window_hours": 24,
        "status_counts": dict(sorted(status_counts.items())),
        "latest_runs": latest_runs,
        "latest_input_snapshots": snapshot_items,
        "output_point_count": len(output_rows),
        "traced_prediction_run_count": sum(
            1 for run in successful_predict_runs if outputs_by_run.get(run.id)
        ),
        "missing_output_trace_count": missing_trace_count,
    }


def _reporting_overview(session, now: datetime, farm_code: str | None) -> dict:
    query = session.query(ReportOutbox)
    if farm_code:
        query = query.filter(ReportOutbox.farm_code == farm_code)
    rows = query.order_by(ReportOutbox.created_at.desc()).limit(1000).all()
    counts = Counter(str(item.status or "unknown").lower() for item in rows)
    pending = [
        item for item in rows
        if str(item.status or "").lower() in {"pending", "retry", "processing"}
    ]
    oldest_pending = min((item.created_at for item in pending if item.created_at), default=None)
    return {
        "status_counts": dict(sorted(counts.items())),
        "pending_count": len(pending),
        "dead_count": counts.get("dead", 0),
        "oldest_pending_age_seconds": _age_seconds(now, oldest_pending),
        "latest_failures": [{
            "id": item.id,
            "farm_code": item.farm_code,
            "report_type": item.report_type,
            "status": item.status,
            "attempt_count": item.attempt_count,
            "last_error": item.last_error,
            "updated_at": _iso(item.updated_at),
        } for item in rows if str(item.status or "").lower() in {"dead", "retry"}][:10],
    }


def _model_overview(session, farm_code: str | None) -> dict:
    query = session.query(ModelVersion)
    if farm_code:
        query = query.filter(ModelVersion.farm_code == farm_code)
    rows = query.order_by(ModelVersion.trained_at.desc()).limit(500).all()
    lifecycle_counts = Counter(str(item.lifecycle_status or "candidate") for item in rows)
    candidates = [item for item in rows if item.lifecycle_status == "candidate"]
    recent_versions = [{
        "id": item.id,
        "farm_code": item.farm_code,
        "task_type": item.task_type,
        "algorithm": item.algorithm,
        "val_accuracy": item.val_accuracy,
        "is_active": bool(item.is_active),
        "lifecycle_status": item.lifecycle_status,
        "trained_at": _iso(item.trained_at),
        "approved_by": item.approved_by,
        "approved_at": _iso(item.approved_at),
        "dataset_version": item.dataset_version,
        "artifact_sha256": item.artifact_sha256,
        "rejection_reason": item.rejection_reason,
    } for item in rows[:20]]
    return {
        "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
        "active_count": sum(1 for item in rows if item.is_active),
        "recent_versions": recent_versions,
        "candidates": [{
            "id": item.id,
            "farm_code": item.farm_code,
            "task_type": item.task_type,
            "algorithm": item.algorithm,
            "val_accuracy": item.val_accuracy,
            "trained_at": _iso(item.trained_at),
            "dataset_version": item.dataset_version,
            "artifact_sha256": item.artifact_sha256,
        } for item in candidates[:12]],
    }


def build_operations_overview(
    session,
    *,
    now: datetime | None = None,
    farm_code: str | None = None,
    scada_enabled: bool = False,
    scada_required: bool = False,
    scada_stale_after_seconds: int = 1200,
    nwp_enabled: bool = False,
    nwp_required: bool = False,
    nwp_stale_after_seconds: int = 21600,
    storage_path: str | None = None,
) -> dict:
    """构建单次只读运维快照，供界面和现场巡检脚本共用。"""
    effective_now = now or _beijing_now()
    scada = _scada_overview(
        session,
        effective_now,
        scada_enabled,
        scada_required,
        scada_stale_after_seconds,
        farm_code,
    )
    nwp = _nwp_overview(
        session,
        effective_now,
        nwp_enabled,
        nwp_required,
        nwp_stale_after_seconds,
        farm_code,
    )
    prediction = _prediction_overview(session, effective_now, farm_code)
    reporting = _reporting_overview(session, effective_now, farm_code)
    models = _model_overview(session, farm_code)
    storage = _storage_overview(storage_path)

    issues = []
    critical = False
    if scada_enabled and scada["state"] != "healthy":
        issues.append({
            "domain": "scada",
            "severity": "critical" if scada_required else "warning",
            "message": "SCADA 实时数据存在缺失、过期或连接异常",
        })
        critical = critical or scada_required
    if nwp_enabled and nwp["state"] != "healthy":
        issues.append({
            "domain": "nwp",
            "severity": "critical" if nwp_required else "warning",
            "message": "NWP 数据批次缺失、过期或质量降级",
        })
        critical = critical or nwp_required
    failed_runs = sum(
        count for status, count in prediction["status_counts"].items()
        if status in {"failed", "failure", "error"}
    )
    if failed_runs:
        issues.append({
            "domain": "prediction",
            "severity": "warning",
            "message": f"最近 24 小时存在 {failed_runs} 次预测或训练失败",
        })
    missing_output_trace_count = prediction.get("missing_output_trace_count", 0)
    if missing_output_trace_count:
        issues.append({
            "domain": "prediction",
            "severity": "warning",
            "message": f"最近 24 小时有 {missing_output_trace_count} 次成功预测缺少输出账本",
        })
    if reporting["dead_count"]:
        issues.append({
            "domain": "reporting",
            "severity": "critical",
            "message": f"可靠上报队列存在 {reporting['dead_count']} 条死信",
        })
        critical = True
    if storage["used_percent"] >= 90:
        issues.append({
            "domain": "storage",
            "severity": "critical",
            "message": f"运行磁盘使用率达到 {storage['used_percent']}%",
        })
        critical = True
    elif storage["used_percent"] >= 80:
        issues.append({
            "domain": "storage",
            "severity": "warning",
            "message": f"运行磁盘使用率达到 {storage['used_percent']}%",
        })

    overall_state = "critical" if critical else ("degraded" if issues else "healthy")
    return {
        "generated_at": _iso(effective_now),
        "farm_code": farm_code,
        "overall": {
            "state": overall_state,
            "issue_count": len(issues),
            "issues": issues,
        },
        "scada": scada,
        "nwp": nwp,
        "prediction": prediction,
        "reporting": reporting,
        "models": models,
        "storage": storage,
    }


def list_prediction_input_snapshots(
    session,
    *,
    farm_code: str | None = None,
    prediction_run_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    query = session.query(PredictionInputSnapshot)
    if farm_code:
        query = query.filter(PredictionInputSnapshot.farm_code == farm_code)
    if prediction_run_id is not None:
        query = query.filter(PredictionInputSnapshot.prediction_run_id == prediction_run_id)
    rows = query.order_by(PredictionInputSnapshot.captured_at.desc()).limit(min(max(limit, 1), 200)).all()
    return [{
        "id": item.id,
        "prediction_run_id": item.prediction_run_id,
        "farm_code": item.farm_code,
        "task_type": item.task_type,
        "captured_at": _iso(item.captured_at),
        "contract_version": item.contract_version,
        "dataset_version": item.dataset_version,
        "model_version_id": item.model_version_id,
        "data_start": _iso(item.data_start),
        "data_end": _iso(item.data_end),
        "scada_observation_count": item.scada_observation_count,
        "nwp_record_count": item.nwp_record_count,
        "missing_rate": item.missing_rate,
        "status": item.status,
        "quality_summary": item.quality_summary,
        "input_manifest": item.input_manifest,
        "manifest_sha256": item.manifest_sha256,
    } for item in rows]
