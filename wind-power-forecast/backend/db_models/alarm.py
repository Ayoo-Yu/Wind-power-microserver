from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from .base import Base


class AlarmRecord(Base):
    __tablename__ = 'alarm_records'

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, default='system')
    farm_code = Column(String(50), nullable=True, index=True)
    module = Column(String(100), nullable=True)
    level = Column(String(20), nullable=False, default='info', index=True)
    message = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='open', index=True)
    notify_sound = Column(Boolean, nullable=False, default=False)
    notify_sms = Column(Boolean, nullable=False, default=False)
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    closed_by = Column(String(100), nullable=True)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
