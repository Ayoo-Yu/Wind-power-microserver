"""Celery-backed routes for managing automatic power prediction."""

from __future__ import annotations

import datetime
import glob
import os
from pathlib import Path
from typing import Any, Dict, List

from celery.result import AsyncResult
from flask import Blueprint, jsonify, request

from celery_app import celery_app
from config import Config
from services.autopredict_config_service import (
    VALID_TASK_TYPES,
    delete_job,
    get_or_create_job,
    list_jobs_for_wind_farm,
    set_job_enabled,
)
from services.task_history_service import record_task_history
from tasks.autopredict import (
    predict_middle,
    predict_short,
    predict_supershort,
    train_middle,
    train_short,
    train_supershort,
)


autopredict_bp = Blueprint("autopredict", __name__)

log_dirs = Config.LOG_DIRS
DEFAULT_WIND_FARM_CODE = Config.DEFAULT_WIND_FARM_CODE

TASK_EXECUTION_MAP = {
    "short": {
        "train": train_short,
        "predict": predict_short,
    },
    "medium": {
        "train": train_middle,
        "predict": predict_middle,
    },
    "supershort": {
        "train": train_supershort,
        "predict": predict_supershort,
    },
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def normalize_wind_farm_code(raw_code: str | None) -> str:
    raw_code = (raw_code or "").strip()
    return raw_code or DEFAULT_WIND_FARM_CODE


def resolve_request_wind_farm_code(data: Any) -> str:
    if isinstance(data, dict):
        candidate = data.get("wind_farm_code") or data.get("windFarmCode")
    else:
        candidate = data
    if not candidate:
        candidate = request.headers.get("X-Windfarm-Code")
    return normalize_wind_farm_code(candidate)


def resolve_log_dir(prediction_type: str, log_key: str, wind_farm_code: str) -> Path | None:
    base_dir = log_dirs.get(prediction_type, {}).get(log_key)
    if not base_dir:
        return None
    normalized_code = normalize_wind_farm_code(wind_farm_code)
    target_dir = Path(base_dir)
    if normalized_code != DEFAULT_WIND_FARM_CODE:
        target_dir = target_dir / normalized_code
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def trigger_initial_run(prediction_type: str, wind_farm_code: str) -> List[str]:
    """Queue an immediate train/predict cycle for the given type."""

    mapping = TASK_EXECUTION_MAP[prediction_type]
    task_ids: List[str] = []

    if prediction_type in {"short", "medium"}:
        result_train: AsyncResult = mapping["train"].apply_async((wind_farm_code, "train"))
        task_ids.append(result_train.id)
        result_predict: AsyncResult = mapping["predict"].apply_async((wind_farm_code,))
        task_ids.append(result_predict.id)
    else:  # supershort
        result_train = mapping["train"].apply_async((wind_farm_code,))
        result_predict = mapping["predict"].apply_async((wind_farm_code,))
        task_ids.extend([result_train.id, result_predict.id])

    return task_ids


def serialize_jobs(jobs) -> Dict[str, Dict[str, Any]]:
    data: Dict[str, Dict[str, Any]] = {}
    for job in jobs:
        data[job.task_type] = {
            "enabled": job.enabled,
            "schedule_cron": job.schedule_cron,
            "last_triggered_at": job.last_triggered_at.isoformat() if job.last_triggered_at else None,
        }
    return data


def collect_active_tasks() -> Dict[str, List[dict[str, Any]]]:
    inspector = celery_app.control.inspect()
    active = inspector.active() or {}
    pending = inspector.scheduled() or {}
    result: Dict[str, List[dict[str, Any]]] = {}

    for bucket in (active, pending):
        for _, tasks in bucket.items():
            for task in tasks:
                name = task.get("name")
                result.setdefault(name, []).append(task)

    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@autopredict_bp.route("/status", methods=["GET"])
def get_status():
    wind_farm_code = resolve_request_wind_farm_code(request.args.get("wind_farm_code"))
    jobs = list_jobs_for_wind_farm(wind_farm_code)

    response = {task_type: False for task_type in VALID_TASK_TYPES}
    meta = serialize_jobs(jobs)
    for task_type in VALID_TASK_TYPES:
        if task_type in meta:
            response[task_type] = meta[task_type]["enabled"]
    response["meta"] = meta
    return jsonify(response)


@autopredict_bp.route("/start", methods=["POST"])
def start_prediction():
    data = request.get_json() or {}
    prediction_type = data.get("type")
    if prediction_type not in VALID_TASK_TYPES:
        return jsonify({"error": "无效的预测类型"}), 400

    wind_farm_code = resolve_request_wind_farm_code(data)
    job = get_or_create_job(prediction_type, wind_farm_code)
    set_job_enabled(prediction_type, wind_farm_code, enabled=True)

    record_task_history(
        task_type=prediction_type,
        wind_farm_code=wind_farm_code,
        action="start",
        status="success",
    )

    task_ids = trigger_initial_run(prediction_type, wind_farm_code)
    return jsonify(
        {
            "message": f"已启用 {prediction_type} 预测任务，并触发一次执行",
            "task_ids": task_ids,
            "job": {
                "enabled": True,
                "schedule_cron": job.schedule_cron,
            },
        }
    )


@autopredict_bp.route("/stop", methods=["POST"])
def stop_prediction():
    data = request.get_json() or {}
    prediction_type = data.get("type")
    if prediction_type not in VALID_TASK_TYPES:
        return jsonify({"error": "无效的预测类型"}), 400

    wind_farm_code = resolve_request_wind_farm_code(data)
    set_job_enabled(prediction_type, wind_farm_code, enabled=False)
    record_task_history(
        task_type=prediction_type,
        wind_farm_code=wind_farm_code,
        action="stop",
        status="success",
    )
    return jsonify({"message": f"已停止 {prediction_type} 预测任务"})


@autopredict_bp.route("/delete", methods=["POST"])
def delete_prediction():
    data = request.get_json() or {}
    prediction_type = data.get("type")
    if prediction_type not in VALID_TASK_TYPES:
        return jsonify({"error": "无效的预测类型"}), 400

    wind_farm_code = resolve_request_wind_farm_code(data)
    delete_job(prediction_type, wind_farm_code)
    record_task_history(
        task_type=prediction_type,
        wind_farm_code=wind_farm_code,
        action="delete",
        status="success",
    )
    return jsonify({"message": f"已删除 {prediction_type} 的调度配置"})


@autopredict_bp.route("/trigger", methods=["POST"])
def trigger_prediction():
    data = request.get_json() or {}
    prediction_type = data.get("type")
    if prediction_type not in VALID_TASK_TYPES:
        return jsonify({"error": "无效的预测类型"}), 400

    wind_farm_code = resolve_request_wind_farm_code(data)
    task_ids = trigger_initial_run(prediction_type, wind_farm_code)
    record_task_history(
        task_type=prediction_type,
        wind_farm_code=wind_farm_code,
        action="trigger",
        status="success",
        details=f"task_ids={task_ids}",
    )
    return jsonify({"message": "任务已触发", "task_ids": task_ids})


@autopredict_bp.route("/logs", methods=["GET"])
def get_logs():
    prediction_type = request.args.get("type")
    log_type = request.args.get("logType", "train")
    date_str = request.args.get("date", datetime.datetime.now().strftime("%Y%m%d"))
    lines = request.args.get("lines", 500, type=int)
    wind_farm_code = resolve_request_wind_farm_code(request.args.get("wind_farm_code"))

    if not prediction_type or prediction_type not in VALID_TASK_TYPES:
        return jsonify({"error": "无效的预测类型"}), 400

    if log_type == "main":
        return jsonify({"error": "主日志不可用：Celery 模式下无需主日志"}), 400

    log_dir = resolve_log_dir(prediction_type, log_type, wind_farm_code)
    if not log_dir:
        return jsonify({"error": f"无效的日志类型: {log_type}"}), 400

    log_files = glob.glob(str(log_dir / f"{date_str}*.log"))
    if not log_files:
        return jsonify({"logs": f"未找到{date_str}的{log_type}日志文件"})

    latest_log = max(log_files, key=os.path.getmtime)
    with open(latest_log, "r", encoding="utf-8", errors="replace") as fp:
        all_lines = fp.readlines()
        log_content = "".join(all_lines[-lines:]) if len(all_lines) > lines else "".join(all_lines)

    file_info = (
        f"文件: {os.path.basename(latest_log)}\n"
        f"日期: {datetime.datetime.fromtimestamp(os.path.getmtime(latest_log)).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    log_content = file_info + log_content

    record_task_history(
        task_type=prediction_type,
        wind_farm_code=wind_farm_code,
        action="logs",
        status="success",
        details=f"{log_type}::{latest_log}",
    )

    return jsonify({"logs": log_content})


@autopredict_bp.route("/history", methods=["GET"])
def get_task_history():
    from db_models import TaskHistory  # Imported lazily to avoid circular imports
    from db_session import db_session

    task_type = request.args.get("type")
    action = request.args.get("action")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    wind_farm_code = request.args.get("wind_farm_code")

    with db_session() as session:
        query = session.query(TaskHistory).order_by(TaskHistory.created_at.desc())
        if task_type:
            query = query.filter(TaskHistory.task_type == task_type)
        if action:
            query = query.filter(TaskHistory.action == action)
        if wind_farm_code:
            query = query.filter(TaskHistory.wind_farm_code == wind_farm_code)

        total = query.count()
        history = query.offset(offset).limit(limit).all()

        data = [
            {
                "id": item.id,
                "task_id": item.task_id,
                "task_type": item.task_type,
                "wind_farm_code": item.wind_farm_code,
                "action": item.action,
                "status": item.status,
                "details": item.details,
                "user": item.user,
                "created_at": item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else None,
            }
            for item in history
        ]

    return jsonify({
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": data,
    })


@autopredict_bp.route("/task_status", methods=["GET"])
def get_task_status():
    prediction_type = request.args.get("type")
    wind_farm_code = resolve_request_wind_farm_code(request.args.get("wind_farm_code"))
    if prediction_type not in VALID_TASK_TYPES:
        return jsonify({"error": "无效的预测类型"}), 400

    jobs_meta = serialize_jobs(list_jobs_for_wind_farm(wind_farm_code))
    active_tasks = collect_active_tasks()

    predict_task_name = TASK_EXECUTION_MAP[prediction_type]["predict"].name
    response = {
        "enabled": jobs_meta.get(prediction_type, {}).get("enabled", False),
        "last_triggered_at": jobs_meta.get(prediction_type, {}).get("last_triggered_at"),
        "active_tasks": active_tasks.get(predict_task_name, []),
    }
    return jsonify(response)


__all__ = ["autopredict_bp"]

