"""
Utility functions for API Gateway.
"""

import logging
import json
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable
from functools import wraps
import uuid
import aioredis
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import get_settings


def setup_logging(service_name: str, log_level: str = "INFO", log_format: str = "json"):
    """Set up structured logging for API Gateway."""

    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Create formatter
    if log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'tenant_id'):
            log_entry['tenant_id'] = record.tenant_id
        if hasattr(record, 'service_name'):
            log_entry['service_name'] = record.service_name
        if hasattr(record, 'duration_ms'):
            log_entry['duration_ms'] = record.duration_ms
        if hasattr(record, 'status_code'):
            log_entry['status_code'] = record.status_code
        if hasattr(record, 'response_time'):
            log_entry['response_time'] = record.response_time

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance."""
    settings = get_settings()
    return setup_logging(name, settings.log_level, settings.log_format)


# Redis Manager
class RedisManager:
    """Redis connection manager for API Gateway."""

    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        self.logger = get_logger(__name__)

    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = aioredis.from_url(
                self.settings.redis_url,
                max_connections=100,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            self.logger.info("Redis connection pool initialized for API Gateway")

        except Exception as e:
            self.logger.error(f"Failed to initialize Redis: {e}")
            raise Exception(f"Redis initialization failed: {str(e)}")

    async def get_client(self) -> aioredis.Redis:
        """Get Redis client."""
        if not self.redis_client:
            await self.initialize()
        return self.redis_client

    async def health_check(self) -> bool:
        """Check Redis health."""
        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            self.logger.error(f"Redis health check failed: {e}")
            return False

    async def close(self):
        """Close Redis connections."""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("Redis connections closed")

    # Rate limiting methods
    async def check_rate_limit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Check rate limit for a given key."""
        try:
            current = await self.redis_client.get(key)
            current_count = int(current) if current else 0

            if current_count >= limit:
                ttl = await self.redis_client.ttl(key)
                return False, ttl if ttl > 0 else window

            return True, 0
        except Exception as e:
            self.logger.error(f"Rate limit check failed: {e}")
            return True, 0  # Fail open

    async def increment_rate_limit(self, key: str, window: int) -> None:
        """Increment rate limit counter."""
        try:
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            await pipe.execute()
        except Exception as e:
            self.logger.error(f"Failed to increment rate limit: {e}")

    # Circuit breaker methods
    async def get_circuit_breaker_state(self, service_name: str) -> Dict[str, Any]:
        """Get circuit breaker state for a service."""
        try:
            key = f"circuit_breaker:{service_name}"
            state = await self.redis_client.hgetall(key)
            return state or {}
        except Exception as e:
            self.logger.error(f"Failed to get circuit breaker state: {e}")
            return {}

    async def set_circuit_breaker_state(self, service_name: str, state: Dict[str, Any]) -> None:
        """Set circuit breaker state for a service."""
        try:
            key = f"circuit_breaker:{service_name}"
            await self.redis_client.hset(key, mapping=state)
            await self.redis_client.expire(key, 3600)  # 1 hour TTL
        except Exception as e:
            self.logger.error(f"Failed to set circuit breaker state: {e}")

    # Service discovery methods
    async def register_service_instance(self, service_name: str, instance_url: str, metadata: Dict[str, Any]) -> None:
        """Register a service instance."""
        try:
            key = f"services:{service_name}:instances:{instance_url}"
            metadata["registered_at"] = datetime.utcnow().isoformat()
            await self.redis_client.hset(key, mapping=metadata)
            await self.redis_client.expire(key, 30)  # 30 second TTL for health checks
        except Exception as e:
            self.logger.error(f"Failed to register service instance: {e}")

    async def get_service_instances(self, service_name: str) -> Dict[str, Dict[str, Any]]:
        """Get all instances for a service."""
        try:
            pattern = f"services:{service_name}:instances:*"
            keys = await self.redis_client.keys(pattern)

            instances = {}
            for key in keys:
                instance_url = key.decode().split(":")[-1]
                metadata = await self.redis_client.hgetall(key)
                instances[instance_url] = {k.decode(): v.decode() for k, v in metadata.items()}

            return instances
        except Exception as e:
            self.logger.error(f"Failed to get service instances: {e}")
            return {}

    # Caching methods
    async def get_cached_response(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached response."""
        try:
            cached = await self.redis_client.get(key)
            if cached:
                return json.loads(cached.decode())
            return None
        except Exception as e:
            self.logger.error(f"Failed to get cached response: {e}")
            return None

    async def cache_response(self, key: str, response: Dict[str, Any], ttl: int = 300) -> None:
        """Cache response with TTL."""
        try:
            await self.redis_client.setex(key, ttl, json.dumps(response))
        except Exception as e:
            self.logger.error(f"Failed to cache response: {e}")

    async def invalidate_cache(self, pattern: str) -> None:
        """Invalidate cached responses by pattern."""
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
        except Exception as e:
            self.logger.error(f"Failed to invalidate cache: {e}")


def create_redis_manager() -> RedisManager:
    """Create Redis manager instance."""
    return RedisManager()


# Request/Response Utilities
def generate_request_id() -> str:
    """Generate unique request ID."""
    return str(uuid.uuid4())


def get_client_ip(request) -> str:
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


# Performance monitoring
def measure_performance(func: Callable) -> Callable:
    """Decorator to measure function execution time."""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        logger = get_logger(func.__module__)

        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Function {func.__name__} completed",
                extra={
                    "duration_ms": round(duration_ms, 2),
                    "function": func.__name__,
                }
            )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Function {func.__name__} failed",
                extra={
                    "duration_ms": round(duration_ms, 2),
                    "function": func.__name__,
                    "error": str(e),
                }
            )
            raise

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        logger = get_logger(func.__module__)

        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Function {func.__name__} completed",
                extra={
                    "duration_ms": round(duration_ms, 2),
                    "function": func.__name__,
                }
            )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Function {func.__name__} failed",
                extra={
                    "duration_ms": round(duration_ms, 2),
                    "function": func.__name__,
                    "error": str(e),
                }
            )
            raise

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


# HTTP Client with retry logic
class HTTPClient:
    """HTTP client with retry logic and circuit breaker."""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
        )
        self.logger = get_logger(__name__)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """HTTP GET with retry logic."""
        try:
            response = await self.client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP GET failed: {url} - {e}")
            raise
        except Exception as e:
            self.logger.error(f"HTTP GET error: {url} - {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """HTTP POST with retry logic."""
        try:
            response = await self.client.post(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP POST failed: {url} - {e}")
            raise
        except Exception as e:
            self.logger.error(f"HTTP POST error: {url} - {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def put(self, url: str, **kwargs) -> httpx.Response:
        """HTTP PUT with retry logic."""
        try:
            response = await self.client.put(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP PUT failed: {url} - {e}")
            raise
        except Exception as e:
            self.logger.error(f"HTTP PUT error: {url} - {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """HTTP DELETE with retry logic."""
        try:
            response = await self.client.delete(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP DELETE failed: {url} - {e}")
            raise
        except Exception as e:
            self.logger.error(f"HTTP DELETE error: {url} - {e}")
            raise

    async def close(self):
        """Close HTTP client."""
        await self.client.close()


def create_http_client() -> HTTPClient:
    """Create HTTP client instance."""
    return HTTPClient()


# Response utilities
def create_success_response(
    data: Any = None,
    message: str = "Success",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create standardized success response."""
    response = {
        "success": True,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if data is not None:
        response["data"] = data

    if metadata:
        response["metadata"] = metadata

    return response


def create_error_response(
    message: str,
    error_code: str = "ERROR",
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create standardized error response."""
    response = {
        "success": False,
        "message": message,
        "error_code": error_code,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if details:
        response["details"] = details

    return response


# Security utilities
def sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Sanitize headers by removing sensitive information."""
    sensitive_headers = ["authorization", "x-api-key", "cookie", "set-cookie"]
    sanitized = {}

    for key, value in headers.items():
        if key.lower() in sensitive_headers:
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value

    return sanitized