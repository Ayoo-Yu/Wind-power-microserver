"""
Configuration management for Meteorological Data Service
"""

from typing import List, Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings."""

    # Application settings
    app_name: str = Field("Meteorological Data Service", description="Application name")
    app_version: str = Field("1.0.0", description="Application version")
    host: str = Field("0.0.0.0", description="Host address")
    port: int = Field(8003, description="Port number")
    debug: bool = Field(False, description="Debug mode")

    # Database settings
    database_url: str = Field(
        "postgresql+asyncpg://postgres:password@localhost:5434/meteorological_db",
        description="PostgreSQL database URL"
    )

    # Redis settings
    redis_url: str = Field("redis://localhost:6381", description="Redis connection URL")

    # Kafka settings
    kafka_bootstrap_servers: str = Field("localhost:9094", description="Kafka bootstrap servers")
    kafka_topics_weather_data: str = Field("weather-data", description="Weather data topic")
    kafka_topics_weather_forecast: str = Field("weather-forecast", description="Weather forecast topic")
    kafka_topics_weather_alerts: str = Field("weather-alerts", description="Weather alerts topic")

    # Weather API settings
    weather_api_enabled: bool = Field(True, description="Enable weather API integration")
    weather_api_sources: List[str] = Field(
        ["openweathermap", "weatherapi", "noaa"],
        description="Enabled weather data sources"
    )

    # OpenWeatherMap API
    openweathermap_api_key: Optional[str] = Field(None, description="OpenWeatherMap API key")
    openweathermap_api_url: str = Field("https://api.openweathermap.org/data/2.5", description="OpenWeatherMap API URL")
    openweathermap_rate_limit: int = Field(60, description="API rate limit per minute")

    # WeatherAPI
    weatherapi_key: Optional[str] = Field(None, description="WeatherAPI key")
    weatherapi_url: str = Field("https://api.weatherapi.com/v1", description="WeatherAPI URL")

    # NOAA API
    noaa_api_key: Optional[str] = Field(None, description="NOAA API key")
    noaa_api_url: str = Field("https://api.weather.gov", description="NOAA API URL")

    # Forecast settings
    forecast_hours: int = Field(72, description="Forecast horizon in hours")
    forecast_update_interval: int = Field(3600, description="Forecast update interval in seconds")

    # Data collection settings
    weather_data_collection_interval: int = Field(300, description="Weather data collection interval in seconds")
    historical_data_retention_days: int = Field(365, description="Historical data retention in days")

    # Security settings
    secret_key: str = Field("your-secret-key-here", description="Secret key for JWT")
    algorithm: str = Field("HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(30, description="Access token expiration time")

    # CORS settings
    cors_origins: List[str] = Field(
        ["http://localhost:3000", "http://localhost:8080"],
        description="CORS allowed origins"
    )

    # Rate limiting
    rate_limit_per_minute: int = Field(1000, description="Rate limit per minute")
    rate_limit_per_hour: int = Field(10000, description="Rate limit per hour")

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
_settings = None


def get_settings() -> Settings:
    """Get application settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings