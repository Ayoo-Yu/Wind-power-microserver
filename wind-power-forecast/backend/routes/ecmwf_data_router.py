"""
ECMWF 气象数据 API 路由

提供气象预报数据的查询和可用性检查接口。
数据存储在每场独立的 ecmwf_grid_{farm_code} 表中。
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime
from db_session import db_session
from common.api_response import success
import logging

from services.grid_to_farm_service import (
    query_grid_data_as_wide,
    get_grid_latest_timestamp,
    get_grid_availability,
)

logger = logging.getLogger(__name__)

ecmwf_data_bp = Blueprint('ecmwf_data', __name__)


@ecmwf_data_bp.route('/api/ecmwf/latest', methods=['GET'])
@jwt_required()
def get_latest():
    """获取最新可用预报数据时间戳

    Query params:
        farm_code: 风场编码
        data_type: 数据类型 DQ/CDQ/QXYC (默认 DQ)
    """
    farm_code = request.args.get('farm_code', '')
    data_type = request.args.get('data_type', 'DQ')

    with db_session() as db:
        ts = get_grid_latest_timestamp(db, farm_code)

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
    """查询时间范围内的预报数据

    Query params:
        farm_code: 风场编码
        start: ISO格式起始时间 (如 2026-04-17T00:00:00)
        end: ISO格式结束时间
        data_type: DQ/CDQ/QXYC (默认 DQ)
        limit: 最大返回行数 (默认 1000，上限 50000)
    """
    farm_code = request.args.get('farm_code', '')
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

    # 限制查询范围不超过 31 天
    if (end_time - start_time).days > 31:
        return jsonify({'error': 'Time range too wide, max 31 days'}), 400

    limit = min(max(1, limit), 50000)

    with db_session() as db:
        df = query_grid_data_as_wide(db, farm_code, start_time, end_time, data_type, limit)

    if df.empty:
        return success(data={'rows': 0, 'data': []})

    return success(data={
        'rows': len(df),
        'columns': list(df.columns),
        'data': df.to_dict(orient='records'),
    })


@ecmwf_data_bp.route('/api/ecmwf/availability', methods=['GET'])
@jwt_required()
def check_availability():
    """检查指定日期的数据可用性

    Query params:
        farm_code: 风场编码
        date: 日期 (YYYY-MM-DD 格式)
    """
    farm_code = request.args.get('farm_code', '')
    date_str = request.args.get('date')

    if not date_str:
        return jsonify({'error': 'date parameter required (YYYY-MM-DD)'}), 400

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    with db_session() as db:
        availability = get_grid_availability(db, farm_code, date)

    result = {}
    for dtype, info in availability.items():
        result[dtype] = {
            'count': info['count'],
            'min_timestamp': info['min_timestamp'].isoformat() if info['min_timestamp'] else None,
            'max_timestamp': info['max_timestamp'].isoformat() if info['max_timestamp'] else None,
        }

    return success(data={'farm_code': farm_code, 'date': date_str, 'availability': result})
