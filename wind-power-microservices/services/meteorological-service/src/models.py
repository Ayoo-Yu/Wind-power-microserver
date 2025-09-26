"""
Data models for Meteorological Data Service
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator


class WeatherDataSource(str, Enum):
    """Weather data sources."""
    OPENWEATHERMAP = "openweathermap"
    WEATHERAPI = "weatherapi"
    NOAA = "noaa"
    MANUAL = "manual"
    SENSOR = "sensor"


class WeatherParameter(str, Enum):
    """Weather parameters."""
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    WIND_SPEED = "wind_speed"
    WIND_DIRECTION = "wind_direction"
    PRESSURE = "pressure"
    PRECIPITATION = "precipitation"
    CLOUD_COVER = "cloud_cover"
    VISIBILITY = "visibility"
    UV_INDEX = "uv_index"


class AlertSeverity(str, Enum):
    """Weather alert severity levels."""
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


class WeatherAlertStatus(str, Enum):
    """Weather alert status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class BaseSchema(BaseModel):
    """Base schema with common fields."""

    class Config:
        orm_mode = True
        allow_population_by_field_name = True


class WeatherStationCreate(BaseSchema):
    """Weather station creation schema."""
    name: str = Field(..., description="Weather station name")
    code: str = Field(..., description="Unique station code")
    wind_farm_id: str = Field(..., description="Associated wind farm ID")
    latitude: float = Field(..., ge=-90, le=90, description="Station latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Station longitude")
    elevation: Optional[float] = Field(None, description="Station elevation in meters")
    source: WeatherDataSource = Field(WeatherDataSource.MANUAL, description="Data source")
    is_active: bool = Field(True, description="Station active status")
    description: Optional[str] = Field(None, description="Station description")


class WeatherStationUpdate(BaseSchema):
    """Weather station update schema."""
    name: Optional[str] = Field(None, description="Weather station name")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Station latitude")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Station longitude")
    elevation: Optional[float] = Field(None, description="Station elevation in meters")
    source: Optional[WeatherDataSource] = Field(None, description="Data source")
    is_active: Optional[bool] = Field(None, description="Station active status")
    description: Optional[str] = Field(None, description="Station description")


class WeatherStationResponse(BaseSchema):
    """Weather station response schema."""
    id: str = Field(..., description="Station ID")
    name: str = Field(..., description="Weather station name")
    code: str = Field(..., description="Unique station code")
    wind_farm_id: str = Field(..., description="Associated wind farm ID")
    latitude: float = Field(..., description="Station latitude")
    longitude: float = Field(..., description="Station longitude")
    elevation: Optional[float] = Field(None, description="Station elevation in meters")
    source: WeatherDataSource = Field(..., description="Data source")
    is_active: bool = Field(..., description="Station active status")
    description: Optional[str] = Field(None, description="Station description")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class WeatherDataCreate(BaseSchema):
    """Weather data creation schema."""
    station_id: str = Field(..., description="Weather station ID")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    parameter: WeatherParameter = Field(..., description="Weather parameter")
    value: float = Field(..., description="Parameter value")
    unit: str = Field(..., description="Unit of measurement")
    timestamp: datetime = Field(..., description="Measurement timestamp")
    source: WeatherDataSource = Field(..., description="Data source")
    quality: str = Field("good", description="Data quality")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class WeatherDataResponse(BaseSchema):
    """Weather data response schema."""
    id: str = Field(..., description="Data ID")
    station_id: str = Field(..., description="Weather station ID")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    parameter: WeatherParameter = Field(..., description="Weather parameter")
    value: float = Field(..., description="Parameter value")
    unit: str = Field(..., description="Unit of measurement")
    timestamp: datetime = Field(..., description="Measurement timestamp")
    source: WeatherDataSource = Field(..., description="Data source")
    quality: str = Field(..., description="Data quality")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_at: datetime = Field(..., description="Creation timestamp")


class WeatherForecastCreate(BaseSchema):
    """Weather forecast creation schema."""
    station_id: str = Field(..., description="Weather station ID")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    forecast_time: datetime = Field(..., description="Forecast target time")
    forecast_hours: int = Field(..., description="Forecast horizon in hours")
    parameters: Dict[str, float] = Field(..., description="Forecast parameters")
    confidence_interval: Optional[Dict[str, Any]] = Field(None, description="Confidence intervals")
    source: WeatherDataSource = Field(..., description="Forecast source")
    model_version: Optional[str] = Field(None, description="Forecast model version")


class WeatherForecastResponse(BaseSchema):
    """Weather forecast response schema."""
    id: str = Field(..., description="Forecast ID")
    station_id: str = Field(..., description="Weather station ID")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    forecast_time: datetime = Field(..., description="Forecast target time")
    forecast_hours: int = Field(..., description="Forecast horizon in hours")
    parameters: Dict[str, float] = Field(..., description="Forecast parameters")
    confidence_interval: Optional[Dict[str, Any]] = Field(None, description="Confidence intervals")
    source: WeatherDataSource = Field(..., description="Forecast source")
    model_version: Optional[str] = Field(None, description="Forecast model version")
    created_at: datetime = Field(..., description="Creation timestamp")


