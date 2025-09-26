"""
Health check endpoints for Wind Farm Management Service.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session, health_check as db_health_check
from ..utils import RedisManager, get_logger
from ..config import get_settings

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Health check",
    description="Check the health status of the wind farm management service",
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy"}
    }
)
async def health_check(
    db: AsyncSession = Depends(get_db_session)
):
    """Health check endpoint."""
    try:
        # Check database health
        db_healthy = await db_health_check()

        # Check Redis health
        redis_manager = RedisManager()
        redis_healthy = await redis_manager.health_check()

        # Overall health status
        overall_healthy = db_healthy and redis_healthy

        health_status = {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": "2024-01-01T00:00:00Z",  # Will be replaced with actual timestamp
            "services": {
                "database": {
                    "status": "healthy" if db_healthy else "unhealthy",
                    "message": "Database connection is working" if db_healthy else "Database connection failed"
                },
                "redis": {
                    "status": "healthy" if redis_healthy else "unhealthy",
                    "message": "Redis connection is working" if redis_healthy else "Redis connection failed"
                }
            }
        }

        if overall_healthy:
            return health_status
        else:
            raise HTTPException(status_code=503, detail=health_status)

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "timestamp": "2024-01-01T00:00:00Z",
                "error": str(e),
                "services": {
                    "database": {"status": "unknown", "message": "Health check failed"},
                    "redis": {"status": "unknown", "message": "Health check failed"}
                }
            }
        )


@router.get(
    "/ready",
    response_model=Dict[str, str],
    summary="Readiness check",
    description="Check if the service is ready to accept requests",
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready"}
    }
)
async def readiness_check(
    db: AsyncSession = Depends(get_db_session)
):
    """Readiness check endpoint."""
    try:
        # Check database connectivity
        db_healthy = await db_health_check()

        if db_healthy:
            return {
                "status": "ready",
                "message": "Service is ready to accept requests"
            }
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "not_ready",
                    "message": "Database connection is not available"
                }
            )

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "message": f"Service is not ready: {str(e)}"
            }
        )


@router.get(
    "/live",
    response_model=Dict[str, str],
    summary="Liveness check",
    description="Check if the service is alive",
    responses={
        200: {"description": "Service is alive"}
    }
)
async def liveness_check():
    """Liveness check endpoint."""
    return {
        "status": "alive",
        "message": "Service is running",
        "service": "wind-farm-management-service"
    }


@router.get(
    "/dependencies",
    response_model=Dict[str, Any],
    summary="Dependency health check",
    description="Check the health of all service dependencies",
    responses={
        200: {"description": "Dependencies are healthy"},
        503: {"description": "Some dependencies are unhealthy"}
    }
)
async def dependency_health_check(
    db: AsyncSession = Depends(get_db_session)
):
    """Dependency health check endpoint."""
    try:
        settings = get_settings()

        # Check database
        db_healthy = await db_health_check()

        # Check Redis
        redis_manager = RedisManager()
        redis_healthy = await redis_manager.health_check()

        # Build dependency status
        dependencies = {
            "database": {
                "name": "PostgreSQL Database",
                "status": "healthy" if db_healthy else "unhealthy",
                "connection_string": settings.database_url.replace("://", "://***@", 1) if settings.database_url else "not configured",
                "message": "Database is accessible" if db_healthy else "Database connection failed"
            },
            "redis": {
                "name": "Redis Cache",
                "status": "healthy" if redis_healthy else "unhealthy",
                "url": settings.redis_url.replace("://", "://***@", 1) if settings.redis_url else "not configured",
                "message": "Redis is accessible" if redis_healthy else "Redis connection failed"
            }
        }

        # Overall status
        all_healthy = all(dep["status"] == "healthy" for dep in dependencies.values())

        response = {
            "status": "healthy" if all_healthy else "unhealthy",
            "timestamp": "2024-01-01T00:00:00Z",  # Will be replaced with actual timestamp
            "dependencies": dependencies
        }

        if all_healthy:
            return response
        else:
            raise HTTPException(status_code=503, detail=response)

    except Exception as e:
        logger.error(f"Dependency health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "timestamp": "2024-01-01T00:00:00Z",
                "error": str(e),
                "dependencies": {}
            }
        )


@router.get(
    "/metrics",
    response_model=Dict[str, Any],
    summary="Service metrics",
    description="Get basic service metrics and statistics",
    responses={
        200: {"description": "Metrics retrieved successfully"}
    }
)
async def get_metrics(
    db: AsyncSession = Depends(get_db_session)
):
    """Get service metrics."""
    try:
        from sqlalchemy import select, func
        from ..database import WindFarm, WindTurbine, User

        # Get database statistics
        wind_farm_count_result = await db.execute(select(func.count(WindFarm.id)))
        wind_farm_count = wind_farm_count_result.scalar()

        turbine_count_result = await db.execute(select(func.count(WindTurbine.id)))
        turbine_count = turbine_count_result.scalar()

        user_count_result = await db.execute(select(func.count(User.id)))
        user_count = user_count_result.scalar()

        # Get active wind farms
        active_wind_farms_result = await db.execute(
            select(func.count(WindFarm.id)).where(WindFarm.status == "active")
        )
        active_wind_farms = active_wind_farms_result.scalar()

        # Get running turbines
        running_turbines_result = await db.execute(
            select(func.count(WindTurbine.id)).where(WindTurbine.status == "running")
        )
        running_turbines = running_turbines_result.scalar()

        return {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",  # Will be replaced with actual timestamp
            "metrics": {
                "wind_farms": {
                    "total": wind_farm_count,
                    "active": active_wind_farms,
                    "inactive": wind_farm_count - active_wind_farms
                },
                "turbines": {
                    "total": turbine_count,
                    "running": running_turbines,
                    "stopped": turbine_count - running_turbines
                },
                "users": {
                    "total": user_count
                }
            }
        }

    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        return {
            "status": "error",
            "timestamp": "2024-01-01T00:00:00Z",
            "error": str(e),
            "metrics": {}
        }