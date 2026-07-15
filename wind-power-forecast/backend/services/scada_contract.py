"""SCADA 点位语义、单位和版本化契约。"""

from __future__ import annotations

from typing import Any, Mapping


SCADA_POINT_CONTRACT_VERSION = "scada-point-v2"

SCADA_METRICS = {
    "active_power_mw": {
        "unit": "MW",
        "label": "实发功率",
        "minimum": -0.5,
        "capacity_factor": 1.2,
    },
    "wind_speed_mps": {
        "unit": "m/s",
        "label": "场站风速",
        "minimum": 0.0,
        "maximum": 90.0,
    },
    "theoretical_power_mw": {
        "unit": "MW",
        "label": "理论功率",
        "minimum": 0.0,
        "capacity_factor": 1.5,
    },
    "available_power_mw": {
        "unit": "MW",
        "label": "可用功率",
        "minimum": 0.0,
        "capacity_factor": 1.5,
    },
    "availability_pct": {
        "unit": "%",
        "label": "风机可用率",
        "minimum": 0.0,
        "maximum": 100.0,
    },
}

REQUIRED_SCADA_METRICS = tuple(SCADA_METRICS)


class ScadaContractError(ValueError):
    """点位配置或样本与版本化契约不一致。"""


def normalize_point_catalog(
    raw_points: Mapping[str, Any] | None,
    *,
    active_power_ioa: int | None = None,
) -> dict[str, dict[str, Any]]:
    """兼容旧点表并返回以 IOA 为键的规范化配置。"""

    result: dict[str, dict[str, Any]] = {}
    for raw_ioa, raw_definition in dict(raw_points or {}).items():
        try:
            ioa = str(int(raw_ioa))
        except (TypeError, ValueError) as exc:
            raise ScadaContractError(f"IOA 地址无效: {raw_ioa}") from exc

        if isinstance(raw_definition, str):
            definition: dict[str, Any] = {"type": raw_definition}
        elif isinstance(raw_definition, Mapping):
            definition = dict(raw_definition)
        else:
            raise ScadaContractError(f"IOA {ioa} 的点位定义必须是字符串或对象")

        definition["type"] = str(definition.get("type") or "M_ME_NC_1")
        metric = str(definition.get("metric") or "").strip()
        if not metric and active_power_ioa is not None and int(ioa) == int(active_power_ioa):
            metric = "active_power_mw"
        if metric:
            if metric not in SCADA_METRICS:
                raise ScadaContractError(f"IOA {ioa} 使用了未知指标 {metric}")
            definition["metric"] = metric
            definition["unit"] = str(
                definition.get("unit") or SCADA_METRICS[metric]["unit"]
            )
        result[ioa] = definition
    return result


def point_definition(
    raw_points: Mapping[str, Any] | None,
    ioa: int | None,
    *,
    active_power_ioa: int | None = None,
) -> dict[str, Any] | None:
    if ioa is None:
        return None
    return normalize_point_catalog(
        raw_points,
        active_power_ioa=active_power_ioa,
    ).get(str(int(ioa)))


def validate_metric_unit(metric: str, unit: str) -> None:
    definition = SCADA_METRICS.get(metric)
    if definition is None:
        raise ScadaContractError(f"不支持的 SCADA 指标: {metric}")
    expected = definition["unit"]
    if unit != expected:
        raise ScadaContractError(f"指标 {metric} 的单位必须是 {expected}")


def metric_range_error(metric: str, value: float, capacity_mw: float | None) -> str | None:
    definition = SCADA_METRICS[metric]
    minimum = definition.get("minimum")
    maximum = definition.get("maximum")
    if minimum is not None and value < float(minimum):
        return f"{definition['label']}低于允许下限 {minimum} {definition['unit']}"
    if maximum is not None and value > float(maximum):
        return f"{definition['label']}超过允许上限 {maximum} {definition['unit']}"
    factor = definition.get("capacity_factor")
    if factor is not None and capacity_mw is not None and capacity_mw > 0:
        if value > float(capacity_mw) * float(factor):
            return f"{definition['label']}超过装机容量允许范围"
    return None
