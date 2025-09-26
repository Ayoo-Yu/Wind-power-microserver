"""
Configuration management for Report Service
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseSettings, validator
import os


class Settings(BaseSettings):
    """Application settings."""

    # Application settings
    app_name: str = "Report Service"
    app_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8005
    debug: bool = False

    # Database settings
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/report_db"
    redis_url: str = "redis://localhost:6379"

    # Kafka settings
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topics_reports: str = "reports"
    kafka_topics_power_predictions: str = "power-predictions"
    kafka_topics_weather_data: str = "weather-data"
    kafka_topics_scada_data: str = "scada-data"

    # Report Generation settings
    report_templates_path: str = "/app/templates"
    report_output_path: str = "/app/reports"
    report_cache_ttl: int = 3600
    max_report_size_mb: int = 50

    # Report Types Configuration
    enable_pdf_reports: bool = True
    enable_excel_reports: bool = True
    enable_html_reports: bool = True
    enable_charts: bool = True

    # API Settings
    power_prediction_api_url: str = "http://localhost:8004"
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

    # Report Scheduling
    enable_scheduled_reports: bool = True
    report_scheduler_interval: int = 300  # 5 minutes

    # Data Retention
    report_history_days: int = 365
    temp_file_cleanup_interval: int = 86400  # 24 hours

    # Chart Configuration
    chart_default_width: int = 1200
    chart_default_height: int = 600
    chart_dpi: int = 150

    # Email Settings (for report delivery)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@windfarm.com"

    # External Integrations
    slack_webhook_url: str = ""
    teams_webhook_url: str = ""

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

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


# Report configuration constants
REPORT_TYPES = {
    "daily_power_generation": {
        "name": "Daily Power Generation Report",
        "description": "Daily summary of power generation across all wind farms",
        "template": "daily_power_generation.html",
        "supported_formats": ["pdf", "excel", "html"],
        "default_schedule": "daily_08:00",
        "data_sources": ["scada", "power_prediction"],
        "charts": ["power_generation_trend", "efficiency_analysis", "availability_summary"]
    },
    "weekly_performance": {
        "name": "Weekly Performance Report",
        "description": "Weekly performance analysis with predictions vs actual",
        "template": "weekly_performance.html",
        "supported_formats": ["pdf", "excel"],
        "default_schedule": "weekly_monday_08:00",
        "data_sources": ["scada", "power_prediction", "meteorological"],
        "charts": ["prediction_accuracy", "performance_trends", "weather_correlation"]
    },
    "monthly_maintenance": {
        "name": "Monthly Maintenance Report",
        "description": "Monthly maintenance activities and equipment status",
        "template": "monthly_maintenance.html",
        "supported_formats": ["pdf", "excel"],
        "default_schedule": "monthly_1st_08:00",
        "data_sources": ["scada", "wind_farm"],
        "charts": ["maintenance_schedule", "equipment_status", "failure_analysis"]
    },
    "weather_forecast_accuracy": {
        "name": "Weather Forecast Accuracy Report",
        "description": "Analysis of weather forecast accuracy and impact on predictions",
        "template": "weather_forecast_accuracy.html",
        "supported_formats": ["pdf", "excel", "html"],
        "default_schedule": "weekly_friday_15:00",
        "data_sources": ["meteorological", "power_prediction"],
        "charts": ["forecast_accuracy", "prediction_vs_actual", "weather_impact"]
    },
    "financial_performance": {
        "name": "Financial Performance Report",
        "description": "Financial analysis including revenue, costs, and ROI",
        "template": "financial_performance.html",
        "supported_formats": ["pdf", "excel"],
        "default_schedule": "monthly_15th_09:00",
        "data_sources": ["scada", "wind_farm"],
        "charts": ["revenue_analysis", "cost_breakdown", "roi_trends"]
    },
    "environmental_impact": {
        "name": "Environmental Impact Report",
        "description": "Environmental benefits and carbon footprint reduction",
        "template": "environmental_impact.html",
        "supported_formats": ["pdf", "html"],
        "default_schedule": "quarterly",
        "data_sources": ["scada"],
        "charts": ["carbon_reduction", "environmental_benefits", "sustainability_metrics"]
    },
    "operational_dashboard": {
        "name": "Operational Dashboard",
        "description": "Real-time operational overview and KPIs",
        "template": "operational_dashboard.html",
        "supported_formats": ["html"],
        "default_schedule": "real_time",
        "data_sources": ["scada", "meteorological", "power_prediction"],
        "charts": ["real_time_power", "wind_conditions", "system_status"]
    },
    "compliance_report": {
        "name": "Regulatory Compliance Report",
        "description": "Compliance with regulatory requirements and standards",
        "template": "compliance_report.html",
        "supported_formats": ["pdf", "excel"],
        "default_schedule": "quarterly",
        "data_sources": ["scada", "wind_farm"],
        "charts": ["compliance_status", "regulatory_metrics", "audit_findings"]
    }
}

# Chart configuration
CHART_CONFIG = {
    "power_generation_trend": {
        "type": "line",
        "title": "Power Generation Trend",
        "x_axis": "timestamp",
        "y_axis": "power_output",
        "colors": ["#1f77b4", "#ff7f0e"],
        "height": 400,
        "width": 800
    },
    "prediction_accuracy": {
        "type": "scatter",
        "title": "Prediction vs Actual",
        "x_axis": "actual_power",
        "y_axis": "predicted_power",
        "colors": ["#2ca02c"],
        "height": 400,
        "width": 600
    },
    "efficiency_analysis": {
        "type": "bar",
        "title": "Efficiency Analysis by Turbine",
        "x_axis": "turbine_id",
        "y_axis": "efficiency",
        "colors": ["#d62728"],
        "height": 400,
        "width": 800
    },
    "availability_summary": {
        "type": "pie",
        "title": "System Availability Summary",
        "colors": ["#2ca02c", "#ff7f0e", "#d62728"],
        "height": 400,
        "width": 500
    },
    "weather_correlation": {
        "type": "heatmap",
        "title": "Weather Correlation Matrix",
        "height": 500,
        "width": 600
    },
    "maintenance_schedule": {
        "type": "gantt",
        "title": "Maintenance Schedule",
        "height": 400,
        "width": 1000
    },
    "equipment_status": {
        "type": "status_grid",
        "title": "Equipment Status Overview",
        "height": 300,
        "width": 800
    },
    "failure_analysis": {
        "type": "bar",
        "title": "Failure Analysis",
        "x_axis": "failure_type",
        "y_axis": "count",
        "colors": ["#d62728"],
        "height": 400,
        "width": 600
    }
}

# Data aggregation configurations
AGGREGATION_CONFIG = {
    "hourly": {
        "interval": "1H",
        "functions": ["mean", "sum", "min", "max", "std"],
        "description": "Hourly aggregation"
    },
    "daily": {
        "interval": "1D",
        "functions": ["mean", "sum", "min", "max", "std"],
        "description": "Daily aggregation"
    },
    "weekly": {
        "interval": "1W",
        "functions": ["mean", "sum", "min", "max", "std"],
        "description": "Weekly aggregation"
    },
    "monthly": {
        "interval": "1M",
        "functions": ["mean", "sum", "min", "max", "std"],
        "description": "Monthly aggregation"
    }
}

# Report scheduling configuration
SCHEDULING_CONFIG = {
    "real_time": {
        "interval_seconds": 300,  # 5 minutes
        "description": "Real-time updates"
    },
    "hourly": {
        "cron": "0 * * * *",
        "description": "Every hour"
    },
    "daily_08:00": {
        "cron": "0 8 * * *",
        "description": "Daily at 8:00 AM"
    },
    "weekly_monday_08:00": {
        "cron": "0 8 * * 1",
        "description": "Every Monday at 8:00 AM"
    },
    "weekly_friday_15:00": {
        "cron": "0 15 * * 5",
        "description": "Every Friday at 3:00 PM"
    },
    "monthly_1st_08:00": {
        "cron": "0 8 1 * *",
        "description": "First day of month at 8:00 AM"
    },
    "monthly_15th_09:00": {
        "cron": "0 9 15 * *",
        "description": "15th day of month at 9:00 AM"
    },
    "quarterly": {
        "cron": "0 8 1 */3 *",
        "description": "First day of quarter at 8:00 AM"
    }
}

# Email template configuration
EMAIL_TEMPLATES = {
    "report_ready": {
        "subject": "Wind Farm Report Ready - {report_name}",
        "body": """
