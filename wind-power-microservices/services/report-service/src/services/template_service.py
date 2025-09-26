"""
Template service for managing report templates
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from ..database import report_template_crud
from ..models import TemplateCreate, TemplateUpdate, TemplateResponse
from ..exceptions import TemplateNotFoundException, ValidationException
from ..utils import get_logger

logger = get_logger(__name__)


class TemplateService:
    """Service for managing report templates."""

    def __init__(self):
        self.is_initialized = False

    async def initialize(self):
        """Initialize the template service."""
        try:
            logger.info("Initializing Template Service...")
            self.is_initialized = True
            logger.info("Template Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Template Service: {e}")
            raise

    async def shutdown(self):
        """Shutdown the template service."""
        try:
            logger.info("Shutting down Template Service...")
            self.is_initialized = False
            logger.info("Template Service shutdown completed")
        except Exception as e:
            logger.error(f"Error during Template Service shutdown: {e}")

    async def create_template(
        self,
        db: AsyncSession,
        template_data: TemplateCreate
    ) -> TemplateResponse:
        """Create a new report template."""
        try:
            logger.info(f"Creating template: {template_data.name} (type: {template_data.report_type})")

            # Validate template data
            self._validate_template_data(template_data)

            # Create template record
            template_dict = template_data.dict()
            template_dict["id"] = f"template_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{hash(template_data.name) % 10000:04d}"
            template_dict["is_active"] = True
            template_dict["created_at"] = datetime.utcnow()
            template_dict["updated_at"] = datetime.utcnow()

            template = await report_template_crud.create(db, template_dict)

            return TemplateResponse.from_orm(template)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error creating template: {e}")
            raise ValidationException(f"Failed to create template: {str(e)}")

    async def list_templates(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[TemplateResponse], int]:
        """List templates with filtering."""
        try:
            logger.info(f"Listing templates: skip={skip}, limit={limit}, filters={filters}")

            # Build query conditions
            conditions = []
            if filters:
                if "report_type" in filters:
                    conditions.append(report_template_crud.model.report_type == filters["report_type"])
                if "is_active" in filters:
                    conditions.append(report_template_crud.model.is_active == filters["is_active"])

            # Execute query
            query = select(report_template_crud.model)
            if conditions:
                query = query.where(and_(*conditions))

            # Get total count
            count_query = select(func.count(report_template_crud.model.id))
            if conditions:
                count_query = count_query.where(and_(*conditions))

            total_result = await db.execute(count_query)
            total = total_result.scalar()

            # Get paginated results
            query = query.offset(skip).limit(limit).order_by(report_template_crud.model.created_at.desc())
            result = await db.execute(query)
            templates = result.scalars().all()

            # Convert to response models
            template_responses = [TemplateResponse.from_orm(template) for template in templates]

            return template_responses, total

        except Exception as e:
            logger.error(f"Error listing templates: {e}")
            return [], 0

    async def get_template(
        self,
        db: AsyncSession,
        template_id: str
    ) -> Optional[TemplateResponse]:
        """Get a specific template by ID."""
        try:
            logger.info(f"Getting template: {template_id}")

            template = await report_template_crud.get(db, template_id)
            if not template:
                return None

            return TemplateResponse.from_orm(template)

        except Exception as e:
            logger.error(f"Error getting template {template_id}: {e}")
            return None

    async def update_template(
        self,
        db: AsyncSession,
        template_id: str,
        template_data: TemplateUpdate
    ) -> Optional[TemplateResponse]:
        """Update a template."""
        try:
            logger.info(f"Updating template: {template_id}")

            # Get existing template
            existing_template = await report_template_crud.get(db, template_id)
            if not existing_template:
                return None

            # Validate template data
            self._validate_template_update(template_data)

            # Update fields
            update_data = template_data.dict(exclude_unset=True)
            update_data["updated_at"] = datetime.utcnow()

            updated_template = await report_template_crud.update(db, template_id, update_data)

            return TemplateResponse.from_orm(updated_template)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error updating template {template_id}: {e}")
            raise ValidationException(f"Failed to update template: {str(e)}")

    async def delete_template(
        self,
        db: AsyncSession,
        template_id: str
    ) -> bool:
        """Delete a template."""
        try:
            logger.info(f"Deleting template: {template_id}")

            template = await report_template_crud.get(db, template_id)
            if not template:
                return False

            # Don't delete if it's the only active template for a report type
            if template.is_active:
                active_count = await self._count_active_templates_by_type(db, template.report_type)
                if active_count <= 1:
                    raise ValidationException(f"Cannot delete the only active template for report type: {template.report_type}")

            success = await report_template_crud.delete(db, template_id)
            return success

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error deleting template {template_id}: {e}")
            return False

    async def duplicate_template(
        self,
        db: AsyncSession,
        template_id: str,
        new_name: Optional[str] = None
    ) -> Optional[TemplateResponse]:
        """Duplicate an existing template."""
        try:
            logger.info(f"Duplicating template: {template_id}")

            # Get existing template
            existing_template = await report_template_crud.get(db, template_id)
            if not existing_template:
                return None

            # Create duplicate data
            duplicate_data = TemplateCreate(
                name=new_name or f"{existing_template.name} (Copy)",
                report_type=existing_template.report_type,
                template_content=existing_template.template_content,
                template_format=existing_template.template_format,
                css_styles=existing_template.css_styles,
                header_template=existing_template.header_template,
                footer_template=existing_template.footer_template,
                default_parameters=existing_template.default_parameters,
                default_charts=existing_template.default_charts,
                default_data_sources=existing_template.default_data_sources,
                description=existing_template.description
            )

            # Create new template
            new_template = await self.create_template(db, duplicate_data)
            return new_template

        except Exception as e:
            logger.error(f"Error duplicating template {template_id}: {e}")
            return None

    async def activate_template(
        self,
        db: AsyncSession,
        template_id: str
    ) -> Optional[TemplateResponse]:
        """Activate a template."""
        try:
            logger.info(f"Activating template: {template_id}")

            template = await report_template_crud.get(db, template_id)
            if not template:
                return None

            updated_template = await report_template_crud.update(db, template_id, {
                "is_active": True,
                "updated_at": datetime.utcnow()
            })

            return TemplateResponse.from_orm(updated_template)

        except Exception as e:
            logger.error(f"Error activating template {template_id}: {e}")
            return None

    async def deactivate_template(
        self,
        db: AsyncSession,
        template_id: str
    ) -> Optional[TemplateResponse]:
        """Deactivate a template."""
        try:
            logger.info(f"Deactivating template: {template_id}")

            template = await report_template_crud.get(db, template_id)
            if not template:
                return None

            # Don't deactivate if it's the only active template for a report type
            active_count = await self._count_active_templates_by_type(db, template.report_type)
            if active_count <= 1:
                raise ValidationException(f"Cannot deactivate the only active template for report type: {template.report_type}")

            updated_template = await report_template_crud.update(db, template_id, {
                "is_active": False,
                "updated_at": datetime.utcnow()
            })

            return TemplateResponse.from_orm(updated_template)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error deactivating template {template_id}: {e}")
            return None

    async def get_available_template_types(self) -> List[Dict[str, Any]]:
        """Get available template types and their configurations."""
        try:
            logger.info("Getting available template types")

            template_types = [
                {
                    "type": "daily_power_generation",
                    "name": "Daily Power Generation Report",
                    "description": "Daily report showing power generation metrics and trends",
                    "supported_formats": ["pdf", "html", "excel"],
                    "default_charts": ["power_generation_trend", "efficiency_analysis"],
                    "default_data_sources": ["scada", "power_prediction"],
                    "template_variables": [
                        "total_generation", "avg_power", "capacity_factor", "availability",
                        "power_output", "wind_speed", "efficiency", "timestamp"
                    ]
                },
                {
                    "type": "weekly_performance",
                    "name": "Weekly Performance Report",
                    "description": "Weekly report showing prediction accuracy and performance metrics",
                    "supported_formats": ["pdf", "html", "excel"],
                    "default_charts": ["prediction_accuracy", "performance_trends"],
                    "default_data_sources": ["scada", "power_prediction", "meteorological"],
                    "template_variables": [
                        "prediction_accuracy", "mae", "rmse", "r2_score",
                        "model_performance", "horizon_analysis"
                    ]
                },
                {
                    "type": "operational_dashboard",
                    "name": "Operational Dashboard",
                    "description": "Real-time operational dashboard with system status",
                    "supported_formats": ["html"],
                    "default_charts": ["real_time_power", "wind_conditions", "system_status"],
                    "default_data_sources": ["scada", "meteorological", "power_prediction"],
                    "template_variables": [
                        "current_power", "wind_speed", "critical_alerts", "warning_alerts",
                        "turbine_status", "system_health"
                    ]
                },
                {
                    "type": "maintenance_summary",
                    "name": "Maintenance Summary Report",
                    "description": "Summary of maintenance activities and equipment status",
                    "supported_formats": ["pdf", "html", "excel"],
                    "default_charts": ["maintenance_schedule", "equipment_status"],
                    "default_data_sources": ["scada", "wind_farm"],
                    "template_variables": [
                        "maintenance_tasks", "equipment_status", "downtime", "uptime",
                        "maintenance_costs", "next_maintenance"
                    ]
                }
            ]

            return template_types

        except Exception as e:
            logger.error(f"Error getting available template types: {e}")
            return []

    async def preview_template(
        self,
        db: AsyncSession,
        template_id: str,
        sample_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Preview a template with sample data."""
        try:
            logger.info(f"Previewing template: {template_id}")

            template = await report_template_crud.get(db, template_id)
            if not template:
                return None

            # Use provided sample data or generate default
            if not sample_data:
                sample_data = self._generate_sample_template_data(template.report_type)

            # Render template preview
            from jinja2 import Template
            jinja_template = Template(template.template_content)

            try:
                rendered_content = jinja_template.render(**sample_data)
            except Exception as e:
                rendered_content = f"Template rendering error: {str(e)}"

            return {
                "template_id": template.id,
                "template_name": template.name,
                "report_type": template.report_type,
                "rendered_content": rendered_content,
                "sample_data": sample_data,
                "css_styles": template.css_styles,
                "template_variables": list(sample_data.keys())
            }

        except Exception as e:
            logger.error(f"Error previewing template {template_id}: {e}")
            return None

    async def get_default_templates(self) -> List[Dict[str, Any]]:
        """Get built-in default templates."""
        try:
            logger.info("Getting default templates")

            defaults = [
                {
                    "id": "default_daily_power",
                    "name": "Default Daily Power Generation Template",
                    "report_type": "daily_power_generation",
                    "template_content": self._get_default_daily_power_template(),
                    "css_styles": self._get_default_css(),
                    "description": "Default template for daily power generation reports"
                },
                {
                    "id": "default_weekly_performance",
                    "name": "Default Weekly Performance Template",
                    "report_type": "weekly_performance",
                    "template_content": self._get_default_weekly_performance_template(),
                    "css_styles": self._get_default_css(),
                    "description": "Default template for weekly performance reports"
                },
                {
                    "id": "default_operational_dashboard",
                    "name": "Default Operational Dashboard Template",
                    "report_type": "operational_dashboard",
                    "template_content": self._get_default_dashboard_template(),
                    "css_styles": self._get_dashboard_css(),
                    "description": "Default template for operational dashboards"
                }
            ]

            return defaults

        except Exception as e:
            logger.error(f"Error getting default templates: {e}")
            return []

    async def export_template(
        self,
        db: AsyncSession,
        template_id: str
    ) -> Optional[Dict[str, Any]]:
        """Export a template for backup or sharing."""
        try:
            logger.info(f"Exporting template: {template_id}")

            template = await report_template_crud.get(db, template_id)
            if not template:
                return None

            export_data = {
                "template_id": template.id,
                "name": template.name,
                "report_type": template.report_type,
                "template_content": template.template_content,
                "template_format": template.template_format,
                "css_styles": template.css_styles,
                "header_template": template.header_template,
                "footer_template": template.footer_template,
                "default_parameters": template.default_parameters,
                "default_charts": template.default_charts,
                "default_data_sources": template.default_data_sources,
                "description": template.description,
                "is_active": template.is_active,
                "created_at": template.created_at.isoformat() if template.created_at else None,
                "updated_at": template.updated_at.isoformat() if template.updated_at else None,
                "export_metadata": {
                    "exported_at": datetime.utcnow().isoformat(),
                    "export_version": "1.0"
                }
            }

            return export_data

        except Exception as e:
            logger.error(f"Error exporting template {template_id}: {e}")
            return None

    def _validate_template_data(self, template_data: TemplateCreate):
        """Validate template data."""
        if not template_data.name or len(template_data.name.strip()) == 0:
            raise ValidationException("Template name cannot be empty")

        if not template_data.report_type or len(template_data.report_type.strip()) == 0:
            raise ValidationException("Report type cannot be empty")

        if not template_data.template_content or len(template_data.template_content.strip()) == 0:
            raise ValidationException("Template content cannot be empty")

        # Validate template content syntax
        try:
            from jinja2 import Template
            Template(template_data.template_content)
        except Exception as e:
            raise ValidationException(f"Invalid template syntax: {str(e)}")

    def _validate_template_update(self, template_data: TemplateUpdate):
        """Validate template update data."""
        if template_data.template_content:
            try:
                from jinja2 import Template
                Template(template_data.template_content)
            except Exception as e:
                raise ValidationException(f"Invalid template syntax: {str(e)}")

    async def _count_active_templates_by_type(
        self,
        db: AsyncSession,
        report_type: str
    ) -> int:
        """Count active templates by report type."""
        try:
            query = select(func.count(report_template_crud.model.id)).where(
                and_(
                    report_template_crud.model.report_type == report_type,
                    report_template_crud.model.is_active == True
                )
            )
            result = await db.execute(query)
            return result.scalar()
        except Exception as e:
            logger.error(f"Error counting active templates: {e}")
            return 0

    def _generate_sample_template_data(self, report_type: str) -> Dict[str, Any]:
        """Generate sample data for template preview."""
        sample_data = {
            "report_name": f"Sample {report_type} Report",
            "report_type": report_type,
            "generation_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "wind_farm_name": "Wind Farm Alpha",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "css_styles": "body { font-family: Arial, sans-serif; }",
            "charts": [],
            "data_table": [],
            "data_quality_score": 95.5
        }

        if report_type == "daily_power_generation":
            sample_data.update({
                "total_generation": 48.5,
                "avg_power": 2.02,
                "capacity_factor": 45.2,
                "availability": 98.5,
                "max_power": 2.15,
                "min_power": 0.85
            })
        elif report_type == "weekly_performance":
            sample_data.update({
                "prediction_accuracy": 92.3,
                "mae": 0.15,
                "rmse": 0.22,
                "r2_score": 0.85,
                "model_performance": [
                    {"horizon": "1h", "mae": 0.12, "rmse": 0.18, "mape": 3.2, "r2": 0.89},
                    {"horizon": "6h", "mae": 0.15, "rmse": 0.22, "mape": 4.1, "r2": 0.85},
                    {"horizon": "24h", "mae": 0.21, "rmse": 0.31, "mape": 5.8, "r2": 0.78}
                ]
            })
        elif report_type == "operational_dashboard":
            sample_data.update({
                "refresh_interval": 300,
                "current_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "critical_alerts": 0,
                "warning_alerts": 2,
                "current_power": 2.1,
                "wind_speed": 8.5,
                "turbine_status": [
                    {"name": "Turbine 01", "status": "Running", "status_class": "status-good", "power_output": 2.1},
                    {"name": "Turbine 02", "status": "Maintenance", "status_class": "status-warning", "power_output": 0.0},
                    {"name": "Turbine 03", "status": "Running", "status_class": "status-good", "power_output": 1.9}
                ]
            })

        return sample_data

    def _get_default_daily_power_template(self) -> str:
        """Get default daily power generation template."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ report_name }}</title>
            <style>{{ css_styles }}</style>
        </head>
        <body>
            <div class="report-header">
                <h1>{{ report_name }}</h1>
                <p>Generated: {{ generation_time }}</p>
                <p>Wind Farm: {{ wind_farm_name }}</p>
                <p>Period: {{ start_date }} to {{ end_date }}</p>
            </div>
            <div class="summary-section">
                <h2>Executive Summary</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Total Generation</h3>
                        <p class="metric-value">{{ total_generation }} MWh</p>
                    </div>
                    <div class="metric-card">
                        <h3>Average Power</h3>
                        <p class="metric-value">{{ avg_power }} MW</p>
                    </div>
                    <div class="metric-card">
                        <h3>Capacity Factor</h3>
                        <p class="metric-value">{{ capacity_factor }}%</p>
                    </div>
                    <div class="metric-card">
                        <h3>Availability</h3>
                        <p class="metric-value">{{ availability }}%</p>
                    </div>
                </div>
            </div>
            <div class="charts-section">
                <h2>Performance Charts</h2>
                {% for chart in charts %}
                <div class="chart-container">
                    <h3>{{ chart.name }}</h3>
                    <img src="data:image/png;base64,{{ chart.image_data }}" alt="{{ chart.name }}" />
                </div>
                {% endfor %}
            </div>
            <div class="report-footer">
                <p>Data Quality Score: {{ data_quality_score }}%</p>
            </div>
        </body>
        </html>
        """

    def _get_default_weekly_performance_template(self) -> str:
        """Get default weekly performance template."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ report_name }}</title>
            <style>{{ css_styles }}</style>
        </head>
        <body>
            <div class="report-header">
                <h1>{{ report_name }}</h1>
                <p>Generated: {{ generation_time }}</p>
                <p>Period: {{ start_date }} to {{ end_date }}</p>
            </div>
            <div class="performance-summary">
                <h2>Performance Summary</h2>
                <div class="kpi-grid">
                    <div class="kpi-card">
                        <h3>Prediction Accuracy</h3>
                        <p class="kpi-value">{{ prediction_accuracy }}%</p>
                    </div>
                    <div class="kpi-card">
                        <h3>MAE</h3>
                        <p class="kpi-value">{{ mae }} MW</p>
                    </div>
                    <div class="kpi-card">
                        <h3>RMSE</h3>
                        <p class="kpi-value">{{ rmse }} MW</p>
                    </div>
                    <div class="kpi-card">
                        <h3>R² Score</h3>
                        <p class="kpi-value">{{ r2_score }}</p>
                    </div>
                </div>
            </div>
            <div class="charts-section">
                <h2>Prediction vs Actual</h2>
                {% for chart in charts %}
                <div class="chart-container">
                    <h3>{{ chart.name }}</h3>
                    <img src="data:image/png;base64,{{ chart.image_data }}" alt="{{ chart.name }}" />
                </div>
                {% endfor %}
            </div>
            <div class="report-footer">
                <p>Data Quality Score: {{ data_quality_score }}%</p>
            </div>
        </body>
        </html>
        """

    def _get_default_dashboard_template(self) -> str:
        """Get default operational dashboard template."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ report_name }}</title>
            <style>{{ dashboard_css }}</style>
            <meta http-equiv="refresh" content="{{ refresh_interval }}">
        </head>
        <body>
            <div class="dashboard-header">
                <h1>{{ wind_farm_name }} - Operational Dashboard</h1>
                <p class="last-updated">Last Updated: {{ current_time }}</p>
            </div>
            <div class="dashboard-grid">
                <div class="metric-tile status-critical">
                    <h3>Critical Alerts</h3>
                    <p class="metric-value">{{ critical_alerts }}</p>
                </div>
                <div class="metric-tile status-warning">
                    <h3>Warning Alerts</h3>
                    <p class="metric-value">{{ warning_alerts }}</p>
                </div>
                <div class="metric-tile status-good">
                    <h3>Current Power</h3>
                    <p class="metric-value">{{ current_power }} MW</p>
                </div>
                <div class="metric-tile status-good">
                    <h3>Wind Speed</h3>
                    <p class="metric-value">{{ wind_speed }} m/s</p>
                </div>
            </div>
            <div class="charts-container">
                {% for chart in charts %}
                <div class="chart-widget">
                    <h3>{{ chart.name }}</h3>
                    <img src="data:image/png;base64,{{ chart.image_data }}" alt="{{ chart.name }}" />
                </div>
                {% endfor %}
            </div>
            <div class="status-overview">
                <h2>System Status Overview</h2>
                <div class="status-grid">
                    {% for turbine in turbine_status %}
                    <div class="turbine-status {{ turbine.status_class }}">
                        <h4>{{ turbine.name }}</h4>
                        <p>{{ turbine.status }}</p>
                        <p>{{ turbine.power_output }} MW</p>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </body>
        </html>
        """

    def _get_default_css(self) -> str:
        """Get default CSS styles."""
        return """
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .report-header {
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .metrics-grid, .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card, .kpi-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        .metric-value, .kpi-value {
            font-size: 24px;
            font-weight: bold;
            color: #27ae60;
            margin: 0;
        }
        .charts-section {
            margin-bottom: 30px;
        }
        .chart-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .report-footer {
            margin-top: 30px;
            padding: 20px;
            background-color: #ecf0f1;
            border-radius: 8px;
            text-align: center;
            color: #7f8c8d;
        }
        """

    def _get_dashboard_css(self) -> str:
        """Get dashboard CSS styles."""
        return """
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #1a1a1a;
            color: #ffffff;
        }
        .dashboard-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 20px;
        }
        .metric-tile {
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            padding: 30px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 8px 16px rgba(0,0,0,0.3);
        }
        .metric-value {
            font-size: 32px;
            font-weight: bold;
            margin: 0;
        }
        .status-critical {
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
        }
        .status-warning {
            background: linear-gradient(135deg, #f39c12 0%, #d68910 100%);
        }
        .status-good {
            background: linear-gradient(135deg, #27ae60 0%, #229954 100%);
        }
        """


# Global template service instance
template_service = TemplateService()