#!/usr/bin/env python3
"""管理员密码人工重置工具。"""
import getpass
import sys
import os
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_config import get_db
from utils.admin_password import load_admin_password, validate_admin_password
from utils.password_utils import generate_password_hash
from models import User

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def reset_admin_password(password):
    """重置管理员密码"""
    try:
        password = validate_admin_password(password)
        db = next(get_db())
        try:
            # 查找管理员用户
            admin = db.query(User).filter(User.username == "admin").first()

            if not admin:
                logger.error("未找到管理员用户，请先运行初始化脚本")
                return False

            admin.password_hash = generate_password_hash(password)
            db.commit()
            logger.info("管理员 '%s' 密码已重置", admin.username)
            return True
        finally:
            db.close()
    except Exception as e:
        logger.error(f"重置密码失败: {str(e)}")
        return False


def _read_reset_password():
    """优先读取受控环境配置，交互终端中允许隐藏输入。"""

    if os.environ.get("RESET_ADMIN_PASSWORD") or os.environ.get("RESET_ADMIN_PASSWORD_FILE"):
        return load_admin_password(
            "RESET_ADMIN_PASSWORD",
            "RESET_ADMIN_PASSWORD_FILE",
        )
    if not sys.stdin.isatty():
        raise RuntimeError(
            "非交互环境需要设置 RESET_ADMIN_PASSWORD 或 RESET_ADMIN_PASSWORD_FILE"
        )
    first = getpass.getpass("请输入新的管理员密码: ")
    second = getpass.getpass("请再次输入新的管理员密码: ")
    if first != second:
        raise RuntimeError("两次输入的密码不一致")
    return validate_admin_password(first)


if __name__ == "__main__":
    try:
        new_password = _read_reset_password()
    except Exception as exc:
        logger.error("无法读取新密码: %s", exc)
        raise SystemExit(2) from exc
    raise SystemExit(0 if reset_admin_password(new_password) else 1)
