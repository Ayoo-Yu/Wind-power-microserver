"""
Data models for Report Service
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, JSON, ForeignKey, Text, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class ReportStatus(str, Enum):
    """Report status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ReportFormat(str, Enum):
    """Report format enumeration."""
    PDF = "pdf"
    EXCEL = "excel"
    HTML = "html"
    CSV = "csv"
    PNG = "png"
    JSON = "json"


class ReportType(str, Enum):
    """Report type enumeration."""
    DAILY_POWER_GENERATION = "daily_power_generation"
    WEEKLY_PERFORMANCE = "weekly_performance"
    MONTHLY_MAINTENANCE = "monthly_maintenance"
    WEATHER_FORECAST_ACCURACY = "weather_forecast_accuracy"
    FINANCIAL_PERFORMANCE = "financial_performance"
    ENVIRONMENTAL_IMPACT = "environmental_impact"
    OPERATIONAL_DASHBOARD = "operational_dashboard"
    COMPLIANCE_REPORT = "compliance_report"
    CUSTOM_REPORT = "custom_report"


class ChartType(str, Enum):
    """Chart type enumeration."""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    AREA = "area"
    BOX = "box"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    STATUS_GRID = "status_grid"
    GANTT = "gantt"


class ReportScheduleType(str, Enum):
    """Report schedule type enumeration."""
    ONE_TIME = "one_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class ReportScheduleStatus(str, Enum):
    """Report schedule status enumeration."""
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"
    DISABLED = "disabled"


