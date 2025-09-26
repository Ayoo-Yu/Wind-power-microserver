"""
SCADA Data Service - Main Application
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging

from .config import get_settings
from .database import init_db, close_db, get_db_session
from .services import ConnectionManager, DataProcessor
from .routers import (
    connections_router,
    data_points_router,
    realtime_data_router,
    alarms_router,
    monitoring_router,
    health_router
)
from .exceptions import (
    ScadaConnectionNotFoundException,
    DuplicateScadaConnectionException,
    InvalidScadaDataException,
    ValidationException,
    DatabaseConnectionException
)
from .utils import get_logger

# Initialize logger
logger = get_logger(__name__)

# Get settings
settings = get_settings()

# Global service instances
connection_manager = ConnectionManager()
data_processor = DataProcessor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting SCADA Data Service...")

    try:
        # Initialize database
        logger.info("Initializing database...")
        await init_db()

        # Initialize connection manager
        logger.info("Initializing connection manager...")
        await connection_manager.initialize()

        logger.info("SCADA Data Service started successfully")

    except Exception as e:
        logger.error(f"Failed to start SCADA Data Service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down SCADA Data Service...")

    try:
        # Shutdown connection manager
        logger.info("Shutting down connection manager...")
        await connection_manager.shutdown()

        # Close database connections
        logger.info("Closing database connections...")
        await close_db()

        logger.info("SCADA Data Service shutdown completed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="SCADA Data Service for Wind Power Forecasting System - Handles real-time SCADA data collection, processing, and monitoring",
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
@app.exception_handler(ScadaConnectionNotFoundException)
async def scada_connection_not_found_handler(request: Request, exc: ScadaConnectionNotFoundException):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": str(exc),
            "error_code": "SCADA_CONNECTION_NOT_FOUND"
        }
    )

@app.exception_handler(DuplicateScadaConnectionException)
async def duplicate_scada_connection_handler(request: Request, exc: DuplicateScadaConnectionException):
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "message": str(exc),
            "error_code": "DUPLICATE_SCADA_CONNECTION"
        }
    )

@app.exception_handler(InvalidScadaDataException)
async def invalid_scada_data_handler(request: Request, exc: InvalidScadaDataException):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": str(exc),
            "error_code": "INVALID_SCADA_DATA"
        }
    )

@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": str(exc),
            "error_code": "VALIDATION_ERROR"
        }
    )

@app.exception_handler(DatabaseConnectionException)
async def database_connection_handler(request: Request, exc: DatabaseConnectionException):
    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "message": str(exc),
            "error_code": "DATABASE_CONNECTION_ERROR"
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
        "description": "SCADA Data Service for Wind Power Forecasting System",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "api_documentation": "/api/docs"
    }


# Include routers
app.include_router(connections_router)
app.include_router(data_points_router)
app.include_router(realtime_data_router)
app.include_router(alarms_router)
app.include_router(monitoring_router)
app.include_router(health_router)


# Startup event (additional initialization)
@app.on_event("startup")
async def startup_event():
    """Additional startup tasks."""
    logger.info("Running additional startup tasks...")

    try:
        # Add data processing callback to connection manager
        connection_manager.add_data_callback(data_processor.process_data_points)

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