"""
User and Authentication API endpoints.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session
from ..models import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    UserLoginResponse,
    UserFilter,
    PaginationParams,
    SuccessResponse,
    ErrorResponse
)
from ..services import UserService
from ..auth import get_current_user, create_access_token, create_refresh_token, get_current_active_user
from ..exceptions import (
    UserNotFoundException,
    DuplicateUserException,
    InvalidUserDataException,
    AuthenticationException,
    AuthorizationException,
    ValidationException
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Register a new user account",
    responses={
        201: {"description": "User registered successfully"},
        400: {"description": "Invalid user data", "model": ErrorResponse},
        409: {"description": "Username or email already exists", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """Register new user."""
    try:
        service = UserService()
        user = await service.create_user(db=db, user_data=user_data)
        return user

    except (ValidationException, InvalidUserDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateUserException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register user: {str(e)}")


@router.post(
    "/login",
    response_model=UserLoginResponse,
    summary="User login",
    description="Authenticate user and return access tokens",
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials", "model": ErrorResponse},
        400: {"description": "Invalid login data", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def login_user(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db_session)
):
    """User login."""
    try:
        service = UserService()
        user = await service.authenticate_user(
            db=db,
            username=login_data.username,
            password=login_data.password
        )

        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Create tokens
        access_token = create_access_token(data={"sub": user.username, "user_id": user.id})
        refresh_token = create_refresh_token(data={"sub": user.username})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user
        }

    except AuthenticationException as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.post(
    "/refresh",
    response_model=Dict[str, str],
    summary="Refresh access token",
    description="Refresh access token using refresh token",
    responses={
        200: {"description": "Token refreshed successfully"},
        401: {"description": "Invalid refresh token", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Refresh access token."""
    try:
        service = UserService()
        new_access_token = await service.refresh_access_token(
            db=db,
            refresh_token=refresh_token
        )

        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }

    except AuthenticationException as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get information about the currently authenticated user",
    responses={
        200: {"description": "User information retrieved successfully"},
        401: {"description": "Not authenticated", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_current_user_info(
    current_user = Depends(get_current_active_user)
):
    """Get current user information."""
    return current_user


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Get list of users",
    description="Retrieve paginated list of users with filtering (admin only)",
    responses={
        200: {"description": "Users retrieved successfully"},
        403: {"description": "Access denied - admin required", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_users(
    # Filter parameters
    username: Optional[str] = Query(None, description="Filter by username (case-insensitive partial match)"),
    email: Optional[str] = Query(None, description="Filter by email (case-insensitive partial match)"),
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_superuser: Optional[bool] = Query(None, description="Filter by superuser status"),

    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),

    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_active_user)
):
    """Get list of users (admin only)."""
    try:
        # Check if user is admin or superuser
        if not (current_user.role == "admin" or current_user.is_superuser):
            raise HTTPException(status_code=403, detail="Admin access required")

        service = UserService()

        # Build filter parameters
        filter_params = None
        if any([username, email, role, is_active is not None, is_superuser is not None]):
            filter_params = UserFilter(
                username=username,
                email=email,
                role=role,
                is_active=is_active,
                is_superuser=is_superuser
            )

        # Build pagination parameters
        pagination = PaginationParams(page=page, size=size)

        result = await service.get_users(
            db=db,
            filter_params=filter_params,
            pagination=pagination
        )

        return {
            "success": True,
            "message": "Users retrieved successfully",
            "data": result["items"],
            "pagination": {
                "total": result["total"],
                "page": result["page"],
                "size": result["size"],
                "pages": result["pages"],
                "has_next": result["has_next"],
                "has_prev": result["has_prev"]
            }
        }

    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get users: {str(e)}")


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    description="Get detailed information about a specific user (admin only)",
    responses={
        200: {"description": "User retrieved successfully"},
        404: {"description": "User not found", "model": ErrorResponse},
        403: {"description": "Access denied - admin required", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_user(
    user_id: str = Path(..., description="User ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_active_user)
):
    """Get user by ID (admin only or self)."""
    try:
        # Users can view their own profile, admins can view any profile
        if current_user.id != user_id and not (current_user.role == "admin" or current_user.is_superuser):
            raise HTTPException(status_code=403, detail="Access denied")

        service = UserService()
        user = await service.get_user(db=db, user_id=user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user: {str(e)}")


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    description="Update user information (admin only or self)",
    responses={
        200: {"description": "User updated successfully"},
        404: {"description": "User not found", "model": ErrorResponse},
        400: {"description": "Invalid user data", "model": ErrorResponse},
        409: {"description": "Username or email already exists", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def update_user(
    user_id: str = Path(..., description="User ID"),
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_active_user)
):
    """Update user information (admin only or self)."""
    try:
        # Users can update their own profile, admins can update any profile
        if current_user.id != user_id and not (current_user.role == "admin" or current_user.is_superuser):
            raise HTTPException(status_code=403, detail="Access denied")

        service = UserService()
        user = await service.update_user(
            db=db,
            user_id=user_id,
            user_data=user_data,
            updated_by_user_id=current_user.id
        )

        return user

    except UserNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationException, InvalidUserDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateUserException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")


@router.delete(
    "/{user_id}",
    response_model=SuccessResponse,
    summary="Delete user",
    description="Delete a user account (admin only)",
    responses={
        200: {"description": "User deleted successfully"},
        404: {"description": "User not found", "model": ErrorResponse},
        403: {"description": "Access denied - admin required", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def delete_user(
    user_id: str = Path(..., description="User ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_active_user)
):
    """Delete user (admin only)."""
    try:
        # Only admins can delete users
        if not (current_user.role == "admin" or current_user.is_superuser):
            raise HTTPException(status_code=403, detail="Admin access required")

        # Prevent self-deletion
        if current_user.id == user_id:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")

        service = UserService()
        success = await service.delete_user(
            db=db,
            user_id=user_id,
            deleted_by_user_id=current_user.id
        )

        return {
            "success": success,
            "message": f"User {user_id} deleted successfully"
        }

    except HTTPException:
        raise
    except UserNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")


@router.post(
    "/{user_id}/change-password",
    response_model=SuccessResponse,
    summary="Change user password",
    description="Change user password (self or admin)",
    responses={
        200: {"description": "Password changed successfully"},
        404: {"description": "User not found", "model": ErrorResponse},
        400: {"description": "Invalid password data", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def change_password(
    user_id: str = Path(..., description="User ID"),
    current_password: str = Query(..., description="Current password"),
    new_password: str = Query(..., description="New password"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_active_user)
):
    """Change user password."""
    try:
        # Users can change their own password, admins can change any password
        if current_user.id != user_id and not (current_user.role == "admin" or current_user.is_superuser):
            raise HTTPException(status_code=403, detail="Access denied")

        service = UserService()
        success = await service.change_password(
            db=db,
            user_id=user_id,
            current_password=current_password,
            new_password=new_password,
            changed_by_user_id=current_user.id
        )

        return {
            "success": success,
            "message": "Password changed successfully"
        }

    except HTTPException:
        raise
    except (ValidationException, InvalidUserDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UserNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthenticationException as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to change password: {str(e)}")


@router.post(
    "/{user_id}/reset-password",
    response_model=SuccessResponse,
    summary="Reset user password",
    description="Reset user password (admin only)",
    responses={
        200: {"description": "Password reset successfully"},
        404: {"description": "User not found", "model": ErrorResponse},
        403: {"description": "Access denied - admin required", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def reset_password(
    user_id: str = Path(..., description="User ID"),
    new_password: str = Query(..., description="New password"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_active_user)
):
    """Reset user password (admin only)."""
    try:
        # Only admins can reset passwords
        if not (current_user.role == "admin" or current_user.is_superuser):
            raise HTTPException(status_code=403, detail="Admin access required")

        service = UserService()
        success = await service.reset_password(
            db=db,
            user_id=user_id,
            new_password=new_password,
            reset_by_user_id=current_user.id
        )

        return {
            "success": success,
            "message": "Password reset successfully"
        }

    except UserNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValidationException, InvalidUserDataException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset password: {str(e)}")


@router.get(
    "/{user_id}/wind-farms",
    response_model=List[Dict[str, Any]],
    summary="Get user's wind farm access",
    description="Get list of wind farms the user has access to",
    responses={
        200: {"description": "Wind farm access retrieved successfully"},
        404: {"description": "User not found", "model": ErrorResponse},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_user_wind_farm_access(
    user_id: str = Path(..., description="User ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_active_user)
):
    """Get user's wind farm access."""
    try:
        # Users can view their own access, admins can view any access
        if current_user.id != user_id and not (current_user.role == "admin" or current_user.is_superuser):
            raise HTTPException(status_code=403, detail="Access denied")

        service = UserService()
        wind_farm_access = await service.get_user_wind_farm_access(
            db=db,
            user_id=user_id
        )

        return wind_farm_access

    except UserNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user wind farm access: {str(e)}")


@router.post(
    "/{user_id}/wind-farms/{wind_farm_id}/access",
    response_model=SuccessResponse,
    summary="Grant wind farm access",
    description="Grant user access to a specific wind farm (admin only)",
    responses={
        200: {"description": "Access granted successfully"},
        404: {"description": "User or wind farm not found", "model": ErrorResponse},
        409: {"description": "Access already exists", "model": ErrorResponse},
        403: {"description": "Access denied - admin required", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def grant_wind_farm_access(
    user_id: str = Path(..., description="User ID"),
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    role: str = Query("viewer", description="Access role (viewer, analyst, operator, admin)"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_active_user)
):
    """Grant wind farm access (admin only)."""
    try:
        # Only admins can grant access
        if not (current_user.role == "admin" or current_user.is_superuser):
            raise HTTPException(status_code=403, detail="Admin access required")

        service = UserService()
        success = await service.grant_wind_farm_access(
            db=db,
            user_id=user_id,
            wind_farm_id=wind_farm_id,
            role=role,
            granted_by_user_id=current_user.id
        )

        return {
            "success": success,
            "message": f"Wind farm access granted to user {user_id}"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to grant wind farm access: {str(e)}")


@router.delete(
    "/{user_id}/wind-farms/{wind_farm_id}/access",
    response_model=SuccessResponse,
    summary="Revoke wind farm access",
    description="Revoke user access to a specific wind farm (admin only)",
    responses={
        200: {"description": "Access revoked successfully"},
        404: {"description": "Access not found", "model": ErrorResponse},
        403: {"description": "Access denied - admin required", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def revoke_wind_farm_access(
    user_id: str = Path(..., description="User ID"),
    wind_farm_id: str = Path(..., description="Wind farm ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_active_user)
):
    """Revoke wind farm access (admin only)."""
    try:
        # Only admins can revoke access
        if not (current_user.role == "admin" or current_user.is_superuser):
            raise HTTPException(status_code=403, detail="Admin access required")

        service = UserService()
        success = await service.revoke_wind_farm_access(
            db=db,
            user_id=user_id,
            wind_farm_id=wind_farm_id,
            revoked_by_user_id=current_user.id
        )

        return {
            "success": success,
            "message": f"Wind farm access revoked from user {user_id}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to revoke wind farm access: {str(e)}")