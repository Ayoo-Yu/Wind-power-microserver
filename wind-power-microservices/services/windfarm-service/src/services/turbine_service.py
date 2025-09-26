"""
Wind Turbine Service - Core business logic for wind turbine management.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from ..database import WindTurbine, turbine_crud, WindFarm, wind_farm_crud, log_audit_event
from ..models import (
    WindTurbineCreate,
    WindTurbineUpdate,
    WindTurbineResponse,
    WindTurbineFilter,
    PaginationParams,
    TurbineStatus
)
from ..exceptions import (
    ValidationException,
    TurbineNotFoundException,
    DuplicateTurbineException,
    InvalidTurbineDataException,
    WindFarmNotFoundException,
    AuthorizationException
)
from ..auth import check_user_permission
from ..utils import get_logger, calculate_distance, format_coordinates


logger = get_logger(__name__)


class TurbineService:
    """Service for managing wind turbines."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def create_turbine(
        self,
        db: AsyncSession,
        turbine_data: WindTurbineCreate,
        current_user_id: str
    ) -> WindTurbineResponse:
        """Create a new wind turbine."""
        try:
            # Validate turbine data
            await self._validate_turbine_data(db, turbine_data)

            # Check wind farm exists and user has access
            wind_farm = await wind_farm_crud.get(db, turbine_data.wind_farm_id)
            if not wind_farm:
                raise WindFarmNotFoundException(turbine_data.wind_farm_id)

            # Check user access to wind farm
            has_access = await check_user_permission(
                db, current_user_id, turbine_data.wind_farm_id, "operator"
            )
            if not has_access:
                raise AuthorizationException(
                    f"User {current_user_id} does not have operator access to wind farm {turbine_data.wind_farm_id}"
                )

            # Check for duplicate turbine ID within wind farm
            existing_turbine = await self._get_turbine_by_turbine_id(
                db, turbine_data.wind_farm_id, turbine_data.turbine_id
            )
            if existing_turbine:
                raise DuplicateTurbineException(turbine_data.wind_farm_id, turbine_data.turbine_id)

            # Create turbine
            turbine = await turbine_crud.create(db, turbine_data)

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=current_user_id,
                action="turbine.created",
                resource_type="turbine",
                resource_id=turbine.id,
                details=f"Wind turbine {turbine.turbine_id} created in wind farm {wind_farm.name}",
            )

            self.logger.info(f"Wind turbine created successfully: {turbine.turbine_id} in wind farm {wind_farm.name}")

            return WindTurbineResponse.from_orm(turbine)

        except (ValidationException, DuplicateTurbineException, WindFarmNotFoundException, AuthorizationException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to create turbine: {e}")
            raise Exception("Failed to create wind turbine")

    async def get_turbine(
        self,
        db: AsyncSession,
        turbine_id: str,
        current_user_id: str
    ) -> WindTurbineResponse:
        """Get wind turbine by ID."""
        try:
            turbine = await turbine_crud.get(db, turbine_id)
            if not turbine:
                raise TurbineNotFoundException(turbine_id)

            # Check user access to wind farm
            has_access = await check_user_permission(
                db, current_user_id, turbine.wind_farm_id, "viewer"
            )
            if not has_access:
                raise AuthorizationException(
                    f"User {current_user_id} does not have viewer access to wind farm {turbine.wind_farm_id}"
                )

            # Get real-time data
            real_time_data = await self._get_turbine_real_time_data(turbine_id)

            # Create response with real-time data
            turbine_dict = turbine.to_dict()
            if real_time_data:
                turbine_dict.update({
                    "current_power": real_time_data.get("current_power"),
                    "wind_speed": real_time_data.get("wind_speed"),
                    "rotor_speed": real_time_data.get("rotor_speed"),
                    "availability": real_time_data.get("availability"),
                })

            return WindTurbineResponse(**turbine_dict)

        except TurbineNotFoundException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to get turbine {turbine_id}: {e}")
            raise Exception("Failed to get wind turbine")

    async def get_turbines(
        self,
        db: AsyncSession,
        current_user_id: str,
        filter_params: Optional[WindTurbineFilter] = None,
        pagination: Optional[PaginationParams] = None
    ) -> Dict[str, Any]:
        """Get list of wind turbines with filtering and pagination."""
        try:
            from ..auth import get_user_accessible_wind_farms

            # Get accessible wind farms for user
            accessible_wind_farm_ids = await get_user_accessible_wind_farms(
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
            query = select(WindTurbine).where(WindTurbine.wind_farm_id.in_(accessible_wind_farm_ids))

            # Apply filters
            if filter_params:
                query = self._apply_filters(query, filter_params)

            # Get total count
            count_query = select(func.count(WindTurbine.id)).where(WindTurbine.wind_farm_id.in_(accessible_wind_farm_ids))
            if filter_params:
                count_query = self._apply_filters(count_query, filter_params)

            total_result = await db.execute(count_query)
            total = total_result.scalar()

            # Apply pagination
            if pagination:
                query = query.offset((pagination.page - 1) * pagination.size).limit(pagination.size)

            # Execute query
            result = await db.execute(query)
            turbines = result.scalars().all()

            # Convert to response models with real-time data
            items = []
            for turbine in turbines:
                real_time_data = await self._get_turbine_real_time_data(turbine.id)
                turbine_dict = turbine.to_dict()
                if real_time_data:
                    turbine_dict.update({
                        "current_power": real_time_data.get("current_power"),
                        "wind_speed": real_time_data.get("wind_speed"),
                        "rotor_speed": real_time_data.get("rotor_speed"),
                        "availability": real_time_data.get("availability"),
                    })
                items.append(WindTurbineResponse(**turbine_dict))

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
            self.logger.error(f"Failed to get turbines: {e}")
            raise Exception("Failed to get wind turbines")

    async def update_turbine(
        self,
        db: AsyncSession,
        turbine_id: str,
        turbine_data: WindTurbineUpdate,
        current_user_id: str
    ) -> WindTurbineResponse:
        """Update wind turbine information."""
        try:
            # Get turbine
            turbine = await turbine_crud.get(db, turbine_id)
            if not turbine:
                raise TurbineNotFoundException(turbine_id)

            # Check user access to wind farm
            has_access = await check_user_permission(
                db, current_user_id, turbine.wind_farm_id, "operator"
            )
            if not has_access:
                raise AuthorizationException(
                    f"User {current_user_id} does not have operator access to wind farm {turbine.wind_farm_id}"
                )

            # Validate update data
            if turbine_data.turbine_id and turbine_data.turbine_id != turbine.turbine_id:
                # Check for duplicate turbine ID within wind farm
                existing_turbine = await self._get_turbine_by_turbine_id(
                    db, turbine.wind_farm_id, turbine_data.turbine_id
                )
                if existing_turbine and existing_turbine.id != turbine_id:
                    raise DuplicateTurbineException(turbine.wind_farm_id, turbine_data.turbine_id)

            # Update turbine
            updated_turbine = await turbine_crud.update(db, turbine, turbine_data)

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=current_user_id,
                action="turbine.updated",
                resource_type="turbine",
                resource_id=turbine_id,
                details=f"Wind turbine {turbine.turbine_id} updated",
            )

            self.logger.info(f"Wind turbine updated successfully: {updated_turbine.turbine_id}")

            return WindTurbineResponse.from_orm(updated_turbine)

        except (TurbineNotFoundException, AuthorizationException, DuplicateTurbineException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to update turbine {turbine_id}: {e}")
            raise Exception("Failed to update wind turbine")

    async def delete_turbine(
        self,
        db: AsyncSession,
        turbine_id: str,
        current_user_id: str
    ) -> bool:
        """Delete wind turbine."""
        try:
            # Get turbine
            turbine = await turbine_crud.get(db, turbine_id)
            if not turbine:
                raise TurbineNotFoundException(turbine_id)

            # Check user access to wind farm
            has_access = await check_user_permission(
                db, current_user_id, turbine.wind_farm_id, "operator"
            )
            if not has_access:
                raise AuthorizationException(
                    f"User {current_user_id} does not have operator access to wind farm {turbine.wind_farm_id}"
                )

            # Delete turbine
            await turbine_crud.delete(db, turbine_id)

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=current_user_id,
                action="turbine.deleted",
                resource_type="turbine",
                resource_id=turbine_id,
                details=f"Wind turbine {turbine.turbine_id} deleted",
            )

            self.logger.info(f"Wind turbine deleted: {turbine.turbine_id}")

            return True

        except (TurbineNotFoundException, AuthorizationException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to delete turbine {turbine_id}: {e}")
            raise Exception("Failed to delete wind turbine")

    async def get_turbines_by_wind_farm(
        self,
        db: AsyncSession,
        wind_farm_id: str,
        current_user_id: str,
        status_filter: Optional[str] = None
    ) -> List[WindTurbineResponse]:
        """Get turbines by wind farm."""
        try:
            # Check user access to wind farm
            from .access_service import AccessService
            access_service = AccessService()
            has_access = await access_service.check_wind_farm_access(
                db, current_user_id, wind_farm_id, "viewer"
            )
            if not has_access:
                raise AuthorizationException(
                    f"User {current_user_id} does not have viewer access to wind farm {wind_farm_id}"
                )

            # Build query
            query = select(WindTurbine).where(WindTurbine.wind_farm_id == wind_farm_id)

            # Apply status filter
            if status_filter:
                query = query.where(WindTurbine.status == status_filter)

            # Execute query
            result = await db.execute(query)
            turbines = result.scalars().all()

            # Convert to response models with real-time data
            items = []
            for turbine in turbines:
                real_time_data = await self._get_turbine_real_time_data(turbine.id)
                turbine_dict = turbine.to_dict()
                if real_time_data:
                    turbine_dict.update({
                        "current_power": real_time_data.get("current_power"),
                        "wind_speed": real_time_data.get("wind_speed"),
                        "rotor_speed": real_time_data.get("rotor_speed"),
                        "availability": real_time_data.get("availability"),
                    })
                items.append(WindTurbineResponse(**turbine_dict))

            return items

        except AuthorizationException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to get turbines by wind farm {wind_farm_id}: {e}")
            raise Exception("Failed to get turbines by wind farm")

    async def get_turbine_statistics(
        self,
        db: AsyncSession,
        turbine_id: str,
        current_user_id: str
    ) -> Dict[str, Any]:
        """Get comprehensive statistics for a wind turbine."""
        try:
            # Get turbine
            turbine = await turbine_crud.get(db, turbine_id)
            if not turbine:
                raise TurbineNotFoundException(turbine_id)

            # Check user access to wind farm
            has_access = await check_user_permission(
                db, current_user_id, turbine.wind_farm_id, "viewer"
            )
            if not has_access:
                raise AuthorizationException(
                    f"User {current_user_id} does not have viewer access to wind farm {turbine.wind_farm_id}"
                )

            # Get real-time data
            real_time_data = await self._get_turbine_real_time_data(turbine_id)

            # Get performance metrics (simplified - would integrate with SCADA data service)
            performance_metrics = await self._get_turbine_performance_metrics(turbine_id)

            return {
                "turbine_id": turbine_id,
                "basic_info": {
                    "turbine_id": turbine.turbine_id,
                    "manufacturer": turbine.manufacturer,
                    "model": turbine.model,
                    "rated_power": turbine.rated_power,
                    "rotor_diameter": turbine.rotor_diameter,
                    "hub_height": turbine.hub_height,
                    "coordinates": format_coordinates(turbine.latitude, turbine.longitude),
                    "commissioning_date": turbine.commissioning_date.isoformat() if turbine.commissioning_date else None,
                    "status": turbine.status,
                },
                "real_time_data": real_time_data or {
                    "current_power": 0,
                    "wind_speed": 0,
                    "rotor_speed": 0,
                    "availability": 0,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "performance_metrics": performance_metrics or {
                    "energy_today": 0,
                    "energy_this_month": 0,
                    "energy_this_year": 0,
                    "capacity_factor": 0,
                    "availability_rate": 0,
                },
                "last_updated": datetime.utcnow().isoformat(),
            }

        except (TurbineNotFoundException, AuthorizationException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to get turbine statistics for {turbine_id}: {e}")
            raise Exception("Failed to get turbine statistics")

    async def control_turbine(
        self,
        db: AsyncSession,
        turbine_id: str,
        action: str,
        current_user_id: str
    ) -> bool:
        """Control wind turbine (start, stop, reset)."""
        try:
            # Get turbine
            turbine = await turbine_crud.get(db, turbine_id)
            if not turbine:
                raise TurbineNotFoundException(turbine_id)

            # Check user access to wind farm
            has_access = await check_user_permission(
                db, current_user_id, turbine.wind_farm_id, "operator"
            )
            if not has_access:
                raise AuthorizationException(
                    f"User {current_user_id} does not have operator access to wind farm {turbine.wind_farm_id}"
                )

            # Validate action
            valid_actions = ["start", "stop", "reset"]
            if action not in valid_actions:
                raise InvalidTurbineDataException(f"Invalid control action: {action}")

            # Update turbine status based on action
            status_map = {
                "start": TurbineStatus.RUNNING,
                "stop": TurbineStatus.STOPPED,
                "reset": TurbineStatus.RUNNING
            }

            new_status = status_map[action]
            update_data = WindTurbineUpdate(status=new_status)
            await turbine_crud.update(db, turbine, update_data)

            # Log audit event
            await log_audit_event(
                db=db,
                user_id=current_user_id,
                action=f"turbine.{action}",
                resource_type="turbine",
                resource_id=turbine_id,
                details=f"Wind turbine {turbine.turbine_id} {action} executed",
            )

            self.logger.info(f"Wind turbine control action executed: {turbine.turbine_id} - {action}")

            return True

        except (TurbineNotFoundException, AuthorizationException, InvalidTurbineDataException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to control turbine {turbine_id}: {e}")
            raise Exception("Failed to control wind turbine")

    async def get_nearby_turbines(
        self,
        db: AsyncSession,
        latitude: float,
        longitude: float,
        radius_km: float,
        limit: int,
        current_user_id: str
    ) -> List[WindTurbineResponse]:
        """Get turbines within radius of given coordinates."""
        try:
            from ..auth import get_user_accessible_wind_farms

            # Get accessible wind farms for user
            accessible_wind_farm_ids = await get_user_accessible_wind_farms(
                db, current_user_id
            )

            if not accessible_wind_farm_ids:
                return []

            # Get all turbines in accessible wind farms
            query = select(WindTurbine).where(WindTurbine.wind_farm_id.in_(accessible_wind_farm_ids))
            result = await db.execute(query)
            turbines = result.scalars().all()

            # Filter by distance
            nearby_turbines = []
            for turbine in turbines:
                distance = calculate_distance(latitude, longitude, turbine.latitude, turbine.longitude)
                if distance <= radius_km:
                    real_time_data = await self._get_turbine_real_time_data(turbine.id)
                    turbine_dict = turbine.to_dict()
                    if real_time_data:
                        turbine_dict.update({
                            "current_power": real_time_data.get("current_power"),
                            "wind_speed": real_time_data.get("wind_speed"),
                            "rotor_speed": real_time_data.get("rotor_speed"),
                            "availability": real_time_data.get("availability"),
                        })
                    turbine_dict["distance_km"] = round(distance, 2)
                    nearby_turbines.append(WindTurbineResponse(**turbine_dict))

            # Sort by distance and limit results
            nearby_turbines.sort(key=lambda x: x.distance_km)
            return nearby_turbines[:limit]

        except Exception as e:
            self.logger.error(f"Failed to get nearby turbines: {e}")
            raise Exception("Failed to get nearby turbines")

    # Private helper methods

    async def _validate_turbine_data(self, db: AsyncSession, turbine_data: WindTurbineCreate) -> None:
        """Validate turbine data."""
        # Validate coordinates
        if not (-90 <= turbine_data.latitude <= 90):
            raise InvalidTurbineDataException("Latitude must be between -90 and 90 degrees")

        if not (-180 <= turbine_data.longitude <= 180):
            raise InvalidTurbineDataException("Longitude must be between -180 and 180 degrees")

        # Validate power and dimensions
        if turbine_data.rated_power <= 0:
            raise InvalidTurbineDataException("Rated power must be greater than 0")

        if turbine_data.rotor_diameter <= 0:
            raise InvalidTurbineDataException("Rotor diameter must be greater than 0")

        if turbine_data.hub_height <= 0:
            raise InvalidTurbineDataException("Hub height must be greater than 0")

        # Validate reasonable ranges
        if turbine_data.rated_power > 20:
            raise InvalidTurbineDataException("Rated power seems too high (>20 MW)")

        if turbine_data.rotor_diameter > 200:
            raise InvalidTurbineDataException("Rotor diameter seems too large (>200m)")

        if turbine_data.hub_height > 200:
            raise InvalidTurbineDataException("Hub height seems too high (>200m)")

    async def _get_turbine_by_turbine_id(self, db: AsyncSession, wind_farm_id: str, turbine_id: str) -> Optional[WindTurbine]:
        """Get turbine by turbine ID within wind farm."""
        result = await db.execute(
            select(WindTurbine).where(
                WindTurbine.wind_farm_id == wind_farm_id,
                WindTurbine.turbine_id == turbine_id.upper()
            )
        )
        return result.scalar_one_or_none()

    def _apply_filters(self, query, filter_params: WindTurbineFilter):
        """Apply filters to query."""
        if filter_params.wind_farm_id:
            query = query.where(WindTurbine.wind_farm_id == filter_params.wind_farm_id)

        if filter_params.turbine_id:
            query = query.where(WindTurbine.turbine_id.ilike(f"%{filter_params.turbine_id}%"))

        if filter_params.manufacturer:
            query = query.where(WindTurbine.manufacturer.ilike(f"%{filter_params.manufacturer}%"))

        if filter_params.model:
            query = query.where(WindTurbine.model.ilike(f"%{filter_params.model}%"))

        if filter_params.status:
            query = query.where(WindTurbine.status == filter_params.status)

        if filter_params.min_power:
            query = query.where(WindTurbine.rated_power >= filter_params.min_power)

        if filter_params.max_power:
            query = query.where(WindTurbine.rated_power <= filter_params.max_power)

        return query

    async def _get_turbine_real_time_data(self, turbine_id: str) -> Optional[Dict[str, Any]]:
        """Get real-time data for turbine (placeholder - would integrate with SCADA service)."""
        # This is a placeholder - would integrate with SCADA data service
        # For now, return mock data
        return {
            "current_power": 2.5,  # MW
            "wind_speed": 8.5,     # m/s
            "rotor_speed": 15.2,   # RPM
            "availability": 98.5,  # %
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _get_turbine_performance_metrics(self, turbine_id: str) -> Optional[Dict[str, Any]]:
        """Get performance metrics for turbine (placeholder - would integrate with SCADA service)."""
        # This is a placeholder - would integrate with SCADA data service
        # For now, return mock data
        return {
            "energy_today": 45.2,      # MWh
            "energy_this_month": 1024.8,  # MWh
            "energy_this_year": 8760.0,   # MWh
            "capacity_factor": 35.2,   # %
            "availability_rate": 97.8, # %
        }