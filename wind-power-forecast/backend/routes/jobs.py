from flask import Blueprint, jsonify, request
from celery import states

from services.job_service import create_job, get_job, serialize_job, update_job_metadata
from tasks.training_tasks import train_model_task
from tasks.prediction_tasks import predict_task


jobs_bp = Blueprint('jobs', __name__)


def _validate_train_payload(data: dict):
    required = ['file_id', 'model']
    missing = [key for key in required if key not in data]
    if missing:
        return False, f"缺少必要参数: {', '.join(missing)}"
    return True, None


def _validate_predict_payload(data: dict):
    required = ['csvfileId', 'modelfileId', 'scalerfileId']
    missing = [key for key in required if key not in data]
    if missing:
        return False, f"缺少必要参数: {', '.join(missing)}"
    return True, None


@jobs_bp.route('/jobs/train', methods=['POST'])
def submit_train_job():
    data = request.get_json() or {}
    is_valid, error = _validate_train_payload(data)
    if not is_valid:
        return jsonify({'error': error}), 400

    async_result = train_model_task.apply_async(kwargs={'payload': data})
    create_job(async_result.id, 'train', payload=data)
    update_job_metadata(async_result.id, payload=data)
    return jsonify({'job_id': async_result.id, 'status': states.PENDING}), 202


@jobs_bp.route('/jobs/predict', methods=['POST'])
def submit_predict_job():
    data = request.get_json() or {}
    is_valid, error = _validate_predict_payload(data)
    if not is_valid:
        return jsonify({'error': error}), 400

    async_result = predict_task.apply_async(kwargs={'payload': data})
    create_job(async_result.id, 'predict', payload=data)
    update_job_metadata(async_result.id, payload=data)
    return jsonify({'job_id': async_result.id, 'status': states.PENDING}), 202


@jobs_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(serialize_job(job))
