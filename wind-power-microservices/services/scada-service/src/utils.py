"""
Utility functions for SCADA Data Service.
"""

import logging
import redis
import aioredis
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from .config import get_settings
from .database import wind_farm_crud


# Logging Configuration
def get_logger(name: str) -> logging.Logger:
    """Get configured logger instance."""
    settings = get_settings()

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# Redis Manager
class RedisManager:
    """Redis connection manager."""

    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        self.logger = get_logger(__name__)

    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = aioredis.from_url(
                self.settings.redis_url,
                max_connections=self.settings.redis_pool_size,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            self.logger.info("Redis connection pool initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize Redis: {e}")
            raise Exception(f"Redis initialization failed: {str(e)}")

    async def get_client(self) -> aioredis.Redis:
        """Get Redis client."""
        if not self.redis_client:
            await self.initialize()
        return self.redis_client

    async def health_check(self) -> bool:
        """Check Redis health."""
        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            self.logger.error(f"Redis health check failed: {e}")
            return False

    async def close(self):
        """Close Redis connections."""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("Redis connections closed")


def create_redis_manager() -> RedisManager:
    """Create Redis manager instance."""
    return RedisManager()


# InfluxDB Manager
class InfluxDBManager:
    """InfluxDB time-series database manager."""

    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self.write_api = None
        self.query_api = None
        self.logger = get_logger(__name__)

    async def initialize(self):
        """Initialize InfluxDB connection."""
        try:
            from influxdb_client import InfluxDBClient
            from influxdb_client.client.write_api import SYNCHRONOUS

            self.client = InfluxDBClient(
                url=self.settings.influxdb_url,
                token=self.settings.influxdb_token,
                org=self.settings.influxdb_org,
                timeout=30_000,  # 30 seconds
            )

            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.client.query_api()

            self.logger.info("InfluxDB client initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize InfluxDB: {e}")
            raise Exception(f"InfluxDB initialization failed: {str(e)}")

    async def write_points(self, points: List[Dict[str, Any]]):
        """Write data points to InfluxDB."""
        try:
            if not self.write_api:
                await self.initialize()

            from influxdb_client import Point

            influx_points = []
            for point_data in points:
                point = (
                    Point(point_data["measurement"])
                    .tag("wind_farm_id", point_data["wind_farm_id"])
                    .tag("connection_id", point_data["connection_id"])
                    .tag("turbine_id", point_data.get("turbine_id", ""))
                    .tag("point_id", point_data["point_id"])
                    .tag("point_name", point_data["point_name"])
                    .field("value", point_data["value"])
                    .field("quality", point_data["quality"])
                    .time(point_data["timestamp"])
                )
                influx_points.append(point)

            self.write_api.write(
                bucket=self.settings.influxdb_bucket,
                org=self.settings.influxdb_org,
                record=influx_points
            )

        except Exception as e:
            self.logger.error(f"Failed to write points to InfluxDB: {e}")
            raise

    async def query_data(self, query: str) -> List[Dict[str, Any]]:
        """Query data from InfluxDB."""
        try:
            if not self.query_api:
                await self.initialize()

            result = self.query_api.query(org=self.settings.influxdb_org, query=query)

            data_points = []
            for table in result:
                for record in table.records:
                    data_points.append({
                        "time": record.get_time(),
                        "wind_farm_id": record.values.get("wind_farm_id"),
                        "connection_id": record.values.get("connection_id"),
                        "turbine_id": record.values.get("turbine_id"),
                        "point_id": record.values.get("point_id"),
                        "point_name": record.values.get("point_name"),
                        "value": record.get_value(),
                        "quality": record.values.get("quality"),
                    })

            return data_points

        except Exception as e:
            self.logger.error(f"Failed to query InfluxDB: {e}")
            raise

    async def health_check(self) -> bool:
        """Check InfluxDB health."""
        try:
            if not self.client:
                await self.initialize()

            health = self.client.health()
            return health.status == "pass"

        except Exception as e:
            self.logger.error(f"InfluxDB health check failed: {e}")
            return False

    async def close(self):
        """Close InfluxDB connection."""
        if self.client:
            self.client.close()
            self.logger.info("InfluxDB connection closed")


def create_influxdb_manager() -> InfluxDBManager:
    """Create InfluxDB manager instance."""
    return InfluxDBManager()


# Kafka Manager
class KafkaManager:
    """Kafka message broker manager."""

    def __init__(self):
        self.settings = get_settings()
        self.producer = None
        self.consumer = None
        self.logger = get_logger(__name__)

    async def initialize_producer(self):
        """Initialize Kafka producer."""
        try:
            from aiokafka import AIOKafkaProducer
            import json

            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                compression_type='gzip',
                max_batch_size=16384,  # 16KB
                linger_ms=100,  # 100ms batching
            )

            await self.producer.start()
            self.logger.info("Kafka producer initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize Kafka producer: {e}")
            raise

    async def initialize_consumer(self, topics: List[str], group_id: str):
        """Initialize Kafka consumer."""
        try:
            from aiokafka import AIOKafkaConsumer
            import json

            self.consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.settings.kafka_bootstrap_servers,
                group_id=group_id,
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
            )

            await self.consumer.start()
            self.logger.info(f"Kafka consumer initialized for topics: {topics}")

        except Exception as e:
            self.logger.error(f"Failed to initialize Kafka consumer: {e}")
            raise

    async def send_message(self, topic: str, message: Dict[str, Any]):
        """Send message to Kafka topic."""
        try:
            if not self.producer:
                await self.initialize_producer()

            await self.producer.send_and_wait(topic, message)
            self.logger.debug(f"Message sent to Kafka topic {topic}")

        except Exception as e:
            self.logger.error(f"Failed to send message to Kafka: {e}")
            raise

    async def consume_messages(self):
        """Consume messages from Kafka."""
        try:
            if not self.consumer:
                raise Exception("Kafka consumer not initialized")

            async for message in self.consumer:
                self.logger.debug(f"Received message from {message.topic}: {message.value}")
                yield message.value

        except Exception as e:
            self.logger.error(f"Failed to consume messages from Kafka: {e}")
            raise

    async def health_check(self) -> bool:
        """Check Kafka health."""
        try:
            if self.producer:
                # Test by sending a ping message
                ping_message = {
                    "type": "ping",
                    "timestamp": datetime.utcnow().isoformat(),
                    "service": "scada-service"
                }
                await self.send_message("health.check", ping_message)
                return True
            return False

        except Exception as e:
            self.logger.error(f"Kafka health check failed: {e}")
            return False

    async def close(self):
        """Close Kafka connections."""
        try:
            if self.producer:
                await self.producer.stop()
                self.logger.info("Kafka producer closed")

            if self.consumer:
                await self.consumer.stop()
                self.logger.info("Kafka consumer closed")

        except Exception as e:
            self.logger.error(f"Error closing Kafka connections: {e}")


