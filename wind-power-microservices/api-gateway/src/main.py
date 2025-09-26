"""
API Gateway for Wind Power Forecasting Microservices Platform.

This API Gateway provides:
- Request routing to microservices
- Authentication and authorization
- Rate limiting and throttling
- Request/response transformation
- Circuit breaker patterns
- Load balancing
- Monitoring and logging
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

from .config import get_settings
from .utils import get_logger, create_redis_manager
from .middleware import (
    RequestContextMiddleware,
    AuthenticationMiddleware,
    RateLimitMiddleware,
    CircuitBreakerMiddleware,
    LoggingMiddleware,
)
from .routers import proxy_router, health_router, admin_router
from .services import ServiceRegistry, LoadBalancer, CircuitBreakerManager
from .models import GatewayResponse, HealthStatus


# Initialize settings and logger
settings = get_settings()
logger = get_logger("api-gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""

    # Startup
    logger.info(f"Starting API Gateway v{settings.service_version}")

    # Initialize Redis
    redis_manager = create_redis_manager()
    await redis_manager.initialize()
    app.state.redis_manager = redis_manager

    # Initialize service registry
    service_registry = ServiceRegistry()
    await service_registry.initialize()
    app.state.service_registry = service_registry

    # Initialize load balancer
    load_balancer = LoadBalancer(service_registry)
    app.state.load_balancer = load_balancer

    # Initialize circuit breaker manager
    circuit_breaker_manager = CircuitBreakerManager()
    app.state.circuit_breaker_manager = circuit_breaker_manager

    logger.info("API Gateway started successfully")

    yield

    # Shutdown
    logger.info("Shutting down API Gateway")

    # Close connections
    if hasattr(app.state, 'redis_manager'):
        await app.state.redis_manager.close()

    logger.info("API Gateway shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Wind Power API Gateway",
    description="API Gateway for Wind Power Forecasting Microservices Platform",
    version=settings.service_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(RequestContextMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with gateway information."""
    return {
        "service": "wind-power-api-gateway",
        "version": settings.service_version,
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "description": "API Gateway for Wind Power Forecasting Microservices Platform",
        "services": list(settings.services.keys()),
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check Redis connection
        redis_healthy = await app.state.redis_manager.health_check()

        # Check service registry
        services_healthy = await app.state.service_registry.health_check()

        if redis_healthy and services_healthy:
            return {
                "status": "healthy",
                "service": "api-gateway",
                "timestamp": datetime.utcnow().isoformat(),
                "dependencies": {
                    "redis": "healthy" if redis_healthy else "unhealthy",
                    "service_registry": "healthy" if services_healthy else "unhealthy",
                }
            }
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "service": "api-gateway",
                    "timestamp": datetime.utcnow().isoformat(),
                    "dependencies": {
                        "redis": "healthy" if redis_healthy else "unhealthy",
                        "service_registry": "healthy" if services_healthy else "unhealthy",
                    }
                }
            )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "api-gateway",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


# Include routers
app.include_router(proxy_router, prefix="/api", tags=["proxy"])
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(admin_router, tags=["admin"])


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
            },
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path),
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
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
            },
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path),
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level=settings.log_level.lower(),
    )