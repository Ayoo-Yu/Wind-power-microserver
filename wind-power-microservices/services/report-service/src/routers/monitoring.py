"""
Monitoring and analytics router for Report Service
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services import monitoring_service
from ..utils import get_logger, create_success_response, create_error_response

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


@router.get("/status")
async def get_system_status(db: AsyncSession = Depends(get_db)):
    """Get overall system status and health metrics."""
    try:
        logger.info("Getting system status")

        status = await monitoring_service.get_system_status(db)

        return create_success_response("System status retrieved successfully", status)

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system status")


@router.get("/metrics")
async def get_metrics(
    start_date: Optional[datetime] = Query(None, description="Start date for metrics"),
    end_date: Optional[datetime] = Query(None, description="End date for metrics"),
    metric_type: Optional[str] = Query(None, description="Specific metric type to filter"),
    db: AsyncSession = Depends(get_db)
):
    """Get system metrics and performance data."""
    try:
        logger.info(f"Getting metrics: start={start_date}, end={end_date}, type={metric_type}")

        # Set default date range if not provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)

        metrics = await monitoring_service.get_metrics(
            db, start_date, end_date, metric_type
        )

        return create_success_response("Metrics retrieved successfully", metrics)

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get metrics")


@router.get("/reports/statistics")
async def get_report_statistics(
    start_date: Optional[datetime] = Query(None, description="Start date for statistics"),
    end_date: Optional[datetime] = Query(None, description="End date for statistics"),
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get report generation statistics."""
    try:
        logger.info(f"Getting report statistics: type={report_type}, wind_farm={wind_farm_id}")

        # Set default date range if not provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        statistics = await monitoring_service.get_report_statistics(
            db, start_date, end_date, report_type, wind_farm_id
        )

        return create_success_response("Report statistics retrieved successfully", statistics)

    except Exception as e:
        logger.error(f"Error getting report statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get report statistics")


@router.get("/charts/statistics")
async def get_chart_statistics(
    start_date: Optional[datetime] = Query(None, description="Start date for statistics"),
    end_date: Optional[datetime] = Query(None, description="End date for statistics"),
    chart_type: Optional[str] = Query(None, description="Filter by chart type"),
    backend: Optional[str] = Query(None, description="Filter by chart backend"),
    db: AsyncSession = Depends(get_db)
):
    """Get chart generation statistics."""
    try:
        logger.info(f"Getting chart statistics: type={chart_type}, backend={backend}")

        # Set default date range if not provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        statistics = await monitoring_service.get_chart_statistics(
            db, start_date, end_date, chart_type, backend
        )

        return create_success_response("Chart statistics retrieved successfully", statistics)

    except Exception as e:
        logger.error(f"Error getting chart statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chart statistics")


@router.get("/data-quality")
async def get_data_quality_metrics(
    data_source: Optional[str] = Query(None, description="Filter by data source"),
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db)
):
    """Get data quality metrics."""
    try:
        logger.info(f"Getting data quality metrics: source={data_source}, wind_farm={wind_farm_id}")

        metrics = await monitoring_service.get_data_quality_metrics(
            db, data_source, wind_farm_id, days
        )

        return create_success_response("Data quality metrics retrieved successfully", metrics)

    except Exception as e:
        logger.error(f"Error getting data quality metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get data quality metrics")


@router.get("/performance/trends")
async def get_performance_trends(
    metric: str = Query(..., description="Performance metric to analyze"),
    time_period: str = Query("7d", description="Time period: 1d, 7d, 30d, 90d"),
    aggregation: str = Query("hourly", description="Aggregation: hourly, daily, weekly"),
    db: AsyncSession = Depends(get_db)
):
    """Get performance trends over time."""
    try:
        logger.info(f"Getting performance trends: metric={metric}, period={time_period}")

        trends = await monitoring_service.get_performance_trends(
            db, metric, time_period, aggregation
        )

        return create_success_response("Performance trends retrieved successfully", trends)

    except Exception as e:
        logger.error(f"Error getting performance trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance trends")


@router.get("/alerts/active")
async def get_active_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: low, medium, high, critical"),
    category: Optional[str] = Query(None, description="Filter by category"),
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get active system alerts."""
    try:
        logger.info(f"Getting active alerts: severity={severity}, category={category}")

        alerts = await monitoring_service.get_active_alerts(
            db, severity, category, wind_farm_id
        )

        return create_success_response("Active alerts retrieved successfully", alerts)

    except Exception as e:
        logger.error(f"Error getting active alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active alerts")


@router.get("/alerts/history")
async def get_alerts_history(
    start_date: Optional[datetime] = Query(None, description="Start date for history"),
    end_date: Optional[datetime] = Query(None, description="End date for history"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of alerts"),
    db: AsyncSession = Depends(get_db)
):
    """Get alerts history."""
    try:
        logger.info(f"Getting alerts history: severity={severity}, category={category}")

        # Set default date range if not provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        history = await monitoring_service.get_alerts_history(
            db, start_date, end_date, severity, category, limit
        )

        return create_success_response("Alerts history retrieved successfully", history)

    except Exception as e:
        logger.error(f"Error getting alerts history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get alerts history")


@router.get("/usage/analytics")
async def get_usage_analytics(
    start_date: Optional[datetime] = Query(None, description="Start date for analytics"),
    end_date: Optional[datetime] = Query(None, description="End date for analytics"),
    group_by: str = Query("daily", description="Group by: hourly, daily, weekly, monthly"),
    db: AsyncSession = Depends(get_db)
):
    """Get usage analytics and patterns."""
    try:
        logger.info(f"Getting usage analytics: group_by={group_by}")

        # Set default date range if not provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        analytics = await monitoring_service.get_usage_analytics(
            db, start_date, end_date, group_by
        )

        return create_success_response("Usage analytics retrieved successfully", analytics)

    except Exception as e:
        logger.error(f"Error getting usage analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get usage analytics")


@router.get("/system/health")
async def get_system_health(
    detailed: bool = Query(False, description="Include detailed health information"),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed system health status."""
    try:
        logger.info(f"Getting system health: detailed={detailed}")

        health = await monitoring_service.get_system_health(db, detailed)

        return create_success_response("System health retrieved successfully", health)

    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system health")


@router.get("/capacity/planning")
async def get_capacity_planning(
    forecast_days: int = Query(30, ge=7, le=365, description="Number of days to forecast"),
    db: AsyncSession = Depends(get_db)
):
    """Get capacity planning metrics and forecasts."""
    try:
        logger.info(f"Getting capacity planning: forecast_days={forecast_days}")

        planning = await monitoring_service.get_capacity_planning(db, forecast_days)

        return create_success_response("Capacity planning retrieved successfully", planning)

    except Exception as e:
        logger.error(f"Error getting capacity planning: {e}")
        raise HTTPException(status_code=500, detail="Failed to get capacity planning")


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    time_period: str = Query("24h", description="Time period: 1h, 24h, 7d, 30d"),
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard summary data."""
    try:
        logger.info(f"Getting dashboard summary: period={time_period}, wind_farm={wind_farm_id}")

        summary = await monitoring_service.get_dashboard_summary(db, time_period, wind_farm_id)

        return create_success_response("Dashboard summary retrieved successfully", summary)

    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard summary")