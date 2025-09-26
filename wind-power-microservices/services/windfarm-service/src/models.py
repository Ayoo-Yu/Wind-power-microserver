"""
Data models for Wind Farm Management Service.
"""

from pydantic import BaseModel, Field, validator, EmailStr
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class WindFarmStatus(str, Enum):
    """Wind farm operational status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    UNDER_CONSTRUCTION = "under_construction"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"


class TurbineStatus(str, Enum):
    """Wind turbine operational status."""

    RUNNING = "running"
    STOPPED = "stopped"
    MAINTENANCE = "maintenance"
    FAULT = "fault"
    GRID_DISCONNECTED = "grid_disconnected"
    UNKNOWN = "unknown"


class UserRole(str, Enum):
    """User roles for wind farm access."""

    ADMIN = "admin"
    OPERATOR = "operator"
    ANALYST = "analyst"
    VIEWER = "viewer"


# Base Models
class BaseSchema(BaseModel):
    """Base schema for all data models."""

    class Config:
        orm_mode = True
        validate_assignment = True
        use_enum_values = True


# Wind Farm Models
class WindFarmBase(BaseSchema):
    """Base wind farm schema."""

    code: str = Field(..., min_length=3, max_length=20, description="Wind farm unique code")
    name: str = Field(..., min_length=1, max_length=100, description="Wind farm name")
    description: Optional[str] = Field(None, max_length=500, description="Wind farm description")
    location: str = Field(..., min_length=1, max_length=200, description="Wind farm location")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    total_capacity: float = Field(..., gt=0, description="Total capacity in MW")
    turbine_count: int = Field(..., gt=0, description="Number of turbines")
    commissioning_date: Optional[datetime] = Field(None, description="Commissioning date")
    contact_email: Optional[EmailStr] = Field(None, description="Contact email")
    contact_phone: Optional[str] = Field(None, max_length=20, description="Contact phone")
    address: Optional[str] = Field(None, max_length=300, description="Detailed address")
    status: WindFarmStatus = Field(WindFarmStatus.ACTIVE, description="Wind farm status")

    @validator('code')
    def validate_code(cls, v):
        """Validate wind farm code format."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Code must be alphanumeric with underscores and hyphens only')
        return v.upper()

    @validator('total_capacity', 'turbine_count')
    def validate_capacity_consistency(cls, v, values):
        """Validate capacity consistency."""
        if 'total_capacity' in values and 'turbine_count' in values:
            total_capacity = values.get('total_capacity')
            turbine_count = values.get('turbine_count')
            if total_capacity and turbine_count:
                avg_capacity = total_capacity / turbine_count
                if avg_capacity < 0.5 or avg_capacity > 10:
                    raise ValueError(f'Average capacity per turbine ({avg_capacity:.2f} MW) seems unreasonable')
        return v


class WindFarmCreate(WindFarmBase):
    """Wind farm creation schema."""
    pass


class WindFarmUpdate(BaseSchema):
    """Wind farm update schema."""

    code: Optional[str] = Field(None, min_length=3, max_length=20, description="Wind farm unique code")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Wind farm name")
    description: Optional[str] = Field(None, max_length=500, description="Wind farm description")
    location: Optional[str] = Field(None, min_length=1, max_length=200, description="Wind farm location")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude in decimal degrees")
    total_capacity: Optional[float] = Field(None, gt=0, description="Total capacity in MW")
    turbine_count: Optional[int] = Field(None, gt=0, description="Number of turbines")
    commissioning_date: Optional[datetime] = Field(None, description="Commissioning date")
    contact_email: Optional[EmailStr] = Field(None, description="Contact email")
    contact_phone: Optional[str] = Field(None, max_length=20, description="Contact phone")
    address: Optional[str] = Field(None, max_length=300, description="Detailed address")
    status: Optional[WindFarmStatus] = Field(None, description="Wind farm status")

    @validator('code')
    def validate_code(cls, v):
        """Validate wind farm code format."""
        if v and not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Code must be alphanumeric with underscores and hyphens only')
        return v.upper() if v else v


class WindFarmResponse(WindFarmBase):
    """Wind farm response schema."""

    id: str = Field(..., description="Wind farm ID")
    current_power: Optional[float] = Field(None, description="Current power output in MW")
    running_turbines: Optional[int] = Field(None, description="Number of running turbines")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# Wind Turbine Models
