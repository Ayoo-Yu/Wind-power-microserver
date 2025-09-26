"""
Power Prediction Service - Main Application
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime

from .config import get_settings
from .database import db_manager
from .prediction_service import prediction_service
from .routers import (
    predictions_router,
    models_router,
    training_router,
    evaluation_router,
    monitoring_router,
    health_router
)
from .exceptions import (
    PowerPredictionException,
    ModelNotFoundException,
    PredictionException,
    TrainingDataException,
    ValidationException,
    DatabaseConnectionException
)
from .utils import get_logger

# Initialize logger
logger = get_logger(__name__)

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Power Prediction Service...")

    try:
        # Initialize database
        await db_manager.initialize()
        logger.info("Database initialized successfully")

        # Initialize prediction service
        await prediction_service.initialize()
        logger.info("Prediction service initialized successfully")

        logger.info("Power Prediction Service started successfully")

    except Exception as e:
        logger.error(f"Failed to start Power Prediction Service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Power Prediction Service...")

    try:
        # Shutdown prediction service
        await prediction_service.shutdown()
        logger.info("Prediction service shutdown completed")

        # Shutdown database
        await db_manager.shutdown()
        logger.info("Database shutdown completed")

        logger.info("Power Prediction Service shutdown completed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Power Prediction Service for Wind Power Forecasting System - Machine learning-based power prediction",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# Exception handlers
@app.exception_handler(PowerPredictionException)
async def power_prediction_exception_handler(request: Request, exc: PowerPredictionException):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": str(exc),
            "error_code": exc.error_code,
            "details": exc.details
        }
    )

@app.exception_handler(ModelNotFoundException)
async def model_not_found_handler(request: Request, exc: ModelNotFoundException):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": str(exc),
            "error_code": exc.error_code,
            "details": exc.details
        }
    )

@app.exception_handler(PredictionException)
async def prediction_exception_handler(request: Request, exc: PredictionException):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": str(exc),
            "error_code": exc.error_code,
            "details": exc.details
        }
    )

@app.exception_handler(TrainingDataException)
async def training_data_exception_handler(request: Request, exc: TrainingDataException):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": str(exc),
            "error_code": exc.error_code,
            "details": exc.details
        }
    )

@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": str(exc),
            "error_code": exc.error_code,
            "details": exc.details
        }
    )

@app.exception_handler(DatabaseConnectionException)
async def database_connection_handler(request: Request, exc: DatabaseConnectionException):
    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "message": str(exc),
            "error_code": exc.error_code,
            "details": exc.details
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error_code": "INTERNAL_SERVER_ERROR"
        }
    )


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "description": "Power Prediction Service for Wind Power Forecasting System",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "api_documentation": "/api/docs",
        "service_status": "initialized" if prediction_service.is_initialized else "not_initialized"
    }


# Include routers
app.include_router(predictions_router)
app.include_router(models_router)
app.include_router(training_router)
app.include_router(evaluation_router)
app.include_router(monitoring_router)
app.include_router(health_router)


# Startup event (additional initialization)
@app.on_event("startup")
async def startup_event():
    """Additional startup tasks."""
    logger.info("Running additional startup tasks...")

    try:
        # Additional initialization can be added here
        logger.info("Additional startup tasks completed")

    except Exception as e:
        logger.error(f"Error in startup event: {e}")
        raise


# Shutdown event
def shutdown_event():
    """Additional shutdown tasks."""
    logger.info("Running shutdown tasks...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )