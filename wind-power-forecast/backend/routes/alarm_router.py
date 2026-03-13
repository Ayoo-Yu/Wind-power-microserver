import json
import logging
import os
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from db_session import db_session
from models import AlarmRecord, User


alarm_bp = Blueprint('alarm', __name__)


def _normalize_level(value):
    text = str(value or '').lower()
    if text in ('danger', 'critical', 'error'):
        return 'danger'
    if text in ('warning', 'warn'):
        return 'warning'
    return 'info'


def _parse_log_time(value):
    if not value:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return datetime.utcnow()


def _get_current_user(session):
    current_user_id = get_jwt_identity()
    if not current_user_id:
        return None
    return session.query(User).filter(User.id == current_user_id).first()


def _serialize_alarm(item):
    return {
        'id': item.id,
        'source': item.source,
        'farm_code': item.farm_code,
        'module': item.module,
        'level': item.level,
        'message': item.message,
        'status': item.status,
        'notify_sound': bool(item.notify_sound),
        'notify_sms': bool(item.notify_sms),
        'occurred_at': item.occurred_at.isoformat() if item.occurred_at else None,
        'acknowledged_at': item.acknowledged_at.isoformat() if item.acknowledged_at else None,
        'acknowledged_by': item.acknowledged_by,
        'closed_at': item.closed_at.isoformat() if item.closed_at else None,
        'closed_by': item.closed_by,
        'raw_payload': item.raw_payload
    }


def _read_system_log_snapshot():
    logs = []
    log_file_path = os.path.join(os.path.dirname(__file__), '..', 'logs', 'app.log')
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r', encoding='utf-8') as file_handle:
                lines = file_handle.readlines()
            recent_lines = lines[-30:] if len(lines) > 30 else lines
            for line in recent_lines:
                parts = line.strip().split(' - ')
                if len(parts) < 3:
                    continue
                logs.append({
                    'timestamp': parts[0],
                    'level': parts[1].lower(),
                    'message': ' - '.join(parts[2:])
                })
        except Exception as error:
            logging.error(f'读取系统日志快照失败: {error}', exc_info=True)

    if not logs:
        now = datetime.utcnow()
        logs = [
            {
                'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
                'level': 'info',
                'message': '系统运行正常，当前未发现新增高优先级告警'
            },
            {
                'timestamp': (now - timedelta(minutes=8)).strftime('%Y-%m-%d %H:%M:%S'),
                'level': 'warning',
                'message': '调度器最近一次重连成功，请关注链路稳定性'
            }
        ]
    return logs


def _seed_alarms_from_logs(session):
    if session.query(AlarmRecord).count() > 0:
        return

    for row in _read_system_log_snapshot():
        level = _normalize_level(row.get('level'))
        message = row.get('message') or ''
        notify_sound = level == 'danger'
        notify_sms = level == 'danger'
        module = 'system-log'
        farm_code = None

        session.add(AlarmRecord(
            source='system-log',
            farm_code=farm_code,
            module=module,
            level=level,
            message=message,
            status='open',
            notify_sound=notify_sound,
            notify_sms=notify_sms,
            occurred_at=_parse_log_time(row.get('timestamp')),
            raw_payload=json.dumps(row, ensure_ascii=False)
        ))
    session.commit()


@alarm_bp.route('/alarms', methods=['GET'])
@jwt_required()
def list_alarms():
    try:
        status = request.args.get('status')
        level = request.args.get('level')
        with db_session() as session:
            _seed_alarms_from_logs(session)
            query = session.query(AlarmRecord)
            if status:
                query = query.filter(AlarmRecord.status == status)
            if level:
                query = query.filter(AlarmRecord.level == _normalize_level(level))
            rows = query.order_by(AlarmRecord.occurred_at.desc(), AlarmRecord.id.desc()).limit(200).all()
            return jsonify([_serialize_alarm(item) for item in rows])
    except Exception as error:
        logging.error(f'获取告警列表失败: {error}', exc_info=True)
        return jsonify({'error': '获取告警列表失败'}), 500


@alarm_bp.route('/alarms/notifications', methods=['GET'])
@jwt_required()
def list_alarm_notifications():
    try:
        with db_session() as session:
            _seed_alarms_from_logs(session)
            rows = session.query(AlarmRecord).order_by(AlarmRecord.occurred_at.desc(), AlarmRecord.id.desc()).limit(50).all()
            notifications = []
            for item in rows:
                if item.notify_sound:
                    notifications.append({
                        'alarm_id': item.id,
                        'channel': 'sound',
                        'status': 'sent' if item.status != 'closed' else 'stopped',
                        'message': item.message,
                        'occurred_at': item.occurred_at.isoformat() if item.occurred_at else None
                    })
                if item.notify_sms:
                    notifications.append({
                        'alarm_id': item.id,
                        'channel': 'sms',
                        'status': 'queued' if item.status == 'open' else 'cancelled',
                        'message': item.message,
                        'occurred_at': item.occurred_at.isoformat() if item.occurred_at else None
                    })
            return jsonify(notifications[:100])
    except Exception as error:
        logging.error(f'获取告警通知记录失败: {error}', exc_info=True)
        return jsonify({'error': '获取告警通知记录失败'}), 500


@alarm_bp.route('/alarms/<int:alarm_id>/ack', methods=['POST'])
@jwt_required()
def ack_alarm(alarm_id):
    try:
        with db_session() as session:
            current_user = _get_current_user(session)
            row = session.query(AlarmRecord).filter(AlarmRecord.id == alarm_id).first()
            if not row:
                return jsonify({'error': '告警不存在'}), 404
            row.status = 'acked'
            row.acknowledged_at = datetime.utcnow()
            row.acknowledged_by = current_user.username if current_user else 'unknown'
            session.commit()
            session.refresh(row)
            return jsonify({'message': '告警已确认', 'alarm': _serialize_alarm(row)})
    except Exception as error:
        logging.error(f'确认告警失败: {error}', exc_info=True)
        return jsonify({'error': '确认告警失败'}), 500


@alarm_bp.route('/alarms/<int:alarm_id>/close', methods=['POST'])
@jwt_required()
def close_alarm(alarm_id):
    try:
        with db_session() as session:
            current_user = _get_current_user(session)
            row = session.query(AlarmRecord).filter(AlarmRecord.id == alarm_id).first()
            if not row:
                return jsonify({'error': '告警不存在'}), 404
            row.status = 'closed'
            row.closed_at = datetime.utcnow()
            row.closed_by = current_user.username if current_user else 'unknown'
            if not row.acknowledged_at:
                row.acknowledged_at = row.closed_at
                row.acknowledged_by = row.closed_by
            session.commit()
            session.refresh(row)
            return jsonify({'message': '告警已关闭', 'alarm': _serialize_alarm(row)})
    except Exception as error:
        logging.error(f'关闭告警失败: {error}', exc_info=True)
        return jsonify({'error': '关闭告警失败'}), 500
