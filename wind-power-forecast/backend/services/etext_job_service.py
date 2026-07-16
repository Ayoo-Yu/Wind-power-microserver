"""E 文本处理任务的持久化状态与执行入口。"""

import json
import os
import sys
from datetime import datetime, timedelta

from services.etext_config import PROJECT_ROOT


ETEXT_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "etext")
JOB_DIR = os.path.join(ETEXT_DATA_DIR, "jobs")


def _job_path(job_id: str) -> str:
    safe_job_id = "".join(ch for ch in str(job_id) if ch.isalnum() or ch in ("_", "-"))
    if not safe_job_id:
        raise ValueError("任务编号无效")
    return os.path.join(JOB_DIR, f"{safe_job_id}.json")


def write_job(job_id: str, payload: dict) -> None:
    """原子写入可供 Web 进程查询的任务状态。"""

    os.makedirs(JOB_DIR, exist_ok=True)
    path = _job_path(job_id)
    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, ensure_ascii=False)
    os.replace(temporary_path, path)


def read_job(job_id: str):
    """读取任务状态，文件不存在或损坏时返回空值。"""

    try:
        with open(_job_path(job_id), "r", encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        return None


def describe_schedule(config: dict) -> dict:
    """返回前端可展示的调度规则和下一次计划时间。"""

    if not config.get("enabled", True):
        return None

    minutes = sorted({int(value) for value in config.get("schedule_minutes") or []})
    if not minutes:
        return None

    hour = int(config.get("schedule_hour", 8))
    now = datetime.now()
    next_run = None
    for day_offset in (0, 1):
        day = now + timedelta(days=day_offset)
        for minute in minutes:
            candidate = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate > now:
                next_run = candidate
                break
        if next_run:
            break

    return {
        "next_run_time": next_run.isoformat() if next_run else None,
        "trigger": f"{','.join(str(value) for value in minutes)} {hour} * * *",
        "mode": "celery",
        "managed_externally": True,
    }


def execute_pipeline(
    *,
    incoming_dir=None,
    force: bool = False,
    job_id=None,
    started_at=None,
) -> dict:
    """执行 E 文本管道，并按需更新手动任务状态。"""

    started_at = started_at or datetime.now().isoformat()
    if job_id:
        write_job(job_id, {"status": "running", "started_at": started_at})
    try:
        scripts_dir = os.path.join(PROJECT_ROOT, "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

        from etext_pipeline import run_pipeline

        results = run_pipeline(incoming_dir=incoming_dir or None, force=force)
        if not results:
            payload = {
                "status": "done",
                "started_at": started_at,
                "finished_at": datetime.now().isoformat(),
                "tables": 0,
                "inserted": 0,
                "updated": 0,
                "errors": 0,
                "message": "No .dat files found in incoming directory",
            }
        else:
            payload = {
                "status": "done",
                "started_at": started_at,
                "finished_at": datetime.now().isoformat(),
                "tables": len(results),
                "inserted": sum(result.get("inserted", 0) for result in results),
                "updated": sum(result.get("updated", 0) for result in results),
                "errors": sum(result.get("errors", 0) for result in results),
            }

        if job_id:
            write_job(job_id, payload)
        return payload
    except Exception as exc:
        payload = {
            "status": "failed",
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(),
            "error": str(exc),
        }
        if job_id:
            write_job(job_id, payload)
        raise
