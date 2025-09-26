"""
Health check router for API Gateway.
"""

from fastapi import APIRouter, Request, Depends
from datetime import datetime
from typing import Dict, Any, Optional

from ..services import ServiceRegistry, LoadBalancer, CircuitBreakerManager
from ..models import HealthCheckResponse, ServiceStatus
from ..utils import get_logger
from ..config import get_settings


router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()


@router.get("/ready")
async def readiness_check(
    request: Request,
    service_registry: ServiceRegistry = Depends(get_service_registry),
    load_balancer: LoadBalancer = Depends(get_load_balancer),
    circuit_breaker_manager: CircuitBreakerManager = Depends(get_circuit_breaker_manager),
) -> HealthCheckResponse:
    """
    Readiness check - indicates if the gateway is ready to handle requests.
    """
    try:
        start_time = datetime.utcnow()

        # Check Redis connection
        redis_healthy = await request.app.state.redis_manager.health_check()

        # Check service registry
        registry_healthy = await service_registry.health_check()

        # Check load balancer
        lb_healthy = await load_balancer.health_check()

        # Check circuit breaker manager
        cb_healthy = await circuit_breaker_manager.health_check()

        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Determine overall status
        if redis_healthy and registry_healthy and lb_healthy and cb_healthy:
            status = ServiceStatus.HEALTHY
        elif redis_healthy and (registry_healthy or lb_healthy or cb_healthy):
            status = ServiceStatus.DEGRADED
        else:
            status = ServiceStatus.UNHEALTHY

        return HealthCheckResponse(
            status=status,
            service=settings.service_name,
            timestamp=datetime.utcnow(),
            version=settings.service_version,
            dependencies={
                "redis": "healthy" if redis_healthy else "unhealthy",
                "service_registry": "healthy" if registry_healthy else "unhealthy",
                "load_balancer": "healthy" if lb_healthy else "unhealthy",
                "circuit_breaker_manager": "healthy" if cb_healthy else "unhealthy",
            },
            response_time_ms=round(response_time, 2),
        )

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return HealthCheckResponse(
            status=ServiceStatus.UNHEALTHY,
            service=settings.service_name,
            timestamp=datetime.utcnow(),
            version=settings.service_version,
            error=str(e),
            dependencies={},
        )


@router.get("/live")
async def liveness_check(
    request: Request,
) -> HealthCheckResponse:
    """
    Liveness check - indicates if the gateway is alive.
    """
    return HealthCheckResponse(
        status=ServiceStatus.HEALTHY,
        service=settings.service_name,
        timestamp=datetime.utcnow(),
        version=settings.service_version,
    )


@router.get("/startup")
async def startup_check(
    request: Request,
) -> HealthCheckResponse:
    """
    Startup check - indicates if the gateway has successfully started.
    """
    return HealthCheckResponse(
        status=ServiceStatus.HEALTHY,
        service=settings.service_name,
        timestamp=datetime.utcnow(),
        version=settings.service_version,
    )


