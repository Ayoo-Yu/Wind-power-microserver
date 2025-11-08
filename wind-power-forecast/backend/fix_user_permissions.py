#!/usr/bin/env python3
"""
用户权限修复工具 - 检查并确保所有用户拥有正确的权限
"""
import sys
import os
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_config import get_db, engine
try:
    from .db_models import Base, User, Role
except ImportError:  # 在脚本模式下回退到绝对导入
    from db_models import Base, User, Role  # type: ignore
from sqlalchemy import text

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_user_permissions():
    """检查并修复所有用户的权限"""
    try:
        db = next(get_db())
        
        # 获取所有用户
        users = db.query(User).all()
        
        if not users:
            logger.info("没有找到任何用户")
            return True
        
        # 获取所有角色
        roles = db.query(Role).all()
        role_dict = {role.id: role for role in roles}
        
        fixed_count = 0
        
        for user in users:
            try:
                # 检查用户是否有有效的角色
                if user.role_id not in role_dict:
                    logger.warning(f"用户 '{user.username}' 没有有效的角色 ID: {user.role_id}")
                    
                    # 为普通用户分配默认角色
                    if user.username == "admin":
                        # 查找系统管理员角色
                        admin_role = db.query(Role).filter(Role.name == "系统管理员").first()
                        if admin_role:
                            user.role_id = admin_role.id
                            logger.info(f"已为管理员用户 '{user.username}' 分配系统管理员角色")
                        else:
                            logger.error(f"未找到系统管理员角色，无法修复用户 '{user.username}'")
                            continue
                    else:
                        # 为普通用户分配默认角色
                        default_role = db.query(Role).filter(Role.name == "普通用户").first()
                        if default_role:
                            user.role_id = default_role.id
                            logger.info(f"已为用户 '{user.username}' 分配普通用户角色")
                        else:
                            logger.error(f"未找到普通用户角色，无法修复用户 '{user.username}'")
                            continue
                    
                    fixed_count += 1
                else:
                    # 用户有有效的角色，检查角色权限
                    role = role_dict[user.role_id]
                    
                    # 确保角色权限格式正确
                    if not isinstance(role.permissions, dict) or "permissions" not in role.permissions:
                        logger.warning(f"用户 '{user.username}' 的角色 '{role.name}' 权限格式不正确")
                        
                        # 根据角色类型设置默认权限
                        if role.name == "系统管理员":
                            role.permissions = {
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
                        elif role.name == "普通用户":
                            role.permissions = {
                                "permissions": [
                                    "view_dashboard",
                                    "upload_files",
                                    "download_files",
                                    "run_predictions"
                                ]
                            }
                        else:
                            role.permissions = {
                                "permissions": [
                                    "view_dashboard"
                                ]
                            }
                        
                        fixed_count += 1
                        logger.info(f"已修复角色 '{role.name}' 的权限格式")
                
            except Exception as e:
                logger.error(f"修复用户 '{user.username}' 权限时发生错误: {str(e)}")
                continue
        
        # 提交所有更改
        db.commit()
        
        logger.info(f"权限修复完成，共修复 {fixed_count} 个用户/角色")
        return True
        
    except Exception as e:
        logger.error(f"修复用户权限失败: {str(e)}")
        return False

if __name__ == "__main__":
    if fix_user_permissions():
        logger.info("用户权限修复成功")
    else:
        logger.error("用户权限修复失败") 