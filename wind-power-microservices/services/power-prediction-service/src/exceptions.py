"""
Custom exceptions for Power Prediction Service
"""

from typing import Optional, Dict, Any


class PowerPredictionException(Exception):
    """Base exception for power prediction service."""

    def __init__(
        self,
        message: str,
        error_code: str = "POWER_PREDICTION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ModelNotFoundException(PowerPredictionException):
    """Exception raised when ML model is not found."""

    def __init__(self, model_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"ML model {model_id} not found",
            "MODEL_NOT_FOUND",
            details or {"model_id": model_id}
        )


class PredictionNotFoundException(PowerPredictionException):
    """Exception raised when power prediction is not found."""

    def __init__(self, prediction_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Power prediction {prediction_id} not found",
            "PREDICTION_NOT_FOUND",
            details or {"prediction_id": prediction_id}
        )


class TrainingDataException(PowerPredictionException):
    """Exception raised when training data is insufficient or invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "TRAINING_DATA_ERROR",
            details
        )


class ModelTrainingException(PowerPredictionException):
    """Exception raised during model training."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "MODEL_TRAINING_ERROR",
            details
        )


class PredictionException(PowerPredictionException):
    """Exception raised during power prediction."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "PREDICTION_ERROR",
            details
        )


class DataQualityException(PowerPredictionException):
    """Exception raised when data quality is insufficient."""

    def __init__(self, message: str, quality_score: float, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["quality_score"] = quality_score
        super().__init__(
            message,
            "DATA_QUALITY_ERROR",
            details
        )


class FeatureEngineeringException(PowerPredictionException):
    """Exception raised during feature engineering."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "FEATURE_ENGINEERING_ERROR",
            details
        )


class DatabaseConnectionException(PowerPredictionException):
    """Exception raised when database connection fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "DATABASE_CONNECTION_ERROR",
            details
        )


class ExternalAPIException(PowerPredictionException):
    """Exception raised when external API calls fail."""

    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["service"] = service
        super().__init__(
            f"External API error for {service}: {message}",
            "EXTERNAL_API_ERROR",
            details
        )


class ValidationException(PowerPredictionException):
    """Exception raised when data validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(
            message,
            "VALIDATION_ERROR",
            details
        )


class ConfigurationException(PowerPredictionException):
    """Exception raised when configuration is invalid."""

    def __init__(self, message: str, config_key: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(
            message,
            "CONFIGURATION_ERROR",
            details
        )


class ServiceUnavailableException(PowerPredictionException):
    """Exception raised when a required service is unavailable."""

    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["service"] = service
        super().__init__(
            f"Service {service} unavailable: {message}",
            "SERVICE_UNAVAILABLE",
            details
        )


class InsufficientDataException(PowerPredictionException):
    """Exception raised when there's insufficient data for operations."""

    def __init__(self, message: str, required_samples: Optional[int] = None,
                 available_samples: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if required_samples:
            details["required_samples"] = required_samples
        if available_samples:
            details["available_samples"] = available_samples
        super().__init__(
            message,
            "INSUFFICIENT_DATA",
            details
        )


class ModelPerformanceException(PowerPredictionException):
    """Exception raised when model performance is below threshold."""

    def __init__(self, message: str, performance_metrics: Optional[Dict[str, float]] = None,
                 details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if performance_metrics:
            details["performance_metrics"] = performance_metrics
        super().__init__(
            message,
            "MODEL_PERFORMANCE_ERROR",
            details
        )