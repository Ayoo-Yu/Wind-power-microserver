"""
Weather Alerts API endpoints for Meteorological Data Service
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session, weather_alert_crud, weather_station_crud
from ..models import (
    WeatherAlertCreate,
    WeatherAlertResponse,
    WeatherAlertFilter,
    PaginationParams,
    SuccessResponse,
    ErrorResponse,
    AlertSeverity,
    WeatherAlertStatus
)
from ..services import MeteorologicalManager
from ..auth import get_current_user, require_operator, WindFarmAccessChecker
from ..exceptions import (
    WeatherStationNotFoundException,
    WeatherAlertException,
    ValidationException
)

router = APIRouter(prefix="/api/v1/alerts", tags=["weather-alerts"])

# Global meteorological manager instance
meteo_manager = MeteorologicalManager()


@router.post(
    "",
    response_model=WeatherAlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create weather alert",
    description="Create a new weather alert manually",
    responses={
        201: {"description": "Weather alert created successfully"},
        400: {"description": "Invalid alert data", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def create_weather_alert(
    alert_data: WeatherAlertCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Create a new weather alert."""
    try:
        # Validate alert data
        if alert_data.effective_time >= alert_data.expires_time:
            raise HTTPException(status_code=400, detail="Effective time must be before expires time")

        if alert_data.expires_time < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Expires time must be in the future")

        # Create alert
        alert = await weather_alert_crud.create(db, alert_data.dict())

        # Publish alert event
        if meteo_manager.is_initialized:
            alert_event = {
                "event_type": "weather_alert_created",
                "alert_id": alert.id,
                "alert_code": alert.alert_code,
                "severity": alert.severity,
                "wind_farm_id": alert.wind_farm_id,
                "title": alert.title,
                "created_at": alert.created_at.isoformat()
            }
            # Would publish to Kafka here

        return WeatherAlertResponse.from_orm(alert)

    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create weather alert: {str(e)}")


