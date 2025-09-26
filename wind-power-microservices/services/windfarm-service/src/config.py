"""
Configuration for Wind Farm Management Service.
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, validator, AnyHttpUrl
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""

    # Application settings
    app_name: str = "Wind Farm Management Service"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8001

    # Database settings
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/windfarm_db"
    database_pool_size: int = 20
    database_max_overflow: int = 40

    # Redis settings
    redis_url: str = "redis://localhost:6379/0"
    redis_pool_size: int = 50

    # JWT settings
    secret_key: str = "your-secret-key-here-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    jwt_refresh_expiration_days: int = 7

    # CORS settings
    cors_origins: List[str] = ["*"]
    allowed_hosts: List[str] = ["*"]

    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Service discovery
    service_discovery_enabled: bool = False
    consul_host: str = "localhost"
    consul_port: int = 8500
    consul_service_name: str = "windfarm-service"

    # Health check
    health_check_interval: int = 30  # seconds
    health_check_timeout: int = 5    # seconds

    # Audit logging
    audit_log_enabled: bool = True
    audit_log_max_entries: int = 1000000

    # Performance monitoring
    metrics_enabled: bool = False
    metrics_port: int = 9090

    # Feature flags
    enable_real_time_data: bool = True
    enable_notifications: bool = True
    enable_cache: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("database_url", pre=True)
    def validate_database_url(cls, v: Optional[str]) -> str:
        """Validate database URL."""
        if v is None:
            return "postgresql+asyncpg://postgres:password@localhost:5432/windfarm_db"
        return v

    @validator("redis_url", pre=True)
    def validate_redis_url(cls, v: Optional[str]) -> str:
        """Validate Redis URL."""
        if v is None:
            return "redis://localhost:6379/0"
        return v

    @validator("secret_key", pre=True)
    def validate_secret_key(cls, v: Optional[str]) -> str:
        """Validate secret key."""
        if v is None or v == "your-secret-key-here-change-in-production":
            import secrets
            return secrets.token_urlsafe(32)
        return v

    @validator("cors_origins", pre=True)
    def validate_cors_origins(cls, v: str) -> List[str]:
        """Validate CORS origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @validator("allowed_hosts", pre=True)
    def validate_allowed_hosts(cls, v: str) -> List[str]:
        """Validate allowed hosts."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v

    @property
    def database_config(self) -> dict:
        """Get database configuration."""
        return {
            "url": self.database_url,
            "pool_size": self.database_pool_size,
            "max_overflow": self.database_max_overflow,
        }

    @property
    def redis_config(self) -> dict:
        """Get Redis configuration."""
        return {
            "url": self.redis_url,
            "pool_size": self.redis_pool_size,
        }

    @property
    def jwt_config(self) -> dict:
        """Get JWT configuration."""
        return {
            "secret_key": self.secret_key,
            "algorithm": self.jwt_algorithm,
            "expiration_minutes": self.jwt_expiration_minutes,
            "refresh_expiration_days": self.jwt_refresh_expiration_days,
        }

    @property
    def cors_config(self) -> dict:
        """Get CORS configuration."""
        return {
            "origins": self.cors_origins,
            "allowed_hosts": self.allowed_hosts,
        }

    @property
    def rate_limit_config(self) -> dict:
        """Get rate limiting configuration."""
        return {
            "per_minute": self.rate_limit_per_minute,
            "per_hour": self.rate_limit_per_hour,
        }

    @property
    def service_info(self) -> dict:
        """Get service information."""
        return {
            "name": self.app_name,
            "version": self.app_version,
            "debug": self.debug,
            "host": self.host,
            "port": self.port,
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