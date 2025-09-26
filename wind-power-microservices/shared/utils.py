"""
Shared utility functions for all microservices.
"""

import logging
import json
import time
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Callable, Awaitable
from functools import wraps
import uuid
import redis
import aioredis
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import get_database_settings, get_redis_settings, get_settings
from .exceptions import DatabaseException, RedisException, ExternalServiceException


# Logging Configuration
def setup_logging(service_name: str, log_level: str = "INFO", log_format: str = "json"):
    """Set up structured logging for microservices."""

    # Create logger
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

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance."""
    settings = get_settings()
    return setup_logging(name, settings.log_level, settings.log_format)


# Database Utilities
class DatabaseManager:
    """Database connection manager for async operations."""

    def __init__(self):
        self.db_settings = get_database_settings()
        self.engine = None
        self.async_session = None
        self.logger = get_logger(__name__)

    async def initialize(self):
        """Initialize database connections."""
        try:
            # Create async engine
            self.engine = create_async_engine(
                self.db_settings.database_url,
                pool_size=self.db_settings.pool_size,
                max_overflow=self.db_settings.max_overflow,
                pool_timeout=self.db_settings.pool_timeout,
                pool_recycle=self.db_settings.pool_recycle,
                echo=self.db_settings.echo,
                poolclass=QueuePool,
            )

            # Create session factory
            self.async_session = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            self.logger.info("Database connection pool initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise DatabaseException(f"Database initialization failed: {str(e)}")

    async def get_session(self) -> AsyncSession:
        """Get database session."""
        if not self.async_session:
            await self.initialize()
        return self.async_session()

    async def health_check(self) -> bool:
        """Check database health."""
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute("SELECT 1")
                await result.scalar()
                return True
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False

    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            self.logger.info("Database connections closed")


def create_database_manager() -> DatabaseManager:
    """Create database manager instance."""
    return DatabaseManager()


# Redis Utilities
class RedisManager:
    """Redis connection manager."""

    def __init__(self):
        self.redis_settings = get_redis_settings()
        self.redis_client = None
        self.logger = get_logger(__name__)

    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = aioredis.from_url(
                self.redis_settings.redis_url,
                max_connections=self.redis_settings.max_connections,
                socket_timeout=self.redis_settings.socket_timeout,
                socket_connect_timeout=self.redis_settings.socket_connect_timeout,
            )
            self.logger.info("Redis connection pool initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize Redis: {e}")
            raise RedisException(f"Redis initialization failed: {str(e)}")

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


def create_redis_manager() -> RedisManager:
    """Create Redis manager instance."""
    return RedisManager()


# HTTP Client Utilities
class HTTPClient:
    """HTTP client with retry logic and circuit breaker."""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
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
            raise ExternalServiceException(
                "external_service",
                f"HTTP GET failed: {e.response.status_code}",
                service_error=str(e),
            )
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
            raise ExternalServiceException(
                "external_service",
                f"HTTP POST failed: {e.response.status_code}",
                service_error=str(e),
            )
        except Exception as e:
            self.logger.error(f"HTTP POST error: {url} - {e}")
            raise

    async def close(self):
        """Close HTTP client."""
        await self.client.close()


def create_http_client() -> HTTPClient:
    """Create HTTP client instance."""
    return HTTPClient()


# Performance Monitoring
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


# Request ID Generation
def generate_request_id() -> str:
    """Generate unique request ID for tracing."""
    return str(uuid.uuid4())


# Date/Time Utilities
def format_datetime(dt: datetime) -> str:
    """Format datetime to ISO string."""
    return dt.isoformat()


def parse_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string."""
    return datetime.fromisoformat(dt_str)


# Validation Utilities
def validate_email(email: str) -> bool:
    """Validate email format."""
    import re
    pattern = r'^[^@]+@[^@]+\.[^@]+$'
    return re.match(pattern, email) is not None


def validate_phone(phone: str) -> bool:
    """Validate phone number format."""
    import re
    pattern = r'^\+?[1-9]\d{1,14}$'
    return re.match(pattern, phone) is not None


# Circuit Breaker Implementation
class CircuitBreaker:
    """Simple circuit breaker implementation."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.logger = get_logger(__name__)

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""

        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                self.logger.info("Circuit breaker attempting reset")
            else:
                from .exceptions import CircuitBreakerException
                raise CircuitBreakerException(
                    "protected_service",
                    "Circuit breaker is open"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return True

        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
        self.logger.debug("Circuit breaker reset on success")

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )


def create_circuit_breaker(**kwargs) -> CircuitBreaker:
    """Create circuit breaker instance."""
    return CircuitBreaker(**kwargs)