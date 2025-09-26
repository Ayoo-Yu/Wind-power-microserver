"""
Proxy service for API Gateway.

Handles request routing, load balancing, and response forwarding.
"""

import asyncio
import time
from typing import Dict, Any, Optional
from urllib.parse import urljoin
import httpx

from .service_registry import ServiceRegistry
from .load_balancer import LoadBalancer
from .circuit_breaker import CircuitBreakerManager
from ..config import get_service_config
from ..utils import get_logger, create_http_client, sanitize_headers
from ..models import ProxyRequest, ProxyResponse


logger = get_logger(__name__)


class ProxyService:
    """Proxy service for routing requests to microservices."""

    def __init__(
        self,
        service_registry: ServiceRegistry,
        load_balancer: LoadBalancer,
        circuit_breaker_manager: CircuitBreakerManager,
    ):
        self.service_registry = service_registry
        self.load_balancer = load_balancer
        self.circuit_breaker_manager = circuit_breaker_manager
        self.http_client = create_http_client()
        self.logger = get_logger(__name__)

    async def proxy_request(
        self,
        request: ProxyRequest,
        service_name: str,
        path: str,
    ) -> ProxyResponse:
        """Proxy a request to the specified service."""

        start_time = time.time()

        try:
            # Get service configuration
            service_config = get_service_config(service_name)
            if not service_config:
                return ProxyResponse(
                    status_code=404,
                    body={"error": f"Service '{service_name}' not found"},
                    headers={},
                    error="Service not found",
                )

            # Check circuit breaker
            if await self.circuit_breaker_manager.is_open(service_name):
                self.logger.warning(f"Circuit breaker open for service: {service_name}")
                return ProxyResponse(
                    status_code=503,
                    body={"error": f"Service '{service_name}' is temporarily unavailable"},
                    headers={},
                    error="Circuit breaker open",
                )

            # Select service instance using load balancer
            instance = await self.load_balancer.select_instance(service_name)
            if not instance:
                self.logger.error(f"No healthy instances available for service: {service_name}")
                await self.circuit_breaker_manager.record_failure(service_name)
                return ProxyResponse(
                    status_code=503,
                    body={"error": f"No healthy instances available for service '{service_name}'"},
                    headers={},
                    error="No healthy instances",
                )

            # Build target URL
            target_url = urljoin(instance.url, path)

            # Prepare headers
            headers = self._prepare_headers(request.headers, request.request_id)

            # Record connection start
            self.load_balancer.record_connection_start(instance.url)

            # Make the request
            response = await self._make_request(
                method=request.method,
                url=target_url,
                headers=headers,
                body=request.body,
                timeout=service_config.timeout,
            )

            # Calculate response time
            response_time = (time.time() - start_time) * 1000

            # Record connection end
            self.load_balancer.record_connection_end(instance.url, response_time)

            # Record circuit breaker result
            if response.error:
                await self.circuit_breaker_manager.record_failure(service_name)
                self.load_balancer.record_instance_failure(instance.url, response.error)
            else:
                await self.circuit_breaker_manager.record_success(service_name)
                self.load_balancer.record_instance_success(instance.url, response_time)

            return response

        except Exception as e:
            self.logger.error(f"Proxy request failed for service {service_name}: {e}")
            await self.circuit_breaker_manager.record_failure(service_name)

            return ProxyResponse(
                status_code=500,
                body={"error": "Internal proxy error"},
                headers={},
                error=str(e),
            )

    async def _make_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[bytes],
        timeout: int,
    ) -> ProxyResponse:
        """Make HTTP request to target service."""

        try:
            # Prepare request parameters
            request_params = {
                "method": method,
                "url": url,
                "headers": headers,
                "timeout": timeout,
                "follow_redirects": False,
            }

            if body:
                request_params["content"] = body

            # Make the request
            start_time = time.time()
            response = await self.http_client.request(**request_params)
            response_time = (time.time() - start_time) * 1000

            # Read response body
            response_body = response.content

            # Parse JSON body if content-type indicates JSON
            body_data = None
            if response_body and response.headers.get("content-type", "").startswith("application/json"):
                try:
                    body_data = response.json()
                except Exception:
                    body_data = response_body.decode("utf-8", errors="ignore")
            elif response_body:
                body_data = response_body.decode("utf-8", errors="ignore")

            # Prepare response headers (exclude hop-by-hop headers)
            response_headers = self._prepare_response_headers(response.headers)

            self.logger.info(
                f"Proxy request completed: {method} {url} -> {response.status_code} ({response_time:.2f}ms)",
                extra={
                    "method": method,
                    "url": url,
                    "status_code": response.status_code,
                    "response_time_ms": response_time,
                }
            )

            return ProxyResponse(
                status_code=response.status_code,
                body=body_data,
                headers=response_headers,
                error=None,
            )

        except httpx.TimeoutException as e:
            self.logger.error(f"Proxy request timeout: {method} {url}")
            return ProxyResponse(
                status_code=504,
                body={"error": "Gateway timeout"},
                headers={},
                error=f"Timeout: {str(e)}",
            )

        except httpx.ConnectError as e:
            self.logger.error(f"Proxy request connection error: {method} {url}")
            return ProxyResponse(
                status_code=502,
                body={"error": "Bad gateway"},
                headers={},
                error=f"Connection error: {str(e)}",
            )

        except httpx.HTTPStatusError as e:
            self.logger.error(f"Proxy request HTTP error: {method} {url} -> {e.response.status_code}")
            return ProxyResponse(
                status_code=e.response.status_code,
                body={"error": e.response.text},
                headers=dict(e.response.headers),
                error=f"HTTP error: {str(e)}",
            )

        except Exception as e:
            self.logger.error(f"Proxy request unexpected error: {method} {url} - {e}")
            return ProxyResponse(
                status_code=500,
                body={"error": "Internal proxy error"},
                headers={},
                error=f"Unexpected error: {str(e)}",
            )

    def _prepare_headers(self, original_headers: Dict[str, str], request_id: str) -> Dict[str, str]:
        """Prepare headers for the proxied request."""

        # Start with original headers
        headers = dict(original_headers)

        # Add request ID for tracing
        headers["X-Request-ID"] = request_id

        # Remove hop-by-hop headers
        hop_by_hop_headers = {
            "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
            "te", "trailers", "transfer-encoding", "upgrade", "host"
        }

        # Filter out hop-by-hop headers
        filtered_headers = {
            k: v for k, v in headers.items()
            if k.lower() not in hop_by_hop_headers
        }

        # Sanitize sensitive headers
        return sanitize_headers(filtered_headers)

    def _prepare_response_headers(self, original_headers: Dict[str, str]) -> Dict[str, str]:
        """Prepare response headers for the client."""

        # Remove hop-by-hop headers from response
        hop_by_hop_headers = {
            "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
            "te", "trailers", "transfer-encoding", "upgrade"
        }

        # Filter out hop-by-hop headers
        filtered_headers = {
            k: v for k, v in original_headers.items()
            if k.lower() not in hop_by_hop_headers
        }

        return filtered_headers

    async def health_check(self) -> bool:
        """Perform health check on proxy service."""
        try:
            # Check if HTTP client is working
            if not self.http_client:
                return False

            # Check if dependencies are healthy
            if not await self.service_registry.health_check():
                return False

            if not await self.load_balancer.health_check():
                return False

            if not await self.circuit_breaker_manager.health_check():
                return False

            return True

        except Exception as e:
            self.logger.error(f"Proxy service health check failed: {e}")
            return False

    async def close(self):
        """Close proxy service and cleanup resources."""
        self.logger.info("Closing proxy service")

        if self.http_client:
            await self.http_client.close()

        self.logger.info("Proxy service closed")

    def get_proxy_stats(self) -> Dict[str, Any]:
        """Get proxy service statistics."""
        return {
            "service": "proxy_service",
            "status": "active",
            "timestamp": time.time(),
            "dependencies": {
                "service_registry": "healthy" if self.service_registry else "unhealthy",
                "load_balancer": "healthy" if self.load_balancer else "unhealthy",
                "circuit_breaker_manager": "healthy" if self.circuit_breaker_manager else "unhealthy",
            }
        }


# Proxy service factory
def create_proxy_service(
    service_registry: ServiceRegistry,
    load_balancer: LoadBalancer,
    circuit_breaker_manager: CircuitBreakerManager,
) -> ProxyService:
    """Create a proxy service instance."""
    return ProxyService(service_registry, load_balancer, circuit_breaker_manager)