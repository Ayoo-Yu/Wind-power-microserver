"""
Weather Stations API endpoints for Meteorological Data Service
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session, weather_station_crud
from ..models import (
    WeatherStationCreate,
    WeatherStationUpdate,
    WeatherStationResponse,
    WeatherDataResponse,
    PaginationParams,
    SuccessResponse,
    ErrorResponse
)
from ..services import MeteorologicalManager
from ..auth import get_current_user, require_operator, WindFarmAccessChecker
from ..exceptions import (
    WeatherStationNotFoundException,
    DuplicateWeatherStationException,
    ValidationException
)

router = APIRouter(prefix="/api/v1/weather-stations", tags=["weather-stations"])

# Global meteorological manager instance
meteo_manager = MeteorologicalManager()


@router.post(
    "",
    response_model=WeatherStationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new weather station",
    description="Create a new weather station for meteorological data collection",
    responses={
        201: {"description": "Weather station created successfully"},
        400: {"description": "Invalid station data", "model": ErrorResponse},
        409: {"description": "Weather station already exists", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def create_weather_station(
    station_data: WeatherStationCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Create a new weather station."""
    try:
        # Check for duplicate station code
        existing = await weather_station_crud.get_by_code(db, station_data.code)
        if existing:
            raise HTTPException(status_code=409, detail=f"Weather station with code {station_data.code} already exists")

        # Create station
        station = await weather_station_crud.create(db, station_data.dict())

        # Initialize station with meteorological manager
        if meteo_manager.is_initialized:
            await meteo_manager.collect_weather_data(WeatherStationResponse.from_orm(station))

        return WeatherStationResponse.from_orm(station)

    except DuplicateWeatherStationException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create weather station: {str(e)}")


