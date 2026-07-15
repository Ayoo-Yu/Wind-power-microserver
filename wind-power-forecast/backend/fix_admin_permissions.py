#!/usr/bin/env python3
"""
管理员权限修复工具 - 检查并确保admin用户拥有正确的管理员权限
"""
import sys
import os
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_config import get_db, engine
from db_models import Base, User, Role
from sqlalchemy import text

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_admin_permissions():
    """检查并修复管理员用户权限"""
    try:
        db = next(get_db())
        
        # 查找系统管理员角色
        admin_role = db.query(Role).filter(Role.name == "系统管理员").first()
        
        if not admin_role:
            logger.error("未找到系统管理员角色，尝试创建...")
            admin_role = Role(
                name="系统管理员",
                description="系统管理员，拥有所有权限",
                permissions={
                    "permissions": [
                        "manage_users",
                        "manage_roles",
                        "view_all_data",
                        "upload_files",
                        "download_files",
                        "train_models",
                        "run_predictions",
                        "configure_system",
                        "manage_reports",
                        "view_dashboard",
                        "manage_tasks"
                    ]
                }
            )
            db.add(admin_role)
            db.commit()
            logger.info("已创建系统管理员角色")
        
        # 检查权限格式
        permissions = admin_role.permissions
        
        # 显示当前权限
        logger.info(f"当前权限设置: {permissions}")
        
        # 确保权限格式正确且包含管理员运行所需权限。
        if (
            isinstance(permissions, dict)
            and isinstance(permissions.get("permissions"), list)
        ):
            required_permissions = {"manage_users", "manage_reports"}
            missing_permissions = sorted(required_permissions - set(permissions["permissions"]))
            if missing_permissions:
                updated_permissions = dict(permissions)
                updated_permissions["permissions"] = (
                    list(permissions["permissions"]) + missing_permissions
                )
                admin_role.permissions = updated_permissions
                db.commit()
                logger.info(f"已补充管理员权限: {missing_permissions}")
        else:
            # 如果权限格式不正确，重置为正确的格式
            admin_role.permissions = {
                "permissions": [
                    "manage_users",
                    "manage_roles",
                    "view_all_data",
                    "upload_files",
                    "download_files",
                    "train_models",
                    "run_predictions",
                    "configure_system",
                    "manage_reports",
                    "view_dashboard",
                    "manage_tasks"
                ]
            }
            db.commit()
            logger.info("已重置权限格式")
        
        # 查找管理员用户
        admin_user = db.query(User).filter(User.username == "admin").first()
        
        if not admin_user:
            logger.error("未找到管理员用户，请先运行初始化脚本")
            return False
        
        # 确保admin用户关联的是系统管理员角色
        if admin_user.role_id != admin_role.id:
            admin_user.role_id = admin_role.id
            db.commit()
            logger.info(f"已将用户 {admin_user.username} 关联到系统管理员角色")
        
        logger.info(f"管理员用户 '{admin_user.username}' 权限已检查和修复")
        return True
            
    except Exception as e:
        logger.error(f"修复权限失败: {str(e)}")
        return False

if __name__ == "__main__":
    if fix_admin_permissions():
        logger.info("管理员权限修复成功")
    else:
        logger.error("管理员权限修复失败")
