"""
Proxy router for API Gateway.

Handles request routing to microservices with load balancing and circuit breaking.
"""

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional

from ..services import ProxyService
from ..models import ProxyRequest, ProxyResponse, GatewayResponse
from ..utils import get_logger, generate_request_id
from ..config import get_settings


router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()


@router.api_route("/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_request(
    service_name: str,
    path: str,
    request: Request,
    proxy_service: ProxyService = Depends(get_proxy_service),
):
    """
    Proxy requests to microservices.

    This endpoint routes requests to the appropriate microservice with:
    - Load balancing across healthy instances
    - Circuit breaker protection
    - Request/response transformation
    - Error handling and fallback

    Args:
        service_name: Name of the target service (e.g., tenant-service, scada-service)
        path: Path to forward to the service
        request: Incoming HTTP request
        proxy_service: Proxy service instance

    Returns:
        Proxied response from the target service
    """

    try:
        # Validate service name
        if service_name not in settings.services:
            raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

        # Get request ID from headers or generate new one
        request_id = request.headers.get("X-Request-ID") or generate_request_id()

        # Read request body
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()

        # Create proxy request
        proxy_request = ProxyRequest(
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            body=body,
            request_id=request_id,
        )

        # Log request
        logger.info(
            f"Proxying request: {request.method} /api/{service_name}/{path}",
            extra={
                "request_id": request_id,
                "service": service_name,
                "path": path,
                "method": request.method,
                "user_id": getattr(request.state, 'user_id', None),
                "tenant_id": getattr(request.state, 'tenant_id', None),
            }
        )

        # Make proxy request
        proxy_response = await proxy_service.proxy_request(
            request=proxy_request,
            service_name=service_name,
            path=path,
        )

        # Handle proxy response
        if proxy_response.error:
            logger.error(
                f"Proxy request failed: {service_name} - {proxy_response.error}",
                extra={
                    "request_id": request_id,
                    "service": service_name,
                    "path": path,
                    "status_code": proxy_response.status_code,
                }
            )

        # Return response with appropriate status code
        return JSONResponse(
            status_code=proxy_response.status_code,
            content=proxy_response.body,
            headers=proxy_response.headers,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Proxy request error for {service_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal proxy error")


@router.get("/services")
async def list_services(
    request: Request,
    proxy_service: ProxyService = Depends(get_proxy_service),
):
    """
    List all available services.

    Returns:
        List of available microservices
    """
    try:
        services = list(settings.services.keys())
        return GatewayResponse(
            success=True,
            message="Services retrieved successfully",
            data={"services": services},
            request_id=getattr(request.state, 'request_id', None),
        )
    except Exception as e:
        logger.error(f"Failed to list services: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve services")


@router.get("/services/{service_name}/status")
async def get_service_status(
    service_name: str,
    request: Request,
    proxy_service: ProxyService = Depends(get_proxy_service),
):
    """
    Get status information for a specific service.

    Args:
        service_name: Name of the service

    Returns:
        Service health and instance information
    """
    try:
        if service_name not in settings.services:
            raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

        # Get service status from service registry
        service_registry = proxy_service.service_registry
        service_status = await service_registry.get_service_status(service_name)

        return GatewayResponse(
            success=True,
            message=f"Service status retrieved for {service_name}",
            data=service_status,
            request_id=getattr(request.state, 'request_id', None),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get service status for {service_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve service status")


@router.get("/services/status")
async def get_all_services_status(
    request: Request,
    proxy_service: ProxyService = Depends(get_proxy_service),
):
    """
    Get status information for all services.

    Returns:
        Health status for all microservices
    """
    try:
        # Get all services status from service registry
        service_registry = proxy_service.service_registry
        all_status = await service_registry.get_all_services_status()

        return GatewayResponse(
            success=True,
            message="All services status retrieved successfully",
            data=all_status,
            request_id=getattr(request.state, 'request_id', None),
        )

    except Exception as e:
        logger.error(f"Failed to get all services status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve services status")


@router.get("/stats/proxy")
async def get_proxy_stats(
    request: Request,
    proxy_service: ProxyService = Depends(get_proxy_service),
):
    """
    Get proxy service statistics.

    Returns:
        Proxy service performance and health metrics
    """
    try:
        stats = proxy_service.get_proxy_stats()

        return GatewayResponse(
            success=True,
            message="Proxy statistics retrieved successfully",
            data=stats,
            request_id=getattr(request.state, 'request_id', None),
        )

    except Exception as e:
        logger.error(f"Failed to get proxy stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve proxy statistics")


@router.get("/stats/load-balancer")
async def get_load_balancer_stats(
    request: Request,
    proxy_service: ProxyService = Depends(get_proxy_service),
):
    """
    Get load balancer statistics.

    Returns:
        Load balancing metrics and performance data
    """
    try:
        load_balancer = proxy_service.load_balancer
        service_registry = proxy_service.service_registry

        stats = {}
        for service_name in service_registry.services:
            service_stats = load_balancer.get_load_balancer_stats(service_name)
            stats[service_name] = service_stats

        return GatewayResponse(
            success=True,
            message="Load balancer statistics retrieved successfully",
            data=stats,
            request_id=getattr(request.state, 'request_id', None),
        )

    except Exception as e:
        logger.error(f"Failed to get load balancer stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve load balancer statistics")


@router.get("/stats/circuit-breaker")
async def get_circuit_breaker_stats(
    request: Request,
    proxy_service: ProxyService = Depends(get_proxy_service),
):
    """
    Get circuit breaker statistics.

    Returns:
        Circuit breaker status and metrics
    """
    try:
        circuit_breaker_manager = proxy_service.circuit_breaker_manager
        stats = circuit_breaker_manager.get_all_circuit_breaker_stats()

        return GatewayResponse(
            success=True,
            message="Circuit breaker statistics retrieved successfully",
            data=stats,
            request_id=getattr(request.state, 'request_id', None),
        )

    except Exception as e:
        logger.error(f"Failed to get circuit breaker stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve circuit breaker statistics")


# Dependency injection
async def get_proxy_service(request: Request) -> ProxyService:
    """Get proxy service instance from application state."""
    return request.app.state.proxy_service


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
            "request_id": getattr(request.state, 'request_id', None),
            "path": str(request.url.path),
        }
    )


@router.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception in proxy router: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal proxy error",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
            },
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": getattr(request.state, 'request_id', None),
            "path": str(request.url.path),
        }
    )


# Import datetime
from datetime import datetime