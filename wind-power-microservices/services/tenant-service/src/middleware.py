"""
Middleware components for Tenant Management Service.
"""

import time
import uuid
from datetime import datetime
from typing import Callable, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from .config import get_settings
from .exceptions import ServiceException
from .utils import get_logger


class RequestContextMiddleware:
    """Middleware for request context management."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings = get_settings()

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Process request and add context information."""

        # Generate request ID for tracing
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Extract user information from JWT token if present
        user_id = None
        tenant_id = None
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            try:
                # For now, we'll add JWT parsing later
                # token = auth_header.split(" ")[1]
                # payload = decode_jwt_token(token)
                # user_id = payload.get("user_id")
                # tenant_id = payload.get("tenant_id")
                pass
            except Exception as e:
                self.logger.warning(f"Failed to parse token for request {request_id}: {e}")

        # Add context to request state
        request.state.request_id = request_id
        request.state.user_id = user_id
        request.state.tenant_id = tenant_id

        # Log request
        self.logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "method": request.method,
                "path": request.url.path,
                "user_agent": request.headers.get("user-agent"),
                "ip_address": self._get_client_ip(request),
            },
        )

        # Process request
        start_time = time.time()
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Log response
            self.logger.info(
                f"Request completed: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "error": str(e),
                },
            )
            raise

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection
        if hasattr(request.client, 'host'):
            return request.client.host

        return "unknown"


class ErrorHandlingMiddleware:
    """Global error handling middleware."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Handle exceptions and return appropriate error responses."""

        try:
            return await call_next(request)

        except ServiceException as e:
            self.logger.error(f"Service exception: {e.message}", extra={"error": str(e)})
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "success": False,
                    "error": e.to_dict(),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        except Exception as e:
            self.logger.error(f"Unhandled exception: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": {
                        "error_code": "INTERNAL_SERVER_ERROR",
                        "message": "An internal server error occurred",
                        "status_code": 500,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )


class CORSMiddleware:
    """CORS middleware for cross-origin requests."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Handle CORS preflight and actual requests."""

        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response()
            self._set_cors_headers(response, request)
            return response

        # Process actual request
        response = await call_next(request)
        self._set_cors_headers(response, request)
        return response

    def _set_cors_headers(self, response: Response, request: Request):
        """Set CORS headers on response."""
        origin = request.headers.get("origin")

        if origin and ("*" in self.settings.cors_origins or origin in self.settings.cors_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization, X-Request-ID, X-API-Key"
            )
            response.headers["Access-Control-Max-Age"] = "3600"


class RateLimitMiddleware:
    """Rate limiting middleware."""

    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.logger = get_logger(__name__)
        self.default_limit = 100  # requests per minute
        self.default_window = 60  # seconds

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Check rate limits before processing request."""

        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_identifier(request)
        request_id = request.state.request_id

        try:
            # Check rate limit
            if await self._is_rate_limited(client_id, request_id):
                from .exceptions import RateLimitExceededException
                raise RateLimitExceededException(retry_after=self.default_window)

            # Process request
            response = await call_next(request)
            return response

        except Exception as e:
            # Re-raise if it's our exception, otherwise log and continue
            if isinstance(e, Exception) and "RateLimitExceededException" in str(type(e)):
                raise

            self.logger.error(f"Rate limiting error: {e}")
            # Fail open - allow request if rate limiting fails
            return await call_next(request)

    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Try to get user ID from authenticated request
        if hasattr(request.state, 'user_id') and request.state.user_id:
            return f"user:{request.state.user_id}"

        # Fall back to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"

        if hasattr(request.client, 'host'):
            return f"ip:{request.client.host}"

        return "unknown"

    async def _is_rate_limited(self, client_id: str, request_id: str) -> bool:
        """Check if client is rate limited."""
        try:
            key = f"rate_limit:{client_id}"
            current_count = await self.redis_client.get(key)

            if current_count is None:
                # First request in window
                await self.redis_client.setex(key, self.default_window, 1)
                return False

            current_count = int(current_count)
            if current_count >= self.default_limit:
                self.logger.warning(
                    f"Rate limit exceeded for client {client_id}",
                    extra={"request_id": request_id, "current_count": current_count},
                )
                return True

            # Increment counter
            await self.redis_client.incr(key)
            return False

        except Exception as e:
            self.logger.error(f"Redis rate limiting error: {e}")
            return False  # Fail open


# Middleware Factory Functions
def create_request_context_middleware() -> RequestContextMiddleware:
    """Create request context middleware."""
    return RequestContextMiddleware()


def create_error_handling_middleware() -> ErrorHandlingMiddleware:
    """Create error handling middleware."""
    return ErrorHandlingMiddleware()


def create_cors_middleware() -> CORSMiddleware:
    """Create CORS middleware."""
    return CORSMiddleware()


def create_rate_limit_middleware(redis_client) -> RateLimitMiddleware:
    """Create rate limiting middleware."""
    return RateLimitMiddleware(redis_client)