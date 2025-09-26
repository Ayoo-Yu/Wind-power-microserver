"""
Wind Turbine API endpoints.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session
from ..models import (
    WindTurbineCreate,
    WindTurbineUpdate,
    WindTurbineResponse,
    WindTurbineFilter,
    PaginationParams,
    SuccessResponse,
    ErrorResponse
)
from ..services import TurbineService
from ..auth import get_current_user
from ..exceptions import (
    TurbineNotFoundException,
    DuplicateTurbineException,
    InvalidTurbineDataException,
    WindFarmNotFoundException,
    AuthorizationException,
    ValidationException
)

router = APIRouter(prefix="/api/v1/turbines", tags=["turbines"])


@router.post(
    "",
    response_model=WindTurbineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new wind turbine",
    description="Create a new wind turbine within a wind farm",
    responses={
        201: {"description": "Wind turbine created successfully"},
        400: {"description": "Invalid turbine data", "model": ErrorResponse},
        409: {"description": "Turbine ID already exists in wind farm", "model": ErrorResponse},
        404: {"description": "Wind farm not found", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def create_turbine(
    turbine_data: WindTurbineCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Create a new wind turbine."""
    try:
        service = TurbineService()
        turbine = await service.create_turbine(
            db=db,
            turbine_data=turbine_data,
            current_user_id=current_user.id
        )
        return turbine

    except (ValidationException, InvalidTurbineDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateTurbineException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except WindFarmNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create turbine: {str(e)}")


@router.get(
    "/{turbine_id}",
    response_model=WindTurbineResponse,
    summary="Get wind turbine by ID",
    description="Retrieve detailed information about a specific wind turbine",
    responses={
        200: {"description": "Wind turbine retrieved successfully"},
        404: {"description": "Wind turbine not found", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_turbine(
    turbine_id: str = Path(..., description="Wind turbine ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get wind turbine by ID."""
    try:
        service = TurbineService()
        turbine = await service.get_turbine(
            db=db,
            turbine_id=turbine_id,
            current_user_id=current_user.id
        )
        return turbine

    except TurbineNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get turbine: {str(e)}")


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Get list of wind turbines",
    description="Retrieve paginated list of wind turbines with filtering",
    responses={
        200: {"description": "Wind turbines retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_turbines(
    # Filter parameters
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    turbine_id: Optional[str] = Query(None, description="Filter by turbine ID"),
    manufacturer: Optional[str] = Query(None, description="Filter by manufacturer"),
    model: Optional[str] = Query(None, description="Filter by model"),
    status: Optional[str] = Query(None, description="Filter by status"),
    min_power: Optional[float] = Query(None, description="Minimum rated power (MW)"),
    max_power: Optional[float] = Query(None, description="Maximum rated power (MW)"),

    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),

    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get list of wind turbines with filtering and pagination."""
    try:
        service = TurbineService()

        # Build filter parameters
        filter_params = None
        if any([wind_farm_id, turbine_id, manufacturer, model, status, min_power, max_power]):
            filter_params = WindTurbineFilter(
                wind_farm_id=wind_farm_id,
                turbine_id=turbine_id,
                manufacturer=manufacturer,
                model=model,
                status=status,
                min_power=min_power,
                max_power=max_power
            )

        # Build pagination parameters
        pagination = PaginationParams(page=page, size=size)

        result = await service.get_turbines(
            db=db,
            current_user_id=current_user.id,
            filter_params=filter_params,
            pagination=pagination
        )

        return {
            "success": True,
            "message": "Wind turbines retrieved successfully",
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
        raise HTTPException(status_code=500, detail=f"Failed to get turbines: {str(e)}")


@router.put(
    "/{turbine_id}",
    response_model=WindTurbineResponse,
    summary="Update wind turbine",
    description="Update wind turbine information with validation and access control",
    responses={
        200: {"description": "Wind turbine updated successfully"},
        404: {"description": "Wind turbine not found", "model": ErrorResponse},
        400: {"description": "Invalid turbine data", "model": ErrorResponse},
        409: {"description": "Turbine ID already exists", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def update_turbine(
    turbine_id: str = Path(..., description="Wind turbine ID"),
    turbine_data: WindTurbineUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Update wind turbine information."""
    try:
        service = TurbineService()
        turbine = await service.update_turbine(
            db=db,
            turbine_id=turbine_id,
            turbine_data=turbine_data,
            current_user_id=current_user.id
        )
        return turbine

    except TurbineNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationException, InvalidTurbineDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateTurbineException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update turbine: {str(e)}")


@router.delete(
    "/{turbine_id}",
    response_model=SuccessResponse,
    summary="Delete wind turbine",
    description="Delete a wind turbine permanently",
    responses={
        200: {"description": "Wind turbine deleted successfully"},
        404: {"description": "Wind turbine not found", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def delete_turbine(
    turbine_id: str = Path(..., description="Wind turbine ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Delete wind turbine."""
    try:
        service = TurbineService()
        success = await service.delete_turbine(
            db=db,
            turbine_id=turbine_id,
            current_user_id=current_user.id
        )

        return {
            "success": success,
            "message": f"Wind turbine {turbine_id} deleted successfully"
        }

    except TurbineNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete turbine: {str(e)}")


@router.get(
    "/by-wind-farm/{wind_farm_id}",
    response_model=List[WindTurbineResponse],
    summary="Get turbines by wind farm",
    description="Get all turbines within a specific wind farm",
    responses={
        200: {"description": "Turbines retrieved successfully"},
        404: {"description": "Wind farm not found", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_turbines_by_wind_farm(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    status_filter: Optional[str] = Query(None, description="Filter by turbine status"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get turbines by wind farm."""
    try:
        service = TurbineService()
        turbines = await service.get_turbines_by_wind_farm(
            db=db,
            wind_farm_id=wind_farm_id,
            current_user_id=current_user.id,
            status_filter=status_filter
        )
        return turbines

    except WindFarmNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get turbines by wind farm: {str(e)}")


@router.get(
    "/{turbine_id}/statistics",
    response_model=Dict[str, Any],
    summary="Get turbine statistics",
    description="Get operational statistics for a specific wind turbine",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        404: {"description": "Wind turbine not found", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_turbine_statistics(
    turbine_id: str = Path(..., description="Wind turbine ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get turbine statistics."""
    try:
        service = TurbineService()
        statistics = await service.get_turbine_statistics(
            db=db,
            turbine_id=turbine_id,
            current_user_id=current_user.id
        )

        return {
            "success": True,
            "message": "Turbine statistics retrieved successfully",
            "data": statistics
        }

    except TurbineNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get turbine statistics: {str(e)}")


@router.post(
    "/{turbine_id}/control/{action}",
    response_model=SuccessResponse,
    summary="Control wind turbine",
    description="Perform control actions on a wind turbine (start, stop, reset)",
    responses={
        200: {"description": "Control action executed successfully"},
        404: {"description": "Wind turbine not found", "model": ErrorResponse},
        400: {"description": "Invalid control action", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def control_turbine(
    turbine_id: str = Path(..., description="Wind turbine ID"),
    action: str = Path(..., description="Control action (start, stop, reset)"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Control wind turbine."""
    try:
        service = TurbineService()
        result = await service.control_turbine(
            db=db,
            turbine_id=turbine_id,
            action=action,
            current_user_id=current_user.id
        )

        return {
            "success": result,
            "message": f"Turbine {turbine_id} {action} action executed successfully"
        }

    except TurbineNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationException, InvalidTurbineDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to control turbine: {str(e)}")


@router.get(
    "/by-location/nearby",
    response_model=List[WindTurbineResponse],
    summary="Get nearby turbines",
    description="Get turbines within a specified radius of given coordinates",
    responses={
        200: {"description": "Nearby turbines retrieved successfully"},
        400: {"description": "Invalid coordinates", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_nearby_turbines(
    latitude: float = Query(..., description="Latitude"),
    longitude: float = Query(..., description="Longitude"),
    radius_km: float = Query(10.0, description="Search radius in kilometers"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get nearby turbines."""
    try:
        service = TurbineService()
        turbines = await service.get_nearby_turbines(
            db=db,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit,
            current_user_id=current_user.id
        )
        return turbines

    except (ValidationException, InvalidTurbineDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get nearby turbines: {str(e)}")