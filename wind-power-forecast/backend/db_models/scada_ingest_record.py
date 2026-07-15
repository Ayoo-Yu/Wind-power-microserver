"""SCADA 采集审计记录。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from .base import Base


class ScadaIngestRecord(Base):
    """保存 SCADA 样本的来源、质量和落库结果。"""

    __tablename__ = "scada_ingest_records"

    id = Column(Integer, primary_key=True)
    connection_id = Column(Integer, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)
    ioa = Column(Integer, nullable=True)
    metric = Column(String(64), nullable=False, default="active_power_mw", index=True)
    value = Column(Float, nullable=True)
    unit = Column(String(24), nullable=True)
    source_id = Column(String(128), nullable=True)
    source_timestamp = Column(DateTime, nullable=True, index=True)
    normalized_timestamp = Column(DateTime, nullable=True, index=True)
    received_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    power_mw = Column(Float, nullable=True)
    quality = Column(String(20), nullable=False, default="unknown", index=True)
    outcome = Column(String(20), nullable=False, index=True)
    message = Column(Text, nullable=True)
    actual_power_id = Column(Integer, nullable=True, index=True)
    observation_id = Column(Integer, nullable=True, index=True)
