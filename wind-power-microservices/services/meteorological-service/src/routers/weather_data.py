"""
Weather Data API endpoints for Meteorological Data Service
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session, weather_data_crud, weather_station_crud
from ..models import (
    WeatherDataCreate,
    WeatherDataResponse,
    WeatherParameter,
    WeatherDataSource,
    PaginationParams,
    SuccessResponse,
    ErrorResponse,
    WeatherSummary
)
from ..services import MeteorologicalManager
from ..auth import get_current_user, require_operator, WindFarmAccessChecker
from ..exceptions import (
    WeatherStationNotFoundException,
    InvalidWeatherDataException,
    ValidationException
)

router = APIRouter(prefix="/api/v1/weather-data", tags=["weather-data"])

# Global meteorological manager instance
meteo_manager = MeteorologicalManager()


@router.post(
    "",
    response_model=WeatherDataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create weather data record",
    description="Create a new weather data record (manual or sensor data)",
    responses={
        201: {"description": "Weather data created successfully"},
        400: {"description": "Invalid weather data", "model": ErrorResponse},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def create_weather_data(
    data: WeatherDataCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Create weather data record."""
    try:
        # Validate station exists
        station = await weather_station_crud.get(db, data.station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {data.station_id} not found")

        # Process weather data
        if meteo_manager.is_initialized:
            processing_result = await meteo_manager.data_processor.process_weather_data([data])

            if processing_result["valid_records"] == 0:
                raise HTTPException(status_code=400, detail="Weather data validation failed")

            # Use processed data
            processed_data = processing_result["processed_records"][0]
            weather_data = await weather_data_crud.create(db, processed_data.dict())
        else:
            # Store raw data if processor not available
            weather_data = await weather_data_crud.create(db, data.dict())

        return WeatherDataResponse.from_orm(weather_data)

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidWeatherDataException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create weather data: {str(e)}")


@router.get(
    "/{data_id}",
    response_model=WeatherDataResponse,
    summary="Get weather data by ID",
    description="Retrieve a specific weather data record",
    responses={
        200: {"description": "Weather data retrieved successfully"},
        404: {"description": "Weather data not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_weather_data(
    data_id: str = Path(..., description="Weather data ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get weather data by ID."""
    try:
        weather_data = await weather_data_crud.get(db, data_id)
        if not weather_data:
            raise HTTPException(status_code=404, detail=f"Weather data {data_id} not found")
        return WeatherDataResponse.from_orm(weather_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get weather data: {str(e)}")


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Get weather data records",
    description="Retrieve weather data with filtering and pagination",
    responses={
        200: {"description": "Weather data retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_weather_data_records(
    # Filter parameters
    station_id: Optional[str] = Query(None, description="Filter by weather station ID"),
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    parameter: Optional[WeatherParameter] = Query(None, description="Filter by weather parameter"),
    source: Optional[WeatherDataSource] = Query(None, description="Filter by data source"),
    quality: Optional[str] = Query(None, description="Filter by data quality"),

    # Time range parameters
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    hours: int = Query(24, ge=1, le=168, description="Get data from last N hours"),

    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Page size"),

    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get weather data records with filtering and pagination."""
    try:
        # Determine time range
        if not start_time or not end_time:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)

        # Build filter parameters
        filter_params = {
            "station_id": station_id,
            "wind_farm_id": wind_farm_id,
            "parameter": parameter,
            "source": source,
            "quality": quality
        }
        filter_params = {k: v for k, v in filter_params.items() if v is not None}

        # Build pagination parameters
        pagination = PaginationParams(page=page, size=size)

        # Get weather data
        result = await weather_data_crud.get_multi(
            db=db,
            filter_params=filter_params,
            time_range={"start_time": start_time, "end_time": end_time},
            pagination=pagination
        )

        return {
            "success": True,
            "message": "Weather data retrieved successfully",
            "data": [WeatherDataResponse.from_orm(data) for data in result["items"]],
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
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
        raise HTTPException(status_code=500, detail=f"Failed to get weather data: {str(e)}")


@router.get(
    "/current/summary",
    response_model=Dict[str, Any],
    summary="Get current weather summary",
    description="Get summarized current weather conditions",
    responses={
        200: {"description": "Current weather summary retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_current_weather_summary(
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker() if wind_farm_id else get_current_user)
):
    """Get current weather summary."""
    try:
        if meteo_manager.is_initialized:
            summary = await meteo_manager.get_weather_summary(
                wind_farm_id=wind_farm_id,
                period_hours=1  # Last hour
            )
            return {
                "success": True,
                "message": "Current weather summary retrieved successfully",
                "data": summary
            }
        else:
            return {
                "success": False,
                "message": "Meteorological manager not initialized",
                "data": None
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get weather summary: {str(e)}")


@router.get(
    "/by-station/{station_id}",
    response_model=Dict[str, Any],
    summary="Get weather data by station",
    description="Retrieve weather data for a specific weather station",
    responses={
        200: {"description": "Weather data retrieved successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_weather_data_by_station(
    station_id: str = Path(..., description="Weather station ID"),
    parameter: Optional[WeatherParameter] = Query(None, description="Filter by weather parameter"),
    hours: int = Query(24, ge=1, le=168, description="Get data from last N hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get weather data by station."""
    try:
        # Verify station exists
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Get time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Get weather data for station
        if parameter:
            # Get specific parameter data
            data = await weather_data_crud.get_latest_by_station(db, station_id, parameter)
            records = [data] if data else []
        else:
            # Get all parameters
            result = await weather_data_crud.get_multi(
                db=db,
                filter_params={"station_id": station_id},
                time_range={"start_time": start_time, "end_time": end_time},
                pagination=None
            )
            records = result["items"]

        # Group by parameter for summary
        parameter_summary = {}
        for record in records:
            param = record.parameter
            if param not in parameter_summary:
                parameter_summary[param] = []
            parameter_summary[param].append({
                "value": record.value,
                "unit": record.unit,
                "timestamp": record.timestamp.isoformat(),
                "quality": record.quality
            })

        return {
            "success": True,
            "message": f"Weather data for station {station_id} retrieved successfully",
            "data": {
                "station_id": station_id,
                "station_name": station.name,
                "parameters": parameter_summary,
                "total_records": len(records),
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
            }
        }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get weather data by station: {str(e)}")


@router.get(
    "/by-wind-farm/{wind_farm_id}",
    response_model=Dict[str, Any],
    summary="Get weather data by wind farm",
    description="Retrieve weather data for all stations in a wind farm",
    responses={
        200: {"description": "Weather data retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_weather_data_by_wind_farm(
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    parameter: Optional[WeatherParameter] = Query(None, description="Filter by weather parameter"),
    hours: int = Query(24, ge=1, le=168, description="Get data from last N hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(WindFarmAccessChecker())
):
    """Get weather data by wind farm."""
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
                    "total_records": 0
                }
            }

        # Get weather data for all stations
        all_data = []
        station_summaries = {}

        for station in stations:
            if parameter:
                # Get specific parameter data
                data = await weather_data_crud.get_latest_by_station(db, station.id, parameter)
                if data:
                    all_data.append(data)
                    station_summaries[station.id] = {
                        "name": station.name,
                        "data": WeatherDataResponse.from_orm(data)
                    }
            else:
                # Get recent data for all parameters
                result = await weather_data_crud.get_multi(
                    db=db,
                    filter_params={"station_id": station.id},
                    time_range={"start_time": start_time, "end_time": end_time},
                    pagination=PaginationParams(page=1, size=10)
                )
                all_data.extend(result["items"])

                if result["items"]:
                    latest_data = result["items"][0]  # Most recent
                    station_summaries[station.id] = {
                        "name": station.name,
                        "latest_data": WeatherDataResponse.from_orm(latest_data)
                    }

        # Calculate wind farm summary
        if all_data and parameter:
            values = [d.value for d in all_data if d.quality == "good"]
            if values:
                import numpy as np
                wind_farm_summary = {
                    "parameter": parameter,
                    "average": np.mean(values),
                    "min": np.min(values),
                    "max": np.max(values),
                    "std": np.std(values),
                    "station_count": len(stations),
                    "data_points": len(values)
                }
            else:
                wind_farm_summary = None
        else:
            wind_farm_summary = None

        return {
            "success": True,
            "message": f"Weather data for wind farm {wind_farm_id} retrieved successfully",
            "data": {
                "wind_farm_id": wind_farm_id,
                "stations": station_summaries,
                "total_records": len(all_data),
                "wind_farm_summary": wind_farm_summary,
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get weather data by wind farm: {str(e)}")


@router.get(
    "/time-series/{station_id}/{parameter}",
    response_model=Dict[str, Any],
    summary="Get weather time series",
    description="Retrieve time series weather data for a specific parameter and station",
    responses={
        200: {"description": "Time series data retrieved successfully"},
        404: {"description": "Weather station not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_weather_time_series(
    station_id: str = Path(..., description="Weather station ID"),
    parameter: WeatherParameter = Path(..., description="Weather parameter"),
    start_time: Optional[datetime] = Query(None, description="Start time"),
    end_time: Optional[datetime] = Query(None, description="End time"),
    hours: int = Query(24, ge=1, le=720, description="Get data from last N hours"),
    interval: str = Query("raw", description="Data aggregation interval (raw/hourly/daily)"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get weather time series data."""
    try:
        # Verify station exists
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Determine time range
        if not start_time or not end_time:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)

        # Get time series data
        time_series = await weather_data_crud.get_time_series(
            db, station_id, parameter, start_time, end_time
        )

        # Process based on interval
        processed_series = []
        if interval == "raw":
            processed_series = [WeatherDataResponse.from_orm(data) for data in time_series]
        elif interval in ["hourly", "daily"]:
            processed_series = await _aggregate_time_series(time_series, interval)

        # Calculate statistics
        if time_series:
            values = [d.value for d in time_series if d.quality == "good"]
            if values:
                import numpy as np
                statistics = {
                    "count": len(values),
                    "mean": np.mean(values),
                    "min": np.min(values),
                    "max": np.max(values),
                    "std": np.std(values),
                    "missing_data": len(time_series) - len(values)
                }
            else:
                statistics = None
        else:
            statistics = None

        return {
            "success": True,
            "message": f"Time series data for {parameter} retrieved successfully",
            "data": {
                "station_id": station_id,
                "station_name": station.name,
                "parameter": parameter,
                "interval": interval,
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "data_points": processed_series,
                "statistics": statistics,
                "total_records": len(time_series)
            }
        }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get time series data: {str(e)}")


@router.post(
    "/simulate",
    response_model=Dict[str, Any],
    summary="Simulate weather data",
    description="Generate simulated weather data for testing purposes",
    responses={
        200: {"description": "Data simulation completed"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def simulate_weather_data(
    station_id: str = Query(..., description="Weather station ID for simulation"),
    count: int = Query(10, ge=1, le=100, description="Number of data points to simulate"),
    parameters: List[WeatherParameter] = Query([WeatherParameter.TEMPERATURE, WeatherParameter.WIND_SPEED], description="Parameters to simulate"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(require_operator)
):
    """Simulate weather data for testing."""
    try:
        # Get station info
        station = await weather_station_crud.get(db, station_id)
        if not station:
            raise HTTPException(status_code=404, detail=f"Weather station {station_id} not found")

        # Generate simulated data
        import random
        simulated_data = []
        base_time = datetime.utcnow()

        for i in range(count):
            # Generate realistic values based on parameter
            for param in parameters:
                if param == WeatherParameter.TEMPERATURE:
                    value = random.uniform(-5, 35)  # -5 to 35°C
                    unit = "celsius"
                elif param == WeatherParameter.WIND_SPEED:
                    value = random.uniform(0, 25)  # 0 to 25 m/s
                    unit = "m/s"
                elif param == WeatherParameter.WIND_DIRECTION:
                    value = random.uniform(0, 360)  # 0 to 360 degrees
                    unit = "degrees"
                elif param == WeatherParameter.HUMIDITY:
                    value = random.uniform(30, 90)  # 30% to 90%
                    unit = "percent"
                elif param == WeatherParameter.PRESSURE:
                    value = random.uniform(980, 1040)  # 980 to 1040 hPa
                    unit = "hPa"
                elif param == WeatherParameter.PRECIPITATION:
                    value = random.uniform(0, 10)  # 0 to 10 mm
                    unit = "mm"
                elif param == WeatherParameter.CLOUD_COVER:
                    value = random.uniform(0, 100)  # 0% to 100%
                    unit = "percent"
                else:
                    value = random.uniform(0, 100)
                    unit = ""

                # Determine quality (mostly good)
                quality = random.choice(["good", "good", "good", "good", "uncertain"])

                weather_data = WeatherDataCreate(
                    station_id=station_id,
                    wind_farm_id=station.wind_farm_id,
                    parameter=param,
                    value=value,
                    unit=unit,
                    timestamp=base_time - timedelta(minutes=i*5),  # 5-minute intervals
                    source=WeatherDataSource.MANUAL,
                    quality=quality
                )

                simulated_data.append(weather_data)

        # Process simulated data
        if meteo_manager.is_initialized:
            processing_result = await meteo_manager.data_processor.process_weather_data(simulated_data)

            # Store processed data
            stored_records = []
            for data in processing_result["processed_records"]:
                stored = await weather_data_crud.create(db, data.dict())
                stored_records.append(WeatherDataResponse.from_orm(stored))

            return {
                "success": True,
                "message": f"Generated {len(stored_records)} simulated weather data records",
                "data": {
                    "simulated_records": len(stored_records),
                    "processed_records": processing_result["valid_records"],
                    "quality_issues": len(processing_result["quality_issues"]),
                    "parameters": [p.value for p in parameters]
                }
            }
        else:
            return {
                "success": False,
                "message": "Meteorological manager not initialized",
                "data": None
            }

    except WeatherStationNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to simulate weather data: {str(e)}")


@router.get(
    "/quality/summary",
    response_model=Dict[str, Any],
    summary="Get data quality summary",
    description="Get weather data quality summary and statistics",
    responses={
        200: {"description": "Quality summary retrieved successfully"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_data_quality_summary(
    wind_farm_id: Optional[str] = Query(None, description="Filter by wind farm ID"),
    hours: int = Query(24, ge=1, le=168, description="Time period in hours"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user)
):
    """Get data quality summary."""
    try:
        if meteo_manager.is_initialized:
            quality_summary = await meteo_manager.data_processor.calculate_weather_summary(
                wind_farm_id=wind_farm_id,
                station_id="aggregated",
                start_time=datetime.utcnow() - timedelta(hours=hours),
                end_time=datetime.utcnow()
            )

            # Add quality-specific metrics
            quality_metrics = {
                "total_data_points": 0,
                "good_quality_points": 0,
                "questionable_quality_points": 0,
                "bad_quality_points": 0
            }

            return {
                "success": True,
                "message": "Data quality summary retrieved successfully",
                "data": {
                    "period_summary": quality_summary,
                    "quality_metrics": quality_metrics,
                    "quality_score": 95.0  # Placeholder
                }
            }
        else:
            return {
                "success": False,
                "message": "Meteorological manager not initialized",
                "data": None
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data quality summary: {str(e)}")


# Helper functions
async def _aggregate_time_series(data: List, interval: str) -> List[Dict[str, Any]]:
    """Aggregate time series data by interval."""
    if not data:
        return []

    import pandas as pd
    import numpy as np

    # Convert to DataFrame
    df = pd.DataFrame([
        {
            "timestamp": d.timestamp,
            "value": d.value,
            "quality": d.quality
        }
        for d in data
    ])

    df.set_index("timestamp", inplace=True)

    # Filter good quality data
    df_good = df[df["quality"] == "good"]

    if df_good.empty:
        return []

    # Resample based on interval
    if interval == "hourly":
        resampled = df_good.resample("H")
    elif interval == "daily":
        resampled = df_good.resample("D")
    else:
        return []

    # Calculate statistics
    aggregated = resampled.agg({
        "value": ["mean", "min", "max", "std", "count"]
    })

    aggregated.columns = ["mean", "min", "max", "std", "count"]
    aggregated = aggregated.dropna()

    # Convert to list of dictionaries
    result = []
    for timestamp, row in aggregated.iterrows():
        result.append({
            "timestamp": timestamp.isoformat(),
            "mean_value": round(row["mean"], 2),
            "min_value": round(row["min"], 2),
            "max_value": round(row["max"], 2),
            "std_value": round(row["std"], 2) if not pd.isna(row["std"]) else 0,
            "count": int(row["count"]),
            "interval": interval
        })

    return result