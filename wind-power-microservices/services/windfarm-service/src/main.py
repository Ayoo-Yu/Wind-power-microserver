"""
Main application for Wind Farm Management Service.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from .config import get_settings
from .database import init_database, close_database
from .utils import get_logger, RedisManager
from .routers import wind_farms_router, turbines_router, users_router, health_router
from .exceptions import ServiceException, create_error_response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting Wind Farm Management Service...")

    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized successfully")

        # Initialize Redis
        redis_manager = RedisManager()
        await redis_manager.initialize()
        logger.info("Redis initialized successfully")

        logger.info("Wind Farm Management Service started successfully")

    except Exception as e:
        logger.error(f"Failed to initialize service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Wind Farm Management Service...")

    try:
        # Close database connections
        await close_database()
        logger.info("Database connections closed")

        # Close Redis connections
        redis_manager = RedisManager()
        await redis_manager.close()
        logger.info("Redis connections closed")

        logger.info("Wind Farm Management Service shut down successfully")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="Wind Farm Management Service",
    description="Microservice for managing wind farms and turbines",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts
)


@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    """Handle service exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc)
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred",
                "status_code": 500,
                "details": {"error": str(exc)}
            },
            "timestamp": "2024-01-01T00:00:00Z"
        }
    )


# Include routers
app.include_router(wind_farms_router)
app.include_router(turbines_router)
app.include_router(users_router)
app.include_router(health_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Wind Farm Management Service",
        "version": "1.0.0",
        "status": "running",
        "description": "Microservice for managing wind farms and turbines",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "wind_farms": "/api/v1/wind-farms",
            "turbines": "/api/v1/turbines",
            "users": "/api/v1/users"
        }
    }


@app.get("/info")
async def info():
    """Service information endpoint."""
    return {
        "service": "Wind Farm Management Service",
        "version": "1.0.0",
        "description": "Microservice for managing wind farms and turbines",
        "features": [
            "Wind farm CRUD operations",
            "Turbine management",
            "User authentication and authorization",
            "Multi-windfarm access control",
            "Real-time statistics",
            "Audit logging"
        ],
        "technology": {
            "framework": "FastAPI",
            "database": "PostgreSQL",
            "cache": "Redis",
            "authentication": "JWT"
        },
        "contact": {
            "name": "Wind Power System Team",
            "email": "support@windpower.com"
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning"
    )