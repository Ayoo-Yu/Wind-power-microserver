"""
Chart service for managing chart operations
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import pandas as pd

from ..database import chart_crud, report_data_crud
from ..chart_generator import chart_generator
from ..data_collector import data_collector
from ..models import ChartResponse, ChartType
from ..exceptions import ChartGenerationException, DataCollectionException
from ..utils import get_logger, create_error_response

logger = get_logger(__name__)


class ChartService:
    """Service for managing chart operations."""

    def __init__(self):
        self.is_initialized = False

    async def initialize(self):
        """Initialize the chart service."""
        try:
            logger.info("Initializing Chart Service...")
            await chart_generator.initialize()
            await data_collector.initialize()
            self.is_initialized = True
            logger.info("Chart Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Chart Service: {e}")
            raise

    async def shutdown(self):
        """Shutdown the chart service."""
        try:
            logger.info("Shutting down Chart Service...")
            await chart_generator.shutdown()
            await data_collector.shutdown()
            self.is_initialized = False
            logger.info("Chart Service shutdown completed")
        except Exception as e:
            logger.error(f"Error during Chart Service shutdown: {e}")

    async def generate_chart(
        self,
        db: AsyncSession,
        chart_type: str,
        title: str,
        data_source: str,
        wind_farm_id: Optional[str] = None,
        turbine_ids: Optional[List[str]] = None,
        time_range_hours: int = 24,
        config: Optional[Dict[str, Any]] = None,
        backend: str = "matplotlib"
    ) -> ChartResponse:
        """Generate a chart from data source."""
        try:
            logger.info(f"Generating chart: type={chart_type}, title={title}, source={data_source}")

            # Determine time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=time_range_hours)

            # Collect data
            time_range = {
                "start_date": start_time.isoformat(),
                "end_date": end_time.isoformat()
            }

            data = await data_collector.collect_data(
                report_type="chart_generation",
                wind_farm_id=wind_farm_id,
                turbine_ids=turbine_ids,
                time_range=time_range,
                data_sources=[data_source],
                db_session=db
            )

            if not data or data_source not in data:
                raise DataCollectionException(f"No data available from source: {data_source}")

            # Prepare chart data
            source_data = data[data_source]
            if not source_data.get("data"):
                raise DataCollectionException(f"No data records from source: {data_source}")

            chart_data = self._prepare_chart_dataframe(chart_type, source_data["data"])
            if chart_data is None or chart_data.empty:
                raise ChartGenerationException(f"Cannot prepare data for chart type: {chart_type}")

            # Generate chart
            chart_image = await chart_generator.generate_chart(
                chart_type=chart_type,
                data=chart_data,
                title=title,
                config=config,
                backend=backend
            )

            if not chart_image:
                raise ChartGenerationException(f"Failed to generate chart: {chart_type}")

            # Save chart record
            import base64
            chart_record = {
                "id": f"chart_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{hash(title) % 10000:04d}",
                "chart_type": chart_type,
                "title": title,
                "data_source": data_source,
                "wind_farm_id": wind_farm_id,
                "turbine_ids": turbine_ids,
                "config": config or {},
                "backend": backend,
                "image_data": base64.b64encode(chart_image).decode('utf-8'),
                "data_points": len(chart_data),
                "created_at": datetime.utcnow()
            }

            chart = await chart_crud.create(db, chart_record)

            return ChartResponse.from_orm(chart)

        except (DataCollectionException, ChartGenerationException):
            raise
        except Exception as e:
            logger.error(f"Error generating chart: {e}")
            raise ChartGenerationException(f"Failed to generate chart: {str(e)}")

    async def generate_chart_from_dataframe(
        self,
        df: pd.DataFrame,
        chart_type: str,
        title: str,
        x_column: Optional[str] = None,
        y_column: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        backend: str = "matplotlib"
    ) -> Dict[str, Any]:
        """Generate a chart from a DataFrame."""
        try:
            logger.info(f"Generating chart from DataFrame: type={chart_type}, title={title}")

            # Validate DataFrame
            if df.empty:
                raise ChartGenerationException("DataFrame is empty")

            # Prepare data for chart type
            chart_data = self._prepare_dataframe_for_chart(df, chart_type, x_column, y_column)
            if chart_data is None or chart_data.empty:
                raise ChartGenerationException(f"Cannot prepare DataFrame for chart type: {chart_type}")

            # Generate chart
            chart_image = await chart_generator.generate_chart(
                chart_type=chart_type,
                data=chart_data,
                title=title,
                config=config,
                backend=backend
            )

            if not chart_image:
                raise ChartGenerationException(f"Failed to generate chart: {chart_type}")

            # Return chart data
            import base64
            return {
                "chart_type": chart_type,
                "title": title,
                "backend": backend,
                "image_data": base64.b64encode(chart_image).decode('utf-8'),
                "data_points": len(chart_data),
                "data_preview": chart_data.head(10).to_dict('records')
            }

        except ChartGenerationException:
            raise
        except Exception as e:
            logger.error(f"Error generating chart from DataFrame: {e}")
            raise ChartGenerationException(f"Failed to generate chart from DataFrame: {str(e)}")

    async def generate_multiple_charts(
        self,
        db: AsyncSession,
        charts_config: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate multiple charts."""
        try:
            logger.info(f"Generating multiple charts: count={len(charts_config)}")

            charts = []
            for config in charts_config:
                try:
                    chart_data = await self.generate_chart(
                        db=db,
                        chart_type=config.get("type", "line"),
                        title=config.get("title", "Chart"),
                        data_source=config.get("data_source", "scada"),
                        wind_farm_id=config.get("wind_farm_id"),
                        turbine_ids=config.get("turbine_ids"),
                        time_range_hours=config.get("time_range_hours", 24),
                        config=config.get("config", {}),
                        backend=config.get("backend", "matplotlib")
                    )
                    charts.append(ChartResponse.from_orm(chart_data).dict())
                except Exception as e:
                    logger.warning(f"Failed to generate chart {config.get('title', 'unknown')}: {e}")
                    continue

            return charts

        except Exception as e:
            logger.error(f"Error generating multiple charts: {e}")
            raise ChartGenerationException(f"Failed to generate multiple charts: {str(e)}")

    async def list_templates(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        chart_type: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List chart templates."""
        try:
            logger.info(f"Listing chart templates: skip={skip}, limit={limit}, type={chart_type}")

            # For now, return built-in templates
            templates = self._get_builtin_templates()

            if chart_type:
                templates = [t for t in templates if t["chart_type"] == chart_type]

            total = len(templates)
            paginated_templates = templates[skip:skip + limit]

            return paginated_templates, total

        except Exception as e:
            logger.error(f"Error listing chart templates: {e}")
            return [], 0

    async def get_available_backends(self) -> List[Dict[str, Any]]:
        """Get available chart generation backends."""
        try:
            logger.info("Getting available chart backends")

            backends = [
                {
                    "name": "matplotlib",
                    "description": "Matplotlib backend for static charts",
                    "supported_types": ["line", "bar", "pie", "scatter", "histogram", "box"],
                    "features": ["Static images", "High quality", "Multiple formats"]
                },
                {
                    "name": "plotly",
                    "description": "Plotly backend for interactive charts",
                    "supported_types": ["line", "bar", "scatter"],
                    "features": ["Interactive", "Web-friendly", "Zoom/pan"]
                },
                {
                    "name": "seaborn",
                    "description": "Seaborn backend for statistical charts",
                    "supported_types": ["heatmap", "box", "scatter"],
                    "features": ["Statistical", "Beautiful styling", "Correlation matrices"]
                }
            ]

            return backends

        except Exception as e:
            logger.error(f"Error getting available backends: {e}")
            return []

    async def get_sample_data(
        self,
        db: AsyncSession,
        data_source: str,
        wind_farm_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get sample data for chart testing."""
        try:
            logger.info(f"Getting sample data: source={data_source}, wind_farm={wind_farm_id}")

            # Collect sample data
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)

            time_range = {
                "start_date": start_time.isoformat(),
                "end_date": end_time.isoformat()
            }

            data = await data_collector.collect_data(
                report_type="sample_data",
                wind_farm_id=wind_farm_id,
                time_range=time_range,
                data_sources=[data_source],
                db_session=db
            )

            if not data or data_source not in data:
                return []

            source_data = data[data_source]
            sample_data = source_data.get("data", [])[:limit]

            return sample_data

        except Exception as e:
            logger.error(f"Error getting sample data: {e}")
            return []

    async def get_chart_preview(
        self,
        db: AsyncSession,
        chart_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get chart preview data."""
        try:
            logger.info(f"Getting chart preview: {chart_id}")

            chart = await chart_crud.get(db, chart_id)
            if not chart:
                return None

            return {
                "chart_id": chart.id,
                "chart_type": chart.chart_type,
                "title": chart.title,
                "data_source": chart.data_source,
                "wind_farm_id": chart.wind_farm_id,
                "created_at": chart.created_at,
                "data_points": chart.data_points,
                "backend": chart.backend,
                "image_data": chart.image_data
            }

        except Exception as e:
            logger.error(f"Error getting chart preview {chart_id}: {e}")
            return None

    async def delete_chart(
        self,
        db: AsyncSession,
        chart_id: str
    ) -> bool:
        """Delete a chart."""
        try:
            logger.info(f"Deleting chart: {chart_id}")

            chart = await chart_crud.get(db, chart_id)
            if not chart:
                return False

            success = await chart_crud.delete(db, chart_id)
            return success

        except Exception as e:
            logger.error(f"Error deleting chart {chart_id}: {e}")
            return False

    def get_chart_type_description(self, chart_type: str) -> str:
        """Get description for chart type."""
        descriptions = {
            "line": "Line chart for showing trends over time",
            "bar": "Bar chart for comparing categories",
            "pie": "Pie chart for showing proportions",
            "scatter": "Scatter plot for showing relationships",
            "histogram": "Histogram for showing distributions",
            "box": "Box plot for showing statistical summaries",
            "heatmap": "Heatmap for showing correlation matrices"
        }
        return descriptions.get(chart_type, "Chart")

    def _prepare_chart_dataframe(
        self,
        chart_type: str,
        data: List[Dict[str, Any]]
    ) -> Optional[pd.DataFrame]:
        """Prepare data for specific chart type."""
        try:
            if not data:
                return None

            df = pd.DataFrame(data)

            if chart_type == "line":
                # Use timestamp and first numeric column
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    numeric_cols = df.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) > 0:
                        return df[["timestamp", numeric_cols[0]]]
                return df

            elif chart_type == "bar":
                # Use categorical and numeric columns
                categorical_cols = df.select_dtypes(include=['object']).columns
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(categorical_cols) > 0 and len(numeric_cols) > 0:
                    return df[[categorical_cols[0], numeric_cols[0]]]
                return df

            elif chart_type == "pie":
                # Use categorical column or first column for labels, numeric for values
                categorical_cols = df.select_dtypes(include=['object']).columns
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(categorical_cols) > 0 and len(numeric_cols) > 0:
                    return df[[categorical_cols[0], numeric_cols[0]]]
                elif len(df.columns) >= 2:
                    return df.iloc[:, :2]
                return df

            elif chart_type in ["scatter", "histogram", "box"]:
                # Return numeric columns
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    return df[numeric_cols[:2]]  # Use first 2 numeric columns
                return df

            elif chart_type == "heatmap":
                # Return correlation-ready data (numeric columns)
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 1:
                    return df[numeric_cols]
                return df

            else:
                return df

        except Exception as e:
            logger.error(f"Error preparing chart DataFrame: {e}")
            return None

    def _prepare_dataframe_for_chart(
        self,
        df: pd.DataFrame,
        chart_type: str,
        x_column: Optional[str] = None,
        y_column: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """Prepare DataFrame for specific chart type."""
        try:
            if chart_type == "line":
                if x_column and y_column:
                    if x_column in df.columns and y_column in df.columns:
                        return df[[x_column, y_column]]
                # Auto-detect
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    numeric_cols = df.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) > 0:
                        return df[["timestamp", numeric_cols[0]]]
                return df

            elif chart_type == "bar":
                if x_column and y_column:
                    if x_column in df.columns and y_column in df.columns:
                        return df[[x_column, y_column]]
                return df

            elif chart_type == "scatter":
                if x_column and y_column:
                    if x_column in df.columns and y_column in df.columns:
                        return df[[x_column, y_column]]
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) >= 2:
                    return df[numeric_cols[:2]]
                return df

            else:
                return df

        except Exception as e:
            logger.error(f"Error preparing DataFrame for chart: {e}")
            return None

    def _get_builtin_templates(self) -> List[Dict[str, Any]]:
        """Get built-in chart templates."""
        return [
            {
                "id": "template_line_trend",
                "name": "Time Series Trend",
                "chart_type": "line",
                "description": "Line chart for showing trends over time",
                "default_config": {
                    "show_grid": True,
                    "show_legend": True,
                    "colors": ["#1f77b4", "#ff7f0e"]
                }
            },
            {
                "id": "template_bar_comparison",
                "name": "Bar Comparison",
                "chart_type": "bar",
                "description": "Bar chart for comparing categories",
                "default_config": {
                    "show_grid": True,
                    "colors": ["#2ca02c", "#d62728"]
                }
            },
            {
                "id": "template_pie_distribution",
                "name": "Pie Distribution",
                "chart_type": "pie",
                "description": "Pie chart for showing proportions",
                "default_config": {
                    "colors": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
                }
            }
        ]


# Global chart service instance
chart_service = ChartService()