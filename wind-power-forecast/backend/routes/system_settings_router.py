from datetime import datetime
import json
import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from db_session import db_session
from models import SystemSetting
from utils.database_schema import require_model_tables


system_settings_bp = Blueprint('system_settings', __name__)


def _ensure_system_settings_table(session):
    require_model_tables(session, SystemSetting.__table__)


DEFAULT_SYSTEM_SETTINGS = {
    'holidays': [
        {'date': '2026-10-01', 'note': '国庆节'}
    ],
    'dict': {
        'turbineModels': 'GW121, GW155, EN171',
        'vendors': '金风, 远景, 明阳'
    },
    'params': {
        'retentionMonths': 12,
        'logRetentionDays': 180,
        'diskAlertPercent': 85
    }
}


def _build_default_system_settings():
    return json.loads(json.dumps(DEFAULT_SYSTEM_SETTINGS))


def _serialize_system_settings(setting):
    payload = _build_default_system_settings()
    if setting and setting.payload:
        try:
            parsed = json.loads(setting.payload)
            if isinstance(parsed, dict):
                payload['holidays'] = parsed.get('holidays', payload['holidays'])
                payload['dict'] = {**payload['dict'], **(parsed.get('dict') or {})}
                payload['params'] = {**payload['params'], **(parsed.get('params') or {})}
        except Exception:
            pass

    return {
        'settings_key': 'default',
        'data': payload,
        'updated_by': setting.updated_by if setting else None,
        'updated_at': setting.updated_at.isoformat() if setting and setting.updated_at else None
    }


@system_settings_bp.route('/settings', methods=['GET'])
@jwt_required()
def get_system_settings():
    try:
        with db_session() as session:
            _ensure_system_settings_table(session)
            setting = session.query(SystemSetting).filter(SystemSetting.settings_key == 'default').first()
            return jsonify(_serialize_system_settings(setting))
    except Exception as e:
        logging.error(f"获取系统基础配置失败: {str(e)}")
        return jsonify({'error': '获取系统基础配置失败'}), 500


@system_settings_bp.route('/settings', methods=['PUT'])
@jwt_required()
def save_system_settings():
    try:
        data = request.get_json() or {}
        payload = data.get('data')
        updated_by = data.get('updated_by')
        if not isinstance(payload, dict):
            return jsonify({'error': '配置数据格式不正确'}), 400

        merged = _build_default_system_settings()
        merged['holidays'] = payload.get('holidays', merged['holidays'])
        merged['dict'] = {**merged['dict'], **(payload.get('dict') or {})}
        merged['params'] = {**merged['params'], **(payload.get('params') or {})}

        with db_session() as session:
            _ensure_system_settings_table(session)
            setting = session.query(SystemSetting).filter(SystemSetting.settings_key == 'default').first()
            if not setting:
                setting = SystemSetting(settings_key='default', payload=json.dumps(merged, ensure_ascii=False))
                session.add(setting)
            else:
                setting.payload = json.dumps(merged, ensure_ascii=False)

            setting.updated_by = updated_by
            session.commit()
            session.refresh(setting)
            return jsonify({
                'message': '系统基础配置保存成功',
                **_serialize_system_settings(setting)
            })
    except Exception as e:
        logging.error(f"保存系统基础配置失败: {str(e)}")
        return jsonify({'error': '保存系统基础配置失败'}), 500


@system_settings_bp.route('/settings/reset', methods=['POST'])
@jwt_required()
def reset_system_settings():
    try:
        data = request.get_json() or {}
        updated_by = data.get('updated_by')

        with db_session() as session:
            _ensure_system_settings_table(session)
            setting = session.query(SystemSetting).filter(SystemSetting.settings_key == 'default').first()
            default_payload = json.dumps(_build_default_system_settings(), ensure_ascii=False)
            if not setting:
                setting = SystemSetting(settings_key='default', payload=default_payload)
                session.add(setting)
            else:
                setting.payload = default_payload
            setting.updated_by = updated_by
            session.commit()
            session.refresh(setting)
            return jsonify({
                'message': '系统基础配置已恢复默认',
                **_serialize_system_settings(setting)
            })
    except Exception as e:
        logging.error(f"恢复系统基础配置失败: {str(e)}")
        return jsonify({'error': '恢复系统基础配置失败'}), 500
