"""
Zone2 处理器专用数据库配置

最小化 SQLAlchemy 引擎，从环境变量读取连接参数。
不依赖 Flask 上下文，可独立运行。

环境变量:
  DB_HOST - 数据库主机 (默认 host.docker.internal)
  DB_PORT - 数据库端口 (默认 54321)
  DB_USER - 数据库用户 (默认 system)
  DB_PASSWORD - 数据库密码
  DB_NAME - 数据库名 (默认 windpower)
"""

import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, Session

# 导入金仓方言以处理版本字符串兼容性
import kingbase_dialect

logger = logging.getLogger(__name__)

DB_HOST = os.environ.get('DB_HOST', 'host.docker.internal')
DB_PORT = os.environ.get('DB_PORT', '54321')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME', 'windpower')

# 使用 URL.create() 构建连接字符串，密码不会出现在 URI 字面量中
DATABASE_URL = URL.create(
    "postgresql+kingbase",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        logger.info(f"Creating DB engine: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        _engine = create_engine(
            DATABASE_URL,
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
            connect_args={'connect_timeout': 10}
        )
    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        engine = _get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal()
