"""
Middleware components for API Gateway.
"""

import time
import uuid
from datetime import datetime
from typing import Callable, Optional, Dict, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
import jwt

from .config import get_settings
from .utils import get_logger, generate_request_id, get_client_ip, sanitize_headers


class RequestContextMiddleware:
    """Middleware for request context management and logging."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings = get_settings()

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Process request and add context information."""

        # Generate request ID for tracing
        request_id = request.headers.get("X-Request-ID") or generate_request_id()

        # Extract user information from JWT token if present
        user_id = None
        tenant_id = None
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = jwt.decode(
                    token,
                    self.settings.secret_key,
                    algorithms=[self.settings.jwt_algorithm],
                    options={"verify_signature": False}  # We'll verify in auth middleware
                )
                user_id = payload.get("user_id")
                tenant_id = payload.get("tenant_id")
            except Exception as e:
                self.logger.warning(f"Failed to parse token for request {request_id}: {e}")

        # Add context to request state
        request.state.request_id = request_id
        request.state.user_id = user_id
        request.state.tenant_id = tenant_id
        request.state.start_time = time.time()

        # Process request
        try:
            response = await call_next(request)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Calculate response time
            response_time = (time.time() - request.state.start_time) * 1000
            response.headers["X-Response-Time"] = f"{response_time:.2f}ms"

            return response

        except Exception as e:
            self.logger.error(f"Request processing failed: {e}", extra={"request_id": request_id})
            raise


class LoggingMiddleware:
    """Middleware for request/response logging."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings = get_settings()

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""

        if not self.settings.request_logging_enabled:
            return await call_next(request)

        request_id = request.state.request_id
        start_time = time.time()

        # Log request
        self.logger.info(
            f"Request received: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "user_id": getattr(request.state, 'user_id', None),
                "tenant_id": getattr(request.state, 'tenant_id', None),
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_ip": get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
                "headers": sanitize_headers(dict(request.headers)),
            },
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate response time
            response_time = (time.time() - start_time) * 1000

            # Log response
            self.logger.info(
                f"Request completed: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "user_id": getattr(request.state, 'user_id', None),
                    "tenant_id": getattr(request.state, 'tenant_id', None),
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "response_time_ms": round(response_time, 2),
                },
            )

            return response

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "user_id": getattr(request.state, 'user_id', None),
                    "tenant_id": getattr(request.state, 'tenant_id', None),
                    "method": request.method,
                    "path": request.url.path,
                    "response_time_ms": round(response_time, 2),
                    "error": str(e),
                },
            )
            raise


class AuthenticationMiddleware:
    """Authentication middleware for JWT token validation."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Validate JWT token and extract user information."""

        # Skip authentication for public endpoints
        if self._is_public_endpoint(request):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

        try:
            token = auth_header.split(" ")[1]

            # Forward authentication to tenant service
            user_info = await self._authenticate_with_tenant_service(token)

            # Add user context to request state
            request.state.user_id = user_info.get("user_id")
            request.state.tenant_id = user_info.get("tenant_id")
            request.state.user_role = user_info.get("role")

            return await call_next(request)

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            raise HTTPException(status_code=401, detail="Authentication failed")

    def _is_public_endpoint(self, request: Request) -> bool:
        """Check if endpoint is public (no authentication required)."""
        public_paths = [
            "/health",
            "/docs",
            "/openapi.json",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
        ]

        return any(request.url.path.startswith(path) for path in public_paths)

    async def _authenticate_with_tenant_service(self, token: str) -> Dict[str, Any]:
        """Forward authentication to tenant service."""
        try:
            # Validate token with tenant service
            tenant_service_url = self.settings.services["tenant-service"].url
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{tenant_service_url}/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {token}"}
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return data.get("data", {})

                raise HTTPException(status_code=401, detail="Invalid token")

        except httpx.RequestError as e:
            self.logger.error(f"Failed to connect to tenant service: {e}")
            raise HTTPException(status_code=503, detail="Authentication service unavailable")
        except Exception as e:
            self.logger.error(f"Token validation failed: {e}")
            raise HTTPException(status_code=401, detail="Token validation failed")


