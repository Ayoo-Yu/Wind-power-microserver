import sys
import os
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_config import get_db, engine, Base
from models import Role, User
from services.auth_service import get_password_hash, get_user_by_username, get_role_by_id

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 定义默认角色和权限
DEFAULT_ROLES = [
    {
        "name": "系统管理员",
        "description": "系统管理员，拥有所有权限",
        "permissions": {
            "permissions": [
                "manage_users",
                "manage_roles",
                "view_all_data",
                "upload_files",
                "download_files",
                "train_models",
                "run_predictions",
                "configure_system",
                "view_dashboard",
                "manage_tasks"
            ]
        }
    },
    {
        "name": "运行操作人员",
        "description": "运行操作人员，可以进行模型训练和预测",
        "permissions": {
            "permissions": [
                "view_all_data",
                "upload_files",
                "download_files",
                "train_models",
                "run_predictions",
                "view_dashboard"
            ]
        }
    },
    {
        "name": "普通用户",
        "description": "普通用户，只能查看数据",
        "permissions": {
            "permissions": [
                "view_dashboard"
            ]
        }
    }
]

# 默认管理员用户
DEFAULT_ADMIN = {
    "username": "admin",
    "password": "admin123",  # 初始密码，应该在首次登录后修改
    "email": "admin@example.com",
    "full_name": "系统管理员"
}

def create_default_roles(db):
    """创建默认角色"""
    for role_data in DEFAULT_ROLES:
        # 检查角色是否已存在
        existing_role = db.query(Role).filter(Role.name == role_data["name"]).first()
        if existing_role:
            logger.info(f"角色 '{role_data['name']}' 已存在，跳过创建")
            continue
        
        # 创建新角色
        role = Role(
            name=role_data["name"],
            description=role_data["description"],
            permissions=role_data["permissions"]
        )
        db.add(role)
        logger.info(f"创建角色: {role_data['name']}")
    
    db.commit()

def create_admin_user(db):
    """创建管理员用户"""
    # 检查用户是否已存在
    existing_user = get_user_by_username(db, DEFAULT_ADMIN["username"])
    if existing_user:
        logger.info(f"用户 '{DEFAULT_ADMIN['username']}' 已存在，跳过创建")
        return
    
    # 获取管理员角色
    admin_role = db.query(Role).filter(Role.name == "系统管理员").first()
    if not admin_role:
        logger.error("未找到系统管理员角色，请先创建角色")
        return
    
    # 创建管理员用户
    hashed_password = get_password_hash(DEFAULT_ADMIN["password"])
    admin_user = User(
        username=DEFAULT_ADMIN["username"],
        password_hash=hashed_password,
        email=DEFAULT_ADMIN["email"],
        full_name=DEFAULT_ADMIN["full_name"],
        role_id=admin_role.id
    )
    
    db.add(admin_user)
    db.commit()
    logger.info(f"创建管理员用户: {DEFAULT_ADMIN['username']}")

def init_users_and_roles():
    """初始化用户和角色"""
    logger.info("开始初始化用户和角色...")
    
    db = next(get_db())
    
    try:
        # 创建默认角色
        create_default_roles(db)
        
        # 创建管理员用户
        create_admin_user(db)
        
        logger.info("用户和角色初始化完成")
    except Exception as e:
        logger.error(f"初始化过程中发生错误: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_users_and_roles() 