"""SQLAlchemy model for storing autopredict scheduling configuration."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint

from db_models.base import Base


class AutopredictJobConfig(Base):
    __tablename__ = "autopredict_job_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(32), nullable=False, index=True)
    wind_farm_code = Column(String(64), nullable=False, index=True)
    enabled = Column(Boolean, default=False, nullable=False)
    schedule_cron = Column(String(64), nullable=True)
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("task_type", "wind_farm_code", name="uq_autopredict_job"),
    )


__all__ = ["AutopredictJobConfig"]


