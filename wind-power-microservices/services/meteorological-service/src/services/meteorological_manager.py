"""
Main meteorological manager that orchestrates all weather services
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .weather_api_client import WeatherAPIClient
from .weather_data_processor import WeatherDataProcessor
from .forecast_service import ForecastService
from .alert_service import WeatherAlertService
from ..database import weather_station_crud, db_manager
from ..models import WeatherStationResponse, WeatherDataCreate, WeatherSummary
from ..config import get_settings
from ..utils import get_logger

logger = get_logger(__name__)


class MeteorologicalManager:
    """Main manager for meteorological services."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)

        # Initialize services
        self.api_client = WeatherAPIClient()
        self.data_processor = WeatherDataProcessor()
        self.forecast_service = ForecastService()
        self.alert_service = WeatherAlertService()

        # Service status
        self.is_initialized = False
        self.services_status = {}

        # Background tasks
        self._data_collection_task = None
        self._forecast_update_task = None
        self._alert_monitoring_task = None
        self._running = False

    async def initialize(self):
        """Initialize the meteorological manager and all services."""
        try:
            self.logger.info("Initializing Meteorological Manager...")

            # Initialize API client
            await self.api_client.initialize()
            self.services_status["api_client"] = "initialized"

            # Initialize database
            await db_manager.init_db(self.settings.database_url)
            await db_manager.create_tables()
            self.services_status["database"] = "connected"

            # Start background tasks
            self._running = True
            self._data_collection_task = asyncio.create_task(self._data_collection_loop())
            self._forecast_update_task = asyncio.create_task(self._forecast_update_loop())
            self._alert_monitoring_task = asyncio.create_task(self._alert_monitoring_loop())

            self.is_initialized = True
            self.services_status["manager"] = "initialized"

            self.logger.info("Meteorological Manager initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize Meteorological Manager: {e}")
            raise

    async def shutdown(self):
        """Shutdown the meteorological manager and all services."""
        try:
            self.logger.info("Shutting down Meteorological Manager...")

            self._running = False

            # Cancel background tasks
            tasks = [
                self._data_collection_task,
                self._forecast_update_task,
                self._alert_monitoring_task
            ]

            for task in tasks:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            # Close API client
            await self.api_client.close()
            self.services_status["api_client"] = "closed"

            # Close database
            await db_manager.close_db()
            self.services_status["database"] = "closed"

            self.is_initialized = False
            self.services_status["manager"] = "shutdown"

            self.logger.info("Meteorological Manager shutdown completed")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    async def collect_weather_data(
        self,
        station: WeatherStationResponse,
        include_forecast: bool = True
    ) -> Dict[str, Any]:
        """Collect weather data for a specific station."""
        try:
            self.logger.info(f"Collecting weather data for station {station.code}")

            # Get current weather data
            current_data = await self.api_client.get_current_weather(
                latitude=station.latitude,
                longitude=station.longitude,
                wind_farm_id=station.wind_farm_id,
                station_id=station.id
            )

            # Process the data
            processing_result = await self.data_processor.process_weather_data(current_data)

            # Store processed data in database
            async for db_session in db_manager.get_session():
                for record in processing_result["processed_records"]:
                    await weather_station_crud.create_weather_data(db_session, record)
                break

            # Get forecast if requested
            forecast_data = []
            if include_forecast:
                forecast_data = await self.api_client.get_weather_forecast(
                    latitude=station.latitude,
                    longitude=station.longitude,
                    hours=self.settings.forecast_hours,
                    wind_farm_id=station.wind_farm_id,
                    station_id=station.id
                )

            # Get weather alerts
            alerts = await self.api_client.get_weather_alerts(
                latitude=station.latitude,
                longitude=station.longitude,
                wind_farm_id=station.wind_farm_id
            )

            # Process alerts
            alert_result = await self.alert_service.process_weather_alerts(alerts)

            return {
                "station_id": station.id,
                "station_code": station.code,
                "collected_records": len(current_data),
                "processed_records": processing_result["valid_records"],
                "quality_issues": processing_result["quality_issues"],
                "forecast_records": len(forecast_data),
                "alerts_processed": alert_result["new_alerts"],
                "collection_time": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error collecting weather data for station {station.code}: {e}")
            raise

    async def generate_weather_forecast(
        self,
        station: WeatherStationResponse,
        hours: int = 24,
        include_ensemble: bool = True
    ) -> Dict[str, Any]:
        """Generate weather forecast for a specific station."""
        try:
            self.logger.info(f"Generating forecast for station {station.code}, hours: {hours}")

            # Get historical data for training
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=14)

            async for db_session in db_manager.get_session():
                historical_data = await weather_station_crud.get_station_data(
                    db_session, station.id, start_time, end_time
                )
                break

            # Generate forecast
            forecast_result = await self.forecast_service.generate_forecast(
                station_id=station.id,
                wind_farm_id=station.wind_farm_id,
                hours=hours,
                include_ensemble=include_ensemble
            )

            return forecast_result

        except Exception as e:
            self.logger.error(f"Error generating forecast for station {station.code}: {e}")
            raise

    async def get_weather_summary(
        self,
        wind_farm_id: str,
        period_hours: int = 24
    ) -> WeatherSummary:
        """Get weather summary for a wind farm."""
        try:
            self.logger.info(f"Getting weather summary for wind farm {wind_farm_id}")

            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=period_hours)

            # Get stations for the wind farm
            async for db_session in db_manager.get_session():
                stations = await weather_station_crud.get_by_wind_farm(db_session, wind_farm_id)
                break

            if not stations:
                raise ValueError(f"No weather stations found for wind farm {wind_farm_id}")

            # Calculate summary for each station
            station_summaries = []
            for station in stations:
                summary = await self.data_processor.calculate_weather_summary(
                    wind_farm_id=wind_farm_id,
                    station_id=station.id,
                    start_time=start_time,
                    end_time=end_time
                )
                station_summaries.append(summary)

            # Aggregate across stations
            aggregated_summary = self._aggregate_station_summaries(station_summaries)

            return WeatherSummary(
                wind_farm_id=wind_farm_id,
                station_id="aggregated",
                timestamp=datetime.utcnow(),
                temperature=aggregated_summary.get("temperature"),
                humidity=aggregated_summary.get("humidity"),
                wind_speed=aggregated_summary.get("wind_speed"),
                wind_direction=aggregated_summary.get("wind_direction"),
                pressure=aggregated_summary.get("pressure"),
                precipitation=aggregated_summary.get("precipitation"),
                cloud_cover=aggregated_summary.get("cloud_cover"),
                visibility=aggregated_summary.get("visibility")
            )

        except Exception as e:
            self.logger.error(f"Error getting weather summary for wind farm {wind_farm_id}: {e}")
            raise

    def _aggregate_station_summaries(self, station_summaries: List[Dict[str, Any]]) -> Dict[str, float]:
        """Aggregate summaries from multiple stations."""
        if not station_summaries:
            return {}

        aggregated = {}
        parameters = [
            "temperature", "humidity", "wind_speed", "wind_direction",
            "pressure", "precipitation", "cloud_cover", "visibility"
        ]

        for param in parameters:
            values = []
            for summary in station_summaries:
                if param in summary.get("parameters", {}):
                    values.append(summary["parameters"][param]["mean"])

            if values:
                aggregated[param] = np.mean(values)

        return aggregated

    async def check_weather_alert_impact(
        self,
        wind_farm_id: str,
        turbine_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Check the impact of weather alerts on wind farm operations."""
        try:
            impact_analysis = await self.alert_service.check_alert_impact(
                wind_farm_id=wind_farm_id,
                turbine_ids=turbine_ids
            )

            return impact_analysis

        except Exception as e:
            self.logger.error(f"Error checking weather alert impact: {e}")
            raise

    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status and health information."""
        try:
            # Check API connectivity
            api_healthy = await self.api_client.ping()

            # Get service statistics
            processor_stats = await self.data_processor.get_processing_statistics()
            alert_stats = await self.alert_service.get_processing_statistics()

            return {
                "status": "healthy" if api_healthy else "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "services": self.services_status,
                "api_connectivity": api_healthy,
                "statistics": {
                    "data_processing": processor_stats,
                    "alert_processing": alert_stats
                }
            }

        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    # Background task loops
    async def _data_collection_loop(self):
        """Background loop for automatic weather data collection."""
        self.logger.info("Starting weather data collection loop")

        while self._running:
            try:
                # Get all active weather stations
                async for db_session in db_manager.get_session():
                    stations = await weather_station_crud.get_multi(db_session)
                    active_stations = [s for s in stations["items"] if s.is_active]
                    break

                # Collect data for each station
                for station in active_stations:
                    try:
                        await self.collect_weather_data(station, include_forecast=True)
                        await asyncio.sleep(1)  # Small delay between stations
                    except Exception as e:
                        self.logger.error(f"Error collecting data for station {station.code}: {e}")

                self.logger.info(f"Completed weather data collection cycle for {len(active_stations)} stations")

                # Wait for next collection cycle
                await asyncio.sleep(self.settings.weather_data_collection_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in data collection loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

        self.logger.info("Weather data collection loop stopped")

    async def _forecast_update_loop(self):
        """Background loop for forecast updates."""
        self.logger.info("Starting forecast update loop")

        while self._running:
            try:
                # Get all active weather stations
                async for db_session in db_manager.get_session():
                    stations = await weather_station_crud.get_multi(db_session)
                    active_stations = [s for s in stations["items"] if s.is_active]
                    break

                # Generate forecasts for each station
                for station in active_stations:
                    try:
                        await self.generate_weather_forecast(
                            station,
                            hours=self.settings.forecast_hours,
                            include_ensemble=True
                        )
                        await asyncio.sleep(2)  # Small delay between stations
                    except Exception as e:
                        self.logger.error(f"Error generating forecast for station {station.code}: {e}")

                self.logger.info(f"Completed forecast update cycle for {len(active_stations)} stations")

                # Wait for next update cycle
                await asyncio.sleep(self.settings.forecast_update_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in forecast update loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying

        self.logger.info("Forecast update loop stopped")

    async def _alert_monitoring_loop(self):
        """Background loop for alert monitoring and expiration."""
        self.logger.info("Starting alert monitoring loop")

        while self._running:
            try:
                # Expire old alerts
                expired_count = await self.alert_service.expire_old_alerts()

                if expired_count > 0:
                    self.logger.info(f"Expired {expired_count} old weather alerts")

                # Wait for next check cycle
                await asyncio.sleep(3600)  # Check every hour

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in alert monitoring loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying

        self.logger.info("Alert monitoring loop stopped")

    # Utility methods
    async def cleanup_old_data(self, retention_days: int = 30):
        """Clean up old weather data from processing cache."""
        try:
            await self.data_processor.cleanup_old_data(retention_hours=retention_days * 24)
            self.logger.info(f"Cleaned up weather data older than {retention_days} days")

        except Exception as e:
            self.logger.error(f"Error cleaning up old weather data: {e}")

    async def get_processing_statistics(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics."""
        try:
            data_stats = await self.data_processor.get_processing_statistics()
            forecast_stats = {}  # Would get from forecast service
            alert_stats = await self.alert_service.get_processing_statistics()

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "data_processing": data_stats,
                "forecast_processing": forecast_stats,
                "alert_processing": alert_stats,
                "service_status": self.services_status
            }

        except Exception as e:
            self.logger.error(f"Error getting processing statistics: {e}")
            return {"error": str(e)},