@router.get("/dependencies")
async def dependencies_check(
    request: Request,
    service_registry: ServiceRegistry = Depends(get_service_registry),
    load_balancer: LoadBalancer = Depends(get_load_balancer),
    circuit_breaker_manager: CircuitBreakerManager = Depends(get_circuit_breaker_manager),
) -> Dict[str, Any]:
    """
    Dependencies check - checks all external dependencies.
    """
    dependencies = {}
    overall_status = ServiceStatus.HEALTHY

    # Check Redis
    try:
        redis_healthy = await request.app.state.redis_manager.health_check()
        dependencies["redis"] = {
            "status": "healthy" if redis_healthy else "unhealthy",
            "type": "redis",
            "url": settings.redis_url,
        }
        if not redis_healthy:
            overall_status = ServiceStatus.UNHEALTHY

    except Exception as e:
        dependencies["redis"] = {
            "status": "unhealthy",
            "type": "redis",
            "error": str(e),
        }
        overall_status = ServiceStatus.UNHEALTHY

    # Check Service Registry
    try:
        registry_healthy = await service_registry.health_check()
        dependencies["service_registry"] = {
            "status": "healthy" if registry_healthy else "unhealthy",
            "type": "service_registry",
            "services_count": len(service_registry.services),
        }
        if not registry_healthy:
            overall_status = ServiceStatus.UNHEALTHY

    except Exception as e:
        dependencies["service_registry"] = {
            "status": "unhealthy",
            "type": "service_registry",
            "error": str(e),
        }
        overall_status = ServiceStatus.UNHEALTHY

    # Check Load Balancer
    try:
        lb_healthy = await load_balancer.health_check()
        dependencies["load_balancer"] = {
            "status": "healthy" if lb_healthy else "unhealthy",
            "type": "load_balancer",
            "algorithm": settings.load_balancing_algorithm,
        }
        if not lb_healthy:
            overall_status = ServiceStatus.UNHEALTHY

    except Exception as e:
        dependencies["load_balancer"] = {
            "status": "unhealthy",
            "type": "load_balancer",
            "error": str(e),
        }
        overall_status = ServiceStatus.UNHEALTHY

    # Check Circuit Breaker Manager
    try:
        cb_healthy = await circuit_breaker_manager.health_check()
        dependencies["circuit_breaker_manager"] = {
            "status": "healthy" if cb_healthy else "unhealthy",
            "type": "circuit_breaker_manager",
            "enabled": settings.circuit_breaker_enabled,
        }
        if not cb_healthy:
            overall_status = ServiceStatus.UNHEALTHY

    except Exception as e:
        dependencies["circuit_breaker_manager"] = {
            "status": "unhealthy",
            "type": "circuit_breaker_manager",
            "error": str(e),
        }
        overall_status = ServiceStatus.UNHEALTHY

    return {
        "status": overall_status.value,
        "service": settings.service_name,
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": dependencies,
    }


@router.get("/deep")
async def deep_health_check(
    request: Request,
    service_registry: ServiceRegistry = Depends(get_service_registry),
) -> Dict[str, Any]:
    """
    Deep health check - performs comprehensive health checks including service discovery.
    """
    try:
        start_time = datetime.utcnow()

        # Basic dependency checks
        basic_checks = await dependencies_check(request, service_registry)

        # Check each service individually
        services_health = {}
        all_services_healthy = True

        for service_name in settings.services:
            try:
                service_status = await service_registry.get_service_status(service_name)
                services_health[service_name] = {
                    "status": "healthy" if service_status["health_percentage"] > 50 else "unhealthy",
                    "healthy_instances": service_status["healthy_instances"],
                    "total_instances": service_status["total_instances"],
                    "health_percentage": service_status["health_percentage"],
                }

                if service_status["health_percentage"] <= 50:
                    all_services_healthy = False

            except Exception as e:
                services_health[service_name] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                all_services_healthy = False

        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Determine overall status
        if basic_checks["status"] == "healthy" and all_services_healthy:
            overall_status = ServiceStatus.HEALTHY
        elif basic_checks["status"] in ["healthy", "degraded"]:
            overall_status = ServiceStatus.DEGRADED
        else:
            overall_status = ServiceStatus.UNHEALTHY

        return {
            "status": overall_status.value,
            "service": settings.service_name,
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": round(response_time, 2),
            "basic_dependencies": basic_checks["dependencies"],
            "services_health": services_health,
            "summary": {
                "total_services": len(settings.services),
                "healthy_services": len([s for s in services_health.values() if s["status"] == "healthy"]),
                "unhealthy_services": len([s for s in services_health.values() if s["status"] == "unhealthy"]),
            }
        }

    except Exception as e:
        logger.error(f"Deep health check failed: {e}")
        return {
            "status": ServiceStatus.UNHEALTHY.value,
            "service": settings.service_name,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
        }


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