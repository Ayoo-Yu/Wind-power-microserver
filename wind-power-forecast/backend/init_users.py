from database_config import get_db
from db_models import User, Role
from utils.admin_password import load_admin_password, validate_admin_password
from utils.password_utils import generate_password_hash
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

def init_users_and_roles():
    """初始化默认角色和管理员用户"""
    try:
        # 添加调试信息
        print("初始化默认角色和用户...")
        
        # 使用get_db获取数据库会话
        db = next(get_db())
        try:
            # 检查和创建角色
            init_roles(db)

            # 已有管理员保持原密码，全新数据库需要显式提供引导密码
            init_admin_user(db)
        finally:
            db.close()
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

def init_admin_user(db, password=None):
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
    
    if password is None:
        password = load_admin_password(
            "BOOTSTRAP_ADMIN_PASSWORD",
            "BOOTSTRAP_ADMIN_PASSWORD_FILE",
        )
    else:
        password = validate_admin_password(password)

    # 使用统一的哈希函数，日志中不输出密码或哈希片段
    password_hash = generate_password_hash(password)
    
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
