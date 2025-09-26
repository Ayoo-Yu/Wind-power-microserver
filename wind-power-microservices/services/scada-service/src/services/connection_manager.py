"""
SCADA Connection Manager - Manages multiple SCADA protocol connections.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import logging

from ..protocols import IEC104ProtocolAdapter, BaseProtocolAdapter
from ..database import ScadaConnection, data_point_crud, wind_farm_crud
from ..models import ScadaConnectionResponse, DataPointResponse, ScadaDataPoint, ConnectionStatus
from ..exceptions import (
    ScadaConnectionNotFoundException,
    DuplicateScadaConnectionException,
    InvalidScadaDataException,
    ValidationException
)
from ..utils import get_logger, create_influxdb_manager, create_kafka_manager, create_scada_data_processor


logger = get_logger(__name__)


class ConnectionManager:
    """Manages SCADA protocol connections and data processing."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.protocol_adapters: Dict[str, BaseProtocolAdapter] = {}
        self.influxdb_manager = create_influxdb_manager()
        self.kafka_manager = create_kafka_manager()
        self.data_processor = create_scada_data_processor()
        self._data_callbacks: List[Callable] = []
        self._alarm_callbacks: List[Callable] = []
        self._connection_status_callbacks: List[Callable] = []
        self._running = False
        self._monitoring_task = None
        self._data_buffer: List[ScadaDataPoint] = []
        self._buffer_size = 1000
        self._batch_size = 100
        self._batch_interval = 5  # seconds

        # Initialize protocol adapters
        self._initialize_protocols()

    def _initialize_protocols(self):
        """Initialize protocol adapters."""
        try:
            # IEC 60870-5-104 Protocol
            iec104_adapter = IEC104ProtocolAdapter()
            self.protocol_adapters["iec104"] = iec104_adapter

            self.logger.info("Protocol adapters initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize protocol adapters: {e}")
            raise

    def add_data_callback(self, callback: Callable):
        """Add data callback for real-time data processing."""
        self._data_callbacks.append(callback)

    def add_alarm_callback(self, callback: Callable):
        """Add alarm callback for alarm processing."""
        self._alarm_callbacks.append(callback)

    def add_connection_status_callback(self, callback: Callable):
        """Add connection status callback."""
        self._connection_status_callbacks.append(callback)

    async def initialize(self):
        """Initialize connection manager."""
        try:
            self.logger.info("Initializing SCADA connection manager...")

            # Initialize InfluxDB
            await self.influxdb_manager.initialize()

            # Initialize Kafka producer
            await self.kafka_manager.initialize_producer()

            # Add callbacks to protocol adapters
            for adapter in self.protocol_adapters.values():
                for connection in adapter.get_all_connections().values():
                    connection.add_data_callback(self._handle_data_points)
                    connection.add_status_callback(self._handle_connection_status_change)

            self._running = True
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

            self.logger.info("SCADA connection manager initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize connection manager: {e}")
            raise

    async def shutdown(self):
        """Shutdown connection manager."""
        try:
            self.logger.info("Shutting down SCADA connection manager...")

            self._running = False

            # Stop monitoring task
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass

            # Stop all protocol connections
            await self.stop_all_connections()

            # Close InfluxDB
            await self.influxdb_manager.close()

            # Close Kafka
            await self.kafka_manager.close()

            self.logger.info("SCADA connection manager shutdown completed")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    async def create_connection(self, db, connection_data: Dict[str, Any], current_user_id: str) -> ScadaConnectionResponse:
        """Create a new SCADA connection."""
        try:
            # Validate connection data
            await self._validate_connection_data(db, connection_data)

            # Check for duplicate connection
            existing = await self._get_connection_by_host_port(db, connection_data["host"], connection_data["port"])
            if existing:
                raise DuplicateScadaConnectionException(connection_data["wind_farm_id"], connection_data["host"], connection_data["port"])

            # Check wind farm exists
            wind_farm = await wind_farm_crud.get(db, connection_data["wind_farm_id"])
            if not wind_farm:
                raise ValidationException(f"Wind farm {connection_data['wind_farm_id']} not found")

            # Create connection in database
            connection = await scada_connection_crud.create(db, connection_data)

            # Add to protocol adapter
            adapter = self.protocol_adapters.get(connection_data.get("protocol", "iec104"))
            if not adapter:
                raise ValidationException(f"Unsupported protocol: {connection_data.get('protocol')}")

            # Create protocol connection
            protocol_config = {
                "host": connection_data["host"],
                "port": connection_data["port"],
                "connection_timeout": connection_data.get("connection_timeout", 30),
                "max_reconnect_attempts": connection_data.get("max_reconnect_attempts", 5),
                "reconnect_delay": connection_data.get("reconnect_delay", 10),
                "wind_farm_id": connection_data["wind_farm_id"],
                "wind_farm_code": wind_farm.code,
            }

            protocol_connection = await adapter.add_connection(connection.id, protocol_config)

            # Add callbacks
            protocol_connection.add_data_callback(self._handle_data_points)
            protocol_connection.add_status_callback(self._handle_connection_status_change)

            self.logger.info(f"Created SCADA connection: {connection.name} ({connection.id})")

            return ScadaConnectionResponse.from_orm(connection)

        except (ValidationException, DuplicateScadaConnectionException):
            raise
        except Exception as e:
            self.logger.error(f"Failed to create SCADA connection: {e}")
            raise Exception("Failed to create SCADA connection")

    async def update_connection(self, db, connection_id: str, update_data: Dict[str, Any], current_user_id: str) -> ScadaConnectionResponse:
        """Update SCADA connection."""
        try:
            # Get existing connection
            connection = await scada_connection_crud.get(db, connection_id)
            if not connection:
                raise ScadaConnectionNotFoundException(connection_id)

            # Update connection
            updated_connection = await scada_connection_crud.update(db, connection, update_data)

            # Update protocol connection if needed
            if any(key in update_data for key in ["host", "port", "connection_timeout", "max_reconnect_attempts", "reconnect_delay"]):
                adapter = self.protocol_adapters.get(connection.protocol)
                if adapter:
                    protocol_connection = adapter.get_connection(connection_id)
                    if protocol_connection:
                        # Reconnect with new configuration
                        await protocol_connection.disconnect()
                        await asyncio.sleep(1)
                        await protocol_connection.connect()

            self.logger.info(f"Updated SCADA connection: {connection.name} ({connection_id})")

            return ScadaConnectionResponse.from_orm(updated_connection)

        except ScadaConnectionNotFoundException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to update SCADA connection {connection_id}: {e}")
            raise Exception("Failed to update SCADA connection")

    async def delete_connection(self, db, connection_id: str, current_user_id: str) -> bool:
        """Delete SCADA connection."""
        try:
            # Get connection
            connection = await scada_connection_crud.get(db, connection_id)
            if not connection:
                raise ScadaConnectionNotFoundException(connection_id)

            # Remove from protocol adapter
            adapter = self.protocol_adapters.get(connection.protocol)
            if adapter:
                await adapter.remove_connection(connection_id)

            # Delete from database
            await scada_connection_crud.delete(db, connection_id)

            self.logger.info(f"Deleted SCADA connection: {connection.name} ({connection_id})")

            return True

        except ScadaConnectionNotFoundException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to delete SCADA connection {connection_id}: {e}")
            raise Exception("Failed to delete SCADA connection")

    async def get_connection(self, db, connection_id: str) -> Optional[ScadaConnectionResponse]:
        """Get SCADA connection by ID."""
        try:
            connection = await scada_connection_crud.get(db, connection_id)
            if not connection:
                return None

            return ScadaConnectionResponse.from_orm(connection)

        except Exception as e:
            self.logger.error(f"Failed to get SCADA connection {connection_id}: {e}")
            raise Exception("Failed to get SCADA connection")

    async def get_connections(self, db, filter_params: Optional[Dict[str, Any]] = None, pagination: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get SCADA connections with filtering and pagination."""
        try:
            # Build query
            query = select(ScadaConnection)

            # Apply filters
            if filter_params:
                if filter_params.get("wind_farm_id"):
                    query = query.where(ScadaConnection.wind_farm_id == filter_params["wind_farm_id"])
                if filter_params.get("protocol"):
                    query = query.where(ScadaConnection.protocol == filter_params["protocol"])
                if filter_params.get("status"):
                    query = query.where(ScadaConnection.status == filter_params["status"])
                if filter_params.get("is_active") is not None:
                    query = query.where(ScadaConnection.is_active == filter_params["is_active"])

            # Get total count
            count_query = select(func.count(ScadaConnection.id))
            if filter_params:
                if filter_params.get("wind_farm_id"):
                    count_query = count_query.where(ScadaConnection.wind_farm_id == filter_params["wind_farm_id"])
                if filter_params.get("protocol"):
                    count_query = count_query.where(ScadaConnection.protocol == filter_params["protocol"])
                if filter_params.get("status"):
                    count_query = count_query.where(ScadaConnection.status == filter_params["status"])
                if filter_params.get("is_active") is not None:
                    count_query = count_query.where(ScadaConnection.is_active == filter_params["is_active"])

            total_result = await db.execute(count_query)
            total = total_result.scalar()

            # Apply pagination
            if pagination:
                query = query.offset((pagination["page"] - 1) * pagination["size"]).limit(pagination["size"])

            # Execute query
            result = await db.execute(query)
            connections = result.scalars().all()

            # Convert to response models
            items = [ScadaConnectionResponse.from_orm(conn) for conn in connections]

            # Calculate pagination info
            pages = (total + pagination["size"] - 1) // pagination["size"] if pagination else 1
            has_next = pagination["page"] < pages if pagination else False
            has_prev = pagination["page"] > 1 if pagination else False

            return {
                "items": items,
                "total": total,
                "page": pagination["page"] if pagination else 1,
                "size": pagination["size"] if pagination else total,
                "pages": pages,
                "has_next": has_next,
                "has_prev": has_prev,
            }

        except Exception as e:
            self.logger.error(f"Failed to get SCADA connections: {e}")
            raise Exception("Failed to get SCADA connections")

    async def start_connection(self, connection_id: str) -> bool:
        """Start SCADA connection."""
        try:
            # Find connection in adapters
            for adapter in self.protocol_adapters.values():
                connection = adapter.get_connection(connection_id)
                if connection:
                    success = await connection.connect()
                    if success:
                        self.logger.info(f"Started SCADA connection: {connection_id}")
                    return success

            self.logger.warning(f"SCADA connection not found for start: {connection_id}")
            return False

        except Exception as e:
            self.logger.error(f"Failed to start SCADA connection {connection_id}: {e}")
            return False

    async def stop_connection(self, connection_id: str) -> bool:
        """Stop SCADA connection."""
        try:
            # Find connection in adapters
            for adapter in self.protocol_adapters.values():
                connection = adapter.get_connection(connection_id)
                if connection:
                    success = await connection.disconnect()
                    if success:
                        self.logger.info(f"Stopped SCADA connection: {connection_id}")
                    return success

            self.logger.warning(f"SCADA connection not found for stop: {connection_id}")
            return False

        except Exception as e:
            self.logger.error(f"Failed to stop SCADA connection {connection_id}: {e}")
            return False

    async def start_all_connections(self):
        """Start all SCADA connections."""
        try:
            self.logger.info("Starting all SCADA connections...")

            for adapter in self.protocol_adapters.values():
                await adapter.start_all_connections()

            self.logger.info("All SCADA connections started")

        except Exception as e:
            self.logger.error(f"Failed to start all SCADA connections: {e}")

    async def stop_all_connections(self):
        """Stop all SCADA connections."""
        try:
            self.logger.info("Stopping all SCADA connections...")

            for adapter in self.protocol_adapters.values():
                await adapter.stop_all_connections()

            self.logger.info("All SCADA connections stopped")

        except Exception as e:
            self.logger.error(f"Failed to stop all SCADA connections: {e}")

    def get_connection_statistics(self) -> Dict[str, Any]:
        """Get connection manager statistics."""
        try:
            total_connections = 0
            active_connections = 0
            protocol_stats = {}

            for protocol, adapter in self.protocol_adapters.items():
                stats = adapter.get_statistics()
                protocol_stats[protocol] = stats
                total_connections += stats["total_connections"]
                active_connections += stats["active_connections"]

            return {
                "total_connections": total_connections,
                "active_connections": active_connections,
                "protocols": protocol_stats,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Failed to get connection statistics: {e}")
            return {
                "total_connections": 0,
                "active_connections": 0,
                "protocols": {},
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    # Private helper methods

    async def _validate_connection_data(self, db, connection_data: Dict[str, Any]):
        """Validate SCADA connection data."""
        required_fields = ["name", "wind_farm_id", "protocol", "host", "port"]
        for field in required_fields:
            if field not in connection_data or not connection_data[field]:
                raise InvalidScadaDataException(f"Missing required field: {field}")

        # Validate protocol
        valid_protocols = ["iec104", "modbus_tcp", "dnp3"]
        if connection_data["protocol"] not in valid_protocols:
            raise InvalidScadaDataException(f"Unsupported protocol: {connection_data['protocol']}")

        # Validate host
        host = connection_data["host"]
        if not host or len(host.strip()) == 0:
            raise InvalidScadaDataException("Host cannot be empty")

        # Validate port
        port = connection_data["port"]
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise InvalidScadaDataException("Port must be between 1 and 65535")

        # Validate timeout
        timeout = connection_data.get("connection_timeout", 30)
        if not isinstance(timeout, int) or timeout < 5 or timeout > 300:
            raise InvalidScadaDataException("Connection timeout must be between 5 and 300 seconds")

    async def _get_connection_by_host_port(self, db, host: str, port: int) -> Optional[ScadaConnection]:
        """Get connection by host and port."""
        from sqlalchemy import select
        result = await db.execute(
            select(ScadaConnection).where(
                ScadaConnection.host == host,
                ScadaConnection.port == port
            )
        )
        return result.scalar_one_or_none()

    async def _handle_data_points(self, data_points: List[ScadaDataPoint]):
        """Handle incoming data points."""
        try:
            # Add to buffer
            self._data_buffer.extend(data_points)

            # Process alarms
            alarm_points = [point for point in data_points if point.is_alarm]
            if alarm_points:
                await self._process_alarms(alarm_points)

            # Buffer management
            if len(self._data_buffer) >= self._buffer_size:
                await self._flush_data_buffer()

            # Notify callbacks
            for callback in self._data_callbacks:
                try:
                    await callback(data_points)
                except Exception as e:
                    self.logger.error(f"Error in data callback: {e}")

        except Exception as e:
            self.logger.error(f"Error handling data points: {e}")

    async def _handle_connection_status_change(self, connection_id: str, status: ConnectionStatus, details: Optional[Dict[str, Any]] = None):
        """Handle connection status changes."""
        try:
            # Update database
            from sqlalchemy import select
            async for db in self._get_db_session():
                result = await db.execute(
                    select(ScadaConnection).where(ScadaConnection.id == connection_id)
                )
                connection = result.scalar_one_or_none()
                if connection:
                    connection.status = status.value
                    if status == ConnectionStatus.CONNECTED:
                        connection.last_connected_at = datetime.utcnow()
                    await db.commit()
                    break

            # Publish event to Kafka
            event_data = {
                "event_type": "connection_status_changed",
                "connection_id": connection_id,
                "status": status.value,
                "details": details,
                "timestamp": datetime.utcnow().isoformat()
            }

            await self.kafka_manager.send_message(
                self.settings.kafka_topics["scada_events"],
                event_data
            )

            # Notify callbacks
            for callback in self._connection_status_callbacks:
                try:
                    await callback(connection_id, status, details)
                except Exception as e:
                    self.logger.error(f"Error in connection status callback: {e}")

        except Exception as e:
            self.logger.error(f"Error handling connection status change: {e}")

    async def _process_alarms(self, alarm_points: List[ScadaDataPoint]):
        """Process alarm data points."""
        try:
            for point in alarm_points:
                alarm_data = {
                    "alarm_code": f"ALARM_{point.point_id}",
                    "alarm_name": f"Alarm: {point.point_name}",
                    "description": f"High/Low threshold exceeded for {point.point_name}",
                    "severity": "critical" if point.quality == "bad" else "warning",
                    "wind_farm_id": point.wind_farm_id,
                    "turbine_id": point.turbine_id,
                    "point_id": point.point_id,
                    "actual_value": point.value,
                    "triggered_at": point.timestamp.isoformat()
                }

                # Publish alarm to Kafka
                await self.kafka_manager.send_message(
                    self.settings.kafka_topics["scada_alarms"],
                    alarm_data
                )

                # Notify alarm callbacks
                for callback in self._alarm_callbacks:
                    try:
                        await callback(alarm_data)
                    except Exception as e:
                        self.logger.error(f"Error in alarm callback: {e}")

        except Exception as e:
            self.logger.error(f"Error processing alarms: {e}")

    async def _flush_data_buffer(self):
        """Flush data buffer to InfluxDB and Kafka."""
        try:
            if not self._data_buffer:
                return

            # Convert to InfluxDB points
            influx_points = []
            for point in self._data_buffer:
                measurement = "scada_data"
                if point.point_name.lower().endswith("power"):
                    measurement = "power_data"
                elif point.point_name.lower().endswith("status"):
                    measurement = "status_data"

                influx_points.append({
                    "measurement": measurement,
                    "wind_farm_id": point.wind_farm_id,
                    "connection_id": point.connection_id,
                    "turbine_id": point.turbine_id,
                    "point_id": point.point_id,
                    "point_name": point.point_name,
                    "value": point.value,
                    "quality": point.quality,
                    "timestamp": point.timestamp
                })

            # Write to InfluxDB
            await self.influxdb_manager.write_points(influx_points)

            # Publish to Kafka
            for point in self._data_buffer:
                kafka_message = {
                    "type": "scada_data",
                    "point_id": point.point_id,
                    "point_name": point.point_name,
                    "value": point.value,
                    "quality": point.quality,
                    "timestamp": point.timestamp.isoformat(),
                    "wind_farm_id": point.wind_farm_id,
                    "connection_id": point.connection_id,
                    "turbine_id": point.turbine_id
                }

                await self.kafka_manager.send_message(
                    self.settings.kafka_topics["scada_realtime"],
                    kafka_message
                )

            self.logger.debug(f"Flushed {len(self._data_buffer)} data points")
            self._data_buffer.clear()

        except Exception as e:
            self.logger.error(f"Error flushing data buffer: {e}")

    async def _monitoring_loop(self):
        """Main monitoring loop for periodic tasks."""
        self.logger.info("Starting SCADA connection monitoring loop")

        while self._running:
            try:
                # Periodic data buffer flush
                if self._data_buffer:
                    await self._flush_data_buffer()

                # Connection health checks
                await self._perform_health_checks()

                # Statistics collection
                await self._collect_statistics()

                # Wait for next cycle
                await asyncio.sleep(self._batch_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self._batch_interval)

        self.logger.info("SCADA connection monitoring loop stopped")

    async def _perform_health_checks(self):
        """Perform health checks on all connections."""
        try:
            for adapter in self.protocol_adapters.values():
                for connection_id, connection in adapter.get_all_connections().items():
                    if not connection.is_healthy():
                        self.logger.warning(f"Connection {connection_id} is unhealthy, attempting reconnection")
                        await connection.reconnect()

        except Exception as e:
            self.logger.error(f"Error performing health checks: {e}")

    async def _collect_statistics(self):
        """Collect connection statistics."""
        try:
            # This would collect and store statistics in the database
            # For now, just log the statistics
            stats = self.get_connection_statistics()
            self.logger.debug(f"Connection statistics: {stats}")

        except Exception as e:
            self.logger.error(f"Error collecting statistics: {e}")

    async def _get_db_session(self):
        """Get database session generator."""
        from .database import get_db_session
        async for session in get_db_session():
            yield session

    @property
    def settings(self):
        """Get settings."""
        from .config import get_settings
        return get_settings()