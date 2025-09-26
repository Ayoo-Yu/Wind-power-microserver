"""
API routers for Power Prediction Service
"""

from .predictions import router as predictions_router
from .models import router as models_router
from .training import router as training_router
from .evaluation import router as evaluation_router
from .monitoring import router as monitoring_router
from .health import router as health_router

__all__ = [
    "predictions_router",
    "models_router",
    "training_router",
    "evaluation_router",
    "monitoring_router",
    "health_router"
]