Dear {recipient_name},

Your requested report "{report_name}" is now ready for download.

Report Details:
- Type: {report_type}
- Period: {report_period}
- Generated: {generation_time}
- Format: {report_format}

You can download the report from the following link:
{download_link}

Best regards,
Wind Farm Management System
        """
    },
    "scheduled_report": {
        "subject": "Scheduled Report Available - {report_name}",
        "body": """
Dear {recipient_name},

Your scheduled report "{report_name}" has been generated automatically.

Report Details:
- Type: {report_type}
- Period: {report_period}
- Generated: {generation_time}
- Format: {report_format}

You can access the report through the system dashboard or download it directly:
{download_link}

Best regards,
Wind Farm Management System
        """
    }
}

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "power_generation_efficiency": {
        "min_efficiency": 0.85,
        "max_efficiency": 1.0,
        "warning_threshold": 0.90
    },
    "prediction_accuracy": {
        "mae_threshold": 50,  # kW
        "mape_threshold": 10,  # percentage
        "r2_threshold": 0.8
    },
    "system_availability": {
        "target_availability": 0.98,
        "warning_threshold": 0.95,
        "critical_threshold": 0.90
    },
    "environmental_impact": {
        "min_carbon_reduction_tonnes": 1000,
        "target_renewable_percentage": 0.95
    }
}