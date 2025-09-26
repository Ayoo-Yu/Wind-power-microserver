"""
Utility functions for Wind Farm Management Service.
"""

import logging
import redis
import aioredis
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import jwt
from passlib.context import CryptContext

from .config import get_settings
from .database import wind_farm_crud


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
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    """Create refresh token."""
    from jose import jwt

    settings = get_settings()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_expiration_days)

    payload = {
        "user_id": user_id,
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


# Password Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash password."""
    return pwd_context.hash(password)


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


# Wind Farm Specific Utilities
async def get_wind_farm_statistics(db: AsyncSession, wind_farm_id: str) -> Dict[str, Any]:
    """Get wind farm statistics."""
    try:
        # Get turbine count
        from .database import WindTurbine
        turbine_count_result = await db.execute(
            select(func.count(WindTurbine.id)).where(WindTurbine.wind_farm_id == wind_farm_id)
        )
        total_turbines = turbine_count_result.scalar()

        # Get running turbine count
        running_turbines_result = await db.execute(
            select(func.count(WindTurbine.id)).where(
                WindTurbine.wind_farm_id == wind_farm_id,
                WindTurbine.status == "running"
            )
        )
        running_turbines = running_turbines_result.scalar()

        return {
            "total_turbines": total_turbines,
            "running_turbines": running_turbines,
            "availability_rate": (running_turbines / total_turbines * 100) if total_turbines > 0 else 0,
        }
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to get wind farm statistics for {wind_farm_id}: {e}")
        return {
            "total_turbines": 0,
            "running_turbines": 0,
            "availability_rate": 0,
        }


async def validate_wind_farm_access(db: AsyncSession, user_id: str, wind_farm_id: str, required_role: str = "viewer") -> bool:
    """Validate user access to wind farm."""
    try:
        from .database import WindFarmAccess, User
        from .models import UserRole

        # Check if user is superuser
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if user and user.is_superuser:
            return True

        # Check wind farm access
        access_result = await db.execute(
            select(WindFarmAccess).where(
                WindFarmAccess.user_id == user_id,
                WindFarmAccess.wind_farm_id == wind_farm_id
            )
        )
        access = access_result.scalar_one_or_none()

        if not access:
            return False

        # Check role hierarchy
        role_hierarchy = {
            "viewer": 1,
            "analyst": 2,
            "operator": 3,
            "admin": 4,
        }

        user_role_level = role_hierarchy.get(access.role, 0)
        required_role_level = role_hierarchy.get(required_role, 0)

        return user_role_level >= required_role_level

    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to validate wind farm access for user {user_id} and wind farm {wind_farm_id}: {e}")
        return False


def format_coordinates(latitude: float, longitude: float) -> str:
    """Format coordinates as string."""
    return f"{latitude:.6f}, {longitude:.6f}"


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates in kilometers."""
    import math

    # Haversine formula
    R = 6371  # Earth's radius in kilometers
    lat_rad1 = math.radians(lat1)
    lat_rad2 = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat_rad1) * math.cos(lat_rad2) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# Configuration
class Config:
    """Configuration for utilities."""

    # Use enum values in serialization
    use_enum_values = True

    # Validate assignment
    validate_assignment = True

    # Allow population by field name
    allow_population_by_field_name = True

    # Use ORM mode
    orm_mode = True


# Apply configuration to utility models
for model in []:
    model.Config = Config()