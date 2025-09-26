"""
Custom exceptions for Meteorological Data Service
"""


class MeteorologicalServiceException(Exception):
    """Base exception for meteorological service."""

    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code or "METEOROLOGICAL_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class WeatherStationNotFoundException(MeteorologicalServiceException):
    """Raised when weather station is not found."""

    def __init__(self, station_id: str):
        super().__init__(
            f"Weather station {station_id} not found",
            error_code="WEATHER_STATION_NOT_FOUND",
            details={"station_id": station_id}
        )


class DuplicateWeatherStationException(MeteorologicalServiceException):
    """Raised when trying to create a duplicate weather station."""

    def __init__(self, station_code: str):
        super().__init__(
            f"Weather station with code {station_code} already exists",
            error_code="DUPLICATE_WEATHER_STATION",
            details={"station_code": station_code}
        )


class InvalidWeatherDataException(MeteorologicalServiceException):
    """Raised when weather data is invalid."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message,
            error_code="INVALID_WEATHER_DATA",
            details=details
        )


class WeatherAPIException(MeteorologicalServiceException):
    """Raised when weather API integration fails."""

    def __init__(self, api_source: str, message: str, status_code: int = None):
        super().__init__(
            f"Weather API error from {api_source}: {message}",
            error_code="WEATHER_API_ERROR",
            details={"api_source": api_source, "status_code": status_code}
        )


class ForecastModelException(MeteorologicalServiceException):
    """Raised when forecast model fails."""

    def __init__(self, model_name: str, message: str):
        super().__init__(
            f"Forecast model {model_name} error: {message}",
            error_code="FORECAST_MODEL_ERROR",
            details={"model_name": model_name}
        )


class InsufficientDataException(MeteorologicalServiceException):
    """Raised when insufficient data is available for processing."""

    def __init__(self, required: int, available: int, data_type: str = "data"):
        super().__init__(
            f"Insufficient {data_type}: required {required}, available {available}",
            error_code="INSUFFICIENT_DATA",
            details={"required": required, "available": available, "data_type": data_type}
        )


class WeatherAlertException(MeteorologicalServiceException):
    """Raised when weather alert processing fails."""

    def __init__(self, message: str, alert_id: str = None):
        super().__init__(
            f"Weather alert error: {message}",
            error_code="WEATHER_ALERT_ERROR",
            details={"alert_id": alert_id}
        )


class ValidationException(MeteorologicalServiceException):
    """Raised when data validation fails."""

    def __init__(self, field: str, message: str, value: Any = None):
        super().__init__(
            f"Validation error for {field}: {message}",
            error_code="VALIDATION_ERROR",
            details={"field": field, "value": value}
        )


class DatabaseConnectionException(MeteorologicalServiceException):
    """Raised when database connection fails."""

    def __init__(self, message: str):
        super().__init__(
            f"Database connection error: {message}",
            error_code="DATABASE_CONNECTION_ERROR"
        )


class KafkaConnectionException(MeteorologicalServiceException):
    """Raised when Kafka connection fails."""

    def __init__(self, message: str):
        super().__init__(
            f"Kafka connection error: {message}",
            error_code="KAFKA_CONNECTION_ERROR"
        )


class RateLimitException(MeteorologicalServiceException):
    """Raised when API rate limit is exceeded."""

    def __init__(self, api_source: str, retry_after: int = None):
        message = f"Rate limit exceeded for {api_source}"
        if retry_after:
            message += f", retry after {retry_after} seconds"

        super().__init__(
            message,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"api_source": api_source, "retry_after": retry_after}
        )


class ExternalServiceException(MeteorologicalServiceException):
    """Raised when external service call fails."""

    def __init__(self, service_name: str, message: str, status_code: int = None):
        super().__init__(
            f"External service {service_name} error: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service_name": service_name, "status_code": status_code}
        )


class ConfigurationException(MeteorologicalServiceException):
    """Raised when configuration is invalid."""

    def __init__(self, message: str, config_key: str = None):
        super().__init__(
            f"Configuration error: {message}",
            error_code="CONFIGURATION_ERROR",
            details={"config_key": config_key}
        )