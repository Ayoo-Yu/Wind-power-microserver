"""系统能力清单。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping


def _capability(
    capability_id: str,
    name: str,
    *,
    availability: str,
    maturity: str,
    reason: str,
    action: str | None = None,
    attention_required: bool = False,
    runtime: dict | None = None,
) -> dict:
    result = {
        "id": capability_id,
        "name": name,
        "availability": availability,
        "maturity": maturity,
        "reason": reason,
        "action": action,
        "attention_required": attention_required,
    }
    if runtime is not None:
        result["runtime"] = runtime
    return result


def build_capability_manifest(config: Mapping, runtime: Mapping | None = None) -> dict:
    """根据部署配置生成可供前后端共同使用的能力事实表。"""

    integration_enabled = bool(config.get("INTEGRATION_API_ENABLED", False))
    scada_enabled = bool(config.get("SCADA_REALTIME_ENABLED", False))
    nwp_enabled = bool(config.get("NWP_INGESTION_ENABLED", False))
    integration_required = bool(config.get("INTEGRATION_API_REQUIRED", False))
    scada_required = bool(config.get("SCADA_REQUIRED", False)) or scada_enabled
    nwp_required = bool(config.get("NWP_INGESTION_REQUIRED", False))
    scada_runtime = (runtime or {}).get("scada")

    scada_availability = "available" if scada_enabled else "config_required"
    scada_reason = (
        "当前部署声明已接入 SCADA 数据源"
        if scada_enabled
        else "当前部署没有声明可用的 SCADA 实时数据源"
    )
    if scada_enabled and scada_runtime:
        scada_availability = str(scada_runtime.get("availability", "unavailable"))
        scada_reason = str(scada_runtime.get("reason", "SCADA 运行状态未知"))

    capabilities = [
        _capability(
            "forecasting",
            "功率预测与模型调度",
            availability="available",
            maturity="production",
            reason="预测、校准和模型版本链路已接入数据库调度",
        ),
        _capability(
            "report_delivery",
            "可靠数据上报",
            availability="available",
            maturity="production",
            reason="发件箱、幂等键、重试、死信和恢复机制已启用",
        ),
        _capability(
            "integration_ingest",
            "统一跨区数据接入",
            availability="available" if integration_enabled else "config_required",
            maturity="production",
            reason=(
                "统一数据接入接口已启用"
                if integration_enabled
                else "代码已就绪，当前部署未显式启用接入接口"
            ),
            action=None if integration_enabled else "设置 INTEGRATION_API_ENABLED 和独立接入令牌",
            attention_required=integration_required,
        ),
        _capability(
            "scada_realtime",
            "SCADA 实时数据",
            availability=scada_availability,
            maturity="production",
            reason=scada_reason,
            action=None if scada_enabled else "完成 C104 点表与链路验收后设置 SCADA_REALTIME_ENABLED",
            attention_required=scada_required,
            runtime=scada_runtime,
        ),
        _capability(
            "nwp_ingestion",
            "数值天气预报数据接入",
            availability="available" if nwp_enabled else "config_required",
            maturity="production",
            reason=(
                "当前部署声明已接入 NWP 数据源"
                if nwp_enabled
                else "当前部署没有声明可用的内网 NWP 数据源"
            ),
            action=None if nwp_enabled else "配置电力分区数据通道后设置 NWP_INGESTION_ENABLED",
            attention_required=nwp_required,
        ),
        _capability(
            "extreme_weather",
            "极端天气实时检测",
            availability="unavailable",
            maturity="placeholder",
            reason="阈值配置已实现，实时天气输入和历史事件持久化尚未接通",
            action="接通实时天气输入和告警事件存储后再启用",
        ),
    ]
    counts = {
        status: sum(1 for item in capabilities if item["availability"] == status)
        for status in ("available", "degraded", "config_required", "unavailable")
    }
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deployment_mode": str(config.get("DEPLOYMENT_MODE", "development")),
        "counts": counts,
        "capabilities": capabilities,
    }
