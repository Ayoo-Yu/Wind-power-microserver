"""
Chart generation service for Report Service
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import io
import base64
import pandas as pd
import numpy as np

from .config import get_settings, CHART_CONFIG
from .exceptions import ChartGenerationException
from .utils import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ChartGenerator:
    """Service for generating charts and visualizations."""

    def __init__(self):
        self.is_initialized = False
        self.chart_backends = {}

    async def initialize(self):
        """Initialize chart generator."""
        try:
            logger.info("Initializing Chart Generator...")

            # Initialize chart backends
            self.chart_backends = {
                "matplotlib": MatplotlibBackend(),
                "plotly": PlotlyBackend(),
                "seaborn": SeabornBackend()
            }

            # Initialize backends
            for backend in self.chart_backends.values():
                await backend.initialize()

            self.is_initialized = True
            logger.info("Chart Generator initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Chart Generator: {e}")
            raise ChartGenerationException(f"Initialization failed: {str(e)}")

    async def shutdown(self):
        """Shutdown chart generator."""
        try:
            logger.info("Shutting down Chart Generator...")
            for backend in self.chart_backends.values():
                await backend.shutdown()
            self.chart_backends.clear()
            self.is_initialized = False
            logger.info("Chart Generator shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def generate_chart(
        self,
        chart_type: str,
        data: pd.DataFrame,
        title: str = "Chart",
        config: Optional[Dict[str, Any]] = None,
        backend: str = "matplotlib"
    ) -> Optional[bytes]:
        """Generate a chart from data."""
        try:
            logger.info(f"Generating {chart_type} chart: {title}")

            if not self.is_initialized:
                raise ChartGenerationException("Chart generator not initialized")

            # Get chart backend
            chart_backend = self.chart_backends.get(backend)
            if not chart_backend:
                raise ChartGenerationException(f"Unknown chart backend: {backend}")

            # Generate chart based on type
            if chart_type == ChartType.LINE:
                return await chart_backend.generate_line_chart(data, title, config)
            elif chart_type == ChartType.BAR:
                return await chart_backend.generate_bar_chart(data, title, config)
            elif chart_type == ChartType.PIE:
                return await chart_backend.generate_pie_chart(data, title, config)
            elif chart_type == ChartType.SCATTER:
                return await chart_backend.generate_scatter_chart(data, title, config)
            elif chart_type == ChartType.HISTOGRAM:
                return await chart_backend.generate_histogram_chart(data, title, config)
            elif chart_type == ChartType.BOX:
                return await chart_backend.generate_box_chart(data, title, config)
            elif chart_type == ChartType.HEATMAP:
                return await chart_backend.generate_heatmap_chart(data, title, config)
            elif chart_type == ChartType.AREA:
                return await chart_backend.generate_area_chart(data, title, config)
            else:
                # Default to line chart
                return await chart_backend.generate_line_chart(data, title, config)

        except Exception as e:
            logger.error(f"Chart generation failed: {e}")
            raise ChartGenerationException(f"Failed to generate {chart_type} chart: {str(e)}")

    async def generate_multiple_charts(
        self,
        charts_config: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate multiple charts."""
        try:
            logger.info(f"Generating {len(charts_config)} charts")

            generated_charts = []

            for chart_config in charts_config:
                try:
                    chart_type = chart_config.get("type", "line")
                    data = chart_config.get("data")
                    title = chart_config.get("title", "Chart")
                    config = chart_config.get("config", {})
                    backend = chart_config.get("backend", "matplotlib")

                    if data is not None and not data.empty:
                        chart_image = await self.generate_chart(
                            chart_type=chart_type,
                            data=data,
                            title=title,
                            config=config,
                            backend=backend
                        )

                        if chart_image:
                            generated_charts.append({
                                "name": title,
                                "type": chart_type,
                                "image_data": base64.b64encode(chart_image).decode('utf-8'),
                                "config": config,
                                "backend": backend
                            })

                except Exception as e:
                    logger.warning(f"Failed to generate chart {chart_config.get('title', 'unknown')}: {e}")
                    continue

            logger.info(f"Generated {len(generated_charts)} charts successfully")
            return generated_charts

        except Exception as e:
            logger.error(f"Multiple chart generation failed: {e}")
            raise ChartGenerationException(f"Failed to generate multiple charts: {str(e)}")

    def prepare_chart_data(self, data: Any, chart_type: str) -> pd.DataFrame:
        """Prepare data for chart generation."""
        try:
            if isinstance(data, pd.DataFrame):
                return data
            elif isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict):
                return pd.DataFrame([data])
            else:
                raise ChartGenerationException(f"Unsupported data type for chart: {type(data)}")

        except Exception as e:
            logger.error(f"Chart data preparation failed: {e}")
            raise ChartGenerationException(f"Failed to prepare chart data: {str(e)}")