# Database Models
class Report(Base):
    """Report database model."""
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    report_type = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    wind_farm_id = Column(String, ForeignKey("wind_farms.id"), nullable=True, index=True)
    turbine_ids = Column(JSON, nullable=True)  # List of turbine IDs

    # Report configuration
    parameters = Column(JSON, nullable=True)  # Report-specific parameters
    filters = Column(JSON, nullable=True)  # Data filters
    time_range = Column(JSON, nullable=True)  # Time range configuration

    # Report content
    template_id = Column(String, ForeignKey("report_templates.id"), nullable=True)
    charts_config = Column(JSON, nullable=True)  # Chart configurations
    data_sources = Column(JSON, nullable=True)  # Data source configuration

    # Output configuration
    formats = Column(JSON, nullable=False)  # List of output formats
    output_path = Column(String, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    # Status and scheduling
    status = Column(String, nullable=False, default=ReportStatus.PENDING, index=True)
    schedule_id = Column(String, ForeignKey("report_schedules.id"), nullable=True, index=True)

    # Generation metadata
    generated_by = Column(String, nullable=True)
    generation_start_time = Column(DateTime, nullable=True)
    generation_end_time = Column(DateTime, nullable=True)
    generation_duration_seconds = Column(Integer, nullable=True)

    # Quality metrics
    data_quality_score = Column(Float, nullable=True)
    completeness_percentage = Column(Float, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    template = relationship("ReportTemplate", back_populates="reports")
    schedule = relationship("ReportSchedule", back_populates="reports")


class ReportTemplate(Base):
    """Report template database model."""
    __tablename__ = "report_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    report_type = Column(String, nullable=False, index=True)

    # Template configuration
    template_content = Column(Text, nullable=False)  # Jinja2 template
    template_format = Column(String, nullable=False, default="html")  # html, markdown

    # Default parameters
    default_parameters = Column(JSON, nullable=True)
    default_charts = Column(JSON, nullable=True)
    default_data_sources = Column(JSON, nullable=True)

    # Styling
    css_styles = Column(Text, nullable=True)
    header_template = Column(Text, nullable=True)
    footer_template = Column(Text, nullable=True)

    # Versioning
    version = Column(String, nullable=False, default="1.0.0")
    is_active = Column(Boolean, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String, nullable=True)

    # Relationships
    reports = relationship("Report", back_populates="template")


class ReportSchedule(Base):
    """Report schedule database model."""
    __tablename__ = "report_schedules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Schedule configuration
    schedule_type = Column(String, nullable=False, index=True)
    cron_expression = Column(String, nullable=True)
    interval_minutes = Column(Integer, nullable=True)

    # Report configuration
    report_type = Column(String, nullable=False, index=True)
    wind_farm_id = Column(String, ForeignKey("wind_farms.id"), nullable=True, index=True)
    turbine_ids = Column(JSON, nullable=True)
    parameters = Column(JSON, nullable=True)
    formats = Column(JSON, nullable=False)

    # Recipients
    email_recipients = Column(JSON, nullable=True)
    webhook_urls = Column(JSON, nullable=True)

    # Status
    status = Column(String, nullable=False, default=ReportScheduleStatus.ACTIVE, index=True)
    last_run_time = Column(DateTime, nullable=True)
    next_run_time = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String, nullable=True)

    # Relationships
    reports = relationship("Report", back_populates="schedule")


class Chart(Base):
    """Chart database model."""
    __tablename__ = "charts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    chart_type = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Chart configuration
    config = Column(JSON, nullable=False)  # Chart-specific configuration
    data_query = Column(Text, nullable=True)  # Data query or configuration

    # Styling
    width = Column(Integer, default=800)
    height = Column(Integer, default=600)
    dpi = Column(Integer, default=150)
    color_scheme = Column(String, nullable=True)

    # Output
    image_path = Column(String, nullable=True)
    image_data = Column(LargeBinary, nullable=True)  # Store chart image

    # Relationships
    report_id = Column(String, ForeignKey("reports.id"), nullable=True, index=True)
    report = relationship("Report")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ReportData(Base):
    """Report data cache database model."""
    __tablename__ = "report_data"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String, ForeignKey("reports.id"), nullable=False, index=True)

    # Data identification
    data_source = Column(String, nullable=False, index=True)
    query_hash = Column(String, nullable=False, index=True)  # Hash of query parameters

    # Data content
    data = Column(JSON, nullable=False)  # Cached data
    metadata = Column(JSON, nullable=True)  # Data metadata (count, quality, etc.)

    # Cache metadata
    cache_ttl_seconds = Column(Integer, default=3600)
    expires_at = Column(DateTime, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    accessed_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ReportDelivery(Base):
    """Report delivery tracking database model."""
    __tablename__ = "report_deliveries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String, ForeignKey("reports.id"), nullable=False, index=True)

    # Delivery information
    delivery_method = Column(String, nullable=False)  # email, webhook, download
    recipient = Column(String, nullable=False)

    # Status
    status = Column(String, nullable=False, default="pending", index=True)
    delivery_time = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# Reference tables (would be imported from other services)
class WindFarm(Base):
    """Wind farm reference model."""
    __tablename__ = "wind_farms"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    capacity_mw = Column(Float, nullable=True)
    number_of_turbines = Column(Integer, nullable=True)
    commission_date = Column(DateTime, nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Pydantic Models for API
class ReportCreate(BaseModel):
    """Report create model."""
    name: str
    report_type: str
    description: Optional[str] = None
    wind_farm_id: Optional[str] = None
    turbine_ids: Optional[List[str]] = None

    parameters: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None
    time_range: Optional[Dict[str, Any]] = None

    template_id: Optional[str] = None
    charts_config: Optional[List[Dict[str, Any]]] = None
    data_sources: Optional[List[str]] = None

    formats: List[str]
    schedule_id: Optional[str] = None

    @validator('formats')
    def validate_formats(cls, v):
        valid_formats = ["pdf", "excel", "html", "csv", "png", "json"]
        for format in v:
            if format not in valid_formats:
                raise ValueError(f"Invalid report format: {format}")
        return v


class ReportResponse(BaseModel):
    """Report response model."""
    id: str
    name: str
    report_type: str
    description: Optional[str]
    wind_farm_id: Optional[str]
    turbine_ids: Optional[List[str]]

    parameters: Optional[Dict[str, Any]]
    filters: Optional[Dict[str, Any]]
    time_range: Optional[Dict[str, Any]]

    template_id: Optional[str]
    charts_config: Optional[List[Dict[str, Any]]]
    data_sources: Optional[List[str]]

    formats: List[str]
    output_path: Optional[str]
    file_size_bytes: Optional[int]

    status: str
    schedule_id: Optional[str]
    generated_by: Optional[str]
    generation_start_time: Optional[datetime]
    generation_end_time: Optional[datetime]
    generation_duration_seconds: Optional[int]

    data_quality_score: Optional[float]
    completeness_percentage: Optional[float]
    error_message: Optional[str]

    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]

    class Config:
        orm_mode = True


class ReportTemplateCreate(BaseModel):
    """Report template create model."""
    name: str
    description: Optional[str] = None
    report_type: str
    template_content: str
    template_format: str = "html"

    default_parameters: Optional[Dict[str, Any]] = None
    default_charts: Optional[List[Dict[str, Any]]] = None
    default_data_sources: Optional[List[str]] = None

    css_styles: Optional[str] = None
    header_template: Optional[str] = None
    footer_template: Optional[str] = None
    version: str = "1.0.0"


class ReportTemplateResponse(BaseModel):
    """Report template response model."""
    id: str
    name: str
    description: Optional[str]
    report_type: str
    template_content: str
    template_format: str

    default_parameters: Optional[Dict[str, Any]]
    default_charts: Optional[List[Dict[str, Any]]]
    default_data_sources: Optional[List[str]]

    css_styles: Optional[str]
    header_template: Optional[str]
    footer_template: Optional[str]

    version: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        orm_mode = True


class ReportScheduleCreate(BaseModel):
    """Report schedule create model."""
    name: str
    description: Optional[str] = None

    schedule_type: str
    cron_expression: Optional[str] = None
    interval_minutes: Optional[int] = None

    report_type: str
    wind_farm_id: Optional[str] = None
    turbine_ids: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = None
    formats: List[str]

    email_recipients: Optional[List[str]] = None
    webhook_urls: Optional[List[str]] = None


class ReportScheduleResponse(BaseModel):
    """Report schedule response model."""
    id: str
    name: str
    description: Optional[str]

    schedule_type: str
    cron_expression: Optional[str]
    interval_minutes: Optional[int]

    report_type: str
    wind_farm_id: Optional[str]
    turbine_ids: Optional[List[str]]
    parameters: Optional[Dict[str, Any]]
    formats: List[str]

    email_recipients: Optional[List[str]]
    webhook_urls: Optional[List[str]]

    status: str
    last_run_time: Optional[datetime]
    next_run_time: Optional[datetime]
    run_count: int

    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        orm_mode = True


class ChartCreate(BaseModel):
    """Chart create model."""
    name: str
    chart_type: str
    description: Optional[str] = None
    config: Dict[str, Any]
    data_query: Optional[str] = None

    width: int = 800
    height: int = 600
    dpi: int = 150
    color_scheme: Optional[str] = None


class ChartResponse(BaseModel):
    """Chart response model."""
    id: str
    name: str
    chart_type: str
    description: Optional[str]
    config: Dict[str, Any]
    data_query: Optional[str]

    width: int
    height: int
    dpi: int
    color_scheme: Optional[str]

    image_path: Optional[str]
    report_id: Optional[str]

    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ReportGenerationRequest(BaseModel):
    """Report generation request model."""
    report_type: str
    wind_farm_id: Optional[str] = None
    turbine_ids: Optional[List[str]] = None

    parameters: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None
    time_range: Optional[Dict[str, Any]] = None

    formats: List[str] = ["pdf"]
    charts: Optional[List[str]] = None
    template_id: Optional[str] = None

    generate_charts: bool = True
    include_raw_data: bool = False

    @validator('formats')
    def validate_formats(cls, v):
        valid_formats = ["pdf", "excel", "html", "csv", "png", "json"]
        for format in v:
            if format not in valid_formats:
                raise ValueError(f"Invalid report format: {format}")
        return v


class ReportDataRequest(BaseModel):
    """Report data request model."""
    report_type: str
    wind_farm_id: Optional[str] = None
    turbine_ids: Optional[List[str]] = None

    parameters: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None
    time_range: Optional[Dict[str, Any]] = None

    data_sources: Optional[List[str]] = None
    aggregation_level: str = "hourly"


class SuccessResponse(BaseModel):
    """Success response model."""
    success: bool = True
    message: str
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class PaginationParams(BaseModel):
    """Pagination parameters model."""
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=200, description="Page size")


class ReportFilter(BaseModel):
    """Report filter model."""
    report_type: Optional[str] = None
    wind_farm_id: Optional[str] = None
    status: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    generated_by: Optional[str] = None


class DashboardConfig(BaseModel):
    """Dashboard configuration model."""
    name: str
    description: Optional[str] = None
    wind_farm_id: Optional[str] = None

    widgets: List[Dict[str, Any]]
    layout: Dict[str, Any]
    refresh_interval_seconds: int = 300

    is_public: bool = False
    is_default: bool = False


class DataExportRequest(BaseModel):
    """Data export request model."""
    report_id: str
    format: str = "csv"
    include_metadata: bool = True
    compression: bool = False


class ReportShareRequest(BaseModel):
    """Report share request model."""
    report_id: str
    recipient_emails: List[str]
    message: Optional[str] = None
    expiry_hours: int = 168  # 7 days
    permissions: List[str] = ["read"]  # read, download, share