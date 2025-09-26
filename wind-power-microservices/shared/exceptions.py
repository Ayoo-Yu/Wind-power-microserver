"""
Shared exception classes for all microservices.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime


class ServiceException(Exception):
    """Base exception for all service-related errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "SERVICE_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }


class ValidationException(ServiceException):
    """Exception for data validation errors."""

    def __init__(
        self,
        message: str = "Validation failed",
        error_code: str = "VALIDATION_ERROR",
        status_code: int = 400,
        validation_errors: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(message, error_code, status_code)
        self.validation_errors = validation_errors or []

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["validation_errors"] = self.validation_errors
        return result


class AuthenticationException(ServiceException):
    """Exception for authentication failures."""

    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: str = "AUTHENTICATION_ERROR",
        status_code: int = 401,
    ):
        super().__init__(message, error_code, status_code)


class AuthorizationException(ServiceException):
    """Exception for authorization failures."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        error_code: str = "AUTHORIZATION_ERROR",
        status_code: int = 403,
    ):
        super().__init__(message, error_code, status_code)


class ResourceNotFoundException(ServiceException):
    """Exception for missing resources."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        message: Optional[str] = None,
        error_code: str = "RESOURCE_NOT_FOUND",
        status_code: int = 404,
    ):
        if message is None:
            message = f"{resource_type} with ID {resource_id} not found"
        super().__init__(message, error_code, status_code)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ConflictException(ServiceException):
    """Exception for resource conflicts."""

    def __init__(
        self,
        message: str = "Resource conflict",
        error_code: str = "CONFLICT_ERROR",
        status_code: int = 409,
    ):
        super().__init__(message, error_code, status_code)


class DatabaseException(ServiceException):
    """Exception for database-related errors."""

    def __init__(
        self,
        message: str = "Database operation failed",
        error_code: str = "DATABASE_ERROR",
        status_code: int = 500,
        db_error: Optional[str] = None,
    ):
        super().__init__(message, error_code, status_code)
        self.db_error = db_error


class RedisException(ServiceException):
    """Exception for Redis-related errors."""

    def __init__(
        self,
        message: str = "Redis operation failed",
        error_code: str = "REDIS_ERROR",
        status_code: int = 500,
        redis_error: Optional[str] = None,
    ):
        super().__init__(message, error_code, status_code)
        self.redis_error = redis_error


class ExternalServiceException(ServiceException):
    """Exception for external service integration errors."""

    def __init__(
        self,
        service_name: str,
        message: str,
        error_code: str = "EXTERNAL_SERVICE_ERROR",
        status_code: int = 502,
        service_error: Optional[str] = None,
    ):
        full_message = f"External service {service_name} error: {message}"
        super().__init__(full_message, error_code, status_code)
        self.service_name = service_name
        self.service_error = service_error


class RateLimitException(ServiceException):
    """Exception for rate limiting violations."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        error_code: str = "RATE_LIMIT_ERROR",
        status_code: int = 429,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message, error_code, status_code)
        self.retry_after = retry_after

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.retry_after:
            result["retry_after"] = self.retry_after
        return result


class CircuitBreakerException(ServiceException):
    """Exception for circuit breaker failures."""

    def __init__(
        self,
        service_name: str,
        message: str = "Service temporarily unavailable",
        error_code: str = "CIRCUIT_BREAKER_OPEN",
        status_code: int = 503,
    ):
        full_message = f"Circuit breaker open for service {service_name}: {message}"
        super().__init__(full_message, error_code, status_code)
        self.service_name = service_name


class TimeoutException(ServiceException):
    """Exception for operation timeouts."""

    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        message: Optional[str] = None,
        error_code: str = "TIMEOUT_ERROR",
        status_code: int = 504,
    ):
        if message is None:
            message = f"Operation {operation} timed out after {timeout_seconds} seconds"
        super().__init__(message, error_code, status_code)
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class BusinessRuleException(ServiceException):
    """Exception for business rule violations."""

    def __init__(
        self,
        rule_name: str,
        message: str,
        error_code: str = "BUSINESS_RULE_ERROR",
        status_code: int = 400,
    ):
        full_message = f"Business rule '{rule_name}' violated: {message}"
        super().__init__(full_message, error_code, status_code)
        self.rule_name = rule_name


# Specific Business Exceptions
class InvalidTurbineDataException(BusinessRuleException):
    """Exception for invalid turbine data."""

    def __init__(
        self,
        message: str = "Invalid turbine data provided",
        rule_name: str = "turbine_data_validation",
    ):
        super().__init__(rule_name, message)


class PredictionModelNotFoundException(ResourceNotFoundException):
    """Exception for missing prediction models."""

    def __init__(self, model_id: str):
        super().__init__("Prediction Model", model_id, f"Prediction model {model_id} not found")


class ReportScheduleException(BusinessRuleException):
    """Exception for report scheduling conflicts."""

    def __init__(
        self,
        message: str = "Invalid report schedule configuration",
        rule_name: str = "report_schedule_validation",
    ):
        super().__init__(rule_name, message)


class TenantAccessException(AuthorizationException):
    """Exception for tenant access violations."""

    def __init__(
        self,
        tenant_id: str,
        user_id: str,
        message: Optional[str] = None,
    ):
        if message is None:
            message = f"User {user_id} does not have access to tenant {tenant_id}"
        super().__init__(message)
        self.tenant_id = tenant_id
        self.user_id = user_id


class DataQualityException(BusinessRuleException):
    """Exception for data quality issues."""

    def __init__(
        self,
        data_source: str,
        quality_issues: List[str],
        rule_name: str = "data_quality_validation",
    ):
        message = f"Data quality issues in {data_source}: {', '.join(quality_issues)}"
        super().__init__(rule_name, message)
        self.data_source = data_source
        self.quality_issues = quality_issues


# Error Code Mapping
ERROR_CODE_MAPPING = {
    "VALIDATION_ERROR": 400,
    "AUTHENTICATION_ERROR": 401,
    "AUTHORIZATION_ERROR": 403,
    "RESOURCE_NOT_FOUND": 404,
    "CONFLICT_ERROR": 409,
    "RATE_LIMIT_ERROR": 429,
    "BUSINESS_RULE_ERROR": 400,
    "DATABASE_ERROR": 500,
    "EXTERNAL_SERVICE_ERROR": 502,
    "CIRCUIT_BREAKER_OPEN": 503,
    "TIMEOUT_ERROR": 504,
    "SERVICE_ERROR": 500,
}


def get_http_status_code(error_code: str) -> int:
    """Get HTTP status code for an error code."""
    return ERROR_CODE_MAPPING.get(error_code, 500)


def create_validation_error(field: str, message: str) -> Dict[str, Any]:
    """Create a validation error dictionary."""
    return {"field": field, "message": message}


def create_error_response(exception: ServiceException) -> Dict[str, Any]:
    """Create a standard error response from an exception."""
    return {
        "success": False,
        "error": exception.to_dict(),
        "timestamp": datetime.utcnow().isoformat(),
    }