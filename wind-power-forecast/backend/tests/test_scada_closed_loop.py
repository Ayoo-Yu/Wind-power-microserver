import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models.power import ActualPower
from db_models.data_lineage import SourceObservation
from db_models.operational_data import (
    AvailableCapacityData,
    AvailablePowerData,
    TheoreticalPowerData,
    WeatherData,
)
from db_models.prediction_task import PredictionTask
from db_models.report_config import ReportConfig, WindFarm
from db_models.report_outbox import ReportOutbox
from db_models.scada_connection import ScadaConnection
from db_models.scada_ingest_record import ScadaIngestRecord
from services.scada_health_service import (
    assess_connection_health,
    build_scada_health_snapshot,
)
from services.scada_ingest_service import ScadaIngestError, ingest_scada_sample


TABLES = [
    WindFarm.__table__,
    ScadaConnection.__table__,
    ScadaIngestRecord.__table__,
    SourceObservation.__table__,
    ActualPower.__table__,
    WeatherData.__table__,
    TheoreticalPowerData.__table__,
    AvailablePowerData.__table__,
    AvailableCapacityData.__table__,
    PredictionTask.__table__,
    ReportConfig.__table__,
    ReportOutbox.__table__,
]


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    for table in TABLES:
        table.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _connection(session, *, status="running", capacity=48.0):
    farm = WindFarm(
        farm_code="CF",
        farm_name="仓房风电场",
        capacity=capacity,
        is_active=True,
    )
    connection = ScadaConnection(
        farm_code="CF",
        name="仓房 SCADA",
        protocol="c104",
        server_ip="127.0.0.1",
        server_port=2404,
        status=status,
        is_enabled=True,
    )
    session.add_all([farm, connection])
    session.flush()
    return farm, connection


def _payload(connection_id, **overrides):
    payload = {
        "connection_id": connection_id,
        "farm_code": "CF",
        "ioa": 16385,
        "source_timestamp": "2026-07-15T10:00:00+08:00",
        "normalized_timestamp": "2026-07-15T10:00:00+08:00",
        "power_mw": 21.5,
        "quality": "good",
    }
    payload.update(overrides)
    return payload


def test_ingest_creates_trace_and_actual_power(session):
    _farm, connection = _connection(session)
    now = datetime(2026, 7, 15, 10, 0, 5)

    result = ingest_scada_sample(
        session,
        _payload(connection.id),
        {},
        now=now,
    )

    assert result.accepted is True
    assert result.outcome == "created"
    assert session.query(ActualPower).count() == 1
    record = session.query(ScadaIngestRecord).one()
    assert record.actual_power_id == result.actual_power_id
    assert record.quality == "good"
    assert connection.last_data_at == now
    assert connection.last_power_value == 215
    assert session.query(SourceObservation).one().metric == "active_power_mw"


def test_ingest_is_idempotent_and_records_updates(session):
    _farm, connection = _connection(session)
    now = datetime(2026, 7, 15, 10, 0, 5)

    created = ingest_scada_sample(session, _payload(connection.id), {}, now=now)
    duplicate = ingest_scada_sample(
        session, _payload(connection.id), {}, now=now + timedelta(seconds=1)
    )
    updated = ingest_scada_sample(
        session,
        _payload(connection.id, power_mw=22.0),
        {},
        now=now + timedelta(seconds=2),
    )

    assert created.outcome == "created"
    assert duplicate.outcome == "duplicate"
    assert updated.outcome == "updated"
    assert session.query(ActualPower).count() == 1
    assert session.query(ActualPower).one().wp_true == 22.0
    assert session.query(ScadaIngestRecord).count() == 3
    assert session.query(SourceObservation).count() == 2


def test_ingest_projects_all_versioned_scada_metrics(session):
    _farm, connection = _connection(session)
    definitions = {
        16385: ("active_power_mw", "MW", 21.5),
        17385: ("wind_speed_mps", "m/s", 8.2),
        18385: ("theoretical_power_mw", "MW", 25.0),
        19385: ("available_power_mw", "MW", 23.0),
        20385: ("availability_pct", "%", 95.0),
    }
    connection.ioa_points = json.dumps({
        str(ioa): {"type": "M_ME_NC_1", "metric": metric, "unit": unit}
        for ioa, (metric, unit, _value) in definitions.items()
    })
    connection.upload_target_ioa = 16385

    for ioa, (metric, unit, value) in definitions.items():
        result = ingest_scada_sample(
            session,
            _payload(
                connection.id,
                ioa=ioa,
                metric=metric,
                unit=unit,
                value=value,
                power_mw=value if metric == "active_power_mw" else None,
            ),
            {},
            now=datetime(2026, 7, 15, 10, 0, 5),
        )
        assert result.accepted is True

    assert session.query(SourceObservation).count() == 5
    assert session.query(ActualPower).one().wp_true == 21.5
    assert session.query(WeatherData).one().wind_speed_avg == 8.2
    assert session.query(TheoreticalPowerData).one().theoretical_power == 25.0
    assert session.query(AvailablePowerData).one().available_power == 23.0
    availability = session.query(AvailableCapacityData).one()
    assert availability.availability_rate == 95.0
    assert availability.available_capacity == pytest.approx(45.6)


