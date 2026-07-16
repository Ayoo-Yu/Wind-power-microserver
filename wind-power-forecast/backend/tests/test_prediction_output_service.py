from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models.forecast_trace import ForecastOutputPoint
from services.prediction_output_service import record_forecast_output_points


def _session():
    engine = create_engine("sqlite:///:memory:")
    ForecastOutputPoint.__table__.create(engine)
    return sessionmaker(bind=engine)(), engine


def _points(issued_at, count):
    return [{
        "target_time": issued_at + timedelta(minutes=15 * index),
        "horizon_index": index,
        "horizon_minutes": 15 * index,
        "predicted_power": 20.0 + index,
        "raw_predicted_power": 19.5 + index,
    } for index in range(1, count + 1)]


def test_output_ledger_is_idempotent_and_hashes_exact_points():
    session, engine = _session()
    issued_at = datetime(2026, 7, 16, 10, 0)
    try:
        manifest = record_forecast_output_points(
            session,
            prediction_run_id=101,
            input_snapshot_id=11,
            model_version_id=7,
            farm_code="WF001",
            forecast_type="supershort",
            issued_at=issued_at,
            expected_count=16,
            points=_points(issued_at, 16),
        )
        repeated = record_forecast_output_points(
            session,
            prediction_run_id=101,
            input_snapshot_id=11,
            model_version_id=7,
            farm_code="WF001",
            forecast_type="supershort",
            issued_at=issued_at,
            expected_count=16,
            points=_points(issued_at, 16),
        )

        assert manifest["status"] == "complete"
        assert manifest["record_count"] == 16
        assert manifest["regulatory_delivery_ready"] is True
        assert len(manifest["output_sha256"]) == 64
        assert repeated["output_sha256"] == manifest["output_sha256"]
        assert session.query(ForecastOutputPoint).count() == 16
    finally:
        session.close()
        engine.dispose()


def test_output_ledger_rejects_changed_content_for_same_run():
    session, engine = _session()
    issued_at = datetime(2026, 7, 16, 10, 0)
    try:
        points = _points(issued_at, 2)
        record_forecast_output_points(
            session,
            prediction_run_id=102,
            input_snapshot_id=None,
            model_version_id=None,
            farm_code="WF001",
            forecast_type="short",
            issued_at=issued_at,
            expected_count=2,
            points=points,
        )
        changed = _points(issued_at, 2)
        changed[1]["predicted_power"] = 999.0
        with pytest.raises(ValueError, match="不同内容"):
            record_forecast_output_points(
                session,
                prediction_run_id=102,
                input_snapshot_id=None,
                model_version_id=None,
                farm_code="WF001",
                forecast_type="short",
                issued_at=issued_at,
                expected_count=2,
                points=changed,
            )
    finally:
        session.close()
        engine.dispose()


def test_current_mid_run_is_traced_but_not_marked_240_hour_ready():
    session, engine = _session()
    issued_at = datetime(2026, 7, 16, 8, 50)
    try:
        manifest = record_forecast_output_points(
            session,
            prediction_run_id=103,
            input_snapshot_id=12,
            model_version_id=8,
            farm_code="WF001",
            forecast_type="mid",
            issued_at=issued_at,
            expected_count=96,
            points=_points(issued_at, 96),
        )

        assert manifest["status"] == "complete"
        assert manifest["delivery_expected_count"] == 960
        assert manifest["regulatory_delivery_ready"] is False
    finally:
        session.close()
        engine.dispose()


def test_output_manifest_requires_contiguous_horizons_for_completion():
    session, engine = _session()
    issued_at = datetime(2026, 7, 16, 10, 0)
    try:
        points = _points(issued_at, 2)
        points[1]["horizon_index"] = 3
        manifest = record_forecast_output_points(
            session,
            prediction_run_id=104,
            input_snapshot_id=None,
            model_version_id=None,
            farm_code="WF001",
            forecast_type="supershort",
            issued_at=issued_at,
            expected_count=2,
            points=points,
        )

        assert manifest["record_count"] == 2
        assert manifest["horizon_complete"] is False
        assert manifest["status"] == "partial"
        assert manifest["regulatory_delivery_ready"] is False
    finally:
        session.close()
        engine.dispose()
