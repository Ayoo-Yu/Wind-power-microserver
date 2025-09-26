"""
Configuration management for Power Prediction Service
"""

from typing import List, Optional
from pydantic import BaseSettings, validator
import os


class Settings(BaseSettings):
    """Application settings."""

    # Application settings
    app_name: str = "Power Prediction Service"
    app_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8004
    debug: bool = False

    # Database settings
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/power_prediction_db"
    redis_url: str = "redis://localhost:6379"

    # Kafka settings
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topics_power_prediction: str = "power-predictions"
    kafka_topics_power_data: str = "power-data"
    kafka_topics_weather_data: str = "weather-data"
    kafka_topics_scada_data: str = "scada-data"

    # Machine Learning settings
    ml_models_path: str = "/app/models"
    ml_model_update_interval: int = 3600
    ml_training_batch_size: int = 1000
    ml_prediction_horizon_hours: int = 72

    # Model Configuration
    enable_lstm_model: bool = True
    enable_xgboost_model: bool = True
    enable_random_forest_model: bool = True
    enable_ensemble_model: bool = True

    # API Settings
    weather_api_url: str = "http://localhost:8003"
    scada_api_url: str = "http://localhost:8002"
    wind_farm_api_url: str = "http://localhost:8001"

    # Security settings
    secret_key: str = "your-secret-key-here-change-in-production"
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    # Monitoring Settings
    prometheus_metrics_enabled: bool = True
    metrics_port: int = 8000

    # Logging Settings
    log_level: str = "INFO"
    log_format: str = "json"

    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Rate limiting
    rate_limit_per_minute: int = 1000
    rate_limit_per_hour: int = 10000

    # Data Retention
    prediction_history_days: int = 365
    model_performance_history_days: int = 90

    # Training Settings
    auto_retraining_enabled: bool = True
    retraining_interval_hours: int = 168  # 7 days
    min_training_samples: int = 10000

    # Feature Engineering
    enable_feature_engineering: bool = True
    feature_lag_hours: int = 24
    feature_rolling_windows: str = "3,6,12,24"

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @validator("feature_rolling_windows", pre=True)
    def parse_rolling_windows(cls, v):
        """Parse rolling windows from string."""
        if isinstance(v, str):
            return v
        return v

    @property
    def rolling_windows_list(self) -> List[int]:
        """Get rolling windows as list of integers."""
        try:
            return [int(w.strip()) for w in self.feature_rolling_windows.split(",")]
        except:
            return [3, 6, 12, 24]

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


# Feature engineering configuration
FEATURE_ENGINEERING_CONFIG = {
    "wind_speed_features": [
        "mean", "std", "min", "max", "trend", "seasonality"
    ],
    "wind_direction_features": [
        "mean", "std", "direction_change_rate"
    ],
    "temperature_features": [
        "mean", "std", "min", "max", "gradient"
    ],
    "pressure_features": [
        "mean", "std", "trend", "pressure_change_rate"
    ],
    "humidity_features": [
        "mean", "std", "gradient"
    ],
    "time_features": [
        "hour", "day_of_week", "month", "season", "is_weekend"
    ],
    "lag_features": [1, 2, 3, 6, 12, 24],  # hours
    "rolling_features": [3, 6, 12, 24],  # hours
}

# Model hyperparameters
MODEL_HYPERPARAMETERS = {
    "lstm": {
        "units": [64, 128, 256],
        "dropout": 0.2,
        "recurrent_dropout": 0.2,
        "optimizer": "adam",
        "loss": "mse",
        "epochs": 100,
        "batch_size": 32,
        "validation_split": 0.2
    },
    "xgboost": {
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42
    },
    "random_forest": {
        "n_estimators": 100,
        "max_depth": 10,
        "min_samples_split": 2,
        "min_samples_leaf": 1,
        "random_state": 42
    }
}

# Prediction configuration
PREDICTION_CONFIG = {
    "horizons": [1, 6, 12, 24, 48, 72],  # hours ahead
    "update_frequencies": {
        "1h": 300,    # 5 minutes
        "6h": 900,    # 15 minutes
        "12h": 1800,  # 30 minutes
        "24h": 3600,  # 1 hour
        "48h": 7200,  # 2 hours
        "72h": 10800  # 3 hours
    },
    "confidence_intervals": [0.8, 0.9, 0.95]
}

# Model evaluation metrics
EVALUATION_METRICS = {
    "regression": ["mae", "mse", "rmse", "mape", "r2"],
    "classification": ["accuracy", "precision", "recall", "f1"],
    "time_series": ["mae", "mse", "rmse", "mape", "smape", "mase"]
}