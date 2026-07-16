"""南方区域风电功率预测日评估服务。"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from statistics import mean

from db_models.forecast_trace import ForecastOutputPoint
from db_models.operational_data import AvailablePowerData
from db_models.power import MidPower, ShortlPower, SupershortlPower
from db_models.training import DailyMetrics
from services.actual_power_service import load_canonical_actual_power


SOUTH_GRID_DOCUMENT_POLICY_VERSION = "south-grid-2022"
SOUTH_GRID_OPERATIONAL_POLICY_VERSION = "south-grid-2022-ultrashort-mean-1-16-actual-source-v2"
EXPECTED_DAILY_POINTS = 96
SUPPORTED_FORECAST_TYPES = ("short", "mid", "supershort")

POLICY = {
    "version": SOUTH_GRID_OPERATIONAL_POLICY_VERSION,
    "document_version": SOUTH_GRID_DOCUMENT_POLICY_VERSION,
    "time_resolution_minutes": 15,
    "expected_daily_points": EXPECTED_DAILY_POINTS,
    "low_power_exclusion_ratio": 0.10,
    "normalisation_floor_ratio": 0.20,
    "forecast_types": {
        "short": {
            "label": "短期日前",
            "target_day_offset": 1,
            "threshold_percent": 60.0,
            "assessment_coefficient": 1.0,
            "selection": "目标日前一日生成的最新完整预测",
        },
        "mid": {
            "label": "中期第 4 日",
            "target_day_offset": 3,
            "target_hours": "73-96",
            "threshold_percent": 40.0,
            "assessment_coefficient": 1.0,
            "selection": "目标日前三日生成的第 4 日预测",
        },
        "supershort": {
            "label": "超短期 1 至 16 提前量均值",
            "threshold_percent": 65.0,
            "assessment_coefficient": 1.0,
            "selection": "同一目标时刻的 1 至 16 个提前量预测均值",
        },
    },
}


def _finite(value) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def calculate_south_grid_daily_metrics(
    points: list[dict],
    *,
    capacity_mw: float,
    threshold_percent: float,
    assessment_coefficient: float = 1.0,
    expected_count: int = EXPECTED_DAILY_POINTS,
) -> dict:
    """按南方区域分段归一化公式计算单日准确率。"""

    capacity = float(capacity_mw)
    if not math.isfinite(capacity) or capacity <= 0:
        raise ValueError("装机容量必须为大于 0 的有限数值")
    if expected_count <= 0:
        raise ValueError("期望点数必须大于 0")

    floor = capacity * POLICY["normalisation_floor_ratio"]
    exclusion_limit = capacity * POLICY["low_power_exclusion_ratio"]
    squared_normalised_errors = []
    squared_errors = []
    absolute_errors = []
    excluded_count = 0
    reference_source_counts = {"actual": 0, "available": 0}

    for point in points:
        actual = _finite(point.get("actual_power"))
        predicted = _finite(point.get("predicted_power"))
        available = _finite(point.get("available_power"))
        if actual is None or predicted is None:
            continue
        if (
            available is not None
            and actual < exclusion_limit
            and predicted < exclusion_limit
            and available < exclusion_limit
        ):
            excluded_count += 1
            continue

        use_available = bool(point.get("curtailed")) and available is not None
        reference = available if use_available else actual
        reference_source_counts["available" if use_available else "actual"] += 1
        denominator = max(reference, floor)
        error = predicted - reference
        squared_normalised_errors.append((error / denominator) ** 2)
        squared_errors.append(error ** 2)
        absolute_errors.append(abs(error))

    sample_count = len(squared_errors)
    covered_count = sample_count + excluded_count
    completeness = min(1.0, covered_count / expected_count)
    if sample_count == 0:
        status = "excluded" if covered_count >= expected_count else "missing"
        accuracy_percent = None
        rmse = None
        mse = None
        mae = None
    else:
        status = "complete" if covered_count >= expected_count else "partial"
        normalised_rmse = math.sqrt(sum(squared_normalised_errors) / sample_count)
        accuracy_percent = (1.0 - normalised_rmse) * 100.0
        mse = sum(squared_errors) / sample_count
        rmse = math.sqrt(mse)
        mae = sum(absolute_errors) / sample_count

    qualified = (
        accuracy_percent >= threshold_percent
        if status == "complete" and accuracy_percent is not None
        else None
    )
    if qualified is None:
        deficit_percentage_points = None
        assessment_energy_mwh = None
    else:
        deficit = max(0.0, threshold_percent - accuracy_percent)
        deficit_percentage_points = int(math.ceil(max(0.0, deficit - 1e-12)))
        assessment_energy_mwh = (
            deficit_percentage_points
            * capacity
            * 0.2
            * float(assessment_coefficient)
        )

    return {
        "status": status,
        "expected_count": expected_count,
        "sample_count": sample_count,
        "covered_count": covered_count,
        "excluded_count": excluded_count,
        "completeness": completeness,
        "accuracy_percent": accuracy_percent,
        "threshold_percent": float(threshold_percent),
        "qualified": qualified,
        "mse": mse,
        "rmse": rmse,
        "mae": mae,
        "deficit_percentage_points": deficit_percentage_points,
        "assessment_energy_mwh": assessment_energy_mwh,
        "reference_source_counts": reference_source_counts,
    }


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min)
    return start, start + timedelta(days=1)


def _expected_timestamps(day: date) -> list[datetime]:
    start, _ = _day_bounds(day)
    return [start + timedelta(minutes=15 * index) for index in range(EXPECTED_DAILY_POINTS)]


def _load_actual_map(
    session,
    farm_code: str,
    start: datetime,
    end: datetime,
) -> tuple[dict, str, dict[str, int], int]:
    series = load_canonical_actual_power(session, farm_code, start, end)
    return (
        series.values,
        series.source_label,
        series.source_counts,
        series.ignored_off_grid_count,
    )


def _load_available_map(session, farm_code: str, start: datetime, end: datetime) -> dict:
    rows = session.query(AvailablePowerData).filter(
        AvailablePowerData.farm_code == farm_code,
        AvailablePowerData.timestamp >= start,
        AvailablePowerData.timestamp < end,
    ).all()
    result = {}
    for row in rows:
        constraints = (
            row.grid_constraint,
            row.environmental_constraint,
            row.maintenance_constraint,
            row.operational_constraint,
        )
        result[row.timestamp] = {
            "available_power": _finite(row.available_power),
            "curtailed": any((_finite(value) or 0.0) > 0 for value in constraints),
        }
    return result


def _select_run(rows: list) -> list:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.prediction_run_id].append(row)
    if not grouped:
        return []
    candidates = list(grouped.values())
    candidates.sort(
        key=lambda group: (
            len({row.target_time for row in group}),
            max(row.issued_at for row in group),
            group[0].prediction_run_id,
        ),
        reverse=True,
    )
    return candidates[0]


def _ledger_day_predictions(session, farm_code: str, forecast_type: str, day: date) -> tuple[dict, dict]:
    start, end = _day_bounds(day)
    offset = POLICY["forecast_types"][forecast_type]["target_day_offset"]
    issue_start, issue_end = _day_bounds(day - timedelta(days=offset))
    rows = session.query(ForecastOutputPoint).filter(
        ForecastOutputPoint.farm_code == farm_code,
        ForecastOutputPoint.forecast_type == forecast_type,
        ForecastOutputPoint.target_time >= start,
        ForecastOutputPoint.target_time < end,
        ForecastOutputPoint.issued_at >= issue_start,
        ForecastOutputPoint.issued_at < issue_end,
    ).all()
    selected = _select_run(rows)
    if not selected:
        return {}, {"source": "forecast_output_points", "status": "missing"}
    latest_by_target = {}
    for row in selected:
        previous = latest_by_target.get(row.target_time)
        if previous is None or row.horizon_index > previous.horizon_index:
            latest_by_target[row.target_time] = row
    return (
        {target: row.predicted_power for target, row in latest_by_target.items()},
        {
            "source": "forecast_output_points",
            "status": "selected",
            "prediction_run_id": selected[0].prediction_run_id,
            "issued_at": max(row.issued_at for row in selected).isoformat(),
            "point_count": len(latest_by_target),
        },
    )


def _legacy_day_predictions(session, farm_code: str, forecast_type: str, day: date) -> tuple[dict, dict]:
    start, end = _day_bounds(day)
    offset = POLICY["forecast_types"][forecast_type]["target_day_offset"]
    issue_start, issue_end = _day_bounds(day - timedelta(days=offset))
    model = ShortlPower if forecast_type == "short" else MidPower
    rows = session.query(model).filter(
        model.farm_code == farm_code,
        model.timestamp >= start,
        model.timestamp < end,
        model.pre_at >= issue_start,
        model.pre_at < issue_end,
    ).all()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.pre_at].append(row)
    if not grouped:
        return {}, {"source": model.__tablename__, "status": "missing"}
    selected = max(
        grouped.values(),
        key=lambda group: (len({row.timestamp for row in group}), group[0].pre_at),
    )
    latest_by_target = {}
    for row in selected:
        previous = latest_by_target.get(row.timestamp)
        if previous is None or row.id > previous.id:
            latest_by_target[row.timestamp] = row
    return (
        {target: row.wp_pred for target, row in latest_by_target.items()},
        {
            "source": model.__tablename__,
            "status": "selected",
            "issued_at": selected[0].pre_at.isoformat(),
            "point_count": len(latest_by_target),
            "legacy_fallback": True,
        },
    )


def _load_day_predictions(session, farm_code: str, forecast_type: str, day: date) -> tuple[dict, dict]:
    predictions, selection = _ledger_day_predictions(session, farm_code, forecast_type, day)
    if predictions:
        return predictions, selection
    return _legacy_day_predictions(session, farm_code, forecast_type, day)


def _ledger_supershort_predictions(session, farm_code: str, day: date) -> tuple[dict, dict]:
    start, end = _day_bounds(day)
    rows = session.query(ForecastOutputPoint).filter(
        ForecastOutputPoint.farm_code == farm_code,
        ForecastOutputPoint.forecast_type == "supershort",
        ForecastOutputPoint.target_time >= start,
        ForecastOutputPoint.target_time < end,
        ForecastOutputPoint.horizon_index >= 1,
        ForecastOutputPoint.horizon_index <= 16,
    ).order_by(ForecastOutputPoint.issued_at).all()
    by_target = defaultdict(dict)
    for row in rows:
        previous = by_target[row.target_time].get(row.horizon_index)
        if previous is None or row.issued_at > previous.issued_at:
            by_target[row.target_time][row.horizon_index] = row
    if not by_target:
        return {}, {"source": "forecast_output_points", "status": "missing"}
    counts = {target: len(horizons) for target, horizons in by_target.items()}
    predictions = {
        target: mean(row.predicted_power for row in horizons.values())
        for target, horizons in by_target.items()
        if len(horizons) == 16
    }
    return predictions, {
        "source": "forecast_output_points",
        "status": "selected" if predictions else "partial",
        "aggregation": "mean_horizons_1_16",
        "target_count": len(counts),
        "evaluated_target_count": len(predictions),
        "complete_horizon_target_count": sum(1 for count in counts.values() if count == 16),
        "mean_horizon_count": mean(counts.values()) if counts else 0,
        "horizon_counts": {target.isoformat(): count for target, count in counts.items()},
    }


def _legacy_supershort_predictions(session, farm_code: str, day: date) -> tuple[dict, dict]:
    start, end = _day_bounds(day)
    earliest = start - timedelta(minutes=225)
    rows = session.query(SupershortlPower).filter(
        SupershortlPower.farm_code == farm_code,
        SupershortlPower.timestamp >= earliest,
        SupershortlPower.timestamp < end,
    ).all()
    records = {row.timestamp: row for row in rows}
    predictions = {}
    counts = {}
    for target in _expected_timestamps(day):
        values = []
        for column_index in range(2, 18):
            source_time = target - timedelta(minutes=(column_index - 2) * 15)
            source = records.get(source_time)
            value = _finite(getattr(source, f"wp_pred{column_index}", None)) if source else None
            if value is not None:
                values.append(value)
        if len(values) == 16:
            predictions[target] = mean(values)
        if values:
            counts[target] = len(values)
    return predictions, {
        "source": "supershortl_power",
        "status": "selected" if predictions else ("partial" if counts else "missing"),
        "aggregation": "mean_horizons_1_16",
        "target_count": len(counts),
        "evaluated_target_count": len(predictions),
        "complete_horizon_target_count": sum(1 for count in counts.values() if count == 16),
        "mean_horizon_count": mean(counts.values()) if counts else 0,
        "legacy_fallback": True,
    }


def _load_supershort_predictions(session, farm_code: str, day: date) -> tuple[dict, dict]:
    predictions, selection = _ledger_supershort_predictions(session, farm_code, day)
    if selection.get("status") != "missing":
        return predictions, selection
    return _legacy_supershort_predictions(session, farm_code, day)


def _persist_daily_metrics(session, result: dict) -> None:
    day_start = datetime.combine(date.fromisoformat(result["date"]), time.min)
    row = session.query(DailyMetrics).filter(
        DailyMetrics.date == day_start,
        DailyMetrics.farm_code == result["farm_code"],
        DailyMetrics.metric_type == result["forecast_type"],
        DailyMetrics.policy_version == result["policy_version"],
    ).order_by(DailyMetrics.id.desc()).first()
    if row is None:
        row = DailyMetrics(
            date=day_start,
            farm_code=result["farm_code"],
            metric_type=result["forecast_type"],
            policy_version=result["policy_version"],
        )
        session.add(row)
    row.mae = result["mae"]
    row.mse = result["mse"]
    row.rmse = result["rmse"]
    row.acc = result["accuracy_percent"]
    row.k = result["accuracy_percent"]
    row.pe = result["assessment_energy_mwh"]
    row.sample_count = result["sample_count"]
    row.threshold_percent = result["threshold_percent"]
    row.expected_count = result["expected_count"]
    row.excluded_count = result["excluded_count"]
    row.completeness = result["completeness"]
    row.status = result["status"]
    row.details_json = {
        "qualified": result["qualified"],
        "selection": result["selection"],
        "actual_source": result["actual_source"],
        "actual_source_counts": result["actual_source_counts"],
        "ignored_off_grid_actual_count": result["ignored_off_grid_actual_count"],
        "reference_source_counts": result["reference_source_counts"],
        "deficit_percentage_points": result["deficit_percentage_points"],
    }
    row.computed_at = datetime.now()
    session.flush()


def evaluate_regulatory_day(
    session,
    *,
    farm_code: str,
    forecast_type: str,
    day: date,
    capacity_mw: float,
    persist: bool = False,
) -> dict:
    """计算单场站、单尺度、单日评估结果。"""

    if forecast_type not in SUPPORTED_FORECAST_TYPES:
        raise ValueError(f"不支持的预测尺度: {forecast_type}")
    start, end = _day_bounds(day)
    (
        actual_map,
        actual_source,
        actual_source_counts,
        ignored_off_grid_actual_count,
    ) = _load_actual_map(session, farm_code, start, end)
    available_map = _load_available_map(session, farm_code, start, end)
    if forecast_type == "supershort":
        prediction_map, selection = _load_supershort_predictions(session, farm_code, day)
    else:
        prediction_map, selection = _load_day_predictions(session, farm_code, forecast_type, day)

    points = []
    for target in _expected_timestamps(day):
        available = available_map.get(target, {})
        points.append({
            "timestamp": target,
            "actual_power": actual_map.get(target),
            "predicted_power": prediction_map.get(target),
            "available_power": available.get("available_power"),
            "curtailed": available.get("curtailed", False),
        })

    type_policy = POLICY["forecast_types"][forecast_type]
    result = calculate_south_grid_daily_metrics(
        points,
        capacity_mw=capacity_mw,
        threshold_percent=type_policy["threshold_percent"],
        assessment_coefficient=type_policy["assessment_coefficient"],
    )
    result.update({
        "farm_code": farm_code,
        "forecast_type": forecast_type,
        "date": day.isoformat(),
        "policy_version": SOUTH_GRID_OPERATIONAL_POLICY_VERSION,
        "actual_source": actual_source,
        "actual_source_counts": actual_source_counts,
        "ignored_off_grid_actual_count": ignored_off_grid_actual_count,
        "actual_point_count": len(actual_map),
        "prediction_point_count": len(prediction_map),
        "selection": selection,
    })
    if persist:
        _persist_daily_metrics(session, result)
    return result


def _aggregate_daily_results(results: list[dict]) -> dict:
    complete = [item for item in results if item["status"] == "complete"]
    excluded = [item for item in results if item["status"] == "excluded"]
    covered = complete + excluded
    provisional = [item for item in results if item["accuracy_percent"] is not None]
    qualified = [item for item in complete if item["qualified"] is True]
    if covered and len(covered) == len(results):
        status = "complete" if complete else "excluded"
    elif provisional:
        status = "partial"
    elif covered:
        status = "partial"
    else:
        status = "missing"
    return {
        "status": status,
        "day_count": len(results),
        "complete_day_count": len(complete),
        "excluded_day_count": len(excluded),
        "partial_day_count": sum(1 for item in results if item["status"] == "partial"),
        "missing_day_count": sum(1 for item in results if item["status"] == "missing"),
        "accuracy_percent": mean(item["accuracy_percent"] for item in complete) if complete else None,
        "provisional_accuracy_percent": (
            mean(item["accuracy_percent"] for item in provisional) if provisional else None
        ),
        "qualified_rate_percent": (len(qualified) / len(complete) * 100.0) if complete else None,
        "unqualified_day_count": sum(1 for item in complete if item["qualified"] is False),
        "rmse": mean(item["rmse"] for item in complete) if complete else None,
        "mae": mean(item["mae"] for item in complete) if complete else None,
        "assessment_energy_mwh": (
            sum(item["assessment_energy_mwh"] or 0.0 for item in complete)
            if complete
            else None
        ),
        "sample_count": sum(item["sample_count"] for item in results),
        "expected_count": sum(item["expected_count"] for item in results),
        "daily": results,
    }


def evaluate_regulatory_period(
    session,
    *,
    farm_code: str,
    capacity_mw: float,
    start_date: date,
    end_date: date,
    forecast_types: tuple[str, ...] | list[str] = SUPPORTED_FORECAST_TYPES,
    persist: bool = False,
) -> dict:
    """计算一个场站在日期区间内的三尺度评估。"""

    if end_date < start_date:
        raise ValueError("结束日期不能早于开始日期")
    requested = []
    for forecast_type in forecast_types:
        value = "mid" if forecast_type == "medium" else str(forecast_type)
        if value not in SUPPORTED_FORECAST_TYPES:
            raise ValueError(f"不支持的预测尺度: {forecast_type}")
        if value not in requested:
            requested.append(value)

    days = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)

    metrics = {}
    for forecast_type in requested:
        daily = [evaluate_regulatory_day(
            session,
            farm_code=farm_code,
            forecast_type=forecast_type,
            day=day,
            capacity_mw=capacity_mw,
            persist=persist,
        ) for day in days]
        metrics[forecast_type] = {
            **_aggregate_daily_results(daily),
            "threshold_percent": POLICY["forecast_types"][forecast_type]["threshold_percent"],
            "label": POLICY["forecast_types"][forecast_type]["label"],
        }

    return {
        "farm_code": farm_code,
        "capacity_mw": float(capacity_mw),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "policy_version": SOUTH_GRID_OPERATIONAL_POLICY_VERSION,
        "metrics": metrics,
    }
