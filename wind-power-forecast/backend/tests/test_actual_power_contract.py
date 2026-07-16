from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models.data_lineage import SourceObservation
from db_models.operational_data import TurbinePowerData
from db_models.power import ActualPower
from routes.report_management_router import get_actual_power_data
from services.actual_power_service import (
    ActualPowerContractError,
    load_canonical_actual_power,
    parse_actual_power_value,
    quarter_hour_grid,
    require_quarter_hour,
    turbine_power_to_mw,
)
from services.import_job_service import _prepare_actual_power_chunk


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    for table in (
        ActualPower.__table__,
        SourceObservation.__table__,
        TurbinePowerData.__table__,
    ):
        table.create(engine)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _observation(event_time: datetime, value: float, key: str) -> SourceObservation:
    return SourceObservation(
        observation_key=key,
        source_type="scada",
        source_id="scada.connection.1",
        farm_code="WF001",
        metric="active_power_mw",
        event_time=event_time,
        received_at=event_time,
        value=value,
        unit="MW",
        quality="good",
        schema_version="scada-point-v2",
    )


def test_timestamp_contract_converts_offset_and_requires_quarter_boundary():
    utc_value = datetime(2026, 7, 15, 2, 15, tzinfo=timezone.utc)

    assert require_quarter_hour(utc_value) == datetime(2026, 7, 15, 10, 15)
    assert require_quarter_hour("2026-07-15T10:30:00+08:00") == datetime(
        2026, 7, 15, 10, 30
    )

    with pytest.raises(ActualPowerContractError, match="十五分钟边界"):
        require_quarter_hour("2026-07-15T10:07:00+08:00")
    with pytest.raises(ActualPowerContractError, match="十五分钟边界"):
        require_quarter_hour("2026-07-15T10:15:01+08:00")


def test_quarter_grid_is_left_closed_and_right_open():
    assert quarter_hour_grid(
        datetime(2026, 7, 15, 10, 7),
        datetime(2026, 7, 15, 11, 0),
    ) == (
        datetime(2026, 7, 15, 10, 15),
        datetime(2026, 7, 15, 10, 30),
        datetime(2026, 7, 15, 10, 45),
    )


def test_power_value_contract_rejects_infinite_values():
    assert parse_actual_power_value("12.5") == 12.5
    assert parse_actual_power_value("NaN") is None
    assert parse_actual_power_value(None) is None

    with pytest.raises(ActualPowerContractError, match="有限数值"):
        parse_actual_power_value(float("inf"))


def test_canonical_series_fills_each_missing_point_by_declared_priority(session):
    start = datetime(2026, 7, 15, 0, 0)
    session.add_all([
        ActualPower(timestamp=start, farm_code="WF001", wp_true=10.0),
        ActualPower(
            timestamp=start + timedelta(minutes=7),
            farm_code="WF001",
            wp_true=999.0,
        ),
        _observation(start + timedelta(minutes=14), 20.0, "obs-1"),
        TurbinePowerData(
            timestamp=start + timedelta(minutes=30),
            turbine_id="T01",
            farm_code="WF001",
            active_power=10000.0,
        ),
        TurbinePowerData(
            timestamp=start + timedelta(minutes=30),
            turbine_id="T02",
            farm_code="WF001",
            active_power=20000.0,
        ),
        TurbinePowerData(
            timestamp=start + timedelta(minutes=30),
            turbine_id="T01",
            farm_code="WF001",
            active_power=12000.0,
        ),
    ])
    session.flush()

    series = load_canonical_actual_power(
        session,
        "WF001",
        start,
        start + timedelta(hours=1),
    )

    assert series.values == {
        start: 10.0,
        start + timedelta(minutes=15): 20.0,
        start + timedelta(minutes=30): 32.0,
    }
    assert series.sources == {
        start: "actual_power",
        start + timedelta(minutes=15): "source_observations",
        start + timedelta(minutes=30): "turbine_power_sum",
    }
    assert series.source_label == "mixed"
    assert series.source_counts == {
        "actual_power": 1,
        "source_observations": 1,
        "turbine_power_sum": 1,
    }
    assert series.missing_count == 1
    assert series.ignored_off_grid_count == 1


