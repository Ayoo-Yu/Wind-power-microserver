"""
Wind Farm API endpoints.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session
from ..models import (
    WindFarmCreate,
    WindFarmUpdate,
    WindFarmResponse,
    WindFarmFilter,
    PaginationParams,
    SuccessResponse,
    ErrorResponse
)
from ..services import WindFarmService
from ..auth import get_current_user
from ..exceptions import (
    WindFarmNotFoundException,
    DuplicateWindFarmException,
    InvalidWindFarmDataException,
    AuthorizationException,
    ValidationException
)

router = APIRouter(prefix="/api/v1/wind-farms", tags=["wind-farms"])


@router.post(
    "",
    response_model=WindFarmResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new wind farm",
    description="Create a new wind farm with validation and access control",
    responses={
        201: {"description": "Wind farm created successfully"},
        400: {"description": "Invalid wind farm data", "model": ErrorResponse},
        409: {"description": "Wind farm code already exists", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def create_wind_farm(
    wind_farm_data: WindFarmCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Create a new wind farm."""
    try:
        service = WindFarmService()
        wind_farm = await service.create_wind_farm(
            db=db,
            wind_farm_data=wind_farm_data,
            current_user_id=current_user.id
        )
        return wind_farm

    except (ValidationException, InvalidWindFarmDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateWindFarmException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create wind farm: {str(e)}")


@router.get(
    "/{wind_farm_id}",
    response_model=WindFarmResponse,
    summary="Get wind farm by ID",
    description="Retrieve detailed information about a specific wind farm",
    responses={
        200: {"description": "Wind farm retrieved successfully"},
        404: {"description": "Wind farm not found", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_wind_farm(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get wind farm by ID."""
    try:
        service = WindFarmService()
        wind_farm = await service.get_wind_farm(
            db=db,
            wind_farm_id=wind_farm_id,
            current_user_id=current_user.id
        )
        return wind_farm

    except WindFarmNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get wind farm: {str(e)}")


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Get list of wind farms",
    description="Retrieve paginated list of wind farms with filtering and search capabilities",
    responses={
        200: {"description": "Wind farms retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_wind_farms(
    # Filter parameters
    name: Optional[str] = Query(None, description="Filter by name (case-insensitive partial match)"),
    code: Optional[str] = Query(None, description="Filter by code (case-insensitive partial match)"),
    location: Optional[str] = Query(None, description="Filter by location (case-insensitive partial match)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    min_capacity: Optional[float] = Query(None, description="Minimum total capacity (MW)"),
    max_capacity: Optional[float] = Query(None, description="Maximum total capacity (MW)"),

    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),

    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get list of wind farms with filtering and pagination."""
    try:
        service = WindFarmService()

        # Build filter parameters
        filter_params = None
        if any([name, code, location, status, min_capacity, max_capacity]):
            filter_params = WindFarmFilter(
                name=name,
                code=code,
                location=location,
                status=status,
                min_capacity=min_capacity,
                max_capacity=max_capacity
            )

        # Build pagination parameters
        pagination = PaginationParams(page=page, size=size)

        result = await service.get_wind_farms(
            db=db,
            current_user_id=current_user.id,
            filter_params=filter_params,
            pagination=pagination
        )

        return {
            "success": True,
            "message": "Wind farms retrieved successfully",
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
        raise HTTPException(status_code=500, detail=f"Failed to get wind farms: {str(e)}")


@router.put(
    "/{wind_farm_id}",
    response_model=WindFarmResponse,
    summary="Update wind farm",
    description="Update wind farm information with validation and access control",
    responses={
        200: {"description": "Wind farm updated successfully"},
        404: {"description": "Wind farm not found", "model": ErrorResponse},
        400: {"description": "Invalid wind farm data", "model": ErrorResponse},
        409: {"description": "Wind farm code already exists", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def update_wind_farm(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    wind_farm_data: WindFarmUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Update wind farm information."""
    try:
        service = WindFarmService()
        wind_farm = await service.update_wind_farm(
            db=db,
            wind_farm_id=wind_farm_id,
            wind_farm_data=wind_farm_data,
            current_user_id=current_user.id
        )
        return wind_farm

    except WindFarmNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationException, InvalidWindFarmDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateWindFarmException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update wind farm: {str(e)}")


@router.delete(
    "/{wind_farm_id}",
    response_model=SuccessResponse,
    summary="Delete wind farm",
    description="Delete a wind farm (soft delete if it has turbines, hard delete if empty)",
    responses={
        200: {"description": "Wind farm deleted successfully"},
        404: {"description": "Wind farm not found", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def delete_wind_farm(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Delete wind farm."""
    try:
        service = WindFarmService()
        success = await service.delete_wind_farm(
            db=db,
            wind_farm_id=wind_farm_id,
            current_user_id=current_user.id
        )

        return {
            "success": success,
            "message": f"Wind farm {wind_farm_id} deleted successfully"
        }

    except WindFarmNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete wind farm: {str(e)}")


@router.get(
    "/{wind_farm_id}/statistics",
    response_model=Dict[str, Any],
    summary="Get wind farm statistics",
    description="Get comprehensive statistics for a specific wind farm",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        404: {"description": "Wind farm not found", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_wind_farm_statistics(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get wind farm statistics."""
    try:
        service = WindFarmService()
        statistics = await service.get_wind_farm_statistics(
            db=db,
            wind_farm_id=wind_farm_id,
            current_user_id=current_user.id
        )

        return {
            "success": True,
            "message": "Wind farm statistics retrieved successfully",
            "data": statistics
        }

    except WindFarmNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get wind farm statistics: {str(e)}")


@router.get(
    "/search/{query}",
    response_model=List[WindFarmResponse],
    summary="Search wind farms",
    description="Search wind farms by name, code, or location",
    responses={
        200: {"description": "Search results retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def search_wind_farms(
    query: str = Path(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Search wind farms."""
    try:
        service = WindFarmService()
        results = await service.search_wind_farms(
            db=db,
            query=query,
            current_user_id=current_user.id,
            limit=limit
        )

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search wind farms: {str(e)}")


@router.get(
    "/by-status/{status}",
    response_model=List[WindFarmResponse],
    summary="Get wind farms by status",
    description="Get all wind farms filtered by status",
    responses={
        200: {"description": "Wind farms retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_wind_farms_by_status(
    status: str = Path(..., description="Wind farm status"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get wind farms by status."""
    try:
        service = WindFarmService()
        wind_farms = await service.get_wind_farms_by_status(
            db=db,
            status=status,
            current_user_id=current_user.id
        )

        return wind_farms

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get wind farms by status: {str(e)}")


@router.get(
    "/by-code/{code}",
    response_model=WindFarmResponse,
    summary="Get wind farm by code",
    description="Get wind farm by its unique code",
    responses={
        200: {"description": "Wind farm retrieved successfully"},
        404: {"description": "Wind farm not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_wind_farm_by_code(
    code: str = Path(..., description="Wind farm code"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get wind farm by code."""
    try:
        service = WindFarmService()
        wind_farm = await service.get_wind_farm_by_code(db, code)

        if not wind_farm:
            raise HTTPException(status_code=404, detail=f"Wind farm with code '{code}' not found")

        return wind_farm

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get wind farm by code: {str(e)}")