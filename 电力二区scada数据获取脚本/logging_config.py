import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta, timezone

class BeijingTimeFormatter(logging.Formatter):
    """自定义日志格式化器，使用北京时间"""
    
    def formatTime(self, record, datefmt=None):
        """重写formatTime方法，将日志时间调整为北京时间（UTC+8）"""
        # 从 record.created (UTC timestamp) 创建一个 timezone-aware UTC datetime 对象
        dt_utc = datetime.fromtimestamp(record.created, tz=timezone.utc)

        # 调整为北京时间（UTC+8）
        beijing_tz = timezone(timedelta(hours=8), name='Asia/Shanghai')
        dt_beijing = dt_utc.astimezone(beijing_tz)
        
        if datefmt:
            s = dt_beijing.strftime(datefmt)
        else:
            s = dt_beijing.strftime("%Y-%m-%d %H:%M:%S")
            # 添加毫秒 (record.msecs 是整数毫秒部分)
            s = "%s,%03d" % (s, record.msecs)
        return s

def configure_scada_logging(
    logger_name="SCADAClient",
    log_file_path="scada_client.log", 
    log_level="INFO",
    script_dir=None,
    backup_count=30,
    console_output=True
):
    """
    为SCADA数据获取脚本配置日志系统
    
    Args:
        logger_name (str): 日志记录器名称
        log_file_path (str): 日志文件路径
        log_level (str): 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        script_dir (str): 脚本目录，用于计算相对路径
        backup_count (int): 保留的历史日志文件数量
        console_output (bool): 是否同时输出到控制台
    
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    
    # 确保日志路径是绝对路径
    if script_dir and not os.path.isabs(log_file_path):
        log_file_path = os.path.join(script_dir, log_file_path)
    
    # 创建日志目录
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # 获取日志级别
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 创建日志记录器
    logger = logging.getLogger(logger_name)
    logger.setLevel(numeric_level)
    
    # 清除已有的处理器，避免重复
    logger.handlers.clear()
    
    # 创建北京时间格式化器
    formatter = BeijingTimeFormatter(
        '[%(asctime)s] %(name)s - %(levelname)s - %(message)s'
    )
    
    # 配置文件处理器（每天轮转）
    file_handler = TimedRotatingFileHandler(
        log_file_path,
        when="midnight",      # 每天午夜轮转
        interval=1,           # 每1天轮转一次
        backupCount=backup_count,  # 保留的备份文件数量
        encoding='utf-8'      # 指定编码
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 配置控制台处理器（可选）
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 防止日志向上传播到根日志记录器
    logger.propagate = False
    
    logger.info(f"日志系统已配置完成 - 文件: {log_file_path}, 级别: {log_level}, 保留: {backup_count}天")
    
    return logger

def configure_simple_logging(log_file_path="app.log", log_level="INFO"):
    """
    简单的日志配置函数，适用于快速设置
    
    Args:
        log_file_path (str): 日志文件路径
        log_level (str): 日志级别
    
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    return configure_scada_logging(
        logger_name="SimpleLogger",
        log_file_path=log_file_path,
        log_level=log_level,
        backup_count=7  # 简单配置只保留7天
    )
