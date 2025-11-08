from database_config import get_db, engine
from .db_models import Base, User, Role
from utils.password_utils import generate_password_hash
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

def init_users_and_roles():
    """初始化默认角色和管理员用户"""
    try:
        # 添加调试信息
        print("初始化数据库表和用户...")
        
        # 创建数据库表
        Base.metadata.create_all(bind=engine)
        
        # 使用get_db获取数据库会话
        db = next(get_db())
        
        # 检查和创建角色
        init_roles(db)
        
        # 检查和创建管理员用户
        init_admin_user(db)
        
    except Exception as e:
        logger.error(f"初始化用户和角色失败: {str(e)}")
        raise

def init_roles(db):
    """初始化角色"""
    # 检查是否已经有角色
    roles_count = db.query(Role).count()
    if roles_count > 0:
        logger.info("已经存在角色数据，跳过角色初始化")
        return
    
    logger.info("开始初始化默认角色")
    
    # 创建默认角色 - 使用列表格式的权限，与auth.py中的权限检查兼容
    admin_role = Role(
        name="系统管理员",
        description="系统管理员，拥有所有权限",
        permissions={
            "permissions": [
                # 用户管理权限
                "manage_users",
                "manage_roles",
                # 数据访问权限
                "view_all_data",
                "upload_files",
                "download_files",
                # 模型和预测权限
                "train_models",
                "run_predictions",
                "auto_predictions",
                "run_simulations",
                # 系统管理权限
                "configure_system",
                "system_maintenance",
                "manage_reports",
                "manage_weather_data",
                # 基础权限
                "view_dashboard",
                "manage_tasks"
            ]
        }
    )
    
    operator_role = Role(
        name="运行操作人员",
        description="运行操作人员，可以使用除了用户管理和系统维护外的所有功能",
        permissions={
            "permissions": [
                # 数据访问权限
                "view_all_data",
                "upload_files",
                "download_files",
                # 模型和预测权限
                "train_models",
                "run_predictions",
                "auto_predictions",
                "run_simulations",
                # 系统管理权限（除了用户管理和系统维护）
                "configure_system",
                "manage_reports",
                "manage_weather_data",
                # 基础权限
                "view_dashboard",
                "manage_tasks"
            ]
        }
    )
    
    viewer_role = Role(
        name="普通人员",
        description="普通人员，可以使用模型训练、模型预测、数据展示、物理仿真",
        permissions={
            "permissions": [
                # 数据访问权限
                "view_all_data",
                # 模型和预测权限
                "train_models",
                "run_predictions",
                "run_simulations",
                # 基础权限
                "view_dashboard"
            ]
        }
    )
    
    db.add_all([admin_role, operator_role, viewer_role])
    db.commit()
    logger.info("角色初始化完成")

def init_admin_user(db):
    """初始化管理员用户"""
    # 检查是否已经有管理员用户
    admin_exists = db.query(User).filter(User.username == "admin").first()
    if admin_exists:
        logger.info("管理员用户已存在，跳过用户初始化")
        return
    
    logger.info("开始初始化管理员用户")
    
    # 获取系统管理员角色
    admin_role = db.query(Role).filter(Role.name == "系统管理员").first()
    if not admin_role:
        logger.error("未找到系统管理员角色，无法创建管理员用户")
        return
    
    # 使用统一的哈希函数
    password_hash = generate_password_hash("admin123")
    logger.info(f"生成的密码哈希: {password_hash[:20]}...")
    
    # 创建默认管理员用户
    admin_user = User(
        username="admin",
        password_hash=password_hash,
        email="admin@example.com",
        full_name="系统管理员",
        is_active=True,
        role_id=admin_role.id,
        created_at=datetime.now()
    )
    
    db.add(admin_user)
    db.commit()
    
    logger.info(f"初始化完成，创建了管理员用户: {admin_user.username}")

if __name__ == "__main__":
    init_users_and_roles() 