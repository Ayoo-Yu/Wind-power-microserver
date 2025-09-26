"""
Base protocol adapter for SCADA Data Service.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
import asyncio
import logging

from ..utils import get_logger
from ..models import ScadaDataPoint, DataPointType


logger = get_logger(__name__)


class ConnectionStatus(Enum):
    """Protocol connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class ProtocolConnection(ABC):
    """Base class for protocol connections."""

    def __init__(self, connection_id: str, config: Dict[str, Any]):
        self.connection_id = connection_id
        self.config = config
        self.status = ConnectionStatus.DISCONNECTED
        self.is_connected = False
        self.error_count = 0
        self.data_count = 0
        self.last_data_time = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = config.get("max_reconnect_attempts", 5)
        self.reconnect_delay = config.get("reconnect_delay", 10)
        self.connection_timeout = config.get("connection_timeout", 30)
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self._data_callbacks: List[Callable] = []
        self._status_callbacks: List[Callable] = []
        self._alarm_callbacks: List[Callable] = []

    def add_data_callback(self, callback: Callable):
        """Add data callback."""
        self._data_callbacks.append(callback)

    def add_status_callback(self, callback: Callable):
        """Add status callback."""
        self._status_callbacks.append(callback)

    def add_alarm_callback(self, callback: Callable):
        """Add alarm callback."""
        self._alarm_callbacks.append(callback)

    async def _notify_data_callbacks(self, data_points: List[ScadaDataPoint]):
        """Notify data callbacks."""
        for callback in self._data_callbacks:
            try:
                await callback(data_points)
            except Exception as e:
                self.logger.error(f"Error in data callback: {e}")

    async def _notify_status_callbacks(self, status: ConnectionStatus, details: Optional[Dict[str, Any]] = None):
        """Notify status callbacks."""
        for callback in self._status_callbacks:
            try:
                await callback(self.connection_id, status, details)
            except Exception as e:
                self.logger.error(f"Error in status callback: {e}")

    async def _notify_alarm_callbacks(self, alarm_data: Dict[str, Any]):
        """Notify alarm callbacks."""
        for callback in self._alarm_callbacks:
            try:
                await callback(alarm_data)
            except Exception as e:
                self.logger.error(f"Error in alarm callback: {e}")

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to SCADA system."""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from SCADA system."""
        pass

    @abstractmethod
    async def read_data(self) -> List[ScadaDataPoint]:
        """Read data from SCADA system."""
        pass

    @abstractmethod
    async def write_data(self, data_points: List[Dict[str, Any]]) -> bool:
        """Write data to SCADA system."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        pass

    async def reconnect(self) -> bool:
        """Attempt to reconnect."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.warning(f"Max reconnection attempts reached for {self.connection_id}")
            return False

        self.reconnect_attempts += 1
        self.status = ConnectionStatus.RECONNECTING
        await self._notify_status_callbacks(self.status, {"attempt": self.reconnect_attempts})

        self.logger.info(f"Reconnection attempt {self.reconnect_attempts} for {self.connection_id}")

        # Wait before reconnecting
        await asyncio.sleep(self.reconnect_delay)

        try:
            success = await self.connect()
            if success:
                self.reconnect_attempts = 0
                self.logger.info(f"Successfully reconnected {self.connection_id}")
            return success
        except Exception as e:
            self.logger.error(f"Reconnection attempt {self.reconnect_attempts} failed: {e}")
            return False

    def update_status(self, status: ConnectionStatus, details: Optional[Dict[str, Any]] = None):
        """Update connection status."""
        old_status = self.status
        self.status = status
        self.is_connected = (status == ConnectionStatus.CONNECTED)

        if status != old_status:
            self.logger.info(f"Connection {self.connection_id} status changed: {old_status.value} -> {status.value}")
            # Run in background to avoid blocking
            asyncio.create_task(self._notify_status_callbacks(status, details))

    def record_data_received(self):
        """Record that data was received."""
        self.data_count += 1
        self.last_data_time = datetime.utcnow()

    def record_error(self, error_message: str):
        """Record an error."""
        self.error_count += 1
        self.logger.error(f"Connection {self.connection_id} error: {error_message}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "connection_id": self.connection_id,
            "status": self.status.value,
            "is_connected": self.is_connected,
            "error_count": self.error_count,
            "data_count": self.data_count,
            "last_data_time": self.last_data_time.isoformat() if self.last_data_time else None,
            "reconnect_attempts": self.reconnect_attempts,
            "max_reconnect_attempts": self.max_reconnect_attempts,
            "config": {
                "connection_timeout": self.connection_timeout,
                "reconnect_delay": self.reconnect_delay,
            }
        }


