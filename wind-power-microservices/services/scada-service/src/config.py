"""
Configuration for SCADA Data Service.
"""

import os
from typing import List, Optional, Dict, Any
from pydantic import BaseSettings, validator
from functools import lru_cache


class Settings(BaseSettings):
    """SCADA Data Service configuration."""

    # Service Information
    app_name: str = "SCADA Data Service"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8002

    # Database Configuration
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/scada_db"
    database_pool_size: int = 20
    database_max_overflow: int = 40

    # Time Series Database (InfluxDB)
    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = "your-influxdb-token"
    influxdb_org: str = "windpower"
    influxdb_bucket: str = "scada_data"

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/1"
    redis_pool_size: int = 50

    # Kafka Configuration
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topics: Dict[str, str] = {
        "scada_realtime": "scada.realtime.data",
        "scada_events": "scada.events",
        "scada_alarms": "scada.alarms",
        "turbine_status": "turbine.status.changes",
        "power_data": "power.measurements"
    }

    # SCADA Protocol Configuration
    max_connections_per_wind_farm: int = 10
    connection_timeout: int = 30
    reconnect_interval: int = 60
    heartbeat_interval: int = 30

    # IEC 60870-5-104 Configuration
    iec104_port: int = 2404
    iec104_default_timeout: int = 30
    iec104_max_reconnect_attempts: int = 5
    iec104_reconnect_delay: int = 10

    # Data Processing Configuration
    data_buffer_size: int = 10000
    batch_processing_size: int = 1000
    data_retention_days: int = 30
    realtime_data_interval: int = 5  # seconds

    # Security Configuration
    secret_key: str = "your-secret-key-here-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30

    # CORS Configuration
    cors_origins: List[str] = ["*"]
    allowed_hosts: List[str] = ["*"]

    # Rate Limiting
    rate_limit_per_minute: int = 1000
    rate_limit_per_hour: int = 10000

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Monitoring Configuration
    metrics_enabled: bool = True
    metrics_port: int = 9090
    health_check_interval: int = 30

    # Feature Flags
    enable_real_time_processing: bool = True
    enable_event_publishing: bool = True
    enable_alarm_processing: bool = True
    enable_historical_storage: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("database_url", pre=True)
    def validate_database_url(cls, v: Optional[str]) -> str:
        """Validate database URL."""
        if v is None:
            return "postgresql+asyncpg://postgres:password@localhost:5432/scada_db"
        return v

    @validator("cors_origins", pre=True)
    def validate_cors_origins(cls, v: str) -> List[str]:
        """Validate CORS origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @validator("secret_key", pre=True)
    def validate_secret_key(cls, v: Optional[str]) -> str:
        """Validate secret key."""
        if v is None or v == "your-secret-key-here-change-in-production":
            import secrets
            return secrets.token_urlsafe(32)
        return v

    @property
    def database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        return {
            "url": self.database_url,
            "pool_size": self.database_pool_size,
            "max_overflow": self.database_max_overflow,
        }

    @property
    def influxdb_config(self) -> Dict[str, Any]:
        """Get InfluxDB configuration."""
        return {
            "url": self.influxdb_url,
            "token": self.influxdb_token,
            "org": self.influxdb_org,
            "bucket": self.influxdb_bucket,
        }

    @property
    def kafka_config(self) -> Dict[str, Any]:
        """Get Kafka configuration."""
        return {
            "bootstrap_servers": self.kafka_bootstrap_servers,
            "topics": self.kafka_topics,
        }

    @property
    def scada_config(self) -> Dict[str, Any]:
        """Get SCADA configuration."""
        return {
            "max_connections_per_wind_farm": self.max_connections_per_wind_farm,
            "connection_timeout": self.connection_timeout,
            "reconnect_interval": self.reconnect_interval,
            "heartbeat_interval": self.heartbeat_interval,
            "iec104_port": self.iec104_port,
            "iec104_default_timeout": self.iec104_default_timeout,
            "iec104_max_reconnect_attempts": self.iec104_max_reconnect_attempts,
            "iec104_reconnect_delay": self.iec104_reconnect_delay,
        }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_config():
    """Get configuration."""
    return get_settings()


# Create default settings instance
settings = get_settings()

__all__ = ["Settings", "get_settings", "get_config", "settings"]