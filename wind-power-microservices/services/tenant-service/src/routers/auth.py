"""
Authentication endpoints for Tenant Management Service.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from ..database import get_db_session
from ..config import get_settings
from ..utils import (
    get_logger,
    create_jwt_token,
    create_refresh_token,
    decode_jwt_token,
    validate_password_strength,
)
from ..exceptions import (
    ValidationException,
    AuthenticationException,
    AuthorizationException,
    UserNotFoundException,
    InvalidCredentialsException,
    TokenExpiredException,
    InvalidTokenException,
)
from ..models import UserCreate, UserResponse, TokenResponse, RefreshTokenRequest
from ..services import AuthService
from ..database import log_audit_event


router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


@router.post("/register", response_model=Dict[str, Any])
async def register_user(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(),
):
    """
    Register a new user.

    This endpoint creates a new user account. The user will be associated with
    the tenant specified in the request.
    """
    try:
        # Validate password strength
        is_valid, password_message = validate_password_strength(user_data.password)
        if not is_valid:
            raise ValidationException(password_message)

        # Create user
        user = await auth_service.create_user(db, user_data)

        # Log audit event
        await log_audit_event(
            db=db,
            user_id=user.id,
            tenant_id=user.tenant_id,
            action="user.registered",
            resource_type="user",
            resource_id=user.id,
            details=f"User {user.username} registered successfully",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        logger.info(f"User registered successfully: {user.username}")

        return {
            "success": True,
            "message": "User registered successfully",
            "data": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "tenant_id": user.tenant_id,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except ValidationException as e:
        raise e
    except Exception as e:
        logger.error(f"User registration failed: {e}")
        raise HTTPException(status_code=500, detail="User registration failed")


@router.post("/login", response_model=TokenResponse)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(),
):
    """
    Login user and return access tokens.

    This endpoint authenticates a user and returns JWT access and refresh tokens.
    """
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(db, form_data.username, form_data.password)
        if not user:
            raise InvalidCredentialsException()

        if not user.is_active:
            raise AuthenticationException("User account is disabled")

        # Create tokens
        access_token = create_jwt_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
        )

        refresh_token = create_refresh_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
        )

        # Store refresh token in database
        await auth_service.store_refresh_token(db, user.id, refresh_token)

        # Log audit event
        await log_audit_event(
            db=db,
            user_id=user.id,
            tenant_id=user.tenant_id,
            action="user.login",
            resource_type="user",
            resource_id=user.id,
            details=f"User {user.username} logged in successfully",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        logger.info(f"User logged in successfully: {user.username}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_expiration_minutes * 60,
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
        )

    except (InvalidCredentialsException, AuthenticationException) as e:
        raise e
    except Exception as e:
        logger.error(f"User login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(),
):
    """
    Refresh access token using refresh token.

    This endpoint validates a refresh token and returns a new access token.
    """
    try:
        # Validate refresh token
        payload = decode_jwt_token(refresh_request.refresh_token)

        if payload.get("type") != "refresh":
            raise InvalidTokenException()

        user_id = payload.get("user_id")
        tenant_id = payload.get("tenant_id")

        if not user_id or not tenant_id:
            raise InvalidTokenException()

        # Verify refresh token exists in database
        is_valid = await auth_service.validate_refresh_token(db, user_id, refresh_request.refresh_token)
        if not is_valid:
            raise InvalidTokenException()

        # Get user details
        user = await auth_service.get_user_by_id(db, user_id)
        if not user or not user.is_active:
            raise InvalidTokenException()

        # Create new access token
        access_token = create_jwt_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
        )

        logger.info(f"Token refreshed successfully for user: {user.username}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_request.refresh_token,  # Return same refresh token
            token_type="bearer",
            expires_in=settings.jwt_expiration_minutes * 60,
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
        )

    except (InvalidTokenException, TokenExpiredException) as e:
        raise e
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(status_code=500, detail="Token refresh failed")


@router.post("/logout")
async def logout_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(),
    current_user: dict = Depends(get_current_user),
):
    """
    Logout user and invalidate refresh token.

    This endpoint logs out the authenticated user and invalidates their refresh token.
    """
    try:
        # Invalidate refresh token
        await auth_service.invalidate_refresh_token(db, current_user["user_id"])

        # Log audit event
        await log_audit_event(
            db=db,
            user_id=current_user["user_id"],
            tenant_id=current_user["tenant_id"],
            action="user.logout",
            resource_type="user",
            resource_id=current_user["user_id"],
            details=f"User logged out successfully",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        logger.info(f"User logged out successfully: {current_user['user_id']}")

        return {
            "success": True,
            "message": "User logged out successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"User logout failed: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(),
):
    """
    Get current user information.

    This endpoint returns detailed information about the authenticated user.
    """
    try:
        user = await auth_service.get_user_by_id(db, current_user["user_id"])
        if not user:
            raise UserNotFoundException(current_user["user_id"])

        return {
            "success": True,
            "data": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "tenant_id": user.tenant_id,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat(),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except UserNotFoundException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user information")


# Authentication dependency
async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Get current authenticated user from JWT token."""
    try:
        payload = decode_jwt_token(token)
        return {
            "user_id": payload["user_id"],
            "tenant_id": payload["tenant_id"],
            "role": payload["role"],
        }
    except Exception as e:
        logger.error(f"Failed to decode token: {e}")
        raise AuthenticationException("Invalid authentication credentials")


# Admin-only dependency
async def get_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current user and verify admin role."""
    if current_user["role"] != "admin":
        raise AuthorizationException("Admin privileges required")
    return current_user


# Tenant admin dependency
async def get_tenant_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current user and verify tenant admin role."""
    if current_user["role"] not in ["admin", "operator"]:
        raise AuthorizationException("Tenant admin privileges required")
    return current_user


# Import dependencies
from sqlalchemy.ext.asyncio import AsyncSession

# Import models
from ..models import UserCreate, UserResponse, TokenResponse, RefreshTokenRequest