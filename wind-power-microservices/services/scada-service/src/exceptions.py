"""
Exception classes for SCADA Data Service.
"""

from typing import Optional, Dict, Any
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
        validation_errors: Optional[list] = None,
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


# SCADA Specific Exceptions
class ScadaConnectionNotFoundException(ResourceNotFoundException):
    """Exception for SCADA connection not found."""

    def __init__(self, connection_id: str):
        super().__init__("SCADA Connection", connection_id, f"SCADA connection {connection_id} not found")


class DataPointNotFoundException(ResourceNotFoundException):
    """Exception for data point not found."""

    def __init__(self, point_id: str):
        super().__init__("Data Point", point_id, f"Data point {point_id} not found")


class AlarmNotFoundException(ResourceNotFoundException):
    """Exception for alarm not found."""

    def __init__(self, alarm_id: str):
        super().__init__("Alarm", alarm_id, f"Alarm {alarm_id} not found")


class DuplicateScadaConnectionException(ConflictException):
    """Exception for duplicate SCADA connection."""

    def __init__(self, wind_farm_id: str, host: str, port: int):
        message = f"SCADA connection already exists for wind farm {wind_farm_id} at {host}:{port}"
        super().__init__(message, "DUPLICATE_SCADA_CONNECTION")


class DuplicateDataPointException(ConflictException):
    """Exception for duplicate data point."""

    def __init__(self, connection_id: str, point_address: str):
        message = f"Data point with address '{point_address}' already exists in connection {connection_id}"
        super().__init__(message, "DUPLICATE_DATA_POINT")


class ScadaConnectionAccessDeniedException(AuthorizationException):
    """Exception for SCADA connection access denied."""

    def __init__(self, connection_id: str, user_id: str):
        message = f"User {user_id} does not have access to SCADA connection {connection_id}"
        super().__init__(message, "SCADA_CONNECTION_ACCESS_DENIED")
        self.connection_id = connection_id
        self.user_id = user_id


class InvalidScadaDataException(ValidationException):
    """Exception for invalid SCADA data."""

    def __init__(self, message: str):
        super().__init__(message, "INVALID_SCADA_DATA")


class InvalidDataPointException(ValidationException):
    """Exception for invalid data point."""

    def __init__(self, message: str):
        super().__init__(message, "INVALID_DATA_POINT")


class ScadaConnectionException(ServiceException):
    """Exception for SCADA connection errors."""

    def __init__(self, message: str, error_code: str = "SCADA_CONNECTION_ERROR"):
        super().__init__(message, error_code)


class ProtocolException(ServiceException):
    """Exception for protocol-related errors."""

    def __init__(self, message: str, protocol: str, error_code: str = "PROTOCOL_ERROR"):
        super().__init__(message, error_code)
        self.protocol = protocol


class KafkaException(ServiceException):
    """Exception for Kafka-related errors."""

    def __init__(self, message: str, error_code: str = "KAFKA_ERROR"):
        super().__init__(message, error_code)


class InfluxDBException(ServiceException):
    """Exception for InfluxDB-related errors."""

    def __init__(self, message: str, error_code: str = "INFLUXDB_ERROR"):
        super().__init__(message, error_code)


class TimeSeriesException(ServiceException):
    """Exception for time-series data errors."""

    def __init__(self, message: str, error_code: str = "TIMESERIES_ERROR"):
        super().__init__(message, error_code)


class RateLimitExceededException(ServiceException):
    """Exception for rate limit exceeded."""

    def __init__(self, retry_after: Optional[int] = None):
        super().__init__("Rate limit exceeded", "RATE_LIMIT_ERROR", 429)
        self.retry_after = retry_after

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.retry_after:
            result["retry_after"] = self.retry_after
        return result


# Error Code Mapping
ERROR_CODE_MAPPING = {
    "VALIDATION_ERROR": 400,
    "AUTHENTICATION_ERROR": 401,
    "AUTHORIZATION_ERROR": 403,
    "RESOURCE_NOT_FOUND": 404,
    "CONFLICT_ERROR": 409,
    "RATE_LIMIT_ERROR": 429,
    "DUPLICATE_SCADA_CONNECTION": 409,
    "DUPLICATE_DATA_POINT": 409,
    "SCADA_CONNECTION_ACCESS_DENIED": 403,
    "INVALID_SCADA_DATA": 400,
    "INVALID_DATA_POINT": 400,
    "SCADA_CONNECTION_ERROR": 500,
    "PROTOCOL_ERROR": 500,
    "KAFKA_ERROR": 500,
    "INFLUXDB_ERROR": 500,
    "TIMESERIES_ERROR": 500,
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