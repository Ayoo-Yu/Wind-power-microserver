from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models.data_lineage import SourceObservation
from db_models.forecast_trace import ForecastOutputPoint
from db_models.operational_data import AvailablePowerData, TurbinePowerData
from db_models.power import ActualPower, MidPower, ShortlPower, SupershortlPower
from db_models.training import DailyMetrics
from services.regulatory_evaluation_service import (
    SOUTH_GRID_OPERATIONAL_POLICY_VERSION,
    calculate_south_grid_daily_metrics,
    evaluate_regulatory_day,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    for table in (
        ActualPower.__table__,
        SourceObservation.__table__,
        AvailablePowerData.__table__,
        TurbinePowerData.__table__,
        ShortlPower.__table__,
        MidPower.__table__,
        SupershortlPower.__table__,
        ForecastOutputPoint.__table__,
        DailyMetrics.__table__,
    ):
        table.create(engine)
    return sessionmaker(bind=engine)(), engine


def test_south_grid_formula_uses_pointwise_twenty_percent_floor():
    points = [{"actual_power": 10.0, "predicted_power": 0.0} for _ in range(96)]

    result = calculate_south_grid_daily_metrics(
        points,
        capacity_mw=100.0,
        threshold_percent=60.0,
    )

    assert result["status"] == "complete"
    assert result["accuracy_percent"] == pytest.approx(50.0)
    assert result["qualified"] is False
    assert result["deficit_percentage_points"] == 10
    assert result["assessment_energy_mwh"] == pytest.approx(200.0)


def test_low_power_points_are_excluded_without_creating_missing_data_alarm():
    points = [{
        "actual_power": 5.0,
        "predicted_power": 5.0,
        "available_power": 5.0,
    } for _ in range(96)]

    result = calculate_south_grid_daily_metrics(
        points,
        capacity_mw=100.0,
        threshold_percent=60.0,
    )

    assert result["status"] == "excluded"
    assert result["excluded_count"] == 96
    assert result["completeness"] == 1.0
    assert result["qualified"] is None


def test_supershort_assessment_averages_horizons_one_to_sixteen_for_each_target():
    session, engine = _session()
    target_day = date(2026, 7, 15)
    start = datetime(2026, 7, 15)
    try:
        for point_index in range(96):
            target = start + timedelta(minutes=15 * point_index)
            session.add(ActualPower(timestamp=target, farm_code="WF001", wp_true=51.0))
            for horizon in range(1, 17):
                session.add(ForecastOutputPoint(
                    prediction_run_id=point_index * 16 + horizon,
                    farm_code="WF001",
                    forecast_type="supershort",
                    issued_at=target - timedelta(minutes=15 * horizon),
                    target_time=target,
                    horizon_index=horizon,
                    horizon_minutes=15 * horizon,
                    predicted_power=42.5 + horizon,
                ))
        session.flush()

        result = evaluate_regulatory_day(
            session,
            farm_code="WF001",
            forecast_type="supershort",
            day=target_day,
            capacity_mw=100.0,
        )

        assert result["status"] == "complete"
        assert result["accuracy_percent"] == pytest.approx(100.0)
        assert result["selection"]["aggregation"] == "mean_horizons_1_16"
        assert result["selection"]["complete_horizon_target_count"] == 96
        assert result["selection"]["mean_horizon_count"] == 16
    finally:
        session.close()
        engine.dispose()


def test_supershort_assessment_keeps_incomplete_horizon_sets_provisional():
    session, engine = _session()
    target_day = date(2026, 7, 15)
    start = datetime(2026, 7, 15)
    try:
        for point_index in range(96):
            target = start + timedelta(minutes=15 * point_index)
            session.add(ActualPower(timestamp=target, farm_code="WF001", wp_true=50.0))
            for horizon in range(1, 16):
                session.add(ForecastOutputPoint(
                    prediction_run_id=point_index * 16 + horizon,
                    farm_code="WF001",
                    forecast_type="supershort",
                    issued_at=target - timedelta(minutes=15 * horizon),
                    target_time=target,
                    horizon_index=horizon,
                    horizon_minutes=15 * horizon,
                    predicted_power=50.0,
                ))
        session.flush()

        result = evaluate_regulatory_day(
            session,
            farm_code="WF001",
            forecast_type="supershort",
            day=target_day,
            capacity_mw=100.0,
        )

        assert result["status"] == "missing"
        assert result["prediction_point_count"] == 0
        assert result["selection"]["status"] == "partial"
        assert result["selection"]["target_count"] == 96
        assert result["selection"]["complete_horizon_target_count"] == 0
        assert result["selection"]["mean_horizon_count"] == 15
    finally:
        session.close()
        engine.dispose()


def test_mid_assessment_selects_output_issued_three_days_before_target_day_and_persists_policy():
    session, engine = _session()
    target_day = date(2026, 7, 15)
    target_start = datetime(2026, 7, 15)
    issued_at = datetime(2026, 7, 12, 8, 50)
    try:
        for index in range(96):
            target = target_start + timedelta(minutes=15 * index)
            session.add(ActualPower(timestamp=target, farm_code="WF001", wp_true=50.0))
            session.add(ForecastOutputPoint(
                prediction_run_id=500,
                farm_code="WF001",
                forecast_type="mid",
                issued_at=issued_at,
                target_time=target,
                horizon_index=index + 1,
                horizon_minutes=int((target - issued_at).total_seconds() / 60),
                predicted_power=50.0,
            ))
        session.flush()

        result = evaluate_regulatory_day(
            session,
            farm_code="WF001",
            forecast_type="mid",
            day=target_day,
            capacity_mw=100.0,
            persist=True,
        )

        stored = session.query(DailyMetrics).one()
        assert result["status"] == "complete"
        assert result["accuracy_percent"] == pytest.approx(100.0)
        assert result["selection"]["prediction_run_id"] == 500
        assert stored.policy_version == SOUTH_GRID_OPERATIONAL_POLICY_VERSION
        assert stored.status == "complete"
        assert stored.expected_count == 96
    finally:
        session.close()
        engine.dispose()


def test_daily_assessment_fills_partial_actual_power_from_turbine_sum():
    session, engine = _session()
    target_day = date(2026, 7, 15)
    target_start = datetime(2026, 7, 15)
    issued_at = datetime(2026, 7, 14, 8, 50)
    try:
        for index in range(96):
            target = target_start + timedelta(minutes=15 * index)
            if index % 2 == 0:
                session.add(ActualPower(
                    timestamp=target,
                    farm_code="WF001",
                    wp_true=50.0,
                ))
            else:
                session.add(TurbinePowerData(
                    timestamp=target,
                    turbine_id="T01",
                    farm_code="WF001",
                    active_power=50000.0,
                ))
            session.add(ForecastOutputPoint(
                prediction_run_id=700,
                farm_code="WF001",
                forecast_type="short",
                issued_at=issued_at,
                target_time=target,
                horizon_index=index + 1,
                horizon_minutes=index * 15,
                predicted_power=50.0,
            ))
        session.flush()

        result = evaluate_regulatory_day(
            session,
            farm_code="WF001",
            forecast_type="short",
            day=target_day,
            capacity_mw=100.0,
        )

        assert result["status"] == "complete"
        assert result["accuracy_percent"] == pytest.approx(100.0)
        assert result["actual_source"] == "mixed"
        assert result["actual_source_counts"] == {
            "actual_power": 48,
            "turbine_power_sum": 48,
        }
    finally:
        session.close()
        engine.dispose()
