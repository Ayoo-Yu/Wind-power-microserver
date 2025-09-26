"""
API routers for Meteorological Data Service
"""

from .weather_stations import router as weather_stations_router
from .weather_data import router as weather_data_router
from .forecasts import router as forecasts_router
from .alerts import router as alerts_router
from .monitoring import router as monitoring_router
from .health import router as health_router

__all__ = [
    "weather_stations_router",
    "weather_data_router",
    "forecasts_router",
    "alerts_router",
    "monitoring_router",
    "health_router"
]