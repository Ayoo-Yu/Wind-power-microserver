from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from .base import Base


class FarmProfileConfig(Base):
    __tablename__ = 'farm_profile_configs'

    id = Column(Integer, primary_key=True, index=True)
    farm_code = Column(String(50), nullable=False, unique=True, index=True)
    payload = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
