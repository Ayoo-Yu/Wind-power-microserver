"""系统能力清单。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping

from db_models import IngestionBatch, WindFarm


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
    scada_required = bool(config.get("SCADA_REQUIRED", False))
    nwp_required = bool(config.get("NWP_INGESTION_REQUIRED", False))
    scada_runtime = (runtime or {}).get("scada")
    nwp_runtime = (runtime or {}).get("nwp")

    scada_availability = "available" if scada_enabled else "config_required"
    scada_reason = (
        "当前部署声明已接入 SCADA 数据源"
        if scada_enabled
        else "当前部署没有声明可用的 SCADA 实时数据源"
    )
    if scada_enabled and scada_runtime:
        scada_availability = str(scada_runtime.get("availability", "unavailable"))
        scada_reason = str(scada_runtime.get("reason", "SCADA 运行状态未知"))

    nwp_availability = "available" if nwp_enabled else "config_required"
    nwp_reason = (
        "当前部署声明已接入 NWP 数据源"
        if nwp_enabled
        else "当前部署没有声明可用的内网 NWP 数据源"
    )
    if nwp_enabled and nwp_runtime:
        nwp_availability = str(nwp_runtime.get("availability", "unavailable"))
        nwp_reason = str(nwp_runtime.get("reason", "NWP 运行状态未知"))

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
            availability=nwp_availability,
            maturity="production",
            reason=nwp_reason,
            action=None if nwp_enabled else "配置电力分区数据通道后设置 NWP_INGESTION_ENABLED",
            attention_required=nwp_required,
            runtime=nwp_runtime,
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


def build_nwp_runtime_snapshot(
    session,
    config: Mapping,
    *,
    now: datetime | None = None,
) -> dict:
    """根据已完成业务批次判断 NWP 的覆盖范围、新鲜度和质量。"""
    effective_now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    stale_after_seconds = int(config.get("NWP_DATA_STALE_AFTER_SECONDS", 21600))
    expected_farms = [
        str(row[0])
        for row in session.query(WindFarm.farm_code)
        .filter(WindFarm.is_active.is_(True))
        .order_by(WindFarm.farm_code)
        .all()
    ]
    batches = (
        session.query(IngestionBatch)
        .filter(
            IngestionBatch.source_type == "nwp",
            IngestionBatch.status == "completed",
        )
        .order_by(IngestionBatch.completed_at.desc(), IngestionBatch.id.desc())
        .limit(max(200, len(expected_farms) * 4))
        .all()
    )
    latest_by_farm = {}
    for batch in batches:
        latest_by_farm.setdefault(batch.farm_code, batch)
    if not expected_farms:
        expected_farms = sorted(latest_by_farm)

    items = []
    missing_farms = []
    stale_farms = []
    degraded_farms = []
    cutoff = effective_now - timedelta(seconds=stale_after_seconds)
    for farm_code in expected_farms:
        batch = latest_by_farm.get(farm_code)
        if batch is None:
            missing_farms.append(farm_code)
            items.append({"farm_code": farm_code, "state": "missing"})
            continue
        completed_at = batch.completed_at or batch.received_at
        if completed_at is None or completed_at < cutoff:
            state = "stale"
            stale_farms.append(farm_code)
        elif batch.quality_status != "good" or batch.accepted_count <= 0:
            state = "degraded"
            degraded_farms.append(farm_code)
        else:
            state = "healthy"
        items.append({
            "farm_code": farm_code,
            "state": state,
            "batch_id": batch.id,
            "message_id": batch.message_id,
            "completed_at": completed_at.isoformat() if completed_at else None,
            "accepted_count": batch.accepted_count,
            "rejected_count": batch.rejected_count,
        })

    if not expected_farms or missing_farms:
        availability = "unavailable"
        reason = f"NWP 业务批次缺失，缺少 {len(missing_farms) or '全部'} 个场站"
    elif stale_farms or degraded_farms:
        availability = "degraded"
        reason = f"NWP 批次存在 {len(stale_farms)} 个过期场站和 {len(degraded_farms)} 个质量降级场站"
    else:
        availability = "available"
        reason = f"{len(expected_farms)} 个场站的 NWP 业务批次均已就绪"

    return {
        "availability": availability,
        "reason": reason,
        "stale_after_seconds": stale_after_seconds,
        "expected_farm_count": len(expected_farms),
        "missing_farms": missing_farms,
        "stale_farms": stale_farms,
        "degraded_farms": degraded_farms,
        "farms": items,
    }
