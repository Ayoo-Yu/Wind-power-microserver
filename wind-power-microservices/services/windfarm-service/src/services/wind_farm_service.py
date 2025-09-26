"""
Wind Farm Service - Core business logic for wind farm management.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from ..database import WindFarm, wind_farm_crud, WindTurbine, turbine_crud, log_audit_event
from ..models import (
    WindFarmCreate,
    WindFarmUpdate,
    WindFarmResponse,
    WindFarmFilter,
    PaginationParams,
    WindFarmStatus
)
from ..exceptions import (
    ValidationException,
    WindFarmNotFoundException,
    DuplicateWindFarmException,
    InvalidWindFarmDataException,
    AuthorizationException,
    WindFarmAccessDeniedException
)
from ..utils import get_logger, get_wind_farm_statistics, format_coordinates


logger = get_logger(__name__)


class WindFarmService:
    """Service for managing wind farms."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def create_wind_farm(
        self,
        db: AsyncSession,
        wind_farm_data: WindFarmCreate,
        current_user_id: str
    ) -> WindFarmResponse:
        """Create a new wind farm."""
        try:
            # Validate wind farm data
            await self._validate_wind_farm_data(db, wind_farm_data)

            # Check for duplicate code
            existing_wind_farm = await self._get_wind_farm_by_code(db, wind_farm_data.code)
            if existing_wind_farm:
                raise DuplicateWindFarmException(wind_farm_data.code)

            # Create wind farm
            wind_farm_dict = wind_farm_data.dict()
            wind_farm_dict["status"] = WindFarmStatus.ACTIVE

            wind_farm = await wind_farm_crud.create(db, wind_farm_data)

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=current_user_id,
                action="wind_farm.created",
                resource_type="wind_farm",
                resource_id=wind_farm.id,
                details=f"Wind farm {wind_farm.name} (code: {wind_farm.code}) created successfully",
            )

            self.logger.info(f"Wind farm created successfully: {wind_farm.name} (code: {wind_farm.code})")

            return WindFarmResponse.from_orm(wind_farm)

        except (ValidationException, DuplicateWindFarmException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to create wind farm: {e}")
            raise Exception("Failed to create wind farm")

    async def get_wind_farm(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        current_user_id: str
    ) -> WindFarmResponse:
        """Get wind farm by ID."""
        try:
            wind_farm = await wind_farm_crud.get(db, wind_farm_id)
            if not wind_farm:
                raise WindFarmNotFoundException(wind_farm_id)

            # Check user access
            from .access_service import AccessService
            access_service = AccessService()
            has_access = await access_service.check_wind_farm_access(
                db, current_user_id, wind_farm_id, "viewer"
            )
            if not has_access:
                raise WindFarmAccessDeniedException(wind_farm_id, current_user_id)

            # Get additional statistics
            stats = await get_wind_farm_statistics(db, wind_farm_id)

            # Create response with statistics
            wind_farm_dict = wind_farm.to_dict()
            wind_farm_dict.update({
                "current_power": stats.get("current_power"),
                "running_turbines": stats.get("running_turbines"),
            })

            return WindFarmResponse(**wind_farm_dict)

        except WindFarmNotFoundException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to get wind farm {wind_farm_id}: {e}")
            raise Exception("Failed to get wind farm")

    async def get_wind_farms(
        self,
        db: AsyncSession,
        current_user_id: str,
        filter_params: Optional[WindFarmFilter] = None,
        pagination: Optional[PaginationParams] = None
    ) -> Dict[str, Any]:
        """Get list of wind farms with filtering and pagination."""
        try:
            from .access_service import AccessService
            access_service = AccessService()

            # Get accessible wind farms for user
            accessible_wind_farm_ids = await access_service.get_user_accessible_wind_farms(
                db, current_user_id
            )

            if not accessible_wind_farm_ids:
                return {
                    "items": [],
                    "total": 0,
                    "page": pagination.page if pagination else 1,
                    "size": pagination.size if pagination else 20,
                    "pages": 0,
                    "has_next": False,
                    "has_prev": False,
                }

            # Build query
            query = select(WindFarm).where(WindFarm.id.in_(accessible_wind_farm_ids))

            # Apply filters
            if filter_params:
                query = self._apply_filters(query, filter_params)

            # Get total count
            count_query = select(func.count(WindFarm.id)).where(WindFarm.id.in_(accessible_wind_farm_ids))
            if filter_params:
                count_query = self._apply_filters(count_query, filter_params)

            total_result = await db.execute(count_query)
            total = total_result.scalar()

            # Apply pagination
            if pagination:
                query = query.offset((pagination.page - 1) * pagination.size).limit(pagination.size)

            # Execute query
            result = await db.execute(query)
            wind_farms = result.scalars().all()

            # Convert to response models with statistics
            items = []
            for wind_farm in wind_farms:
                stats = await get_wind_farm_statistics(db, wind_farm.id)
                wind_farm_dict = wind_farm.to_dict()
                wind_farm_dict.update({
                    "current_power": stats.get("current_power"),
                    "running_turbines": stats.get("running_turbines"),
                })
                items.append(WindFarmResponse(**wind_farm_dict))

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
            self.logger.error(f"Failed to get wind farms: {e}")
            raise Exception("Failed to get wind farms")

    async def update_wind_farm(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        wind_farm_data: WindFarmUpdate,
        current_user_id: str
    ) -> WindFarmResponse:
        """Update wind farm information."""
        try:
            # Get wind farm
            wind_farm = await wind_farm_crud.get(db, wind_farm_id)
            if not wind_farm:
                raise WindFarmNotFoundException(wind_farm_id)

            # Check user access
            from .access_service import AccessService
            access_service = AccessService()
            has_access = await access_service.check_wind_farm_access(
                db, current_user_id, wind_farm_id, "operator"
            )
            if not has_access:
                raise WindFarmAccessDeniedException(wind_farm_id, current_user_id)

            # Validate update data
            if wind_farm_data.code and wind_farm_data.code != wind_farm.code:
                # Check for duplicate code
                existing_wind_farm = await self._get_wind_farm_by_code(db, wind_farm_data.code)
                if existing_wind_farm and existing_wind_farm.id != wind_farm_id:
                    raise DuplicateWindFarmException(wind_farm_data.code)

            # Update wind farm
            updated_wind_farm = await wind_farm_crud.update(db, wind_farm, wind_farm_data)

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=current_user_id,
                action="wind_farm.updated",
                resource_type="wind_farm",
                resource_id=wind_farm_id,
                details=f"Wind farm {wind_farm.name} updated",
            )

            self.logger.info(f"Wind farm updated successfully: {updated_wind_farm.name}")

            return WindFarmResponse.from_orm(updated_wind_farm)

        except (WindFarmNotFoundException, WindFarmAccessDeniedException, DuplicateWindFarmException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to update wind farm {wind_farm_id}: {e}")
            raise Exception("Failed to update wind farm")

    async def delete_wind_farm(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        current_user_id: str
    ) -> bool:
        """Delete wind farm (soft delete by setting status to inactive)."""
        try:
            # Get wind farm
            wind_farm = await wind_farm_crud.get(db, wind_farm_id)
            if not wind_farm:
                raise WindFarmNotFoundException(wind_farm_id)

            # Check user access
            from .access_service import AccessService
            access_service = AccessService()
            has_access = await access_service.check_wind_farm_access(
                db, current_user_id, wind_farm_id, "admin"
            )
            if not has_access:
                raise WindFarmAccessDeniedException(wind_farm_id, current_user_id)

            # Check if wind farm has turbines
            turbine_count_result = await db.execute(
                select(func.count(WindTurbine.id)).where(WindTurbine.wind_farm_id == wind_farm_id)
            )
            turbine_count = turbine_count_result.scalar()

            if turbine_count > 0:
                # Soft delete: set status to inactive
                wind_farm.status = "inactive"
                await db.commit()

                await log_audit_event(
                    db=db,
                    user_id=current_user_id,
                    action="wind_farm.deactivated",
                    resource_type="wind_farm",
                    resource_id=wind_farm_id,
                    details=f"Wind farm {wind_farm.name} deactivated (has {turbine_count} turbines)",
                )

                self.logger.info(f"Wind farm deactivated: {wind_farm.name}")
            else:
                # Hard delete if no turbines
                await wind_farm_crud.delete(db, wind_farm_id)

                await log_audit_event(
                    db=db,
                    user_id=current_user_id,
                    action="wind_farm.deleted",
                    resource_type="wind_farm",
                    resource_id=wind_farm_id,
                    details=f"Wind farm {wind_farm.name} deleted",
                )

                self.logger.info(f"Wind farm deleted: {wind_farm.name}")

            return True

        except (WindFarmNotFoundException, WindFarmAccessDeniedException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to delete wind farm {wind_farm_id}: {e}")
            raise Exception("Failed to delete wind farm")

    async def get_wind_farm_statistics(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        current_user_id: str
    ) -> Dict[str, Any]:
        """Get comprehensive statistics for a wind farm."""
        try:
            # Check user access
            from .access_service import AccessService
            access_service = AccessService()
            has_access = await access_service.check_wind_farm_access(
                db, current_user_id, wind_farm_id, "viewer"
            )
            if not has_access:
                raise WindFarmAccessDeniedException(wind_farm_id, current_user_id)

            # Get wind farm
            wind_farm = await wind_farm_crud.get(db, wind_farm_id)
            if not wind_farm:
                raise WindFarmNotFoundException(wind_farm_id)

            # Get basic statistics
            basic_stats = await get_wind_farm_statistics(db, wind_farm_id)

            # Get turbine statistics
            turbine_stats_result = await db.execute(
                select(
                    func.count(WindTurbine.id),
                    func.count().filter(WindTurbine.status == "running"),
                    func.avg(WindTurbine.rated_power),
                    func.sum(WindTurbine.rated_power)
                ).where(WindTurbine.wind_farm_id == wind_farm_id)
            )
            total_turbines, running_turbines, avg_power, total_capacity = turbine_stats_result.first()

            # Calculate additional metrics
            capacity_factor = (total_capacity / wind_farm.total_capacity * 100) if wind_farm.total_capacity > 0 else 0
            availability_rate = (running_turbines / total_turbines * 100) if total_turbines > 0 else 0

            return {
                "wind_farm_id": wind_farm_id,
                "basic_info": {
                    "code": wind_farm.code,
                    "name": wind_farm.name,
                    "location": wind_farm.location,
                    "coordinates": format_coordinates(wind_farm.latitude, wind_farm.longitude),
                    "total_capacity": wind_farm.total_capacity,
                    "commissioning_date": wind_farm.commissioning_date.isoformat() if wind_farm.commissioning_date else None,
                    "status": wind_farm.status,
                },
                "turbine_statistics": {
                    "total_turbines": total_turbines,
                    "running_turbines": running_turbines,
                    "avg_rated_power": avg_power,
                    "total_rated_capacity": total_capacity,
                    "capacity_factor": capacity_factor,
                    "availability_rate": availability_rate,
                },
                "operational_metrics": {
                    "current_power": basic_stats.get("current_power"),
                    "running_turbines": basic_stats.get("running_turbines"),
                    "last_updated": datetime.utcnow().isoformat(),
                }
            }

        except (WindFarmNotFoundException, WindFarmAccessDeniedException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to get wind farm statistics for {wind_farm_id}: {e}")
            raise Exception("Failed to get wind farm statistics")

    # Private helper methods

    async def _validate_wind_farm_data(self, db: AsyncSession, wind_farm_data: WindFarmCreate) -> None:
        """Validate wind farm data."""
        # Validate coordinates
        if not (-90 <= wind_farm_data.latitude <= 90):
            raise InvalidWindFarmDataException("Latitude must be between -90 and 90 degrees")

        if not (-180 <= wind_farm_data.longitude <= 180):
            raise InvalidWindFarmDataException("Longitude must be between -180 and 180 degrees")

        # Validate capacity and turbine count
        if wind_farm_data.total_capacity <= 0:
            raise InvalidWindFarmDataException("Total capacity must be greater than 0")

        if wind_farm_data.turbine_count <= 0:
            raise InvalidWindFarmDataException("Turbine count must be greater than 0")

        # Validate capacity consistency (rough estimate: 1.5-6 MW per turbine)
        avg_capacity_per_turbine = wind_farm_data.total_capacity / wind_farm_data.turbine_count
        if avg_capacity_per_turbine < 0.5 or avg_capacity_per_turbine > 10:
            raise InvalidWindFarmDataException(
                f"Average capacity per turbine ({avg_capacity_per_turbine:.2f} MW) seems unreasonable"
            )

    async def _get_wind_farm_by_code(self, db: AsyncSession, code: str) -> Optional[WindFarm]:
        """Get wind farm by code."""
        result = await db.execute(
            select(WindFarm).where(WindFarm.code == code.upper())
        )
        return result.scalar_one_or_none()

    def _apply_filters(self, query, filter_params: WindFarmFilter):
        """Apply filters to query."""
        if filter_params.name:
            query = query.where(WindFarm.name.ilike(f"%{filter_params.name}%"))

        if filter_params.code:
            query = query.where(WindFarm.code.ilike(f"%{filter_params.code}%"))

        if filter_params.location:
            query = query.where(WindFarm.location.ilike(f"%{filter_params.location}%"))

        if filter_params.status:
            query = query.where(WindFarm.status == filter_params.status)

        if filter_params.min_capacity:
            query = query.where(WindFarm.total_capacity >= filter_params.min_capacity)

        if filter_params.max_capacity:
            query = query.where(WindFarm.total_capacity <= filter_params.max_capacity)

        return query

    async def get_wind_farm_by_code(self, db: AsyncSession, code: str) -> Optional[WindFarmResponse]:
        """Get wind farm by code."""
        wind_farm = await self._get_wind_farm_by_code(db, code)
        if not wind_farm:
            return None

        return WindFarmResponse.from_orm(wind_farm)

    async def get_wind_farms_by_status(
        self,
        db: AsyncSession,
        status: str,
        current_user_id: str
    ) -> List[WindFarmResponse]:
        """Get wind farms by status."""
        try:
            from .access_service import AccessService
            access_service = AccessService()

            # Get accessible wind farms for user
            accessible_wind_farm_ids = await access_service.get_user_accessible_wind_farms(
                db, current_user_id
            )

            if not accessible_wind_farm_ids:
                return []

            # Query wind farms by status
            result = await db.execute(
                select(WindFarm).where(
                    and_(
                        WindFarm.id.in_(accessible_wind_farm_ids),
                        WindFarm.status == status
                    )
                )
            )
            wind_farms = result.scalars().all()

            return [WindFarmResponse.from_orm(wf) for wf in wind_farms]

        except Exception as e:
            self.logger.error(f"Failed to get wind farms by status {status}: {e}")
            raise Exception("Failed to get wind farms by status")

    async def search_wind_farms(
        self,
        db: AsyncSession,
        query: str,
        current_user_id: str,
        limit: int = 10
    ) -> List[WindFarmResponse]:
        """Search wind farms by name, code, or location."""
        try:
            from .access_service import AccessService
            access_service = AccessService()

            # Get accessible wind farms for user
            accessible_wind_farm_ids = await access_service.get_user_accessible_wind_farms(
                db, current_user_id
            )

            if not accessible_wind_farm_ids:
                return []

            # Search query
            search_query = select(WindFarm).where(
                and_(
                    WindFarm.id.in_(accessible_wind_farm_ids),
                    or_(
                        WindFarm.name.ilike(f"%{query}%"),
                        WindFarm.code.ilike(f"%{query}%"),
                        WindFarm.location.ilike(f"%{query}%")
                    )
                )
            ).limit(limit)

            result = await db.execute(search_query)
            wind_farms = result.scalars().all()

            return [WindFarmResponse.from_orm(wf) for wf in wind_farms]

        except Exception as e:
            self.logger.error(f"Failed to search wind farms with query '{query}': {e}")
            raise Exception("Failed to search wind farms")