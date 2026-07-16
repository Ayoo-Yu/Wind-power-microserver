from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models.prediction_run import PredictionRun
from db_models.prediction_task import PredictionTask
from services.prediction_run_service import (
    PredictionRunConflict,
    PredictionTaskMissing,
    claim_prediction_run,
    finish_prediction_run,
    reserve_prediction_run,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    PredictionTask.__table__.create(engine)
    PredictionRun.__table__.create(engine)
    return sessionmaker(bind=engine)(), engine


def _task(session, farm_code="WF001", task_type="short"):
    task = PredictionTask(
        farm_code=farm_code,
        task_type=task_type,
        enabled=True,
    )
    session.add(task)
    session.flush()
    return task


def test_manual_reservation_is_idempotent_and_rejects_another_active_run():
    session, engine = _session()
    try:
        _task(session)
        first = reserve_prediction_run(
            session,
            farm_code="WF001",
            task_type="short",
            action="predict",
            celery_task_id="manual-1",
            requested_by="operator",
            trigger_source="manual_api",
            request_id="request-1",
        )
        replay = reserve_prediction_run(
            session,
            farm_code="WF001",
            task_type="short",
            action="predict",
            celery_task_id="manual-1",
            requested_by="operator",
            trigger_source="manual_api",
            request_id="request-1",
        )

        assert first.reason == "reserved"
        assert replay.reason == "idempotent_replay"
        assert replay.run_id == first.run_id
        assert session.query(PredictionRun).count() == 1

        try:
            reserve_prediction_run(
                session,
                farm_code="WF001",
                task_type="short",
                action="predict",
                celery_task_id="manual-2",
                requested_by="operator",
                trigger_source="manual_api",
                request_id="request-2",
            )
        except PredictionRunConflict as exc:
            assert exc.active_run_id == first.run_id
        else:
            raise AssertionError("同类排队运行应触发冲突")
    finally:
        session.close()
        engine.dispose()


def test_worker_retry_reuses_run_and_duplicate_delivery_does_not_execute():
    session, engine = _session()
    try:
        _task(session)
        reserved = reserve_prediction_run(
            session,
            farm_code="WF001",
            task_type="short",
            action="predict",
            celery_task_id="celery-1",
            requested_by="operator",
            trigger_source="manual_api",
            request_id="request-1",
        )
        first = claim_prediction_run(
            session,
            farm_code="WF001",
            task_type="short",
            action="predict",
            celery_task_id="celery-1",
            attempt_number=1,
        )
        duplicate = claim_prediction_run(
            session,
            farm_code="WF001",
            task_type="short",
            action="predict",
            celery_task_id="celery-1",
            attempt_number=1,
        )

        assert first.should_execute is True
        assert duplicate.should_execute is False
        assert duplicate.reason == "duplicate_delivery"
        assert first.run_id == reserved.run_id

        assert finish_prediction_run(
            session,
            run_id=first.run_id,
            attempt_number=1,
            status="failed",
            error_message="temporary error",
        ) is True
        retry = claim_prediction_run(
            session,
            farm_code="WF001",
            task_type="short",
            action="predict",
            celery_task_id="celery-1",
            attempt_number=2,
        )
        assert retry.should_execute is True
        assert retry.run_id == first.run_id
        assert session.query(PredictionRun).count() == 1

        assert finish_prediction_run(
            session,
            run_id=retry.run_id,
            attempt_number=2,
            status="success",
            result_data={"points": 96},
        ) is True
        terminal = claim_prediction_run(
            session,
            farm_code="WF001",
            task_type="short",
            action="predict",
            celery_task_id="celery-1",
            attempt_number=3,
        )
        assert terminal.should_execute is False
        assert terminal.reason == "terminal_run"
    finally:
        session.close()
        engine.dispose()


def test_different_worker_delivery_is_recorded_as_skipped_while_run_is_active():
    session, engine = _session()
    try:
        _task(session)
        active = claim_prediction_run(
            session,
            farm_code="WF001",
            task_type="short",
            action="predict",
            celery_task_id="celery-active",
            attempt_number=1,
        )
        skipped = claim_prediction_run(
            session,
            farm_code="WF001",
            task_type="short",
            action="train",
            celery_task_id="celery-duplicate",
            attempt_number=1,
        )

        assert active.should_execute is True
        assert skipped.should_execute is False
        assert skipped.status == "skipped"
        assert skipped.active_run_id == active.run_id
        assert session.query(PredictionRun).count() == 2
    finally:
        session.close()
        engine.dispose()


def test_stale_attempt_cannot_overwrite_newer_attempt_status():
    session, engine = _session()
    try:
        _task(session)
        run = claim_prediction_run(
            session,
            farm_code="WF001",
            task_type="short",
            action="predict",
            celery_task_id="celery-1",
            attempt_number=1,
        )
        row = session.get(PredictionRun, run.run_id)
        row.attempt_count = 2
        session.flush()

        updated = finish_prediction_run(
            session,
            run_id=run.run_id,
            attempt_number=1,
            status="success",
        )

        assert updated is False
        assert row.status == "running"
    finally:
        session.close()
        engine.dispose()


def test_worker_refuses_to_run_without_prediction_task_configuration():
    session, engine = _session()
    try:
        try:
            claim_prediction_run(
                session,
                farm_code="MISSING",
                task_type="short",
                action="predict",
                celery_task_id="celery-missing",
                attempt_number=1,
            )
        except PredictionTaskMissing as exc:
            assert "MISSING/short" in str(exc)
        else:
            raise AssertionError("缺少任务配置时应拒绝执行")
        assert session.query(PredictionRun).count() == 0
    finally:
        session.close()
        engine.dispose()
