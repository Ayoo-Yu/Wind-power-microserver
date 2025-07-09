#!/usr/bin/env python3
"""
管理员密码重置工具 - 在系统部署后可以运行此脚本重置管理员密码
"""
import sys
import os
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_config import get_db, engine
from utils.password_utils import generate_password_hash, get_debug_hash
from models import User

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def reset_admin_password(password="admin123"):
    """重置管理员密码"""
    try:
        db = next(get_db())
        
        # 查找管理员用户
        admin = db.query(User).filter(User.username == "admin").first()
        
        if not admin:
            logger.error("未找到管理员用户，请先运行初始化脚本")
            return False
        
        # 生成新密码哈希
        password_hash = generate_password_hash(password)
        
        # 更新密码
        admin.password_hash = password_hash
        db.commit()
        
        logger.info(f"管理员 '{admin.username}' 密码已重置")
        logger.info(f"密码哈希: {password_hash[:20]}...")
        
        return True
    except Exception as e:
        logger.error(f"重置密码失败: {str(e)}")
        return False

if __name__ == "__main__":
    # 显示使用统一方法生成的哈希值示例
    logger.info(get_debug_hash())
    
    # 重置密码
    if reset_admin_password():
        logger.info("密码重置成功，可以使用 admin/admin123 登录")
    else:
        logger.error("密码重置失败") 