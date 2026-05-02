from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from .base import Base


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("prediction_tasks.id"), index=True)
    celery_task_id = Column(String(100))
    action = Column(String(20))
    status = Column(String(20))
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration_sec = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
