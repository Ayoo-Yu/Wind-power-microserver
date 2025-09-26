"""
Service registry for API Gateway.

Manages service discovery and health checking for microservices.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import httpx

from ..config import get_all_service_configs, ServiceConfig
from ..utils import get_logger, create_redis_manager


logger = get_logger(__name__)


class ServiceInstance:
    """Represents a service instance."""

    def __init__(self, url: str, metadata: Optional[Dict[str, Any]] = None):
        self.url = url
        self.metadata = metadata or {}
        self.is_healthy = True
        self.last_health_check = datetime.utcnow()
        self.failure_count = 0
        self.success_count = 0
        self.response_time = 0

    def mark_healthy(self, response_time: float):
        """Mark instance as healthy."""
        self.is_healthy = True
        self.last_health_check = datetime.utcnow()
        self.failure_count = 0
        self.success_count += 1
        self.response_time = response_time

    def mark_unhealthy(self, error: str):
        """Mark instance as unhealthy."""
        self.is_healthy = False
        self.last_health_check = datetime.utcnow()
        self.failure_count += 1
        self.metadata['last_error'] = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "is_healthy": self.is_healthy,
            "last_health_check": self.last_health_check.isoformat(),
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "response_time": self.response_time,
            "metadata": self.metadata,
        }


class ServiceRegistry:
    """Service registry for managing microservice instances."""

    def __init__(self):
        self.services: Dict[str, List[ServiceInstance]] = {}
        self.service_configs: Dict[str, ServiceConfig] = {}
        self.redis_manager = None
        self.logger = get_logger(__name__)
        self.health_check_task = None

    async def initialize(self):
        """Initialize service registry."""
        self.logger.info("Initializing service registry")

        # Initialize Redis manager
        self.redis_manager = create_redis_manager()
        await self.redis_manager.initialize()

        # Load service configurations
        self.service_configs = get_all_service_configs()

        # Initialize service instances
        for service_name, config in self.service_configs.items():
            await self._initialize_service(service_name, config)

        # Start health check task
        self.health_check_task = asyncio.create_task(self._health_check_loop())

        self.logger.info("Service registry initialized successfully")

    async def _initialize_service(self, service_name: str, config: ServiceConfig):
        """Initialize a service with its instances."""
        self.logger.info(f"Initializing service: {service_name}")

        # Create initial instance from configuration
        instance = ServiceInstance(config.url, {
            "service_name": service_name,
            "health_check_path": config.health_check_path,
            "timeout": config.timeout,
        })

        self.services[service_name] = [instance]

        # Perform initial health check
        await self._check_service_health(service_name, instance)

    async def register_instance(self, service_name: str, instance_url: str, metadata: Optional[Dict[str, Any]] = None):
        """Register a service instance."""
        if service_name not in self.services:
            self.services[service_name] = []

        # Check if instance already exists
        existing_instance = next(
            (inst for inst in self.services[service_name] if inst.url == instance_url),
            None
        )

        if existing_instance:
            self.logger.info(f"Service instance already registered: {service_name} - {instance_url}")
            return

        # Create new instance
        instance = ServiceInstance(instance_url, metadata or {})
        self.services[service_name].append(instance)

        # Store in Redis
        await self.redis_manager.register_service_instance(service_name, instance_url, {
            "service_name": service_name,
            "registered_at": datetime.utcnow().isoformat(),
            **(metadata or {})
        })

        self.logger.info(f"Service instance registered: {service_name} - {instance_url}")

    async def deregister_instance(self, service_name: str, instance_url: str):
        """Deregister a service instance."""
        if service_name not in self.services:
            return

        # Remove instance from local registry
        self.services[service_name] = [
            inst for inst in self.services[service_name] if inst.url != instance_url
        ]

        # Remove from Redis
        await self.redis_manager.redis_client.delete(f"services:{service_name}:instances:{instance_url}")

        self.logger.info(f"Service instance deregistered: {service_name} - {instance_url}")

    async def get_healthy_instances(self, service_name: str) -> List[ServiceInstance]:
        """Get healthy instances for a service."""
        if service_name not in self.services:
            return []

        healthy_instances = [
            inst for inst in self.services[service_name]
            if inst.is_healthy and self._is_instance_recent(inst)
        ]

        return healthy_instances

    async def get_all_instances(self, service_name: str) -> List[ServiceInstance]:
        """Get all instances for a service (healthy and unhealthy)."""
        return self.services.get(service_name, [])

    async def get_service_config(self, service_name: str) -> Optional[ServiceConfig]:
        """Get configuration for a service."""
        return self.service_configs.get(service_name)

    def get_all_services(self) -> List[str]:
        """Get list of all registered services."""
        return list(self.services.keys())

    async def health_check(self) -> bool:
        """Perform health check on service registry."""
        try:
            # Check Redis connection
            if not await self.redis_manager.health_check():
                return False

            # Check if we have at least one healthy instance per service
            for service_name in self.services:
                healthy_instances = await self.get_healthy_instances(service_name)
                if not healthy_instances:
                    self.logger.warning(f"No healthy instances for service: {service_name}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Service registry health check failed: {e}")
            return False

    async def _health_check_loop(self):
        """Background task for periodic health checks."""
        self.logger.info("Starting health check loop")

        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                for service_name, instances in self.services.items():
                    for instance in instances:
                        await self._check_service_health(service_name, instance)

            except asyncio.CancelledError:
                self.logger.info("Health check loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Health check loop error: {e}")

    async def _check_service_health(self, service_name: str, instance: ServiceInstance):
        """Check health of a service instance."""
        try:
            config = self.service_configs.get(service_name)
            if not config:
                return

            health_check_url = f"{instance.url}{config.health_check_path}"
            start_time = asyncio.get_event_loop().time()

            async with httpx.AsyncClient(timeout=config.timeout) as client:
                response = await client.get(health_check_url)
                response_time = (asyncio.get_event_loop().time() - start_time) * 1000

                if response.status_code == 200:
                    instance.mark_healthy(response_time)
                    self.logger.debug(f"Health check passed for {service_name} - {instance.url}")
                else:
                    instance.mark_unhealthy(f"HTTP {response.status_code}")
                    self.logger.warning(f"Health check failed for {service_name} - {instance.url}: HTTP {response.status_code}")

        except httpx.TimeoutException:
            instance.mark_unhealthy("Timeout")
            self.logger.warning(f"Health check timeout for {service_name} - {instance.url}")

        except httpx.ConnectError:
            instance.mark_unhealthy("Connection failed")
            self.logger.warning(f"Health check connection failed for {service_name} - {instance.url}")

        except Exception as e:
            instance.mark_unhealthy(str(e))
            self.logger.error(f"Health check error for {service_name} - {instance.url}: {e}")

    def _is_instance_recent(self, instance: ServiceInstance) -> bool:
        """Check if instance health check is recent (within 5 minutes)."""
        return datetime.utcnow() - instance.last_health_check < timedelta(minutes=5)

    async def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Get detailed status information for a service."""
        if service_name not in self.services:
            return {"error": "Service not found"}

        instances = []
        for instance in self.services[service_name]:
            instances.append(instance.to_dict())

        healthy_count = len([inst for inst in self.services[service_name] if inst.is_healthy])
        total_count = len(self.services[service_name])

        return {
            "service_name": service_name,
            "total_instances": total_count,
            "healthy_instances": healthy_count,
            "unhealthy_instances": total_count - healthy_count,
            "health_percentage": (healthy_count / total_count * 100) if total_count > 0 else 0,
            "instances": instances,
            "last_updated": datetime.utcnow().isoformat(),
        }

    async def get_all_services_status(self) -> Dict[str, Any]:
        """Get status information for all services."""
        services_status = {}
        total_services = 0
        total_healthy_services = 0

        for service_name in self.services:
            status = await self.get_service_status(service_name)
            services_status[service_name] = status

            total_services += 1
            if status.get("healthy_instances", 0) > 0:
                total_healthy_services += 1

        return {
            "total_services": total_services,
            "healthy_services": total_healthy_services,
            "unhealthy_services": total_services - total_healthy_services,
            "services": services_status,
            "last_updated": datetime.utcnow().isoformat(),
        }

    async def cleanup_expired_instances(self):
        """Clean up instances that haven't been updated recently."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=10)

        for service_name, instances in self.services.items():
            expired_instances = [
                inst for inst in instances
                if inst.last_health_check < cutoff_time
            ]

            for instance in expired_instances:
                await self.deregister_instance(service_name, instance.url)

    async def close(self):
        """Close service registry and cleanup resources."""
        self.logger.info("Closing service registry")

        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

        if self.redis_manager:
            await self.redis_manager.close()

        self.logger.info("Service registry closed")