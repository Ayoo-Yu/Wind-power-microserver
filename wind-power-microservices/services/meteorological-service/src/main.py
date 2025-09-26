"""
Meteorological Data Service - Main Application
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime

from .config import get_settings
from .database import db_manager
from .services import MeteorologicalManager
from .routers import (
    weather_stations_router,
    weather_data_router,
    forecasts_router,
    alerts_router,
    monitoring_router,
    health_router
)
from .exceptions import (
    WeatherStationNotFoundException,
    DuplicateWeatherStationException,
    InvalidWeatherDataException,
    ValidationException,
    DatabaseConnectionException,
    WeatherAPIException
)
from .utils import get_logger

# Initialize logger
logger = get_logger(__name__)

# Get settings
settings = get_settings()

# Global meteorological manager instance
meteo_manager = MeteorologicalManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Meteorological Data Service...")

    try:
        # Initialize meteorological manager
        await meteo_manager.initialize()
        logger.info("Meteorological Data Service started successfully")

    except Exception as e:
        logger.error(f"Failed to start Meteorological Data Service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Meteorological Data Service...")

    try:
        # Shutdown meteorological manager
        await meteo_manager.shutdown()
        logger.info("Meteorological Data Service shutdown completed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Meteorological Data Service for Wind Power Forecasting System - Handles weather data collection, forecasting, and alerts",
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
@app.exception_handler(WeatherStationNotFoundException)
async def weather_station_not_found_handler(request: Request, exc: WeatherStationNotFoundException):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": str(exc),
            "error_code": exc.error_code,
            "details": exc.details
        }
    )

@app.exception_handler(DuplicateWeatherStationException)
async def duplicate_weather_station_handler(request: Request, exc: DuplicateWeatherStationException):
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "message": str(exc),
            "error_code": exc.error_code,
            "details": exc.details
        }
    )

@app.exception_handler(InvalidWeatherDataException)
async def invalid_weather_data_handler(request: Request, exc: InvalidWeatherDataException):
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

@app.exception_handler(WeatherAPIException)
async def weather_api_exception_handler(request: Request, exc: WeatherAPIException):
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
        "description": "Meteorological Data Service for Wind Power Forecasting System",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "api_documentation": "/api/docs",
        "manager_status": "initialized" if meteo_manager.is_initialized else "not_initialized"
    }


# Include routers
app.include_router(weather_stations_router)
app.include_router(weather_data_router)
app.include_router(forecasts_router)
app.include_router(alerts_router)
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