from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, UniqueConstraint
from datetime import datetime, timezone
from .base import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PredictionTask(Base):
    __tablename__ = "prediction_tasks"
    __table_args__ = (
        UniqueConstraint("farm_code", "task_type", name="uq_prediction_tasks_farm_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    farm_code = Column(String(50), nullable=False, index=True)
    task_type = Column(String(20), nullable=False)
    enabled = Column(Boolean, default=False)
    train_schedule = Column(String(20))
    train_day_of_week = Column(String(20))
    predict_schedule = Column(String(100))
    calibrate_schedule = Column(String(20))
    last_train_at = Column(DateTime)
    last_predict_at = Column(DateTime)
    last_train_status = Column(String(20))
    last_predict_status = Column(String(20))
    last_error = Column(Text)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
