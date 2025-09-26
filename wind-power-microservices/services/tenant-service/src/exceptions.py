"""
Exception classes for Tenant Management Service.
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


# Specific exceptions for Tenant Service
class UserNotFoundException(ResourceNotFoundException):
    """Exception for user not found."""

    def __init__(self, user_id: str):
        super().__init__("User", user_id, f"User {user_id} not found")


class TenantNotFoundException(ResourceNotFoundException):
    """Exception for tenant not found."""

    def __init__(self, tenant_id: str):
        super().__init__("Tenant", tenant_id, f"Tenant {tenant_id} not found")


class DuplicateUserException(ConflictException):
    """Exception for duplicate user."""

    def __init__(self, username: str, email: str):
        message = f"User with username '{username}' or email '{email}' already exists"
        super().__init__(message, "DUPLICATE_USER_ERROR")


class DuplicateTenantException(ConflictException):
    """Exception for duplicate tenant."""

    def __init__(self, code: str):
        message = f"Tenant with code '{code}' already exists"
        super().__init__(message, "DUPLICATE_TENANT_ERROR")


class InvalidCredentialsException(AuthenticationException):
    """Exception for invalid login credentials."""

    def __init__(self):
        super().__init__("Invalid username or password", "INVALID_CREDENTIALS_ERROR")


class TokenExpiredException(AuthenticationException):
    """Exception for expired token."""

    def __init__(self):
        super().__init__("Token has expired", "TOKEN_EXPIRED_ERROR")


class InvalidTokenException(AuthenticationException):
    """Exception for invalid token."""

    def __init__(self):
        super().__init__("Invalid token", "INVALID_TOKEN_ERROR")


class InsufficientPermissionsException(AuthorizationException):
    """Exception for insufficient permissions."""

    def __init__(self, required_role: str):
        message = f"Insufficient permissions. Required role: {required_role}"
        super().__init__(message, "INSUFFICIENT_PERMISSIONS_ERROR")


class TenantAccessException(AuthorizationException):
    """Exception for tenant access violations."""

    def __init__(self, tenant_id: str, user_id: str):
        message = f"User {user_id} does not have access to tenant {tenant_id}"
        super().__init__(message, "TENANT_ACCESS_ERROR")
        self.tenant_id = tenant_id
        self.user_id = user_id


class WeakPasswordException(ValidationException):
    """Exception for weak password."""

    def __init__(self, message: str):
        super().__init__(message, "WEAK_PASSWORD_ERROR")


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
    "DUPLICATE_USER_ERROR": 409,
    "DUPLICATE_TENANT_ERROR": 409,
    "INVALID_CREDENTIALS_ERROR": 401,
    "TOKEN_EXPIRED_ERROR": 401,
    "INVALID_TOKEN_ERROR": 401,
    "INSUFFICIENT_PERMISSIONS_ERROR": 403,
    "TENANT_ACCESS_ERROR": 403,
    "WEAK_PASSWORD_ERROR": 400,
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