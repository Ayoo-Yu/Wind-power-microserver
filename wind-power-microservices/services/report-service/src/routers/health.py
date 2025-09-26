"""
Health check router for Report Service
"""

from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services import health_service
from ..utils import get_logger, create_success_response, create_error_response

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    """Basic health check endpoint."""
    try:
        return {
            "status": "healthy",
            "service": "report-service",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@router.get("/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check with system information."""
    try:
        logger.info("Running detailed health check")

        health_data = await health_service.get_detailed_health(db)

        # Determine overall status
        if health_data["database"]["status"] == "healthy" and \
           health_data["chart_generator"]["status"] == "healthy":
            overall_status = "healthy"
            status_code = 200
        else:
            overall_status = "unhealthy"
            status_code = 503

        response = {
            "status": overall_status,
            "service": "report-service",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "checks": health_data
        }

        if status_code == 503:
            raise HTTPException(status_code=503, detail=response)

        return response

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "report-service",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Kubernetes readiness probe."""
    try:
        logger.info("Running readiness check")

        is_ready = await health_service.is_service_ready(db)

        if is_ready:
            return {
                "status": "ready",
                "service": "report-service",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "not_ready",
                    "service": "report-service",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "service": "report-service",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )


@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe."""
    try:
        logger.info("Running liveness check")

        is_alive = await health_service.is_service_alive()

        if is_alive:
            return {
                "status": "alive",
                "service": "report-service",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "dead",
                    "service": "report-service",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "dead",
                "service": "report-service",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )


@router.get("/startup")
async def startup_check(db: AsyncSession = Depends(get_db)):
    """Check if service has completed startup."""
    try:
        logger.info("Running startup check")

        startup_status = await health_service.get_startup_status(db)

        if startup_status["status"] == "completed":
            return startup_status
        else:
            raise HTTPException(
                status_code=503,
                detail=startup_status
            )

    except Exception as e:
        logger.error(f"Startup check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "failed",
                "service": "report-service",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )


@router.get("/external-services")
async def external_services_health():
    """Check health of external service dependencies."""
    try:
        logger.info("Checking external services health")

        external_health = await health_service.check_external_services()

        # Determine overall status
        all_healthy = all(service["status"] == "healthy" for service in external_health.values())
        overall_status = "healthy" if all_healthy else "degraded"

        response = {
            "status": overall_status,
            "service": "report-service",
            "timestamp": datetime.utcnow().isoformat(),
            "external_services": external_health
        }

        if not all_healthy:
            raise HTTPException(status_code=503, detail=response)

        return response

    except Exception as e:
        logger.error(f"External services health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "report-service",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )


@router.get("/database")
async def database_health(db: AsyncSession = Depends(get_db)):
    """Check database health specifically."""
    try:
        logger.info("Running database health check")

        db_health = await health_service.check_database_health(db)

        if db_health["status"] == "healthy":
            return {
                "status": "healthy",
                "service": "report-service-database",
                "timestamp": datetime.utcnow().isoformat(),
                "details": db_health
            }
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "unhealthy",
                    "service": "report-service-database",
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": db_health
                }
            )

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "report-service-database",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )


@router.get("/resources")
async def resource_usage():
    """Get current resource usage information."""
    try:
        logger.info("Getting resource usage")

        resources = await health_service.get_resource_usage()

        return {
            "status": "healthy",
            "service": "report-service",
            "timestamp": datetime.utcnow().isoformat(),
            "resources": resources
        }

    except Exception as e:
        logger.error(f"Resource usage check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "service": "report-service",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )


@router.get("/dependencies")
async def dependency_versions():
    """Get versions of key dependencies."""
    try:
        logger.info("Getting dependency versions")

        dependencies = await health_service.get_dependency_versions()

        return {
            "status": "healthy",
            "service": "report-service",
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": dependencies
        }

    except Exception as e:
        logger.error(f"Dependency versions check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "service": "report-service",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )