"""SCADA 样本校验、审计与实际功率落库。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping

from db_models.power import ActualPower
from db_models.report_config import WindFarm
from db_models.scada_connection import ScadaConnection
from db_models.scada_ingest_record import ScadaIngestRecord


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

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "outcome": self.outcome,
            "message": self.message,
            "record_id": self.record_id,
            "actual_power_id": self.actual_power_id,
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
    power_mw: float | None,
    quality: str,
    outcome: str,
    message: str,
    actual_power_id: int | None = None,
) -> ScadaIngestRecord:
    record = ScadaIngestRecord(
        connection_id=connection_id,
        farm_code=farm_code,
        ioa=ioa,
        source_timestamp=source_timestamp,
        normalized_timestamp=normalized_timestamp,
        received_at=received_at,
        power_mw=power_mw,
        quality=quality,
        outcome=outcome,
        message=message,
        actual_power_id=actual_power_id,
    )
    session.add(record)
    session.flush()
    return record


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

    raw_power = payload.get("power_mw")
    try:
        power_mw = float(raw_power) if raw_power is not None else None
    except (TypeError, ValueError):
        power_mw = None

    rejection = None
    if quality != "good":
        rejection = f"质量码不可用: {quality}"
    elif power_mw is None or not math.isfinite(power_mw):
        rejection = "功率值无效"

    farm = session.query(WindFarm).filter(WindFarm.farm_code == farm_code).first()
    min_power = _float_setting(config, "SCADA_POWER_MIN_MW", -0.5)
    max_factor = _float_setting(config, "SCADA_POWER_MAX_CAPACITY_FACTOR", 1.2)
    if rejection is None and power_mw is not None and power_mw < min_power:
        rejection = f"功率值低于允许下限 {min_power:.2f} MW"
    if (
        rejection is None
        and power_mw is not None
        and farm is not None
        and farm.capacity is not None
        and farm.capacity > 0
        and power_mw > float(farm.capacity) * max_factor
    ):
        rejection = "功率值超过装机容量允许范围"

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
            source_timestamp=source_timestamp,
            normalized_timestamp=normalized_timestamp,
            received_at=received_at,
            power_mw=power_mw,
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
        )

    connection.last_data_at = received_at
    connection.last_power_value = int(round(power_mw * 10))
    connection.updated_at = received_at
    connection.last_error = None
    if connection.status in {"connecting", "error"}:
        connection.status = "running"

    if normalized_timestamp is None:
        message = "实时样本已审计，当前时间策略无需写入十五分钟实际功率"
        connection.status_message = message
        record = _add_record(
            session,
            connection_id=connection_id,
            farm_code=farm_code,
            ioa=ioa,
            source_timestamp=source_timestamp,
            normalized_timestamp=None,
            received_at=received_at,
            power_mw=power_mw,
            quality=quality,
            outcome="observed",
            message=message,
        )
        return ScadaIngestResult(
            accepted=True,
            outcome="observed",
            message=message,
            record_id=record.id,
            actual_power_id=None,
            normalized_timestamp=None,
        )

    actual = session.query(ActualPower).filter(
        ActualPower.farm_code == farm_code,
        ActualPower.timestamp == normalized_timestamp,
    ).first()
    if actual is None:
        actual = ActualPower(
            farm_code=farm_code,
            timestamp=normalized_timestamp,
            wp_true=power_mw,
        )
        session.add(actual)
        session.flush()
        outcome = "created"
        message = "实际功率记录已创建"
    elif actual.wp_true is not None and abs(float(actual.wp_true) - power_mw) <= 1e-6:
        outcome = "duplicate"
        message = "重复样本已幂等处理"
    else:
        actual.wp_true = power_mw
        session.flush()
        outcome = "updated"
        message = "实际功率记录已更新"

    connection.status_message = f"{power_mw:.2f} MW，{message}"
    record = _add_record(
        session,
        connection_id=connection_id,
        farm_code=farm_code,
        ioa=ioa,
        source_timestamp=source_timestamp,
        normalized_timestamp=normalized_timestamp,
        received_at=received_at,
        power_mw=power_mw,
        quality=quality,
        outcome=outcome,
        message=message,
        actual_power_id=actual.id,
    )
    return ScadaIngestResult(
        accepted=True,
        outcome=outcome,
        message=message,
        record_id=record.id,
        actual_power_id=actual.id,
        normalized_timestamp=normalized_timestamp,
    )
