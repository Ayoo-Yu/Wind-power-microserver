from datetime import datetime
import json
import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import asc, desc

from db_session import db_session
from models import OperationAuditLog, User, UserProfileMeta


auth_extensions_bp = Blueprint('auth_extensions', __name__)


def _get_permissions(user):
    if not user or not user.role:
        return []
    permissions = user.role.permissions
    if isinstance(permissions, dict) and 'permissions' in permissions:
        permissions = permissions['permissions']
    return permissions if isinstance(permissions, list) else []


def _has_any_permission(user, permissions):
    current_permissions = _get_permissions(user)
    role_name = str(user.role.name if user and user.role else '').lower()
    if role_name in {'admin', 'administrator', '系统管理员'}:
        return True
    return any(permission in current_permissions for permission in permissions)


def _get_current_user(session):
    current_user_id = get_jwt_identity()
    if not current_user_id:
        return None
    return session.query(User).filter(User.id == current_user_id).first()


def _parse_stations(value):
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except Exception:
            pass
    return []


def _serialize_user_meta(meta):
    return {
        'user_id': meta.user_id,
        'username': meta.user.username if meta.user else None,
        'phone': meta.phone or '',
        'stations': _parse_stations(meta.stations),
        'updated_at': meta.updated_at.isoformat() if meta.updated_at else None
    }


def _serialize_audit_log(item):
    return {
        'id': item.id,
        'operationTime': item.operation_time.isoformat() if item.operation_time else None,
        'operator': item.operator,
        'ipAddress': item.ip_address or '-',
        'module': item.module,
        'operationType': item.operation_type,
        'details': item.details or '',
        'result': item.result,
        'source': 'backend'
    }


def _safe_parse_datetime(value):
    text = (value or '').strip()
    if not text:
        return None
    return datetime.fromisoformat(text)


@auth_extensions_bp.route('/users-meta', methods=['GET'])
@jwt_required()
def get_users_meta():
    try:
        with db_session() as session:
            current_user = _get_current_user(session)
            if not current_user:
                return jsonify({'message': '用户不存在'}), 404
            if not _has_any_permission(current_user, ['manage_users']):
                return jsonify({'message': '缺少管理用户权限'}), 403

            rows = session.query(UserProfileMeta).all()
            return jsonify([_serialize_user_meta(item) for item in rows])
    except Exception as e:
        logging.error(f"获取用户扩展元数据失败: {e}", exc_info=True)
        return jsonify({'message': '获取用户扩展元数据失败'}), 500


@auth_extensions_bp.route('/me/profile-meta', methods=['GET'])
@jwt_required()
def get_current_user_meta():
    try:
        with db_session() as session:
            current_user = _get_current_user(session)
            if not current_user:
                return jsonify({'message': '用户不存在'}), 404

            meta = session.query(UserProfileMeta).filter(UserProfileMeta.user_id == current_user.id).first()
            if not meta:
                return jsonify({
                    'user_id': current_user.id,
                    'username': current_user.username,
                    'phone': '',
                    'stations': ['__ALL__'],
                    'updated_at': None
                })
            return jsonify(_serialize_user_meta(meta))
    except Exception as e:
        logging.error(f"获取当前用户扩展元数据失败: {e}", exc_info=True)
        return jsonify({'message': '获取当前用户扩展元数据失败'}), 500


@auth_extensions_bp.route('/users/<int:user_id>/meta', methods=['PUT'])
@jwt_required()
def upsert_user_meta(user_id):
    try:
        data = request.get_json() or {}
        with db_session() as session:
            current_user = _get_current_user(session)
            if not current_user:
                return jsonify({'message': '用户不存在'}), 404
            if not _has_any_permission(current_user, ['manage_users']):
                return jsonify({'message': '缺少管理用户权限'}), 403

            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return jsonify({'message': '目标用户不存在'}), 404

            meta = session.query(UserProfileMeta).filter(UserProfileMeta.user_id == user_id).first()
            if not meta:
                meta = UserProfileMeta(user_id=user_id)
                session.add(meta)

            meta.phone = data.get('phone') or ''
            meta.stations = json.dumps(_parse_stations(data.get('stations', [])), ensure_ascii=False)
            session.commit()
            session.refresh(meta)
            return jsonify({
                'message': '用户扩展元数据保存成功',
                'meta': _serialize_user_meta(meta)
            })
    except Exception as e:
        logging.error(f"保存用户扩展元数据失败: {e}", exc_info=True)
        return jsonify({'message': '保存用户扩展元数据失败'}), 500


