"""
Data models for API Gateway.
"""

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class ProxyRequest(BaseModel):
    """Request model for proxy service."""

    method: str = Field(..., description="HTTP method")
    url: str = Field(..., description="Request URL")
    headers: Dict[str, str] = Field(default_factory=dict, description="Request headers")
    body: Optional[bytes] = Field(None, description="Request body")
    request_id: str = Field(..., description="Unique request ID for tracing")

    @validator("method")
    def validate_method(cls, v):
        valid_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        if v.upper() not in valid_methods:
            raise ValueError(f"Method must be one of {valid_methods}")
        return v.upper()


class ProxyResponse(BaseModel):
    """Response model for proxy service."""

    status_code: int = Field(..., description="HTTP status code")
    body: Optional[Any] = Field(None, description="Response body")
    headers: Dict[str, str] = Field(default_factory=dict, description="Response headers")
    error: Optional[str] = Field(None, description="Error message if request failed")

    @validator("status_code")
    def validate_status_code(cls, v):
        if not 100 <= v <= 599:
            raise ValueError("Status code must be between 100 and 599")
        return v


class GatewayResponse(BaseModel):
    """Standard gateway response model."""

    success: bool = Field(..., description="Request success status")
    message: str = Field(..., description="Response message")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional[Dict[str, Any]] = Field(None, description="Error details if request failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")


