"""
Router modules for Tenant Management Service.
"""

from .auth import router as auth_router
from .users import router as users_router
from .tenants import router as tenants_router
from .health import router as health_router

__all__ = ["auth_router", "users_router", "tenants_router", "health_router"]