"""
Authentication and authorization for Meteorological Data Service
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .database import get_db_session
from .models import UserRole
from .exceptions import DatabaseConnectionException
from .utils import get_logger

logger = get_logger(__name__)

# Security configuration
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Import settings
from .config import get_settings

settings = get_settings()


class User:
    """User model for authentication."""

    def __init__(
        self,
        id: str,
        username: str,
        email: str,
        role: UserRole,
        is_active: bool = True,
        wind_farm_ids: Optional[List[str]] = None
    ):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.is_active = is_active
        self.wind_farm_ids = wind_farm_ids or []

    def has_permission(self, required_role: UserRole) -> bool:
        """Check if user has required role."""
        role_hierarchy = {
            UserRole.VIEWER: 1,
            UserRole.OPERATOR: 2,
            UserRole.MANAGER: 3,
            UserRole.ADMIN: 4
        }
        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(required_role, 0)

    def has_wind_farm_access(self, wind_farm_id: str) -> bool:
        """Check if user has access to specific wind farm."""
        if self.role == UserRole.ADMIN:
            return True
        return wind_farm_id in self.wind_farm_ids


class AuthService:
    """Authentication service."""

    def __init__(self):
        self.pwd_context = pwd_context

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Generate password hash."""
        return self.pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            return payload
        except JWTError:
            return None


# Global auth service instance
auth_service = AuthService()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """Get user by ID from database."""
    try:
        # This would typically query the database
        # For now, return a mock user (simplified implementation)
        if user_id == "admin":
            return User(
                id="admin",
                username="admin",
                email="admin@windpower.com",
                role=UserRole.ADMIN,
                is_active=True
            )
        return None

    except Exception as e:
        logger.error(f"Error getting user by ID: {e}")
        raise DatabaseConnectionException(f"Database error: {str(e)}")


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get user by username from database."""
    try:
        # This would typically query the database
        # For now, return a mock user (simplified implementation)
        if username == "admin":
            return User(
                id="admin",
                username="admin",
                email="admin@windpower.com",
                role=UserRole.ADMIN,
                is_active=True
            )
        return None

    except Exception as e:
        logger.error(f"Error getting user by username: {e}")
        raise DatabaseConnectionException(f"Database error: {str(e)}")


async def authenticate_user(username: str, password: str, db: AsyncSession) -> Optional[User]:
    """Authenticate user with username and password."""
    try:
        user = await get_user_by_username(db, username)
        if not user:
            return None

        # In a real implementation, you would verify the password hash
        # For now, accept any password for the admin user
        if username == "admin" and password == "admin":
            return user

        return None

    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = auth_service.verify_token(token)

        if payload is None:
            raise credentials_exception

        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        user = await get_user_by_id(db, user_id)
        if user is None:
            raise credentials_exception

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise credentials_exception


class RoleChecker:
    """Role-based access control."""

    def __init__(self, required_role: UserRole):
        self.required_role = required_role

    async def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        """Check if user has required role."""
        if not current_user.has_permission(self.required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {self.required_role}"
            )
        return current_user


class WindFarmAccessChecker:
    """Wind farm access control."""

    def __init__(self, wind_farm_id_param: str = "wind_farm_id"):
        self.wind_farm_id_param = wind_farm_id_param

    async def __call__(
        self,
        wind_farm_id: str,
        current_user: User = Depends(get_current_user)
    ) -> User:
        """Check if user has access to specific wind farm."""
        if not current_user.has_wind_farm_access(wind_farm_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to wind farm {wind_farm_id}"
            )
        return current_user


# Role-based dependencies
require_admin = RoleChecker(UserRole.ADMIN)
require_manager = RoleChecker(UserRole.MANAGER)
require_operator = RoleChecker(UserRole.OPERATOR)
require_viewer = RoleChecker(UserRole.VIEWER)

# Permission decorators (for function-based endpoints)
def require_role(required_role: UserRole):
    """Decorator for role-based access control."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would need to be adapted based on how the function is called
            # In a real implementation, you'd integrate with FastAPI's dependency system
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_wind_farm_access(wind_farm_id_param: str = "wind_farm_id"):
    """Decorator for wind farm access control."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would need to be adapted based on how the function is called
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Utility functions
def create_user_access_token(user: User) -> str:
    """Create access token for user."""
    token_data = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "wind_farm_ids": user.wind_farm_ids
    }
    return auth_service.create_access_token(token_data)


def get_user_permissions(user: User) -> Dict[str, Any]:
    """Get user permissions and accessible resources."""
    return {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "permissions": {
            "can_view": user.has_permission(UserRole.VIEWER),
            "can_operate": user.has_permission(UserRole.OPERATOR),
            "can_manage": user.has_permission(UserRole.MANAGER),
            "can_admin": user.has_permission(UserRole.ADMIN),
        },
        "wind_farm_access": user.wind_farm_ids,
        "is_admin": user.role == UserRole.ADMIN
    }


# Authentication endpoints would be defined in the main application
# This is just the utility module for authentication functionality