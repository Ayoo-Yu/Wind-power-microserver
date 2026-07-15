"""SCADA 样本校验、审计与实际功率落库。"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping

from db_models.power import ActualPower
from db_models.data_lineage import SourceObservation
from db_models.operational_data import (
    AvailableCapacityData,
    AvailablePowerData,
    TheoreticalPowerData,
    WeatherData,
)
from db_models.report_config import WindFarm
from db_models.scada_connection import ScadaConnection
from db_models.scada_ingest_record import ScadaIngestRecord
from services.scada_contract import (
    SCADA_METRICS,
    SCADA_POINT_CONTRACT_VERSION,
    ScadaContractError,
    metric_range_error,
    normalize_point_catalog,
    validate_metric_unit,
)


BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


class ScadaIngestError(ValueError):
    """表示无法关联到合法连接的请求错误。"""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ScadaIngestResult:
    accepted: bool
    outcome: str
    message: str
    record_id: int | None
    actual_power_id: int | None
    normalized_timestamp: datetime | None
    metric: str = "active_power_mw"
    observation_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "outcome": self.outcome,
            "message": self.message,
            "record_id": self.record_id,
            "actual_power_id": self.actual_power_id,
            "metric": self.metric,
            "observation_id": self.observation_id,
            "normalized_timestamp": (
                self.normalized_timestamp.isoformat()
                if self.normalized_timestamp is not None
                else None
            ),
        }


def _parse_timestamp(value, field_name: str) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ScadaIngestError(f"{field_name} 必须使用 ISO 8601 时间格式") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(BEIJING_TZ).replace(tzinfo=None)
    return parsed


def _optional_int(value, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ScadaIngestError(f"{field_name} 必须是整数") from exc


def _float_setting(config: Mapping, name: str, default: float) -> float:
    try:
        return float(config.get(name, default))
    except (TypeError, ValueError):
        return default


def _int_setting(config: Mapping, name: str, default: int) -> int:
    try:
        return int(config.get(name, default))
    except (TypeError, ValueError):
        return default


def _add_record(
    session,
    *,
    connection_id: int,
    farm_code: str,
    ioa: int | None,
    source_timestamp: datetime | None,
    normalized_timestamp: datetime | None,
    received_at: datetime,
    metric: str,
    value: float | None,
    unit: str,
    source_id: str,
    quality: str,
    outcome: str,
    message: str,
    actual_power_id: int | None = None,
    observation_id: int | None = None,
) -> ScadaIngestRecord:
    record = ScadaIngestRecord(
        connection_id=connection_id,
        farm_code=farm_code,
        ioa=ioa,
        metric=metric,
        value=value,
        unit=unit,
        source_id=source_id,
        source_timestamp=source_timestamp,
        normalized_timestamp=normalized_timestamp,
        received_at=received_at,
        power_mw=value if metric == "active_power_mw" else None,
        quality=quality,
        outcome=outcome,
        message=message,
        actual_power_id=actual_power_id,
        observation_id=observation_id,
    )
    session.add(record)
    session.flush()
    return record


def _load_point_catalog(connection: ScadaConnection) -> dict:
    try:
        raw = json.loads(connection.ioa_points) if connection.ioa_points else {}
    except (TypeError, json.JSONDecodeError) as exc:
        raise ScadaIngestError("SCADA 点表不是有效 JSON", status_code=409) from exc
    try:
        return normalize_point_catalog(
            raw,
            active_power_ioa=connection.upload_target_ioa,
        )
    except ScadaContractError as exc:
        raise ScadaIngestError(str(exc), status_code=409) from exc


def _observation_key(
    *,
    source_id: str,
    farm_code: str,
    metric: str,
    event_time: datetime,
    ioa: int | None,
    sequence: str | None,
    value: float,
    quality: str,
) -> str:
    identity = {
        "source_id": source_id,
        "farm_code": farm_code,
        "metric": metric,
        "event_time": event_time.isoformat(timespec="microseconds"),
        "ioa": ioa,
        "sequence": sequence,
        "value": value,
        "quality": quality,
    }
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record_observation(
    session,
    *,
    source_id: str,
    farm_code: str,
    metric: str,
    event_time: datetime,
    received_at: datetime,
    value: float,
    unit: str,
    quality: str,
    ioa: int | None,
    sequence: str | None,
    schema_version: str,
    payload_sha256: str | None,
    normalized_timestamp: datetime | None,
) -> tuple[SourceObservation, bool]:
    key = _observation_key(
        source_id=source_id,
        farm_code=farm_code,
        metric=metric,
        event_time=event_time,
        ioa=ioa,
        sequence=sequence,
        value=value,
        quality=quality,
    )
    existing = session.query(SourceObservation).filter(
        SourceObservation.observation_key == key
    ).first()
    if existing is not None:
        return existing, True

    observation = SourceObservation(
        observation_key=key,
        source_type="scada",
        source_id=source_id,
        farm_code=farm_code,
        metric=metric,
        event_time=event_time,
        received_at=received_at,
        value=value,
        unit=unit,
        quality=quality,
        sequence=sequence,
        schema_version=schema_version,
        payload_sha256=payload_sha256,
        metadata_json={
            "ioa": ioa,
            "normalized_timestamp": (
                normalized_timestamp.isoformat() if normalized_timestamp else None
            ),
        },
    )
    session.add(observation)
    session.flush()
    return observation, False


def _project_metric(
    session,
    *,
    metric: str,
    farm_code: str,
    timestamp: datetime,
    value: float,
    farm: WindFarm | None,
) -> tuple[str, int | None]:
    """将规范化观测投影到现有业务表，保持旧查询继续可用。"""

    if metric == "active_power_mw":
        actual = session.query(ActualPower).filter(
            ActualPower.farm_code == farm_code,
            ActualPower.timestamp == timestamp,
        ).first()
        if actual is None:
            actual = ActualPower(farm_code=farm_code, timestamp=timestamp, wp_true=value)
            session.add(actual)
            session.flush()
            return "created", actual.id
        if actual.wp_true is not None and abs(float(actual.wp_true) - value) <= 1e-6:
            return "duplicate", actual.id
        actual.wp_true = value
        session.flush()
        return "updated", actual.id

    if metric == "wind_speed_mps":
        row = session.query(WeatherData).filter(
            WeatherData.farm_code == farm_code,
            WeatherData.timestamp == timestamp,
        ).first()
        if row is None:
            row = WeatherData(farm_code=farm_code, timestamp=timestamp, wind_speed_avg=value)
            session.add(row)
            session.flush()
            return "created", row.id
        outcome = "duplicate" if row.wind_speed_avg == value else "updated"
        row.wind_speed_avg = value
        session.flush()
        return outcome, row.id

    if metric == "theoretical_power_mw":
        row = session.query(TheoreticalPowerData).filter(
            TheoreticalPowerData.farm_code == farm_code,
            TheoreticalPowerData.timestamp == timestamp,
        ).first()
        if row is None:
            row = TheoreticalPowerData(
                farm_code=farm_code,
                timestamp=timestamp,
                theoretical_power=value,
            )
            session.add(row)
            session.flush()
            return "created", row.id
        outcome = "duplicate" if row.theoretical_power == value else "updated"
        row.theoretical_power = value
        session.flush()
        return outcome, row.id

    if metric == "available_power_mw":
        row = session.query(AvailablePowerData).filter(
            AvailablePowerData.farm_code == farm_code,
            AvailablePowerData.timestamp == timestamp,
        ).first()
        if row is None:
            row = AvailablePowerData(
                farm_code=farm_code,
                timestamp=timestamp,
                available_power=value,
            )
            session.add(row)
            session.flush()
            return "created", row.id
        outcome = "duplicate" if row.available_power == value else "updated"
        row.available_power = value
        session.flush()
        return outcome, row.id

    if metric == "availability_pct":
        available_capacity = (
            float(farm.capacity) * value / 100.0
            if farm is not None and farm.capacity is not None
            else 0.0
        )
        row = session.query(AvailableCapacityData).filter(
            AvailableCapacityData.farm_code == farm_code,
            AvailableCapacityData.timestamp == timestamp,
        ).first()
        if row is None:
            row = AvailableCapacityData(
                farm_code=farm_code,
                timestamp=timestamp,
                available_capacity=available_capacity,
                availability_rate=value,
            )
            session.add(row)
            session.flush()
            return "created", row.id
        outcome = "duplicate" if row.availability_rate == value else "updated"
        row.available_capacity = available_capacity
        row.availability_rate = value
        session.flush()
        return outcome, row.id

    raise ScadaIngestError(f"没有指标 {metric} 的业务投影器")


def ingest_scada_sample(
    session,
    payload: Mapping,
    config: Mapping,
    *,
    now: datetime | None = None,
) -> ScadaIngestResult:
    """校验一个样本，记录来源，并按需写入十五分钟实际功率表。"""

    try:
        connection_id = int(payload.get("connection_id"))
    except (TypeError, ValueError) as exc:
        raise ScadaIngestError("connection_id 必须是整数") from exc

    farm_code = str(payload.get("farm_code", "") or "").strip()
    if not farm_code:
        raise ScadaIngestError("farm_code 不能为空")

    connection = session.query(ScadaConnection).filter(
        ScadaConnection.id == connection_id
    ).first()
    if connection is None:
        raise ScadaIngestError("SCADA 连接不存在", status_code=404)
    if connection.farm_code != farm_code:
        raise ScadaIngestError("连接与场站编码不匹配", status_code=409)
    if not connection.is_enabled:
        raise ScadaIngestError("SCADA 连接尚未启用", status_code=409)

    received_at = now or datetime.now()
    if received_at.tzinfo is not None:
        received_at = received_at.astimezone(BEIJING_TZ).replace(tzinfo=None)

    source_timestamp = _parse_timestamp(payload.get("source_timestamp"), "source_timestamp")
    normalized_timestamp = _parse_timestamp(
        payload.get("normalized_timestamp"), "normalized_timestamp"
    )
    ioa = _optional_int(payload.get("ioa"), "ioa")
    quality = str(payload.get("quality", "unknown") or "unknown").strip().lower()
    catalog = _load_point_catalog(connection)
    point = catalog.get(str(ioa)) if ioa is not None else None

    metric = str(payload.get("metric") or (point or {}).get("metric") or "").strip()
    if not metric and "power_mw" in payload:
        metric = "active_power_mw"
    unit = str(
        payload.get("unit")
        or (point or {}).get("unit")
        or SCADA_METRICS.get(metric, {}).get("unit")
        or "unknown"
    ).strip()
    source_id = str(
        payload.get("source_id") or f"scada.connection.{connection_id}"
    ).strip()
    sequence = payload.get("sequence")
    sequence = str(sequence) if sequence not in (None, "") else None
    schema_version = str(
        payload.get("schema_version")
        or connection.point_catalog_version
        or SCADA_POINT_CONTRACT_VERSION
    ).strip()
    payload_sha256 = str(payload.get("payload_sha256") or "").strip() or None

    raw_value = payload.get("value", payload.get("power_mw"))
    try:
        value = float(raw_value) if raw_value is not None else None
    except (TypeError, ValueError):
        value = None

    rejection = None
    if catalog and point is None:
        rejection = f"IOA {ioa} 未在当前版本点表中配置"
    elif point and point.get("metric") and metric != point["metric"]:
        rejection = f"IOA {ioa} 与指标 {metric} 的点表映射不一致"
    elif metric not in SCADA_METRICS:
        rejection = f"不支持的 SCADA 指标: {metric or 'empty'}"
    else:
        try:
            validate_metric_unit(metric, unit)
        except ScadaContractError as exc:
            rejection = str(exc)

    if rejection is None and quality != "good":
        rejection = f"质量码不可用: {quality}"
    elif rejection is None and (value is None or not math.isfinite(value)):
        rejection = f"{metric} 数值无效"

    farm = session.query(WindFarm).filter(WindFarm.farm_code == farm_code).first()
    if rejection is None and value is not None:
        if metric == "active_power_mw":
            min_power = _float_setting(config, "SCADA_POWER_MIN_MW", -0.5)
            max_factor = _float_setting(config, "SCADA_POWER_MAX_CAPACITY_FACTOR", 1.2)
            if value < min_power:
                rejection = f"功率值低于允许下限 {min_power:.2f} MW"
            elif (
                farm is not None
                and farm.capacity is not None
                and farm.capacity > 0
                and value > float(farm.capacity) * max_factor
            ):
                rejection = "功率值超过装机容量允许范围"
        else:
            rejection = metric_range_error(
                metric,
                value,
                float(farm.capacity) if farm and farm.capacity is not None else None,
            )

    max_future_seconds = _int_setting(config, "SCADA_MAX_CLOCK_SKEW_SECONDS", 300)
    max_source_age_seconds = _int_setting(config, "SCADA_MAX_SOURCE_AGE_SECONDS", 86400)
    if rejection is None and source_timestamp is not None:
        source_age = (received_at - source_timestamp).total_seconds()
        if source_age < -max_future_seconds:
            rejection = "源时间超前，超过允许时钟偏差"
        elif source_age > max_source_age_seconds:
            rejection = "源数据超过允许时效"

    if rejection is not None:
        record = _add_record(
            session,
            connection_id=connection_id,
            farm_code=farm_code,
            ioa=ioa,
            metric=metric or "unknown",
            value=value,
            unit=unit,
            source_id=source_id,
            source_timestamp=source_timestamp,
            normalized_timestamp=normalized_timestamp,
            received_at=received_at,
            quality=quality,
            outcome="rejected",
            message=rejection,
        )
        connection.updated_at = received_at
        connection.status_message = rejection
        return ScadaIngestResult(
            accepted=False,
            outcome="rejected",
            message=rejection,
            record_id=record.id,
            actual_power_id=None,
            normalized_timestamp=normalized_timestamp,
            metric=metric or "unknown",
        )

    event_time = source_timestamp or normalized_timestamp or received_at
    observation, observation_duplicate = _record_observation(
        session,
        source_id=source_id,
        farm_code=farm_code,
        metric=metric,
        event_time=event_time,
        received_at=received_at,
        value=value,
        unit=unit,
        quality=quality,
        ioa=ioa,
        sequence=sequence,
        schema_version=schema_version,
        payload_sha256=payload_sha256,
        normalized_timestamp=normalized_timestamp,
    )

    connection.last_data_at = received_at
    if metric == "active_power_mw":
        connection.last_power_value = int(round(value * 10))
    connection.updated_at = received_at
    connection.last_error = None
    if connection.status in {"connecting", "error"}:
        connection.status = "running"

    if normalized_timestamp is None:
        outcome = "duplicate" if observation_duplicate else "observed"
        message = (
            "重复实时观测已幂等处理"
            if observation_duplicate
            else "实时观测已审计，当前时间策略无需写入业务汇总表"
        )
        actual_power_id = None
    else:
        outcome, projected_id = _project_metric(
            session,
            metric=metric,
            farm_code=farm_code,
            timestamp=normalized_timestamp,
            value=value,
            farm=farm,
        )
        actual_power_id = projected_id if metric == "active_power_mw" else None
        action = {
            "created": "记录已创建",
            "updated": "记录已更新",
            "duplicate": "重复样本已幂等处理",
        }[outcome]
        message = f"{SCADA_METRICS[metric]['label']}{action}"

    connection.status_message = f"{SCADA_METRICS[metric]['label']} {value:.2f} {unit}，{message}"
    record = _add_record(
        session,
        connection_id=connection_id,
        farm_code=farm_code,
        ioa=ioa,
        metric=metric,
        value=value,
        unit=unit,
        source_id=source_id,
        source_timestamp=source_timestamp,
        normalized_timestamp=normalized_timestamp,
        received_at=received_at,
        quality=quality,
        outcome=outcome,
        message=message,
        actual_power_id=actual_power_id,
        observation_id=observation.id,
    )
    return ScadaIngestResult(
        accepted=True,
        outcome=outcome,
        message=message,
        record_id=record.id,
        actual_power_id=actual_power_id,
        normalized_timestamp=normalized_timestamp,
        metric=metric,
        observation_id=observation.id,
    )
