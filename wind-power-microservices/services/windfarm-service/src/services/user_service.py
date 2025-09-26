"""
User Service - Core business logic for user management and authentication.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from ..database import User, user_crud, WindFarmAccess, wind_farm_access_crud, log_audit_event, WindFarm
from ..models import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserFilter,
    PaginationParams,
    UserRole
)
from ..exceptions import (
    ValidationException,
    UserNotFoundException,
    DuplicateUserException,
    InvalidUserDataException,
    AuthenticationException,
    AuthorizationException
)
from ..utils import get_logger, hash_password, verify_password, decode_jwt_token, create_jwt_token


logger = get_logger(__name__)


class UserService:
    """Service for managing users."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def create_user(self, db: AsyncSession, user_data: UserCreate) -> UserResponse:
        """Create a new user."""
        try:
            # Validate user data
            await self._validate_user_data(db, user_data)

            # Check for duplicate username
            existing_user = await self._get_user_by_username(db, user_data.username)
            if existing_user:
                raise DuplicateUserException(f"Username '{user_data.username}' already exists")

            # Check for duplicate email
            existing_user = await self._get_user_by_email(db, user_data.email)
            if existing_user:
                raise DuplicateUserException(f"Email '{user_data.email}' already exists")

            # Create user
            user_dict = user_data.dict()
            user_dict["hashed_password"] = hash_password(user_data.password)
            del user_dict["password"]

            user = await user_crud.create(db, user_data)

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=user.id,
                action="user.created",
                resource_type="user",
                resource_id=user.id,
                details=f"User {user.username} created successfully",
            )

            self.logger.info(f"User created successfully: {user.username}")

            return UserResponse.from_orm(user)

        except (ValidationException, DuplicateUserException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to create user: {e}")
            raise Exception("Failed to create user")

    async def get_user(self, db: AsyncSession, user_id: str) -> Optional[UserResponse]:
        """Get user by ID."""
        try:
            user = await user_crud.get(db, user_id)
            if not user:
                return None

            return UserResponse.from_orm(user)

        except Exception as e:
            self.logger.error(f"Failed to get user {user_id}: {e}")
            raise Exception("Failed to get user")

    async def get_users(
        self,
        db: AsyncSession,
        filter_params: Optional[UserFilter] = None,
        pagination: Optional[PaginationParams] = None
    ) -> Dict[str, Any]:
        """Get list of users with filtering and pagination."""
        try:
            # Build query
            query = select(User)

            # Apply filters
            if filter_params:
                query = self._apply_filters(query, filter_params)

            # Get total count
            count_query = select(func.count(User.id))
            if filter_params:
                count_query = self._apply_filters(count_query, filter_params)

            total_result = await db.execute(count_query)
            total = total_result.scalar()

            # Apply pagination
            if pagination:
                query = query.offset((pagination.page - 1) * pagination.size).limit(pagination.size)

            # Execute query
            result = await db.execute(query)
            users = result.scalars().all()

            # Convert to response models
            items = [UserResponse.from_orm(user) for user in users]

            # Calculate pagination info
            pages = (total + pagination.size - 1) // pagination.size if pagination else 1
            has_next = pagination.page < pages if pagination else False
            has_prev = pagination.page > 1 if pagination else False

            return {
                "items": items,
                "total": total,
                "page": pagination.page if pagination else 1,
                "size": pagination.size if pagination else total,
                "pages": pages,
                "has_next": has_next,
                "has_prev": has_prev,
            }

        except Exception as e:
            self.logger.error(f"Failed to get users: {e}")
            raise Exception("Failed to get users")

    async def update_user(
        self,
        db: AsyncSession,
        user_id: str,
        user_data: UserUpdate,
        updated_by_user_id: str
    ) -> UserResponse:
        """Update user information."""
        try:
            # Get user
            user = await user_crud.get(db, user_id)
            if not user:
                raise UserNotFoundException(user_id)

            # Validate update data
            if user_data.username and user_data.username != user.username:
                # Check for duplicate username
                existing_user = await self._get_user_by_username(db, user_data.username)
                if existing_user and existing_user.id != user_id:
                    raise DuplicateUserException(f"Username '{user_data.username}' already exists")

            if user_data.email and user_data.email != user.email:
                # Check for duplicate email
                existing_user = await self._get_user_by_email(db, user_data.email)
                if existing_user and existing_user.id != user_id:
                    raise DuplicateUserException(f"Email '{user_data.email}' already exists")

            # Update user
            updated_user = await user_crud.update(db, user, user_data)

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=updated_by_user_id,
                action="user.updated",
                resource_type="user",
                resource_id=user_id,
                details=f"User {user.username} updated",
            )

            self.logger.info(f"User updated successfully: {updated_user.username}")

            return UserResponse.from_orm(updated_user)

        except (UserNotFoundException, DuplicateUserException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to update user {user_id}: {e}")
            raise Exception("Failed to update user")

    async def delete_user(
        self,
        db: AsyncSession,
        user_id: str,
        deleted_by_user_id: str
    ) -> bool:
        """Delete user (soft delete by setting is_active to False)."""
        try:
            # Get user
            user = await user_crud.get(db, user_id)
            if not user:
                raise UserNotFoundException(user_id)

            # Prevent deletion of superusers by non-superusers
            if user.is_superuser:
                deleter = await user_crud.get(db, deleted_by_user_id)
                if not deleter.is_superuser:
                    raise AuthorizationException("Only superusers can delete superuser accounts")

            # Soft delete: set is_active to False
            user.is_active = False
            await db.commit()

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=deleted_by_user_id,
                action="user.deactivated",
                resource_type="user",
                resource_id=user_id,
                details=f"User {user.username} deactivated",
            )

            self.logger.info(f"User deactivated: {user.username}")

            return True

        except (UserNotFoundException, AuthorizationException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to delete user {user_id}: {e}")
            raise Exception("Failed to delete user")

    async def authenticate_user(
        self,
        db: AsyncSession,
        username: str,
        password: str
    ) -> Optional[User]:
        """Authenticate user with username and password."""
        try:
            # Get user by username
            user = await self._get_user_by_username(db, username)
            if not user:
                return None

            # Check if user is active
            if not user.is_active:
                raise AuthenticationException("User account is inactive")

            # Verify password
            if not verify_password(password, user.hashed_password):
                return None

            # Update last login timestamp (if we had such a field)
            # user.last_login = datetime.utcnow()
            # await db.commit()

            return user

        except AuthenticationException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to authenticate user {username}: {e}")
            raise AuthenticationException("Authentication failed")

    async def refresh_access_token(
        self,
        db: AsyncSession,
        refresh_token: str
    ) -> str:
        """Refresh access token using refresh token."""
        try:
            # Decode and validate refresh token
            payload = decode_jwt_token(refresh_token)

            # Check if it's a refresh token
            if payload.get("type") != "refresh":
                raise AuthenticationException("Invalid token type")

            # Get user ID from token
            user_id = payload.get("sub")
            if not user_id:
                raise AuthenticationException("Invalid token payload")

            # Get user from database
            user = await user_crud.get(db, user_id)
            if not user:
                raise AuthenticationException("User not found")

            # Check if user is active
            if not user.is_active:
                raise AuthenticationException("User account is inactive")

            # Create new access token
            access_token = create_jwt_token(
                user_id=user.id,
                role=user.role,
                expires_delta=timedelta(minutes=30)
            )

            return access_token

        except AuthenticationException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to refresh access token: {e}")
            raise AuthenticationException("Token refresh failed")

    async def change_password(
        self,
        db: AsyncSession,
        user_id: str,
        current_password: str,
        new_password: str,
        changed_by_user_id: str
    ) -> bool:
        """Change user password."""
        try:
            # Get user
            user = await user_crud.get(db, user_id)
            if not user:
                raise UserNotFoundException(user_id)

            # If changing own password, verify current password
            if user_id == changed_by_user_id:
                if not verify_password(current_password, user.hashed_password):
                    raise AuthenticationException("Current password is incorrect")

            # Validate new password
            if len(new_password) < 8:
                raise InvalidUserDataException("Password must be at least 8 characters long")

            # Update password
            user.hashed_password = hash_password(new_password)
            await db.commit()

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=changed_by_user_id,
                action="user.password_changed",
                resource_type="user",
                resource_id=user_id,
                details=f"Password changed for user {user.username}",
            )

            self.logger.info(f"Password changed for user: {user.username}")

            return True

        except (UserNotFoundException, AuthenticationException, InvalidUserDataException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to change password for user {user_id}: {e}")
            raise Exception("Failed to change password")

    async def reset_password(
        self,
        db: AsyncSession,
        user_id: str,
        new_password: str,
        reset_by_user_id: str
    ) -> bool:
        """Reset user password (admin function)."""
        try:
            # Get user
            user = await user_crud.get(db, user_id)
            if not user:
                raise UserNotFoundException(user_id)

            # Validate new password
            if len(new_password) < 8:
                raise InvalidUserDataException("Password must be at least 8 characters long")

            # Update password
            user.hashed_password = hash_password(new_password)
            await db.commit()

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=reset_by_user_id,
                action="user.password_reset",
                resource_type="user",
                resource_id=user_id,
                details=f"Password reset for user {user.username}",
            )

            self.logger.info(f"Password reset for user: {user.username}")

            return True

        except (UserNotFoundException, InvalidUserDataException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to reset password for user {user_id}: {e}")
            raise Exception("Failed to reset password")

    async def get_user_wind_farm_access(
        self,
        db: AsyncSession,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """Get user's wind farm access list."""
        try:
            # Get user
            user = await user_crud.get(db, user_id)
            if not user:
                raise UserNotFoundException(user_id)

            # Get wind farm access
            query = select(WindFarmAccess).where(WindFarmAccess.user_id == user_id)
            result = await db.execute(query)
            accesses = result.scalars().all()

            # Build response with wind farm details
            access_list = []
            for access in accesses:
                # Get wind farm details
                wind_farm_result = await db.execute(
                    select(WindFarm).where(WindFarm.id == access.wind_farm_id)
                )
                wind_farm = wind_farm_result.scalar_one_or_none()

                access_list.append({
                    "id": access.id,
                    "wind_farm_id": access.wind_farm_id,
                    "wind_farm": {
                        "id": wind_farm.id if wind_farm else None,
                        "code": wind_farm.code if wind_farm else None,
                        "name": wind_farm.name if wind_farm else None,
                    },
                    "role": access.role,
                    "granted_at": access.granted_at.isoformat(),
                })

            return access_list

        except UserNotFoundException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to get user wind farm access for {user_id}: {e}")
            raise Exception("Failed to get user wind farm access")

    async def grant_wind_farm_access(
        self,
        db: AsyncSession,
        user_id: str,
        wind_farm_id: str,
        role: str,
        granted_by_user_id: str
    ) -> bool:
        """Grant wind farm access to user."""
        try:
            # Check if user exists
            user = await user_crud.get(db, user_id)
            if not user:
                raise UserNotFoundException(user_id)

            # Check if wind farm exists
            wind_farm_result = await db.execute(
                select(WindFarm).where(WindFarm.id == wind_farm_id)
            )
            wind_farm = wind_farm_result.scalar_one_or_none()

            if not wind_farm:
                raise Exception(f"Wind farm {wind_farm_id} not found")

            # Check if access already exists
            existing_access = await db.execute(
                select(WindFarmAccess).where(
                    WindFarmAccess.user_id == user_id,
                    WindFarmAccess.wind_farm_id == wind_farm_id
                )
            )
            if existing_access.scalar_one_or_none():
                raise Exception(f"Access already exists for user {user_id} and wind farm {wind_farm_id}")

            # Create access
            access_data = {
                "user_id": user_id,
                "wind_farm_id": wind_farm_id,
                "role": role,
                "granted_by": granted_by_user_id,
                "granted_at": datetime.utcnow()
            }

            await wind_farm_access_crud.create(db, access_data)

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=granted_by_user_id,
                action="wind_farm_access.granted",
                resource_type="wind_farm_access",
                resource_id=f"{user_id}:{wind_farm_id}",
                details=f"User {user.username} granted {role} access to wind farm {wind_farm.name}",
            )

            self.logger.info(f"Wind farm access granted to user {user.username} for wind farm {wind_farm.name}")

            return True

        except (UserNotFoundException, Exception):
            raise
        except Exception as e:
            self.logger.error(f"Failed to grant wind farm access: {e}")
            raise Exception("Failed to grant wind farm access")

    async def revoke_wind_farm_access(
        self,
        db: AsyncSession,
        user_id: str,
        wind_farm_id: str,
        revoked_by_user_id: str
    ) -> bool:
        """Revoke wind farm access from user."""
        try:
            # Check if user exists
            user = await user_crud.get(db, user_id)
            if not user:
                raise UserNotFoundException(user_id)

            # Find and delete access
            access_result = await db.execute(
                select(WindFarmAccess).where(
                    WindFarmAccess.user_id == user_id,
                    WindFarmAccess.wind_farm_id == wind_farm_id
                )
            )
            access = access_result.scalar_one_or_none()

            if not access:
                raise Exception(f"Access not found for user {user_id} and wind farm {wind_farm_id}")

            # Delete access
            await db.delete(access)
            await db.commit()

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=revoked_by_user_id,
                action="wind_farm_access.revoked",
                resource_type="wind_farm_access",
                resource_id=f"{user_id}:{wind_farm_id}",
                details=f"Wind farm access revoked from user {user.username}",
            )

            self.logger.info(f"Wind farm access revoked from user {user.username}")

            return True

        except UserNotFoundException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to revoke wind farm access: {e}")
            raise Exception("Failed to revoke wind farm access")

    # Private helper methods

    async def _validate_user_data(self, db: AsyncSession, user_data: UserCreate) -> None:
        """Validate user data."""
        # Validate username format
        if not user_data.username.replace('_', '').replace('-', '').isalnum():
            raise InvalidUserDataException("Username must be alphanumeric with underscores and hyphens only")

        # Validate email format (already handled by EmailStr)

        # Validate password strength
        if len(user_data.password) < 8:
            raise InvalidUserDataException("Password must be at least 8 characters long")

        # Check for common weak passwords
        weak_passwords = ["password", "12345678", "qwerty123", "admin123"]
        if user_data.password.lower() in weak_passwords:
            raise InvalidUserDataException("Password is too weak")

    async def _get_user_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        """Get user by username."""
        result = await db.execute(
            select(User).where(User.username == username.lower())
        )
        return result.scalar_one_or_none()

    async def _get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email."""
        result = await db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    def _apply_filters(self, query, filter_params: UserFilter):
        """Apply filters to query."""
        if filter_params.username:
            query = query.where(User.username.ilike(f"%{filter_params.username}%"))

        if filter_params.email:
            query = query.where(User.email.ilike(f"%{filter_params.email}%"))

        if filter_params.role:
            query = query.where(User.role == filter_params.role)

        if filter_params.is_active is not None:
            query = query.where(User.is_active == filter_params.is_active)

        if filter_params.is_superuser is not None:
            query = query.where(User.is_superuser == filter_params.is_superuser)

        return query


# Add missing exception classes
class UserNotFoundException(Exception):
    """Exception for user not found."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User {user_id} not found")


class DuplicateUserException(Exception):
    """Exception for duplicate user."""

    def __init__(self, message: str):
        super().__init__(message)


class InvalidUserDataException(Exception):
    """Exception for invalid user data."""

    def __init__(self, message: str):
        super().__init__(message)