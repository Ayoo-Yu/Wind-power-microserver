import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta, timezone


class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Windows-safe TimedRotatingFileHandler that handles locked log files."""

    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            pass

    def emit(self, record):
        try:
            super().emit(record)
        except PermissionError:
            pass

class BeijingTimeFormatter(logging.Formatter):
    """自定义日志格式化器，使用北京时间"""
    
    def formatTime(self, record, datefmt=None):
        """重写formatTime方法，将日志时间调整为北京时间（UTC+8）"""
        # 从 record.created (UTC timestamp) 创建一个 timezone-aware UTC datetime 对象
        dt_utc = datetime.fromtimestamp(record.created, tz=timezone.utc)

        # 调整为北京时间（UTC+8）
        # Create a specific timezone object for UTC+8
        beijing_tz = timezone(timedelta(hours=8), name='Asia/Shanghai') # or just timedelta(hours=8)
        dt_beijing = dt_utc.astimezone(beijing_tz)
        
        if datefmt:
            s = dt_beijing.strftime(datefmt)
        else:
            s = dt_beijing.strftime("%Y-%m-%d %H:%M:%S")
            # 添加毫秒 (record.msecs 是整数毫秒部分)
            s = "%s,%03d" % (s, record.msecs)
        return s

class SocketIOHandler(logging.Handler):
    """自定义日志处理器，通过SocketIO发送日志消息。"""
    def __init__(self, socketio):
        super().__init__()
        self.socketio = socketio

    def emit(self, record):
        log_entry = self.format(record)
        print(f"Emitting log: {log_entry}")  # 调试信息
        self.socketio.emit('log', {'message': log_entry})

def configure_logging(app, socketio):
    # 删除原有的RotatingFileHandler配置
    # 改用更安全的日志处理方式
    
    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # 文件日志（使用TimedRotatingFileHandler替代FileHandler）
    # 确保 logs 目录存在
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    file_handler = SafeTimedRotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        when="midnight",      # Rotate at midnight
        interval=1,           # Daily rotation
        backupCount=30,       # Keep 30 backup files
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # 添加 SocketIO 处理器
    socketio_handler = SocketIOHandler(socketio)
    socketio_handler.setLevel(logging.INFO)
    
    # 创建使用北京时间的格式化器
    formatter = BeijingTimeFormatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    socketio_handler.setFormatter(formatter)
    
    # 清空原有处理器
    app.logger.handlers.clear()
    
    # 添加新处理器
    app.logger.addHandler(console_handler)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(socketio_handler)
    app.logger.setLevel(logging.DEBUG)
    
    # 添加Socket.IO日志
    engineio_logger = logging.getLogger('engineio')
    # Clear existing handlers for engineio_logger if any, to avoid duplication
    engineio_logger.handlers.clear() 
    engineio_logger.addHandler(console_handler)
    engineio_logger.addHandler(file_handler)
    engineio_logger.addHandler(socketio_handler)
    engineio_logger.propagate = False # Prevent duplicating logs to root logger if it also has handlers
    engineio_logger.setLevel(logging.DEBUG) # Or app.logger.level if preferred

    app.logger.info('Wind Forecast Backend Startup with TimedRotatingFileHandler for app.log')
