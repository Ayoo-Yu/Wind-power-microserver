"""
System Monitoring API endpoints for Meteorological Data Service
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session
from ..models import SuccessResponse, ErrorResponse
from ..services import MeteorologicalManager
from ..auth import get_current_user, require_operator
from ..exceptions import ValidationException

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

# Global meteorological manager instance
meteo_manager = MeteorologicalManager()


@router.get(
    "/status",
    response_model=Dict[str, Any],
    summary="Get system status",
    description="Get comprehensive system status and health information",
    responses={
        200: {"description": "System status retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_system_status(
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get comprehensive system status."""
    try:
        status_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "meteorological-data-service",
            "version": "1.0.0",
            "status": "operational",
            "components": {}
        }

        # Check database connectivity
        try:
            # Test database connection
            await db.execute("SELECT 1")
            status_info["components"]["database"] = {
                "status": "healthy",
                "message": "Database connection successful"
            }
        except Exception as e:
            status_info["components"]["database"] = {
                "status": "unhealthy",
                "message": f"Database connection failed: {str(e)}"
            }
            status_info["status"] = "degraded"

        # Check Redis connectivity
        try:
            if meteo_manager.redis_client:
                await meteo_manager.redis_client.ping()
                status_info["components"]["redis"] = {
                    "status": "healthy",
                    "message": "Redis connection successful"
                }
            else:
                status_info["components"]["redis"] = {
                    "status": "warning",
                    "message": "Redis client not initialized"
                }
        except Exception as e:
            status_info["components"]["redis"] = {
                "status": "unhealthy",
                "message": f"Redis connection failed: {str(e)}"
            }
            status_info["status"] = "degraded"

        # Check Kafka connectivity
        try:
            if meteo_manager.kafka_producer:
                # Test Kafka producer
                status_info["components"]["kafka"] = {
                    "status": "healthy",
                    "message": "Kafka producer available"
                }
            else:
                status_info["components"]["kafka"] = {
                    "status": "warning",
                    "message": "Kafka producer not initialized"
                }
        except Exception as e:
            status_info["components"]["kafka"] = {
                "status": "unhealthy",
                "message": f"Kafka connection failed: {str(e)}"
            }
            status_info["status"] = "degraded"

        # Check meteorological services
        if meteo_manager.is_initialized:
            status_info["components"]["meteorological_manager"] = {
                "status": "healthy",
                "message": "Meteorological manager initialized",
                "services": {
                    "data_processor": meteo_manager.data_processor is not None,
                    "forecast_service": meteo_manager.forecast_service is not None,
                    "alert_service": meteo_manager.alert_service is not None
                }
            }
        else:
            status_info["components"]["meteorological_manager"] = {
                "status": "warning",
                "message": "Meteorological manager not initialized"
            }

        return {
            "success": True,
            "message": "System status retrieved successfully",
            "data": status_info
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system status: {str(e)}")


@router.get(
    "/data-quality",
    response_model=Dict[str, Any],
    summary="Get data quality metrics",
    description="Get weather data quality monitoring metrics and statistics",
    responses={
        200: {"description": "Data quality metrics retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_data_quality_metrics(
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    hours: int = Query(24, ge=1, le=168, description="Time period in hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get data quality monitoring metrics."""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        quality_metrics = {
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": hours
            },
            "overall_quality": 0,
            "data_completeness": 0,
            "parameters": {}
        }

        if meteo_manager.is_initialized and meteo_manager.data_processor:
            # Get quality summary from data processor
            quality_summary = await meteo_manager.data_processor.calculate_weather_summary(
                wind_farm_id=wind_farm_id,
                station_id="aggregated",
                start_time=start_time,
                end_time=end_time
            )

            # Calculate quality metrics
            if quality_summary:
                quality_metrics["overall_quality"] = quality_summary.get("quality_score", 0)
                quality_metrics["data_completeness"] = quality_summary.get("completeness", 0)
                quality_metrics["parameters"] = quality_summary.get("parameter_breakdown", {})

        return {
            "success": True,
            "message": "Data quality metrics retrieved successfully",
            "data": quality_metrics
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data quality metrics: {str(e)}")


@router.get(
    "/forecast-accuracy",
    response_model=Dict[str, Any],
    summary="Get forecast accuracy metrics",
    description="Get weather forecast accuracy monitoring and evaluation metrics",
    responses={
        200: {"description": "Forecast accuracy metrics retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_forecast_accuracy_metrics(
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    days: int = Query(7, ge=1, le=30, description="Evaluation period in days"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get forecast accuracy monitoring metrics."""
    try:
        if meteo_manager.is_initialized and meteo_manager.forecast_service:
            accuracy_metrics = await meteo_manager.forecast_service.get_forecast_accuracy_summary(
                wind_farm_id=wind_farm_id,
                days=days
            )

            return {
                "success": True,
                "message": "Forecast accuracy metrics retrieved successfully",
                "data": accuracy_metrics
            }
        else:
            return {
                "success": False,
                "message": "Forecast service not available",
                "data": {
                    "evaluation_period_days": days,
                    "overall_accuracy": 0,
                    "model_accuracies": {},
                    "forecast_horizons": {}
                }
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get forecast accuracy metrics: {str(e)}")


@router.get(
    "/api-health",
    response_model=Dict[str, Any],
    summary="Get API health status",
    description="Get external weather API health and availability status",
    responses={
        200: {"description": "API health status retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_api_health_status(
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get external API health status."""
    try:
        api_health = {
            "timestamp": datetime.utcnow().isoformat(),
            "apis": {}
        }

        # Check weather API sources
        weather_apis = ["openweathermap", "weatherapi", "noaa"]

        for api_name in weather_apis:
            api_health["apis"][api_name] = {
                "status": "unknown",
                "last_success": None,
                "failure_count": 0,
                "response_time": None
            }

        # If we have weather API client, get detailed health info
        if meteo_manager.is_initialized and hasattr(meteo_manager, 'weather_api_client'):
            try:
                health_info = await meteo_manager.weather_api_client.get_api_health()
                api_health["apis"].update(health_info)
            except Exception as e:
                api_health["error"] = f"Failed to get API health: {str(e)}"

        return {
            "success": True,
            "message": "API health status retrieved successfully",
            "data": api_health
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get API health status: {str(e)}")


@router.get(
    "/performance",
    response_model=Dict[str, Any],
    summary="Get performance metrics",
    description="Get system performance metrics and statistics",
    responses={
        200: {"description": "Performance metrics retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_performance_metrics(
    hours: int = Query(24, ge=1, le=168, description="Time period in hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Get system performance metrics."""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        performance_metrics = {
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": hours
            },
            "api_performance": {
                "total_requests": 0,
                "average_response_time": 0,
                "error_rate": 0,
                "requests_per_minute": 0
            },
            "data_processing": {
                "records_processed": 0,
                "processing_time_avg": 0,
                "success_rate": 0
            },
            "forecast_performance": {
                "forecasts_generated": 0,
                "generation_time_avg": 0,
                "accuracy_trend": []
            }
        }

        # Get performance data from services
        if meteo_manager.is_initialized:
            # Data processing metrics
            if meteo_manager.data_processor:
                processing_stats = await meteo_manager.data_processor.get_processing_stats(
                    start_time=start_time,
                    end_time=end_time
                )
                if processing_stats:
                    performance_metrics["data_processing"].update(processing_stats)

            # Forecast performance metrics
            if meteo_manager.forecast_service:
                forecast_stats = await meteo_manager.forecast_service.get_forecast_stats(
                    start_time=start_time,
                    end_time=end_time
                )
                if forecast_stats:
                    performance_metrics["forecast_performance"].update(forecast_stats)

        return {
            "success": True,
            "message": "Performance metrics retrieved successfully",
            "data": performance_metrics
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@router.get(
    "/alerts-trend",
    response_model=Dict[str, Any],
    summary="Get alerts trend analysis",
    description="Get weather alerts trend analysis and statistics",
    responses={
        200: {"description": "Alerts trend analysis retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_alerts_trend(
    days: int = Query(30, ge=1, le=90, description="Analysis period in days"),
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get weather alerts trend analysis."""
    try:
        if meteo_manager.is_initialized and meteo_manager.alert_service:
            trend_analysis = await meteo_manager.alert_service.get_alerts_trend(
                days=days,
                wind_farm_id=wind_farm_id
            )

            return {
                "success": True,
                "message": "Alerts trend analysis retrieved successfully",
                "data": trend_analysis
            }
        else:
            return {
                "success": False,
                "message": "Alert service not available",
                "data": {
                    "period_days": days,
                    "total_alerts": 0,
                    "severity_trend": {},
                    "daily_counts": [],
                    "common_types": []
                }
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alerts trend: {str(e)}")


@router.post(
    "/clear-cache",
    response_model=SuccessResponse,
    summary="Clear monitoring cache",
    description="Clear monitoring and statistics cache",
    responses={
        200: {"description": "Cache cleared successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def clear_monitoring_cache(
    cache_type: Optional[str] = Query(None, description="Specific cache type to clear"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Clear monitoring cache."""
    try:
        cleared_caches = []

        # Clear Redis cache
        if meteo_manager.redis_client:
            if cache_type:
                # Clear specific cache
                await meteo_manager.redis_client.delete(f"monitoring:{cache_type}:*")
                cleared_caches.append(f"monitoring:{cache_type}")
            else:
                # Clear all monitoring cache
                pattern = "monitoring:*"
                keys = await meteo_manager.redis_client.keys(pattern)
                if keys:
                    await meteo_manager.redis_client.delete(*keys)
                cleared_caches.append("all_monitoring")

        return {
            "success": True,
            "message": f"Monitoring cache cleared successfully: {', '.join(cleared_caches)}",
            "data": {
                "cleared_caches": cleared_caches,
                "cleared_at": datetime.utcnow().isoformat()
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear monitoring cache: {str(e)}")


# Add logging
import logging
logger = logging.getLogger(__name__)