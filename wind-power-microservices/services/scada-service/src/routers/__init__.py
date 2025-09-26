"""
API routers for SCADA Data Service.
"""

from .connections import router as connections_router
from .data_points import router as data_points_router
from .realtime_data import router as realtime_data_router
from .alarms import router as alarms_router
from .monitoring import router as monitoring_router
from .health import router as health_router

__all__ = [
    "connections_router",
    "data_points_router",
    "realtime_data_router",
    "alarms_router",
    "monitoring_router",
    "health_router"
]