"""
Custom exceptions for Report Service
"""

from typing import Optional, Dict, Any


class ReportServiceException(Exception):
    """Base exception for report service."""

    def __init__(
        self,
        message: str,
        error_code: str = "REPORT_SERVICE_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ReportNotFoundException(ReportServiceException):
    """Exception raised when report is not found."""

    def __init__(self, report_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Report {report_id} not found",
            "REPORT_NOT_FOUND",
            details or {"report_id": report_id}
        )


class TemplateNotFoundException(ReportServiceException):
    """Exception raised when report template is not found."""

    def __init__(self, template_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Report template {template_id} not found",
            "TEMPLATE_NOT_FOUND",
            details or {"template_id": template_id}
        )


class ReportGenerationException(ReportServiceException):
    """Exception raised during report generation."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "REPORT_GENERATION_ERROR",
            details
        )


class DataCollectionException(ReportServiceException):
    """Exception raised during data collection."""

    def __init__(self, message: str, data_source: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if data_source:
            details["data_source"] = data_source
        super().__init__(
            f"Data collection failed: {message}",
            "DATA_COLLECTION_ERROR",
            details
        )


class ChartGenerationException(ReportServiceException):
    """Exception raised during chart generation."""

    def __init__(self, message: str, chart_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if chart_type:
            details["chart_type"] = chart_type
        super().__init__(
            f"Chart generation failed: {message}",
            "CHART_GENERATION_ERROR",
            details
        )


class TemplateRenderingException(ReportServiceException):
    """Exception raised during template rendering."""

    def __init__(self, message: str, template_name: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if template_name:
            details["template_name"] = template_name
        super().__init__(
            f"Template rendering failed: {message}",
            "TEMPLATE_RENDERING_ERROR",
            details
        )


class DataValidationException(ReportServiceException):
    """Exception raised when data validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(
            message,
            "DATA_VALIDATION_ERROR",
            details
        )


class DatabaseConnectionException(ReportServiceException):
    """Exception raised when database connection fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            "DATABASE_CONNECTION_ERROR",
            details
        )


class ExternalAPIException(ReportServiceException):
    """Exception raised when external API calls fail."""

    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["service"] = service
        super().__init__(
            f"External API error for {service}: {message}",
            "EXTERNAL_API_ERROR",
            details
        )


class ValidationException(ReportServiceException):
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


class ConfigurationException(ReportServiceException):
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


class ServiceUnavailableException(ReportServiceException):
    """Exception raised when a required service is unavailable."""

    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["service"] = service
        super().__init__(
            f"Service {service} unavailable: {message}",
            "SERVICE_UNAVAILABLE",
            details
        )


class InsufficientDataException(ReportServiceException):
    """Exception raised when there's insufficient data for report generation."""

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


class FileOperationException(ReportServiceException):
    """Exception raised during file operations."""

    def __init__(self, message: str, file_path: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if file_path:
            details["file_path"] = file_path
        super().__init__(
            message,
            "FILE_OPERATION_ERROR",
            details
        )


class ReportDeliveryException(ReportServiceException):
    """Exception raised during report delivery."""

    def __init__(self, message: str, delivery_method: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if delivery_method:
            details["delivery_method"] = delivery_method
        super().__init__(
            message,
            "REPORT_DELIVERY_ERROR",
            details
        )


class ReportSchedulingException(ReportServiceException):
    """Exception raised during report scheduling."""

    def __init__(self, message: str, schedule_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if schedule_id:
            details["schedule_id"] = schedule_id
        super().__init__(
            message,
            "REPORT_SCHEDULING_ERROR",
            details
        )


class DataQualityException(ReportServiceException):
    """Exception raised when data quality is insufficient."""

    def __init__(self, message: str, quality_score: float, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["quality_score"] = quality_score
        super().__init__(
            message,
            "DATA_QUALITY_ERROR",
            details
        )


class ReportPermissionException(ReportServiceException):
    """Exception raised when user lacks permission for report operation."""

    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if operation:
            details["operation"] = operation
        super().__init__(
            message,
            "REPORT_PERMISSION_ERROR",
            details
        )