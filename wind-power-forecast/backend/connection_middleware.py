"""
连接中间件 - 确保请求结束后清理所有数据库连接
"""
from flask import Flask, g, request
import logging
from db_session import SessionFactory

logger = logging.getLogger(__name__)

def init_connection_middleware(app: Flask):
    """
    初始化连接中间件
    
    在请求结束时自动清理会话和连接，防止连接泄漏
    """
    @app.before_request
    def setup_request():
        """在请求开始时记录开始时间"""
        g.start_time = request.environ.get('REQUEST_TIME', None)
    
    @app.teardown_request
    def teardown_request(exception=None):
        """
        在请求结束时自动清理资源
        无论请求是否成功，都会执行此函数
        """
        # 移除当前线程的会话
        SessionFactory.remove()
        
        if exception:
            logger.error(f"请求处理异常: {str(exception)}")
        
        # 记录请求处理时间（如果有开始时间）
        if hasattr(g, 'start_time') and g.start_time:
            import time
            elapsed = time.time() - g.start_time
            logger.debug(f"请求处理时间: {elapsed:.4f}秒 - {request.method} {request.path}")
        
        # 删除g中的属性，防止内存泄漏
        if hasattr(g, 'start_time'):
            delattr(g, 'start_time')
        
        # 如果g中存储了数据库会话，确保关闭
        if hasattr(g, 'db'):
            try:
                g.db.close()
            except Exception as e:
                logger.error(f"关闭数据库会话失败: {str(e)}")
            finally:
                delattr(g, 'db')
        
        logger.debug(f"请求资源已清理 - {request.method} {request.path}")

def register_middleware(app: Flask):
    """向应用注册所有中间件"""
    init_connection_middleware(app)
    logger.info("数据库连接中间件已注册") 