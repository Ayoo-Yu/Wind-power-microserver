"""
Authentication service for Tenant Management Service.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext

from ..database import User, UserSession, user_crud, user_session_crud
from ..exceptions import (
    DuplicateUserException,
    InvalidCredentialsException,
    UserNotFoundException,
    TokenExpiredException,
)
from ..utils import get_logger, create_jwt_token, decode_jwt_token
from ..config import get_settings


logger = get_logger(__name__)
settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Authentication service for user management."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain_password, hashed_password)

    def hash_password(self, password: str) -> str:
        """Hash password."""
        return pwd_context.hash(password)

    async def create_user(self, db: AsyncSession, user_data) -> User:
        """Create new user."""
        try:
            # Check if username or email already exists
            existing_user = await self._get_user_by_username_or_email(
                db, user_data.username, user_data.email
            )
            if existing_user:
                raise DuplicateUserException(user_data.username, user_data.email)

            # Hash password
            hashed_password = self.hash_password(user_data.password)

            # Create user
            user_dict = user_data.dict(exclude={"password"})
            user_dict["hashed_password"] = hashed_password
            user_dict["is_active"] = True
            user_dict["is_superuser"] = False

            user = await user_crud.create(db, user_dict)

            self.logger.info(f"User created successfully: {user.username}")
            return user

        except DuplicateUserException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to create user: {e}")
            raise Exception("Failed to create user")

    async def authenticate_user(self, db: AsyncSession, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password."""
        try:
            # Get user by username
            user = await self._get_user_by_username(db, username)
            if not user:
                return None

            # Verify password
            if not self.verify_password(password, user.hashed_password):
                return None

            return user

        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return None

    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """Get user by ID."""
        try:
            return await user_crud.get(db, user_id)
        except Exception as e:
            self.logger.error(f"Failed to get user by ID {user_id}: {e}")
            return None

    async def store_refresh_token(self, db: AsyncSession, user_id: str, refresh_token: str) -> None:
        """Store refresh token in database."""
        try:
            # Decode token to get expiration
            payload = decode_jwt_token(refresh_token)
            expires_at = datetime.fromtimestamp(payload["exp"])

            # Create user session
            session_data = {
                "user_id": user_id,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "is_active": True,
            }

            await user_session_crud.create(db, session_data)
            self.logger.info(f"Refresh token stored for user {user_id}")

        except Exception as e:
            self.logger.error(f"Failed to store refresh token: {e}")
            raise Exception("Failed to store refresh token")

    async def validate_refresh_token(self, db: AsyncSession, user_id: str, refresh_token: str) -> bool:
        """Validate refresh token."""
        try:
            # Check if session exists and is active
            result = await db.execute(
                select(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.refresh_token == refresh_token,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow()
                )
            )
            session = result.scalar_one_or_none()
            return session is not None

        except Exception as e:
            self.logger.error(f"Failed to validate refresh token: {e}")
            return False

    async def invalidate_refresh_token(self, db: AsyncSession, user_id: str) -> None:
        """Invalidate all refresh tokens for user."""
        try:
            # Deactivate all sessions for user
            await db.execute(
                select(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True
                )
            )

            result = await db.execute(
                select(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True
                )
            )
            sessions = result.scalars().all()

            for session in sessions:
                session.is_active = False

            await db.commit()
            self.logger.info(f"Refresh tokens invalidated for user {user_id}")

        except Exception as e:
            self.logger.error(f"Failed to invalidate refresh tokens: {e}")
            raise Exception("Failed to invalidate refresh tokens")

    async def cleanup_expired_sessions(self, db: AsyncSession) -> int:
        """Clean up expired sessions. Returns number of cleaned sessions."""
        try:
            result = await db.execute(
                select(UserSession).where(
                    UserSession.expires_at < datetime.utcnow(),
                    UserSession.is_active == True
                )
            )
            expired_sessions = result.scalars().all()

            count = 0
            for session in expired_sessions:
                session.is_active = False
                count += 1

            await db.commit()
            self.logger.info(f"Cleaned up {count} expired sessions")
            return count

        except Exception as e:
            self.logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0

    async def _get_user_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        """Get user by username."""
        try:
            result = await db.execute(
                select(User).where(User.username == username)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            self.logger.error(f"Failed to get user by username {username}: {e}")
            return None

    async def _get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email."""
        try:
            result = await db.execute(
                select(User).where(User.email == email)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            self.logger.error(f"Failed to get user by email {email}: {e}")
            return None

    async def _get_user_by_username_or_email(self, db: AsyncSession, username: str, email: str) -> Optional[User]:
        """Get user by username or email."""
        try:
            result = await db.execute(
                select(User).where(
                    (User.username == username) | (User.email == email)
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            self.logger.error(f"Failed to get user by username or email: {e}")
            return None

    async def change_password(
        self, db: AsyncSession, user_id: str, current_password: str, new_password: str
    ) -> bool:
        """Change user password."""
        try:
            # Get user
            user = await self.get_user_by_id(db, user_id)
            if not user:
                raise UserNotFoundException(user_id)

            # Verify current password
            if not self.verify_password(current_password, user.hashed_password):
                raise InvalidCredentialsException()

            # Hash new password
            new_hashed_password = self.hash_password(new_password)

            # Update password
            user.hashed_password = new_hashed_password
            await db.commit()

            self.logger.info(f"Password changed successfully for user {user_id}")
            return True

        except (UserNotFoundException, InvalidCredentialsException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to change password for user {user_id}: {e}")
            raise Exception("Failed to change password")

    async def reset_password(self, db: AsyncSession, user_id: str, new_password: str) -> bool:
        """Reset user password (admin function)."""
        try:
            # Get user
            user = await self.get_user_by_id(db, user_id)
            if not user:
                raise UserNotFoundException(user_id)

            # Hash new password
            new_hashed_password = self.hash_password(new_password)

            # Update password
            user.hashed_password = new_hashed_password
            await db.commit()

            self.logger.info(f"Password reset successfully for user {user_id}")
            return True

        except UserNotFoundException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to reset password for user {user_id}: {e}")
            raise Exception("Failed to reset password")

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = decode_jwt_token(token)
            return payload
        except Exception as e:
            self.logger.error(f"Token verification failed: {e}")
            raise TokenExpiredException() if "expired" in str(e).lower() else Exception("Invalid token")