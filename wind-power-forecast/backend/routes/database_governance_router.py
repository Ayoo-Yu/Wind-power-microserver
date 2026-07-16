"""管理员数据库治理只读接口。"""

import logging

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from database_config import ensure_engine
from utils.authorization import permission_required
from services.database_governance_service import build_database_overview


logger = logging.getLogger(__name__)
database_governance_bp = Blueprint("database_governance", __name__)


@database_governance_bp.route("/database/overview", methods=["GET"])
@jwt_required()
@permission_required("system_maintenance")
def get_database_overview():
    """返回数据库结构、容量和增长情况。"""
    engine = ensure_engine()
    if engine is None:
        return jsonify({"message": "数据库连接不可用"}), 503

    try:
        return jsonify(build_database_overview(engine))
    except Exception as exc:
        logger.error("获取数据库治理概览失败: %s", exc, exc_info=True)
        return jsonify({"message": "获取数据库治理概览失败"}), 500