@router.get(
    "/{station_id}",
    response_model=WeatherStationResponse,
    summary="Get weather station by ID",
    description="Retrieve detailed information about a specific weather station",
    responses={
        200: {"description": "Weather station retrieved successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_weather_station(
    station_id: str = Path(..., description="Weather station ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get weather station by ID."""
    try:
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")
        return WeatherStationResponse.from_orm(station)

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get weather station: {str(e)}")


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Get list of weather stations",
    description="Retrieve paginated list of weather stations with filtering and search capabilities",
    responses={
        200: {"description": "Weather stations retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_weather_stations(
    # Filter parameters
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    source: Optional[str] = Query(None, description="Filter by data source"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),

    # Search parameters
    search: Optional[str] = Query(None, description="Search by station name or code"),

    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),

    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get list of weather stations with filtering and pagination."""
    try:
        # Build filter parameters
        filter_params = None
        if any([wind_farm_id, source, is_active is not None]):
            filter_params = {
                "wind_farm_id": wind_farm_id,
                "source": source,
                "is_active": is_active
            }

        # Build pagination parameters
        pagination = PaginationParams(page=page, size=size)

        result = await weather_station_crud.get_multi(
            db=db,
            filter_params=filter_params,
            search=search,
            pagination=pagination
        )

        return {
            "success": True,
            "message": "Weather stations retrieved successfully",
            "data": [WeatherStationResponse.from_orm(station) for station in result["items"]],
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
        raise HTTPException(status_code=500, detail=f"Failed to get weather stations: {str(e)}")


@router.put(
    "/{station_id}",
    response_model=WeatherStationResponse,
    summary="Update weather station",
    description="Update weather station configuration",
    responses={
        200: {"description": "Weather station updated successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        400: {"description": "Invalid station data", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def update_weather_station(
    station_id: str = Path(..., description="Weather station ID"),
    station_data: WeatherStationUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Update weather station."""
    try:
        # Get existing station
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Update station
        updated_station = await weather_station_crud.update(db, station, station_data.dict(exclude_unset=True))

        return WeatherStationResponse.from_orm(updated_station)

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update weather station: {str(e)}")


@router.delete(
    "/{station_id}",
    response_model=SuccessResponse,
    summary="Delete weather station",
    description="Delete a weather station permanently",
    responses={
        200: {"description": "Weather station deleted successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def delete_weather_station(
    station_id: str = Path(..., description="Weather station ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Delete weather station."""
    try:
        # Get station
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Delete from database
        await weather_station_crud.delete(db, station_id)

        return {
            "success": True,
            "message": f"Weather station {station_id} deleted successfully"
        }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete weather station: {str(e)}")


@router.post(
    "/{station_id}/activate",
    response_model=SuccessResponse,
    summary="Activate weather station",
    description="Activate a weather station for data collection",
    responses={
        200: {"description": "Weather station activated successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def activate_weather_station(
    station_id: str = Path(..., description="Weather station ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Activate weather station."""
    try:
        # Get station
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Activate station
        await weather_station_crud.update(db, station, {"is_active": True})

        return {
            "success": True,
            "message": f"Weather station {station_id} activated successfully"
        }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate weather station: {str(e)}")


@router.post(
    "/{station_id}/deactivate",
    response_model=SuccessResponse,
    summary="Deactivate weather station",
    description="Deactivate a weather station from data collection",
    responses={
        200: {"description": "Weather station deactivated successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def deactivate_weather_station(
    station_id: str = Path(..., description="Weather station ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Deactivate weather station."""
    try:
        # Get station
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Deactivate station
        await weather_station_crud.update(db, station, {"is_active": False})

        return {
            "success": True,
            "message": f"Weather station {station_id} deactivated successfully"
        }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate weather station: {str(e)}")


@router.get(
    "/by-wind-farm/{wind_farm_id}",
    response_model=List[WeatherStationResponse],
    summary="Get weather stations by wind farm",
    description="Get all weather stations for a specific wind farm",
    responses={
        200: {"description": "Weather stations retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_weather_stations_by_wind_farm(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker())
):
    """Get weather stations by wind farm."""
    try:
        # Get stations for wind farm
        stations = await weather_station_crud.get_by_wind_farm(db, wind_farm_id)

        return [WeatherStationResponse.from_orm(station) for station in stations]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get weather stations by wind farm: {str(e)}")


@router.get(
    "/{station_id}/current-data",
    response_model=Dict[str, Any],
    summary="Get current weather data",
    description="Get current weather data for a specific station",
    responses={
        200: {"description": "Current weather data retrieved successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_current_weather_data(
    station_id: str = Path(..., description="Weather station ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get current weather data for a station."""
    try:
        # Get station
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Collect current data
        if meteo_manager.is_initialized:
            result = await meteo_manager.collect_weather_data(
                WeatherStationResponse.from_orm(station),
                include_forecast=False
            )
            return result
        else:
            return {
                "success": False,
                "message": "Meteorological manager not initialized",
                "data": None
            }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get current weather data: {str(e)}")


@router.post(
    "/{station_id}/collect-data",
    response_model=Dict[str, Any],
    summary="Trigger data collection",
    description="Manually trigger weather data collection for a station",
    responses={
        200: {"description": "Data collection triggered successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def trigger_data_collection(
    station_id: str = Path(..., description="Weather station ID"),
    include_forecast: bool = Query(True, description="Include forecast data"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Trigger weather data collection for a station."""
    try:
        # Get station
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Trigger data collection
        if meteo_manager.is_initialized:
            result = await meteo_manager.collect_weather_data(
                WeatherStationResponse.from_orm(station),
                include_forecast=include_forecast
            )
            return result
        else:
            return {
                "success": False,
                "message": "Meteorological manager not initialized",
                "data": None
            }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger data collection: {str(e)}")


@router.get(
    "/{station_id}/latest-data",
    response_model=List[WeatherDataResponse],
    summary="Get latest weather data",
    description="Get the latest weather data for a specific station",
    responses={
        200: {"description": "Latest weather data retrieved successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_latest_weather_data(
    station_id: str = Path(..., description="Weather station ID"),
    hours: int = Query(24, ge=1, le=168, description="Get data from last N hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get latest weather data for a station."""
    try:
        # Get station
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Get latest data
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Get weather data (would need to implement this method)
        # For now, return empty list
        return []

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get latest weather data: {str(e)}")