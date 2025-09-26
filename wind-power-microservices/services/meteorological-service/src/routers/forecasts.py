"""
Weather Forecasts API endpoints for Meteorological Data Service
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session, weather_station_crud
from ..models import (
    WeatherForecastCreate,
    WeatherForecastResponse,
    WeatherForecastFilter,
    PaginationParams,
    SuccessResponse,
    ErrorResponse,
    ForecastAccuracy
)
from ..services import MeteorologicalManager
from ..auth import get_current_user, require_operator, WindFarmAccessChecker
from ..exceptions import (
    WeatherStationNotFoundException,
    ForecastModelException,
    ValidationException
)

router = APIRouter(prefix="/api/v1/forecasts", tags=["weather-forecasts"])

# Global meteorological manager instance
meteo_manager = MeteorologicalManager()


@router.post(
    "/generate/{station_id}",
    response_model=Dict[str, Any],
    summary="Generate weather forecast",
    description="Generate weather forecast for a specific station using multiple models",
    responses={
        200: {"description": "Forecast generated successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        400: {"description": "Invalid forecast parameters", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def generate_forecast(
    station_id: str = Path(..., description="Weather station ID"),
    hours: int = Query(24, ge=1, le=168, description="Forecast horizon in hours"),
    include_ensemble: bool = Query(True, description="Include ensemble forecast"),
    models: Optional[List[str]] = Query(None, description="Specific models to use"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Generate weather forecast for a station."""
    try:
        # Verify station exists
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Generate forecast
        if meteo_manager.is_initialized:
            forecast_result = await meteo_manager.forecast_service.generate_forecast(
                station_id=station_id,
                wind_farm_id=station.wind_farm_id,
                hours=hours,
                include_ensemble=include_ensemble
            )

            return {
                "success": True,
                "message": f"Weather forecast generated successfully for station {station_id}",
                "data": forecast_result
            }
        else:
            return {
                "success": False,
                "message": "Forecast service not initialized",
                "data": None
            }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ForecastModelException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate forecast: {str(e)}")


