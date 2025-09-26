"""
Data collector service for Report Service
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import hashlib
import json

from .config import get_settings
from .database import report_data_crud
from .exceptions import DataCollectionException, ExternalAPIException
from .utils import APIClient, get_logger, safe_divide

logger = get_logger(__name__)
settings = get_settings()


class DataCollector:
    """Service for collecting data from various sources for report generation."""

    def __init__(self):
        self.api_clients = {}
        self.is_initialized = False

    async def initialize(self):
        """Initialize data collector."""
        try:
            logger.info("Initializing Data Collector...")

            # Initialize API clients
            self.api_clients = {
                "power_prediction": APIClient(settings.power_prediction_api_url),
                "weather": APIClient(settings.weather_api_url),
                "scada": APIClient(settings.scada_api_url),
                "wind_farm": APIClient(settings.wind_farm_api_url)
            }

            self.is_initialized = True
            logger.info("Data Collector initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Data Collector: {e}")
            raise DataCollectionException(f"Initialization failed: {str(e)}")

    async def shutdown(self):
        """Shutdown data collector."""
        try:
            logger.info("Shutting down Data Collector...")
            self.api_clients.clear()
            self.is_initialized = False
            logger.info("Data Collector shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def collect_data(
        self,
        report_type: str,
        wind_farm_id: Optional[str] = None,
        turbine_ids: Optional[List[str]] = None,
        time_range: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        data_sources: Optional[List[str]] = None,
        db_session: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Collect data from various sources for report generation."""
        try:
            logger.info(f"Collecting data for report type: {report_type}, wind farm: {wind_farm_id}")

            # Determine time range
            if not time_range:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=1)
            else:
                start_time = time_range.get("start_date", datetime.utcnow() - timedelta(days=1))
                end_time = time_range.get("end_date", datetime.utcnow())

            # Determine data sources
            if not data_sources:
                data_sources = self._get_default_data_sources(report_type)

            # Collect data from each source
            collected_data = {}

            for source in data_sources:
                try:
                    logger.info(f"Collecting data from source: {source}")
                    source_data = await self._collect_from_source(
                        source=source,
                        report_type=report_type,
                        wind_farm_id=wind_farm_id,
                        turbine_ids=turbine_ids,
                        start_time=start_time,
                        end_time=end_time,
                        parameters=parameters,
                        filters=filters,
                        db_session=db_session
                    )

                    if source_data:
                        collected_data[source] = source_data
                        logger.info(f"Collected {len(source_data.get('data', []))} records from {source}")

                except Exception as e:
                    logger.warning(f"Failed to collect data from {source}: {e}")
                    # Continue with other sources even if one fails
                    continue

            # Cache collected data if database session is available
            if db_session and collected_data:
                await self._cache_collected_data(report_type, collected_data, db_session)

            logger.info(f"Data collection completed. Sources: {list(collected_data.keys())}")
            return collected_data

        except Exception as e:
            logger.error(f"Data collection failed: {e}")
            raise DataCollectionException(f"Data collection failed: {str(e)}")

    def _get_default_data_sources(self, report_type: str) -> List[str]:
        """Get default data sources for report type."""
        from .config import REPORT_TYPES

        report_config = REPORT_TYPES.get(report_type, {})
        return report_config.get("data_sources", ["scada"])

    async def _collect_from_source(
        self,
        source: str,
        report_type: str,
        wind_farm_id: Optional[str],
        turbine_ids: Optional[List[str]],
        start_time: datetime,
        end_time: datetime,
        parameters: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]],
        db_session: Optional[Any]
    ) -> Optional[Dict[str, Any]]:
        """Collect data from specific source."""
        try:
            if source == "scada":
                return await self._collect_scada_data(
                    wind_farm_id, turbine_ids, start_time, end_time, parameters, filters
                )
            elif source == "power_prediction":
                return await self._collect_power_prediction_data(
                    wind_farm_id, turbine_ids, start_time, end_time, parameters, filters
                )
            elif source == "meteorological":
                return await self._collect_weather_data(
                    wind_farm_id, start_time, end_time, parameters, filters
                )
            elif source == "wind_farm":
                return await self._collect_wind_farm_data(
                    wind_farm_id, parameters, filters
                )
            else:
                logger.warning(f"Unknown data source: {source}")
                return None

        except Exception as e:
            logger.error(f"Failed to collect data from {source}: {e}")
            return None

    async def _collect_scada_data(
        self,
        wind_farm_id: Optional[str],
        turbine_ids: Optional[List[str]],
        start_time: datetime,
        end_time: datetime,
        parameters: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Collect SCADA data."""
        try:
            logger.info(f"Collecting SCADA data for wind farm: {wind_farm_id}")

            # Build API request parameters
            params = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "hours": int((end_time - start_time).total_seconds() / 3600)
            }

            if wind_farm_id:
                params["wind_farm_id"] = wind_farm_id
            if turbine_ids:
                params["turbine_ids"] = turbine_ids

            # Add additional filters
            if filters:
                params.update(filters)

            # Make API request
            client = self.api_clients.get("scada")
            if not client:
                raise DataCollectionException("SCADA API client not available")

            response = await client.get("/api/v1/scada-data/by-time-range", params=params)

            if response and response.get("success"):
                data = response.get("data", [])

                # Process and validate data
                processed_data = self._process_scada_data(data)

                return {
                    "data": processed_data,
                    "count": len(processed_data),
                    "completeness": self._calculate_completeness(processed_data),
                    "validity": self._calculate_validity(processed_data),
                    "freshness": self._calculate_freshness(data, end_time),
                    "source": "scada"
                }
            else:
                logger.warning("No SCADA data received from API")
                return None

        except Exception as e:
            logger.error(f"SCADA data collection failed: {e}")
            raise ExternalAPIException("SCADA", str(e))

    async def _collect_power_prediction_data(
        self,
        wind_farm_id: Optional[str],
        turbine_ids: Optional[List[str]],
        start_time: datetime,
        end_time: datetime,
        parameters: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Collect power prediction data."""
        try:
            logger.info(f"Collecting power prediction data for wind farm: {wind_farm_id}")

            # Build API request parameters
            params = {
                "start_date": start_time.isoformat(),
                "end_date": end_time.isoformat(),
                "hours": int((end_time - start_time).total_seconds() / 3600)
            }

            if wind_farm_id:
                params["wind_farm_id"] = wind_farm_id
            if turbine_ids:
                params["turbine_ids"] = turbine_ids

            # Make API request
            client = self.api_clients.get("power_prediction")
            if not client:
                raise DataCollectionException("Power prediction API client not available")

            response = await client.get("/api/v1/predictions", params=params)

            if response and response.get("success"):
                data = response.get("data", [])

                # Process and validate data
                processed_data = self._process_prediction_data(data)

                return {
                    "data": processed_data,
                    "count": len(processed_data),
                    "completeness": self._calculate_completeness(processed_data),
                    "validity": self._calculate_validity(processed_data),
                    "freshness": self._calculate_freshness(data, end_time),
                    "source": "power_prediction"
                }
            else:
                logger.warning("No power prediction data received from API")
                return None

        except Exception as e:
            logger.error(f"Power prediction data collection failed: {e}")
            raise ExternalAPIException("Power Prediction", str(e))

    async def _collect_weather_data(
        self,
        wind_farm_id: Optional[str],
        start_time: datetime,
        end_time: datetime,
        parameters: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Collect weather data."""
        try:
            logger.info(f"Collecting weather data for wind farm: {wind_farm_id}")

            # Build API request parameters
            params = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "hours": int((end_time - start_time).total_seconds() / 3600)
            }

            if wind_farm_id:
                params["wind_farm_id"] = wind_farm_id

            # Make API request
            client = self.api_clients.get("weather")
            if not client:
                raise DataCollectionException("Weather API client not available")

            response = await client.get("/api/v1/weather-data", params=params)

            if response and response.get("success"):
                data = response.get("data", [])

                # Process and validate data
                processed_data = self._process_weather_data(data)

                return {
                    "data": processed_data,
                    "count": len(processed_data),
                    "completeness": self._calculate_completeness(processed_data),
                    "validity": self._calculate_validity(processed_data),
                    "freshness": self._calculate_freshness(data, end_time),
                    "source": "meteorological"
                }
            else:
                logger.warning("No weather data received from API")
                return None

        except Exception as e:
            logger.error(f"Weather data collection failed: {e}")
            raise ExternalAPIException("Meteorological", str(e))

    async def _collect_wind_farm_data(
        self,
        wind_farm_id: Optional[str],
        parameters: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Collect wind farm metadata."""
        try:
            logger.info(f"Collecting wind farm data for: {wind_farm_id}")

            # Make API request
            client = self.api_clients.get("wind_farm")
            if not client:
                raise DataCollectionException("Wind farm API client not available")

            if wind_farm_id:
                # Get specific wind farm
                response = await client.get(f"/api/v1/wind-farms/{wind_farm_id}")
                if response and response.get("success"):
                    data = [response.get("data", {})]
                else:
                    data = []
            else:
                # Get all wind farms
                response = await client.get("/api/v1/wind-farms", params=filters or {})
                if response and response.get("success"):
                    data = response.get("data", {}).get("items", [])
                else:
                    data = []

            return {
                "data": data,
                "count": len(data),
                "completeness": 1.0 if data else 0.0,
                "validity": 1.0,
                "freshness": 1.0,
                "source": "wind_farm"
            }

        except Exception as e:
            logger.error(f"Wind farm data collection failed: {e}")
            raise ExternalAPIException("Wind Farm", str(e))

    def _process_scada_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and validate SCADA data."""
        try:
            if not data:
                return []

            processed_data = []
            for record in data:
                try:
                    # Validate required fields
                    if not all(key in record for key in ["timestamp", "power_output"]):
                        continue

                    # Validate data ranges
                    power_output = record.get("power_output", 0)
                    if power_output < 0 or power_output > 5000:  # Reasonable limits
                        continue

                    # Convert timestamp
                    timestamp = record.get("timestamp")
                    if isinstance(timestamp, str):
                        try:
                            record["timestamp"] = pd.to_datetime(timestamp)
                        except:
                            continue

                    processed_data.append(record)

                except Exception as e:
                    logger.warning(f"Skipping invalid SCADA record: {e}")
                    continue

            return processed_data

        except Exception as e:
            logger.error(f"SCADA data processing failed: {e}")
            return []

    def _process_prediction_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and validate prediction data."""
        try:
            if not data:
                return []

            processed_data = []
            for record in data:
                try:
                    # Validate required fields
                    if not all(key in record for key in ["prediction_time", "predicted_power"]):
                        continue

                    # Validate data ranges
                    predicted_power = record.get("predicted_power", 0)
                    if predicted_power < 0 or predicted_power > 5000:
                        continue

                    # Convert timestamp
                    prediction_time = record.get("prediction_time")
                    if isinstance(prediction_time, str):
                        try:
                            record["prediction_time"] = pd.to_datetime(prediction_time)
                        except:
                            continue

                    processed_data.append(record)

                except Exception as e:
                    logger.warning(f"Skipping invalid prediction record: {e}")
                    continue

            return processed_data

        except Exception as e:
            logger.error(f"Prediction data processing failed: {e}")
            return []

    def _process_weather_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and validate weather data."""
        try:
            if not data:
                return []

            processed_data = []
            for record in data:
                try:
                    # Validate required fields
                    if not all(key in record for key in ["timestamp"]):
                        continue

                    # Validate weather parameters
                    wind_speed = record.get("wind_speed", 0)
                    if wind_speed < 0 or wind_speed > 50:  # Reasonable limits
                        continue

                    temperature = record.get("temperature", 0)
                    if temperature < -50 or temperature > 60:
                        continue

                    # Convert timestamp
                    timestamp = record.get("timestamp")
                    if isinstance(timestamp, str):
                        try:
                            record["timestamp"] = pd.to_datetime(timestamp)
                        except:
                            continue

                    processed_data.append(record)

                except Exception as e:
                    logger.warning(f"Skipping invalid weather record: {e}")
                    continue

            return processed_data

        except Exception as e:
            logger.error(f"Weather data processing failed: {e}")
            return []

    def _calculate_completeness(self, data: List[Dict[str, Any]]) -> float:
        """Calculate data completeness score."""
        try:
            if not data:
                return 0.0

            # Check for missing values in key fields
            total_records = len(data)
            if total_records == 0:
                return 0.0

            # Sample a few records to check completeness
            completeness_scores = []
            sample_size = min(100, total_records)
            sample_data = data[:sample_size]

            for record in sample_data:
                # Check for missing values
                missing_count = sum(1 for v in record.values() if v is None or (isinstance(v, float) and np.isnan(v)))
                total_fields = len(record)
                completeness = safe_divide(total_fields - missing_count, total_fields)
                completeness_scores.append(completeness)

            return np.mean(completeness_scores) if completeness_scores else 0.0

        except Exception as e:
            logger.error(f"Completeness calculation failed: {e}")
            return 0.0

    def _calculate_validity(self, data: List[Dict[str, Any]]) -> float:
        """Calculate data validity score."""
        try:
            if not data:
                return 0.0

            # Simple validity check - all records should have timestamps
            valid_records = sum(1 for record in data if record.get("timestamp") is not None)
            total_records = len(data)

            return safe_divide(valid_records, total_records)

        except Exception as e:
            logger.error(f"Validity calculation failed: {e}")
            return 0.0

    def _calculate_freshness(self, data: List[Dict[str, Any]], reference_time: datetime) -> float:
        """Calculate data freshness score."""
        try:
            if not data:
                return 0.0

            # Check if data is recent (within last 24 hours)
            recent_threshold = reference_time - timedelta(hours=24)

            recent_records = 0
            total_records = len(data)

            for record in data:
                timestamp = record.get("timestamp")
                if timestamp:
                    if isinstance(timestamp, str):
                        try:
                            timestamp = pd.to_datetime(timestamp)
                        except:
                            continue

                    if timestamp >= recent_threshold:
                        recent_records += 1

            return safe_divide(recent_records, total_records)

        except Exception as e:
            logger.error(f"Freshness calculation failed: {e}")
            return 0.0

    async def _cache_collected_data(self, report_type: str, data: Dict[str, Any], db_session: Any):
        """Cache collected data for future use."""
        try:
            for source, source_data in data.items():
                if source_data and isinstance(source_data, dict):
                    # Create query hash
                    query_params = {
                        "report_type": report_type,
                        "source": source,
                        "parameters": source_data.get("parameters", {})
                    }
                    query_hash = hashlib.md5(json.dumps(query_params, sort_keys=True).encode()).hexdigest()

                    # Cache data
                    cache_data = {
                        "report_id": f"cache_{report_type}_{source}",
                        "data_source": source,
                        "query_hash": query_hash,
                        "data": source_data.get("data", []),
                        "metadata": {
                            "count": source_data.get("count", 0),
                            "completeness": source_data.get("completeness", 0),
                            "validity": source_data.get("validity", 0),
                            "freshness": source_data.get("freshness", 0)
                        },
                        "cache_ttl_seconds": 3600,  # 1 hour cache
                        "expires_at": datetime.utcnow() + timedelta(hours=1)
                    }

                    await report_data_crud.create(db_session, cache_data)

        except Exception as e:
            logger.warning(f"Failed to cache collected data: {e}")

    async def get_cached_data(self, query_hash: str, db_session: Any) -> Optional[Dict[str, Any]]:
        """Get cached data if available."""
        try:
            cached_data = await report_data_crud.get_by_query_hash(db_session, query_hash)
            if cached_data:
                logger.info(f"Found cached data for query hash: {query_hash}")
                return {
                    "data": cached_data.data,
                    "metadata": cached_data.metadata,
                    "cached": True,
                    "cached_at": cached_data.created_at
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get cached data: {e}")
            return None

    async def cleanup_expired_cache(self, db_session: Any) -> int:
        """Clean up expired cached data."""
        try:
            deleted_count = await report_data_crud.cleanup_expired_data(db_session)
            logger.info(f"Cleaned up {deleted_count} expired cache entries")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            return 0


# Global data collector instance
data_collector = DataCollector()