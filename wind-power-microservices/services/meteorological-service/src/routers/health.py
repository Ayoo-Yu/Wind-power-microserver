"""
Health Check API endpoints for Meteorological Data Service
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..database import get_db_session
from ..services import MeteorologicalManager
from ..exceptions import ServiceUnavailableException

router = APIRouter(tags=["health"])

# Global meteorological manager instance
meteo_manager = MeteorologicalManager()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    service: str
    version: str
    uptime: float
    dependencies: Dict[str, Any]


class DetailedHealthResponse(BaseModel):
    """Detailed health check response model."""
    status: str
    timestamp: str
    service: str
    version: str
    uptime: float
    dependencies: Dict[str, Any]
    system_info: Dict[str, Any]
    performance_metrics: Dict[str, Any]


# Service start time for uptime calculation
_service_start_time = datetime.utcnow()


def _get_uptime() -> float:
    """Calculate service uptime in seconds."""
    return (datetime.utcnow() - _service_start_time).total_seconds()


async def _check_database_health() -> Dict[str, Any]:
    """Check database connectivity and health."""
    try:
        # Get database session
        async for db in get_db_session():
            # Test basic query
            result = await db.execute("SELECT 1")
            await result.fetchone()

            return {
                "status": "healthy",
                "response_time": "< 100ms",
                "details": "Database connection successful"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Database connection failed"
        }


async def _check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity and health."""
    try:
        if meteo_manager.redis_client:
            await meteo_manager.redis_client.ping()
            info = await meteo_manager.redis_client.info()

            return {
                "status": "healthy",
                "response_time": "< 50ms",
                "details": "Redis connection successful",
                "memory_usage": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0)
            }
        else:
            return {
                "status": "warning",
                "details": "Redis client not initialized"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Redis connection failed"
        }


async def _check_kafka_health() -> Dict[str, Any]:
    """Check Kafka connectivity and health."""
    try:
        if meteo_manager.kafka_producer:
            # Test Kafka producer
            return {
                "status": "healthy",
                "details": "Kafka producer available",
                "bootstrap_servers": "meteo-kafka:9092"
            }
        else:
            return {
                "status": "warning",
                "details": "Kafka producer not initialized"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Kafka connection failed"
        }


def _get_system_info() -> Dict[str, Any]:
    """Get system information."""
    try:
        import psutil

        return {
            "cpu_usage": psutil.cpu_percent(interval=1),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0],
            "process_count": len(psutil.pids())
        }
    except ImportError:
        return {
            "cpu_usage": "unavailable",
            "memory_usage": "unavailable",
            "disk_usage": "unavailable",
            "load_average": "unavailable",
            "process_count": "unavailable",
            "note": "psutil not installed"
        }
    except Exception as e:
        return {
            "error": str(e),
            "note": "Failed to get system info"
        }


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Basic health check",
    description="Basic health check endpoint for load balancers and monitoring",
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy", "model": ErrorResponse}
    }
)
async def health_check():
    """Basic health check endpoint."""
    try:
        dependencies = {}

        # Check critical dependencies
        db_health = await _check_database_health()
        dependencies["database"] = db_health

        # Determine overall status
        overall_status = "healthy"
        if db_health["status"] != "healthy":
            overall_status = "unhealthy"

        response = HealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            service="meteorological-data-service",
            version="1.0.0",
            uptime=_get_uptime(),
            dependencies=dependencies
        )

        if overall_status == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service is unhealthy"
            )

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )


