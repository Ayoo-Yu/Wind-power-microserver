"""
Report Service routers
"""

from .reports import router as reports_router
from .charts import router as charts_router
from .templates import router as templates_router
from .monitoring import router as monitoring_router
from .health import router as health_router

__all__ = [
    "reports_router",
    "charts_router",
    "templates_router",
    "monitoring_router",
    "health_router"
]