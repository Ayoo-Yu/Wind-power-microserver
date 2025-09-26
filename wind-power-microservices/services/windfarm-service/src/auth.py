"""
Authentication and authorization for Wind Farm Management Service.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .database import get_db_session, User
from .utils import decode_jwt_token, verify_password, create_jwt_token, create_refresh_token
from .config import get_settings
from .exceptions import AuthenticationException, AuthorizationException

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/users/login")

settings = get_settings()


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password."""
    try:
        result = await db.execute(
            select(User).where(User.username == username, User.is_active == True)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        return user

    except Exception as e:
        raise AuthenticationException(f"Authentication failed: {str(e)}")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT token
        payload = decode_jwt_token(token)
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")

        if username is None or user_id is None:
            raise credentials_exception

    except Exception:
        raise credentials_exception

    # Get user from database
    result = await db.execute(
        select(User).where(User.username == username, User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current admin user."""
    if not (current_user.role == "admin" or current_user.is_superuser):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """Get user by ID."""
    try:
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        raise AuthenticationException(f"Failed to get user: {str(e)}")


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get user by username."""
    try:
        result = await db.execute(
            select(User).where(User.username == username, User.is_active == True)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        raise AuthenticationException(f"Failed to get user: {str(e)}")


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expiration_minutes)

    to_encode = data.copy()
    to_encode.update({"exp": expire, "type": "access"})

    return create_jwt_token(
        user_id=data.get("user_id", ""),
        role=data.get("role", "viewer"),
        expires_delta=expires_delta
    )


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create refresh token."""
    return create_refresh_token(user_id=data.get("sub", ""))


def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode token."""
    try:
        return decode_jwt_token(token)
    except Exception as e:
        raise AuthenticationException(f"Invalid token: {str(e)}")


async def check_user_permission(
    db: AsyncSession,
    user_id: str,
    wind_farm_id: str,
    required_role: str = "viewer"
) -> bool:
    """Check if user has permission for wind farm."""
    try:
        from .database import WindFarmAccess
        from .models import UserRole

        # Get user
        user = await get_user_by_id(db, user_id)
        if not user:
            return False

        # Superusers have access to everything
        if user.is_superuser:
            return True

        # Check wind farm access
        result = await db.execute(
            select(WindFarmAccess).where(
                WindFarmAccess.user_id == user_id,
                WindFarmAccess.wind_farm_id == wind_farm_id
            )
        )
        access = result.scalar_one_or_none()

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
        logger.error(f"Failed to check user permission: {e}")
        return False


async def require_wind_farm_access(
    wind_farm_id: str,
    required_role: str = "viewer",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """Require wind farm access for current user."""
    has_access = await check_user_permission(db, current_user.id, wind_farm_id, required_role)

    if not has_access:
        raise AuthorizationException(
            f"User {current_user.id} does not have {required_role} access to wind farm {wind_farm_id}"
        )

    return current_user


# Role-based dependency functions
async def require_viewer_role(
    wind_farm_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """Require viewer role for wind farm."""
    return await require_wind_farm_access(wind_farm_id, "viewer", current_user, db)


async def require_analyst_role(
    wind_farm_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """Require analyst role for wind farm."""
    return await require_wind_farm_access(wind_farm_id, "analyst", current_user, db)


async def require_operator_role(
    wind_farm_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """Require operator role for wind farm."""
    return await require_wind_farm_access(wind_farm_id, "operator", current_user, db)


async def require_admin_role(
    wind_farm_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """Require admin role for wind farm."""
    return await require_wind_farm_access(wind_farm_id, "admin", current_user, db)


# Admin-only dependency
async def require_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Require admin user."""
    if not (current_user.role == "admin" or current_user.is_superuser):
        raise AuthorizationException("Admin access required")
    return current_user


# Rate limiting helpers
async def check_rate_limit(
    redis_client,
    key: str,
    limit: int,
    window: int
) -> tuple[bool, int]:
    """Check if request is within rate limit."""
    try:
        from .utils import check_rate_limit as utils_check_rate_limit
        return await utils_check_rate_limit(redis_client, key, limit, window)
    except Exception as e:
        # Fail open - allow request if rate limiting fails
        logger = get_logger(__name__)
        logger.warning(f"Rate limit check failed: {e}")
        return True, 0


async def increment_rate_limit(
    redis_client,
    key: str,
    window: int
) -> None:
    """Increment rate limit counter."""
    try:
        from .utils import increment_rate_limit as utils_increment_rate_limit
        await utils_increment_rate_limit(redis_client, key, window)
    except Exception as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to increment rate limit: {e}")


# Audit logging helper
async def log_audit_event(
    db: AsyncSession,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Log audit event."""
    try:
        from .database import log_audit_event as db_log_audit_event
        await db_log_audit_event(
            db=db,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to log audit event: {e}")


async def get_user_accessible_wind_farms(
    db: AsyncSession,
    user_id: str
) -> List[str]:
    """Get list of wind farm IDs that user has access to."""
    try:
        from .database import WindFarmAccess, User, WindFarm

        # Get user
        user_result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            return []

        # Superusers have access to all wind farms
        if user.is_superuser:
            # Get all wind farm IDs
            wind_farms_result = await db.execute(select(WindFarm.id))
            return [str(wf_id) for wf_id in wind_farms_result.scalars().all()]

        # Get accessible wind farms for regular user
        access_result = await db.execute(
            select(WindFarmAccess.wind_farm_id).where(WindFarmAccess.user_id == user_id)
        )
        wind_farm_ids = [str(wf_id) for wf_id in access_result.scalars().all()]

        return wind_farm_ids

    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to get accessible wind farms for user {user_id}: {e}")
        return []


__all__ = [
    "authenticate_user",
    "get_current_user",
    "get_current_active_user",
    "get_admin_user",
    "get_user_by_id",
    "get_user_by_username",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "check_user_permission",
    "get_user_accessible_wind_farms",
    "require_wind_farm_access",
    "require_viewer_role",
    "require_analyst_role",
    "require_operator_role",
    "require_admin_role",
    "require_admin_user",
    "check_rate_limit",
    "increment_rate_limit",
    "log_audit_event",
    "oauth2_scheme"
]