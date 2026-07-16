"""统一的 JWT 身份认证与角色权限校验。"""

from functools import wraps

from flask import g, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from db_models import User
from db_session import db_session


_ADMIN_ROLE_NAMES = {"admin", "administrator", "管理员", "系统管理员"}


def is_admin_role(role) -> bool:
    """判断角色是否具备管理员语义。"""

    role_name = str(getattr(role, "name", "") or "").strip().lower()
    return role_name in _ADMIN_ROLE_NAMES


def normalise_permissions(role) -> set[str]:
    """把历史字典和列表格式统一为权限集合。"""

    permissions = getattr(role, "permissions", None) if role else None
    if isinstance(permissions, dict):
        if permissions.get("admin") is True:
            return {"admin"}
        permissions = permissions.get("permissions", [])
    if not isinstance(permissions, list):
        return set()
    return {str(item).strip() for item in permissions if str(item).strip()}


def enforce_permission(required_permission: str):
    """验证请求令牌和数据库中的当前用户，失败时返回 Flask 响应。"""

    verify_jwt_in_request()
    current_user_id = get_jwt_identity()
    if current_user_id is None:
        return jsonify({"message": "认证令牌缺少用户身份"}), 401

    with db_session() as session:
        user = session.query(User).filter(User.id == current_user_id).first()
        if not user:
            return jsonify({"message": "认证用户不存在"}), 401
        if not user.is_active:
            return jsonify({"message": "操作用户账户已被禁用"}), 403

        permissions = normalise_permissions(user.role)
        if not is_admin_role(user.role) and "admin" not in permissions:
            if required_permission not in permissions:
                return jsonify({
                    "message": f"权限不足，需要 {required_permission} 权限"
                }), 403

        g.acting_user = user
        g.acting_user_id = user.id
        g.acting_username = user.username
    return None


def permission_required(required_permission: str):
    """为路由绑定统一的 JWT 和权限校验。"""

    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            denied = enforce_permission(required_permission)
            if denied is not None:
                return denied
            return func(*args, **kwargs)

        return decorated_function

    return decorator
