"""可靠上报发件箱模型。"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from .base import Base


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReportOutbox(Base):
    """先持久化、后发送的上报任务。"""

    __tablename__ = "report_outbox"

    id = Column(Integer, primary_key=True)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    config_id = Column(Integer, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)
    report_type = Column(String(50), nullable=False, index=True)
    target_url = Column(String(500), nullable=False)
    payload_json = Column(Text, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    headers_json = Column(Text, nullable=False, default="{}")
    timeout_seconds = Column(Integer, nullable=False, default=30)
    data_count = Column(Integer, nullable=False, default=0)
    data_completeness_rate = Column(Float, nullable=True)
    is_on_time = Column(Boolean, nullable=True)

    status = Column(String(20), nullable=False, default="pending", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=4)
    next_attempt_at = Column(DateTime, nullable=True, index=True)
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String(100), nullable=True)

    last_response_code = Column(Integer, nullable=True)
    last_response_body = Column(Text, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )
    sent_at = Column(DateTime, nullable=True)
