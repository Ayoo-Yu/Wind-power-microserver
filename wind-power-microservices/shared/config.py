"""
Shared configuration management for all microservices.
"""

from pydantic import BaseSettings, validator
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Base configuration class for all microservices."""

    # Service Information
    service_name: str = "unknown-service"
    service_version: str = "1.0.0"
    environment: str = "development"

    # Database Configuration
    database_url: str = "postgresql://user:password@localhost:5432/windpower"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    redis_password: Optional[str] = None

    # Kafka Configuration
    kafka_bootstrap_servers: List[str] = ["localhost:9092"]
    kafka_client_id: Optional[str] = None

    # Security Configuration
    secret_key: str = "your-secret-key-here"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30

    # API Configuration
    api_v1_prefix: str = "/api/v1"
    cors_origins: List[str] = ["*"]

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "json"

    # Monitoring Configuration
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    health_check_path: str = "/health"

    # External Service Configuration
    tenant_service_url: str = "http://tenant-service:8001"
    scada_service_url: str = "http://scada-service:8002"
    meteorological_service_url: str = "http://meteorological-service:8003"
    prediction_service_url: str = "http://prediction-service:8004"
    reporting_service_url: str = "http://reporting-service:8005"

    @validator("environment")
    def validate_environment(cls, v):
        if v not in ["development", "staging", "production"]:
            raise ValueError("environment must be development, staging, or production")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        if v not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("log_level must be a valid Python logging level")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False


class DatabaseSettings(BaseSettings):
    """Database-specific settings."""

    # Connection settings
    host: str = "localhost"
    port: int = 5432
    user: str = "windpower"
    password: str = "password"
    database: str = "windpower"

    # Pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600

    # Performance settings
    echo: bool = False
    echo_pool: bool = False

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class KafkaSettings(BaseSettings):
    """Kafka-specific settings."""

    bootstrap_servers: List[str] = ["localhost:9092"]
    client_id: Optional[str] = None

    # Producer settings
    producer_acks: str = "all"
    producer_retries: int = 3
    producer_batch_size: int = 16384

    # Consumer settings
    consumer_group_id: str = "wind-power-consumer"
    consumer_auto_offset_reset: str = "earliest"
    consumer_enable_auto_commit: bool = True


class RedisSettings(BaseSettings):
    """Redis-specific settings."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None

    # Connection pool settings
    max_connections: int = 50
    socket_timeout: int = 5
    socket_connect_timeout: int = 5

    @property
    def redis_url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


def get_database_settings() -> DatabaseSettings:
    """Get database settings."""
    return DatabaseSettings()


def get_kafka_settings() -> KafkaSettings:
    """Get Kafka settings."""
    return KafkaSettings()


def get_redis_settings() -> RedisSettings:
    """Get Redis settings."""
    return RedisSettings()