from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from database_config import get_db
from models import User, Role
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
from db_session import db_session  # 导入上下文管理器

user_bp = Blueprint('user', __name__)

# 获取所有用户
@user_bp.route('/users', methods=['GET'])
def get_users():
    with db_session() as db:
        users = db.query(User).all()
        
        result = []
        for user in users:
            result.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'is_active': user.is_active,
                'role_id': user.role_id,
                'role_name': user.role.name if user.role else None,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None
            })
        
        return jsonify(result)

# 获取单个用户
@user_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    with db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        result = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.full_name,
            'is_active': user.is_active,
            'role_id': user.role_id,
            'role_name': user.role.name if user.role else None,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None
        }
        
        return jsonify(result)

# 创建用户
@user_bp.route('/users', methods=['POST'])
def create_user():
    data = request.json
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    with db_session() as db:
        # 检查用户名是否已存在
        existing_user = db.query(User).filter(User.username == data['username']).first()
        if existing_user:
            return jsonify({'error': '用户名已存在'}), 400
        
        # 检查角色是否存在
        role_id = data.get('role_id')
        if role_id:
            role = db.query(Role).filter(Role.id == role_id).first()
            if not role:
                return jsonify({'error': '指定的角色不存在'}), 400
        
        # 创建新用户
        new_user = User(
            username=data['username'],
            password_hash=generate_password_hash(data['password']),
            email=data.get('email'),
            full_name=data.get('full_name'),
            is_active=data.get('is_active', True),
            role_id=role_id,
            created_at=datetime.now()
        )
        
        try:
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            return jsonify({
                'id': new_user.id,
                'username': new_user.username,
                'message': '用户创建成功'
            }), 201
        except IntegrityError:
            db.rollback()
            return jsonify({'error': '创建用户失败，可能是用户名或邮箱已存在'}), 400

# 更新用户
@user_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    
    if not data:
        return jsonify({'error': '没有提供更新数据'}), 400
    
    with db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        # 更新用户信息
        if 'username' in data and data['username'] != user.username:
            # 检查新用户名是否已存在
            existing_user = db.query(User).filter(User.username == data['username']).first()
            if existing_user:
                return jsonify({'error': '用户名已存在'}), 400
            user.username = data['username']
        
        if 'password' in data:
            user.password_hash = generate_password_hash(data['password'])
        
        if 'email' in data:
            user.email = data['email']
        
        if 'full_name' in data:
            user.full_name = data['full_name']
        
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        if 'role_id' in data:
            # 检查角色是否存在
            role = db.query(Role).filter(Role.id == data['role_id']).first()
            if not role:
                return jsonify({'error': '指定的角色不存在'}), 400
            user.role_id = data['role_id']
        
        try:
            db.commit()
            return jsonify({'message': '用户更新成功'})
        except IntegrityError:
            db.rollback()
            return jsonify({'error': '更新用户失败，可能是用户名或邮箱已存在'}), 400

# 删除用户
@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    with db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        try:
            db.delete(user)
            db.commit()
            return jsonify({'message': '用户删除成功'})
        except Exception as e:
            db.rollback()
            return jsonify({'error': f'删除用户失败: {str(e)}'}), 500

# 获取所有角色
@user_bp.route('/roles', methods=['GET'])
def get_roles():
    with db_session() as db:
        roles = db.query(Role).all()
        
        result = []
        for role in roles:
            result.append({
                'id': role.id,
                'name': role.name,
                'description': role.description,
                'permissions': role.permissions
            })
        
        return jsonify(result)

# 获取单个角色
@user_bp.route('/roles/<int:role_id>', methods=['GET'])
def get_role(role_id):
    with db_session() as db:
        role = db.query(Role).filter(Role.id == role_id).first()
        
        if not role:
            return jsonify({'error': '角色不存在'}), 404
        
        result = {
            'id': role.id,
            'name': role.name,
            'description': role.description,
            'permissions': role.permissions
        }
        
        return jsonify(result)

