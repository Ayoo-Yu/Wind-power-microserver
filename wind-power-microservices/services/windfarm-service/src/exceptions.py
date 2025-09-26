"""
Exception classes for Wind Farm Management Service.
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


# Wind Farm Specific Exceptions
class WindFarmNotFoundException(ResourceNotFoundException):
    """Exception for wind farm not found."""

    def __init__(self, wind_farm_id: str):
        super().__init__("Wind Farm", wind_farm_id, f"Wind farm {wind_farm_id} not found")


class TurbineNotFoundException(ResourceNotFoundException):
    """Exception for turbine not found."""

    def __init__(self, turbine_id: str):
        super().__init__("Wind Turbine", turbine_id, f"Wind turbine {turbine_id} not found")


class DuplicateWindFarmException(ConflictException):
    """Exception for duplicate wind farm code."""

    def __init__(self, code: str):
        message = f"Wind farm with code '{code}' already exists"
        super().__init__(message, "DUPLICATE_WINDFARM_CODE")


class DuplicateTurbineException(ConflictException):
    """Exception for duplicate turbine ID within a wind farm."""

    def __init__(self, wind_farm_id: str, turbine_id: str):
        message = f"Wind turbine with ID '{turbine_id}' already exists in wind farm {wind_farm_id}"
        super().__init__(message, "DUPLICATE_TURBINE_ID")


class WindFarmAccessDeniedException(AuthorizationException):
    """Exception for wind farm access denied."""

    def __init__(self, wind_farm_id: str, user_id: str):
        message = f"User {user_id} does not have access to wind farm {wind_farm_id}"
        super().__init__(message, "WINDFARM_ACCESS_DENIED")
        self.wind_farm_id = wind_farm_id
        self.user_id = user_id


class InvalidWindFarmDataException(ValidationException):
    """Exception for invalid wind farm data."""

    def __init__(self, message: str):
        super().__init__(message, "INVALID_WINDFARM_DATA")


class InvalidTurbineDataException(ValidationException):
    """Exception for invalid turbine data."""

    def __init__(self, message: str):
        super().__init__(message, "INVALID_TURBINE_DATA")


class InvalidCoordinatesException(ValidationException):
    """Exception for invalid coordinates."""

    def __init__(self, latitude: float, longitude: float):
        message = f"Invalid coordinates: latitude={latitude}, longitude={longitude}"
        super().__init__(message, "INVALID_COORDINATES")


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
    "DUPLICATE_WINDFARM_CODE": 409,
    "DUPLICATE_TURBINE_ID": 409,
    "WINDFARM_ACCESS_DENIED": 403,
    "INVALID_WINDFARM_DATA": 400,
    "INVALID_TURBINE_DATA": 400,
    "INVALID_COORDINATES": 400,
    "SERVICE_ERROR": 500,
}


def get_http_status_code(error_code: str) -> int:
    """Get HTTP status code for an error code."""
    return ERROR_CODE_MAPPING.get(error_code, 500)


def create_validation_error(field: str, message: str) -> Dict[str, Any]:
    """Create a validation error dictionary."""
    return {"field": field, "message": message}


# User Specific Exceptions
class UserNotFoundException(ResourceNotFoundException):
    """Exception for user not found."""

    def __init__(self, user_id: str):
        super().__init__("User", user_id, f"User {user_id} not found")


class DuplicateUserException(ConflictException):
    """Exception for duplicate user."""

    def __init__(self, message: str):
        super().__init__(message, "DUPLICATE_USER")


class InvalidUserDataException(ValidationException):
    """Exception for invalid user data."""

    def __init__(self, message: str):
        super().__init__(message, "INVALID_USER_DATA")


def create_error_response(exception: ServiceException) -> Dict[str, Any]:
    """Create a standard error response from an exception."""
    return {
        "success": False,
        "error": exception.to_dict(),
        "timestamp": datetime.utcnow().isoformat(),
    }