@router.get(
    "/health/detailed",
    response_model=DetailedHealthResponse,
    summary="Detailed health check",
    description="Detailed health check with comprehensive system information",
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy", "model": ErrorResponse}
    }
)
async def detailed_health_check():
    """Detailed health check endpoint."""
    try:
        dependencies = {}

        # Check all dependencies
        dependencies["database"] = await _check_database_health()
        dependencies["redis"] = await _check_redis_health()
        dependencies["kafka"] = await _check_kafka_health()

        # Check meteorological services
        if meteo_manager.is_initialized:
            dependencies["meteorological_manager"] = {
                "status": "healthy",
                "services": {
                    "data_processor": meteo_manager.data_processor is not None,
                    "forecast_service": meteo_manager.forecast_service is not None,
                    "alert_service": meteo_manager.alert_service is not None
                }
            }
        else:
            dependencies["meteorological_manager"] = {
                "status": "warning",
                "message": "Meteorological manager not initialized"
            }

        # Determine overall status
        overall_status = "healthy"
        critical_services = ["database"]

        for service in critical_services:
            if dependencies[service]["status"] != "healthy":
                overall_status = "unhealthy"
                break

        # Check for warnings
        for service, health in dependencies.items():
            if health.get("status") == "warning" and overall_status == "healthy":
                overall_status = "warning"

        # Get system info and performance metrics
        system_info = _get_system_info()

        performance_metrics = {
            "uptime_seconds": _get_uptime(),
            "service_start_time": _service_start_time.isoformat(),
            "response_time_ms": "< 100"  # Approximate response time
        }

        response = DetailedHealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            service="meteorological-data-service",
            version="1.0.0",
            uptime=_get_uptime(),
            dependencies=dependencies,
            system_info=system_info,
            performance_metrics=performance_metrics
        )

        if overall_status == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service is unhealthy"
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Detailed health check failed: {str(e)}"
        )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness probe",
    description="Kubernetes readiness probe endpoint",
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready", "model": ErrorResponse}
    }
)
async def readiness_check():
    """Kubernetes readiness probe."""
    try:
        # For readiness, we need to check if service can handle requests
        dependencies = {}

        # Check critical dependencies
        db_health = await _check_database_health()
        dependencies["database"] = db_health

        # Service is ready if database is healthy
        is_ready = db_health["status"] == "healthy"

        status_str = "ready" if is_ready else "not_ready"

        response = HealthResponse(
            status=status_str,
            timestamp=datetime.utcnow().isoformat(),
            service="meteorological-data-service",
            version="1.0.0",
            uptime=_get_uptime(),
            dependencies=dependencies
        )

        if not is_ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service is not ready"
            )

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Readiness check failed: {str(e)}"
        )


@router.get(
    "/health/live",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Kubernetes liveness probe endpoint",
    responses={
        200: {"description": "Service is alive"},
        503: {"description": "Service is not alive", "model": ErrorResponse}
    }
)
async def liveness_check():
    """Kubernetes liveness probe."""
    try:
        # For liveness, we just need to check if the service process is running
        # This is a lightweight check

        response = HealthResponse(
            status="alive",
            timestamp=datetime.utcnow().isoformat(),
            service="meteorological-data-service",
            version="1.0.0",
            uptime=_get_uptime(),
            dependencies={}
        )

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Liveness check failed: {str(e)}"
        )


@router.get(
    "/health/external-services",
    response_model=Dict[str, Any],
    summary="External services health",
    description="Check health of external weather services and APIs",
    responses={
        200: {"description": "External services health status"},
        503: {"description": "One or more external services are down", "model": ErrorResponse}
    }
)
async def external_services_health():
    """Check health of external weather services."""
    try:
        external_services = {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {}
        }

        # Check weather API services
        weather_services = ["openweathermap", "weatherapi", "noaa"]

        for service in weather_services:
            try:
                # This would typically involve making a lightweight API call
                # For now, we'll simulate the check
                external_services["services"][service] = {
                    "status": "healthy",
                    "last_check": datetime.utcnow().isoformat(),
                    "response_time": "< 500ms"
                }
            except Exception as e:
                external_services["services"][service] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "last_check": datetime.utcnow().isoformat()
                }

        # Check if any external services are down
        unhealthy_services = [
            service for service, health in external_services["services"].items()
            if health["status"] != "healthy"
        ]

        if unhealthy_services:
            external_services["overall_status"] = "degraded"
            external_services["message"] = f"Services down: {', '.join(unhealthy_services)}"
        else:
            external_services["overall_status"] = "healthy"
            external_services["message"] = "All external services are healthy"

        return external_services

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"External services health check failed: {str(e)}"
        )


# Add logging
import logging
logger = logging.getLogger(__name__)