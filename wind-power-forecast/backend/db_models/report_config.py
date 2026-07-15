from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float
from datetime import datetime
from .base import Base

class WindFarm(Base):
    """风电场站信息模型"""
    __tablename__ = "wind_farms"
    
    id = Column(Integer, primary_key=True)
    farm_code = Column(String(50), nullable=False, unique=True, index=True)  # 场站编码
    farm_name = Column(String(100), nullable=False)  # 场站名称
    capacity = Column(Float, nullable=True)  # 装机容量(MW)
    location = Column(String(200), nullable=True)  # 地理位置
    is_active = Column(Boolean, default=True)  # 是否启用
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class ReportConfig(Base):
    """上报配置模型"""
    __tablename__ = "report_configs"
    
    id = Column(Integer, primary_key=True)
    farm_id = Column(Integer, nullable=False, index=True)  # 关联风电场站ID
    report_type = Column(String(50), nullable=False)  # 上报类型: 'actual', 'forecast_short', 'forecast_long'
    target_ip = Column(String(100), nullable=False)  # 目标IP地址
    target_port = Column(Integer, nullable=False)  # 目标端口
    report_interval = Column(Integer, nullable=False)  # 上报周期（分钟）
    report_time = Column(String(10), nullable=True)  # 定时上报时间（HH:MM，仅用于长期预测）
    is_enabled = Column(Boolean, default=True)  # 是否启用
    last_report_time = Column(DateTime, nullable=True)  # 最后上报时间
    report_format = Column(String(20), default='json')  # 上报格式: json, xml, csv
    timeout_seconds = Column(Integer, default=30)  # 超时时间（秒）
    retry_count = Column(Integer, default=3)  # 重试次数
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class ReportLog(Base):
    """上报日志模型"""
    __tablename__ = "report_logs"
    
    id = Column(Integer, primary_key=True)
    config_id = Column(Integer, nullable=False, index=True)  # 关联配置ID
    farm_code = Column(String(50), nullable=False)  # 场站编码
    report_type = Column(String(50), nullable=False)  # 上报类型
    report_time = Column(DateTime, nullable=False, default=datetime.now)  # 上报时间
    data_count = Column(Integer, nullable=False, default=0)  # 上报数据条数
    data_completeness_rate = Column(Float, nullable=True, default=None)  # 数据完整率 (0-1)
    status = Column(String(20), nullable=False)  # 状态: success, failed, timeout
    response_code = Column(Integer, nullable=True)  # 响应状态码
    response_message = Column(Text, nullable=True)  # 响应消息
    error_message = Column(Text, nullable=True)  # 错误信息
    execution_time = Column(Float, nullable=True)  # 执行时间（秒）
    created_at = Column(DateTime, default=datetime.now)

class ReportQualityStatistics(Base):
    """上报数据质量统计模型 - 按类型分别统计"""
    __tablename__ = "report_quality_statistics"
    
    id = Column(Integer, primary_key=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    report_type = Column(String(50), nullable=False, index=True)  # 上报类型: 'actual', 'forecast_short', 'forecast_long'
    date = Column(String(10), nullable=False, index=True)  # 统计日期 (YYYY-MM-DD)
    completeness_rate = Column(Float, nullable=False, default=0.0)  # 数据完整率 (0-100)
    timeliness_rate = Column(Float, nullable=False, default=0.0)  # 上报及时率 (0-100)
    total_reports = Column(Integer, nullable=False, default=0)  # 当日总上报次数
    completed_reports = Column(Integer, nullable=False, default=0)  # 完整数据上报次数（兼容字段）
    on_time_reports = Column(Integer, nullable=False, default=0)  # 及时上报次数
    notes = Column(Text, nullable=True)  # 备注信息
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now) 


class DataQualityMarker(Base):
    __tablename__ = "data_quality_markers"

    id = Column(Integer, primary_key=True)
    farm_code = Column(String(50), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    marker_type = Column(String(100), nullable=False)
    reason = Column(Text, nullable=True)
    exclude_from_score = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
