"""
Shared data models for all microservices.
"""

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import uuid


class BaseSchema(BaseModel):
    """Base schema for all data models."""

    class Config:
        orm_mode = True
        validate_assignment = True
        use_enum_values = True


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class UserRole(str, Enum):
    """User roles in the system."""

    ADMIN = "admin"
    OPERATOR = "operator"
    ANALYST = "analyst"
    VIEWER = "viewer"


class TurbineStatus(str, Enum):
    """Wind turbine operational status."""

    RUNNING = "running"
    STOPPED = "stopped"
    MAINTENANCE = "maintenance"
    FAULT = "fault"
    GRID_DISCONNECTED = "grid_disconnected"


class PredictionType(str, Enum):
    """Types of power predictions."""

    SUPERSHORT = "supershort"  # 15 minutes
    SHORT = "short"            # 4 hours
    MIDDLE = "middle"          # 72 hours


class ReportType(str, Enum):
    """Types of reports."""

    ACTUAL = "actual"
    FORECAST_SHORT = "forecast_short"
    FORECAST_LONG = "forecast_long"


class ServiceStatus(str, Enum):
    """Service health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# User Management Models
class User(BaseSchema):
    """User model."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    full_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    tenant_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Tenant(BaseSchema):
    """Tenant (wind farm) model."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    location: str = Field(..., min_length=1, max_length=200)
    total_capacity: float = Field(..., gt=0)
    turbine_count: int = Field(..., gt=0)
    commissioning_date: Optional[datetime] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Wind Turbine Models
class WindTurbine(BaseSchema):
    """Wind turbine model."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    turbine_id: str = Field(..., min_length=1, max_length=50)
    tenant_id: str
    manufacturer: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=50)
    rated_power: float = Field(..., gt=0)
    rotor_diameter: float = Field(..., gt=0)
    hub_height: float = Field(..., gt=0)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    commissioning_date: Optional[datetime] = None
    status: TurbineStatus = TurbineStatus.RUNNING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Power Data Models
class TurbinePowerData(BaseSchema):
    """Individual turbine power data."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    turbine_id: str
    tenant_id: str
    timestamp: datetime
    active_power: float = Field(..., ge=0)
    reactive_power: Optional[float] = Field(None, ge=0)
    power_factor: Optional[float] = Field(None, ge=0, le=1)
    rotor_speed: Optional[float] = Field(None, ge=0)
    generator_speed: Optional[float] = Field(None, ge=0)
    blade_angle: Optional[float] = Field(None, ge=-10, le=90)
    wind_speed: Optional[float] = Field(None, ge=0)
    wind_direction: Optional[float] = Field(None, ge=0, le=360)
    status: TurbineStatus = TurbineStatus.RUNNING


class WindSpeedData(BaseSchema):
    """Wind speed measurement data."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    turbine_id: str
    tenant_id: str
    timestamp: datetime
    wind_speed: float = Field(..., ge=0)
    wind_direction: Optional[float] = Field(None, ge=0, le=360)
    nacelle_position: Optional[float] = Field(None, ge=0, le=360)


# Weather Data Models
class WeatherData(BaseSchema):
    """Weather station data."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    timestamp: datetime
    temperature: Optional[float] = None
    humidity: Optional[float] = Field(None, ge=0, le=100)
    pressure: Optional[float] = Field(None, ge=800, le=1200)
    wind_speed_avg: Optional[float] = Field(None, ge=0)
    wind_speed_max: Optional[float] = Field(None, ge=0)
    wind_direction: Optional[float] = Field(None, ge=0, le=360)
    visibility: Optional[float] = Field(None, ge=0)
    precipitation: Optional[float] = Field(None, ge=0)
    weather_condition: Optional[str] = None


# Prediction Models
class PredictionResult(BaseSchema):
    """Power prediction result."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    turbine_id: str
    tenant_id: str
    prediction_type: PredictionType
    prediction_timestamp: datetime
    target_timestamp: datetime
    predicted_power: float = Field(..., ge=0)
    confidence_interval_lower: Optional[float] = Field(None, ge=0)
    confidence_interval_upper: Optional[float] = Field(None, ge=0)
    model_version: str
    accuracy_metrics: Optional[Dict[str, float]] = None


# Reporting Models
class ReportConfig(BaseSchema):
    """Report configuration."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    report_type: ReportType
    target_ip: str
    target_port: int
    report_interval: int = Field(..., ge=1)
    is_enabled: bool = True
    last_report_time: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReportLog(BaseSchema):
    """Report execution log."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    report_config_id: str
    tenant_id: str
    report_type: ReportType
    execution_time: datetime
    status: str  # "success", "failed", "partial"
    records_sent: int = Field(..., ge=0)
    error_message: Optional[str] = None
    response_time_ms: Optional[int] = None


# API Response Models
class APIResponse(BaseSchema):
    """Standard API response wrapper."""

    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseSchema):
    """Paginated API response."""

    items: List[Any]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


# Health Check Models
class HealthStatus(BaseSchema):
    """Service health status."""

    service: str
    status: ServiceStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    dependencies: Optional[Dict[str, ServiceStatus]] = None
    response_time_ms: Optional[int] = None


# Event Models
class Event(BaseSchema):
    """Base event model for event-driven architecture."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    aggregate_id: str
    aggregate_type: str
    event_data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1


class TurbineDataEvent(Event):
    """Event for turbine data updates."""

    event_type: str = "turbine.data.updated"
    aggregate_type: str = "turbine"


class PredictionGeneratedEvent(Event):
    """Event for prediction generation."""

    event_type: str = "prediction.generated"
    aggregate_type: str = "prediction"


class ReportScheduledEvent(Event):
    """Event for report scheduling."""

    event_type: str = "report.scheduled"
    aggregate_type: str = "report"}


# Validation Functions
def validate_coordinates(lat: float, lon: float) -> bool:
    """Validate latitude and longitude coordinates."""
    return -90 <= lat <= 90 and -180 <= lon <= 180


def validate_wind_speed(speed: float) -> bool:
    """Validate wind speed (non-negative)."""
    return speed >= 0


def validate_power(power: float) -> bool:
    """Validate power output (non-negative)."""
    return power >= 0


def validate_efficiency(efficiency: float) -> bool:
    """Validate efficiency (0-1 range)."""
    return 0 <= efficiency <= 1