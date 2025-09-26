"""
Weather data processing service for validation, quality control, and analysis
"""

import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque

from ..models import WeatherDataCreate, WeatherParameter, WeatherDataResponse
from ..database import weather_data_crud
from ..config import get_settings
from ..utils import get_logger

logger = get_logger(__name__)


class WeatherDataProcessor:
    """Weather data processing and validation service."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)

        # Data quality thresholds
        self.quality_thresholds = {
            WeatherParameter.TEMPERATURE: {
                "min": -50,  # °C
                "max": 60,
                "rate_of_change": 10,  # °C per hour
                "persistence": 6,  # hours
            },
            WeatherParameter.HUMIDITY: {
                "min": 0,   # %
                "max": 100,
                "rate_of_change": 30,  # % per hour
                "persistence": 12,
            },
            WeatherParameter.WIND_SPEED: {
                "min": 0,   # m/s
                "max": 50,
                "rate_of_change": 15,  # m/s per hour
                "persistence": 3,
            },
            WeatherParameter.WIND_DIRECTION: {
                "min": 0,   # degrees
                "max": 360,
                "rate_of_change": 180,  # degrees per hour
                "persistence": 2,
            },
            WeatherParameter.PRESSURE: {
                "min": 800,  # hPa
                "max": 1100,
                "rate_of_change": 10,  # hPa per hour
                "persistence": 24,
            },
        }

        # Data history for quality checks
        self.data_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Processing statistics
        self.processing_stats = {
            "total_records_processed": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "quality_flags_raised": 0,
            "last_processing_time": None,
        }

    async def process_weather_data(
        self,
        weather_data: List[WeatherDataCreate],
        db_session=None
    ) -> Dict[str, Any]:
        """Process incoming weather data."""
        try:
            start_time = datetime.utcnow()
            self.logger.info(f"Processing {len(weather_data)} weather data records")

            processed_records = []
            quality_issues = []
            valid_records = 0
            invalid_records = 0

            for record in weather_data:
                try:
                    # Validate individual record
                    validation_result = await self._validate_weather_record(record)

                    if validation_result["valid"]:
                        # Perform quality control checks
                        quality_result = await self._perform_quality_control(record)

                        if quality_result["quality"] == "good":
                            processed_records.append(record)
                            valid_records += 1
                        else:
                            # Record with quality flag
                            record.quality = quality_result["quality"]
                            processed_records.append(record)
                            quality_issues.append(quality_result["issue"])

                        # Store in history
                        self._store_in_history(record)

                    else:
                        invalid_records += 1
                        quality_issues.extend(validation_result["issues"])

                except Exception as e:
                    self.logger.error(f"Error processing weather record: {e}")
                    invalid_records += 1

            # Update statistics
            self.processing_stats["total_records_processed"] += len(weather_data)
            self.processing_stats["valid_records"] += valid_records
            self.processing_stats["invalid_records"] += invalid_records
            self.processing_stats["quality_flags_raised"] += len(quality_issues)
            self.processing_stats["last_processing_time"] = (datetime.utcnow() - start_time).total_seconds()

            self.logger.info(
                f"Weather data processing completed: {valid_records} valid, "
                f"{invalid_records} invalid, {len(quality_issues)} quality issues"
            )

            return {
                "processed_records": processed_records,
                "valid_records": valid_records,
                "invalid_records": invalid_records,
                "quality_issues": quality_issues,
                "processing_stats": self.processing_stats.copy(),
                "processing_time": (datetime.utcnow() - start_time).total_seconds()
            }

        except Exception as e:
            self.logger.error(f"Error processing weather data: {e}")
            raise

    async def _validate_weather_record(self, record: WeatherDataCreate) -> Dict[str, Any]:
        """Validate individual weather record."""
        issues = []

        # Check parameter validity
        if not isinstance(record.parameter, WeatherParameter):
            issues.append(f"Invalid parameter: {record.parameter}")
            return {"valid": False, "issues": issues}

        # Check value range based on parameter type
        thresholds = self.quality_thresholds.get(record.parameter)
        if thresholds:
            if record.value < thresholds["min"] or record.value > thresholds["max"]:
                issues.append(
                    f"Value {record.value} outside valid range [{thresholds['min']}, {thresholds['max']}] "
                    f"for {record.parameter}"
                )

        # Check unit consistency
        expected_units = self._get_expected_units(record.parameter)
        if record.unit not in expected_units:
            issues.append(f"Unexpected unit '{record.unit}' for {record.parameter}. Expected: {expected_units}")

        # Check timestamp validity
        if record.timestamp > datetime.utcnow() + timedelta(hours=1):
            issues.append("Timestamp is in the future")
        elif record.timestamp < datetime.utcnow() - timedelta(days=30):
            issues.append("Timestamp is too old")

        return {
            "valid": len(issues) == 0,
            "issues": issues
        }

    async def _perform_quality_control(self, record: WeatherDataCreate) -> Dict[str, Any]:
        """Perform quality control checks on weather data."""
        key = f"{record.station_id}:{record.parameter}"
        history = list(self.data_history[key])

        if len(history) < 3:
            return {"quality": "good", "issue": None}

        issues = []
        quality = "good"

        # Rate of change check
        rate_check = self._check_rate_of_change(record, history)
        if not rate_check["valid"]:
            issues.append(rate_check["issue"])
            quality = "questionable"

        # Persistence check
        persistence_check = self._check_persistence(record, history)
        if not persistence_check["valid"]:
            issues.append(persistence_check["issue"])
            if quality == "questionable":
                quality = "bad"
            else:
                quality = "questionable"

        # Statistical outlier detection
        outlier_check = self._detect_statistical_outliers(record, history)
        if not outlier_check["valid"]:
            issues.append(outlier_check["issue"])
            if quality == "questionable":
                quality = "bad"
            else:
                quality = "questionable"

        # Spatial consistency (if multiple stations available)
        spatial_check = await self._check_spatial_consistency(record)
        if not spatial_check["valid"]:
            issues.append(spatial_check["issue"])
            if quality == "questionable":
                quality = "bad"
            else:
                quality = "questionable"

        return {
            "quality": quality,
            "issue": {
                "parameter": record.parameter,
                "value": record.value,
                "issues": issues,
                "timestamp": record.timestamp
            } if issues else None
        }

    def _check_rate_of_change(
        self,
        record: WeatherDataCreate,
        history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Check if rate of change is within acceptable limits."""
        thresholds = self.quality_thresholds.get(record.parameter)
        if not thresholds or "rate_of_change" not in thresholds:
            return {"valid": True}

        # Get recent historical data (last hour)
        recent_history = [
            h for h in history
            if (record.timestamp - h["timestamp"]).total_seconds() / 3600 <= 1
        ]

        if not recent_history:
            return {"valid": True}

        # Calculate maximum rate of change
        max_rate = 0
        for hist_record in recent_history:
            time_diff = abs((record.timestamp - hist_record["timestamp"]).total_seconds() / 3600)
            if time_diff > 0:
                rate = abs(record.value - hist_record["value"]) / time_diff
                max_rate = max(max_rate, rate)

        if max_rate > thresholds["rate_of_change"]:
            return {
                "valid": False,
                "issue": f"Rate of change {max_rate:.2f} exceeds threshold {thresholds['rate_of_change']} for {record.parameter}"
            }

        return {"valid": True}

    def _check_persistence(
        self,
        record: WeatherDataCreate,
        history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Check for unrealistic persistence (unchanging values)."""
        thresholds = self.quality_thresholds.get(record.parameter)
        if not thresholds or "persistence" not in thresholds:
            return {"valid": True}

        # Check for exact same value over extended period
        identical_count = 0
        for hist_record in history:
            if abs(record.value - hist_record["value"]) < 0.001:  # Essentially identical
                identical_count += 1
            else:
                break

        if identical_count > thresholds["persistence"]:
            return {
                "valid": False,
                "issue": f"Value has been identical for {identical_count} consecutive readings for {record.parameter}"
            }

        return {"valid": True}

    def _detect_statistical_outliers(
        self,
        record: WeatherDataCreate,
        history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Detect statistical outliers using Z-score method."""
        if len(history) < 10:
            return {"valid": True}

        # Extract values for statistical analysis
        values = [h["value"] for h in history[-20:]]  # Use last 20 values

        if len(values) < 5:
            return {"valid": True}

        # Calculate statistics
        mean_val = np.mean(values)
        std_val = np.std(values)

        if std_val == 0:
            return {"valid": True}

        # Calculate Z-score
        z_score = abs(record.value - mean_val) / std_val

        # Flag as outlier if Z-score > 3 (99.7% confidence interval)
        if z_score > 3:
            return {
                "valid": False,
                "issue": f"Statistical outlier detected (Z-score: {z_score:.2f}) for {record.parameter}"
            }

        return {"valid": True}

    async def _check_spatial_consistency(
        self,
        record: WeatherDataCreate
    ) -> Dict[str, Any]:
        """Check spatial consistency with nearby stations."""
        # This would require spatial analysis and nearby station data
        # For now, return valid - can be enhanced later
        return {"valid": True}

    def _store_in_history(self, record: WeatherDataCreate):
        """Store record in history cache."""
        key = f"{record.station_id}:{record.parameter}"
        self.data_history[key].append({
            "timestamp": record.timestamp,
            "value": record.value,
            "quality": record.quality
        })

    def _get_expected_units(self, parameter: WeatherParameter) -> List[str]:
        """Get expected units for a weather parameter."""
        unit_map = {
            WeatherParameter.TEMPERATURE: ["celsius", "c", "°c", "fahrenheit", "f", "°f", "kelvin", "k"],
            WeatherParameter.HUMIDITY: ["percent", "%", "relative_humidity"],
            WeatherParameter.WIND_SPEED: ["m/s", "mps", "km/h", "kph", "mph", "knots"],
            WeatherParameter.WIND_DIRECTION: ["degrees", "deg", "°", "radians", "rad"],
            WeatherParameter.PRESSURE: ["hpa", "mb", "pa", "kpa", "bar", "mmhg", "inhg"],
            WeatherParameter.PRECIPITATION: ["mm", "cm", "m", "inches", "in"],
            WeatherParameter.CLOUD_COVER: ["percent", "%"],
            WeatherParameter.VISIBILITY: ["km", "m", "miles", "mi"],
            WeatherParameter.UV_INDEX: ["index", "uvi"],
        }
        return unit_map.get(parameter, [])

    async def calculate_weather_summary(
        self,
        wind_farm_id: str,
        station_id: str,
        start_time: datetime,
        end_time: datetime,
        db_session=None
    ) -> Dict[str, Any]:
        """Calculate weather summary for a specific period."""
        try:
            # Get data for the period
            if db_session:
                # Use database for historical data
                from ..database import weather_data_crud

                summary_data = {}
                for parameter in WeatherParameter:
                    data = await weather_data_crud.get_time_series(
                        db_session, station_id, parameter, start_time, end_time
                    )
                    if data:
                        values = [d.value for d in data if d.quality == "good"]
                        if values:
                            summary_data[parameter] = {
                                "mean": np.mean(values),
                                "min": np.min(values),
                                "max": np.max(values),
                                "std": np.std(values),
                                "count": len(values)
                            }
            else:
                # Use in-memory cache
                summary_data = self._calculate_summary_from_cache(station_id, start_time, end_time)

            return {
                "wind_farm_id": wind_farm_id,
                "station_id": station_id,
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "parameters": summary_data,
                "generated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error calculating weather summary: {e}")
            raise

    def _calculate_summary_from_cache(
        self,
        station_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Calculate summary from in-memory cache."""
        summary_data = {}

        for parameter in WeatherParameter:
            key = f"{station_id}:{parameter}"
            history = list(self.data_history[key])

            # Filter by time range
            period_data = [
                h for h in history
                if start_time <= h["timestamp"] <= end_time and h["quality"] == "good"
            ]

            if period_data:
                values = [h["value"] for h in period_data]
                summary_data[parameter] = {
                    "mean": np.mean(values),
                    "min": np.min(values),
                    "max": np.max(values),
                    "std": np.std(values),
                    "count": len(values)
                }

        return summary_data

    async def get_processing_statistics(self) -> Dict[str, Any]:
        """Get data processing statistics."""
        return {
            **self.processing_stats,
            "timestamp": datetime.utcnow().isoformat(),
            "cache_size": sum(len(h) for h in self.data_history.values()),
            "parameters_monitored": len(self.data_history)
        }

    async def cleanup_old_data(self, retention_hours: int = 168):
        """Clean up old data from history cache."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=retention_hours)
            cleaned_count = 0

            for key, history in self.data_history.items():
                original_length = len(history)

                # Remove old entries
                while history and history[0]["timestamp"] < cutoff_time:
                    history.popleft()
                    cleaned_count += 1

                new_length = len(history)
                if original_length != new_length:
                    self.logger.debug(f"Cleaned {original_length - new_length} old entries for {key}")

            self.logger.info(f"Cleaned up {cleaned_count} old weather data points from history")

        except Exception as e:
            self.logger.error(f"Error cleaning up old weather data: {e}")