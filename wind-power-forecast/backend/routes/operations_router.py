"""现场运维总览和预测输入追溯接口。"""

import logging
import os

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from config import Config
from db_session import db_session
from routes.auth import permission_required
from services.operations_overview_service import (
    build_operations_overview,
    list_prediction_input_snapshots,
)


logger = logging.getLogger(__name__)
operations_bp = Blueprint("operations", __name__, url_prefix="/api/v1/operations")


@operations_bp.route("/overview", methods=["GET"])
@jwt_required()
@permission_required("view_alarm_center")
def get_operations_overview():
    farm_code = str(request.args.get("farm_code") or "").strip() or None
    storage_path = os.environ.get(
        "RUNTIME_STORAGE_PATH",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "runtime")),
    )
    try:
        with db_session() as session:
            result = build_operations_overview(
                session,
                farm_code=farm_code,
                scada_enabled=Config.SCADA_REALTIME_ENABLED,
                scada_required=Config.SCADA_REQUIRED,
                scada_stale_after_seconds=Config.SCADA_DATA_STALE_AFTER_SECONDS,
                nwp_enabled=Config.NWP_INGESTION_ENABLED,
                nwp_required=Config.NWP_INGESTION_REQUIRED,
                nwp_stale_after_seconds=Config.NWP_DATA_STALE_AFTER_SECONDS,
                storage_path=storage_path,
            )
        return jsonify(result)
    except Exception as exc:
        logger.error("获取运维总览失败: %s", exc, exc_info=True)
        return jsonify({"message": "获取运维总览失败"}), 500


@operations_bp.route("/prediction-inputs", methods=["GET"])
@jwt_required()
@permission_required("view_alarm_center")
def get_prediction_inputs():
    farm_code = str(request.args.get("farm_code") or "").strip() or None
    prediction_run_id = request.args.get("prediction_run_id", type=int)
    limit = request.args.get("limit", default=50, type=int)
    try:
        with db_session() as session:
            items = list_prediction_input_snapshots(
                session,
                farm_code=farm_code,
                prediction_run_id=prediction_run_id,
                limit=limit,
            )
        return jsonify({"items": items, "count": len(items)})
    except Exception as exc:
        logger.error("查询预测输入快照失败: %s", exc, exc_info=True)
        return jsonify({"message": "查询预测输入快照失败"}), 500
