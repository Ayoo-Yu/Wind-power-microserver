"""
Admin router for API Gateway.

Provides administrative endpoints for managing the gateway and monitoring services.
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Dict, Any, Optional

from ..services import ServiceRegistry, LoadBalancer, CircuitBreakerManager
from ..models import (
    GatewayResponse,
    CircuitBreakerControlRequest,
    RateLimitConfig,
    CacheConfig,
    ServiceStatus,
)
from ..utils import get_logger
from ..config import get_settings


router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger(__name__)
settings = get_settings()


# Circuit Breaker Management
@router.post("/circuit-breaker/control")
async def control_circuit_breaker(
    request: CircuitBreakerControlRequest,
    circuit_breaker_manager: CircuitBreakerManager = Depends(get_circuit_breaker_manager),
) -> GatewayResponse:
    """
    Control circuit breaker state for a service.

    Args:
        request: Circuit breaker control request

    Returns:
        Operation result
    """
    try:
        service_name = request.service_name
        action = request.action

        if service_name not in settings.services:
            raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

        if action == "reset":
            success = await circuit_breaker_manager.reset_circuit_breaker(service_name)
            message = f"Circuit breaker reset for {service_name}"
        elif action == "force_open":
            success = await circuit_breaker_manager.force_open_circuit_breaker(service_name)
            message = f"Circuit breaker forced open for {service_name}"
        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

        if success:
            logger.info(f"Circuit breaker {action} completed for {service_name}")
            return GatewayResponse(
                success=True,
                message=message,
                data={"service": service_name, "action": action},
            )
        else:
            raise HTTPException(status_code=500, detail=f"Failed to {action} circuit breaker for {service_name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Circuit breaker control failed: {e}")
        raise HTTPException(status_code=500, detail="Circuit breaker control failed")


@router.get("/circuit-breaker/stats")
async def get_circuit_breaker_stats(
    circuit_breaker_manager: CircuitBreakerManager = Depends(get_circuit_breaker_manager),
) -> GatewayResponse:
    """
    Get circuit breaker statistics for all services.

    Returns:
        Circuit breaker statistics
    """
    try:
        stats = circuit_breaker_manager.get_all_circuit_breaker_stats()

        return GatewayResponse(
            success=True,
            message="Circuit breaker statistics retrieved successfully",
            data=stats,
        )

    except Exception as e:
        logger.error(f"Failed to get circuit breaker stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve circuit breaker statistics")


# Load Balancer Management
@router.get("/load-balancer/stats")
async def get_load_balancer_stats(
    load_balancer: LoadBalancer = Depends(get_load_balancer),
) -> GatewayResponse:
    """
    Get load balancer statistics.

    Returns:
        Load balancer statistics
    """
    try:
        global_stats = load_balancer.get_global_stats()
        service_stats = {}

        for service_name in settings.services:
            service_stats[service_name] = load_balancer.get_load_balancer_stats(service_name)

        return GatewayResponse(
            success=True,
            message="Load balancer statistics retrieved successfully",
            data={
                "global": global_stats,
                "services": service_stats,
            }
        )

    except Exception as e:
        logger.error(f"Failed to get load balancer stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve load balancer statistics")


@router.post("/load-balancer/reset-stats")
async def reset_load_balancer_stats(
    load_balancer: LoadBalancer = Depends(get_load_balancer),
    service_name: Optional[str] = None,
) -> GatewayResponse:
    """
    Reset load balancer statistics.

    Args:
        service_name: Optional service name to reset stats for (resets all if not provided)

    Returns:
        Operation result
    """
    try:
        load_balancer.reset_stats(service_name)

        target = service_name if service_name else "all services"
        message = f"Load balancer statistics reset for {target}"

        logger.info(message)
        return GatewayResponse(
            success=True,
            message=message,
            data={"service": service_name, "action": "reset_stats"},
        )

    except Exception as e:
        logger.error(f"Failed to reset load balancer stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset load balancer statistics")


# Service Registry Management
@router.get("/services/discovery")
async def get_service_discovery_info(
    service_registry: ServiceRegistry = Depends(get_service_registry),
) -> GatewayResponse:
    """
    Get service discovery information.

    Returns:
        Service discovery details
    """
    try:
        services_info = {}

        for service_name in settings.services:
            instances = await service_registry.get_all_instances(service_name)
            healthy_instances = await service_registry.get_healthy_instances(service_name)

            services_info[service_name] = {
                "total_instances": len(instances),
                "healthy_instances": len(healthy_instances),
                "instances": [instance.to_dict() for instance in instances],
            }

        return GatewayResponse(
            success=True,
            message="Service discovery information retrieved successfully",
            data=services_info,
        )

    except Exception as e:
        logger.error(f"Failed to get service discovery info: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve service discovery information")


@router.post("/services/cleanup-expired")
async def cleanup_expired_instances(
    service_registry: ServiceRegistry = Depends(get_service_registry),
) -> GatewayResponse:
    """
    Clean up expired service instances.

    Returns:
        Cleanup operation result
    """
    try:
        await service_registry.cleanup_expired_instances()

        logger.info("Expired service instances cleaned up")
        return GatewayResponse(
            success=True,
            message="Expired service instances cleaned up successfully",
            data={"action": "cleanup_expired"},
        )

    except Exception as e:
        logger.error(f"Failed to cleanup expired instances: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup expired service instances")


# Gateway Configuration
@router.get("/config")
async def get_gateway_config() -> GatewayResponse:
    """
    Get gateway configuration.

    Returns:
        Current gateway configuration
    """
    try:
        config = {
            "service_name": settings.service_name,
            "version": settings.service_version,
            "environment": settings.environment,
            "host": settings.host,
            "port": settings.port,
            "cors_origins": settings.cors_origins,
            "features": {
                "circuit_breaker": settings.circuit_breaker_enabled,
                "rate_limiting": True,
                "authentication": True,
                "logging": settings.request_logging_enabled,
                "metrics": settings.metrics_enabled,
                "tracing": settings.tracing_enabled,
            },
            "limits": {
                "global_rate_limit_rpm": settings.global_rate_limit_rpm,
                "per_ip_rate_limit_rpm": settings.per_ip_rate_limit_rpm,
                "per_user_rate_limit_rpm": settings.per_user_rate_limit_rpm,
                "circuit_breaker_failure_threshold": settings.circuit_breaker_failure_threshold,
                "circuit_breaker_recovery_timeout": settings.circuit_breaker_recovery_timeout,
            },
            "supported_algorithms": ["round_robin", "least_connections", "random", "weighted_round_robin", "response_time"],
        }

        return GatewayResponse(
            success=True,
            message="Gateway configuration retrieved successfully",
            data=config,
        )

    except Exception as e:
        logger.error(f"Failed to get gateway config: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gateway configuration")


@router.get("/services")
async def get_configured_services() -> GatewayResponse:
    """
    Get configured services.

    Returns:
        List of configured services with their settings
    """
    try:
        services = {}
        for service_name, config in settings.services.items():
            services[service_name] = {
                "name": config.name,
                "url": config.url,
                "health_check_path": config.health_check_path,
                "timeout": config.timeout,
                "retry_attempts": config.retry_attempts,
                "circuit_breaker_threshold": config.circuit_breaker_threshold,
                "circuit_breaker_timeout": config.circuit_breaker_timeout,
                "rate_limit_rpm": config.rate_limit_rpm,
            }

        return GatewayResponse(
            success=True,
            message="Configured services retrieved successfully",
            data={"services": services},
        )

    except Exception as e:
        logger.error(f"Failed to get configured services: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configured services")


# Gateway Control
@router.post("/reload-config")
async def reload_gateway_config() -> GatewayResponse:
    """
    Reload gateway configuration.

    Note: This is a placeholder for dynamic configuration reloading.
    In a production environment, this would reload configuration from a central source.

    Returns:
        Operation result
    """
    try:
        # In a real implementation, this would reload configuration from:
        # - Configuration management service
        # - Kubernetes ConfigMaps
        # - External configuration store
        # - Database

        logger.info("Gateway configuration reload requested")

        return GatewayResponse(
            success=True,
            message="Gateway configuration reload completed (placeholder)",
            data={"action": "reload_config", "status": "placeholder_implementation"},
        )

    except Exception as e:
        logger.error(f"Failed to reload gateway config: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload gateway configuration")


# Dependency injection functions
async def get_service_registry(request: Request) -> ServiceRegistry:
    """Get service registry from application state."""
    return request.app.state.service_registry


async def get_load_balancer(request: Request) -> LoadBalancer:
    """Get load balancer from application state."""
    return request.app.state.load_balancer


async def get_circuit_breaker_manager(request: Request) -> CircuitBreakerManager:
    """Get circuit breaker manager from application state."""
    return request.app.state.circuit_breaker_manager


# Error handlers
@router.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
            },
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path),
        }
    )


@router.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception in admin router: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal admin error",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
            },
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path),
        }
    )