"""连接中间件 - 确保请求结束后清理所有数据库连接。"""

from flask import Flask
import logging

from db_session import SessionFactory
from windpower_core.web.middleware import register_connection_middleware

logger = logging.getLogger(__name__)


def register_middleware(app: Flask) -> None:
    """向应用注册所有中间件。"""

    register_connection_middleware(app, SessionFactory)
    logger.info("数据库连接中间件已注册")