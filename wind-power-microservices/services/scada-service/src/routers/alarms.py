"""
SCADA Alarms API endpoints.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from ..database import get_db_session, alarm_crud
from ..models import (
    AlarmCreate,
    AlarmUpdate,
    AlarmResponse,
    AlarmFilter,
    PaginationParams,
    SuccessResponse,
    ErrorResponse,
    AlarmSeverity,
    AlarmStatus
)
from ..services import ConnectionManager
from ..auth import get_current_user
from ..exceptions import (
    AlarmNotFoundException,
    InvalidAlarmDataException,
    ValidationException
)

router = APIRouter(prefix="/api/v1/alarms", tags=["scada-alarms"])

# Global connection manager instance
connection_manager = ConnectionManager()


@router.post(
    "",
    response_model=AlarmResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new SCADA alarm",
    description="Create a new SCADA alarm manually (typically alarms are generated automatically)",
    responses={
        201: {"description": "SCADA alarm created successfully"},
        400: {"description": "Invalid alarm data", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def create_alarm(
    alarm_data: AlarmCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Create a new SCADA alarm."""
    try:
        # Create alarm with current user as creator
        alarm_data_dict = alarm_data.dict()
        alarm_data_dict["created_by"] = current_user.id
        alarm_data_dict["triggered_at"] = datetime.utcnow()

        alarm = await alarm_crud.create(db, alarm_data_dict)

        # Publish alarm to Kafka for real-time notifications
        alarm_event = {
            "event_type": "alarm_created",
            "alarm_id": alarm.id,
            "alarm_code": alarm.alarm_code,
            "severity": alarm.severity,
            "wind_farm_id": alarm.wind_farm_id,
            "turbine_id": alarm.turbine_id,
            "description": alarm.description,
            "triggered_at": alarm.triggered_at.isoformat()
        }

        await connection_manager.kafka_manager.send_message(
            connection_manager.settings.kafka_topics["scada_alarms"],
            alarm_event
        )

        return AlarmResponse.from_orm(alarm)

    except (ValidationException, InvalidAlarmDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create SCADA alarm: {str(e)}")


@router.get(
    "/{alarm_id}",
    response_model=AlarmResponse,
    summary="Get SCADA alarm by ID",
    description="Retrieve detailed information about a specific SCADA alarm",
    responses={
        200: {"description": "SCADA alarm retrieved successfully"},
        404: {"description": "SCADA alarm not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_alarm(
    alarm_id: str = Path(..., description="SCADA alarm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA alarm by ID."""
    try:
        alarm = await alarm_crud.get(db, alarm_id)
        if not alarm:
            raise HTTPException(status_code=404, detail=f"SCADA alarm {alarm_id} not found")
        return AlarmResponse.from_orm(alarm)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get SCADA alarm: {str(e)}")


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Get list of SCADA alarms",
    description="Retrieve paginated list of SCADA alarms with filtering and search capabilities",
    responses={
        200: {"description": "SCADA alarms retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_alarms(
    # Filter parameters
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    turbine_id: Optional[str] = Query(None, description="Filter by turbine ID"),
    severity: Optional[str] = Query(None, description="Filter by severity (info/warning/critical)"),
    status: Optional[str] = Query(None, description="Filter by status (active/acknowledged/resolved)"),
    alarm_code: Optional[str] = Query(None, description="Filter by alarm code"),
    is_acknowledged: Optional[bool] = Query(None, description="Filter by acknowledgment status"),

    # Time range filters
    triggered_after: Optional[datetime] = Query(None, description="Filter alarms triggered after this time"),
    triggered_before: Optional[datetime] = Query(None, description="Filter alarms triggered before this time"),

    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),

    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get list of SCADA alarms with filtering and pagination."""
    try:
        # Build filter parameters
        filter_params = None
        if any([wind_farm_id, turbine_id, severity, status, alarm_code, is_acknowledged is not None]):
            filter_params = AlarmFilter(
                wind_farm_id=wind_farm_id,
                turbine_id=turbine_id,
                severity=severity,
                status=status,
                alarm_code=alarm_code,
                is_acknowledged=is_acknowledged
            )

        # Build pagination parameters
        pagination = PaginationParams(page=page, size=size)

        result = await alarm_crud.get_multi(
            db=db,
            filter_params=filter_params,
            time_range={"triggered_after": triggered_after, "triggered_before": triggered_before},
            pagination=pagination
        )

        # Calculate summary statistics
        total_alarms = result["total"]
        active_alarms = sum(1 for alarm in result["items"] if alarm.status == AlarmStatus.ACTIVE)
        critical_alarms = sum(1 for alarm in result["items"] if alarm.severity == AlarmSeverity.CRITICAL)

        return {
            "success": True,
            "message": "SCADA alarms retrieved successfully",
            "data": result["items"],
            "summary": {
                "total_alarms": total_alarms,
                "active_alarms": active_alarms,
                "critical_alarms": critical_alarms,
                "acknowledgment_rate": (total_alarms - active_alarms) / total_alarms if total_alarms > 0 else 0
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
        raise HTTPException(status_code=500, detail=f"Failed to get SCADA alarms: {str(e)}")


@router.put(
    "/{alarm_id}",
    response_model=AlarmResponse,
    summary="Update SCADA alarm",
    description="Update SCADA alarm information (acknowledgment, status, etc.)",
    responses={
        200: {"description": "SCADA alarm updated successfully"},
        404: {"description": "SCADA alarm not found", "model": ErrorResponse},
        400: {"description": "Invalid alarm data", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def update_alarm(
    alarm_id: str = Path(..., description="SCADA alarm ID"),
    alarm_data: AlarmUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Update SCADA alarm."""
    try:
        # Get existing alarm
        alarm = await alarm_crud.get(db, alarm_id)
        if not alarm:
            raise HTTPException(status_code=404, detail=f"SCADA alarm {alarm_id} not found")

        # Add current user info for acknowledgment
        update_data = alarm_data.dict(exclude_unset=True)
        if "is_acknowledged" in update_data and update_data["is_acknowledged"]:
            update_data["acknowledged_by"] = current_user.id
            update_data["acknowledged_at"] = datetime.utcnow()

        # Update alarm
        updated_alarm = await alarm_crud.update(db, alarm, update_data)

        # Publish alarm update to Kafka
        alarm_event = {
            "event_type": "alarm_updated",
            "alarm_id": alarm_id,
            "updates": update_data,
            "updated_by": current_user.id,
            "updated_at": datetime.utcnow().isoformat()
        }

        await connection_manager.kafka_manager.send_message(
            connection_manager.settings.kafka_topics["scada_alarms"],
            alarm_event
        )

        return AlarmResponse.from_orm(updated_alarm)

    except (ValidationException, InvalidAlarmDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update SCADA alarm: {str(e)}")


@router.delete(
    "/{alarm_id}",
    response_model=SuccessResponse,
    summary="Delete SCADA alarm",
    description="Delete a SCADA alarm permanently",
    responses={
        200: {"description": "SCADA alarm deleted successfully"},
        404: {"description": "SCADA alarm not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def delete_alarm(
    alarm_id: str = Path(..., description="SCADA alarm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Delete SCADA alarm."""
    try:
        # Get alarm
        alarm = await alarm_crud.get(db, alarm_id)
        if not alarm:
            raise HTTPException(status_code=404, detail=f"SCADA alarm {alarm_id} not found")

        # Delete from database
        await alarm_crud.delete(db, alarm_id)

        # Publish alarm deletion to Kafka
        alarm_event = {
            "event_type": "alarm_deleted",
            "alarm_id": alarm_id,
            "deleted_by": current_user.id,
            "deleted_at": datetime.utcnow().isoformat()
        }

        await connection_manager.kafka_manager.send_message(
            connection_manager.settings.kafka_topics["scada_alarms"],
            alarm_event
        )

        return {
            "success": True,
            "message": f"SCADA alarm {alarm_id} deleted successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete SCADA alarm: {str(e)}")


@router.post(
    "/{alarm_id}/acknowledge",
    response_model=SuccessResponse,
    summary="Acknowledge SCADA alarm",
    description="Acknowledge a SCADA alarm",
    responses={
        200: {"description": "SCADA alarm acknowledged successfully"},
        404: {"description": "SCADA alarm not found", "model": ErrorResponse},
        400: {"description": "Alarm already acknowledged", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def acknowledge_alarm(
    alarm_id: str = Path(..., description="SCADA alarm ID"),
    notes: Optional[str] = Query(None, description="Acknowledgment notes"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Acknowledge SCADA alarm."""
    try:
        # Get alarm
        alarm = await alarm_crud.get(db, alarm_id)
        if not alarm:
            raise HTTPException(status_code=404, detail=f"SCADA alarm {alarm_id} not found")

        # Check if already acknowledged
        if alarm.is_acknowledged:
            raise HTTPException(status_code=400, detail="Alarm already acknowledged")

        # Update alarm
        update_data = {
            "is_acknowledged": True,
            "acknowledged_by": current_user.id,
            "acknowledged_at": datetime.utcnow(),
            "acknowledgment_notes": notes
        }

        await alarm_crud.update(db, alarm, update_data)

        # Publish acknowledgment to Kafka
        alarm_event = {
            "event_type": "alarm_acknowledged",
            "alarm_id": alarm_id,
            "acknowledged_by": current_user.id,
            "acknowledged_at": datetime.utcnow().isoformat(),
            "notes": notes
        }

        await connection_manager.kafka_manager.send_message(
            connection_manager.settings.kafka_topics["scada_alarms"],
            alarm_event
        )

        return {
            "success": True,
            "message": f"SCADA alarm {alarm_id} acknowledged successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge SCADA alarm: {str(e)}")


@router.post(
    "/{alarm_id}/resolve",
    response_model=SuccessResponse,
    summary="Resolve SCADA alarm",
    description="Mark a SCADA alarm as resolved",
    responses={
        200: {"description": "SCADA alarm resolved successfully"},
        404: {"description": "SCADA alarm not found", "model": ErrorResponse},
        400: {"description": "Alarm already resolved", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def resolve_alarm(
    alarm_id: str = Path(..., description="SCADA alarm ID"),
    resolution_notes: Optional[str] = Query(None, description="Resolution notes"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Resolve SCADA alarm."""
    try:
        # Get alarm
        alarm = await alarm_crud.get(db, alarm_id)
        if not alarm:
            raise HTTPException(status_code=404, detail=f"SCADA alarm {alarm_id} not found")

        # Check if already resolved
        if alarm.status == AlarmStatus.RESOLVED:
            raise HTTPException(status_code=400, detail="Alarm already resolved")

        # Update alarm
        update_data = {
            "status": AlarmStatus.RESOLVED,
            "resolved_by": current_user.id,
            "resolved_at": datetime.utcnow(),
            "resolution_notes": resolution_notes
        }

        await alarm_crud.update(db, alarm, update_data)

        # Publish resolution to Kafka
        alarm_event = {
            "event_type": "alarm_resolved",
            "alarm_id": alarm_id,
            "resolved_by": current_user.id,
            "resolved_at": datetime.utcnow().isoformat(),
            "resolution_notes": resolution_notes
        }

        await connection_manager.kafka_manager.send_message(
            connection_manager.settings.kafka_topics["scada_alarms"],
            alarm_event
        )

        return {
            "success": True,
            "message": f"SCADA alarm {alarm_id} resolved successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve SCADA alarm: {str(e)}")


@router.get(
    "/by-wind-farm/{wind_farm_id}",
    response_model=Dict[str, Any],
    summary="Get alarms by wind farm",
    description="Get all SCADA alarms for a specific wind farm",
    responses={
        200: {"description": "SCADA alarms retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_alarms_by_wind_farm(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    active_only: bool = Query(False, description="Return only active alarms"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA alarms by wind farm."""
    try:
        # Build filter for wind farm
        filter_params = AlarmFilter(wind_farm_id=wind_farm_id)
        if active_only:
            filter_params.status = AlarmStatus.ACTIVE

        result = await alarm_crud.get_multi(
            db=db,
            filter_params=filter_params,
            pagination=None  # Get all alarms for this wind farm
        )

        # Group by turbine
        alarms_by_turbine = {}
        for alarm in result["items"]:
            turbine_id = alarm.turbine_id or "unknown"
            if turbine_id not in alarms_by_turbine:
                alarms_by_turbine[turbine_id] = []
            alarms_by_turbine[turbine_id].append(alarm)

        return {
            "success": True,
            "message": f"SCADA alarms for wind farm {wind_farm_id} retrieved successfully",
            "data": {
                "wind_farm_id": wind_farm_id,
                "total_alarms": len(result["items"]),
                "alarms_by_turbine": alarms_by_turbine
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get SCADA alarms by wind farm: {str(e)}")


@router.get(
    "/by-turbine/{turbine_id}",
    response_model=List[AlarmResponse],
    summary="Get alarms by turbine",
    description="Get all SCADA alarms for a specific turbine",
    responses={
        200: {"description": "SCADA alarms retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_alarms_by_turbine(
    turbine_id: str = Path(..., description="Turbine ID"),
    active_only: bool = Query(False, description="Return only active alarms"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA alarms by turbine."""
    try:
        # Build filter for turbine
        filter_params = AlarmFilter(turbine_id=turbine_id)
        if active_only:
            filter_params.status = AlarmStatus.ACTIVE

        result = await alarm_crud.get_multi(
            db=db,
            filter_params=filter_params,
            pagination=None  # Get all alarms for this turbine
        )

        return result["items"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get SCADA alarms by turbine: {str(e)}")


@router.get(
    "/statistics/summary",
    response_model=Dict[str, Any],
    summary="Get alarm statistics summary",
    description="Get comprehensive alarm statistics and trends",
    responses={
        200: {"description": "Alarm statistics retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_alarm_statistics(
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    days: int = Query(7, ge=1, le=30, description="Statistics period in days"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get alarm statistics summary."""
    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)

        # Build base query
        from sqlalchemy import func, select, and_
        query = select(Alarm)

        # Apply wind farm filter if specified
        if wind_farm_id:
            query = query.where(Alarm.wind_farm_id == wind_farm_id)

        # Get total alarms in period
        total_query = select(func.count(Alarm.id))
        if wind_farm_id:
            total_query = total_query.where(Alarm.wind_farm_id == wind_farm_id)
        total_query = total_query.where(
            and_(Alarm.triggered_at >= start_time, Alarm.triggered_at <= end_time)
        )

        total_result = await db.execute(total_query)
        total_alarms = total_result.scalar()

        # Get alarms by severity
        severity_stats = {}
        for severity in AlarmSeverity:
            severity_query = select(func.count(Alarm.id)).where(
                and_(
                    Alarm.severity == severity,
                    Alarm.triggered_at >= start_time,
                    Alarm.triggered_at <= end_time
                )
            )
            if wind_farm_id:
                severity_query = severity_query.where(Alarm.wind_farm_id == wind_farm_id)

            severity_result = await db.execute(severity_query)
            severity_stats[severity] = severity_result.scalar()

        # Get alarms by status
        status_stats = {}
        for status in AlarmStatus:
            status_query = select(func.count(Alarm.id)).where(
                and_(
                    Alarm.status == status,
                    Alarm.triggered_at >= start_time,
                    Alarm.triggered_at <= end_time
                )
            )
            if wind_farm_id:
                status_query = status_query.where(Alarm.wind_farm_id == wind_farm_id)

            status_result = await db.execute(status_query)
            status_stats[status] = status_result.scalar()

        # Calculate trends (alarms per day)
        daily_trends = []
        for i in range(days):
            day_start = start_time + timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            daily_query = select(func.count(Alarm.id)).where(
                and_(
                    Alarm.triggered_at >= day_start,
                    Alarm.triggered_at < day_end
                )
            )
            if wind_farm_id:
                daily_query = daily_query.where(Alarm.wind_farm_id == wind_farm_id)

            daily_result = await db.execute(daily_query)
            daily_count = daily_result.scalar()

            daily_trends.append({
                "date": day_start.date().isoformat(),
                "alarm_count": daily_count
            })

        return {
            "success": True,
            "message": "Alarm statistics retrieved successfully",
            "data": {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "days": days
                },
                "total_alarms": total_alarms,
                "severity_breakdown": severity_stats,
                "status_breakdown": status_stats,
                "daily_trends": daily_trends,
                "acknowledgment_rate": (total_alarms - status_stats.get(AlarmStatus.ACTIVE, 0)) / total_alarms if total_alarms > 0 else 0
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alarm statistics: {str(e)}")


@router.post(
    "/bulk-acknowledge",
    response_model=SuccessResponse,
    summary="Bulk acknowledge alarms",
    description="Acknowledge multiple SCADA alarms at once",
    responses={
        200: {"description": "Alarms acknowledged successfully"},
        400: {"description": "Invalid request", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def bulk_acknowledge_alarms(
    alarm_ids: List[str],
    notes: Optional[str] = Query(None, description="Acknowledgment notes"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Bulk acknowledge SCADA alarms."""
    try:
        acknowledged_count = 0
        errors = []

        for alarm_id in alarm_ids:
            try:
                # Get alarm
                alarm = await alarm_crud.get(db, alarm_id)
                if not alarm:
                    errors.append(f"Alarm {alarm_id} not found")
                    continue

                # Check if already acknowledged
                if alarm.is_acknowledged:
                    errors.append(f"Alarm {alarm_id} already acknowledged")
                    continue

                # Update alarm
                update_data = {
                    "is_acknowledged": True,
                    "acknowledged_by": current_user.id,
                    "acknowledged_at": datetime.utcnow(),
                    "acknowledgment_notes": notes
                }

                await alarm_crud.update(db, alarm, update_data)
                acknowledged_count += 1

            except Exception as e:
                errors.append(f"Error acknowledging alarm {alarm_id}: {str(e)}")

        return {
            "success": True,
            "message": f"Successfully acknowledged {acknowledged_count} out of {len(alarm_ids)} alarms",
            "data": {
                "total_requested": len(alarm_ids),
                "acknowledged": acknowledged_count,
                "errors": errors
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk acknowledge alarms: {str(e)}")