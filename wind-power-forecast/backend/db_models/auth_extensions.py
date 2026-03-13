from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base


class UserProfileMeta(Base):
    __tablename__ = "user_profile_meta"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    phone = Column(String(50), nullable=True)
    stations = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User")


class OperationAuditLog(Base):
    __tablename__ = "operation_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    operation_time = Column(DateTime, default=datetime.now, index=True)
    operator = Column(String(100), nullable=False, index=True)
    ip_address = Column(String(50), nullable=True)
    module = Column(String(100), nullable=False, index=True)
    operation_type = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    result = Column(String(50), nullable=False, default="成功")
    created_at = Column(DateTime, default=datetime.now)