# 创建角色
@user_bp.route('/roles', methods=['POST'])
def create_role():
    data = request.json
    
    if not data or not data.get('name'):
        return jsonify({'error': '角色名不能为空'}), 400
    
    with db_session() as db:
        # 检查角色名是否已存在
        existing_role = db.query(Role).filter(Role.name == data['name']).first()
        if existing_role:
            return jsonify({'error': '角色名已存在'}), 400
        
        # 创建新角色
        new_role = Role(
            name=data['name'],
            description=data.get('description', ''),
            permissions=data.get('permissions', {})
        )
        
        try:
            db.add(new_role)
            db.commit()
            db.refresh(new_role)
            
            return jsonify({
                'id': new_role.id,
                'name': new_role.name,
                'message': '角色创建成功'
            }), 201
        except IntegrityError:
            db.rollback()
            return jsonify({'error': '创建角色失败'}), 400

# 更新角色
@user_bp.route('/roles/<int:role_id>', methods=['PUT'])
def update_role(role_id):
    data = request.json
    
    if not data:
        return jsonify({'error': '没有提供更新数据'}), 400
    
    with db_session() as db:
        role = db.query(Role).filter(Role.id == role_id).first()
        
        if not role:
            return jsonify({'error': '角色不存在'}), 404
        
        # 更新角色信息
        if 'name' in data and data['name'] != role.name:
            # 检查新角色名是否已存在
            existing_role = db.query(Role).filter(Role.name == data['name']).first()
            if existing_role:
                return jsonify({'error': '角色名已存在'}), 400
            role.name = data['name']
        
        if 'description' in data:
            role.description = data['description']
        
        if 'permissions' in data:
            role.permissions = data['permissions']
        
        try:
            db.commit()
            return jsonify({'message': '角色更新成功'})
        except IntegrityError:
            db.rollback()
            return jsonify({'error': '更新角色失败'}), 400

# 删除角色
@user_bp.route('/roles/<int:role_id>', methods=['DELETE'])
def delete_role(role_id):
    with db_session() as db:
        role = db.query(Role).filter(Role.id == role_id).first()
        
        if not role:
            return jsonify({'error': '角色不存在'}), 404
        
        # 检查是否有用户使用此角色
        users_with_role = db.query(User).filter(User.role_id == role_id).count()
        if users_with_role > 0:
            return jsonify({'error': f'无法删除角色，有{users_with_role}个用户正在使用此角色'}), 400
        
        try:
            db.delete(role)
            db.commit()
            return jsonify({'message': '角色删除成功'})
        except Exception as e:
            db.rollback()
            return jsonify({'error': f'删除角色失败: {str(e)}'}), 500

# 初始化用户和角色
@user_bp.route('/init', methods=['POST'])
def init_users():
    with db_session() as db:
        # 检查是否已经有用户
        existing_users = db.query(User).count()
        if existing_users > 0:
            return jsonify({'message': '已有用户存在，无需初始化'}), 400
        
        # 创建角色
        admin_role = Role(name='管理员', description='系统管理员', permissions={'admin': True})
        user_role = Role(name='普通用户', description='普通用户', permissions={'user': True})
        
        db.add(admin_role)
        db.add(user_role)
        db.flush()  # 获取新创建角色的ID
        
        # 创建管理员用户
        admin_user = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            email='admin@example.com',
            full_name='系统管理员',
            is_active=True,
            role_id=admin_role.id,
            created_at=datetime.now()
        )
        
        # 创建测试用户
        test_user = User(
            username='user',
            password_hash=generate_password_hash('user123'),
            email='user@example.com',
            full_name='测试用户',
            is_active=True,
            role_id=user_role.id,
            created_at=datetime.now()
        )
        
        db.add(admin_user)
        db.add(test_user)
        
        try:
            db.commit()
            return jsonify({'message': '用户和角色初始化成功'})
        except Exception as e:
            db.rollback()
            return jsonify({'error': f'初始化失败: {str(e)}'}), 500 