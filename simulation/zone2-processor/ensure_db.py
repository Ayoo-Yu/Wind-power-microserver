"""
Zone2 数据库引导脚本

启动时自动：
1. 等待 KingBase TCP 端口可达
2. 创建 windpower 数据库（如不存在）
3. 创建 ecmwf_meteorological_data 表（如不存在）
"""

import time
import sys
import socket
import logging
import os
import re

sys.path.insert(0, '/opt/scripts')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('ensure_db')

DB_HOST = os.environ.get('DB_HOST', 'host.docker.internal')
DB_PORT = int(os.environ.get('DB_PORT', '54321'))
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME', 'windpower')

if not DB_USER or not DB_PASSWORD:
    raise RuntimeError("DB_USER and DB_PASSWORD environment variables are required")

# 校验 DB_NAME 只含安全字符，防止 DDL 注入
_SAFE_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]+$')
if not _SAFE_NAME_RE.match(DB_NAME):
    raise ValueError(f"Invalid DB_NAME: {DB_NAME!r} (only alphanumeric and underscore allowed)")


def wait_for_db(timeout=120):
    """等待 KingBase TCP 端口可达"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection((DB_HOST, DB_PORT), 5)
            s.close()
            logger.info(f"DB reachable at {DB_HOST}:{DB_PORT}")
            return True
        except OSError:
            remaining = int(deadline - time.time())
            logger.info(f"Waiting for DB at {DB_HOST}:{DB_PORT}... ({remaining}s left)")
            time.sleep(5)
    raise TimeoutError(f"DB not reachable at {DB_HOST}:{DB_PORT} after {timeout}s")


def ensure_database():
    """创建数据库（如不存在）"""
    import psycopg2
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        dbname='TEST'  # KingBase 默认存在的数据库
    )
    conn.autocommit = True
    cur = conn.cursor()
    # 参数化查询防止 SQL 注入
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
    if not cur.fetchone():
        # CREATE DATABASE 不支持参数化，但 DB_NAME 已通过正则校验
        cur.execute(f'CREATE DATABASE "{DB_NAME}"')
        logger.info(f"Created database: {DB_NAME}")
    else:
        logger.info(f"Database already exists: {DB_NAME}")
    cur.close()
    conn.close()


def ensure_tables():
    """创建表（如不存在）"""
    from db_config import _get_engine
    from db_models.base import Base
    from db_models.ecmwf_model import EcmwfMeteorologicalData  # noqa: F401 — 触发表注册

    engine = _get_engine()
    Base.metadata.create_all(engine)
    logger.info("Ensured all tables exist")


if __name__ == '__main__':
    try:
        wait_for_db()
        ensure_database()
        ensure_tables()
        logger.info("DB bootstrap complete")
    except Exception as e:
        logger.error(f"DB bootstrap failed: {e}")
        sys.exit(1)
