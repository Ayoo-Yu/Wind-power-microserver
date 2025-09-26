"""
API routers for Wind Farm Management Service.
"""

from .wind_farms import router as wind_farms_router
from .turbines import router as turbines_router
from .users import router as users_router
from .health import router as health_router

__all__ = ["wind_farms_router", "turbines_router", "users_router", "health_router"]