"""Flask 连接中间件。"""

from flask import Flask, g, request
from sqlalchemy.orm import scoped_session
import logging
import time


logger = logging.getLogger(__name__)


def register_connection_middleware(app: Flask, session_factory: scoped_session) -> None:
    """注册请求生命周期钩子，确保数据库连接被释放。"""

    @app.before_request
    def setup_request():  # type: ignore[override]
        g.start_time = request.environ.get("REQUEST_TIME")

    @app.teardown_request
    def teardown_request(exception=None):  # type: ignore[override]
        session_factory.remove()

        if exception:
            logger.error(f"请求处理异常: {exception}")

        if hasattr(g, "start_time") and g.start_time:
            elapsed = time.time() - g.start_time
            logger.debug(f"请求处理时间: {elapsed:.4f}秒 - {request.method} {request.path}")
            delattr(g, "start_time")

        if hasattr(g, "db"):
            try:
                g.db.close()
            except Exception as close_exc:  # pragma: no cover - 仅打印告警
                logger.error(f"关闭数据库会话失败: {close_exc}")
            finally:
                delattr(g, "db")

        logger.debug(f"请求资源已清理 - {request.method} {request.path}")


