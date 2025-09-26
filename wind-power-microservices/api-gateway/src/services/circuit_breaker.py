"""
Circuit breaker implementation for API Gateway.

Provides fault tolerance by preventing cascading failures across microservices.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from enum import Enum

from ..config import get_settings
from ..utils import get_logger, create_redis_manager


logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Service unavailable
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Individual circuit breaker for a service."""

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3,
        half_open_max_calls: int = 5,
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_failure_time = None
        self.last_state_change = datetime.utcnow()

        self.logger = get_logger(__name__)

    def is_call_permitted(self) -> bool:
        """Check if a call is permitted based on circuit state."""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            return self._should_attempt_reset()
        elif self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls

        return False

    def record_success(self):
        """Record a successful call."""
        if self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
        elif self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            self.half_open_calls += 1

            # Check if we should close the circuit
            if self.success_count >= self.success_threshold:
                self._close_circuit()

        self.logger.debug(f"Success recorded for {self.service_name} (state: {self.state.value})")

    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.CLOSED:
            # Check if we should open the circuit
            if self.failure_count >= self.failure_threshold:
                self._open_circuit()
        elif self.state == CircuitState.HALF_OPEN:
            # Return to open state on failure
            self._open_circuit()

        self.logger.debug(f"Failure recorded for {self.service_name} (state: {self.state.value}, failures: {self.failure_count})")

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        if self.last_failure_time is None:
            return True

        return datetime.utcnow() - self.last_failure_time >= timedelta(seconds=self.recovery_timeout)

    def _open_circuit(self):
        """Open the circuit."""
        self.state = CircuitState.OPEN
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_state_change = datetime.utcnow()

        self.logger.warning(f"Circuit opened for {self.service_name}")

    def _close_circuit(self):
        """Close the circuit."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_state_change = datetime.utcnow()

        self.logger.info(f"Circuit closed for {self.service_name}")

    def _half_open_circuit(self):
        """Transition to half-open state."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.half_open_calls = 0
        self.last_state_change = datetime.utcnow()

        self.logger.info(f"Circuit half-opened for {self.service_name}")

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "service_name": self.service_name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "half_open_calls": self.half_open_calls,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_state_change": self.last_state_change.isoformat(),
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "success_threshold": self.success_threshold,
        }


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""

    def __init__(self):
        self.settings = get_settings()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.redis_manager = None
        self.logger = get_logger(__name__)

    async def initialize(self):
        """Initialize circuit breaker manager."""
        self.logger.info("Initializing circuit breaker manager")

        # Initialize Redis manager
        self.redis_manager = create_redis_manager()
        await self.redis_manager.initialize()

        # Initialize circuit breakers for all services
        for service_name in self.settings.services:
            await self._initialize_circuit_breaker(service_name)

        self.logger.info("Circuit breaker manager initialized successfully")

    async def _initialize_circuit_breaker(self, service_name: str):
        """Initialize circuit breaker for a service."""
        config = self.settings.services.get(service_name)
        if not config:
            return

        circuit_breaker = CircuitBreaker(
            service_name=service_name,
            failure_threshold=config.circuit_breaker_threshold,
            recovery_timeout=config.circuit_breaker_timeout,
        )

        self.circuit_breakers[service_name] = circuit_breaker

        self.logger.debug(f"Circuit breaker initialized for {service_name}")

    def get_circuit_breaker(self, service_name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker for a service."""
        return self.circuit_breakers.get(service_name)

    async def is_open(self, service_name: str) -> bool:
        """Check if circuit breaker is open for a service."""
        circuit_breaker = self.get_circuit_breaker(service_name)
        if not circuit_breaker:
            return False

        # Check if we should transition from open to half-open
        if circuit_breaker.state == CircuitState.OPEN:
            if circuit_breaker._should_attempt_reset():
                circuit_breaker._half_open_circuit()
                await self._persist_circuit_state(service_name, circuit_breaker)

        return circuit_breaker.state == CircuitState.OPEN

    async def record_success(self, service_name: str):
        """Record a successful call for a service."""
        circuit_breaker = self.get_circuit_breaker(service_name)
        if circuit_breaker:
            circuit_breaker.record_success()
            await self._persist_circuit_state(service_name, circuit_breaker)

    async def record_failure(self, service_name: str):
        """Record a failed call for a service."""
        circuit_breaker = self.get_circuit_breaker(service_name)
        if circuit_breaker:
            circuit_breaker.record_failure()
            await self._persist_circuit_state(service_name, circuit_breaker)

    async def _persist_circuit_state(self, service_name: str, circuit_breaker: CircuitBreaker):
        """Persist circuit breaker state to Redis."""
        try:
            state_data = {
                "state": circuit_breaker.state.value,
                "failure_count": str(circuit_breaker.failure_count),
                "success_count": str(circuit_breaker.success_count),
                "half_open_calls": str(circuit_breaker.half_open_calls),
                "last_failure_time": circuit_breaker.last_failure_time.isoformat() if circuit_breaker.last_failure_time else "",
                "last_state_change": circuit_breaker.last_state_change.isoformat(),
            }

            await self.redis_manager.set_circuit_breaker_state(service_name, state_data)

        except Exception as e:
            self.logger.error(f"Failed to persist circuit state for {service_name}: {e}")

    async def _load_circuit_state(self, service_name: str, circuit_breaker: CircuitBreaker):
        """Load circuit breaker state from Redis."""
        try:
            state_data = await self.redis_manager.get_circuit_breaker_state(service_name)
            if not state_data:
                return

            # Restore state
            state_value = state_data.get("state", "closed")
            if state_value == "open":
                circuit_breaker.state = CircuitState.OPEN
            elif state_value == "half_open":
                circuit_breaker.state = CircuitState.HALF_OPEN
            else:
                circuit_breaker.state = CircuitState.CLOSED

            # Restore counters
            circuit_breaker.failure_count = int(state_data.get("failure_count", 0))
            circuit_breaker.success_count = int(state_data.get("success_count", 0))
            circuit_breaker.half_open_calls = int(state_data.get("half_open_calls", 0))

            # Restore timestamps
            if state_data.get("last_failure_time"):
                circuit_breaker.last_failure_time = datetime.fromisoformat(state_data["last_failure_time"])
            if state_data.get("last_state_change"):
                circuit_breaker.last_state_change = datetime.fromisoformat(state_data["last_state_change"])

        except Exception as e:
            self.logger.error(f"Failed to load circuit state for {service_name}: {e}")

    def get_circuit_breaker_stats(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get circuit breaker statistics for a service."""
        circuit_breaker = self.get_circuit_breaker(service_name)
        if circuit_breaker:
            return circuit_breaker.get_stats()
        return None

    def get_all_circuit_breaker_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get circuit breaker statistics for all services."""
        stats = {}
        for service_name, circuit_breaker in self.circuit_breakers.items():
            stats[service_name] = circuit_breaker.get_stats()
        return stats

    async def reset_circuit_breaker(self, service_name: str) -> bool:
        """Manually reset a circuit breaker."""
        circuit_breaker = self.get_circuit_breaker(service_name)
        if circuit_breaker:
            circuit_breaker._close_circuit()
            await self._persist_circuit_state(service_name, circuit_breaker)
            self.logger.info(f"Circuit breaker manually reset for {service_name}")
            return True
        return False

    async def force_open_circuit_breaker(self, service_name: str) -> bool:
        """Manually force open a circuit breaker."""
        circuit_breaker = self.get_circuit_breaker(service_name)
        if circuit_breaker:
            circuit_breaker._open_circuit()
            await self._persist_circuit_state(service_name, circuit_breaker)
            self.logger.warning(f"Circuit breaker manually opened for {service_name}")
            return True
        return False

    async def health_check(self) -> bool:
        """Perform health check on circuit breaker manager."""
        try:
            # Check Redis connection
            if not await self.redis_manager.health_check():
                return False

            # Check if we have circuit breakers configured
            if not self.circuit_breakers:
                self.logger.warning("No circuit breakers configured")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Circuit breaker manager health check failed: {e}")
            return False

    async def close(self):
        """Close circuit breaker manager and cleanup resources."""
        self.logger.info("Closing circuit breaker manager")

        if self.redis_manager:
            await self.redis_manager.close()

        self.logger.info("Circuit breaker manager closed")


# Circuit breaker factory
def create_circuit_breaker_manager() -> CircuitBreakerManager:
    """Create a circuit breaker manager instance."""
    return CircuitBreakerManager()


# Circuit breaker decorator for functions
class circuit_breaker:
    """Circuit breaker decorator."""

    def __init__(self, service_name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.circuit_breaker = CircuitBreaker(
            service_name=service_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            if not self.circuit_breaker.is_call_permitted():
                raise Exception(f"Circuit breaker open for {self.service_name}")

            try:
                result = await func(*args, **kwargs)
                self.circuit_breaker.record_success()
                return result
            except Exception as e:
                self.circuit_breaker.record_failure()
                raise

        return wrapper