def create_kafka_manager() -> KafkaManager:
    """Create Kafka manager instance."""
    return KafkaManager()


# SCADA Data Processing Utilities
class ScadaDataProcessor:
    """SCADA data processing utilities."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def validate_data_point(self, raw_value: Any, data_point: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and process SCADA data point."""
        try:
            # Apply scaling and offset
            scale_factor = data_point.get("scale_factor", 1.0)
            offset = data_point.get("offset", 0.0)

            if isinstance(raw_value, (int, float)):
                processed_value = (raw_value * scale_factor) + offset
            else:
                processed_value = raw_value

            # Validate against min/max bounds
            min_value = data_point.get("min_value")
            max_value = data_point.get("max_value")

            quality = "good"
            if min_value is not None and processed_value < min_value:
                quality = "uncertain"
            if max_value is not None and processed_value > max_value:
                quality = "uncertain"

            # Check for alarm conditions
            is_alarm = False
            if data_point.get("is_alarmpoint", False):
                high_threshold = data_point.get("alarm_threshold_high")
                low_threshold = data_point.get("alarm_threshold_low")

                if high_threshold is not None and processed_value > high_threshold:
                    is_alarm = True
                    quality = "bad"
                if low_threshold is not None and processed_value < low_threshold:
                    is_alarm = True
                    quality = "bad"

            return {
                "value": processed_value,
                "raw_value": raw_value,
                "quality": quality,
                "is_alarm": is_alarm,
                "validation_errors": []
            }

        except Exception as e:
            self.logger.error(f"Data validation failed for point {data_point.get('point_name', 'unknown')}: {e}")
            return {
                "value": raw_value,
                "raw_value": raw_value,
                "quality": "bad",
                "is_alarm": False,
                "validation_errors": [str(e)]
            }

    def detect_anomalies(self, current_value: float, historical_values: List[float], threshold: float = 3.0) -> Dict[str, Any]:
        """Detect anomalies using statistical methods."""
        try:
            if len(historical_values) < 10:
                return {"is_anomaly": False, "confidence": 0.0, "method": "insufficient_data"}

            import numpy as np

            # Calculate statistics
            mean = np.mean(historical_values)
            std_dev = np.std(historical_values)

            if std_dev == 0:
                return {"is_anomaly": False, "confidence": 0.0, "method": "no_variance"}

            # Z-score method
            z_score = abs(current_value - mean) / std_dev
            is_anomaly = z_score > threshold
            confidence = min(z_score / threshold, 1.0)

            return {
                "is_anomaly": is_anomaly,
                "confidence": confidence,
                "z_score": z_score,
                "mean": mean,
                "std_dev": std_dev,
                "method": "z_score"
            }

        except Exception as e:
            self.logger.error(f"Anomaly detection failed: {e}")
            return {"is_anomaly": False, "confidence": 0.0, "method": "error", "error": str(e)}


def create_scada_data_processor() -> ScadaDataProcessor:
    """Create SCADA data processor instance."""
    return ScadaDataProcessor()


# Response Utilities
def create_success_response(
    data: Any = None,
    message: str = "Success",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create standardized success response."""
    response = {
        "success": True,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if data is not None:
        response["data"] = data

    if metadata:
        response["metadata"] = metadata

    return response


def create_error_response(
    message: str,
    error_code: str = "ERROR",
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create standardized error response."""
    response = {
        "success": False,
        "message": message,
        "error_code": error_code,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if details:
        response["details"] = details

    return response


# Configuration
class Config:
    """Configuration for utilities."""

    # Use enum values in serialization
    use_enum_values = True

    # Validate assignment
    validate_assignment = True

    # Allow population by field name
    allow_population_by_field_name = True

    # Use ORM mode
    orm_mode = True


# Apply configuration to utility models
for model in []:
    model.Config = Config()


__all__ = [
    "get_logger",
    "RedisManager",
    "create_redis_manager",
    "InfluxDBManager",
    "create_influxdb_manager",
    "KafkaManager",
    "create_kafka_manager",
    "ScadaDataProcessor",
    "create_scada_data_processor",
    "create_success_response",
    "create_error_response",
    "Config"
]