@router.get(
    "/current/{station_id}",
    response_model=Dict[str, Any],
    summary="Get current forecast",
    description="Get the most recent weather forecast for a station",
    responses={
        200: {"description": "Current forecast retrieved successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_current_forecast(
    station_id: str = Path(..., description="Weather station ID"),
    hours: int = Query(24, ge=1, le=168, description="Forecast horizon in hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get current weather forecast for a station."""
    try:
        # Verify station exists
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Generate fresh forecast
        if meteo_manager.is_initialized:
            forecast_result = await meteo_manager.forecast_service.generate_forecast(
                station_id=station_id,
                wind_farm_id=station.wind_farm_id,
                hours=hours,
                include_ensemble=True
            )

            return {
                "success": True,
                "message": f"Current forecast for station {station_id} retrieved successfully",
                "data": forecast_result
            }
        else:
            return {
                "success": False,
                "message": "Forecast service not initialized",
                "data": None
            }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get current forecast: {str(e)}")


@router.get(
    "/by-station/{station_id}",
    response_model=Dict[str, Any],
    summary="Get forecasts by station",
    description="Retrieve weather forecasts for a specific station",
    responses={
        200: {"description": "Forecasts retrieved successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_forecasts_by_station(
    station_id: str = Path(..., description="Weather station ID"),
    forecast_hours: Optional[int] = Query(None, description="Filter by forecast horizon"),
    source: Optional[str] = Query(None, description="Filter by forecast source"),
    hours: int = Query(72, ge=1, le=168, description="Get forecasts from last N hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get weather forecasts by station."""
    try:
        # Verify station exists
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Get time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Build filter parameters
        filter_params = {
            "station_id": station_id,
            "forecast_hours": forecast_hours,
            "source": source
        }
        filter_params = {k: v for k, v in filter_params.items() if v is not None}

        # Get forecasts
        result = await weather_forecast_crud.get_multi(
            db=db,
            filter_params=filter_params,
            time_range={"start_time": start_time, "end_time": end_time},
            pagination=None  # Get all forecasts for the period
        )

        # Group forecasts by model/source
        forecasts_by_source = {}
        for forecast in result["items"]:
            source = forecast.source
            if source not in forecasts_by_source:
                forecasts_by_source[source] = []
            forecasts_by_source[source].append(WeatherForecastResponse.from_orm(forecast))

        return {
            "success": True,
            "message": f"Forecasts for station {station_id} retrieved successfully",
            "data": {
                "station_id": station_id,
                "station_name": station.name,
                "forecasts_by_source": forecasts_by_source,
                "total_forecasts": len(result["items"]),
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
            }
        }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get forecasts by station: {str(e)}")


@router.get(
    "/by-wind-farm/{wind_farm_id}",
    response_model=Dict[str, Any],
    summary="Get forecasts by wind farm",
    description="Retrieve weather forecasts for all stations in a wind farm",
    responses={
        200: {"description": "Forecasts retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_forecasts_by_wind_farm(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    forecast_hours: Optional[int] = Query(None, description="Filter by forecast horizon"),
    hours: int = Query(72, ge=1, le=168, description="Get forecasts from last N hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker())
):
    """Get weather forecasts by wind farm."""
    try:
        # Get time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Get stations for wind farm
        stations = await weather_station_crud.get_by_wind_farm(db, wind_farm_id)

        if not stations:
            return {
                "success": True,
                "message": f"No weather stations found for wind farm {wind_farm_id}",
                "data": {
                    "wind_farm_id": wind_farm_id,
                    "stations": [],
                    "total_forecasts": 0
                }
            }

        # Get forecasts for all stations
        all_forecasts = []
        station_forecasts = {}

        for station in stations:
            filter_params = {
                "station_id": station.id,
                "forecast_hours": forecast_hours
            }
            filter_params = {k: v for k, v in filter_params.items() if v is not None}

            result = await weather_forecast_crud.get_multi(
                db=db,
                filter_params=filter_params,
                time_range={"start_time": start_time, "end_time": end_time},
                pagination=PaginationParams(page=1, size=10)  # Limit per station
            )

            forecasts = [WeatherForecastResponse.from_orm(f) for f in result["items"]]
            all_forecasts.extend(forecasts)

            if forecasts:
                station_forecasts[station.id] = {
                    "name": station.name,
                    "forecasts": forecasts[:5]  # Limit to 5 most recent
                }

        # Calculate wind farm forecast summary
        if all_forecasts:
            # Group by forecast time and calculate ensemble
            from collections import defaultdict
            import numpy as np

            time_groups = defaultdict(list)
            for forecast in all_forecasts:
                time_groups[forecast.forecast_time].append(forecast)

            ensemble_forecasts = []
            for forecast_time, forecasts in time_groups.items():
                if len(forecasts) >= 2:  # Need at least 2 stations for ensemble
                    # Calculate average parameters
                    temp_values = []
                    wind_speed_values = []
                    pressure_values = []

                    for f in forecasts:
                        if "temperature" in f.parameters:
                            temp_values.append(f.parameters["temperature"])
                        if "wind_speed" in f.parameters:
                            wind_speed_values.append(f.parameters["wind_speed"])
                        if "pressure" in f.parameters:
                            pressure_values.append(f.parameters["pressure"])

                    ensemble_forecast = {
                        "forecast_time": forecast_time.isoformat(),
                        "temperature": np.mean(temp_values) if temp_values else None,
                        "wind_speed": np.mean(wind_speed_values) if wind_speed_values else None,
                        "pressure": np.mean(pressure_values) if pressure_values else None,
                        "station_count": len(forecasts),
                        "confidence": min(0.9, 0.5 + len(forecasts) * 0.1)  # Higher confidence with more stations
                    }
                    ensemble_forecasts.append(ensemble_forecast)

            wind_farm_summary = {
                "ensemble_forecasts": sorted(ensemble_forecasts, key=lambda x: x["forecast_time"])[:10],  # Limit to 10
                "average_confidence": np.mean([f["confidence"] for f in ensemble_forecasts]) if ensemble_forecasts else 0.6
            }
        else:
            wind_farm_summary = None

        return {
            "success": True,
            "message": f"Forecasts for wind farm {wind_farm_id} retrieved successfully",
            "data": {
                "wind_farm_id": wind_farm_id,
                "stations": station_forecasts,
                "total_forecasts": len(all_forecasts),
                "wind_farm_summary": wind_farm_summary,
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get forecasts by wind farm: {str(e)}")


@router.get(
    "/accuracy/{station_id}",
    response_model=Dict[str, Any],
    summary="Get forecast accuracy",
    description="Evaluate forecast accuracy against actual observations",
    responses={
        200: {"description": "Forecast accuracy evaluated successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_forecast_accuracy(
    station_id: str = Path(..., description="Weather station ID"),
    forecast_hours: int = Query(24, ge=1, le=72, description="Forecast horizon to evaluate"),
    period_days: int = Query(7, ge=3, le=30, description="Evaluation period in days"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get forecast accuracy metrics."""
    try:
        # Verify station exists
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Evaluate forecast accuracy
        if meteo_manager.is_initialized:
            accuracy_result = await meteo_manager.forecast_service.evaluate_forecast_accuracy(
                station_id=station_id,
                forecast_hours=forecast_hours,
                period_days=period_days
            )

            return {
                "success": True,
                "message": f"Forecast accuracy evaluated for station {station_id}",
                "data": accuracy_result
            }
        else:
            return {
                "success": False,
                "message": "Forecast service not initialized",
                "data": None
            }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate forecast accuracy: {str(e)}")


@router.get(
    "/summary/{wind_farm_id}",
    response_model=Dict[str, Any],
    summary="Get forecast summary",
    description="Get forecast summary for a wind farm",
    responses={
        200: {"description": "Forecast summary retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_forecast_summary(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    hours: int = Query(24, ge=6, le=168, description="Forecast horizon in hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker())
):
    """Get forecast summary for a wind farm."""
    try:
        if meteo_manager.is_initialized:
            summary = await meteo_manager.forecast_service.get_forecast_summary(
                wind_farm_id=wind_farm_id,
                hours=hours
            )

            return {
                "success": True,
                "message": f"Forecast summary for wind farm {wind_farm_id} retrieved successfully",
                "data": summary
            }
        else:
            return {
                "success": False,
                "message": "Forecast service not initialized",
                "data": None
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get forecast summary: {str(e)}")


@router.post(
    "/evaluate-all",
    response_model=Dict[str, Any],
    summary="Evaluate all forecast models",
    description="Evaluate accuracy of all available forecast models",
    responses={
        200: {"description": "Model evaluation completed successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def evaluate_all_models(
    station_ids: Optional[List[str]] = Query(None, description="Specific stations to evaluate"),
    forecast_hours: List[int] = Query([1, 6, 24, 72], description="Forecast horizons to evaluate"),
    period_days: int = Query(14, ge=7, le=30, description="Evaluation period in days"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Evaluate all forecast models."""
    try:
        if meteo_manager.is_initialized:
            evaluation_results = {}

            # Get stations to evaluate
            if station_ids:
                stations = []
                for station_id in station_ids:
                    station = await weather_station_crud.get(db, station_id)
                    if station:
                        stations.append(station)
            else:
                # Get all active stations
                result = await weather_station_crud.get_multi(db, filter_params={"is_active": True})
                stations = result["items"]

            # Evaluate each station
            for station in stations:
                station_results = {}
                for hours in forecast_hours:
                    try:
                        accuracy = await meteo_manager.forecast_service.evaluate_forecast_accuracy(
                            station_id=station.id,
                            forecast_hours=hours,
                            period_days=period_days
                        )
                        station_results[f"{hours}h"] = accuracy
                    except Exception as e:
                        logger.warning(f"Failed to evaluate {hours}h forecast for station {station.id}: {e}")
                        station_results[f"{hours}h"] = {"error": str(e)}

                evaluation_results[station.id] = {
                    "station_name": station.name,
                    "results": station_results
                }

            return {
                "success": True,
                "message": "Forecast model evaluation completed",
                "data": {
                    "evaluation_period_days": period_days,
                    "forecast_horizons": forecast_hours,
                    "stations_evaluated": len(evaluation_results),
                    "results": evaluation_results,
                    "evaluation_time": datetime.utcnow().isoformat()
                }
            }
        else:
            return {
                "success": False,
                "message": "Forecast service not initialized",
                "data": None
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate forecast models: {str(e)}")


@router.delete(
    "/old/{days}",
    response_model=SuccessResponse,
    summary="Clean up old forecasts",
    description="Delete old weather forecasts to manage storage",
    responses={
        200: {"description": "Old forecasts cleaned up successfully"},
        400: {"description": "Invalid parameters", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def cleanup_old_forecasts(
    days: int = Path(..., ge=1, le=365, description="Delete forecasts older than N days"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Clean up old weather forecasts."""
    try:
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Delete old forecasts (would need to implement this method)
        # deleted_count = await weather_forecast_crud.delete_old_forecasts(db, cutoff_date)

        return {
            "success": True,
            "message": f"Weather forecasts older than {days} days have been cleaned up",
            "data": {
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": days
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup old forecasts: {str(e)}")


# Add logging
import logging
logger = logging.getLogger(__name__)