def test_ingest_keeps_raw_observation_without_quarter_write(session):
    _farm, connection = _connection(session)
    result = ingest_scada_sample(
        session,
        _payload(connection.id, normalized_timestamp=None),
        {},
        now=datetime(2026, 7, 15, 10, 7),
    )

    assert result.outcome == "observed"
    assert session.query(ActualPower).count() == 0
    assert session.query(ScadaIngestRecord).one().outcome == "observed"
    assert connection.last_data_at == datetime(2026, 7, 15, 10, 7)


def test_ingest_rejects_off_grid_business_timestamp_but_keeps_audit_record(session):
    _farm, connection = _connection(session)
    result = ingest_scada_sample(
        session,
        _payload(connection.id, normalized_timestamp="2026-07-15T10:07:00+08:00"),
        {},
        now=datetime(2026, 7, 15, 10, 7, 5),
    )

    assert result.accepted is False
    assert result.outcome == "rejected"
    assert "十五分钟边界" in result.message
    assert session.query(ActualPower).count() == 0
    assert session.query(SourceObservation).count() == 0
    assert session.query(ScadaIngestRecord).one().normalized_timestamp == datetime(
        2026, 7, 15, 10, 7
    )


def test_ingest_rejects_bad_quality_without_advancing_last_good_sample(session):
    _farm, connection = _connection(session)
    result = ingest_scada_sample(
        session,
        _payload(connection.id, quality="bad", power_mw=None),
        {},
        now=datetime(2026, 7, 15, 10, 0, 5),
    )

    assert result.accepted is False
    assert result.outcome == "rejected"
    assert connection.last_data_at is None
    assert session.query(ActualPower).count() == 0
    assert session.query(ScadaIngestRecord).one().quality == "bad"


def test_ingest_rejects_connection_farm_mismatch(session):
    _farm, connection = _connection(session)
    with pytest.raises(ScadaIngestError) as exc_info:
        ingest_scada_sample(
            session,
            _payload(connection.id, farm_code="BNJ"),
            {},
        )
    assert exc_info.value.status_code == 409


def test_assess_connection_health_detects_stale_and_bad_latest_sample():
    now = datetime(2026, 7, 15, 10, 10)
    connection = SimpleNamespace(
        status="running",
        is_enabled=True,
        last_data_at=now - timedelta(seconds=10),
        last_error=None,
    )
    healthy = assess_connection_health(
        connection,
        deployment_enabled=True,
        stale_after_seconds=60,
        now=now,
    )
    assert healthy["status"] == "healthy"

    connection.last_data_at = now - timedelta(seconds=61)
    stale = assess_connection_health(
        connection,
        deployment_enabled=True,
        stale_after_seconds=60,
        now=now,
    )
    assert stale["status"] == "stale"

    connection.last_data_at = now - timedelta(seconds=10)
    latest_event = SimpleNamespace(
        outcome="rejected",
        quality="bad",
        message="质量码不可用",
        received_at=now - timedelta(seconds=5),
    )
    degraded = assess_connection_health(
        connection,
        deployment_enabled=True,
        stale_after_seconds=60,
        latest_event=latest_event,
        now=now,
    )
    assert degraded["status"] == "degraded"


def test_health_snapshot_links_ingest_prediction_and_report(session):
    farm, connection = _connection(session)
    now = datetime(2026, 7, 15, 10, 10)
    ingest_scada_sample(
        session,
        _payload(connection.id),
        {},
        now=now - timedelta(seconds=10),
    )
    task = PredictionTask(
        farm_code="CF",
        task_type="supershort",
        enabled=True,
        last_predict_at=now,
        last_predict_status="success",
    )
    report_config = ReportConfig(
        farm_id=farm.id,
        report_type="actual",
        target_ip="127.0.0.1",
        target_port=9000,
        report_interval=15,
        is_enabled=True,
    )
    session.add_all([task, report_config])
    session.flush()

    snapshot = build_scada_health_snapshot(
        session,
        {
            "SCADA_REALTIME_ENABLED": True,
            "SCADA_DATA_STALE_AFTER_SECONDS": 60,
        },
        now=now,
    )

    assert snapshot["availability"] == "available"
    item = snapshot["connections"][0]
    assert item["status"] == "healthy"
    assert item["prediction"]["state"] == "current"
    assert item["report"]["state"] == "idle"
