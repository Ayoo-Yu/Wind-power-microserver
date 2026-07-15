from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, Text

from .base import Base


class ReportConfigMeta(Base):
    __tablename__ = 'report_config_meta'

    id = Column(Integer, primary_key=True)
    config_id = Column(Integer, nullable=False, unique=True, index=True)
    payload = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
