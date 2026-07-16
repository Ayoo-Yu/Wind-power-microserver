"""实际功率十五分钟时间契约与统一补源查询。"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from db_models.data_lineage import SourceObservation
from db_models.operational_data import TurbinePowerData
from db_models.power import ActualPower


BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
ACTUAL_POWER_RESOLUTION_MINUTES = 15
DEFAULT_RAW_FALLBACK_MAX_AGE_SECONDS = 900
DEFAULT_TURBINE_POWER_UNIT = "kw"


class ActualPowerContractError(ValueError):
    """实际功率时间或数值不符合统一契约。"""


@dataclass(frozen=True)
class CanonicalActualPowerSeries:
    """统一补源后的十五分钟实际功率序列。"""

    values: dict[datetime, float]
    sources: dict[datetime, str]
    expected_timestamps: tuple[datetime, ...]
    ignored_off_grid_count: int = 0

    @property
    def source_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for source in self.sources.values():
            counts[source] = counts.get(source, 0) + 1
        return counts

    @property
    def source_label(self) -> str:
        labels = list(self.source_counts)
        if not labels:
            return "missing"
        if len(labels) == 1:
            return labels[0]
        return "mixed"

    @property
    def missing_count(self) -> int:
        return max(0, len(self.expected_timestamps) - len(self.values))


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_actual_power_value(value: Any) -> float | None:
    """解析允许为空的实际功率值，并拒绝非有限数值。"""

    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "nan", "null"}:
        return None
    number = _finite(value)
    if number is None:
        raise ActualPowerContractError("wp_true 必须是有限数值或 null")
    return number


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    to_python = getattr(value, "to_pydatetime", None)
    if callable(to_python):
        converted = to_python()
        if isinstance(converted, datetime):
            return converted
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ActualPowerContractError("时间戳必须使用 ISO 8601 格式") from exc


def to_local_naive(value: Any) -> datetime:
    """将时间统一为北京时间无时区对象，以匹配现有数据库字段。"""

    parsed = _as_datetime(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(BEIJING_TZ).replace(tzinfo=None)
    return parsed


def is_quarter_hour(value: datetime) -> bool:
    """判断时间是否落在严格十五分钟边界。"""

    return (
        value.minute % ACTUAL_POWER_RESOLUTION_MINUTES == 0
        and value.second == 0
        and value.microsecond == 0
    )


def require_quarter_hour(value: Any) -> datetime:
    """解析时间并拒绝不在十五分钟边界的值。"""

    parsed = to_local_naive(value)
    if not is_quarter_hour(parsed):
        raise ActualPowerContractError(
            "实际功率时间必须位于十五分钟边界，秒和微秒必须为 0"
        )
    return parsed


def floor_quarter_hour(value: Any) -> datetime:
    """向前对齐到十五分钟边界，仅用于查询边界计算。"""

    parsed = to_local_naive(value)
    return parsed.replace(
        minute=(parsed.minute // ACTUAL_POWER_RESOLUTION_MINUTES)
        * ACTUAL_POWER_RESOLUTION_MINUTES,
        second=0,
        microsecond=0,
    )


def ceil_quarter_hour(value: Any) -> datetime:
    """向后对齐到十五分钟边界，仅用于查询边界计算。"""

    parsed = to_local_naive(value)
    floored = floor_quarter_hour(parsed)
    if parsed == floored:
        return floored
    return floored + timedelta(minutes=ACTUAL_POWER_RESOLUTION_MINUTES)


def quarter_hour_grid(start: Any, end: Any) -> tuple[datetime, ...]:
    """生成左闭右开的北京时间十五分钟网格。"""

    start_dt = ceil_quarter_hour(start)
    end_dt = to_local_naive(end)
    if end_dt <= start_dt:
        return ()
    values = []
    current = start_dt
    step = timedelta(minutes=ACTUAL_POWER_RESOLUTION_MINUTES)
    while current < end_dt:
        values.append(current)
        current += step
    return tuple(values)


def raw_fallback_max_age_seconds() -> int:
    """读取原始 SCADA 补源允许的最大样本年龄。"""

    raw = os.environ.get(
        "ACTUAL_POWER_RAW_FALLBACK_MAX_AGE_SECONDS",
        str(DEFAULT_RAW_FALLBACK_MAX_AGE_SECONDS),
    )
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ActualPowerContractError(
            "ACTUAL_POWER_RAW_FALLBACK_MAX_AGE_SECONDS 必须是整数"
        ) from exc
    if value <= 0 or value > ACTUAL_POWER_RESOLUTION_MINUTES * 60:
        raise ActualPowerContractError(
            "ACTUAL_POWER_RAW_FALLBACK_MAX_AGE_SECONDS 必须在 1 至 900 之间"
        )
    return value


def turbine_power_to_mw(value: Any) -> float | None:
    """按单机功率表声明单位换算为 MW。"""

    number = _finite(value)
    if number is None:
        return None
    unit = os.environ.get(
        "ACTUAL_POWER_TURBINE_SOURCE_UNIT",
        DEFAULT_TURBINE_POWER_UNIT,
    ).strip().lower()
    if unit == "kw":
        return number / 1000.0
    if unit == "mw":
        return number
    raise ActualPowerContractError(
        "ACTUAL_POWER_TURBINE_SOURCE_UNIT 仅支持 kW 或 MW"
    )


def load_canonical_actual_power(
    session,
    farm_code: str,
    start: Any,
    end: Any,
    *,
    raw_max_age_seconds: int | None = None,
) -> CanonicalActualPowerSeries:
    """按业务表、原始 SCADA、单机汇总的优先级逐点补齐。"""

    start_dt = to_local_naive(start)
    end_dt = to_local_naive(end)
    expected = quarter_hour_grid(start_dt, end_dt)
    expected_set = set(expected)
    values: dict[datetime, float] = {}
    sources: dict[datetime, str] = {}
    ignored_off_grid_count = 0

    actual_rows = session.query(ActualPower.timestamp, ActualPower.wp_true).filter(
        ActualPower.farm_code == farm_code,
        ActualPower.timestamp >= start_dt,
        ActualPower.timestamp < end_dt,
        ActualPower.wp_true.isnot(None),
    ).order_by(ActualPower.timestamp, ActualPower.id).all()
    for row in actual_rows:
        value = _finite(row.wp_true)
        if value is None:
            continue
        if row.timestamp not in expected_set:
            ignored_off_grid_count += 1
            continue
        values[row.timestamp] = value
        sources[row.timestamp] = "actual_power"

    if len(values) == len(expected):
        return CanonicalActualPowerSeries(
            values=values,
            sources=sources,
            expected_timestamps=expected,
            ignored_off_grid_count=ignored_off_grid_count,
        )

    max_age_seconds = (
        raw_fallback_max_age_seconds()
        if raw_max_age_seconds is None
        else int(raw_max_age_seconds)
    )
    if max_age_seconds <= 0 or max_age_seconds > ACTUAL_POWER_RESOLUTION_MINUTES * 60:
        raise ActualPowerContractError("原始 SCADA 补源时效必须在 1 至 900 秒之间")

    observation_rows = session.query(
        SourceObservation.event_time,
        SourceObservation.value,
        SourceObservation.id,
    ).filter(
        SourceObservation.farm_code == farm_code,
        SourceObservation.source_type == "scada",
        SourceObservation.metric == "active_power_mw",
        SourceObservation.quality == "good",
        SourceObservation.event_time >= start_dt - timedelta(seconds=max_age_seconds),
        SourceObservation.event_time < end_dt,
        SourceObservation.value.isnot(None),
    ).order_by(SourceObservation.event_time, SourceObservation.id).all()

    observation_index = 0
    latest_observation = None
    for target in expected:
        while (
            observation_index < len(observation_rows)
            and observation_rows[observation_index].event_time <= target
        ):
            latest_observation = observation_rows[observation_index]
            observation_index += 1
        if target in values or latest_observation is None:
            continue
        age_seconds = (target - latest_observation.event_time).total_seconds()
        value = _finite(latest_observation.value)
        if 0 <= age_seconds < max_age_seconds and value is not None:
            values[target] = value
            sources[target] = "source_observations"

    if len(values) == len(expected):
        return CanonicalActualPowerSeries(
            values=values,
            sources=sources,
            expected_timestamps=expected,
            ignored_off_grid_count=ignored_off_grid_count,
        )

    turbine_rows = session.query(
        TurbinePowerData.timestamp,
        TurbinePowerData.turbine_id,
        TurbinePowerData.active_power,
        TurbinePowerData.id,
    ).filter(
        TurbinePowerData.farm_code == farm_code,
        TurbinePowerData.timestamp >= start_dt,
        TurbinePowerData.timestamp < end_dt,
        TurbinePowerData.active_power.isnot(None),
    ).order_by(
        TurbinePowerData.timestamp,
        TurbinePowerData.turbine_id,
        TurbinePowerData.id,
    ).all()
    latest_turbine_values: dict[tuple[datetime, str], float] = {}
    for row in turbine_rows:
        value = _finite(row.active_power)
        if value is not None:
            latest_turbine_values[(row.timestamp, row.turbine_id)] = value
    turbine_sums: dict[datetime, float] = {}
    for (timestamp, _turbine_id), value in latest_turbine_values.items():
        turbine_sums[timestamp] = turbine_sums.get(timestamp, 0.0) + value

    for timestamp, power_sum in turbine_sums.items():
        if timestamp in values or timestamp not in expected_set:
            continue
        value = turbine_power_to_mw(power_sum)
        if value is not None:
            values[timestamp] = value
            sources[timestamp] = "turbine_power_sum"

    return CanonicalActualPowerSeries(
        values=values,
        sources=sources,
        expected_timestamps=expected,
        ignored_off_grid_count=ignored_off_grid_count,
    )
