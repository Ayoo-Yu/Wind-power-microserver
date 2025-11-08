from flask import Blueprint, jsonify, request
from celery import states
from typing import Optional

from services.job_service import create_job, get_job, serialize_job, update_job_metadata
from tasks.training_tasks import train_model_task
from tasks.prediction_tasks import predict_task
from database_config import SessionLocal
from ..db_models import Dataset
from ..config import MINIO_CONFIG
from windpower_core.storage import normalize_wind_farm_code


jobs_bp = Blueprint('jobs', __name__)


def _resolve_wind_farm_by_file_id(file_id: Optional[str]) -> tuple[Optional[int], str]:
    default_code = MINIO_CONFIG.get("default_wind_farm_code", "default-farm")
    if not file_id or SessionLocal is None:
        return None, default_code

    session = SessionLocal()
    try:
        dataset = session.query(Dataset).filter(Dataset.file_id == file_id).first()
        if not dataset:
            return None, default_code
        code = normalize_wind_farm_code(dataset.wind_farm_code or dataset.wind_farm, default_code)
        return dataset.wind_farm_id, code
    finally:
        session.close()


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

    wind_farm_id, wind_farm_code = _resolve_wind_farm_by_file_id(data.get('file_id'))
    if 'wind_farm_code' not in data or not data.get('wind_farm_code'):
        data['wind_farm_code'] = wind_farm_code

    async_result = train_model_task.apply_async(kwargs={'payload': data})
    create_job(
        async_result.id,
        'train',
        payload=data,
        wind_farm_id=wind_farm_id,
        wind_farm_code=wind_farm_code,
    )
    update_job_metadata(async_result.id, payload=data, wind_farm_id=wind_farm_id, wind_farm_code=wind_farm_code)
    return jsonify({'job_id': async_result.id, 'status': states.PENDING}), 202


@jobs_bp.route('/jobs/predict', methods=['POST'])
def submit_predict_job():
    data = request.get_json() or {}
    is_valid, error = _validate_predict_payload(data)
    if not is_valid:
        return jsonify({'error': error}), 400

    wind_farm_id, wind_farm_code = _resolve_wind_farm_by_file_id(data.get('csvfileId'))
    if 'wind_farm_code' not in data or not data.get('wind_farm_code'):
        data['wind_farm_code'] = wind_farm_code

    async_result = predict_task.apply_async(kwargs={'payload': data})
    create_job(
        async_result.id,
        'predict',
        payload=data,
        wind_farm_id=wind_farm_id,
        wind_farm_code=wind_farm_code,
    )
    update_job_metadata(async_result.id, payload=data, wind_farm_id=wind_farm_id, wind_farm_code=wind_farm_code)
    return jsonify({'job_id': async_result.id, 'status': states.PENDING}), 202


@jobs_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(serialize_job(job))
