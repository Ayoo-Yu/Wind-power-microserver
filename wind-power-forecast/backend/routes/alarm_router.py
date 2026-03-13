import json
import logging
import os
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from db_session import db_session
from models import AlarmNotificationPolicy, AlarmRecord, AlarmRule, User


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
        'raw_payload': item.raw_payload,
    }


def _serialize_alarm_rule(item):
    return {
        'id': item.id,
        'rule_name': item.rule_name,
        'module': item.module,
        'level': item.level,
        'keyword': item.keyword,
        'farm_code': item.farm_code,
        'is_enabled': bool(item.is_enabled),
        'notify_sound': bool(item.notify_sound),
        'notify_sms': bool(item.notify_sms),
        'updated_at': item.updated_at.isoformat() if item.updated_at else None,
    }


def _serialize_alarm_policy(item):
    return {
        'id': item.id,
        'policy_name': item.policy_name,
        'channel': item.channel,
        'target': item.target,
        'min_level': item.min_level,
        'is_enabled': bool(item.is_enabled),
        'cooldown_minutes': item.cooldown_minutes,
        'updated_at': item.updated_at.isoformat() if item.updated_at else None,
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
                    'message': ' - '.join(parts[2:]),
                })
        except Exception as error:
            logging.error(f'failed to read system log snapshot: {error}', exc_info=True)

    if not logs:
        now = datetime.utcnow()
        logs = [
            {
                'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
                'level': 'info',
                'message': 'system service heartbeat is normal',
            },
            {
                'timestamp': (now - timedelta(minutes=8)).strftime('%Y-%m-%d %H:%M:%S'),
                'level': 'warning',
                'message': 'scheduler latency is higher than expected',
            },
        ]
    return logs


def _seed_alarms_from_logs(session):
    if session.query(AlarmRecord).count() > 0:
        return

    for row in _read_system_log_snapshot():
        level = _normalize_level(row.get('level'))
        message = row.get('message') or ''
        session.add(AlarmRecord(
            source='system-log',
            farm_code=None,
            module='system-log',
            level=level,
            message=message,
            status='open',
            notify_sound=level == 'danger',
            notify_sms=level == 'danger',
            occurred_at=_parse_log_time(row.get('timestamp')),
            raw_payload=json.dumps(row, ensure_ascii=False),
        ))
    session.commit()


