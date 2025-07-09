"""
数据库会话管理模块 - 确保连接自动关闭
"""
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, scoped_session
from database_config import engine
import logging

logger = logging.getLogger(__name__)

# 创建线程安全的会话工厂
SessionFactory = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False  # 避免提交后访问对象属性重新查询数据库
    )
)

@contextmanager
def db_session():
    """
    自动管理会话生命周期的上下文管理器
    用法:
    with db_session() as session:
        # 使用session执行数据库操作
        result = session.query(Model).all()
        # ...
    # 会话自动关闭，连接归还到连接池
    """
    session = SessionFactory()
    try:
        yield session
        # 如果没有异常，提交事务
        session.commit()
    except Exception as e:
        # 发生异常，回滚事务
        session.rollback()
        logger.error(f"数据库事务错误，已回滚: {str(e)}")
        raise
    finally:
        # 确保会话始终关闭，连接归还到连接池
        session.close()
        
def get_db():
    """
    用于FastAPI/Flask依赖注入的辅助函数
    用法:
    @app.route('/users')
    def get_users():
        db = next(get_db())
        try:
            users = db.query(User).all()
            return jsonify([user.to_dict() for user in users])
        finally:
            db.close()
    """
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
        
# 直接替换掉database_config中的get_db函数
from database_config import get_db as original_get_db
import sys
sys.modules['database_config'].get_db = get_db 