class ChartBackend:
    """Base class for chart backends."""

    async def initialize(self):
        """Initialize backend."""
        pass

    async def shutdown(self):
        """Shutdown backend."""
        pass

    async def generate_line_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate line chart."""
        raise NotImplementedError

    async def generate_bar_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate bar chart."""
        raise NotImplementedError

    async def generate_pie_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate pie chart."""
        raise NotImplementedError

    async def generate_scatter_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate scatter chart."""
        raise NotImplementedError

    async def generate_histogram_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate histogram chart."""
        raise NotImplementedError

    async def generate_box_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate box chart."""
        raise NotImplementedError

    async def generate_heatmap_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate heatmap chart."""
        raise NotImplementedError

    async def generate_area_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate area chart."""
        raise NotImplementedError

    def _get_default_config(self, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get default chart configuration."""
        default_config = {
            "width": settings.chart_default_width,
            "height": settings.chart_default_height,
            "dpi": settings.chart_dpi,
            "colors": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
            "font_size": 12,
            "title_font_size": 16,
            "show_grid": True,
            "show_legend": True
        }

        if config:
            default_config.update(config)

        return default_config


class MatplotlibBackend(ChartBackend):
    """Matplotlib chart backend."""

    async def initialize(self):
        """Initialize matplotlib backend."""
        try:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt
            self.plt = plt
            logger.info("Matplotlib backend initialized")
        except ImportError as e:
            logger.error(f"Matplotlib not available: {e}")
            raise ChartGenerationException("Matplotlib not available")

    async def shutdown(self):
        """Shutdown matplotlib backend."""
        try:
            self.plt.close('all')
        except Exception as e:
            logger.warning(f"Error closing matplotlib plots: {e}")

    async def generate_line_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate line chart using matplotlib."""
        try:
            config = self._get_default_config(config)

            fig, ax = self.plt.subplots(figsize=(config["width"]/100, config["height"]/100), dpi=config["dpi"])

            # Determine x and y columns
            x_col = data.columns[0] if len(data.columns) > 0 else "x"
            y_cols = data.columns[1:] if len(data.columns) > 1 else [data.columns[0]]

            # Plot lines
            for i, y_col in enumerate(y_cols):
                ax.plot(data[x_col], data[y_col],
                       color=config["colors"][i % len(config["colors"])],
                       linewidth=2, label=y_col)

            ax.set_title(title, fontsize=config["title_font_size"], fontweight='bold')
            ax.set_xlabel(x_col, fontsize=config["font_size"])
            ax.set_ylabel(y_cols[0] if len(y_cols) == 1 else 'Value', fontsize=config["font_size"])

            if config["show_grid"]:
                ax.grid(True, alpha=0.3)

            if config["show_legend"] and len(y_cols) > 1:
                ax.legend()

            # Save to bytes
            buffer = io.BytesIO()
            self.plt.savefig(buffer, format='png', bbox_inches='tight', dpi=config["dpi"])
            buffer.seek(0)
            image_data = buffer.getvalue()
            buffer.close()

            self.plt.close(fig)

            return image_data

        except Exception as e:
            logger.error(f"Matplotlib line chart generation failed: {e}")
            raise ChartGenerationException(f"Matplotlib line chart failed: {str(e)}")

    async def generate_bar_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate bar chart using matplotlib."""
        try:
            config = self._get_default_config(config)

            fig, ax = self.plt.subplots(figsize=(config["width"]/100, config["height"]/100), dpi=config["dpi"])

            # Determine x and y columns
            x_col = data.columns[0] if len(data.columns) > 0 else "x"
            y_col = data.columns[1] if len(data.columns) > 1 else data.columns[0]

            # Create bar chart
            bars = ax.bar(data[x_col], data[y_col],
                         color=config["colors"][0],
                         alpha=0.8)

            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}',
                       ha='center', va='bottom')

            ax.set_title(title, fontsize=config["title_font_size"], fontweight='bold')
            ax.set_xlabel(x_col, fontsize=config["font_size"])
            ax.set_ylabel(y_col, fontsize=config["font_size"])

            if config["show_grid"]:
                ax.grid(True, alpha=0.3, axis='y')

            # Rotate x-axis labels if needed
            if len(data) > 10:
                self.plt.xticks(rotation=45, ha='right')

            # Save to bytes
            buffer = io.BytesIO()
            self.plt.savefig(buffer, format='png', bbox_inches='tight', dpi=config["dpi"])
            buffer.seek(0)
            image_data = buffer.getvalue()
            buffer.close()

            self.plt.close(fig)

            return image_data

        except Exception as e:
            logger.error(f"Matplotlib bar chart generation failed: {e}")
            raise ChartGenerationException(f"Matplotlib bar chart failed: {str(e)}")

    async def generate_pie_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate pie chart using matplotlib."""
        try:
            config = self._get_default_config(config)

            fig, ax = self.plt.subplots(figsize=(config["width"]/100, config["height"]/100), dpi=config["dpi"])

            # Determine label and value columns
            label_col = data.columns[0] if len(data.columns) > 0 else "labels"
            value_col = data.columns[1] if len(data.columns) > 1 else data.columns[0]

            # Create pie chart
            wedges, texts, autotexts = ax.pie(data[value_col],
                                            labels=data[label_col],
                                            colors=config["colors"][:len(data)],
                                            autopct='%1.1f%%',
                                            startangle=90)

            ax.set_title(title, fontsize=config["title_font_size"], fontweight='bold')

            # Enhance text appearance
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')

            # Save to bytes
            buffer = io.BytesIO()
            self.plt.savefig(buffer, format='png', bbox_inches='tight', dpi=config["dpi"])
            buffer.seek(0)
            image_data = buffer.getvalue()
            buffer.close()

            self.plt.close(fig)

            return image_data

        except Exception as e:
            logger.error(f"Matplotlib pie chart generation failed: {e}")
            raise ChartGenerationException(f"Matplotlib pie chart failed: {str(e)}")

    async def generate_scatter_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate scatter chart using matplotlib."""
        try:
            config = self._get_default_config(config)

            fig, ax = self.plt.subplots(figsize=(config["width"]/100, config["height"]/100), dpi=config["dpi"])

            # Determine x and y columns
            x_col = data.columns[0] if len(data.columns) > 0 else "x"
            y_col = data.columns[1] if len(data.columns) > 1 else data.columns[0]

            # Create scatter plot
            ax.scatter(data[x_col], data[y_col],
                      color=config["colors"][0],
                      alpha=0.6,
                      s=config.get("point_size", 50))

            ax.set_title(title, fontsize=config["title_font_size"], fontweight='bold')
            ax.set_xlabel(x_col, fontsize=config["font_size"])
            ax.set_ylabel(y_col, fontsize=config["font_size"])

            if config["show_grid"]:
                ax.grid(True, alpha=0.3)

            # Save to bytes
            buffer = io.BytesIO()
            self.plt.savefig(buffer, format='png', bbox_inches='tight', dpi=config["dpi"])
            buffer.seek(0)
            image_data = buffer.getvalue()
            buffer.close()

            self.plt.close(fig)

            return image_data

        except Exception as e:
            logger.error(f"Matplotlib scatter chart generation failed: {e}")
            raise ChartGenerationException(f"Matplotlib scatter chart failed: {str(e)}")

    async def generate_histogram_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate histogram chart using matplotlib."""
        try:
            config = self._get_default_config(config)

            fig, ax = self.plt.subplots(figsize=(config["width"]/100, config["height"]/100), dpi=config["dpi"])

            # Use first numeric column
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) == 0:
                raise ChartGenerationException("No numeric data for histogram")

            value_col = numeric_cols[0]

            # Create histogram
            n, bins, patches = ax.hist(data[value_col],
                                     bins=config.get("bins", 20),
                                     color=config["colors"][0],
                                     alpha=0.7,
                                     edgecolor='black')

            ax.set_title(title, fontsize=config["title_font_size"], fontweight='bold')
            ax.set_xlabel(value_col, fontsize=config["font_size"])
            ax.set_ylabel('Frequency', fontsize=config["font_size"])

            if config["show_grid"]:
                ax.grid(True, alpha=0.3, axis='y')

            # Save to bytes
            buffer = io.BytesIO()
            self.plt.savefig(buffer, format='png', bbox_inches='tight', dpi=config["dpi"])
            buffer.seek(0)
            image_data = buffer.getvalue()
            buffer.close()

            self.plt.close(fig)

            return image_data

        except Exception as e:
            logger.error(f"Matplotlib histogram chart generation failed: {e}")
            raise ChartGenerationException(f"Matplotlib histogram chart failed: {str(e)}")

    async def generate_box_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate box chart using matplotlib."""
        try:
            config = self._get_default_config(config)

            fig, ax = self.plt.subplots(figsize=(config["width"]/100, config["height"]/100), dpi=config["dpi"])

            # Use numeric columns
            numeric_data = data.select_dtypes(include=[np.number])
            if numeric_data.empty:
                raise ChartGenerationException("No numeric data for box plot")

            # Create box plot
            box_plot = ax.boxplot([numeric_data[col].dropna() for col in numeric_data.columns],
                                labels=numeric_data.columns,
                                patch_artist=True)

            # Color the boxes
            for patch, color in zip(box_plot['boxes'], config["colors"]):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)

            ax.set_title(title, fontsize=config["title_font_size"], fontweight='bold')
            ax.set_ylabel('Values', fontsize=config["font_size"])

            if config["show_grid"]:
                ax.grid(True, alpha=0.3, axis='y')

            # Save to bytes
            buffer = io.BytesIO()
            self.plt.savefig(buffer, format='png', bbox_inches='tight', dpi=config["dpi"])
            buffer.seek(0)
            image_data = buffer.getvalue()
            buffer.close()

            self.plt.close(fig)

            return image_data

        except Exception as e:
            logger.error(f"Matplotlib box chart generation failed: {e}")
            raise ChartGenerationException(f"Matplotlib box chart failed: {str(e)}")


class PlotlyBackend(ChartBackend):
    """Plotly chart backend."""

    async def initialize(self):
        """Initialize plotly backend."""
        try:
            import plotly.graph_objects as go
            import plotly.io as pio
            self.go = go
            self.pio = pio
            logger.info("Plotly backend initialized")
        except ImportError as e:
            logger.error(f"Plotly not available: {e}")
            raise ChartGenerationException("Plotly not available")

    async def shutdown(self):
        """Shutdown plotly backend."""
        pass

    async def generate_line_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate line chart using plotly."""
        try:
            config = self._get_default_config(config)

            # Determine x and y columns
            x_col = data.columns[0] if len(data.columns) > 0 else "x"
            y_cols = data.columns[1:] if len(data.columns) > 1 else [data.columns[0]]

            fig = self.go.Figure()

            # Add traces
            for i, y_col in enumerate(y_cols):
                fig.add_trace(self.go.Scatter(
                    x=data[x_col],
                    y=data[y_col],
                    mode='lines+markers',
                    name=y_col,
                    line=dict(color=config["colors"][i % len(config["colors"])], width=2)
                ))

            fig.update_layout(
                title=title,
                xaxis_title=x_col,
                yaxis_title=y_cols[0] if len(y_cols) == 1 else 'Value',
                width=config["width"],
                height=config["height"],
                showlegend=config["show_legend"]
            )

            # Convert to image
            img_bytes = self.pio.to_image(fig, format='png', width=config["width"], height=config["height"])

            return img_bytes

        except Exception as e:
            logger.error(f"Plotly line chart generation failed: {e}")
            raise ChartGenerationException(f"Plotly line chart failed: {str(e)}")

    async def generate_bar_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate bar chart using plotly."""
        try:
            config = self._get_default_config(config)

            # Determine x and y columns
            x_col = data.columns[0] if len(data.columns) > 0 else "x"
            y_col = data.columns[1] if len(data.columns) > 1 else data.columns[0]

            fig = self.go.Figure(data=[
                self.go.Bar(
                    x=data[x_col],
                    y=data[y_col],
                    marker_color=config["colors"][0]
                )
            ])

            fig.update_layout(
                title=title,
                xaxis_title=x_col,
                yaxis_title=y_col,
                width=config["width"],
                height=config["height"]
            )

            # Convert to image
            img_bytes = self.pio.to_image(fig, format='png', width=config["width"], height=config["height"])

            return img_bytes

        except Exception as e:
            logger.error(f"Plotly bar chart generation failed: {e}")
            raise ChartGenerationException(f"Plotly bar chart failed: {str(e)}")


class SeabornBackend(ChartBackend):
    """Seaborn chart backend."""

    async def initialize(self):
        """Initialize seaborn backend."""
        try:
            import seaborn as sns
            import matplotlib.pyplot as plt
            self.sns = sns
            self.plt = plt

            # Set seaborn style
            self.sns.set_style("whitegrid")
            self.sns.set_palette("husl")

            logger.info("Seaborn backend initialized")
        except ImportError as e:
            logger.error(f"Seaborn not available: {e}")
            raise ChartGenerationException("Seaborn not available")

    async def shutdown(self):
        """Shutdown seaborn backend."""
        try:
            self.plt.close('all')
        except Exception as e:
            logger.warning(f"Error closing seaborn plots: {e}")

    async def generate_heatmap_chart(self, data: pd.DataFrame, title: str, config: Optional[Dict[str, Any]]) -> bytes:
        """Generate heatmap chart using seaborn."""
        try:
            config = self._get_default_config(config)

            fig, ax = self.plt.subplots(figsize=(config["width"]/100, config["height"]/100), dpi=config["dpi"])

            # Create correlation matrix if not provided
            if data.shape[1] > 1:
                corr_matrix = data.corr()
            else:
                corr_matrix = data

            # Create heatmap
            heatmap = self.sns.heatmap(corr_matrix,
                                     annot=True,
                                     cmap='coolwarm',
                                     center=0,
                                     square=True,
                                     linewidths=0.5,
                                     cbar_kws={"shrink": .8})

            ax.set_title(title, fontsize=config["title_font_size"], fontweight='bold')

            # Save to bytes
            buffer = io.BytesIO()
            self.plt.savefig(buffer, format='png', bbox_inches='tight', dpi=config["dpi"])
            buffer.seek(0)
            image_data = buffer.getvalue()
            buffer.close()

            self.plt.close(fig)

            return image_data

        except Exception as e:
            logger.error(f"Seaborn heatmap chart generation failed: {e}")
            raise ChartGenerationException(f"Seaborn heatmap chart failed: {str(e)}")


# Global chart generator instance
chart_generator = ChartGenerator()