class BaseProtocolAdapter(ABC):
    """Base protocol adapter for SCADA protocols."""

    def __init__(self, protocol_type: str):
        self.protocol_type = protocol_type
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.connections: Dict[str, ProtocolConnection] = {}

    @abstractmethod
    async def create_connection(self, connection_id: str, config: Dict[str, Any]) -> ProtocolConnection:
        """Create a new protocol connection."""
        pass

    @abstractmethod
    def get_protocol_info(self) -> Dict[str, Any]:
        """Get protocol information."""
        pass

    async def add_connection(self, connection_id: str, config: Dict[str, Any]) -> ProtocolConnection:
        """Add a new connection."""
        if connection_id in self.connections:
            raise ValueError(f"Connection {connection_id} already exists")

        connection = await self.create_connection(connection_id, config)
        self.connections[connection_id] = connection
        self.logger.info(f"Added {self.protocol_type} connection: {connection_id}")
        return connection

    async def remove_connection(self, connection_id: str) -> bool:
        """Remove a connection."""
        connection = self.connections.get(connection_id)
        if not connection:
            return False

        try:
            await connection.disconnect()
            del self.connections[connection_id]
            self.logger.info(f"Removed {self.protocol_type} connection: {connection_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove connection {connection_id}: {e}")
            return False

    def get_connection(self, connection_id: str) -> Optional[ProtocolConnection]:
        """Get connection by ID."""
        return self.connections.get(connection_id)

    def get_all_connections(self) -> Dict[str, ProtocolConnection]:
        """Get all connections."""
        return self.connections.copy()

    async def start_all_connections(self):
        """Start all connections."""
        tasks = []
        for connection_id, connection in self.connections.items():
            if connection.status == ConnectionStatus.DISCONNECTED:
                task = asyncio.create_task(connection.connect())
                tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful = sum(1 for result in results if result is True)
            self.logger.info(f"Started {successful}/{len(tasks)} connections")

    async def stop_all_connections(self):
        """Stop all connections."""
        tasks = []
        for connection_id, connection in self.connections.items():
            if connection.is_connected:
                task = asyncio.create_task(connection.disconnect())
                tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful = sum(1 for result in results if result is True)
            self.logger.info(f"Stopped {successful}/{len(tasks)} connections")

    def get_statistics(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        total_connections = len(self.connections)
        active_connections = sum(1 for conn in self.connections.values() if conn.is_connected)
        error_count = sum(conn.error_count for conn in self.connections.values())
        data_count = sum(conn.data_count for conn in self.connections.values())

        return {
            "protocol_type": self.protocol_type,
            "total_connections": total_connections,
            "active_connections": active_connections,
            "error_count": error_count,
            "data_count": data_count,
            "connections": {
                conn_id: conn.get_statistics() for conn_id, conn in self.connections.items()
            }
        }

    def is_healthy(self) -> bool:
        """Check if adapter is healthy."""
        if not self.connections:
            return True  # Healthy if no connections

        healthy_count = sum(1 for conn in self.connections.values() if conn.is_healthy())
        return healthy_count > 0  # At least one healthy connection

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        connection_health = {}
        for conn_id, connection in self.connections.items():
            connection_health[conn_id] = {
                "status": connection.status.value,
                "is_healthy": connection.is_healthy(),
                "last_data_time": connection.last_data_time.isoformat() if connection.last_data_time else None,
            }

        return {
            "protocol_type": self.protocol_type,
            "is_healthy": self.is_healthy(),
            "total_connections": len(self.connections),
            "active_connections": sum(1 for conn in self.connections.values() if conn.is_connected),
            "connections": connection_health
        }