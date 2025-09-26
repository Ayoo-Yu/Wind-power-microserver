"""
Data models for SCADA Data Service.
"""

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum


class ScadaProtocol(str, Enum):
    """SCADA protocol types."""

    IEC104 = "iec104"
    MODBUS_TCP = "modbus_tcp"
    DNP3 = "dnp3"
    OPC_UA = "opc_ua"


class DataPointType(str, Enum):
    """SCADA data point types."""

    # IEC 60870-5-104 data types
    SINGLE_POINT = "single_point"          # M_SP_NA_1
    DOUBLE_POINT = "double_point"          # M_DP_NA_1
    MEASURED_VALUE = "measured_value"      # M_ME_NA_1
    NORMALIZED_VALUE = "normalized_value"  # M_ME_NC_1
    SCALED_VALUE = "scaled_value"          # M_ME_NB_1
    FLOATING_POINT = "floating_point"      # M_ME_NC_1
    INTEGRATED_TOTALS = "integrated_totals" # M_IT_NA_1
    PROTECTION_EVENT = "protection_event"   # M_EP_TA_1


class ConnectionStatus(str, Enum):
    """SCADA connection status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class TurbineStatus(str, Enum):
    """Wind turbine operational status."""

    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"
    MAINTENANCE = "maintenance"
    FAULT = "fault"
    GRID_DISCONNECTED = "grid_disconnected"
    EMERGENCY_STOP = "emergency_stop"
    MANUAL_MODE = "manual_mode"
    AUTO_MODE = "auto_mode"


class AlarmSeverity(str, Enum):
    """Alarm severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlarmStatus(str, Enum):
    """Alarm status."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    CLEARED = "cleared"
    DISABLED = "disabled"


# Base Models
class BaseSchema(BaseModel):
    """Base schema for all data models."""

    class Config:
        orm_mode = True
        validate_assignment = True
        use_enum_values = True


# Wind Farm and Turbine Reference Models
class WindFarmRef(BaseSchema):
    """Wind farm reference."""

    id: str = Field(..., description="Wind farm ID")
    code: str = Field(..., description="Wind farm code")
    name: str = Field(..., description="Wind farm name")
    location: Optional[str] = Field(None, description="Location")


class TurbineRef(BaseSchema):
    """Wind turbine reference."""

    id: str = Field(..., description="Turbine ID")
    turbine_id: str = Field(..., description="Turbine identifier")
    wind_farm_id: str = Field(..., description="Parent wind farm ID")
    manufacturer: str = Field(..., description="Manufacturer")
    model: str = Field(..., description="Model")
    rated_power: float = Field(..., description="Rated power in MW")


# SCADA Connection Models
class ScadaConnectionBase(BaseSchema):
    """Base SCADA connection schema."""

    name: str = Field(..., min_length=1, max_length=100, description="Connection name")
    description: Optional[str] = Field(None, max_length=500, description="Description")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    protocol: ScadaProtocol = Field(ScadaProtocol.IEC104, description="SCADA protocol")
    host: str = Field(..., description="SCADA server host/IP")
    port: int = Field(..., ge=1, le=65535, description="SCADA server port")
    connection_timeout: int = Field(30, ge=5, le=300, description="Connection timeout in seconds")
    is_active: bool = Field(True, description="Is connection active")
    max_reconnect_attempts: int = Field(5, ge=1, le=20, description="Max reconnection attempts")
    reconnect_delay: int = Field(10, ge=1, le=300, description="Reconnection delay in seconds")

    @validator('host')
    def validate_host(cls, v):
        """Validate host format."""
        if not v or len(v) < 1:
            raise ValueError('Host cannot be empty')
        return v.strip()


class ScadaConnectionCreate(ScadaConnectionBase):
    """SCADA connection creation schema."""
    pass


class ScadaConnectionUpdate(BaseSchema):
    """SCADA connection update schema."""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Connection name")
    description: Optional[str] = Field(None, max_length=500, description="Description")
    protocol: Optional[ScadaProtocol] = Field(None, description="SCADA protocol")
    host: Optional[str] = Field(None, description="SCADA server host/IP")
    port: Optional[int] = Field(None, ge=1, le=65535, description="SCADA server port")
    connection_timeout: Optional[int] = Field(None, ge=5, le=300, description="Connection timeout")
    is_active: Optional[bool] = Field(None, description="Is connection active")
    max_reconnect_attempts: Optional[int] = Field(None, ge=1, le=20, description="Max reconnection attempts")
    reconnect_delay: Optional[int] = Field(None, ge=1, le=300, description="Reconnection delay")


class ScadaConnectionResponse(ScadaConnectionBase):
    """SCADA connection response schema."""

    id: str = Field(..., description="Connection ID")
    status: ConnectionStatus = Field(..., description="Current connection status")
    last_connected_at: Optional[datetime] = Field(None, description="Last successful connection time")
    connection_count: int = Field(0, description="Total connection attempts")
    error_count: int = Field(0, description="Connection error count")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    wind_farm: Optional[WindFarmRef] = Field(None, description="Wind farm details")


# Data Point Models
class DataPointBase(BaseSchema):
    """Base SCADA data point schema."""

    point_name: str = Field(..., min_length=1, max_length=100, description="Data point name")
    point_address: str = Field(..., description="SCADA address (IOA for IEC104)")
    point_type: DataPointType = Field(..., description="Data point type")
    description: Optional[str] = Field(None, max_length=500, description="Point description")
    unit: Optional[str] = Field(None, max_length=20, description="Measurement unit")
    scale_factor: float = Field(1.0, description="Scale factor for raw values")
    offset: float = Field(0.0, description="Offset for raw values")
    min_value: Optional[float] = Field(None, description="Minimum expected value")
    max_value: Optional[float] = Field(None, description="Maximum expected value")
    is_alarmpoint: bool = Field(False, description="Is this an alarm point")
    alarm_threshold_high: Optional[float] = Field(None, description="High alarm threshold")
    alarm_threshold_low: Optional[float] = Field(None, description="Low alarm threshold")
    is_active: bool = Field(True, description="Is data point active")


class DataPointCreate(DataPointBase):
    """Data point creation schema."""

    connection_id: str = Field(..., description="SCADA connection ID")
    turbine_id: Optional[str] = Field(None, description="Turbine ID if turbine-specific")


class DataPointUpdate(BaseSchema):
    """Data point update schema."""

    point_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Data point name")
    description: Optional[str] = Field(None, max_length=500, description="Point description")
    scale_factor: Optional[float] = Field(None, description="Scale factor")
    offset: Optional[float] = Field(None, description="Offset")
    min_value: Optional[float] = Field(None, description="Minimum expected value")
    max_value: Optional[float] = Field(None, description="Maximum expected value")
    is_alarmpoint: Optional[bool] = Field(None, description="Is this an alarm point")
    alarm_threshold_high: Optional[float] = Field(None, description="High alarm threshold")
    alarm_threshold_low: Optional[float] = Field(None, description="Low alarm threshold")
    is_active: Optional[bool] = Field(None, description="Is data point active")


class DataPointResponse(DataPointBase):
    """Data point response schema."""

    id: str = Field(..., description="Data point ID")
    connection_id: str = Field(..., description="SCADA connection ID")
    turbine_id: Optional[str] = Field(None, description="Turbine ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    connection: Optional[ScadaConnectionRef] = Field(None, description="Connection details")
    turbine: Optional[TurbineRef] = Field(None, description="Turbine details")


# Real-time Data Models
class ScadaDataPoint(BaseSchema):
    """SCADA real-time data point."""

    point_id: str = Field(..., description="Data point ID")
    point_name: str = Field(..., description="Point name")
    value: Union[float, int, bool, str] = Field(..., description="Data value")
    raw_value: Optional[Union[float, int, bool, str]] = Field(None, description="Raw value before scaling")
    quality: str = Field("good", description="Data quality (good|bad|uncertain|overflow)")
    timestamp: datetime = Field(..., description="Data timestamp")
    is_alarm: bool = Field(False, description="Is this an alarm state")
    connection_id: str = Field(..., description="Connection ID")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    turbine_id: Optional[str] = Field(None, description="Turbine ID if applicable")


class ScadaDataBatch(BaseSchema):
    """Batch of SCADA data points."""

    connection_id: str = Field(..., description="SCADA connection ID")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    data_points: List[ScadaDataPoint] = Field(..., description="Data points")
    batch_timestamp: datetime = Field(..., description="Batch timestamp")
    total_points: int = Field(..., description="Total number of data points")


# Turbine Status Models
class TurbineStatusData(BaseSchema):
    """Turbine status and operational data."""

    turbine_id: str = Field(..., description="Turbine ID")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    status: TurbineStatus = Field(..., description="Turbine operational status")
    power_output: float = Field(..., description="Current power output (MW)")
    wind_speed: float = Field(..., description="Wind speed (m/s)")
    rotor_speed: float = Field(..., description="Rotor speed (RPM)")
    nacelle_direction: float = Field(..., description="Nacelle direction (degrees)")
    availability: float = Field(..., description="Availability percentage")
    temperature: Optional[float] = Field(None, description="Nacelle temperature (°C)")
    vibration_level: Optional[float] = Field(None, description="Vibration level")
    grid_frequency: Optional[float] = Field(None, description="Grid frequency (Hz)")
    grid_voltage: Optional[float] = Field(None, description="Grid voltage (V)")
    timestamp: datetime = Field(..., description="Data timestamp")


# Alarm Models
class AlarmBase(BaseSchema):
    """Base alarm schema."""

    alarm_code: str = Field(..., description="Alarm code")
    alarm_name: str = Field(..., description="Alarm name")
    description: str = Field(..., description="Alarm description")
    severity: AlarmSeverity = Field(..., description="Alarm severity")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    turbine_id: Optional[str] = Field(None, description="Turbine ID if applicable")
    point_id: Optional[str] = Field(None, description="Data point ID if applicable")
    threshold_value: Optional[float] = Field(None, description="Threshold value")
    actual_value: Optional[float] = Field(None, description="Actual value")
    unit: Optional[str] = Field(None, description="Unit of measurement")


class AlarmCreate(AlarmBase):
    """Alarm creation schema."""

    triggered_at: datetime = Field(..., description="Alarm trigger time")


class AlarmResponse(AlarmBase):
    """Alarm response schema."""

    id: str = Field(..., description="Alarm ID")
    status: AlarmStatus = Field(..., description="Alarm status")
    triggered_at: datetime = Field(..., description="Alarm trigger time")
    acknowledged_at: Optional[datetime] = Field(None, description="Acknowledgment time")
    cleared_at: Optional[datetime] = Field(None, description="Clear time")
    acknowledged_by: Optional[str] = Field(None, description="User who acknowledged")
    created_at: datetime = Field(..., description="Creation timestamp")


# Connection Statistics Models
class ConnectionStatistics(BaseSchema):
    """SCADA connection statistics."""

    connection_id: str = Field(..., description="Connection ID")
    total_data_points: int = Field(..., description="Total data points received")
    valid_data_points: int = Field(..., description="Valid data points")
    invalid_data_points: int = Field(..., description="Invalid data points")
    alarm_count: int = Field(..., description="Total alarms")
    critical_alarm_count: int = Field(..., description="Critical alarms")
    connection_uptime: float = Field(..., description="Connection uptime percentage")
    last_data_received_at: Optional[datetime] = Field(None, description="Last data received time")
    statistics_period: str = Field(..., description="Statistics period (hour|day|week|month)")
    period_start: datetime = Field(..., description="Period start time")
    period_end: datetime = Field(..., description="Period end time")


# Event Models
class ScadaEvent(BaseSchema):
    """SCADA system event."""

    event_type: str = Field(..., description="Event type")
    event_name: str = Field(..., description="Event name")
    description: str = Field(..., description="Event description")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    connection_id: Optional[str] = Field(None, description="Connection ID")
    turbine_id: Optional[str] = Field(None, description="Turbine ID")
    severity: AlarmSeverity = Field(..., description="Event severity")
    event_data: Optional[Dict[str, Any]] = Field(None, description="Additional event data")
    timestamp: datetime = Field(..., description="Event timestamp")


# Filter and Pagination Models
class ConnectionFilter(BaseSchema):
    """SCADA connection filter parameters."""

    wind_farm_id: Optional[str] = Field(None, description="Filter by wind farm ID")
    protocol: Optional[ScadaProtocol] = Field(None, description="Filter by protocol")
    status: Optional[ConnectionStatus] = Field(None, description="Filter by status")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    host: Optional[str] = Field(None, description="Filter by host")


class DataPointFilter(BaseSchema):
    """Data point filter parameters."""

    connection_id: Optional[str] = Field(None, description="Filter by connection ID")
    turbine_id: Optional[str] = Field(None, description="Filter by turbine ID")
    point_type: Optional[DataPointType] = Field(None, description="Filter by point type")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    is_alarmpoint: Optional[bool] = Field(None, description="Filter by alarm point status")


class ScadaDataFilter(BaseSchema):
    """SCADA data filter parameters."""

    connection_id: Optional[str] = Field(None, description="Filter by connection ID")
    wind_farm_id: Optional[str] = Field(None, description="Filter by wind farm ID")
    turbine_id: Optional[str] = Field(None, description="Filter by turbine ID")
    point_type: Optional[DataPointType] = Field(None, description="Filter by point type")
    quality: Optional[str] = Field(None, description="Filter by data quality")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")


class AlarmFilter(BaseSchema):
    """Alarm filter parameters."""

    wind_farm_id: Optional[str] = Field(None, description="Filter by wind farm ID")
    turbine_id: Optional[str] = Field(None, description="Filter by turbine ID")
    severity: Optional[AlarmSeverity] = Field(None, description="Filter by severity")
    status: Optional[AlarmStatus] = Field(None, description="Filter by status")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")


class PaginationParams(BaseSchema):
    """Pagination parameters."""

    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=1000, description="Page size")


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


# Real-time Monitoring Models
class RealtimeDataStream(BaseSchema):
    """Real-time data stream."""

    connection_id: str = Field(..., description="Connection ID")
    wind_farm_id: str = Field(..., description="Wind farm ID")
    data_type: str = Field(..., description="Data type (telemetry|status|alarm)")
    data_points: List[ScadaDataPoint] = Field(..., description="Data points")
    stream_timestamp: datetime = Field(..., description="Stream timestamp")
    processing_latency_ms: float = Field(..., description="Processing latency in milliseconds")


class SystemStatus(BaseSchema):
    """System status overview."""

    total_connections: int = Field(..., description="Total SCADA connections")
    active_connections: int = Field(..., description="Active connections")
    total_turbines: int = Field(..., description="Total turbines monitored")
    running_turbines: int = Field(..., description="Running turbines")
    total_data_points: int = Field(..., description="Total data points configured")
    active_alarms: int = Field(..., description="Active alarms")
    data_throughput_per_second: float = Field(..., description="Data throughput per second")
    average_processing_latency_ms: float = Field(..., description="Average processing latency")
    last_updated: datetime = Field(..., description="Last status update")


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
    WindFarmRef,
    TurbineRef,
    ScadaConnectionBase,
    ScadaConnectionCreate,
    ScadaConnectionUpdate,
    ScadaConnectionResponse,
    DataPointBase,
    DataPointCreate,
    DataPointUpdate,
    DataPointResponse,
    ScadaDataPoint,
    ScadaDataBatch,
    TurbineStatusData,
    AlarmBase,
    AlarmCreate,
    AlarmResponse,
    ConnectionStatistics,
    ScadaEvent,
    ConnectionFilter,
    DataPointFilter,
    ScadaDataFilter,
    AlarmFilter,
    PaginationParams,
    APIResponse,
    SuccessResponse,
    ErrorResponse,
    PaginatedResponse,
    RealtimeDataStream,
    SystemStatus,
]:
    model.Config = Config()