@auth_extensions_bp.route('/users/<int:user_id>/meta', methods=['DELETE'])
@jwt_required()
def delete_user_meta(user_id):
    try:
        with db_session() as session:
            current_user = _get_current_user(session)
            if not current_user:
                return jsonify({'message': '用户不存在'}), 404
            if not _has_any_permission(current_user, ['manage_users']):
                return jsonify({'message': '缺少管理用户权限'}), 403

            meta = session.query(UserProfileMeta).filter(UserProfileMeta.user_id == user_id).first()
            if meta:
                session.delete(meta)
                session.commit()
            return jsonify({'message': '用户扩展元数据删除成功'})
    except Exception as e:
        logging.error(f"删除用户扩展元数据失败: {e}", exc_info=True)
        return jsonify({'message': '删除用户扩展元数据失败'}), 500


@auth_extensions_bp.route('/audit-logs', methods=['GET'])
@jwt_required()
def list_operation_audit_logs():
    try:
        with db_session() as session:
            current_user = _get_current_user(session)
            if not current_user:
                return jsonify({'message': '用户不存在'}), 404
            if not _has_any_permission(current_user, ['manage_users', 'view_audit_logs']):
                return jsonify({'message': '缺少查看审计日志权限'}), 403

            page = request.args.get('page', 1, type=int) or 1
            per_page = request.args.get('per_page', 20, type=int) or 20
            per_page = max(1, min(per_page, 200))
            operator = (request.args.get('operator') or '').strip()
            module = (request.args.get('module') or '').strip()
            result = (request.args.get('result') or '').strip()
            start_time = (request.args.get('start_time') or '').strip()
            end_time = (request.args.get('end_time') or '').strip()
            sort_order = (request.args.get('sort_order') or 'desc').strip().lower()

            query = session.query(OperationAuditLog)

            if operator:
                query = query.filter(OperationAuditLog.operator.ilike(f'%{operator}%'))
            if module:
                query = query.filter(OperationAuditLog.module == module)
            if result:
                query = query.filter(OperationAuditLog.result == result)
            if start_time:
                try:
                    query = query.filter(OperationAuditLog.operation_time >= _safe_parse_datetime(start_time))
                except ValueError:
                    return jsonify({'message': 'start_time format invalid'}), 400
            if end_time:
                try:
                    query = query.filter(OperationAuditLog.operation_time <= _safe_parse_datetime(end_time))
                except ValueError:
                    return jsonify({'message': 'end_time format invalid'}), 400

            order_direction = asc if sort_order == 'asc' else desc
            query = query.order_by(order_direction(OperationAuditLog.operation_time), order_direction(OperationAuditLog.id))

            total = query.count()
            rows = query.offset((page - 1) * per_page).limit(per_page).all()
            return jsonify({
                'logs': [_serialize_audit_log(item) for item in rows],
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page if total else 0
            })
    except Exception as e:
        logging.error(f"获取操作审计日志失败: {e}", exc_info=True)
        return jsonify({'message': '获取操作审计日志失败'}), 500


@auth_extensions_bp.route('/audit-logs', methods=['POST'])
@jwt_required()
def create_operation_audit_log():
    try:
        data = request.get_json() or {}
        with db_session() as session:
            current_user = _get_current_user(session)
            if not current_user:
                return jsonify({'message': '用户不存在'}), 404

            row = OperationAuditLog(
                operation_time=datetime.utcnow(),
                operator=data.get('operator') or current_user.username,
                ip_address=data.get('ipAddress') or request.headers.get('X-Forwarded-For') or request.remote_addr or '-',
                module=data.get('module') or '系统',
                operation_type=data.get('operationType') or '操作',
                details=data.get('details') or '',
                result=data.get('result') or '成功'
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return jsonify({
                'message': '审计日志记录成功',
                'log': _serialize_audit_log(row)
            }), 201
    except Exception as e:
        logging.error(f"写入操作审计日志失败: {e}", exc_info=True)
        return jsonify({'message': '写入操作审计日志失败'}), 500
