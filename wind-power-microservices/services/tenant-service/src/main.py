"""
Main application entry point for Tenant Management Service.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware as FastAPICORS
from fastapi.responses import JSONResponse

# Import shared libraries (will be available after installation)
# from shared.config import get_settings
# from shared.utils import get_logger, create_database_manager, create_redis_manager
# from shared.middleware import (
#     create_request_context_middleware,
#     create_cors_middleware,
#     create_error_handling_middleware,
# )
# from shared.exceptions import ServiceException

# For now, use local imports until shared libraries are properly set up
from .config import Settings
from .database import init_database
from .exceptions import ServiceException
from .middleware import RequestContextMiddleware, ErrorHandlingMiddleware
from .routers import auth, users, tenants, health
from .utils import get_logger, create_redis_manager


# Initialize settings and logger
settings = get_settings()
settings.service_name = "tenant-service"
logger = get_logger(settings.service_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""

    # Startup
    logger.info(f"Starting {settings.service_name} v{settings.service_version}")

    # Initialize database
    await init_database()

    # Initialize Redis connection
    redis_manager = create_redis_manager()
    await redis_manager.initialize()
    app.state.redis_manager = redis_manager

    logger.info(f"{settings.service_name} started successfully")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.service_name}")

    # Close Redis connection
    if hasattr(app.state, 'redis_manager'):
        await app.state.redis_manager.close()

    logger.info(f"{settings.service_name} shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Tenant Management Service",
    description="Multi-tenant wind farm management and authentication service",
    version=settings.service_version,
    docs_url=f"{settings.api_v1_prefix}/docs",
    redoc_url=f"{settings.api_v1_prefix}/redoc",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    lifespan=lifespan,
)

# Add middleware
app.middleware("http")(create_request_context_middleware())
app.middleware("http")(create_error_handling_middleware())

# Add CORS middleware
app.add_middleware(
    FastAPICORS,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        db_manager = create_database_manager()
        db_healthy = await db_manager.health_check()

        # Check Redis connection
        redis_healthy = await app.state.redis_manager.health_check()

        if db_healthy and redis_healthy:
            return {
                "status": "healthy",
                "service": settings.service_name,
                "timestamp": datetime.utcnow().isoformat(),
                "dependencies": {
                    "database": "healthy" if db_healthy else "unhealthy",
                    "redis": "healthy" if redis_healthy else "unhealthy",
                }
            }
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "service": settings.service_name,
                    "timestamp": datetime.utcnow().isoformat(),
                    "dependencies": {
                        "database": "healthy" if db_healthy else "unhealthy",
                        "redis": "healthy" if redis_healthy else "unhealthy",
                    }
                }
            )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": settings.service_name,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


# Include routers
app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["authentication"])
app.include_router(users.router, prefix=f"{settings.api_v1_prefix}/users", tags=["users"])
app.include_router(tenants.router, prefix=f"{settings.api_v1_prefix}/tenants", tags=["tenants"])
app.include_router(health.router, prefix="/health", tags=["health"])


# Exception handlers
@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    """Handle service exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
                "status_code": 500,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level=settings.log_level.lower(),
    )