class WeatherAlertCreate(BaseSchema):
    """Weather alert creation schema."""
    alert_id: str = Field(..., description="External alert ID")
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Alert description")
    severity: AlertSeverity = Field(..., description="Alert severity")
    wind_farm_id: str = Field(..., description="Affected wind farm ID")
    effective_time: datetime = Field(..., description="Alert effective time")
    expires_time: datetime = Field(..., description="Alert expiration time")
    areas: List[str] = Field(..., description="Affected areas")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Alert parameters")
    source: WeatherDataSource = Field(..., description="Alert source")


class WeatherAlertResponse(BaseSchema):
    """Weather alert response schema."""
    id: str = Field(..., description="Alert ID")
    alert_id: str = Field(..., description="External alert ID")
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Alert description")
    severity: AlertSeverity = Field(..., description="Alert severity")
    wind_farm_id: str = Field(..., description="Affected wind farm ID")
    effective_time: datetime = Field(..., description="Alert effective time")
    expires_time: datetime = Field(..., description="Alert expiration time")
    areas: List[str] = Field(..., description="Affected areas")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Alert parameters")
    source: WeatherDataSource = Field(..., description="Alert source")
    status: WeatherAlertStatus = Field(..., description="Alert status")
    created_at: datetime = Field(..., description="Creation timestamp")


class WeatherSummary(BaseSchema):
    """Weather summary for a specific location and time."""
    wind_farm_id: str = Field(..., description="Wind farm ID")
    station_id: str = Field(..., description="Weather station ID")
    timestamp: datetime = Field(..., description="Summary timestamp")
    temperature: Optional[float] = Field(None, description="Temperature in Celsius")
    humidity: Optional[float] = Field(None, description="Humidity percentage")
    wind_speed: Optional[float] = Field(None, description="Wind speed in m/s")
    wind_direction: Optional[float] = Field(None, description="Wind direction in degrees")
    pressure: Optional[float] = Field(None, description="Atmospheric pressure in hPa")
    precipitation: Optional[float] = Field(None, description="Precipitation in mm")
    cloud_cover: Optional[float] = Field(None, description="Cloud cover percentage")
    visibility: Optional[float] = Field(None, description="Visibility in km")


class WeatherDataFilter(BaseSchema):
    """Weather data filter parameters."""
    station_id: Optional[str] = Field(None, description="Weather station ID")
    wind_farm_id: Optional[str] = Field(None, description="Wind farm ID")
    parameter: Optional[WeatherParameter] = Field(None, description="Weather parameter")
    source: Optional[WeatherDataSource] = Field(None, description="Data source")
    quality: Optional[str] = Field(None, description="Data quality")


class WeatherForecastFilter(BaseSchema):
    """Weather forecast filter parameters."""
    station_id: Optional[str] = Field(None, description="Weather station ID")
    wind_farm_id: Optional[str] = Field(None, description="Wind farm ID")
    forecast_hours: Optional[int] = Field(None, description="Forecast horizon in hours")
    source: Optional[WeatherDataSource] = Field(None, description="Forecast source")


class WeatherAlertFilter(BaseSchema):
    """Weather alert filter parameters."""
    wind_farm_id: Optional[str] = Field(None, description="Wind farm ID")
    severity: Optional[AlertSeverity] = Field(None, description="Alert severity")
    status: Optional[WeatherAlertStatus] = Field(None, description="Alert status")
    source: Optional[WeatherDataSource] = Field(None, description="Alert source")


class PaginationParams(BaseSchema):
    """Pagination parameters."""
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Page size")


class SuccessResponse(BaseSchema):
    """Success response schema."""
    success: bool = Field(True, description="Success flag")
    message: str = Field(..., description="Response message")


class ErrorResponse(BaseSchema):
    """Error response schema."""
    success: bool = Field(False, description="Success flag")
    message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")


# Weather API Integration Models
class OpenWeatherMapResponse(BaseModel):
    """OpenWeatherMap API response model."""
    coord: Dict[str, float]
    weather: List[Dict[str, Any]]
    main: Dict[str, float]
    wind: Dict[str, float]
    clouds: Dict[str, int]
    visibility: int
    dt: int
    sys: Dict[str, Any]
    timezone: int
    name: str


class WeatherAPIResponse(BaseModel):
    """WeatherAPI response model."""
    location: Dict[str, Any]
    current: Dict[str, Any]
    forecast: Optional[Dict[str, Any]] = None


class NOAAAlertResponse(BaseModel):
    """NOAA weather alert response model."""
    features: List[Dict[str, Any]]
    title: str
    updated: str


# Forecast Models
class ForecastPoint(BaseModel):
    """Single forecast data point."""
    time: datetime
    temperature: float
    wind_speed: float
    wind_direction: float
    pressure: float
    humidity: float
    precipitation: float
    cloud_cover: float


class ForecastSeries(BaseModel):
    """Time series forecast data."""
    station_id: str
    wind_farm_id: str
    forecast_made: datetime
    forecast_points: List[ForecastPoint]
    source: WeatherDataSource
    confidence: float


class ForecastAccuracy(BaseModel):
    """Forecast accuracy metrics."""
    station_id: str
    parameter: WeatherParameter
    forecast_hours: int
    mae: float  # Mean Absolute Error
    rmse: float  # Root Mean Square Error
    mape: float  # Mean Absolute Percentage Error
    correlation: float
    sample_size: int
    period_start: datetime
    period_end: datetime