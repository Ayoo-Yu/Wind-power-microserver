"""
示例路由 - 展示正确的数据库连接使用方式
"""
from flask import Blueprint, jsonify, request
from db_models import Dataset, User
from db_session import db_session, get_db
import logging

logger = logging.getLogger(__name__)
example_bp = Blueprint('example', __name__)

#=================
# 方法一: 使用上下文管理器 (推荐)
#=================

@example_bp.route('/datasets', methods=['GET'])
def get_datasets():
    """使用上下文管理器自动管理会话生命周期"""
    try:
        with db_session() as session:
            # 数据库操作
            datasets = session.query(Dataset).limit(10).all()
            
            # 转换为JSON格式
            result = []
            for dataset in datasets:
                result.append({
                    'id': dataset.id,
                    'filename': dataset.filename,
                    'upload_time': dataset.upload_time.isoformat() if dataset.upload_time else None,
                    'file_type': dataset.file_type
                })
            
            return jsonify({"datasets": result})
    except Exception as e:
        logger.error(f"获取数据集失败: {str(e)}")
        return jsonify({"error": str(e)}), 500

#=================
# 方法二: 使用依赖注入方式 (适用于复杂请求)
#=================

@example_bp.route('/users', methods=['GET'])
def get_users():
    """使用依赖注入获取会话"""
    db = next(get_db())
    try:
        # 数据库操作
        users = db.query(User).limit(10).all()
        
        # 转换为JSON格式
        result = []
        for user in users:
            result.append({
                'id': user.id,
                'username': user.username,
                'email': user.email
            })
        
        return jsonify({"users": result})
    except Exception as e:
        logger.error(f"获取用户失败: {str(e)}")
        return jsonify({"error": str(e)}), 500
    finally:
        # 必须确保手动关闭会话
        db.close()

#=================
# 复杂操作示例
#=================

@example_bp.route('/complex-operation', methods=['POST'])
def complex_operation():
    """处理多个相关数据库操作"""
    try:
        with db_session() as session:
            # 第一步操作
            user_id = request.json.get('user_id')
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return jsonify({"error": "用户不存在"}), 404
            
            # 第二步操作 - 获取用户的数据集
            datasets = session.query(Dataset).filter(Dataset.created_by == user_id).all()
            
            # 业务逻辑处理...
            
            # 所有操作都成功完成，在with块结束时自动提交事务
            return jsonify({"message": "操作成功"})
    except Exception as e:
        # 发生任何异常，事务会自动回滚
        logger.error(f"复杂操作失败: {str(e)}")
        return jsonify({"error": str(e)}), 500 