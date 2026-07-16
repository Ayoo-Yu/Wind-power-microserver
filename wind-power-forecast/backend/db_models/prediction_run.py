from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from datetime import datetime
from .base import Base


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    __table_args__ = (
        UniqueConstraint(
            "celery_task_id",
            name="uq_prediction_runs_celery_task_id",
        ),
        Index(
            "uq_prediction_runs_active_task",
            "task_id",
            unique=True,
            postgresql_where=text(
                "status IN ('queued', 'running') AND task_id IS NOT NULL"
            ),
            sqlite_where=text(
                "status IN ('queued', 'running') AND task_id IS NOT NULL"
            ),
        ),
        Index(
            "ix_prediction_runs_task_action_status",
            "task_id",
            "action",
            "status",
        ),
        Index("ix_prediction_runs_request_id", "request_id"),
    )

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("prediction_tasks.id"), index=True)
    celery_task_id = Column(String(100))
    action = Column(String(20))
    status = Column(String(20))
    requested_by = Column(String(100))
    trigger_source = Column(String(32), nullable=False, default="legacy")
    request_id = Column(String(100))
    attempt_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime)
    last_heartbeat_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration_sec = Column(Integer)
    error_message = Column(Text)
    result_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
