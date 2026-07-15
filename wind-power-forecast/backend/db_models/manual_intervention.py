from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from .base import Base


class ManualInterventionVersion(Base):
    __tablename__ = 'manual_intervention_versions'

    id = Column(Integer, primary_key=True)
    config_id = Column(Integer, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)
    report_type = Column(String(50), nullable=False, index=True)
    target_date = Column(String(20), nullable=True, index=True)
    version_name = Column(String(100), nullable=True)
    tool_name = Column(String(50), nullable=True)
    tool_value = Column(String(50), nullable=True)
    payload = Column(Text, nullable=False)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    applied_at = Column(DateTime, nullable=True)
    applied_by = Column(String(100), nullable=True)
