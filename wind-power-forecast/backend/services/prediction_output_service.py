"""把预测服务输出写入运行级不可变账本。"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime

from db_models.data_lineage import PredictionInputSnapshot
from db_models.forecast_trace import ForecastOutputPoint
from db_models.prediction_run import PredictionRun


FORECAST_OUTPUT_CONTRACT_VERSION = "forecast-output-v1"
_VALID_FORECAST_TYPES = {"short", "mid", "supershort"}


def _canonical_hash(value: dict) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalise_type(forecast_type: str) -> str:
    value = "mid" if forecast_type == "medium" else str(forecast_type)
    if value not in _VALID_FORECAST_TYPES:
        raise ValueError(f"不支持的预测尺度: {forecast_type}")
    return value


def _finite_or_none(value):
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _normalise_points(issued_at: datetime, points: list[dict]) -> list[dict]:
    normalised = []
    identities = set()
    target_times = set()
    horizon_indices = set()
    for source in points:
        target_time = source.get("target_time")
        horizon_index = int(source.get("horizon_index"))
        predicted_power = _finite_or_none(source.get("predicted_power"))
        if not isinstance(target_time, datetime):
            raise ValueError("预测目标时间必须为 datetime")
        if horizon_index <= 0:
            raise ValueError("预测提前量序号必须大于 0")
        if predicted_power is None:
            raise ValueError("预测功率必须为有限数值")
        identity = (target_time, horizon_index)
        if identity in identities:
            raise ValueError("同一次运行包含重复的目标时刻和提前量序号")
        if target_time in target_times:
            raise ValueError("同一次运行包含重复的目标时刻")
        if horizon_index in horizon_indices:
            raise ValueError("同一次运行包含重复的提前量序号")
        identities.add(identity)
        target_times.add(target_time)
        horizon_indices.add(horizon_index)
        horizon_minutes = source.get("horizon_minutes")
        if horizon_minutes is None:
            horizon_minutes = round((target_time - issued_at).total_seconds() / 60)
        if int(horizon_minutes) <= 0:
            raise ValueError("预测提前分钟数必须大于 0")
        normalised.append({
            "target_time": target_time,
            "horizon_index": horizon_index,
            "horizon_minutes": int(horizon_minutes),
            "predicted_power": predicted_power,
            "raw_predicted_power": _finite_or_none(source.get("raw_predicted_power")),
            "lower_power": _finite_or_none(source.get("lower_power")),
            "upper_power": _finite_or_none(source.get("upper_power")),
        })
    return sorted(normalised, key=lambda item: (item["target_time"], item["horizon_index"]))


def _manifest_payload(
    *,
    prediction_run_id: int,
    input_snapshot_id: int | None,
    model_version_id: int | None,
    farm_code: str,
    forecast_type: str,
    issued_at: datetime,
    expected_count: int,
    points: list[dict],
) -> dict:
    serialised_points = [{
        **item,
        "target_time": item["target_time"].isoformat(),
    } for item in points]
    identity = {
        "contract_version": FORECAST_OUTPUT_CONTRACT_VERSION,
        "prediction_run_id": prediction_run_id,
        "input_snapshot_id": input_snapshot_id,
        "model_version_id": model_version_id,
        "farm_code": farm_code,
        "forecast_type": forecast_type,
        "issued_at": issued_at.isoformat(),
        "points": serialised_points,
    }
    output_sha256 = _canonical_hash(identity)
    count = len(points)
    horizon_indices = {item["horizon_index"] for item in points}
    expected_horizons = set(range(1, expected_count + 1))
    horizon_complete = horizon_indices == expected_horizons
    target_start = points[0]["target_time"] if points else None
    target_end = points[-1]["target_time"] if points else None
    delivery_expected_count = 960 if forecast_type == "mid" else expected_count
    return {
        "contract_version": FORECAST_OUTPUT_CONTRACT_VERSION,
        "prediction_run_id": prediction_run_id,
        "input_snapshot_id": input_snapshot_id,
        "model_version_id": model_version_id,
        "farm_code": farm_code,
        "forecast_type": forecast_type,
        "issued_at": issued_at.isoformat(),
        "target_start": target_start.isoformat() if target_start else None,
        "target_end": target_end.isoformat() if target_end else None,
        "expected_count": expected_count,
        "record_count": count,
        "status": "complete" if count == expected_count and horizon_complete else "partial",
        "horizon_complete": horizon_complete,
        "output_sha256": output_sha256,
        "delivery_expected_count": delivery_expected_count,
        "regulatory_delivery_ready": (
            count >= delivery_expected_count
            and set(range(1, delivery_expected_count + 1)).issubset(horizon_indices)
        ),
    }


def record_forecast_output_points(
    session,
    *,
    prediction_run_id: int,
    input_snapshot_id: int | None,
    model_version_id: int | None,
    farm_code: str,
    forecast_type: str,
    issued_at: datetime,
    expected_count: int,
    points: list[dict],
) -> dict:
    """写入不可变预测点，重复调用时校验内容完全一致。"""

    if not prediction_run_id:
        raise ValueError("prediction_run_id 不能为空")
    if expected_count <= 0:
        raise ValueError("expected_count 必须大于 0")
    normalised_type = _normalise_type(forecast_type)

    run = (
        session.query(PredictionRun)
        .filter(PredictionRun.id == prediction_run_id)
        .with_for_update()
        .first()
    )
    if run is None:
        raise ValueError(f"预测运行 {prediction_run_id} 不存在")
    if run.action != "predict":
        raise ValueError("只有预测运行可以写入输出账本")

    if input_snapshot_id is not None:
        snapshot = (
            session.query(PredictionInputSnapshot)
            .filter(PredictionInputSnapshot.id == input_snapshot_id)
            .first()
        )
        if snapshot is None or snapshot.prediction_run_id != prediction_run_id:
            raise ValueError("输入快照与预测运行不匹配")
        if snapshot.farm_code != farm_code:
            raise ValueError("输入快照与输出场站不匹配")
        snapshot_type = "mid" if snapshot.task_type == "medium" else snapshot.task_type
        if snapshot_type != normalised_type:
            raise ValueError("输入快照与输出预测尺度不匹配")
        if (
            model_version_id is not None
            and snapshot.model_version_id is not None
            and model_version_id != snapshot.model_version_id
        ):
            raise ValueError("输入快照与输出模型版本不匹配")

    normalised_points = _normalise_points(issued_at, points)
    incoming_manifest = _manifest_payload(
        prediction_run_id=prediction_run_id,
        input_snapshot_id=input_snapshot_id,
        model_version_id=model_version_id,
        farm_code=farm_code,
        forecast_type=normalised_type,
        issued_at=issued_at,
        expected_count=expected_count,
        points=normalised_points,
    )

    existing = (
        session.query(ForecastOutputPoint)
        .filter(ForecastOutputPoint.prediction_run_id == prediction_run_id)
        .order_by(ForecastOutputPoint.target_time, ForecastOutputPoint.horizon_index)
        .all()
    )
    if existing:
        existing_points = [{
            "target_time": row.target_time,
            "horizon_index": row.horizon_index,
            "horizon_minutes": row.horizon_minutes,
            "predicted_power": row.predicted_power,
            "raw_predicted_power": row.raw_predicted_power,
            "lower_power": row.lower_power,
            "upper_power": row.upper_power,
        } for row in existing]
        existing_manifest = _manifest_payload(
            prediction_run_id=prediction_run_id,
            input_snapshot_id=existing[0].input_snapshot_id,
            model_version_id=existing[0].model_version_id,
            farm_code=existing[0].farm_code,
            forecast_type=existing[0].forecast_type,
            issued_at=existing[0].issued_at,
            expected_count=expected_count,
            points=existing_points,
        )
        if existing_manifest["output_sha256"] != incoming_manifest["output_sha256"]:
            raise ValueError("同一预测运行已存在不同内容的输出账本")
        return existing_manifest

    for point in normalised_points:
        session.add(ForecastOutputPoint(
            prediction_run_id=prediction_run_id,
            input_snapshot_id=input_snapshot_id,
            model_version_id=model_version_id,
            farm_code=farm_code,
            forecast_type=normalised_type,
            issued_at=issued_at,
            **point,
        ))
    session.flush()
    return incoming_manifest
