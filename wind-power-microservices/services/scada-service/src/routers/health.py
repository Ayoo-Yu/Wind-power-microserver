"""
SCADA Service Health Check API endpoints.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ..database import get_db_session
from ..models import HealthResponse, ErrorResponse
from ..services import ConnectionManager
from ..exceptions import DatabaseConnectionException

router = APIRouter(prefix="/health", tags=["health"])

# Global connection manager instance
connection_manager = ConnectionManager()


@router.get(
    "",
    response_model=HealthResponse,
    summary="Health check",
    description="Basic health check endpoint for SCADA service",
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy", "model": ErrorResponse}
    }
)
async def health_check(
    db: AsyncSession = Depends(get_db_session)
):
    """Basic health check."""
    try:
        # Check database connectivity
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))

        # Check InfluxDB connectivity
        influxdb_healthy = True
        try:
            await connection_manager.influxdb_manager.ping()
        except Exception:
            influxdb_healthy = False

        # Check Kafka connectivity
        kafka_healthy = True
        try:
            await connection_manager.kafka_manager.ping()
        except Exception:
            kafka_healthy = False

        # Determine overall health
        is_healthy = influxdb_healthy and kafka_healthy
        status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

        return HealthResponse(
            status="healthy" if is_healthy else "unhealthy",
            timestamp=datetime.utcnow(),
            service="scada-service",
            version="1.0.0",
            dependencies={
                "database": "healthy",
                "influxdb": "healthy" if influxdb_healthy else "unhealthy",
                "kafka": "healthy" if kafka_healthy else "unhealthy"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )


@router.get(
    "/detailed",
    response_model=Dict[str, Any],
    summary="Detailed health check",
    description="Detailed health check with component-specific information",
    responses={
        200: {"description": "Detailed health status retrieved successfully"},
        503: {"description": "Service components are unhealthy", "model": ErrorResponse}
    }
)
async def detailed_health_check(
    db: AsyncSession = Depends(get_db_session)
):
    """Detailed health check with component information."""
    try:
        health_status = {
            "service": "scada-service",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {}
        }

        # Check database
        try:
            from sqlalchemy import text
            start_time = datetime.utcnow()
            await db.execute(text("SELECT 1"))
            db_response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            health_status["components"]["database"] = {
                "status": "healthy",
                "response_time_ms": round(db_response_time, 2),
                "details": "Database connection successful"
            }
        except Exception as e:
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
                "details": "Database connection failed"
            }

        # Check InfluxDB
        try:
            start_time = datetime.utcnow()
            await connection_manager.influxdb_manager.ping()
            influxdb_response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            health_status["components"]["influxdb"] = {
                "status": "healthy",
                "response_time_ms": round(influxdb_response_time, 2),
                "details": "InfluxDB connection successful"
            }
        except Exception as e:
            health_status["components"]["influxdb"] = {
                "status": "unhealthy",
                "error": str(e),
                "details": "InfluxDB connection failed"
            }

        # Check Kafka
        try:
            start_time = datetime.utcnow()
            await connection_manager.kafka_manager.ping()
            kafka_response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            health_status["components"]["kafka"] = {
                "status": "healthy",
                "response_time_ms": round(kafka_response_time, 2),
                "details": "Kafka connection successful"
            }
        except Exception as e:
            health_status["components"]["kafka"] = {
                "status": "unhealthy",
                "error": str(e),
                "details": "Kafka connection failed"
            }

        # Check connection manager
        try:
            connection_stats = connection_manager.get_connection_statistics()
            health_status["components"]["connection_manager"] = {
                "status": "healthy",
                "total_connections": connection_stats.get("total_connections", 0),
                "active_connections": connection_stats.get("active_connections", 0),
                "details": "Connection manager operational"
            }
        except Exception as e:
            health_status["components"]["connection_manager"] = {
                "status": "unhealthy",
                "error": str(e),
                "details": "Connection manager error"
            }

        # Determine overall health
        unhealthy_components = [
            name for name, component in health_status["components"].items()
            if component["status"] != "healthy"
        ]

        health_status["overall_status"] = "healthy" if not unhealthy_components else "unhealthy"
        health_status["unhealthy_components"] = unhealthy_components

        # Return appropriate status code
        status_code = status.HTTP_200_OK if not unhealthy_components else status.HTTP_503_SERVICE_UNAVAILABLE

        return health_status

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Detailed health check failed: {str(e)}"
        )


@router.get(
    "/ready",
    response_model=Dict[str, Any],
    summary="Readiness check",
    description="Check if the service is ready to accept requests",
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready", "model": ErrorResponse}
    }
)
async def readiness_check(
    db: AsyncSession = Depends(get_db_session)
):
    """Readiness check for Kubernetes."""
    try:
        # Check if service is initialized
        if not hasattr(connection_manager, 'influxdb_manager'):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not initialized"
            )

        # Check database connectivity
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))

        # Check external dependencies
        dependencies_ready = True
        dependency_status = {}

        # Check InfluxDB
        try:
            await connection_manager.influxdb_manager.ping()
            dependency_status["influxdb"] = "ready"
        except Exception as e:
            dependency_status["influxdb"] = f"not ready: {str(e)}"
            dependencies_ready = False

        # Check Kafka
        try:
            await connection_manager.kafka_manager.ping()
            dependency_status["kafka"] = "ready"
        except Exception as e:
            dependency_status["kafka"] = f"not ready: {str(e)}"
            dependencies_ready = False

        if dependencies_ready:
            return {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat(),
                "dependencies": dependency_status
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "not ready",
                    "dependencies": dependency_status
                }
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Readiness check failed: {str(e)}"
        )


@router.get(
    "/live",
    response_model=Dict[str, Any],
    summary="Liveness check",
    description="Check if the service is alive (lightweight check)",
    responses={
        200: {"description": "Service is alive"},
        503: {"description": "Service is not alive", "model": ErrorResponse}
    }
)
async def liveness_check():
    """Liveness check for Kubernetes."""
    try:
        # Simple liveness check - service is running
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "scada-service"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Liveness check failed: {str(e)}"
        )


@router.get(
    "/startup",
    response_model=Dict[str, Any],
    summary="Startup check",
    description="Check if the service has completed startup successfully",
    responses={
        200: {"description": "Service has started successfully"},
        503: {"description": "Service startup incomplete", "model": ErrorResponse}
    }
)
async def startup_check(
    db: AsyncSession = Depends(get_db_session)
):
    """Startup check for Kubernetes."""
    try:
        # Check if connection manager is properly initialized
        if not connection_manager.influxdb_manager.client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="InfluxDB manager not initialized"
            )

        # Check database schema
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        tables = inspector.get_table_names()

        required_tables = ["scada_connections", "data_points", "alarms"]
        missing_tables = [table for table in required_tables if table not in tables]

        if missing_tables:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Missing database tables: {missing_tables}"
            )

        return {
            "status": "started",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "scada-service",
            "version": "1.0.0",
            "database_tables": tables
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Startup check failed: {str(e)}"
        )