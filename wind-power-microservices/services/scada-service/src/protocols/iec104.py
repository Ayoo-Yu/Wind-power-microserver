"""
IEC 60870-5-104 Protocol Adapter for SCADA Data Service.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import logging

# Note: c104 library would need to be installed
# For now, we'll create a mock implementation that simulates the protocol behavior

from .base import BaseProtocolAdapter, ProtocolConnection, ConnectionStatus
from ..utils import get_logger
from ..models import ScadaDataPoint, DataPointType


logger = get_logger(__name__)


class IEC104DataType(Enum):
    """IEC 60870-5-104 data types."""
    SINGLE_POINT_INFO = "M_SP_NA_1"        # 1
    DOUBLE_POINT_INFO = "M_DP_NA_1"        # 3
    MEASURAND_NORMALISED = "M_ME_NA_1"     # 9
    MEASURAND_SCALED = "M_ME_NB_1"         # 11
    MEASURAND_SHORT = "M_ME_NC_1"          # 13
    INTEGRATED_TOTALS = "M_IT_NA_1"        # 15
    SINGLE_COMMAND = "C_SC_NA_1"           # 45
    DOUBLE_COMMAND = "C_DC_NA_1"           # 46
    REGULATING_STEP = "C_RC_NA_1"          # 47
    SET_POINT_NORMALISED = "C_SE_NA_1"     # 48
    SET_POINT_SCALED = "C_SE_NB_1"         # 49
    SET_POINT_SHORT = "C_SE_NC_1"          # 50


class IEC104Connection(ProtocolConnection):
    """IEC 60870-5-104 protocol connection."""

    def __init__(self, connection_id: str, config: Dict[str, Any]):
        super().__init__(connection_id, config)
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 2404)
        self.originator_address = config.get("originator_address", 0)
        self.common_address = config.get("common_address", 1)
        self.cause_of_transmission = config.get("cause_of_transmission", 3)  # Spontaneous

        # Mock client for simulation (would be real c104.Client in production)
        self.client = None
        self.data_points_cache: Dict[str, Dict[str, Any]] = {}
        self.connection_start_time = None
        self.last_interrogation_time = None
        self.interrogation_interval = config.get("interrogation_interval", 300)  # 5 minutes

        # Simulate some realistic data points that would exist in a wind farm
        self._initialize_mock_data_points()

    def _initialize_mock_data_points(self):
        """Initialize mock data points for simulation."""
        # These would normally come from the database configuration
        self.data_points_cache = {
            "10001": {"name": "WT001.Power", "type": "M_ME_NC_1", "unit": "MW", "scale": 0.001},
            "10002": {"name": "WT001.WindSpeed", "type": "M_ME_NC_1", "unit": "m/s", "scale": 0.1},
            "10003": {"name": "WT001.RotorSpeed", "type": "M_ME_NC_1", "unit": "rpm", "scale": 1.0},
            "10004": {"name": "WT001.Status", "type": "M_SP_NA_1", "unit": "", "scale": 1.0},
            "10005": {"name": "WT001.Temperature", "type": "M_ME_NC_1", "unit": "°C", "scale": 0.1},
            "10006": {"name": "WT001.Vibration", "type": "M_ME_NC_1", "unit": "mm/s", "scale": 0.01},
            "10007": {"name": "WT001.GridVoltage", "type": "M_ME_NC_1", "unit": "V", "scale": 1.0},
            "10008": {"name": "WT001.GridFrequency", "type": "M_ME_NC_1", "unit": "Hz", "scale": 0.01},
        }

    async def connect(self) -> bool:
        """Connect to IEC 104 server."""
        try:
            self.update_status(ConnectionStatus.CONNECTING)
            self.logger.info(f"Connecting to IEC 104 server {self.host}:{self.port}")

            # In production, this would use real c104 library:
            # self.client = c104.Client(tick_rate_ms=1000, command_timeout_ms=10000)
            # self.client.originator_address = self.originator_address
            # self.client.connect(host=self.host, port=self.port)

            # Simulate connection process
            await asyncio.sleep(2)  # Simulate connection time

            # Simulate successful connection
            self.connection_start_time = datetime.utcnow()
            self.is_connected = True
            self.update_status(ConnectionStatus.CONNECTED)

            # Start data collection tasks
            asyncio.create_task(self._data_collection_loop())
            asyncio.create_task(self._interrogation_loop())

            self.logger.info(f"Successfully connected to IEC 104 server {self.host}:{self.port}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to IEC 104 server: {e}")
            self.record_error(str(e))
            self.update_status(ConnectionStatus.ERROR, {"error": str(e)})
            return False

    async def disconnect(self) -> bool:
        """Disconnect from IEC 104 server."""
        try:
            self.logger.info(f"Disconnecting from IEC 104 server {self.host}:{self.port}")

            # In production:
            # if self.client:
            #     self.client.disconnect()
            #     self.client = None

            self.is_connected = False
            self.connection_start_time = None
            self.update_status(ConnectionStatus.DISCONNECTED)

            self.logger.info(f"Disconnected from IEC 104 server {self.host}:{self.port}")
            return True

        except Exception as e:
            self.logger.error(f"Error disconnecting from IEC 104 server: {e}")
            return False

    async def read_data(self) -> List[ScadaDataPoint]:
        """Read data from IEC 104 server."""
        if not self.is_connected:
            return []

        try:
            # In production, this would read from the actual c104 client:
            # data_points = []
            # for station in self.client.stations:
            #     for io in station.io_objects:
            #         if io.is_transmission:
            #             data_point = self._convert_to_scada_data_point(io)
            #             data_points.append(data_point)
            # return data_points

            # For simulation, generate realistic data
            return await self._generate_mock_data()

        except Exception as e:
            self.logger.error(f"Error reading data from IEC 104: {e}")
            self.record_error(str(e))
            return []

    async def write_data(self, data_points: List[Dict[str, Any]]) -> bool:
        """Write data to IEC 104 server (for control commands)."""
        if not self.is_connected:
            return False

        try:
            self.logger.info(f"Writing {len(data_points)} data points to IEC 104 server")

            # In production, this would write to the actual c104 client:
            # for point in data_points:
            #     ioa = point.get("point_address")
            #     value = point.get("value")
            #     # Send command to appropriate IO object
            #     pass

            # Simulate write operation
            await asyncio.sleep(0.1)

            self.logger.info(f"Successfully wrote {len(data_points)} data points")
            return True

        except Exception as e:
            self.logger.error(f"Error writing data to IEC 104: {e}")
            return False

    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        if not self.is_connected:
            return False

        # Check if we've received data recently (within last 5 minutes)
        if self.last_data_time:
            time_since_last_data = (datetime.utcnow() - self.last_data_time).total_seconds()
            if time_since_last_data > 300:  # 5 minutes
                return False

        return self.error_count < 10  # Allow some errors but not too many

    async def _data_collection_loop(self):
        """Main data collection loop."""
        self.logger.info(f"Starting data collection loop for {self.connection_id}")

        while self.is_connected:
            try:
                # Read data from the protocol
                data_points = await self.read_data()

                if data_points:
                    self.record_data_received()
                    await self._notify_data_callbacks(data_points)

                    # Log periodic statistics
                    if self.data_count % 100 == 0:
                        self.logger.info(f"Collected {self.data_count} data points from {self.connection_id}")

                # Wait before next collection cycle
                await asyncio.sleep(1)  # 1 second collection interval

            except Exception as e:
                self.logger.error(f"Error in data collection loop: {e}")
                self.record_error(str(e))
                await asyncio.sleep(5)  # Wait longer on error

    async def _interrogation_loop(self):
        """Periodic interrogation (general call) loop."""
        self.logger.info(f"Starting interrogation loop for {self.connection_id}")

        while self.is_connected:
            try:
                current_time = datetime.utcnow()

                # Check if it's time for interrogation
                if (self.last_interrogation_time is None or
                    (current_time - self.last_interrogation_time).total_seconds() >= self.interrogation_interval):

                    self.logger.info(f"Performing interrogation for {self.connection_id}")
                    await self._perform_interrogation()
                    self.last_interrogation_time = current_time

                # Wait before next check
                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                self.logger.error(f"Error in interrogation loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def _perform_interrogation(self):
        """Perform general interrogation (GI)."""
        try:
            # In production, this would send C_IC_NA_1 command:
            # if self.client and self.client.stations:
            #     for station in self.client.stations:
            #         station.send_command(c104.C_IC_NA_1, ca=station.common_address)

            self.logger.info(f"General interrogation completed for {self.connection_id}")

        except Exception as e:
            self.logger.error(f"Error during interrogation: {e}")

    async def _generate_mock_data(self) -> List[ScadaDataPoint]:
        """Generate realistic mock data for simulation."""
        import random
        import math

        data_points = []
        current_time = datetime.utcnow()

        # Simulate wind speed variation (realistic pattern)
        base_wind_speed = 8.5  # m/s
        wind_variation = 2.0 * math.sin(current_time.timestamp() / 300)  # 5-minute cycle
        current_wind_speed = base_wind_speed + wind_variation + random.uniform(-0.5, 0.5)
        current_wind_speed = max(0, min(25, current_wind_speed))  # Limit to realistic range

        # Generate data for each configured point
        for address, point_config in self.data_points_cache.items():
            point_name = point_config["name"]
            point_type = point_config["type"]
            scale = point_config["scale"]
            unit = point_config["unit"]

            # Generate realistic values based on point type
            if "Power" in point_name:
                # Power output based on wind speed with realistic curve
                if current_wind_speed < 3.0:  # Cut-in speed
                    value = 0.0
                elif current_wind_speed > 25.0:  # Cut-out speed
                    value = 0.0
                else:
                    # Simplified power curve
                    if current_wind_speed < 12.0:
                        value = 2.5 * ((current_wind_speed - 3.0) / 9.0) ** 3  # Cubic relationship
                    else:
                        value = 2.5  # Rated power
                    value += random.uniform(-0.1, 0.1)  # Small variation
                    value = max(0, min(2.5, value))

            elif "WindSpeed" in point_name:
                value = current_wind_speed

            elif "RotorSpeed" in point_name:
                # Rotor speed related to wind speed
                if current_wind_speed < 3.0:
                    value = 0.0
                else:
                    value = 15.0 + (current_wind_speed - 3.0) * 1.5  # Approximate relationship
                    value += random.uniform(-0.5, 0.5)
                    value = max(0, min(25, value))

            elif "Status" in point_name:
                # Binary status (running/stopped)
                value = current_wind_speed >= 3.0 and current_wind_speed <= 25.0

            elif "Temperature" in point_name:
                # Nacelle temperature (environmental + operational)
                ambient_temp = 20.0  # Assume 20°C ambient
                operational_heat = value * 2.0 if "Power" in point_name else 0.0
                value = ambient_temp + operational_heat + random.uniform(-2, 2)

            elif "Vibration" in point_name:
                # Vibration level (low when running smoothly)
                if current_wind_speed >= 3.0 and current_wind_speed <= 25.0:
                    value = 2.0 + random.uniform(-0.5, 0.5)  # Normal operation
                else:
                    value = 5.0 + random.uniform(-1, 1)  # Higher when not running

            elif "GridVoltage" in point_name:
                value = 690.0 + random.uniform(-10, 10)  # Typical wind turbine grid voltage

            elif "GridFrequency" in point_name:
                value = 50.0 + random.uniform(-0.2, 0.2)  # Grid frequency (50Hz)

            else:
                # Default random value
                value = random.uniform(0, 100)

            # Apply scaling
            scaled_value = value / scale if scale != 0 else value

            # Determine quality (mostly good, occasional bad data)
            quality = "good"
            is_alarm = False
            if random.random() < 0.05:  # 5% chance of bad data
                quality = "bad"
            elif random.random() < 0.1:  # 10% chance of uncertain data
                quality = "uncertain"

            # Create data point
            data_point = ScadaDataPoint(
                point_id=f"{self.connection_id}_{address}",
                point_name=point_name,
                value=scaled_value,
                raw_value=value,
                quality=quality,
                timestamp=current_time,
                is_alarm=is_alarm,
                connection_id=self.connection_id,
                wind_farm_id=self.config.get("wind_farm_id", "unknown"),
                turbine_id="WT001"  # Would come from configuration
            )

            data_points.append(data_point)

        return data_points

    def _convert_to_scada_data_point(self, io_object) -> ScadaDataPoint:
        """Convert IEC 104 IO object to SCADA data point (for production use)."""
        # This would be implemented with real c104 library objects
        pass


class IEC104ProtocolAdapter(BaseProtocolAdapter):
    """IEC 60870-5-104 Protocol Adapter."""

    def __init__(self):
        super().__init__("iec104")
        self.logger = get_logger(__name__)

    async def create_connection(self, connection_id: str, config: Dict[str, Any]) -> IEC104Connection:
        """Create a new IEC 104 connection."""
        return IEC104Connection(connection_id, config)

    def get_protocol_info(self) -> Dict[str, Any]:
        """Get IEC 104 protocol information."""
        return {
            "protocol_type": "iec104",
            "name": "IEC 60870-5-104",
            "description": "International standard for telecontrol equipment and systems",
            "transport": "TCP/IP",
            "default_port": 2404,
            "features": [
                "Real-time data exchange",
                "Event-driven communication",
                "Time synchronization",
                "File transfer",
                "Command transmission"
            ],
            "data_types": [
                "Single point information",
                "Double point information",
                "Measured values (normalized, scaled, short)",
                "Integrated totals",
                "Protection events"
            ]
        }