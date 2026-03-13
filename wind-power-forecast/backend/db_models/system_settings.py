from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime

from .base import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    settings_key = Column(String(100), nullable=False, unique=True, index=True)
    payload = Column(Text, nullable=False)
    updated_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
