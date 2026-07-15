"""系统能力清单接口。"""

from flask import Blueprint, current_app, jsonify

from db_session import db_session
from services.capability_service import (
    build_capability_manifest,
    build_nwp_runtime_snapshot,
)
from services.scada_health_service import build_scada_health_snapshot


capability_bp = Blueprint(
    "capability",
    __name__,
    url_prefix="/api/v1/system",
)


@capability_bp.get("/capabilities")
def get_capabilities():
    runtime = {}
    if current_app.config.get("SCADA_REALTIME_ENABLED", False):
        try:
            with db_session() as db:
                runtime["scada"] = build_scada_health_snapshot(
                    db, current_app.config
                )
        except Exception as exc:
            current_app.logger.exception("SCADA 运行态能力查询失败")
            runtime["scada"] = {
                "availability": "unavailable",
                "reason": "SCADA 运行态查询失败",
                "error": str(exc),
                "connections": [],
            }
    if current_app.config.get("NWP_INGESTION_ENABLED", False):
        try:
            with db_session() as db:
                runtime["nwp"] = build_nwp_runtime_snapshot(db, current_app.config)
        except Exception as exc:
            current_app.logger.exception("NWP 运行态能力查询失败")
            runtime["nwp"] = {
                "availability": "unavailable",
                "reason": "NWP 运行态查询失败",
                "error": str(exc),
                "farms": [],
            }
    return jsonify(build_capability_manifest(current_app.config, runtime))
