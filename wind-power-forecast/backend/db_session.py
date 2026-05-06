"""
数据库会话管理模块 - 确保连接自动关闭

支持数据库断连后自动重连：
- 每次获取 session 时通过 ensure_engine() 尝试重连
- 连接失败时抛出 RuntimeError，由上层错误处理器转为 503
"""
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, DisconnectionError
import logging

from database_config import ensure_engine, invalidate_engine, _sync_legacy_refs

logger = logging.getLogger(__name__)


def _make_session():
    """Create a new session bound to the current engine (or None)."""
    eng = ensure_engine()
    _sync_legacy_refs()
    if eng is None:
        raise RuntimeError("database connection unavailable")
    factory = sessionmaker(autocommit=False, autoflush=False, bind=eng, expire_on_commit=False)
    return factory()


@contextmanager
def db_session():
    """Context manager that auto-manages session lifecycle.

    On OperationalError / DisconnectionError the engine is invalidated so
    the next call will attempt a fresh connection.
    """
    session = _make_session()
    try:
        yield session
        session.commit()
    except (OperationalError, DisconnectionError) as e:
        session.rollback()
        invalidate_engine()
        _sync_legacy_refs()
        logger.warning(f"database connection lost: {e}")
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"database transaction error, rolled back: {e}")
        raise
    finally:
        session.close()


def get_db():
    """Generator for Flask dependency injection."""
    session = _make_session()
    try:
        yield session
    finally:
        session.close()


# Replace database_config.get_db so that all existing imports work.
import sys
sys.modules['database_config'].get_db = get_db
