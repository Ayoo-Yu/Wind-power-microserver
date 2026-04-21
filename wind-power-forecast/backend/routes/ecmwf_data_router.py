"""
ECMWF 气象数据 API 路由

提供气象预报数据的查询、可用性检查和手动摄取接口。
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timedelta
from db_session import db_session
try:
    from services.ecmwf_ingest_service import (
        query_prediction_data,
        get_latest_timestamp,
        get_data_availability,
        ingest_dataframe,
    )
except ImportError:
    query_prediction_data = None
    get_latest_timestamp = None
    get_data_availability = None
    ingest_dataframe = None
from common.api_response import success
import pandas as pd
import logging

logger = logging.getLogger(__name__)

ecmwf_data_bp = Blueprint('ecmwf_data', __name__)


def _require_service():
    if query_prediction_data is None:
        return jsonify({"error": "ECMWF ingest service not available"}), 503
    return None


@ecmwf_data_bp.route('/api/ecmwf/latest', methods=['GET'])
@jwt_required()
def get_latest():
    err = _require_service()
    if err:
        return err
    """获取最新可用预报数据时间戳

    Query params:
        farm_code: 风场编码 (默认 DEFAULT_FARM)
        data_type: 数据类型 DQ/CDQ/QXYC (默认 DQ)
    """
    farm_code = request.args.get('farm_code', 'DEFAULT_FARM')
    data_type = request.args.get('data_type', 'DQ')

    with db_session() as db:
        ts = get_latest_timestamp(db, farm_code, data_type)

    if ts:
        return success(data={
            'farm_code': farm_code,
            'data_type': data_type,
            'latest_timestamp': ts.isoformat() if isinstance(ts, datetime) else str(ts),
        })
    return success(data={'farm_code': farm_code, 'data_type': data_type, 'latest_timestamp': None})


@ecmwf_data_bp.route('/api/ecmwf/data', methods=['GET'])
@jwt_required()
def get_data():
    err = _require_service()
    if err:
        return err
    """查询时间范围内的预报数据

    Query params:
        farm_code: 风场编码
        start: ISO格式起始时间 (如 2026-04-17T00:00:00)
        end: ISO格式结束时间
        data_type: DQ/CDQ/QXYC (默认 DQ)
        limit: 最大返回行数 (默认 1000，上限 50000)
    """
    farm_code = request.args.get('farm_code', 'DEFAULT_FARM')
    data_type = request.args.get('data_type', 'DQ')
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    limit = request.args.get('limit', type=int, default=1000)

    if not start_str or not end_str:
        return jsonify({'error': 'start and end parameters required'}), 400

    try:
        start_time = datetime.fromisoformat(start_str)
        end_time = datetime.fromisoformat(end_str)
    except ValueError:
        return jsonify({'error': 'Invalid ISO datetime format'}), 400

    # 限制查询范围不超过 31 天，防止全表扫描
    if (end_time - start_time).days > 31:
        return jsonify({'error': 'Time range too wide, max 31 days'}), 400

    # 限制行数上限
    limit = min(max(1, limit), 50000)

    with db_session() as db:
        df = query_prediction_data(db, farm_code, start_time, end_time, data_type, limit)

    if df.empty:
        return success(data={'rows': 0, 'data': []})

    # 转为 JSON 友好格式
    return success(data={
        'rows': len(df),
        'columns': list(df.columns),
        'data': df.to_dict(orient='records'),
    })


@ecmwf_data_bp.route('/api/ecmwf/availability', methods=['GET'])
@jwt_required()
def check_availability():
    err = _require_service()
    if err:
        return err
    """检查指定日期的数据可用性

    Query params:
        farm_code: 风场编码
        date: 日期 (YYYY-MM-DD 格式)
    """
    farm_code = request.args.get('farm_code', 'DEFAULT_FARM')
    date_str = request.args.get('date')

    if not date_str:
        return jsonify({'error': 'date parameter required (YYYY-MM-DD)'}), 400

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    with db_session() as db:
        availability = get_data_availability(db, farm_code, date)

    result = {}
    for dtype, info in availability.items():
        result[dtype] = {
            'count': info['count'],
            'min_timestamp': info['min_timestamp'].isoformat() if info['min_timestamp'] else None,
            'max_timestamp': info['max_timestamp'].isoformat() if info['max_timestamp'] else None,
        }

    return success(data={'farm_code': farm_code, 'date': date_str, 'availability': result})


@ecmwf_data_bp.route('/api/ecmwf/ingest', methods=['POST'])
@jwt_required()
def manual_ingest():
    err = _require_service()
    if err:
        return err
    """手动上传 CSV 文件摄取到数据库

    Form data:
        file: CSV 文件
        farm_code: 风场编码
        data_type: 数据类型
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    farm_code = request.form.get('farm_code', 'DEFAULT_FARM')
    data_type = request.form.get('data_type', 'DQ')

    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    try:
        df = pd.read_csv(file.stream)
        if df.empty:
            return jsonify({'error': 'CSV file is empty'}), 400

        with db_session() as db:
            count = ingest_dataframe(db, df, farm_code, data_type, file.filename)

        return success(data={'ingested_rows': count, 'farm_code': farm_code, 'data_type': data_type})
    except Exception as e:
        logger.exception("Manual ingest failed")
        return jsonify({'error': 'Ingest failed, check server logs'}), 500
