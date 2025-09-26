"""
Utility functions for Tenant Management Service.
"""

import logging
import redis
import aioredis
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool

from .config import get_settings


# Logging Configuration
def get_logger(name: str) -> logging.Logger:
    """Get configured logger instance."""
    settings = get_settings()

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# Redis Manager
class RedisManager:
    """Redis connection manager."""

    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        self.logger = get_logger(__name__)

    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = aioredis.from_url(
                self.settings.redis_url,
                max_connections=50,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            self.logger.info("Redis connection pool initialized")

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


def create_redis_manager() -> RedisManager:
    """Create Redis manager instance."""
    return RedisManager()


# JWT Token Utilities
def create_jwt_token(
    user_id: str,
    tenant_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create JWT token for authentication."""
    from jose import jwt

    settings = get_settings()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expiration_minutes)

    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, tenant_id: str) -> str:
    """Create refresh token."""
    from jose import jwt

    settings = get_settings()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_expiration_days)

    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decode and validate JWT token."""
    from jose import jwt, JWTError, ExpiredSignatureError

    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except ExpiredSignatureError:
        raise Exception("Token has expired")
    except JWTError:
        raise Exception("Invalid token")


# Password Validation
def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password strength."""
    settings = get_settings()

    if len(password) < settings.password_min_length:
        return False, f"Password must be at least {settings.password_min_length} characters long"

    has_uppercase = any(c.isupper() for c in password)
    has_lowercase = any(c.islower() for c in password)
    has_numbers = any(c.isdigit() for c in password)
    has_symbols = any(c in "!@#$%^&*(),.?\":{}|\u003c\u003e" for c in password)

    if settings.password_require_uppercase and not has_uppercase:
        return False, "Password must contain at least one uppercase letter"

    if settings.password_require_lowercase and not has_lowercase:
        return False, "Password must contain at least one lowercase letter"

    if settings.password_require_numbers and not has_numbers:
        return False, "Password must contain at least one number"

    if settings.password_require_symbols and not has_symbols:
        return False, "Password must contain at least one special character"

    return True, "Password is valid"


# Rate Limiting Utilities
async def check_rate_limit(
    redis_client: aioredis.Redis,
    key: str,
    limit: int,
    window: int,
) -> tuple[bool, int]:
    """Check rate limit for a given key."""
    try:
        current = await redis_client.get(key)
        current_count = int(current) if current else 0

        if current_count >= limit:
            ttl = await redis_client.ttl(key)
            return False, ttl if ttl > 0 else window

        return True, 0
    except Exception as e:
        # Fail open - allow request if rate limiting fails
        return True, 0


async def increment_rate_limit(
    redis_client: aioredis.Redis,
    key: str,
    window: int,
) -> None:
    """Increment rate limit counter."""
    try:
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        await pipe.execute()
    except Exception as e:
        # Log error but don't fail the request
        logger = get_logger(__name__)
        logger.error(f"Failed to increment rate limit: {e}")


# Response Utilities
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


# Pagination Utilities
def paginate_query(
    items: list,
    page: int = 1,
    size: int = 20,
) -> Dict[str, Any]:
    """Paginate a list of items."""
    total = len(items)
    pages = (total + size - 1) // size

    start = (page - 1) * size
    end = start + size

    paginated_items = items[start:end]

    return {
        "items": paginated_items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1,
    }