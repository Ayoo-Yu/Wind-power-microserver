"""系统能力清单接口。"""

from flask import Blueprint, current_app, jsonify

from services.capability_service import build_capability_manifest


capability_bp = Blueprint(
    "capability",
    __name__,
    url_prefix="/api/v1/system",
)


@capability_bp.get("/capabilities")
def get_capabilities():
    return jsonify(build_capability_manifest(current_app.config))
