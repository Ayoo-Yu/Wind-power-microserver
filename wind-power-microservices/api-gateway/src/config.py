"""
Configuration for API Gateway.
"""

from pydantic import BaseSettings, validator
from typing import Dict, List, Optional
import os


class ServiceConfig(BaseSettings):
    """Service configuration."""

    name: str
    url: str
    health_check_path: str = "/health"
    timeout: int = 30
    retry_attempts: int = 3
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
    rate_limit_rpm: int = 1000  # requests per minute


class Settings(BaseSettings):
    """Configuration settings for API Gateway."""

    # Service Information
    service_name: str = "api-gateway"
    service_version: str = "1.0.0"
    environment: str = "development"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8080

    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Security Configuration
    secret_key: str = "your-secret-key-here-make-it-long-and-random"
    jwt_algorithm: str = "HS256"
    jwt_public_key: Optional[str] = None
    jwt_private_key: Optional[str] = None

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    redis_db: int = 0

    # Rate Limiting
    global_rate_limit_rpm: int = 10000  # Global requests per minute
    per_ip_rate_limit_rpm: int = 100    # Per IP requests per minute
    per_user_rate_limit_rpm: int = 500  # Per user requests per minute

    # Circuit Breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60

    # Load Balancing
    load_balancing_algorithm: str = "round_robin"  # round_robin, least_connections, random

    # Monitoring
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    request_logging_enabled: bool = True

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "json"

    # Service Registry
    services: Dict[str, ServiceConfig] = {
        "tenant-service": ServiceConfig(
            name="tenant-service",
            url="http://tenant-service:8001",
            health_check_path="/health",
            timeout=30,
            retry_attempts=3,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=60,
            rate_limit_rpm=1000,
        ),
        "scada-service": ServiceConfig(
            name="scada-service",
            url="http://scada-service:8002",
            health_check_path="/health",
            timeout=30,
            retry_attempts=3,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=60,
            rate_limit_rpm=2000,
        ),
        "meteorological-service": ServiceConfig(
            name="meteorological-service",
            url="http://meteorological-service:8003",
            health_check_path="/health",
            timeout=60,
            retry_attempts=3,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=60,
            rate_limit_rpm=500,
        ),
        "prediction-service": ServiceConfig(
            name="prediction-service",
            url="http://prediction-service:8004",
            health_check_path="/health",
            timeout=120,
            retry_attempts=3,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=60,
            rate_limit_rpm=800,
        ),
        "reporting-service": ServiceConfig(
            name="reporting-service",
            url="http://reporting-service:8005",
            health_check_path="/health",
            timeout=30,
            retry_attempts=3,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=60,
            rate_limit_rpm=600,
        ),
    }

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

    @validator("load_balancing_algorithm")
    def validate_load_balancing_algorithm(cls, v):
        valid_algorithms = ["round_robin", "least_connections", "random", "weighted_round_robin"]
        if v not in valid_algorithms:
            raise ValueError(f"load_balancing_algorithm must be one of {valid_algorithms}")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False
        env_prefix = "API_GATEWAY_"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


def get_service_config(service_name: str) -> Optional[ServiceConfig]:
    """Get configuration for a specific service."""
    settings = get_settings()
    return settings.services.get(service_name)


def get_all_service_configs() -> Dict[str, ServiceConfig]:
    """Get configuration for all services."""
    settings = get_settings()
    return settings.services