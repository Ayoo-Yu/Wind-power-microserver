from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from datetime import datetime
from .base import Base


class ScadaConnection(Base):
    """SCADA数据源连接配置模型 - 每个场站对应一个C104/HTTP连接"""
    __tablename__ = "scada_connections"

    id = Column(Integer, primary_key=True)
    farm_code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)

    # 连接参数
    protocol = Column(String(20), default='c104')  # c104 | http_poll
    server_ip = Column(String(100), nullable=False)
    server_port = Column(Integer, default=2404)
    casdu_address = Column(Integer, default=1)
    originator_address = Column(Integer, default=0)
    ioa_points = Column(Text)  # JSON: {"1009": "M_ME_NC_1", "16385": "M_ME_NC_1"}
    upload_target_ioa = Column(Integer, nullable=True)
    point_catalog_version = Column(String(32), nullable=False, default='scada-point-v1')
    fetch_interval = Column(Integer, default=60)  # seconds

    # HTTP polling specific
    poll_url = Column(String(500), nullable=True)  # For http_poll mode

    # 运行状态
    is_enabled = Column(Boolean, default=True)
    status = Column(String(20), default='stopped')  # stopped | running | error | connecting
    status_message = Column(Text, nullable=True)
    last_data_at = Column(DateTime, nullable=True)
    last_power_value = Column(Integer, nullable=True)  # Latest power value * 10 (MW*10)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
