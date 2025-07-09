from flask import Blueprint, request, jsonify, current_app, g
from sqlalchemy.exc import IntegrityError
from database_config import get_db
from services.auth_service import (
    authenticate_user, create_user, update_user, get_user_by_id, get_all_users,
    create_role, get_role_by_id, get_all_roles, create_access_token,
    log_login_attempt, update_last_login, decode_token, check_permission, get_user_by_username,
    verify_password as verify_password_bcrypt
)
from utils.password_utils import verify_password
from models import User, Role
from functools import wraps
from datetime import timedelta
from db_session import db_session  # 导入上下文管理器
from flask_jwt_extended import jwt_required

auth_bp = Blueprint('auth', __name__)

# 中间件：验证JWT令牌
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # 从请求头中获取令牌
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
        
        if not token:
            return jsonify({"message": "缺少认证令牌"}), 401
        
        # 解码令牌
        try:
            payload = decode_token(token)
            with db_session() as db:
                current_user = get_user_by_id(db, payload['sub'])
        except Exception as e:
            return jsonify({"message": "无效或过期的令牌"}), 401
        
        # 将用户信息存储在g对象中，以便在路由处理函数中使用
        g.user = current_user
        return f(*args, **kwargs)
    
    return decorated

# 中间件：检查权限
def permission_required(required_permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 检查请求参数中是否有username
            username = request.args.get('username')
            if not username:
                # 只有非GET请求才尝试从请求体中获取JSON数据
                if request.method != 'GET':
                    # 检查JSON数据中是否有username
                    json_data = request.get_json(silent=True)
                    if json_data and 'username' in json_data:
                        username = json_data.get('username')
                if not username:
                    print(f"权限检查失败：缺少用户名参数，要求权限: {required_permission}")
                    return jsonify({"message": "未提供用户名，无法验证权限"}), 403
            
            # 从数据库获取用户信息
            try:
                with db_session() as db:
                    user = db.query(User).filter(User.username == username).first()
                    
                    if not user:
                        print(f"权限检查失败：用户 {username} 不存在，要求权限: {required_permission}")
                        return jsonify({"message": "用户不存在"}), 404
                    
                    # 检查用户角色权限
                    if not user.role or not user.role.permissions:
                        print(f"权限检查失败：用户 {username} 没有角色或权限为空，要求权限: {required_permission}")
                        return jsonify({"message": "用户没有任何权限"}), 403
                    
                    # 检查权限格式并处理
                    permissions = user.role.permissions
                    print(f"用户 {username} 的权限: {permissions}, 类型: {type(permissions)}")
                    
                    # 处理权限可能是字典的情况
                    if isinstance(permissions, dict) and 'permissions' in permissions:
                        permissions = permissions['permissions']
                    
                    if required_permission not in permissions:
                        print(f"权限检查失败：用户 {username} 没有权限 {required_permission}，拥有权限: {permissions}")
                        return jsonify({"message": f"权限不足，需要 {required_permission} 权限"}), 403
                    
                    print(f"权限检查成功：用户 {username} 具有所需的 {required_permission} 权限")
                    return f(*args, **kwargs)
            except Exception as e:
                print(f"权限检查过程中发生异常: {e}")
                return jsonify({"message": "验证权限时出错"}), 500
                
        return decorated_function
    return decorator

# 登录路由
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"message": "缺少用户名或密码"}), 400
    
    try:
        # 使用上下文管理器
        with db_session() as db:
            # 从数据库中查询用户
            user = db.query(User).filter(User.username == data['username']).first()
            
            # 如果用户不存在，返回错误
            if not user:
                return jsonify({"message": "用户名或密码错误"}), 401
            
            # 检查用户是否已被禁用
            if not user.is_active:
                return jsonify({"message": "账户已被禁用，请联系管理员"}), 403
            
            # 先尝试使用新的统一密码验证方法
            password_valid = verify_password(data['password'], user.password_hash)
            
            # 如果新的验证方法失败，尝试使用旧的bcrypt方法
            if not password_valid:
                print(f"统一密码验证失败，尝试使用bcrypt方法 - 用户: {user.username}")
                password_valid = verify_password_bcrypt(data['password'], user.password_hash)
            
            if not password_valid:
                # 记录更详细的日志，帮助调试
                print(f"两种密码验证方法均失败 - 用户: {user.username}, 哈希值: {user.password_hash[:20]}...")
                return jsonify({"message": "用户名或密码错误"}), 401
            
            # 更新最后登录时间
            update_last_login(db, user.id)
            
            # 获取权限数据
            permissions = user.role.permissions
            if isinstance(permissions, dict) and 'permissions' in permissions:
                permissions = permissions['permissions']
            
            # 返回登录成功响应
            return jsonify({
                "message": "登录成功",
                "user": {
                    "username": user.username,
                    "full_name": user.full_name,
                    "role": user.role.name if user.role else "未知角色",
                    "permissions": permissions
                }
            })
    except Exception as e:
        print(f"登录异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 获取当前用户信息
@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    # 从查询参数获取用户名
    username = request.args.get('username')
    if not username:
        return jsonify({"message": "缺少用户名参数"}), 400
    
    try:
        # 从数据库获取用户信息
        with db_session() as db:
            user = db.query(User).filter(User.username == username).first()
            
            if not user:
                return jsonify({"message": "用户不存在"}), 404
            
            return jsonify({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": {
                    "id": user.role.id,
                    "name": user.role.name,
                    "permissions": user.role.permissions
                },
                "last_login": user.last_login,
                "is_active": user.is_active,
                "first_login": user.first_login
            })
    except Exception as e:
        print(f"获取用户信息异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 修改密码
@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    data = request.json
    if not data or not data.get('username') or not data.get('current_password') or not data.get('new_password'):
        return jsonify({"message": "缺少必要参数"}), 400
    
    try:
        with db_session() as db:
            user = authenticate_user(db, data['username'], data['current_password'])
            
            if not user:
                return jsonify({"message": "当前密码错误"}), 401
            
            # 密码策略验证
            if len(data['new_password']) < 8:
                return jsonify({"message": "新密码长度不能少于8位"}), 400
                
            # 更新密码
            user.password_hash = verify_password(data['new_password'])
            db.commit()
            
            return jsonify({"message": "密码修改成功"})
    except Exception as e:
        print(f"修改密码异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 获取所有用户
@auth_bp.route('/users', methods=['GET'])
@permission_required("manage_users")
def get_users():
    try:
        with db_session() as db:
            users = db.query(User).all()
            
            result = []
            for user in users:
                result.append({
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": {
                        "id": user.role.id if user.role else None,
                        "name": user.role.name if user.role else None
                    },
                    "is_active": user.is_active,
                    "last_login": user.last_login
                })
            
            return jsonify(result)
    except Exception as e:
        print(f"获取用户列表异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 获取单个用户
@auth_bp.route('/users/<int:user_id>', methods=['GET'])
@permission_required("manage_users")
def get_user(user_id):
    try:
        with db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return jsonify({"message": "用户不存在"}), 404
            
            return jsonify({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": {
                    "id": user.role.id if user.role else None,
                    "name": user.role.name if user.role else None
                },
                "is_active": user.is_active,
                "last_login": user.last_login
            })
    except Exception as e:
        print(f"获取用户详情异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

def is_super_admin(username):
    # 通过用户名判断是否是超级管理员
    return username.lower() == "admin"

def is_admin_role(role):
    return role and role.name.lower() in ["admin", "管理员", "系统管理员"]

# 更新用户信息
@auth_bp.route('/users/<int:user_id>', methods=['PUT'])
@permission_required("manage_users")
def update_user_info(user_id):
    data = request.json
    if not data:
        return jsonify({"message": "缺少更新数据"}), 400
    
    try:
        # 获取当前操作用户
        current_username = request.args.get('username') or request.json.get('username')
        
        with db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return jsonify({"message": "用户不存在"}), 404
            
            # 安全检查：不允许非管理员修改管理员信息
            current_user = db.query(User).filter(User.username == current_username).first()
            if is_admin_role(user.role) and not is_super_admin(current_username) and not is_admin_role(current_user.role):
                return jsonify({"message": "无权修改管理员信息"}), 403
            
            # 更新字段
            if 'username' in data and data['username'] != user.username:
                # 检查用户名是否已存在
                existing_user = db.query(User).filter(User.username == data['username']).first()
                if existing_user:
                    return jsonify({"message": "用户名已存在"}), 400
                user.username = data['username']
            
            if 'email' in data:
                user.email = data['email']
            
            if 'full_name' in data:
                user.full_name = data['full_name']
            
            if 'is_active' in data:
                # 只有超级管理员可以停用管理员账户
                if is_admin_role(user.role) and not is_super_admin(current_username) and not data['is_active']:
                    return jsonify({"message": "无权停用管理员账户"}), 403
                user.is_active = data['is_active']
            
            if 'role_id' in data and data['role_id'] != user.role_id:
                # 检查角色是否存在
                role = db.query(Role).filter(Role.id == data['role_id']).first()
                if not role:
                    return jsonify({"message": "指定的角色不存在"}), 400
                # 只有超级管理员可以修改用户的角色为管理员
                if is_admin_role(role) and not is_super_admin(current_username):
                    return jsonify({"message": "只有超级管理员可以分配管理员角色"}), 403
                user.role_id = data['role_id']
            
            db.commit()
            return jsonify({"message": "用户信息更新成功"})
    except Exception as e:
        print(f"更新用户信息异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 删除用户
@auth_bp.route('/users/<int:user_id>', methods=['DELETE'])
@permission_required("manage_users")
def delete_user(user_id):
    try:
        # 获取当前操作用户
        current_username = request.args.get('username')
        
        with db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return jsonify({"message": "用户不存在"}), 404
            
            # 安全检查：不允许删除管理员账户
            if is_admin_role(user.role) and not is_super_admin(current_username):
                return jsonify({"message": "无权删除管理员账户"}), 403
            
            # 不允许删除唯一的管理员账户
            if is_admin_role(user.role):
                admin_count = db.query(User).join(Role).filter(Role.name.in_(["admin", "管理员", "系统管理员"])).count()
                if admin_count <= 1:
                    return jsonify({"message": "系统至少需要一个管理员账户，无法删除"}), 400
            
            db.delete(user)
            db.commit()
            return jsonify({"message": "用户删除成功"})
    except Exception as e:
        print(f"删除用户异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 重置用户密码
@auth_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@permission_required("manage_users")
def reset_user_password(user_id):
    data = request.json
    if not data or not data.get('new_password'):
        return jsonify({"message": "缺少新密码参数"}), 400
    
    try:
        # 获取当前操作用户
        current_username = request.args.get('username') or request.json.get('username')
        
        with db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return jsonify({"message": "用户不存在"}), 404
            
            # 安全检查：不允许非管理员重置管理员密码
            current_user = db.query(User).filter(User.username == current_username).first()
            if is_admin_role(user.role) and not is_super_admin(current_username) and not is_admin_role(current_user.role):
                return jsonify({"message": "无权重置管理员密码"}), 403
            
            # 密码策略验证
            if len(data['new_password']) < 8:
                return jsonify({"message": "新密码长度不能少于8位"}), 400
            
            # 更新密码
            user.password_hash = verify_password(data['new_password'])
            
            # 设置需要首次登录修改密码
            user.first_login = True
            
            db.commit()
            return jsonify({"message": "密码重置成功"})
    except Exception as e:
        print(f"重置密码异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 创建新用户
@auth_bp.route('/users', methods=['POST'])
@permission_required("manage_users")
def create_new_user():
    data = request.json
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"message": "缺少必要参数"}), 400
    
    try:
        # 获取当前操作用户
        current_username = request.args.get('username') or request.json.get('current_username')
        
        with db_session() as db:
            # 检查用户名是否已存在
            existing_user = db.query(User).filter(User.username == data['username']).first()
            if existing_user:
                return jsonify({"message": "用户名已存在"}), 400
            
            # 检查角色
            role_id = data.get('role_id')
            if role_id:
                role = db.query(Role).filter(Role.id == role_id).first()
                if not role:
                    return jsonify({"message": "指定的角色不存在"}), 400
                
                # 只有超级管理员可以创建管理员用户
                if is_admin_role(role) and not is_super_admin(current_username):
                    current_user = db.query(User).filter(User.username == current_username).first()
                    if not current_user or not is_admin_role(current_user.role):
                        return jsonify({"message": "只有超级管理员可以创建管理员用户"}), 403
            
            # 创建新用户
            new_user = User(
                username=data['username'],
                password_hash=verify_password(data['password']),
                email=data.get('email', ''),
                full_name=data.get('full_name', ''),
                is_active=data.get('is_active', True),
                role_id=role_id,
                first_login=True
            )
            
            db.add(new_user)
            db.commit()
            
            return jsonify({
                "message": "用户创建成功",
                "user_id": new_user.id
            }), 201
    except Exception as e:
        print(f"创建用户异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 创建角色
@auth_bp.route('/roles', methods=['POST'])
@permission_required("manage_roles")
def create_role():
    data = request.json
    if not data or not data.get('name'):
        return jsonify({"message": "缺少角色名称"}), 400
    
    try:
        with db_session() as db:
            # 检查角色名是否已存在
            existing_role = db.query(Role).filter(Role.name == data['name']).first()
            if existing_role:
                return jsonify({"message": "角色名称已存在"}), 400
            
            # 创建新角色
            permissions = data.get('permissions', [])
            if not isinstance(permissions, list):
                permissions = []
            
            new_role = Role(
                name=data['name'],
                description=data.get('description', ''),
                permissions={"permissions": permissions}
            )
            
            db.add(new_role)
            db.commit()
            
            return jsonify({
                "message": "角色创建成功",
                "role_id": new_role.id
            }), 201
    except Exception as e:
        print(f"创建角色异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 获取所有角色
@auth_bp.route('/roles', methods=['GET'])
@jwt_required()  # 使用JWT认证保护路由
def get_roles():
    try:
        with db_session() as db:
            roles = db.query(Role).all()
            
            result = []
            for role in roles:
                permissions = role.permissions
                if isinstance(permissions, dict) and 'permissions' in permissions:
                    permissions = permissions['permissions']
                
                result.append({
                    "id": role.id,
                    "name": role.name,
                    "description": role.description,
                    "permissions": permissions
                })
            
            return jsonify(result)
    except Exception as e:
        print(f"获取角色列表异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 获取单个角色
@auth_bp.route('/roles/<int:role_id>', methods=['GET'])
@permission_required("manage_roles")
def get_role(role_id):
    try:
        with db_session() as db:
            role = db.query(Role).filter(Role.id == role_id).first()
            
            if not role:
                return jsonify({"message": "角色不存在"}), 404
            
            permissions = role.permissions
            if isinstance(permissions, dict) and 'permissions' in permissions:
                permissions = permissions['permissions']
            
            return jsonify({
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "permissions": permissions
            })
    except Exception as e:
        print(f"获取角色详情异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 更新角色
@auth_bp.route('/roles/<int:role_id>', methods=['PUT'])
@permission_required("manage_roles")
def update_role_info(role_id):
    data = request.json
    if not data:
        return jsonify({"message": "缺少更新数据"}), 400
    
    try:
        with db_session() as db:
            role = db.query(Role).filter(Role.id == role_id).first()
            
            if not role:
                return jsonify({"message": "角色不存在"}), 404
            
            # 不允许修改内置角色名称
            if role.name.lower() in ["admin", "管理员", "系统管理员"] and 'name' in data:
                return jsonify({"message": "不允许修改内置角色名称"}), 403
            
            # 更新字段
            if 'name' in data and data['name'] != role.name:
                # 检查角色名是否已存在
                existing_role = db.query(Role).filter(Role.name == data['name']).first()
                if existing_role:
                    return jsonify({"message": "角色名称已存在"}), 400
                role.name = data['name']
            
            if 'description' in data:
                role.description = data['description']
            
            if 'permissions' in data:
                permissions = data['permissions']
                if not isinstance(permissions, list):
                    permissions = []
                
                # 对管理员角色保留关键权限
                if role.name.lower() in ["admin", "管理员", "系统管理员"]:
                    admin_permissions = ["manage_users", "manage_roles", "configure_system"]
                    for perm in admin_permissions:
                        if perm not in permissions:
                            permissions.append(perm)
                
                role.permissions = {"permissions": permissions}
            
            db.commit()
            return jsonify({"message": "角色更新成功"})
    except Exception as e:
        print(f"更新角色信息异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 删除角色
@auth_bp.route('/roles/<int:role_id>', methods=['DELETE'])
@permission_required("manage_roles")
def delete_role(role_id):
    try:
        with db_session() as db:
            role = db.query(Role).filter(Role.id == role_id).first()
            
            if not role:
                return jsonify({"message": "角色不存在"}), 404
            
            # 不允许删除内置角色
            if role.name.lower() in ["admin", "管理员", "系统管理员"]:
                return jsonify({"message": "不允许删除内置角色"}), 403
            
            # 检查是否有用户正在使用此角色
            users_count = db.query(User).filter(User.role_id == role_id).count()
            if users_count > 0:
                return jsonify({"message": f"无法删除角色，有{users_count}个用户正在使用此角色"}), 400
            
            db.delete(role)
            db.commit()
            return jsonify({"message": "角色删除成功"})
    except Exception as e:
        print(f"删除角色异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500

# 调试权限
@auth_bp.route('/debug/permissions', methods=['GET'])
def debug_permissions():
    username = request.args.get('username')
    if not username:
        return jsonify({"message": "缺少用户名参数"}), 400
    
    try:
        with db_session() as db:
            user = db.query(User).filter(User.username == username).first()
            
            if not user:
                return jsonify({"message": "用户不存在"}), 404
            
            # 获取用户角色和权限
            role_info = "无角色" if not user.role else user.role.name
            permissions = None if not user.role else user.role.permissions
            
            # 处理权限格式
            formatted_permissions = []
            if permissions:
                if isinstance(permissions, dict) and 'permissions' in permissions:
                    formatted_permissions = permissions['permissions']
                elif isinstance(permissions, list):
                    formatted_permissions = permissions
            
            return jsonify({
                "username": user.username,
                "role": role_info,
                "permissions_raw": permissions,
                "permissions_formatted": formatted_permissions
            })
    except Exception as e:
        print(f"调试权限异常: {e}")
        return jsonify({"message": "服务器内部错误"}), 500 