from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class WeatherConnection(Base):
    """SSH连接配置表"""
    __tablename__ = 'weather_connections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment='连接名称')
    farm_code = Column(String(50), nullable=False, index=True, comment='场站编码')
    host = Column(String(255), nullable=False, comment='服务器地址')
    port = Column(Integer, default=22, comment='SSH端口')
    username = Column(String(100), nullable=False, comment='用户名')
    auth_type = Column(String(20), nullable=False, comment='认证方式: password/key')
    password = Column(String(255), comment='密码')
    private_key_path = Column(String(500), comment='私钥文件路径')
    key_passphrase = Column(String(255), comment='私钥密码')
    status = Column(String(20), default='disconnected', comment='连接状态')
    last_test_at = Column(DateTime, comment='最后测试时间')
    created_by = Column(Integer, comment='创建者ID')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, onupdate=datetime.utcnow, comment='更新时间')
    deleted_at = Column(DateTime, comment='删除时间（软删除）')

    # 关联关系
    tasks = relationship("WeatherTask", back_populates="connection")

class WeatherTask(Base):
    """数据拉取任务表"""
    __tablename__ = 'weather_tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment='任务名称')
    connection_id = Column(Integer, ForeignKey('weather_connections.id'), nullable=False, comment='SSH连接ID')
    farm_code = Column(String(50), nullable=False, index=True, comment='场站编码')
    remote_path = Column(String(500), nullable=False, comment='远程基础路径')
    path_pattern = Column(String(100), nullable=False, default='YYYY_MMDDHHNN', comment='时间文件夹模式')
    custom_path_pattern = Column(String(200), comment='自定义路径模式')
    time_strategy = Column(String(20), nullable=False, default='latest', comment='时间选择策略: latest/specific/range')
    specific_time = Column(DateTime, comment='指定时间')
    time_range_start = Column(DateTime, comment='时间范围开始')
    time_range_end = Column(DateTime, comment='时间范围结束')
    file_pattern = Column(String(100), nullable=False, comment='文件名模式')
    schedule = Column(String(50), nullable=False, comment='执行频率(cron格式)')
    save_path = Column(String(500), nullable=False, comment='本地保存路径')
    processing_options = Column(JSON, comment='数据处理选项')
    deduplication_options = Column(JSON, comment='去重设置选项')
    timeout = Column(Integer, default=300, comment='超时时间(秒)')
    retry_count = Column(Integer, default=3, comment='重试次数')
    enabled = Column(Boolean, default=True, comment='是否启用')
    status = Column(String(20), default='idle', comment='任务状态')
    last_run = Column(DateTime, comment='最后执行时间')
    next_run = Column(DateTime, comment='下次执行时间')
    description = Column(Text, comment='任务描述')
    created_by = Column(Integer, comment='创建者ID')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime, onupdate=datetime.utcnow, comment='更新时间')
    deleted_at = Column(DateTime, comment='删除时间（软删除）')

    # 关联关系
    connection = relationship("WeatherConnection", back_populates="tasks")
    logs = relationship("WeatherLog", back_populates="task")

class WeatherLog(Base):
    """执行日志表"""
    __tablename__ = 'weather_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('weather_tasks.id'), nullable=False, comment='任务ID')
    farm_code = Column(String(50), nullable=False, index=True, comment='场站编码')
    log_level = Column(String(20), nullable=False, comment='日志级别: info/warning/error/success')
    message = Column(Text, nullable=False, comment='日志消息')
    details = Column(Text, comment='详细信息')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')

    # 关联关系
    task = relationship("WeatherTask", back_populates="logs")

class WeatherData(Base):
    """气象数据处理记录表"""
    __tablename__ = 'weather_data_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('weather_tasks.id'), nullable=False, comment='任务ID')
    farm_code = Column(String(50), nullable=False, index=True, comment='场站编码')
    file_name = Column(String(255), nullable=False, comment='文件名')
    file_path = Column(String(500), comment='文件路径')
    file_size = Column(Integer, comment='文件大小(字节)')
    records_count = Column(Integer, default=0, comment='插入记录数')
    status = Column(String(20), default='processing', comment='处理状态: processing/success/failed')
    error_message = Column(Text, comment='错误信息')
    started_at = Column(DateTime, default=datetime.utcnow, comment='开始处理时间')
    completed_at = Column(DateTime, comment='完成处理时间')

    # 关联关系
    task = relationship("WeatherTask") 