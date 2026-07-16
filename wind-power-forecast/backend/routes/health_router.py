"""公开的存活与就绪检查接口。"""

from flask import Blueprint, jsonify

from common.api_response import success
from services.health_service import (
    build_liveness_status,
    build_readiness_status,
    is_ready,
)


health_bp = Blueprint("health", __name__)


def _response(payload: dict, status_code: int):
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response, status_code


@health_bp.get("/health/live")
def liveness():
    """只检查 Web 进程能否响应。"""

    return _response(build_liveness_status(), 200)


@health_bp.get("/health")
@health_bp.get("/health/ready")
def readiness():
    """检查数据库连接和迁移版本是否可承接业务。"""

    status = build_readiness_status()
    return _response(status, 200 if is_ready(status) else 503)


@health_bp.get("/api/v1/health/live")
def liveness_v1():
    """返回统一响应格式的存活状态。"""

    status = build_liveness_status()
    return _response(success(data=status, message="ok"), 200)


@health_bp.get("/api/v1/health")
@health_bp.get("/api/v1/health/ready")
def readiness_v1():
    """返回统一响应格式的就绪状态。"""

    status = build_readiness_status()
    ready = is_ready(status)
    payload = success(
        data=status,
        message="ok" if ready else "not_ready",
        code=0 if ready else 1503,
    )
    return _response(payload, 200 if ready else 503)
