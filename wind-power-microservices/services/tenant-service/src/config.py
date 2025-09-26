"""
Configuration for Tenant Management Service.
"""

from pydantic import BaseSettings, validator
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Configuration settings for Tenant Management Service."""

    # Service Information
    service_name: str = "tenant-service"
    service_version: str = "1.0.0"
    environment: str = "development"

    # API Configuration
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8001

    # Database Configuration
    database_url: str = "postgresql://windpower:password@localhost:5432/windpower_tenant"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/1"
    redis_db: int = 1

    # Security Configuration
    secret_key: str = "your-secret-key-here-make-it-long-and-random"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    jwt_refresh_expiration_days: int = 7

    # Password Security
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_numbers: bool = True
    password_require_symbols: bool = True

    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Rate Limiting
    rate_limit_requests_per_minute: int = 60
    rate_limit_requests_per_hour: int = 1000

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "json"

    # Monitoring Configuration
    metrics_enabled: bool = True
    health_check_path: str = "/health"

    # External Service URLs
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

    @validator("jwt_algorithm")
    def validate_jwt_algorithm(cls, v):
        valid_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        if v not in valid_algorithms:
            raise ValueError(f"jwt_algorithm must be one of {valid_algorithms}")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False
        env_prefix = "TENANT_SERVICE_"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()