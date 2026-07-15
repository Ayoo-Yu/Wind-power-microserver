from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models import Base, ReportConfig, ReportLog, ReportOutbox
from services.report_outbox_service import (
    build_report_payload,
    dispatch_one,
    enqueue_report,
    make_idempotency_key,
    recover_stale_processing,
)


class _Response:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


@pytest.fixture()
def database():
    engine = create_engine("sqlite:///:memory:")
    ReportConfig.__table__.create(engine)
    ReportOutbox.__table__.create(engine)
    ReportLog.__table__.create(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session_scope():
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    with session_scope() as session:
        config = ReportConfig(
            id=1,
            farm_id=1,
            report_type="actual",
            target_ip="127.0.0.1",
            target_port=9000,
            report_interval=15,
            timeout_seconds=3,
            retry_count=2,
        )
        session.add(config)
    return session_scope


def _enqueue(session_scope, logical_time=None):
    logical_time = logical_time or datetime(2026, 7, 15, 8, 15)
    with session_scope() as session:
        config = session.query(ReportConfig).filter_by(id=1).one()
        payload = build_report_payload(config, [{"power": 12.5}], "CF")
        key = make_idempotency_key(
            config_id=config.id,
            farm_code="CF",
            report_type=config.report_type,
            logical_time=logical_time,
        )
        return enqueue_report(
            session,
            config=config,
            farm_code="CF",
            payload=payload,
            idempotency_key=key,
            data_completeness_rate=1.0,
            is_on_time=True,
        )


def test_enqueue_is_idempotent(database):
    first = _enqueue(database)
    second = _enqueue(database)

    assert first.created is True
    assert second.created is False
    assert first.outbox_id == second.outbox_id
    with database() as session:
        assert session.query(ReportOutbox).count() == 1


def test_successful_dispatch_marks_sent_and_logs(database):
    queued = _enqueue(database)
    sent_headers = {}

    def sender(url, data, headers, timeout):
        sent_headers.update(headers)
        return _Response(200, "accepted")

    result = dispatch_one(database, outbox_id=queued.outbox_id, sender=sender)

    assert result.status == "sent"
    assert sent_headers["Idempotency-Key"] == queued.idempotency_key
    with database() as session:
        row = session.query(ReportOutbox).one()
        assert row.status == "sent"
        assert row.attempt_count == 1
        assert session.query(ReportLog).filter_by(status="success").count() == 1


def test_retryable_http_failure_is_retried_then_sent(database):
    queued = _enqueue(database)
    first = dispatch_one(
        database,
        outbox_id=queued.outbox_id,
        sender=lambda url, **kwargs: _Response(503, "maintenance"),
        retry_base_seconds=0,
        retry_max_seconds=0,
    )
    second = dispatch_one(
        database,
        outbox_id=queued.outbox_id,
        sender=lambda url, **kwargs: _Response(201, "accepted"),
    )

    assert first.status == "retry"
    assert second.status == "sent"
    assert second.attempt_count == 2


def test_client_error_goes_to_dead_letter(database):
    queued = _enqueue(database)
    result = dispatch_one(
        database,
        outbox_id=queued.outbox_id,
        sender=lambda url, **kwargs: _Response(400, "invalid payload"),
    )

    assert result.status == "dead"
    with database() as session:
        assert session.query(ReportOutbox).one().status == "dead"
        assert session.query(ReportLog).filter_by(status="failed").count() == 1


def test_transport_exception_keeps_payload_for_retry(database):
    queued = _enqueue(database)

    def sender(url, **kwargs):
        raise ConnectionError("network partition")

    result = dispatch_one(
        database,
        outbox_id=queued.outbox_id,
        sender=sender,
        retry_base_seconds=0,
        retry_max_seconds=0,
    )

    assert result.status == "retry"
    with database() as session:
        row = session.query(ReportOutbox).one()
        assert row.payload_json
        assert row.last_error == "network partition"


def test_stale_processing_is_recovered(database):
    queued = _enqueue(database)
    with database() as session:
        row = session.query(ReportOutbox).filter_by(id=queued.outbox_id).one()
        row.status = "processing"
        row.attempt_count = 1
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        row.locked_at = now - timedelta(minutes=10)

    result = recover_stale_processing(database, stale_after_seconds=300)

    assert result == {"recovered": 1, "dead": 0}
    with database() as session:
        assert session.query(ReportOutbox).one().status == "retry"


def test_corrupted_persisted_payload_is_quarantined_without_network_send(database):
    queued = _enqueue(database)
    with database() as session:
        row = session.query(ReportOutbox).filter_by(id=queued.outbox_id).one()
        row.payload_json = '{"tampered":true}'
    calls = []

    result = dispatch_one(
        database,
        outbox_id=queued.outbox_id,
        sender=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert result.status == "dead"
    assert calls == []
    assert "完整性校验失败" in result.error


def test_late_failure_does_not_overwrite_terminal_state(database):
    queued = _enqueue(database)

    def sender(url, **kwargs):
        with database() as session:
            row = session.query(ReportOutbox).filter_by(id=queued.outbox_id).one()
            row.status = "sent"
            row.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
            row.locked_at = None
            row.locked_by = None
        raise ConnectionError("late network error")

    result = dispatch_one(database, outbox_id=queued.outbox_id, sender=sender)

    assert result.status == "sent"
    with database() as session:
        row = session.query(ReportOutbox).one()
        assert row.status == "sent"
        assert row.last_error is None
