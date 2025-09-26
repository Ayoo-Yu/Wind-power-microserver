"""
Load balancer for API Gateway.

Implements various load balancing algorithms for distributing requests across service instances.
"""

import random
import itertools
from typing import List, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta

from .service_registry import ServiceRegistry, ServiceInstance
from ..config import get_service_config
from ..utils import get_logger


logger = get_logger(__name__)


class LoadBalancer:
    """Load balancer for distributing requests across service instances."""

    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.logger = get_logger(__name__)

        # Connection tracking for least connections algorithm
        self.connection_counts = defaultdict(int)

        # Round-robin counters
        self.round_robin_counters = defaultdict(itertools.count)

        # Response time tracking for weighted algorithms
        self.response_times = defaultdict(lambda: deque(maxlen=10))

    async def select_instance(self, service_name: str, algorithm: str = "round_robin") -> Optional[ServiceInstance]:
        """Select a service instance using the specified algorithm."""

        # Get healthy instances
        healthy_instances = await self.service_registry.get_healthy_instances(service_name)

        if not healthy_instances:
            self.logger.warning(f"No healthy instances available for service: {service_name}")
            return None

        # Select instance based on algorithm
        if algorithm == "round_robin":
            return self._round_robin_selection(healthy_instances, service_name)
        elif algorithm == "least_connections":
            return self._least_connections_selection(healthy_instances, service_name)
        elif algorithm == "random":
            return self._random_selection(healthy_instances)
        elif algorithm == "weighted_round_robin":
            return self._weighted_round_robin_selection(healthy_instances, service_name)
        elif algorithm == "response_time":
            return self._response_time_selection(healthy_instances, service_name)
        else:
            # Default to round robin
            return self._round_robin_selection(healthy_instances, service_name)

    def _round_robin_selection(self, instances: List[ServiceInstance], service_name: str) -> ServiceInstance:
        """Select instance using round-robin algorithm."""
        counter = self.round_robin_counters[service_name]
        index = next(counter) % len(instances)
        selected = instances[index]

        self.logger.debug(f"Round-robin selection for {service_name}: {selected.url}")
        return selected

    def _least_connections_selection(self, instances: List[ServiceInstance], service_name: str) -> ServiceInstance:
        """Select instance with least active connections."""
        # Find instance with minimum connections
        min_connections = float('inf')
        selected_instance = instances[0]

        for instance in instances:
            connections = self.connection_counts[instance.url]
            if connections < min_connections:
                min_connections = connections
                selected_instance = instance

        self.logger.debug(f"Least connections selection for {service_name}: {selected_instance.url} (connections: {min_connections})")
        return selected_instance

    def _random_selection(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Select instance randomly."""
        selected = random.choice(instances)
        self.logger.debug(f"Random selection: {selected.url}")
        return selected

    def _weighted_round_robin_selection(self, instances: List[ServiceInstance], service_name: str) -> ServiceInstance:
        """Select instance using weighted round-robin based on response times."""
        # Calculate weights based on average response times (lower is better)
        weights = []
        for instance in instances:
            avg_response_time = self._get_average_response_time(instance.url)
            # Weight is inverse of response time (add small constant to avoid division by zero)
            weight = 1.0 / (avg_response_time + 0.1)
            weights.append(weight)

        # Select based on weights
        selected = random.choices(instances, weights=weights, k=1)[0]
        self.logger.debug(f"Weighted round-robin selection for {service_name}: {selected.url} (weight: {weights[instances.index(selected)]})")
        return selected

    def _response_time_selection(self, instances: List[ServiceInstance], service_name: str) -> ServiceInstance:
        """Select instance with best average response time."""
        best_instance = instances[0]
        best_response_time = float('inf')

        for instance in instances:
            avg_response_time = self._get_average_response_time(instance.url)
            if avg_response_time < best_response_time:
                best_response_time = avg_response_time
                best_instance = instance

        self.logger.debug(f"Response time selection for {service_name}: {best_instance.url} (avg: {best_response_time:.2f}ms)")
        return best_instance

    def _get_average_response_time(self, instance_url: str) -> float:
        """Get average response time for an instance."""
        response_times = list(self.response_times[instance_url])
        if not response_times:
            return 100.0  # Default response time for new instances
        return sum(response_times) / len(response_times)

    def record_connection_start(self, instance_url: str):
        """Record that a connection to an instance has started."""
        self.connection_counts[instance_url] += 1

    def record_connection_end(self, instance_url: str, response_time: Optional[float] = None):
        """Record that a connection to an instance has ended."""
        self.connection_counts[instance_url] = max(0, self.connection_counts[instance_url] - 1)

        if response_time is not None:
            self.response_times[instance_url].append(response_time)

    def record_instance_failure(self, instance_url: str, error: str):
        """Record a failure for an instance."""
        logger.warning(f"Instance failure recorded: {instance_url} - {error}")
        # Could implement more sophisticated failure tracking here

    def record_instance_success(self, instance_url: str, response_time: float):
        """Record a success for an instance."""
        logger.debug(f"Instance success recorded: {instance_url} - {response_time:.2f}ms")
        self.response_times[instance_url].append(response_time)

    def get_load_balancer_stats(self, service_name: str) -> Dict[str, Any]:
        """Get load balancer statistics for a service."""
        instances = self.service_registry.services.get(service_name, [])

        stats = {
            "service_name": service_name,
            "total_instances": len(instances),
            "healthy_instances": len([inst for inst in instances if inst.is_healthy]),
            "connection_counts": {},
            "average_response_times": {},
            "algorithm": "round_robin",  # Could be made configurable per service
        }

        for instance in instances:
            stats["connection_counts"][instance.url] = self.connection_counts[instance.url]
            stats["average_response_times"][instance.url] = self._get_average_response_time(instance.url)

        return stats

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global load balancer statistics."""
        total_instances = 0
        total_connections = 0
        total_healthy_instances = 0

        for service_name, instances in self.service_registry.services.items():
            total_instances += len(instances)
            total_healthy_instances += len([inst for inst in instances if inst.is_healthy])

            for instance in instances:
                total_connections += self.connection_counts[instance.url]

        return {
            "total_services": len(self.service_registry.services),
            "total_instances": total_instances,
            "total_healthy_instances": total_healthy_instances,
            "total_active_connections": total_connections,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def reset_stats(self, service_name: Optional[str] = None):
        """Reset load balancer statistics."""
        if service_name:
            # Reset stats for specific service
            instances = self.service_registry.services.get(service_name, [])
            for instance in instances:
                self.response_times[instance.url].clear()
                self.connection_counts[instance.url] = 0
            self.logger.info(f"Reset load balancer stats for service: {service_name}")
        else:
            # Reset all stats
            self.response_times.clear()
            self.connection_counts.clear()
            self.logger.info("Reset all load balancer stats")

    async def health_check(self) -> bool:
        """Perform health check on load balancer."""
        try:
            # Check if service registry is healthy
            if not await self.service_registry.health_check():
                return False

            # Check if we have valid connection tracking data
            if not self.connection_counts and not self.response_times:
                # This is OK for a newly started load balancer
                return True

            return True
        except Exception as e:
            logger.error(f"Load balancer health check failed: {e}")
            return False


# Load balancer factory
def create_load_balancer(service_registry: ServiceRegistry) -> LoadBalancer:
    """Create a load balancer instance."""
    return LoadBalancer(service_registry)


# Built-in load balancing algorithms
class LoadBalancingAlgorithms:
    """Constants for load balancing algorithms."""

    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    RESPONSE_TIME = "response_time"


# Algorithm descriptions
ALGORITHM_DESCRIPTIONS = {
    LoadBalancingAlgorithms.ROUND_ROBIN: "Distributes requests evenly across instances in order",
    LoadBalancingAlgorithms.LEAST_CONNECTIONS: "Routes to instance with fewest active connections",
    LoadBalancingAlgorithms.RANDOM: "Randomly selects an instance",
    LoadBalancingAlgorithms.WEIGHTED_ROUND_ROBIN: "Round-robin with weights based on response times",
    LoadBalancingAlgorithms.RESPONSE_TIME: "Routes to instance with best average response time",
}