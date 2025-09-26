"""
SCADA Data Points API endpoints.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session, data_point_crud
from ..models import (
    DataPointCreate,
    DataPointUpdate,
    DataPointResponse,
    DataPointFilter,
    PaginationParams,
    SuccessResponse,
    ErrorResponse,
    DataPointType
)
from ..services import ConnectionManager
from ..auth import get_current_user
from ..exceptions import (
    DataPointNotFoundException,
    DuplicateDataPointException,
    InvalidDataPointDataException,
    ValidationException,
    ScadaConnectionNotFoundException
)

router = APIRouter(prefix="/api/v1/data-points", tags=["scada-data-points"])

# Global connection manager instance
connection_manager = ConnectionManager()


@router.post(
    "",
    response_model=DataPointResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new SCADA data point",
    description="Create a new SCADA data point configuration with alarm thresholds",
    responses={
        201: {"description": "SCADA data point created successfully"},
        400: {"description": "Invalid data point data", "model": ErrorResponse},
        409: {"description": "SCADA data point already exists", "model": ErrorResponse},
        404: {"description": "SCADA connection not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def create_data_point(
    data_point_data: DataPointCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Create a new SCADA data point."""
    try:
        # Validate connection exists
        connection = await connection_manager.get_connection(db, data_point_data.connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail=f"SCADA connection {data_point_data.connection_id} not found")

        # Create data point
        data_point = await data_point_crud.create(db, data_point_data.dict())

        # Register data point with connection manager
        for adapter in connection_manager.protocol_adapters.values():
            conn = adapter.get_connection(data_point_data.connection_id)
            if conn:
                conn.add_data_point(data_point)
                break

        return DataPointResponse.from_orm(data_point)

    except (ValidationException, InvalidDataPointDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateDataPointException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create SCADA data point: {str(e)}")


@router.get(
    "/{data_point_id}",
    response_model=DataPointResponse,
    summary="Get SCADA data point by ID",
    description="Retrieve detailed information about a specific SCADA data point",
    responses={
        200: {"description": "SCADA data point retrieved successfully"},
        404: {"description": "SCADA data point not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_data_point(
    data_point_id: str = Path(..., description="SCADA data point ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA data point by ID."""
    try:
        data_point = await data_point_crud.get(db, data_point_id)
        if not data_point:
            raise HTTPException(status_code=404, detail=f"SCADA data point {data_point_id} not found")
        return DataPointResponse.from_orm(data_point)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get SCADA data point: {str(e)}")


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Get list of SCADA data points",
    description="Retrieve paginated list of SCADA data points with filtering and search capabilities",
    responses={
        200: {"description": "SCADA data points retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_data_points(
    # Filter parameters
    connection_id: Optional[str] = Query(None, description="Filter by connection ID"),
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    turbine_id: Optional[str] = Query(None, description="Filter by turbine ID"),
    point_type: Optional[str] = Query(None, description="Filter by point type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    has_alarms: Optional[bool] = Query(None, description="Filter by alarm configuration"),

    # Search parameters
    search: Optional[str] = Query(None, description="Search by point name or description"),

    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),

    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get list of SCADA data points with filtering and pagination."""
    try:
        # Build filter parameters
        filter_params = None
        if any([connection_id, wind_farm_id, turbine_id, point_type, is_active is not None, has_alarms is not None]):
            filter_params = DataPointFilter(
                connection_id=connection_id,
                wind_farm_id=wind_farm_id,
                turbine_id=turbine_id,
                point_type=point_type,
                is_active=is_active,
                has_alarms=has_alarms
            )

        # Build pagination parameters
        pagination = PaginationParams(page=page, size=size)

        result = await data_point_crud.get_multi(
            db=db,
            filter_params=filter_params,
            search=search,
            pagination=pagination
        )

        return {
            "success": True,
            "message": "SCADA data points retrieved successfully",
            "data": result["items"],
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
        raise HTTPException(status_code=500, detail=f"Failed to get SCADA data points: {str(e)}")


@router.put(
    "/{data_point_id}",
    response_model=DataPointResponse,
    summary="Update SCADA data point",
    description="Update SCADA data point configuration including alarm thresholds",
    responses={
        200: {"description": "SCADA data point updated successfully"},
        404: {"description": "SCADA data point not found", "model": ErrorResponse},
        400: {"description": "Invalid data point data", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def update_data_point(
    data_point_id: str = Path(..., description="SCADA data point ID"),
    data_point_data: DataPointUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Update SCADA data point."""
    try:
        # Get existing data point
        data_point = await data_point_crud.get(db, data_point_id)
        if not data_point:
            raise HTTPException(status_code=404, detail=f"SCADA data point {data_point_id} not found")

        # Update data point
        updated_data_point = await data_point_crud.update(db, data_point, data_point_data.dict(exclude_unset=True))

        # Update connection manager if needed
        if any(key in data_point_data.dict(exclude_unset=True) for key in ["is_active", "alarm_thresholds", "scaling_factor"]):
            for adapter in connection_manager.protocol_adapters.values():
                conn = adapter.get_connection(data_point.connection_id)
                if conn:
                    conn.update_data_point(data_point_id, updated_data_point)
                    break

        return DataPointResponse.from_orm(updated_data_point)

    except (ValidationException, InvalidDataPointDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update SCADA data point: {str(e)}")


@router.delete(
    "/{data_point_id}",
    response_model=SuccessResponse,
    summary="Delete SCADA data point",
    description="Delete a SCADA data point configuration",
    responses={
        200: {"description": "SCADA data point deleted successfully"},
        404: {"description": "SCADA data point not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def delete_data_point(
    data_point_id: str = Path(..., description="SCADA data point ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Delete SCADA data point."""
    try:
        # Get data point
        data_point = await data_point_crud.get(db, data_point_id)
        if not data_point:
            raise HTTPException(status_code=404, detail=f"SCADA data point {data_point_id} not found")

        # Remove from connection manager
        for adapter in connection_manager.protocol_adapters.values():
            conn = adapter.get_connection(data_point.connection_id)
            if conn:
                conn.remove_data_point(data_point_id)
                break

        # Delete from database
        await data_point_crud.delete(db, data_point_id)

        return {
            "success": True,
            "message": f"SCADA data point {data_point_id} deleted successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete SCADA data point: {str(e)}")


@router.post(
    "/{data_point_id}/enable",
    response_model=SuccessResponse,
    summary="Enable SCADA data point",
    description="Enable data collection for a SCADA data point",
    responses={
        200: {"description": "SCADA data point enabled successfully"},
        404: {"description": "SCADA data point not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def enable_data_point(
    data_point_id: str = Path(..., description="SCADA data point ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Enable SCADA data point."""
    try:
        # Get data point
        data_point = await data_point_crud.get(db, data_point_id)
        if not data_point:
            raise HTTPException(status_code=404, detail=f"SCADA data point {data_point_id} not found")

        # Enable data point
        await data_point_crud.update(db, data_point, {"is_active": True})

        # Update connection manager
        for adapter in connection_manager.protocol_adapters.values():
            conn = adapter.get_connection(data_point.connection_id)
            if conn:
                conn.enable_data_point(data_point_id)
                break

        return {
            "success": True,
            "message": f"SCADA data point {data_point_id} enabled successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enable SCADA data point: {str(e)}")


@router.post(
    "/{data_point_id}/disable",
    response_model=SuccessResponse,
    summary="Disable SCADA data point",
    description="Disable data collection for a SCADA data point",
    responses={
        200: {"description": "SCADA data point disabled successfully"},
        404: {"description": "SCADA data point not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def disable_data_point(
    data_point_id: str = Path(..., description="SCADA data point ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Disable SCADA data point."""
    try:
        # Get data point
        data_point = await data_point_crud.get(db, data_point_id)
        if not data_point:
            raise HTTPException(status_code=404, detail=f"SCADA data point {data_point_id} not found")

        # Disable data point
        await data_point_crud.update(db, data_point, {"is_active": False})

        # Update connection manager
        for adapter in connection_manager.protocol_adapters.values():
            conn = adapter.get_connection(data_point.connection_id)
            if conn:
                conn.disable_data_point(data_point_id)
                break

        return {
            "success": True,
            "message": f"SCADA data point {data_point_id} disabled successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disable SCADA data point: {str(e)}")


@router.get(
    "/by-connection/{connection_id}",
    response_model=List[DataPointResponse],
    summary="Get SCADA data points by connection",
    description="Get all SCADA data points for a specific connection",
    responses={
        200: {"description": "SCADA data points retrieved successfully"},
        404: {"description": "SCADA connection not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_data_points_by_connection(
    connection_id: str = Path(..., description="SCADA connection ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA data points by connection."""
    try:
        # Validate connection exists
        connection = await connection_manager.get_connection(db, connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail=f"SCADA connection {connection_id} not found")

        # Get data points for connection
        result = await data_point_crud.get_multi(
            db=db,
            filter_params=DataPointFilter(connection_id=connection_id),
            pagination=None  # Get all data points for this connection
        )

        return result["items"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get SCADA data points by connection: {str(e)}")


@router.get(
    "/by-turbine/{turbine_id}",
    response_model=List[DataPointResponse],
    summary="Get SCADA data points by turbine",
    description="Get all SCADA data points for a specific turbine",
    responses={
        200: {"description": "SCADA data points retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_data_points_by_turbine(
    turbine_id: str = Path(..., description="Turbine ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get SCADA data points by turbine."""
    try:
        # Get data points for turbine
        result = await data_point_crud.get_multi(
            db=db,
            filter_params=DataPointFilter(turbine_id=turbine_id),
            pagination=None  # Get all data points for this turbine
        )

        return result["items"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get SCADA data points by turbine: {str(e)}")


@router.post(
    "/{data_point_id}/test-alarm",
    response_model=Dict[str, Any],
    summary="Test alarm configuration",
    description="Test the alarm configuration for a SCADA data point",
    responses={
        200: {"description": "Alarm test completed"},
        404: {"description": "SCADA data point not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def test_alarm_configuration(
    data_point_id: str = Path(..., description="SCADA data point ID"),
    test_value: float = Query(..., description="Test value to check against alarm thresholds"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Test alarm configuration for a SCADA data point."""
    try:
        # Get data point
        data_point = await data_point_crud.get(db, data_point_id)
        if not data_point:
            raise HTTPException(status_code=404, detail=f"SCADA data point {data_point_id} not found")

        # Test alarm thresholds
        alarms_triggered = []

        if data_point.alarm_thresholds:
            thresholds = data_point.alarm_thresholds

            # Check high alarm
            if "high_alarm" in thresholds and test_value > thresholds["high_alarm"]:
                alarms_triggered.append({
                    "type": "high_alarm",
                    "threshold": thresholds["high_alarm"],
                    "actual_value": test_value,
                    "severity": "warning"
                })

            # Check high-high alarm (critical)
            if "high_high_alarm" in thresholds and test_value > thresholds["high_high_alarm"]:
                alarms_triggered.append({
                    "type": "high_high_alarm",
                    "threshold": thresholds["high_high_alarm"],
                    "actual_value": test_value,
                    "severity": "critical"
                })

            # Check low alarm
            if "low_alarm" in thresholds and test_value < thresholds["low_alarm"]:
                alarms_triggered.append({
                    "type": "low_alarm",
                    "threshold": thresholds["low_alarm"],
                    "actual_value": test_value,
                    "severity": "warning"
                })

            # Check low-low alarm (critical)
            if "low_low_alarm" in thresholds and test_value < thresholds["low_low_alarm"]:
                alarms_triggered.append({
                    "type": "low_low_alarm",
                    "threshold": thresholds["low_low_alarm"],
                    "actual_value": test_value,
                    "severity": "critical"
                })

        return {
            "success": True,
            "message": "Alarm configuration test completed",
            "data": {
                "data_point_id": data_point_id,
                "test_value": test_value,
                "alarms_triggered": alarms_triggered,
                "total_alarms": len(alarms_triggered),
                "is_normal": len(alarms_triggered) == 0
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test alarm configuration: {str(e)}")