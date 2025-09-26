"""
Health check endpoints for Tenant Management Service.
"""

from fastapi import APIRouter, Depends
from datetime import datetime
from typing import Dict, Any

from ..config import get_settings
from ..database import health_check
from ..utils import get_logger
from ..utils import create_redis_manager


router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check - indicates if the service is ready to handle requests.
    """
    try:
        # Check database
        db_healthy = await health_check()

        # Check Redis
        redis_manager = create_redis_manager()
        redis_healthy = await redis_manager.health_check()

        if db_healthy and redis_healthy:
            return {
                "status": "ready",
                "service": settings.service_name,
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {
                    "database": "ready",
                    "redis": "ready",
                }
            }
        else:
            return {
                "status": "not_ready",
                "service": settings.service_name,
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {
                    "database": "ready" if db_healthy else "not_ready",
                    "redis": "ready" if redis_healthy else "not_ready",
                }
            }

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "status": "not_ready",
            "service": settings.service_name,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "checks": {
                "database": "unknown",
                "redis": "unknown",
            }
        }


@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness check - indicates if the service is alive.
    """
    return {
        "status": "alive",
        "service": settings.service_name,
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": "unknown",  # Could be implemented with process start time
    }


@router.get("/startup")
async def startup_check() -> Dict[str, Any]:
    """
    Startup check - indicates if the service has successfully started.
    """
    return {
        "status": "started",
        "service": settings.service_name,
        "version": settings.service_version,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/dependencies")
async def dependencies_check() -> Dict[str, Any]:
    """
    Dependencies check - checks all external dependencies.
    """
    dependencies = {}
    overall_status = "healthy"

    try:
        # Check database
        db_healthy = await health_check()
        dependencies["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "type": "postgresql",
            "connection_string": settings.database_url.replace("://*@", "://***@"),  # Hide password
        }
        if not db_healthy:
            overall_status = "unhealthy"

    except Exception as e:
        dependencies["database"] = {
            "status": "unhealthy",
            "type": "postgresql",
            "error": str(e),
        }
        overall_status = "unhealthy"

    try:
        # Check Redis
        redis_manager = create_redis_manager()
        redis_healthy = await redis_manager.health_check()
        dependencies["redis"] = {
            "status": "healthy" if redis_healthy else "unhealthy",
            "type": "redis",
            "url": settings.redis_url,
        }
        if not redis_healthy:
            overall_status = "unhealthy"

    except Exception as e:
        dependencies["redis"] = {
            "status": "unhealthy",
            "type": "redis",
            "error": str(e),
        }
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "service": settings.service_name,
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": dependencies,
    }