class ServiceStatus(str, Enum):
    """Service health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CircuitBreakerStatus(str, Enum):
    """Circuit breaker status."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ServiceInstanceStatus(BaseModel):
    """Service instance status model."""

    url: str = Field(..., description="Service instance URL")
    is_healthy: bool = Field(..., description="Health status")
    last_health_check: datetime = Field(..., description="Last health check timestamp")
    failure_count: int = Field(0, description="Number of consecutive failures")
    success_count: int = Field(0, description="Number of successful requests")
    response_time: float = Field(0.0, description="Average response time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ServiceHealthStatus(BaseModel):
    """Service health status model."""

    service_name: str = Field(..., description="Service name")
    total_instances: int = Field(..., description="Total number of instances")
    healthy_instances: int = Field(..., description="Number of healthy instances")
    unhealthy_instances: int = Field(..., description="Number of unhealthy instances")
    health_percentage: float = Field(..., description="Health percentage (0-100)")
    instances: List[ServiceInstanceStatus] = Field(..., description="Instance details")
    last_updated: datetime = Field(..., description="Last update timestamp")


class CircuitBreakerStats(BaseModel):
    """Circuit breaker statistics model."""

    service_name: str = Field(..., description="Service name")
    state: CircuitBreakerStatus = Field(..., description="Circuit breaker state")
    failure_count: int = Field(0, description="Number of failures")
    success_count: int = Field(0, description="Number of successes")
    half_open_calls: int = Field(0, description="Number of calls in half-open state")
    last_failure_time: Optional[datetime] = Field(None, description="Last failure timestamp")
    last_state_change: datetime = Field(..., description="Last state change timestamp")
    failure_threshold: int = Field(..., description="Failure threshold")
    recovery_timeout: int = Field(..., description="Recovery timeout in seconds")
    success_threshold: int = Field(..., description="Success threshold for closing")


class LoadBalancerStats(BaseModel):
    """Load balancer statistics model."""

    service_name: str = Field(..., description="Service name")
    total_instances: int = Field(..., description="Total number of instances")
    healthy_instances: int = Field(..., description="Number of healthy instances")
    connection_counts: Dict[str, int] = Field(..., description="Active connection counts by instance")
    average_response_times: Dict[str, float] = Field(..., description="Average response times by instance")
    algorithm: str = Field(..., description="Load balancing algorithm")


class ProxyStats(BaseModel):
    """Proxy service statistics model."""

    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Statistics timestamp")
    dependencies: Dict[str, str] = Field(..., description="Dependency health status")


class HealthCheckResponse(BaseModel):
    """Health check response model."""

    status: ServiceStatus = Field(..., description="Overall health status")
    service: str = Field(..., description="Service name")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="Service version")
    dependencies: Optional[Dict[str, str]] = Field(None, description="Dependency health status")
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = False
    error: Dict[str, Any] = Field(..., description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    path: Optional[str] = Field(None, description="Request path that caused the error")


# Request Models
class ServiceDiscoveryRequest(BaseModel):
    """Service discovery request model."""

    service_name: str = Field(..., description="Service name to discover")
    instance_url: str = Field(..., description="Service instance URL")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Service metadata")


class CircuitBreakerControlRequest(BaseModel):
    """Circuit breaker control request model."""

    service_name: str = Field(..., description="Service name")
    action: str = Field(..., description="Action to perform: reset or force_open")

    @validator("action")
    def validate_action(cls, v):
        if v not in ["reset", "force_open"]:
            raise ValueError("Action must be either 'reset' or 'force_open'")
        return v


class RateLimitConfig(BaseModel):
    """Rate limiting configuration model."""

    service_name: str = Field(..., description="Service name")
    global_limit: Optional[int] = Field(None, description="Global rate limit (requests per minute)")
    per_ip_limit: Optional[int] = Field(None, description="Per IP rate limit (requests per minute)")
    per_user_limit: Optional[int] = Field(None, description="Per user rate limit (requests per minute)")


class CacheConfig(BaseModel):
    """Caching configuration model."""

    service_name: str = Field(..., description="Service name")
    enabled: bool = Field(..., description="Whether caching is enabled")
    ttl_seconds: int = Field(300, description="Cache TTL in seconds")
    cache_key_prefix: str = Field("gateway", description="Cache key prefix")


# Response Models
class ServicesListResponse(GatewayResponse):
    """Services list response model."""

    data: List[str] = Field(..., description="List of service names")


class ServiceStatusResponse(GatewayResponse):
    """Service status response model."""

    data: ServiceHealthStatus = Field(..., description="Service health status")


class AllServicesStatusResponse(GatewayResponse):
    """All services status response model."""

    data: Dict[str, Any] = Field(..., description="All services health status")


class CircuitBreakerStatsResponse(GatewayResponse):
    """Circuit breaker statistics response model."""

    data: Dict[str, CircuitBreakerStats] = Field(..., description="Circuit breaker statistics by service")


class LoadBalancerStatsResponse(GatewayResponse):
    """Load balancer statistics response model."""

    data: Dict[str, LoadBalancerStats] = Field(..., description="Load balancer statistics by service")


class ProxyStatsResponse(GatewayResponse):
    """Proxy statistics response model."""

    data: ProxyStats = Field(..., description="Proxy service statistics")


# Validation Models
class PathValidator(BaseModel):
    """Path validation model."""

    path: str = Field(..., description="URL path")

    @validator("path")
    def validate_path(cls, v):
        if not v.startswith("/"):
            raise ValueError("Path must start with '/'")
        return v


class ServiceNameValidator(BaseModel):
    """Service name validation model."""

    service_name: str = Field(..., description="Service name")

    @validator("service_name")
    def validate_service_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Service name cannot be empty")
        return v.strip()


# Configuration Models
class GatewayConfig(BaseModel):
    """Gateway configuration model."""

    service_name: str = Field(..., description="Gateway service name")
    version: str = Field(..., description="Gateway version")
    environment: str = Field(..., description="Environment")
    features: Dict[str, bool] = Field(..., description="Enabled features")
    limits: Dict[str, int] = Field(..., description="Service limits")
    supported_algorithms: List[str] = Field(..., description="Supported load balancing algorithms")


# Utility Models
class RequestInfo(BaseModel):
    """Request information model."""

    method: str = Field(..., description="HTTP method")
    url: str = Field(..., description="Request URL")
    headers: Dict[str, str] = Field(..., description="Request headers")
    query_params: Dict[str, str] = Field(..., description="Query parameters")
    client_ip: str = Field(..., description="Client IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    request_id: str = Field(..., description="Request ID")


class ResponseInfo(BaseModel):
    """Response information model."""

    status_code: int = Field(..., description="HTTP status code")
    headers: Dict[str, str] = Field(..., description="Response headers")
    body_size: int = Field(..., description="Response body size in bytes")
    response_time_ms: float = Field(..., description="Response time in milliseconds")