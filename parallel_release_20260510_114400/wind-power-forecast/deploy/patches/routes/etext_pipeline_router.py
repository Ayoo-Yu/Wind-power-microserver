"""E text pipeline configuration and manual trigger API."""

import json
import os
import sys
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify

from services.etext_config import read_config, write_config, validate_and_apply_config_updates, PROJECT_ROOT

etext_pipeline_bp = Blueprint('etext_pipeline', __name__)

ETEXT_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "etext")
JOB_DIR = os.path.join(ETEXT_DATA_DIR, "jobs")

# Gevent monkey-patches threading.Thread to use greenlets, but psycopg2 is a
# C extension whose socket I/O blocks the gevent hub.  Use gevent's ThreadPool
# which runs tasks on *real* OS threads so the Flask response returns immediately.
try:
    from gevent.threadpool import ThreadPool as _GeventThreadPool
    _bg_pool = _GeventThreadPool(maxsize=2)
except ImportError:
    _bg_pool = None


def _run_in_background(func):
    if _bg_pool is not None:
        _bg_pool.spawn(func)
    else:
        import threading
        t = threading.Thread(target=func, daemon=True)
        t.start()


def _get_scheduler():
    from services.scheduler_service import get_scheduler
    return get_scheduler()


def _job_path(job_id):
    safe_job_id = "".join(ch for ch in job_id if ch.isalnum() or ch in ("_", "-"))
    return os.path.join(JOB_DIR, f"{safe_job_id}.json")


def _write_job(job_id, payload):
    os.makedirs(JOB_DIR, exist_ok=True)
    tmp = _job_path(job_id) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, _job_path(job_id))


def _read_job(job_id):
    try:
        with open(_job_path(job_id), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None


@etext_pipeline_bp.route('/api/etext_pipeline/config', methods=['GET'])
def get_config():
    cfg = read_config()
    job_info = None
    svc = _get_scheduler()
    if svc:
        job = svc.scheduler.get_job("etext_pipeline_daily")
        if job:
            job_info = {
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
    return jsonify({"config": cfg, "job": job_info})


@etext_pipeline_bp.route('/api/etext_pipeline/config', methods=['PUT'])
def update_config():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Empty body"}), 400

    cfg = read_config()
    cfg, err = validate_and_apply_config_updates(cfg, data)
    if err:
        return jsonify({"error": err}), 400

    write_config(cfg)

    svc = _get_scheduler()
    if svc:
        svc.update_etext_pipeline_schedule(cfg)

    return jsonify({"config": cfg})


@etext_pipeline_bp.route('/api/etext_pipeline/trigger', methods=['POST'])
def trigger_pipeline():
    """Trigger pipeline in background, return job_id to poll."""
    cfg = read_config()
    job_id = str(uuid.uuid4())[:8]
    started_at = datetime.now().isoformat()
    _write_job(job_id, {"status": "running", "started_at": started_at})

    def _run():
        try:
            scripts_dir = os.path.join(PROJECT_ROOT, "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            from etext_pipeline import run_pipeline
            results = run_pipeline(incoming_dir=cfg["incoming_dir"] or None, force=True)
            if not results:
                _write_job(job_id, {
                    "status": "done",
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(),
                    "tables": 0,
                    "inserted": 0,
                    "updated": 0,
                    "errors": 0,
                    "message": "No .dat files found in incoming directory",
                })
            else:
                _write_job(job_id, {
                    "status": "done",
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(),
                    "tables": len(results),
                    "inserted": sum(r.get("inserted", 0) for r in results),
                    "updated": sum(r.get("updated", 0) for r in results),
                    "errors": sum(r.get("errors", 0) for r in results),
                })
        except Exception as e:
            _write_job(job_id, {
                "status": "failed",
                "started_at": started_at,
                "finished_at": datetime.now().isoformat(),
                "error": str(e),
            })

    _run_in_background(_run)
    return jsonify({"job_id": job_id, "status": "running"})


@etext_pipeline_bp.route('/api/etext_pipeline/trigger/<job_id>', methods=['GET'])
def get_trigger_status(job_id):
    """Poll trigger job status."""
    job = _read_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)
