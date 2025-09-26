"""
Data models for Tenant Management Service.
"""

from pydantic import BaseModel, Field, validator, EmailStr
from datetime import datetime
from typing import Optional, List
from enum import Enum


class UserRole(str, Enum):
    """User roles in the system."""

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


# User Models
class UserBase(BaseSchema):
    """Base user model."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole = UserRole.VIEWER

    @validator("username")
    def validate_username(cls, v):
        if not v.isalnum() and "_" not in v:
            raise ValueError("Username must contain only alphanumeric characters and underscores")
        return v.lower()

    @validator("full_name")
    def validate_full_name(cls, v):
        if len(v.strip()) == 0:
            raise ValueError("Full name cannot be empty")
        return v.strip()


class UserCreate(UserBase):
    """User creation model."""

    password: str = Field(..., min_length=8, max_length=100)
    tenant_id: str

    @validator("password")
    def validate_password(cls, v):
        from .utils import validate_password_strength
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v


class UserUpdate(BaseSchema):
    """User update model."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

    @validator("full_name")
    def validate_full_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Full name cannot be empty")
        return v.strip() if v else None


class UserResponse(UserBase):
    """User response model."""

    id: str
    tenant_id: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime


class UserLogin(BaseSchema):
    """User login model."""

    username: str
    password: str


class PasswordChange(BaseSchema):
    """Password change model."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @validator("new_password")
    def validate_new_password(cls, v):
        from .utils import validate_password_strength
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v


# Tenant Models
class TenantBase(BaseSchema):
    """Base tenant model."""

    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = Field(None, max_length=500)
    location: str = Field(..., min_length=1, max_length=200)
    total_capacity: float = Field(..., gt=0)
    turbine_count: int = Field(..., gt=0)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=300)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    @validator("code")
    def validate_code(cls, v):
        if not v.isalnum() and "_" not in v:
            raise ValueError("Tenant code must contain only alphanumeric characters and underscores")
        return v.upper()

    @validator("contact_phone")
    def validate_contact_phone(cls, v):
        if v and not v.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            raise ValueError("Contact phone must contain only digits, plus signs, hyphens, and spaces")
        return v


class TenantCreate(TenantBase):
    """Tenant creation model."""

    commissioning_date: Optional[datetime] = None


class TenantUpdate(BaseSchema):
    """Tenant update model."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, min_length=1, max_length=200)
    total_capacity: Optional[float] = Field(None, gt=0)
    turbine_count: Optional[int] = Field(None, gt=0)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=300)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    is_active: Optional[bool] = None

    @validator("contact_phone")
    def validate_contact_phone(cls, v):
        if v and not v.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            raise ValueError("Contact phone must contain only digits, plus signs, hyphens, and spaces")
        return v


class TenantResponse(TenantBase):
    """Tenant response model."""

    id: str
    commissioning_date: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Authentication Models
class TokenResponse(BaseSchema):
    """Token response model."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    tenant_id: str
    role: str


class RefreshTokenRequest(BaseSchema):
    """Refresh token request model."""

    refresh_token: str


# Audit Log Models
class AuditLogResponse(BaseSchema):
    """Audit log response model."""

    id: str
    user_id: str
    tenant_id: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime


# Pagination Models
class PaginatedResponse(BaseSchema):
    """Paginated response model."""

    items: List[Any]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


class PaginationParams(BaseSchema):
    """Pagination parameters."""

    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


# Search and Filter Models
class UserFilter(BaseSchema):
    """User filter parameters."""

    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    tenant_id: Optional[str] = None


class TenantFilter(BaseSchema):
    """Tenant filter parameters."""

    name: Optional[str] = None
    code: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None


# Response Models
class APIResponse(BaseSchema):
    """Standard API response wrapper."""

    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseSchema):
    """Error response model."""

    success: bool = False
    message: str
    error_code: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Health Check Models
class HealthStatus(BaseSchema):
    """Health status model."""

    status: str
    service: str
    timestamp: datetime
    version: str
    dependencies: Optional[Dict[str, str]] = None


# Configuration Models
class ServiceConfig(BaseSchema):
    """Service configuration model."""

    service_name: str
    version: str
    environment: str
    features: Dict[str, bool]
    limits: Dict[str, int]


# Import Any type for generic models
from typing import Any


# Example usage models
class ExampleUser:
    """Example user data for documentation."""

    EXAMPLE_USER_RESPONSE = UserResponse(
        id="123e4567-e89b-12d3-a456-426614174000",
        username="john_doe",
        email="john.doe@example.com",
        full_name="John Doe",
        role=UserRole.OPERATOR,
        tenant_id="123e4567-e89b-12d3-a456-426614174001",
        is_active=True,
        is_superuser=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    EXAMPLE_TENANT_RESPONSE = TenantResponse(
        id="123e4567-e89b-12d3-a456-426614174001",
        name="Wind Farm Alpha",
        code="WF_ALPHA",
        description="Main wind farm facility",
        location="Texas, USA",
        total_capacity=150.5,
        turbine_count=50,
        contact_email="contact@winalpha.com",
        contact_phone="+1-555-0123",
        address="123 Wind Farm Road, Texas, USA",
        latitude=32.7767,
        longitude=-96.7970,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


# Model configurations
class Config:
    """Configuration for Pydantic models."""

    # Use enum values in serialization
    use_enum_values = True

    # Validate assignment
    validate_assignment = True

    # Allow population by field name
    allow_population_by_field_name = True

    # Use ORM mode
    orm_mode = True


# Set config for all models
for model in [
    BaseSchema,
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    PasswordChange,
    TenantBase,
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TokenResponse,
    RefreshTokenRequest,
    AuditLogResponse,
    PaginatedResponse,
    PaginationParams,
    UserFilter,
    TenantFilter,
    APIResponse,
    ErrorResponse,
    HealthStatus,
    ServiceConfig,
]:
    model.Config = Config()