class RateLimitMiddleware:
    """Rate limiting middleware."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Check rate limits before processing request."""

        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        try:
            # Get rate limit configuration
            client_id = self._get_client_identifier(request)
            limit, window = self._get_rate_limit_config(request)

            # Check rate limit
            redis_client = request.app.state.redis_manager.redis_client
            key = f"rate_limit:{client_id}"

            is_allowed, retry_after = await self._check_rate_limit(redis_client, key, limit, window)

            if not is_allowed:
                self.logger.warning(f"Rate limit exceeded for client {client_id}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Rate limit exceeded",
                            "retry_after": retry_after,
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    headers={"Retry-After": str(retry_after)}
                )

            # Process request
            response = await call_next(request)

            # Increment counter
            await self._increment_rate_limit(redis_client, key, window)

            return response

        except Exception as e:
            self.logger.error(f"Rate limiting error: {e}")
            # Fail open - allow request if rate limiting fails
            return await call_next(request)

    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Try to get user ID from authenticated request
        if hasattr(request.state, 'user_id') and request.state.user_id:
            return f"user:{request.state.user_id}"

        # Fall back to IP address
        client_ip = get_client_ip(request)
        return f"ip:{client_ip}"

    def _get_rate_limit_config(self, request: Request) -> tuple[int, int]:
        """Get rate limit configuration for the request."""
        # Global rate limits
        if hasattr(request.state, 'user_id') and request.state.user_id:
            return self.settings.per_user_rate_limit_rpm, 60  # per minute
        else:
            return self.settings.per_ip_rate_limit_rpm, 60  # per minute

    async def _check_rate_limit(self, redis_client, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Check if request is within rate limit."""
        try:
            current = await redis_client.get(key)
            current_count = int(current) if current else 0

            if current_count >= limit:
                ttl = await redis_client.ttl(key)
                return False, ttl if ttl > 0 else window

            return True, 0
        except Exception as e:
            self.logger.error(f"Rate limit check failed: {e}")
            return True, 0  # Fail open

    async def _increment_rate_limit(self, redis_client, key: str, window: int) -> None:
        """Increment rate limit counter."""
        try:
            pipe = redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            await pipe.execute()
        except Exception as e:
            self.logger.error(f"Failed to increment rate limit: {e}")


class CircuitBreakerMiddleware:
    """Circuit breaker middleware for fault tolerance."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Implement circuit breaker pattern."""

        if not self.settings.circuit_breaker_enabled:
            return await call_next(request)

        # Get service name from request path
        service_name = self._extract_service_name(request)
        if not service_name:
            return await call_next(request)

        # Check circuit breaker state
        circuit_breaker_manager = request.app.state.circuit_breaker_manager
        if await circuit_breaker_manager.is_open(service_name):
            self.logger.warning(f"Circuit breaker open for service {service_name}")
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error": {
                        "code": "CIRCUIT_BREAKER_OPEN",
                        "message": f"Service {service_name} is temporarily unavailable",
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        try:
            # Process request
            response = await call_next(request)

            # Record success
            await circuit_breaker_manager.record_success(service_name)

            return response

        except Exception as e:
            # Record failure
            await circuit_breaker_manager.record_failure(service_name)
            self.logger.error(f"Service {service_name} request failed: {e}")
            raise

    def _extract_service_name(self, request: Request) -> Optional[str]:
        """Extract service name from request path."""
        path = request.url.path

        # Extract service name from /api/{service}/{path} pattern
        if path.startswith("/api/"):
            parts = path.split("/")
            if len(parts) >= 3:
                return parts[2]  # /api/{service}/...

        return None


class ResponseTransformationMiddleware:
    """Middleware for response transformation."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Transform response format if needed."""

        response = await call_next(request)

        # Add CORS headers
        origin = request.headers.get("origin")
        if origin and origin in self.settings.cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response


# Middleware factory functions
def create_request_context_middleware() -> RequestContextMiddleware:
    """Create request context middleware."""
    return RequestContextMiddleware()


def create_logging_middleware() -> LoggingMiddleware:
    """Create logging middleware."""
    return LoggingMiddleware()


def create_authentication_middleware() -> AuthenticationMiddleware:
    """Create authentication middleware."""
    return AuthenticationMiddleware()


def create_rate_limit_middleware() -> RateLimitMiddleware:
    """Create rate limit middleware."""
    return RateLimitMiddleware()


def create_circuit_breaker_middleware() -> CircuitBreakerMiddleware:
    """Create circuit breaker middleware."""
    return CircuitBreakerMiddleware()


def create_response_transformation_middleware() -> ResponseTransformationMiddleware:
    """Create response transformation middleware."""
    return ResponseTransformationMiddleware()