@router.get(
    "/{alert_id}",
    response_model=WeatherAlertResponse,
    summary="Get weather alert by ID",
    description="Retrieve a specific weather alert",
    responses={
        200: {"description": "Weather alert retrieved successfully"},
        404: {"description": "Weather alert not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_weather_alert(
    alert_id: str = Path(..., description="Weather alert ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get weather alert by ID."""
    try:
        alert = await weather_alert_crud.get(db, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail=f"Weather alert {alert_id} not found")
        return WeatherAlertResponse.from_orm(alert)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get weather alert: {str(e)}")


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Get weather alerts",
    description="Retrieve weather alerts with filtering and pagination",
    responses={
        200: {"description": "Weather alerts retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_weather_alerts(
    # Filter parameters
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    status: Optional[WeatherAlertStatus] = Query(None, description="Filter by status"),
    source: Optional[str] = Query(None, description="Filter by alert source"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),

    # Time range parameters
    effective_after: Optional[datetime] = Query(None, description="Alerts effective after this time"),
    effective_before: Optional[datetime] = Query(None, description="Alerts effective before this time"),

    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),

    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get weather alerts with filtering and pagination."""
    try:
        # Build filter parameters
        filter_params = {
            "wind_farm_id": wind_farm_id,
            "severity": severity,
            "status": status,
            "source": source
        }
        filter_params = {k: v for k, v in filter_params.items() if v is not None}

        # Build pagination parameters
        pagination = PaginationParams(page=page, size=size)

        # Get alerts
        result = await weather_alert_crud.get_multi(
            db=db,
            filter_params=filter_params,
            time_range={"effective_after": effective_after, "effective_before": effective_before},
            pagination=pagination
        )

        # Calculate summary statistics
        total_alerts = result["total"]
        active_alerts = sum(1 for alert in result["items"] if alert.status == WeatherAlertStatus.ACTIVE)
        critical_alerts = sum(1 for alert in result["items"] if alert.severity == AlertSeverity.CRITICAL)

        return {
            "success": True,
            "message": "Weather alerts retrieved successfully",
            "data": [WeatherAlertResponse.from_orm(alert) for alert in result["items"]],
            "summary": {
                "total_alerts": total_alerts,
                "active_alerts": active_alerts,
                "critical_alerts": critical_alerts,
                "acknowledgment_rate": (total_alerts - active_alerts) / total_alerts if total_alerts > 0 else 0
            },
            "pagination": {
                "total": result["total"],
                "page": result["page"],
                "size": result["size"],
                "pages": result["pages"],
                "has_next": result["has_next"],
                "has_prev": result["has_prev"]
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get weather alerts: {str(e)}")


@router.get(
    "/active",
    response_model=Dict[str, Any],
    summary="Get active weather alerts",
    description="Get currently active weather alerts",
    responses={
        200: {"description": "Active alerts retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_active_alerts(
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get active weather alerts."""
    try:
        if meteo_manager.is_initialized:
            active_alerts = await meteo_manager.alert_service.get_active_alerts(
                wind_farm_id=wind_farm_id,
                severity=severity,
                db_session=db
            )

            # Calculate risk level
            risk_level = "low"
            if active_alerts:
                max_severity = max(alert.severity for alert in active_alerts)
                if max_severity == AlertSeverity.EXTREME:
                    risk_level = "extreme"
                elif max_severity == AlertSeverity.SEVERE:
                    risk_level = "high"
                elif max_severity == AlertSeverity.MODERATE:
                    risk_level = "moderate"

            return {
                "success": True,
                "message": f"Found {len(active_alerts)} active weather alerts",
                "data": {
                    "alerts": [WeatherAlertResponse.from_orm(alert) for alert in active_alerts],
                    "total_alerts": len(active_alerts),
                    "risk_level": risk_level,
                    "max_severity": max_severity if active_alerts else None
                }
            }
        else:
            return {
                "success": False,
                "message": "Alert service not initialized",
                "data": {
                    "alerts": [],
                    "total_alerts": 0,
                    "risk_level": "unknown"
                }
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active alerts: {str(e)}")


@router.get(
    "/by-wind-farm/{wind_farm_id}",
    response_model=Dict[str, Any],
    summary="Get alerts by wind farm",
    description="Get all weather alerts for a specific wind farm",
    responses={
        200: {"description": "Weather alerts retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_alerts_by_wind_farm(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    active_only: bool = Query(False, description="Return only active alerts"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker())
):
    """Get weather alerts by wind farm."""
    try:
        # Build filter for wind farm
        filter_params = {"wind_farm_id": wind_farm_id}
        if active_only:
            filter_params["status"] = WeatherAlertStatus.ACTIVE

        result = await weather_alert_crud.get_multi(
            db=db,
            filter_params=filter_params,
            pagination=None  # Get all alerts for this wind farm
        )

        # Group by severity
        alerts_by_severity = {}
        for alert in result["items"]:
            severity = alert.severity
            if severity not in alerts_by_severity:
                alerts_by_severity[severity] = []
            alerts_by_severity[severity].append(WeatherAlertResponse.from_orm(alert))

        # Calculate impact assessment
        if meteo_manager.is_initialized:
            impact_assessment = await meteo_manager.alert_service.check_alert_impact(
                wind_farm_id=wind_farm_id,
                turbine_ids=[]  # Would get turbine IDs if needed
            )
        else:
            impact_assessment = None

        return {
            "success": True,
            "message": f"Weather alerts for wind farm {wind_farm_id} retrieved successfully",
            "data": {
                "wind_farm_id": wind_farm_id,
                "total_alerts": len(result["items"]),
                "alerts_by_severity": alerts_by_severity,
                "impact_assessment": impact_assessment,
                "active_alerts": len([a for a in result["items"] if a.status == WeatherAlertStatus.ACTIVE])
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get weather alerts by wind farm: {str(e)}")


@router.get(
    "/summary",
    response_model=Dict[str, Any],
    summary="Get alerts summary",
    description="Get comprehensive weather alerts statistics and trends",
    responses={
        200: {"description": "Alerts summary retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_alerts_summary(
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    days: int = Query(7, ge=1, le=30, description="Summary period in days"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get weather alerts summary."""
    try:
        if meteo_manager.is_initialized:
            summary = await meteo_manager.alert_service.get_alerts_summary(
                wind_farm_id=wind_farm_id,
                days=days,
                db_session=db
            )

            return {
                "success": True,
                "message": "Weather alerts summary retrieved successfully",
                "data": summary
            }
        else:
            return {
                "success": False,
                "message": "Alert service not initialized",
                "data": {
                    "period": {
                        "start": (datetime.utcnow() - timedelta(days=days)).isoformat(),
                        "end": datetime.utcnow().isoformat(),
                        "days": days
                    },
                    "summary": {
                        "total_alerts": 0,
                        "active_alerts": 0,
                        "severity_breakdown": {},
                        "status_breakdown": {},
                        "daily_trends": []
                    },
                    "alerts": []
                }
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alerts summary: {str(e)}")


@router.post(
    "/{alert_id}/acknowledge",
    response_model=SuccessResponse,
    summary="Acknowledge weather alert",
    description="Acknowledge a weather alert",
    responses={
        200: {"description": "Alert acknowledged successfully"},
        404: {"description": "Weather alert not found", "model": ErrorResponse},
        400: {"description": "Alert already acknowledged", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def acknowledge_alert(
    alert_id: str = Path(..., description="Weather alert ID"),
    notes: Optional[str] = Query(None, description="Acknowledgment notes"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Acknowledge weather alert."""
    try:
        # Get alert
        alert = await weather_alert_crud.get(db, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail=f"Weather alert {alert_id} not found")

        # Check if already acknowledged
        if alert.is_acknowledged:
            raise HTTPException(status_code=400, detail="Alert already acknowledged")

        # Update alert
        update_data = {
            "is_acknowledged": True,
            "acknowledged_by": current_user.id,
            "acknowledged_at": datetime.utcnow(),
            "acknowledgment_notes": notes
        }

        await weather_alert_crud.update(db, alert, update_data)

        # Publish acknowledgment event
        if meteo_manager.is_initialized:
            alert_event = {
                "event_type": "weather_alert_acknowledged",
                "alert_id": alert_id,
                "acknowledged_by": current_user.id,
                "acknowledged_at": datetime.utcnow().isoformat(),
                "notes": notes
            }
            # Would publish to Kafka here

        return {
            "success": True,
            "message": f"Weather alert {alert_id} acknowledged successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge alert: {str(e)}")


@router.post(
    "/{alert_id}/resolve",
    response_model=SuccessResponse,
    summary="Resolve weather alert",
    description="Mark a weather alert as resolved",
    responses={
        200: {"description": "Alert resolved successfully"},
        404: {"description": "Weather alert not found", "model": ErrorResponse},
        400: {"description": "Alert already resolved", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def resolve_alert(
    alert_id: str = Path(..., description="Weather alert ID"),
    resolution_notes: Optional[str] = Query(None, description="Resolution notes"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Resolve weather alert."""
    try:
        # Get alert
        alert = await weather_alert_crud.get(db, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail=f"Weather alert {alert_id} not found")

        # Check if already resolved
        if alert.status == WeatherAlertStatus.RESOLVED:
            raise HTTPException(status_code=400, detail="Alert already resolved")

        # Update alert
        update_data = {
            "status": WeatherAlertStatus.RESOLVED,
            "resolved_by": current_user.id,
            "resolved_at": datetime.utcnow(),
            "resolution_notes": resolution_notes
        }

        await weather_alert_crud.update(db, alert, update_data)

        # Publish resolution event
        if meteo_manager.is_initialized:
            alert_event = {
                "event_type": "weather_alert_resolved",
                "alert_id": alert_id,
                "resolved_by": current_user.id,
                "resolved_at": datetime.utcnow().isoformat(),
                "resolution_notes": resolution_notes
            }
            # Would publish to Kafka here

        return {
            "success": True,
            "message": f"Weather alert {alert_id} resolved successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve alert: {str(e)}")


@router.post(
    "/impact-assessment",
    response_model=Dict[str, Any],
    summary="Assess alert impact",
    description="Assess the impact of weather alerts on wind farm operations",
    responses={
        200: {"description": "Impact assessment completed successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def assess_alert_impact(
    wind_farm_id: str = Query(..., description="Wind farm ID to assess"),
    turbine_ids: Optional[List[str]] = Query(None, description="Specific turbines to assess"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker())
):
    """Assess weather alert impact on wind farm operations."""
    try:
        if meteo_manager.is_initialized:
            impact_assessment = await meteo_manager.alert_service.check_alert_impact(
                wind_farm_id=wind_farm_id,
                turbine_ids=turbine_ids
            )

            return {
                "success": True,
                "message": f"Alert impact assessment completed for wind farm {wind_farm_id}",
                "data": impact_assessment
            }
        else:
            return {
                "success": False,
                "message": "Alert service not initialized",
                "data": {
                    "wind_farm_id": wind_farm_id,
                    "impact_level": "unknown",
                    "message": "Alert service unavailable"
                }
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assess alert impact: {str(e)}")


@router.post(
    "/bulk-acknowledge",
    response_model=SuccessResponse,
    summary="Bulk acknowledge alerts",
    description="Acknowledge multiple weather alerts at once",
    responses={
        200: {"description": "Alerts acknowledged successfully"},
        400: {"description": "Invalid request", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def bulk_acknowledge_alerts(
    alert_ids: List[str],
    notes: Optional[str] = Query(None, description="Acknowledgment notes"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Bulk acknowledge weather alerts."""
    try:
        acknowledged_count = 0
        errors = []

        for alert_id in alert_ids:
            try:
                # Get alert
                alert = await weather_alert_crud.get(db, alert_id)
                if not alert:
                    errors.append(f"Alert {alert_id} not found")
                    continue

                # Check if already acknowledged
                if alert.is_acknowledged:
                    errors.append(f"Alert {alert_id} already acknowledged")
                    continue

                # Update alert
                update_data = {
                    "is_acknowledged": True,
                    "acknowledged_by": current_user.id,
                    "acknowledged_at": datetime.utcnow(),
                    "acknowledgment_notes": notes
                }

                await weather_alert_crud.update(db, alert, update_data)
                acknowledged_count += 1

            except Exception as e:
                errors.append(f"Error acknowledging alert {alert_id}: {str(e)}")

        return {
            "success": True,
            "message": f"Successfully acknowledged {acknowledged_count} out of {len(alert_ids)} alerts",
            "data": {
                "total_requested": len(alert_ids),
                "acknowledged": acknowledged_count,
                "errors": errors
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk acknowledge alerts: {str(e)}")


@router.post(
    "/expire-old",
    response_model=SuccessResponse,
    summary="Expire old alerts",
    description="Expire weather alerts that have passed their expiration time",
    responses={
        200: {"description": "Old alerts expired successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def expire_old_alerts(
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Expire old weather alerts."""
    try:
        if meteo_manager.is_initialized:
            expired_count = await meteo_manager.alert_service.expire_old_alerts(db_session=db)

            return {
                "success": True,
                "message": f"Expired {expired_count} old weather alerts",
                "data": {
                    "expired_count": expired_count,
                    "processed_at": datetime.utcnow().isoformat()
                }
            }
        else:
            return {
                "success": False,
                "message": "Alert service not initialized",
                "data": {
                    "expired_count": 0
                }
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to expire old alerts: {str(e)}")


# Add logging
import logging
logger = logging.getLogger(__name__)