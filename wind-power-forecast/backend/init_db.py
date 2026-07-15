"""旧初始化入口，转发到统一数据库管理命令。"""

import sys

from init_users import init_users_and_roles
from manage_db import main as manage_database


if __name__ == "__main__":
    sys.argv = [sys.argv[0], "prepare"]
    exit_code = manage_database()
    if exit_code:
        raise SystemExit(exit_code)
    init_users_and_roles()
    print("数据库初始化完成")