class TurbineBase(BaseSchema):
    """Base wind turbine schema."""

    turbine_id: str = Field(..., min_length=1, max_length=50, description="Turbine ID within wind farm")
    wind_farm_id: str = Field(..., description="Parent wind farm ID")
    manufacturer: str = Field(..., min_length=1, max_length=50, description="Turbine manufacturer")
    model: str = Field(..., min_length=1, max_length=50, description="Turbine model")
    rated_power: float = Field(..., gt=0, description="Rated power in MW")
    rotor_diameter: float = Field(..., gt=0, description="Rotor diameter in meters")
    hub_height: float = Field(..., gt=0, description="Hub height in meters")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    commissioning_date: Optional[datetime] = Field(None, description="Commissioning date")
    status: TurbineStatus = Field(TurbineStatus.RUNNING, description="Turbine status")

    @validator('turbine_id')
    def validate_turbine_id(cls, v):
        """Validate turbine ID format."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Turbine ID must be alphanumeric with underscores and hyphens only')
        return v.upper()


class TurbineCreate(TurbineBase):
    """Wind turbine creation schema."""
    pass


class TurbineUpdate(BaseSchema):
    """Wind turbine update schema."""

    turbine_id: Optional[str] = Field(None, min_length=1, max_length=50, description="Turbine ID within wind farm")
    manufacturer: Optional[str] = Field(None, min_length=1, max_length=50, description="Turbine manufacturer")
    model: Optional[str] = Field(None, min_length=1, max_length=50, description="Turbine model")
    rated_power: Optional[float] = Field(None, gt=0, description="Rated power in MW")
    rotor_diameter: Optional[float] = Field(None, gt=0, description="Rotor diameter in meters")
    hub_height: Optional[float] = Field(None, gt=0, description="Hub height in meters")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude in decimal degrees")
    commissioning_date: Optional[datetime] = Field(None, description="Commissioning date")
    status: Optional[TurbineStatus] = Field(None, description="Turbine status")

    @validator('turbine_id')
    def validate_turbine_id(cls, v):
        """Validate turbine ID format."""
        if v and not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Turbine ID must be alphanumeric with underscores and hyphens only')
        return v.upper() if v else v


class TurbineResponse(TurbineBase):
    """Wind turbine response schema."""

    id: str = Field(..., description="Turbine ID")
    current_power: Optional[float] = Field(None, description="Current power output in MW")
    wind_speed: Optional[float] = Field(None, description="Current wind speed in m/s")
    rotor_speed: Optional[float] = Field(None, description="Current rotor speed in RPM")
    availability: Optional[float] = Field(None, description="Availability percentage")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# User Models
class UserBase(BaseSchema):
    """Base user schema."""

    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    full_name: str = Field(..., min_length=1, max_length=100, description="Full name")
    role: UserRole = Field(UserRole.VIEWER, description="User role")
    is_active: bool = Field(True, description="Is user active")
    is_superuser: bool = Field(False, description="Is superuser")

    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric with underscores and hyphens only')
        return v.lower()


class UserCreate(UserBase):
    """User creation schema."""

    password: str = Field(..., min_length=8, max_length=100, description="Password")


class UserUpdate(BaseSchema):
    """User update schema."""

    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Username")
    email: Optional[EmailStr] = Field(None, description="Email address")
    full_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Full name")
    role: Optional[UserRole] = Field(None, description="User role")
    is_active: Optional[bool] = Field(None, description="Is user active")
    is_superuser: Optional[bool] = Field(None, description="Is superuser")

    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if v and not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric with underscores and hyphens only')
        return v.lower() if v else v


class UserResponse(UserBase):
    """User response schema."""

    id: str = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class UserLogin(BaseSchema):
    """User login schema."""

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class UserLoginResponse(BaseSchema):
    """User login response schema."""

    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field(..., description="Token type")
    user: UserResponse = Field(..., description="User information")


# Wind Farm Access Models
class WindFarmAccess(BaseSchema):
    """Wind farm access schema."""

    user_id: str = Field(..., description="User ID")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    role: UserRole = Field(..., description="Access role")
    granted_by: str = Field(..., description="Granted by user ID")
    granted_at: datetime = Field(..., description="Granted at timestamp")


class WindFarmAccessResponse(WindFarmAccess):
    """Wind farm access response schema."""

    id: str = Field(..., description="Access ID")
    user: UserResponse = Field(..., description="User information")
    wind_farm: WindFarmResponse = Field(..., description="Wind farm information")


# Filter and Pagination Models
class PaginationParams(BaseSchema):
    """Pagination parameters."""

    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Page size")


class WindFarmFilter(BaseSchema):
    """Wind farm filter parameters."""

    name: Optional[str] = Field(None, description="Filter by name")
    code: Optional[str] = Field(None, description="Filter by code")
    location: Optional[str] = Field(None, description="Filter by location")
    status: Optional[WindFarmStatus] = Field(None, description="Filter by status")
    min_capacity: Optional[float] = Field(None, ge=0, description="Minimum capacity")
    max_capacity: Optional[float] = Field(None, ge=0, description="Maximum capacity")


class WindTurbineFilter(BaseSchema):
    """Wind turbine filter parameters."""

    wind_farm_id: Optional[str] = Field(None, description="Filter by wind farm ID")
    turbine_id: Optional[str] = Field(None, description="Filter by turbine ID")
    manufacturer: Optional[str] = Field(None, description="Filter by manufacturer")
    model: Optional[str] = Field(None, description="Filter by model")
    status: Optional[TurbineStatus] = Field(None, description="Filter by status")
    min_power: Optional[float] = Field(None, ge=0, description="Minimum rated power")
    max_power: Optional[float] = Field(None, ge=0, description="Maximum rated power")


class UserFilter(BaseSchema):
    """User filter parameters."""

    username: Optional[str] = Field(None, description="Filter by username")
    email: Optional[str] = Field(None, description="Filter by email")
    role: Optional[UserRole] = Field(None, description="Filter by role")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    is_superuser: Optional[bool] = Field(None, description="Filter by superuser status")


# Response Models
class APIResponse(BaseSchema):
    """Base API response."""

    success: bool = Field(..., description="Request success status")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class SuccessResponse(APIResponse):
    """Success response schema."""

    data: Optional[Any] = Field(None, description="Response data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Response metadata")


class ErrorResponse(APIResponse):
    """Error response schema."""

    error_code: str = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")


class PaginatedResponse(APIResponse):
    """Paginated response schema."""

    data: List[Any] = Field(..., description="Response data")
    pagination: Dict[str, Any] = Field(..., description="Pagination information")


# Real-time Data Models
class WindFarmRealTimeData(BaseSchema):
    """Wind farm real-time data."""

    wind_farm_id: str = Field(..., description="Wind farm ID")
    total_power: float = Field(..., description="Total power output in MW")
    wind_speed: float = Field(..., description="Average wind speed in m/s")
    running_turbines: int = Field(..., description="Number of running turbines")
    availability: float = Field(..., description="Availability percentage")
    timestamp: datetime = Field(..., description="Data timestamp")


class WindFarmStatistics(BaseSchema):
    """Wind farm statistics."""

    wind_farm_id: str = Field(..., description="Wind farm ID")
    total_turbines: int = Field(..., description="Total number of turbines")
    running_turbines: int = Field(..., description="Number of running turbines")
    total_capacity: float = Field(..., description="Total capacity in MW")
    current_power: float = Field(..., description="Current power output in MW")
    availability_rate: float = Field(..., description="Availability rate percentage")
    capacity_factor: float = Field(..., description="Capacity factor percentage")
    energy_today: float = Field(..., description="Energy generated today in MWh")
    energy_this_month: float = Field(..., description="Energy generated this month in MWh")
    energy_this_year: float = Field(..., description="Energy generated this year in MWh")


# Health Check Models
class HealthStatus(BaseSchema):
    """Health status schema."""

    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Check timestamp")
    services: Dict[str, Any] = Field(..., description="Service health details")


# Configuration
class Config:
    """Configuration for all models."""
    orm_mode = True
    validate_assignment = True
    use_enum_values = True
    allow_population_by_field_name = True


# Apply configuration to all models
for model in [
    BaseSchema,
    WindFarmBase,
    WindFarmCreate,
    WindFarmUpdate,
    WindFarmResponse,
    TurbineBase,
    TurbineCreate,
    TurbineUpdate,
    TurbineResponse,
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    UserLoginResponse,
    WindFarmAccess,
    WindFarmAccessResponse,
    WindFarmRealTimeData,
    WindFarmStatistics,
    PaginatedResponse,
    PaginationParams,
    WindFarmFilter,
    WindTurbineFilter,
    UserFilter,
    APIResponse,
    SuccessResponse,
    ErrorResponse,
    HealthStatus,
]:
    model.Config = Config()