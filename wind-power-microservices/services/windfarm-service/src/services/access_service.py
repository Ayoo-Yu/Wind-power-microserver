"""
Access Service - Manages user access to wind farms.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ..database import WindFarmAccess, User, wind_farm_access_crud, log_audit_event
from ..models import UserRole
from ..exceptions import AuthorizationException
from ..utils import get_logger


logger = get_logger(__name__)


class AccessService:
    """Service for managing wind farm access permissions."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def check_wind_farm_access(
        self,
        db: AsyncSession,
        user_id: str,
        wind_farm_id: str,
        required_role: str = "viewer"
    ) -> bool:
        """Check if user has access to wind farm with required role."""
        try:
            # Get user
            user_result = await db.execute(
                select(User).where(User.id == user_id, User.is_active == True)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                return False

            # Superusers have access to everything
            if user.is_superuser:
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
            self.logger.error(f"Failed to check wind farm access for user {user_id} and wind farm {wind_farm_id}: {e}")
            return False

    async def get_user_accessible_wind_farms(
        self,
        db: AsyncSession,
        user_id: str
    ) -> List[str]:
        """Get list of wind farm IDs that user has access to."""
        try:
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
                from ..database import WindFarm
                wind_farms_result = await db.execute(select(WindFarm.id))
                return [str(wf_id) for wf_id in wind_farms_result.scalars().all()]

            # Get accessible wind farms for regular user
            access_result = await db.execute(
                select(WindFarmAccess.wind_farm_id).where(WindFarmAccess.user_id == user_id)
            )
            wind_farm_ids = [str(wf_id) for wf_id in access_result.scalars().all()]

            return wind_farm_ids

        except Exception as e:
            self.logger.error(f"Failed to get accessible wind farms for user {user_id}: {e}")
            return []

    async def get_user_wind_farm_role(
        self,
        db: AsyncSession,
        user_id: str,
        wind_farm_id: str
    ) -> Optional[str]:
        """Get user's role for specific wind farm."""
        try:
            # Get user
            user_result = await db.execute(
                select(User).where(User.id == user_id, User.is_active == True)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                return None

            # Superusers have admin role for all wind farms
            if user.is_superuser:
                return "admin"

            # Get wind farm access
            access_result = await db.execute(
                select(WindFarmAccess).where(
                    WindFarmAccess.user_id == user_id,
                    WindFarmAccess.wind_farm_id == wind_farm_id
                )
            )
            access = access_result.scalar_one_or_none()

            return access.role if access else None

        except Exception as e:
            self.logger.error(f"Failed to get user role for wind farm {wind_farm_id}: {e}")
            return None

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
            from ..database import WindFarm

            # Check if user exists
            user_result = await db.execute(
                select(User).where(User.id == user_id, User.is_active == True)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                raise Exception(f"User {user_id} not found or inactive")

            # Check if wind farm exists
            wind_farm_result = await db.execute(
                select(WindFarm).where(WindFarm.id == wind_farm_id)
            )
            wind_farm = wind_farm_result.scalar_one_or_none()

            if not wind_farm:
                raise Exception(f"Wind farm {wind_farm_id} not found")

            # Validate role
            valid_roles = ["viewer", "analyst", "operator", "admin"]
            if role not in valid_roles:
                raise Exception(f"Invalid role: {role}")

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

        except Exception as e:
            self.logger.error(f"Failed to grant wind farm access: {e}")
            raise Exception(f"Failed to grant wind farm access: {str(e)}")

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
            user_result = await db.execute(
                select(User).where(User.id == user_id, User.is_active == True)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                raise Exception(f"User {user_id} not found or inactive")

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

        except Exception as e:
            self.logger.error(f"Failed to revoke wind farm access: {e}")
            raise Exception(f"Failed to revoke wind farm access: {str(e)}")

    async def update_wind_farm_access_role(
        self,
        db: AsyncSession,
        user_id: str,
        wind_farm_id: str,
        new_role: str,
        updated_by_user_id: str
    ) -> bool:
        """Update user's role for wind farm access."""
        try:
            # Find access
            access_result = await db.execute(
                select(WindFarmAccess).where(
                    WindFarmAccess.user_id == user_id,
                    WindFarmAccess.wind_farm_id == wind_farm_id
                )
            )
            access = access_result.scalar_one_or_none()

            if not access:
                raise Exception(f"Access not found for user {user_id} and wind farm {wind_farm_id}")

            # Validate new role
            valid_roles = ["viewer", "analyst", "operator", "admin"]
            if new_role not in valid_roles:
                raise Exception(f"Invalid role: {new_role}")

            # Update role
            access.role = new_role
            await db.commit()

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=updated_by_user_id,
                action="wind_farm_access.role_updated",
                resource_type="wind_farm_access",
                resource_id=f"{user_id}:{wind_farm_id}",
                details=f"Wind farm access role updated to {new_role}",
            )

            self.logger.info(f"Wind farm access role updated for user {user_id} and wind farm {wind_farm_id}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to update wind farm access role: {e}")
            raise Exception(f"Failed to update wind farm access role: {str(e)}")

    async def get_wind_farm_users(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        role: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all users who have access to a wind farm."""
        try:
            # Build query
            query = select(WindFarmAccess, User).join(
                User, WindFarmAccess.user_id == User.id
            ).where(WindFarmAccess.wind_farm_id == wind_farm_id)

            # Apply role filter
            if role:
                query = query.where(WindFarmAccess.role == role)

            # Execute query
            result = await db.execute(query)
            access_records = result.all()

            # Build response
            users = []
            for access, user in access_records:
                users.append({
                    "id": access.id,
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": access.role,
                    "granted_at": access.granted_at.isoformat(),
                    "granted_by": access.granted_by,
                })

            return users

        except Exception as e:
            self.logger.error(f"Failed to get wind farm users for {wind_farm_id}: {e}")
            raise Exception(f"Failed to get wind farm users: {str(e)}")

    async def cleanup_user_access(self, db: AsyncSession, user_id: str) -> bool:
        """Remove all wind farm access for a user (used when user is deactivated)."""
        try:
            # Find all access for user
            access_result = await db.execute(
                select(WindFarmAccess).where(WindFarmAccess.user_id == user_id)
            )
            accesses = access_result.scalars().all()

            # Delete all access
            for access in accesses:
                await db.delete(access)

            if accesses:
                await db.commit()
                self.logger.info(f"Removed {len(accesses)} wind farm access records for user {user_id}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to cleanup user access for user {user_id}: {e}")
            raise Exception(f"Failed to cleanup user access: {str(e)}")


__all__ = ["AccessService"]