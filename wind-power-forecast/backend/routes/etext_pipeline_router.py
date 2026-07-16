"""E text pipeline configuration and manual trigger API."""

import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify

from services.etext_config import read_config, write_config, validate_and_apply_config_updates
from services.etext_job_service import describe_schedule, read_job, write_job
from utils.authorization import permission_required

etext_pipeline_bp = Blueprint('etext_pipeline', __name__)

@etext_pipeline_bp.route('/api/etext_pipeline/config', methods=['GET'])
@permission_required('manage_weather_data')
def get_config():
    cfg = read_config()
    return jsonify({"config": cfg, "job": describe_schedule(cfg)})


@etext_pipeline_bp.route('/api/etext_pipeline/config', methods=['PUT'])
@permission_required('manage_weather_data')
def update_config():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Empty body"}), 400

    cfg = read_config()
    cfg, err = validate_and_apply_config_updates(cfg, data)
    if err:
        return jsonify({"error": err}), 400

    write_config(cfg)
    return jsonify({"config": cfg, "job": describe_schedule(cfg)})


@etext_pipeline_bp.route('/api/etext_pipeline/trigger', methods=['POST'])
@permission_required('manage_weather_data')
def trigger_pipeline():
    """将手动处理请求提交到 Celery 队列，并返回可轮询任务号。"""
    cfg = read_config()
    job_id = str(uuid.uuid4())[:8]
    started_at = datetime.now().isoformat()
    write_job(job_id, {"status": "queued", "started_at": started_at})

    try:
        from celery_app.tasks import run_etext_pipeline

        result = run_etext_pipeline.apply_async(
            kwargs={
                "job_id": job_id,
                "incoming_dir": cfg["incoming_dir"] or None,
                "force": True,
                "started_at": started_at,
            }
        )
    except Exception as exc:
        write_job(job_id, {
            "status": "failed",
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(),
            "error": f"任务队列不可用: {exc}",
        })
        return jsonify({"error": "任务队列当前不可用"}), 503

    return jsonify({
        "job_id": job_id,
        "celery_task_id": result.id,
        "status": "queued",
    }), 202


@etext_pipeline_bp.route('/api/etext_pipeline/trigger/<job_id>', methods=['GET'])
@permission_required('manage_weather_data')
def get_trigger_status(job_id):
    """Poll trigger job status."""
    job = read_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)