def _seed_default_configs(session):
    if session.query(AlarmRule).count() == 0:
        session.add(AlarmRule(
            rule_name='系统错误告警',
            module='system-log',
            level='danger',
            keyword='error',
            is_enabled=True,
            notify_sound=True,
            notify_sms=True,
        ))
        session.add(AlarmRule(
            rule_name='调度异常告警',
            module='scheduler',
            level='warning',
            keyword='scheduler',
            is_enabled=True,
            notify_sound=True,
            notify_sms=False,
        ))
    if session.query(AlarmNotificationPolicy).count() == 0:
        session.add(AlarmNotificationPolicy(
            policy_name='默认声音通知',
            channel='sound',
            target='browser-audio',
            min_level='warning',
            is_enabled=True,
            cooldown_minutes=1,
        ))
        session.add(AlarmNotificationPolicy(
            policy_name='默认短信通知',
            channel='sms',
            target='ops-oncall',
            min_level='danger',
            is_enabled=False,
            cooldown_minutes=10,
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
            _seed_default_configs(session)
            query = session.query(AlarmRecord)
            if status:
                query = query.filter(AlarmRecord.status == status)
            if level:
                query = query.filter(AlarmRecord.level == _normalize_level(level))
            rows = query.order_by(AlarmRecord.occurred_at.desc(), AlarmRecord.id.desc()).limit(200).all()
            return jsonify([_serialize_alarm(item) for item in rows])
    except Exception as error:
        logging.error(f'failed to list alarms: {error}', exc_info=True)
        return jsonify({'error': 'failed to list alarms'}), 500


@alarm_bp.route('/alarms/notifications', methods=['GET'])
@jwt_required()
def list_alarm_notifications():
    try:
        with db_session() as session:
            _seed_alarms_from_logs(session)
            _seed_default_configs(session)
            rows = session.query(AlarmRecord).order_by(AlarmRecord.occurred_at.desc(), AlarmRecord.id.desc()).limit(50).all()
            notifications = []
            for item in rows:
                if item.notify_sound:
                    notifications.append({
                        'alarm_id': item.id,
                        'channel': 'sound',
                        'status': 'sent' if item.status != 'closed' else 'stopped',
                        'message': item.message,
                        'occurred_at': item.occurred_at.isoformat() if item.occurred_at else None,
                    })
                if item.notify_sms:
                    notifications.append({
                        'alarm_id': item.id,
                        'channel': 'sms',
                        'status': 'queued' if item.status == 'open' else 'cancelled',
                        'message': item.message,
                        'occurred_at': item.occurred_at.isoformat() if item.occurred_at else None,
                    })
            return jsonify(notifications[:100])
    except Exception as error:
        logging.error(f'failed to list alarm notifications: {error}', exc_info=True)
        return jsonify({'error': 'failed to list alarm notifications'}), 500


@alarm_bp.route('/alarm-rules', methods=['GET'])
@jwt_required()
def list_alarm_rules():
    try:
        with db_session() as session:
            _seed_default_configs(session)
            rows = session.query(AlarmRule).order_by(AlarmRule.updated_at.desc(), AlarmRule.id.desc()).all()
            return jsonify([_serialize_alarm_rule(item) for item in rows])
    except Exception as error:
        logging.error(f'failed to list alarm rules: {error}', exc_info=True)
        return jsonify({'error': 'failed to list alarm rules'}), 500


@alarm_bp.route('/alarm-rules', methods=['POST'])
@jwt_required()
def create_alarm_rule():
    try:
        data = request.get_json() or {}
        with db_session() as session:
            row = AlarmRule(
                rule_name=data.get('rule_name') or f'规则-{int(datetime.utcnow().timestamp())}',
                module=data.get('module') or 'system',
                level=_normalize_level(data.get('level')),
                keyword=data.get('keyword') or '',
                farm_code=data.get('farm_code') or None,
                is_enabled=bool(data.get('is_enabled', True)),
                notify_sound=bool(data.get('notify_sound', False)),
                notify_sms=bool(data.get('notify_sms', False)),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return jsonify({'message': 'alarm rule created', 'rule': _serialize_alarm_rule(row)}), 201
    except Exception as error:
        logging.error(f'failed to create alarm rule: {error}', exc_info=True)
        return jsonify({'error': 'failed to create alarm rule'}), 500


@alarm_bp.route('/alarm-rules/<int:rule_id>', methods=['PUT'])
@jwt_required()
def update_alarm_rule(rule_id):
    try:
        data = request.get_json() or {}
        with db_session() as session:
            row = session.query(AlarmRule).filter(AlarmRule.id == rule_id).first()
            if not row:
                return jsonify({'error': 'alarm rule not found'}), 404
            for field in ('rule_name', 'module', 'keyword'):
                if field in data:
                    setattr(row, field, data.get(field) or '')
            if 'farm_code' in data:
                row.farm_code = data.get('farm_code') or None
            if 'level' in data:
                row.level = _normalize_level(data.get('level'))
            if 'is_enabled' in data:
                row.is_enabled = bool(data.get('is_enabled'))
            if 'notify_sound' in data:
                row.notify_sound = bool(data.get('notify_sound'))
            if 'notify_sms' in data:
                row.notify_sms = bool(data.get('notify_sms'))
            session.commit()
            session.refresh(row)
            return jsonify({'message': 'alarm rule updated', 'rule': _serialize_alarm_rule(row)})
    except Exception as error:
        logging.error(f'failed to update alarm rule: {error}', exc_info=True)
        return jsonify({'error': 'failed to update alarm rule'}), 500


@alarm_bp.route('/alarm-rules/<int:rule_id>', methods=['DELETE'])
@jwt_required()
def delete_alarm_rule(rule_id):
    try:
        with db_session() as session:
            row = session.query(AlarmRule).filter(AlarmRule.id == rule_id).first()
            if not row:
                return jsonify({'error': 'alarm rule not found'}), 404
            session.delete(row)
            session.commit()
            return jsonify({'message': 'alarm rule deleted'})
    except Exception as error:
        logging.error(f'failed to delete alarm rule: {error}', exc_info=True)
        return jsonify({'error': 'failed to delete alarm rule'}), 500


@alarm_bp.route('/alarm-policies', methods=['GET'])
@jwt_required()
def list_alarm_policies():
    try:
        with db_session() as session:
            _seed_default_configs(session)
            rows = session.query(AlarmNotificationPolicy).order_by(AlarmNotificationPolicy.updated_at.desc(), AlarmNotificationPolicy.id.desc()).all()
            return jsonify([_serialize_alarm_policy(item) for item in rows])
    except Exception as error:
        logging.error(f'failed to list alarm policies: {error}', exc_info=True)
        return jsonify({'error': 'failed to list alarm policies'}), 500


@alarm_bp.route('/alarm-policies', methods=['POST'])
@jwt_required()
def create_alarm_policy():
    try:
        data = request.get_json() or {}
        with db_session() as session:
            row = AlarmNotificationPolicy(
                policy_name=data.get('policy_name') or f'策略-{int(datetime.utcnow().timestamp())}',
                channel=data.get('channel') or 'sound',
                target=data.get('target') or '',
                min_level=_normalize_level(data.get('min_level')),
                is_enabled=bool(data.get('is_enabled', True)),
                cooldown_minutes=max(0, int(data.get('cooldown_minutes') or 0)),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return jsonify({'message': 'alarm policy created', 'policy': _serialize_alarm_policy(row)}), 201
    except Exception as error:
        logging.error(f'failed to create alarm policy: {error}', exc_info=True)
        return jsonify({'error': 'failed to create alarm policy'}), 500


@alarm_bp.route('/alarm-policies/<int:policy_id>', methods=['PUT'])
@jwt_required()
def update_alarm_policy(policy_id):
    try:
        data = request.get_json() or {}
        with db_session() as session:
            row = session.query(AlarmNotificationPolicy).filter(AlarmNotificationPolicy.id == policy_id).first()
            if not row:
                return jsonify({'error': 'alarm policy not found'}), 404
            for field in ('policy_name', 'channel', 'target'):
                if field in data:
                    setattr(row, field, data.get(field) or '')
            if 'min_level' in data:
                row.min_level = _normalize_level(data.get('min_level'))
            if 'is_enabled' in data:
                row.is_enabled = bool(data.get('is_enabled'))
            if 'cooldown_minutes' in data:
                row.cooldown_minutes = max(0, int(data.get('cooldown_minutes') or 0))
            session.commit()
            session.refresh(row)
            return jsonify({'message': 'alarm policy updated', 'policy': _serialize_alarm_policy(row)})
    except Exception as error:
        logging.error(f'failed to update alarm policy: {error}', exc_info=True)
        return jsonify({'error': 'failed to update alarm policy'}), 500


@alarm_bp.route('/alarm-policies/<int:policy_id>', methods=['DELETE'])
@jwt_required()
def delete_alarm_policy(policy_id):
    try:
        with db_session() as session:
            row = session.query(AlarmNotificationPolicy).filter(AlarmNotificationPolicy.id == policy_id).first()
            if not row:
                return jsonify({'error': 'alarm policy not found'}), 404
            session.delete(row)
            session.commit()
            return jsonify({'message': 'alarm policy deleted'})
    except Exception as error:
        logging.error(f'failed to delete alarm policy: {error}', exc_info=True)
        return jsonify({'error': 'failed to delete alarm policy'}), 500


@alarm_bp.route('/alarms/<int:alarm_id>/ack', methods=['POST'])
@jwt_required()
def ack_alarm(alarm_id):
    try:
        with db_session() as session:
            current_user = _get_current_user(session)
            row = session.query(AlarmRecord).filter(AlarmRecord.id == alarm_id).first()
            if not row:
                return jsonify({'error': 'alarm not found'}), 404
            row.status = 'acked'
            row.acknowledged_at = datetime.utcnow()
            row.acknowledged_by = current_user.username if current_user else 'unknown'
            session.commit()
            session.refresh(row)
            return jsonify({'message': 'alarm acknowledged', 'alarm': _serialize_alarm(row)})
    except Exception as error:
        logging.error(f'failed to acknowledge alarm: {error}', exc_info=True)
        return jsonify({'error': 'failed to acknowledge alarm'}), 500


@alarm_bp.route('/alarms/<int:alarm_id>/close', methods=['POST'])
@jwt_required()
def close_alarm(alarm_id):
    try:
        with db_session() as session:
            current_user = _get_current_user(session)
            row = session.query(AlarmRecord).filter(AlarmRecord.id == alarm_id).first()
            if not row:
                return jsonify({'error': 'alarm not found'}), 404
            row.status = 'closed'
            row.closed_at = datetime.utcnow()
            row.closed_by = current_user.username if current_user else 'unknown'
            if not row.acknowledged_at:
                row.acknowledged_at = row.closed_at
                row.acknowledged_by = row.closed_by
            session.commit()
            session.refresh(row)
            return jsonify({'message': 'alarm closed', 'alarm': _serialize_alarm(row)})
    except Exception as error:
        logging.error(f'failed to close alarm: {error}', exc_info=True)
        return jsonify({'error': 'failed to close alarm'}), 500
