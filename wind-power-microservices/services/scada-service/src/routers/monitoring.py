"""
SCADA System Monitoring API endpoints.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from ..database import get_db_session, scada_connection_crud
from ..models import (
    SystemStatusResponse,
    ConnectionHealthResponse,
    PerformanceMetricsResponse,
    SuccessResponse,
    ErrorResponse
)
from ..services import ConnectionManager, DataProcessor
from ..auth import get_current_user
from ..exceptions import ValidationException

router = APIRouter(prefix="/api/v1/monitoring", tags=["scada-monitoring"])

# Global service instances
connection_manager = ConnectionManager()
data_processor = DataProcessor()


@router.get(
    "/status",
    response_model=Dict[str, Any],
    summary="Get system status",
    description="Get overall SCADA system status and health information",
    responses={
        200: {"description": "System status retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_system_status(
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA system status."""
    try:
        # Get connection statistics
        connection_stats = connection_manager.get_connection_statistics()

        # Get data processing statistics
        processing_stats = await data_processor.get_processing_statistics()

        # Get database connection status
        db_status = "healthy"
        try:
            from sqlalchemy import select, text
            result = await db.execute(text("SELECT 1"))
            result.scalar()
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"

        # Get InfluxDB status
        influxdb_status = "healthy"
        try:
            await connection_manager.influxdb_manager.ping()
        except Exception as e:
            influxdb_status = f"unhealthy: {str(e)}"

        # Get Kafka status
        kafka_status = "healthy"
        try:
            await connection_manager.kafka_manager.ping()
        except Exception as e:
            kafka_status = f"unhealthy: {str(e)}"

        # Calculate overall system health
        services_healthy = all([
            db_status == "healthy",
            influxdb_status == "healthy",
            kafka_status == "healthy"
        ])

        overall_status = "healthy" if services_healthy else "degraded"

        return {
            "success": True,
            "message": "System status retrieved successfully",
            "data": {
                "overall_status": overall_status,
                "timestamp": datetime.utcnow().isoformat(),
                "services": {
                    "database": db_status,
                    "influxdb": influxdb_status,
                    "kafka": kafka_status
                },
                "connections": connection_stats,
                "data_processing": processing_stats
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system status: {str(e)}")


@router.get(
    "/connections/health",
    response_model=Dict[str, Any],
    summary="Get connection health status",
    description="Get health status of all SCADA connections",
    responses={
        200: {"description": "Connection health status retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_connection_health(
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    include_inactive: bool = Query(False, description="Include inactive connections"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA connection health status."""
    try:
        # Get all connections
        connections_result = await connection_manager.get_connections(
            db=db,
            filter_params={"wind_farm_id": wind_farm_id} if wind_farm_id else None,
            pagination=None  # Get all connections
        )

        health_status = []
        for connection in connections_result["items"]:
            # Get connection health from protocol adapters
            connection_health = None
            for adapter in connection_manager.protocol_adapters.values():
                conn = adapter.get_connection(connection.id)
                if conn:
                    connection_health = {
                        "connection_id": connection.id,
                        "connection_name": connection.name,
                        "status": conn.status.value,
                        "is_healthy": conn.is_healthy(),
                        "statistics": conn.get_statistics(),
                        "last_data_time": conn.last_data_time.isoformat() if conn.last_data_time else None,
                        "error_count": conn.error_count,
                        "data_count": conn.data_count
                    }
                    break

            if connection_health:
                health_status.append(connection_health)

        # Calculate overall health metrics
        total_connections = len(health_status)
        healthy_connections = sum(1 for health in health_status if health["is_healthy"])
        active_connections = sum(1 for health in health_status if health["status"] == "connected")

        return {
            "success": True,
            "message": "Connection health status retrieved successfully",
            "data": {
                "summary": {
                    "total_connections": total_connections,
                    "healthy_connections": healthy_connections,
                    "active_connections": active_connections,
                    "health_percentage": (healthy_connections / total_connections * 100) if total_connections > 0 else 0
                },
                "connections": health_status
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get connection health status: {str(e)}")


@router.get(
    "/performance/metrics",
    response_model=Dict[str, Any],
    summary="Get performance metrics",
    description="Get SCADA system performance metrics and KPIs",
    responses={
        200: {"description": "Performance metrics retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_performance_metrics(
    hours: int = Query(24, ge=1, le=168, description="Time period in hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA performance metrics."""
    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Get data ingestion metrics from InfluxDB
        ingestion_metrics = await connection_manager.influxdb_manager.get_ingestion_metrics(
            start_time=start_time,
            end_time=end_time
        )

        # Get processing metrics
        processing_stats = await data_processor.get_processing_statistics()

        # Get connection metrics
        connection_stats = connection_manager.get_connection_statistics()

        # Calculate KPIs
        total_data_points = ingestion_metrics.get("total_points", 0)
        avg_processing_time = processing_stats.get("last_processing_time", 0)
        data_quality_score = 95.0  # Placeholder - would calculate from quality metrics
        system_availability = 99.5  # Placeholder - would calculate from uptime

        # Calculate trends
        if hours > 1:
            # Get metrics for comparison (previous period)
            prev_start_time = start_time - timedelta(hours=hours)
            prev_end_time = start_time

            prev_ingestion_metrics = await connection_manager.influxdb_manager.get_ingestion_metrics(
                start_time=prev_start_time,
                end_time=prev_end_time
            )

            # Calculate percentage changes
            prev_total_points = prev_ingestion_metrics.get("total_points", 0)
            points_trend = ((total_data_points - prev_total_points) / prev_total_points * 100) if prev_total_points > 0 else 0
        else:
            points_trend = 0

        return {
            "success": True,
            "message": "Performance metrics retrieved successfully",
            "data": {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "hours": hours
                },
                "key_performance_indicators": {
                    "total_data_points": total_data_points,
                    "data_ingestion_rate": total_data_points / hours,  # points per hour
                    "average_processing_time": avg_processing_time,
                    "data_quality_score": data_quality_score,
                    "system_availability": system_availability
                },
                "trends": {
                    "data_points_change": points_trend
                },
                "detailed_metrics": {
                    "data_ingestion": ingestion_metrics,
                    "data_processing": processing_stats,
                    "connections": connection_stats
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@router.get(
    "/data-quality/summary",
    response_model=Dict[str, Any],
    summary="Get data quality summary",
    description="Get summary of data quality metrics",
    responses={
        200: {"description": "Data quality summary retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_data_quality_summary(
    hours: int = Query(24, ge=1, le=168, description="Time period in hours"),
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get data quality summary."""
    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Get data quality metrics from InfluxDB
        quality_metrics = await connection_manager.influxdb_manager.get_data_quality_metrics(
            start_time=start_time,
            end_time=end_time,
            wind_farm_id=wind_farm_id
        )

        # Calculate quality scores
        total_points = quality_metrics.get("total_points", 0)
        good_points = quality_metrics.get("good_quality_points", 0)
        bad_points = quality_metrics.get("bad_quality_points", 0)
        uncertain_points = quality_metrics.get("uncertain_quality_points", 0)

        quality_score = (good_points / total_points * 100) if total_points > 0 else 0

        return {
            "success": True,
            "message": "Data quality summary retrieved successfully",
            "data": {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "hours": hours
                },
                "quality_metrics": {
                    "total_points": total_points,
                    "good_quality_points": good_points,
                    "bad_quality_points": bad_points,
                    "uncertain_quality_points": uncertain_points
                },
                "quality_scores": {
                    "overall_quality_score": quality_score,
                    "good_quality_percentage": (good_points / total_points * 100) if total_points > 0 else 0,
                    "bad_quality_percentage": (bad_points / total_points * 100) if total_points > 0 else 0,
                    "uncertain_quality_percentage": (uncertain_points / total_points * 100) if total_points > 0 else 0
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data quality summary: {str(e)}")


@router.get(
    "/turbines/status",
    response_model=Dict[str, Any],
    summary="Get turbine status overview",
    description="Get status overview of all turbines across wind farms",
    responses={
        200: {"description": "Turbine status overview retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_turbine_status_overview(
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get turbine status overview."""
    try:
        # Get turbine status data from data processor cache
        turbine_status_cache = data_processor.turbine_cache

        # Filter by wind farm if specified
        if wind_farm_id:
            filtered_cache = {
                turbine_id: data for turbine_id, data in turbine_status_cache.items()
                if data.get("wind_farm_id") == wind_farm_id
            }
        else:
            filtered_cache = turbine_status_cache

        # Calculate status summary
        total_turbines = len(filtered_cache)
        running_turbines = sum(
            1 for data in filtered_cache.values()
            if data.get("status") == "running"
        )
        stopped_turbines = sum(
            1 for data in filtered_cache.values()
            if data.get("status") == "stopped"
        )
        unknown_turbines = sum(
            1 for data in filtered_cache.values()
            if data.get("status") == "unknown"
        )

        # Calculate average availability
        availability_scores = [
            data.get("availability", 0)
            for data in filtered_cache.values()
            if data.get("availability") is not None
        ]
        avg_availability = sum(availability_scores) / len(availability_scores) if availability_scores else 0

        return {
            "success": True,
            "message": "Turbine status overview retrieved successfully",
            "data": {
                "summary": {
                    "total_turbines": total_turbines,
                    "running_turbines": running_turbines,
                    "stopped_turbines": stopped_turbines,
                    "unknown_turbines": unknown_turbines,
                    "average_availability": avg_availability
                },
                "turbine_details": filtered_cache
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get turbine status overview: {str(e)}")


@router.get(
    "/alerts/active",
    response_model=Dict[str, Any],
    summary="Get active system alerts",
    description="Get current active system alerts and warnings",
    responses={
        200: {"description": "Active alerts retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_active_alerts(
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get active system alerts."""
    try:
        alerts = []

        # Check connection health
        connection_stats = connection_manager.get_connection_statistics()
        total_connections = connection_stats.get("total_connections", 0)
        active_connections = connection_stats.get("active_connections", 0)

        if total_connections > 0:
            connection_health_percentage = (active_connections / total_connections) * 100

            if connection_health_percentage < 50:
                alerts.append({
                    "type": "critical",
                    "category": "connections",
                    "message": f"Less than 50% of SCADA connections are active ({active_connections}/{total_connections})",
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif connection_health_percentage < 80:
                alerts.append({
                    "type": "warning",
                    "category": "connections",
                    "message": f"Less than 80% of SCADA connections are active ({active_connections}/{total_connections})",
                    "timestamp": datetime.utcnow().isoformat()
                })

        # Check data processing health
        processing_stats = await data_processor.get_processing_statistics()
        last_processing_time = processing_stats.get("last_processing_time")

        if last_processing_time and last_processing_time > 10:  # More than 10 seconds
            alerts.append({
                "type": "warning",
                "category": "data_processing",
                "message": f"Data processing time is high: {last_processing_time:.2f} seconds",
                "timestamp": datetime.utcnow().isoformat()
            })

        # Check data quality
        quality_summary = await connection_manager.influxdb_manager.get_data_quality_metrics(
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow()
        )

        total_points = quality_summary.get("total_points", 0)
        bad_points = quality_summary.get("bad_quality_points", 0)

        if total_points > 0:
            bad_quality_percentage = (bad_points / total_points) * 100

            if bad_quality_percentage > 10:
                alerts.append({
                    "type": "warning",
                    "category": "data_quality",
                    "message": f"High percentage of bad quality data: {bad_quality_percentage:.1f}%",
                    "timestamp": datetime.utcnow().isoformat()
                })

        return {
            "success": True,
            "message": "Active alerts retrieved successfully",
            "data": {
                "total_alerts": len(alerts),
                "critical_alerts": len([a for a in alerts if a["type"] == "critical"]),
                "warning_alerts": len([a for a in alerts if a["type"] == "warning"]),
                "alerts": alerts
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active alerts: {str(e)}")


@router.post(
    "/cleanup-data",
    response_model=SuccessResponse,
    summary="Cleanup old monitoring data",
    description="Clean up old monitoring data and statistics",
    responses={
        200: {"description": "Data cleanup completed successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def cleanup_monitoring_data(
    days_to_keep: int = Query(30, ge=7, le=365, description="Number of days of data to keep"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Cleanup old monitoring data."""
    try:
        # Clean up old data from data processor
        await data_processor.cleanup_old_data(retention_hours=days_to_keep * 24)

        # Clean up old data from InfluxDB
        await connection_manager.influxdb_manager.cleanup_old_data(retention_days=days_to_keep)

        return {
            "success": True,
            "message": f"Monitoring data cleanup completed successfully. Kept data from last {days_to_keep} days"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup monitoring data: {str(e)}")