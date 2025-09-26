"""
Router modules for API Gateway.
"""

from .proxy import router as proxy_router
from .health import router as health_router
from .admin import router as admin_router

__all__ = ["proxy_router", "health_router", "admin_router"]