def test_raw_scada_fallback_is_causal_and_does_not_reuse_expired_sample(session):
    start = datetime(2026, 7, 15, 10, 0)
    session.add_all([
        _observation(start + timedelta(minutes=1), 11.0, "obs-after-first-target"),
        _observation(start + timedelta(minutes=14), 12.0, "obs-before-second-target"),
    ])
    session.flush()

    series = load_canonical_actual_power(
        session,
        "WF001",
        start,
        start + timedelta(minutes=45),
    )

    assert start not in series.values
    assert series.values[start + timedelta(minutes=15)] == 12.0
    assert start + timedelta(minutes=30) not in series.values


def test_report_actual_power_uses_exact_target_without_stale_relabeling(session):
    target = datetime(2026, 7, 15, 10, 15)
    session.add_all([
        ActualPower(
            timestamp=target - timedelta(minutes=15),
            farm_code="WF001",
            wp_true=9.0,
        ),
        TurbinePowerData(
            timestamp=target,
            turbine_id="T01",
            farm_code="WF001",
            active_power=12000.0,
        ),
    ])
    session.flush()

    current = get_actual_power_data(
        session,
        target + timedelta(minutes=5),
        "WF001",
    )
    missing_next_point = get_actual_power_data(
        session,
        target + timedelta(minutes=20),
        "WF001",
    )

    assert current == [{
        "time": target.isoformat(),
        "value": 12.0,
        "wp_true": 12.0,
        "actual_timestamp": target.isoformat(),
        "data_source": "database",
        "actual_source": "turbine_power_sum",
    }]
    assert missing_next_point == []


def test_turbine_power_unit_is_explicit(monkeypatch):
    monkeypatch.setenv("ACTUAL_POWER_TURBINE_SOURCE_UNIT", "kW")
    assert turbine_power_to_mw(12500.0) == 12.5

    monkeypatch.setenv("ACTUAL_POWER_TURBINE_SOURCE_UNIT", "MW")
    assert turbine_power_to_mw(12.5) == 12.5

    monkeypatch.setenv("ACTUAL_POWER_TURBINE_SOURCE_UNIT", "W")
    with pytest.raises(ActualPowerContractError, match="kW 或 MW"):
        turbine_power_to_mw(12.5)


def test_async_import_normalizes_timezone_and_rejects_off_grid_rows():
    frame = pd.DataFrame({
        "Timestamp": [
            "2026-07-15T02:15:00Z",
            "2026-07-15T10:07:00+08:00",
            "2026-07-15T10:30:00+08:00",
        ],
        "wp_true": [10.0, 20.0, float("inf")],
    })

    prepared, invalid_count, duplicate_count = _prepare_actual_power_chunk(
        frame,
        "WF001",
    )

    assert invalid_count == 2
    assert duplicate_count == 0
    assert prepared["timestamp"].tolist() == [
        datetime(2026, 7, 15, 10, 15),
    ]
    assert prepared.iloc[0]["wp_true"] == 10.0


def test_async_import_keeps_blank_as_skipped_candidate_and_rejects_bad_number():
    frame = pd.DataFrame({
        "timestamp": [
            "2026-07-15T10:00:00+08:00",
            "2026-07-15T10:15:00+08:00",
        ],
        "wp_true": [None, "invalid"],
    })

    prepared, invalid_count, duplicate_count = _prepare_actual_power_chunk(
        frame,
        "WF001",
    )

    assert invalid_count == 1
    assert duplicate_count == 0
    assert len(prepared) == 1
    assert prepared.iloc[0]["timestamp"] == datetime(2026, 7, 15, 10, 0)
    assert pd.isna(prepared.iloc[0]["wp_true"])


def test_async_import_deduplicates_by_normalized_business_time():
    frame = pd.DataFrame({
        "timestamp": [
            "2026-07-15T02:15:00Z",
            "2026-07-15T10:15:00+08:00",
        ],
        "wp_true": [10.0, 11.0],
    })

    prepared, invalid_count, duplicate_count = _prepare_actual_power_chunk(
        frame,
        "WF001",
    )

    assert invalid_count == 0
    assert duplicate_count == 1
    assert len(prepared) == 1
    assert prepared.iloc[0]["wp_true"] == 11.0
