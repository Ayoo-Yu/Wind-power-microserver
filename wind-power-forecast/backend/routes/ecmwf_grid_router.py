"""
ECMWF 格点气象数据入库路由 (每场独立表)

POST /api/ecmwf/grid/ingest_async — 异步上传长格式 CSV，按 farm_code 路由到对应表
GET  /api/ecmwf/grid/import_jobs/<job_id> — 查询导入任务进度
"""

import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from services.import_job_service import import_job_store

logger = logging.getLogger(__name__)

ecmwf_grid_bp = Blueprint('ecmwf_grid', __name__)


@ecmwf_grid_bp.route('/api/ecmwf/grid/ingest_async', methods=['POST'])
@jwt_required()
def ingest_grid_csv_async():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'Only CSV files are supported'}), 400

    farm_code = request.form.get('farm_code', '').strip()
    if not farm_code:
        return jsonify({'error': 'farm_code is required'}), 400

    try:
        job = import_job_store.create_ecmwf_grid_job(file, farm_code)
        return jsonify(job.to_dict()), 202
    except Exception as e:
        logger.exception("Failed to create ECMWF grid ingest job")
        return jsonify({'error': str(e)}), 500


@ecmwf_grid_bp.route('/api/ecmwf/grid/import_jobs/<job_id>', methods=['GET'])
@jwt_required()
def get_grid_import_job(job_id):
    job = import_job_store.get_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    response = jsonify(job.to_dict())
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response, 200
