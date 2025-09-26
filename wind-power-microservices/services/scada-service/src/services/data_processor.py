"""
SCADA Data Processing Service - Real-time data processing and analysis.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import logging
import numpy as np
from collections import defaultdict, deque

from ..models import ScadaDataPoint, TurbineStatusData, AlarmSeverity, AlarmStatus
from ..database import alarm_crud, turbine_crud, wind_farm_crud
from ..exceptions import InvalidScadaDataException, ValidationException
from ..utils import get_logger, create_scada_data_processor


logger = get_logger(__name__)


class DataProcessor:
    """SCADA data processing service."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.data_processor = create_scada_data_processor()
        self.turbine_cache: Dict[str, Dict[str, Any]] = {}
        self.data_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.alarm_cache: Dict[str, Dict[str, Any]] = {}
        self._processing_stats = {
            "total_points_processed": 0,
            "alarms_generated": 0,
            "anomalies_detected": 0,
            "last_processing_time": None
        }

    async def process_data_points(self, data_points: List[ScadaDataPoint]) -> Dict[str, Any]:
        """Process incoming SCADA data points."""
        try:
            start_time = datetime.utcnow()
            self.logger.debug(f"Processing {len(data_points)} data points")

            processed_points = []
            alarms_generated = []
            anomalies_detected = []

            for point in data_points:
                try:
                    # Process individual data point
                    result = await self._process_single_point(point)

                    if result["processed"]:
                        processed_points.append(result["data"])

                    if result["alarm"]:
                        alarms_generated.extend(result["alarms"])

                    if result["anomaly"]:
                        anomalies_detected.append(result["anomaly"])

                except Exception as e:
                    self.logger.error(f"Error processing data point {point.point_id}: {e}")

            # Update statistics
            self._processing_stats["total_points_processed"] += len(processed_points)
            self._processing_stats["alarms_generated"] += len(alarms_generated)
            self._processing_stats["anomalies_detected"] += len(anomalies_detected)
            self._processing_stats["last_processing_time"] = (datetime.utcnow() - start_time).total_seconds()

            self.logger.debug(f"Data processing completed: {len(processed_points)} points, {len(alarms_generated)} alarms, {len(anomalies_detected)} anomalies")

            return {
                "processed_points": processed_points,
                "alarms_generated": alarms_generated,
                "anomalies_detected": anomalies_detected,
                "processing_stats": self._processing_stats.copy(),
                "processing_time": (datetime.utcnow() - start_time).total_seconds()
            }

        except Exception as e:
            self.logger.error(f"Error processing data points: {e}")
            raise InvalidScadaDataException(f"Data processing failed: {str(e)}")

    async def _process_single_point(self, point: ScadaDataPoint) -> Dict[str, Any]:
        """Process a single SCADA data point."""
        try:
            # Store in history
            self._store_in_history(point)

            # Validate data quality
            if point.quality != "good":
                return {
                    "processed": False,
                    "data": point,
                    "alarm": point.is_alarm,
                    "alarms": [],
                    "anomaly": None,
                    "reason": f"Bad data quality: {point.quality}"
                }

            # Validate value ranges
            validation_result = await self._validate_value_range(point)
            if not validation_result["valid"]:
                return {
                    "processed": False,
                    "data": point,
                    "alarm": True,
                    "alarms": validation_result["alarms"],
                    "anomaly": None,
                    "reason": validation_result["reason"]
                }

            # Detect anomalies
            anomaly_result = await self._detect_anomalies(point)

            # Generate turbine status if applicable
            status_update = None
            if point.turbine_id:
                status_update = await self._update_turbine_status(point)

            # Process alarms
            alarms = []
            if point.is_alarm:
                alarms = await self._generate_alarms(point)
            elif anomaly_result["is_anomaly"]:
                alarms = await self._generate_anomaly_alarms(point, anomaly_result)

            return {
                "processed": True,
                "data": point,
                "alarm": len(alarms) > 0,
                "alarms": alarms,
                "anomaly": anomaly_result if anomaly_result["is_anomaly"] else None,
                "status_update": status_update
            }

        except Exception as e:
            self.logger.error(f"Error processing single point {point.point_id}: {e}")
            return {
                "processed": False,
                "data": point,
                "alarm": False,
                "alarms": [],
                "anomaly": None,
                "reason": str(e)
            }

    def _store_in_history(self, point: ScadaDataPoint):
        """Store data point in history cache."""
        key = f"{point.wind_farm_id}:{point.turbine_id}:{point.point_id}"
        self.data_history[key].append({
            "timestamp": point.timestamp,
            "value": point.value,
            "quality": point.quality
        })

    async def _validate_value_range(self, point: ScadaDataPoint) -> Dict[str, Any]:
        """Validate data point value against expected ranges."""
        try:
            # Get data point configuration (would come from database)
            # For now, use some common validation rules

            alarms = []

            # Power validation
            if "power" in point.point_name.lower():
                if point.value < 0:
                    alarms.append({
                        "alarm_code": "NEGATIVE_POWER",
                        "alarm_name": "Negative Power Detected",
                        "description": f"Negative power value: {point.value} MW",
                        "severity": "warning",
                        "actual_value": point.value,
                        "expected_range": "0 to 3.0 MW"
                    })
                elif point.value > 3.0:  # Typical max for 2.5MW turbine
                    alarms.append({
                        "alarm_code": "POWER_TOO_HIGH",
                        "alarm_name": "Power Output Too High",
                        "description": f"Power output exceeds rated capacity: {point.value} MW",
                        "severity": "critical",
                        "actual_value": point.value,
                        "expected_range": "0 to 3.0 MW"
                    })

            # Wind speed validation
            elif "wind" in point.point_name.lower() and "speed" in point.point_name.lower():
                if point.value < 0:
                    alarms.append({
                        "alarm_code": "NEGATIVE_WIND_SPEED",
                        "alarm_name": "Negative Wind Speed",
                        "description": f"Negative wind speed detected: {point.value} m/s",
                        "severity": "warning",
                        "actual_value": point.value,
                        "expected_range": "0 to 30 m/s"
                    })
                elif point.value > 30:  # Unrealistically high
                    alarms.append({
                        "alarm_code": "WIND_SPEED_TOO_HIGH",
                        "alarm_name": "Wind Speed Too High",
                        "description": f"Wind speed exceeds realistic range: {point.value} m/s",
                        "severity": "warning",
                        "actual_value": point.value,
                        "expected_range": "0 to 30 m/s"
                    })

            # Temperature validation
            elif "temperature" in point.point_name.lower():
                if point.value < -40 or point.value > 80:
                    alarms.append({
                        "alarm_code": "TEMPERATURE_OUT_OF_RANGE",
                        "alarm_name": "Temperature Out of Range",
                        "description": f"Temperature outside normal operating range: {point.value} °C",
                        "severity": "warning",
                        "actual_value": point.value,
                        "expected_range": "-40 to 80 °C"
                    })

            return {
                "valid": len(alarms) == 0,
                "alarms": alarms,
                "reason": f"Validation failed with {len(alarms)} alarms" if alarms else "Valid"
            }

        except Exception as e:
            self.logger.error(f"Error validating value range: {e}")
            return {
                "valid": False,
                "alarms": [],
                "reason": str(e)
            }

    async def _detect_anomalies(self, point: ScadaDataPoint) -> Dict[str, Any]:
        """Detect anomalies in data point."""
        try:
            key = f"{point.wind_farm_id}:{point.turbine_id}:{point.point_id}"
            history = list(self.data_history[key])

            if len(history) < 10:
                return {"is_anomaly": False, "confidence": 0.0, "method": "insufficient_data"}

            # Extract values for analysis
            values = [h["value"] for h in history if h["quality"] == "good"]

            if len(values) < 5:
                return {"is_anomaly": False, "confidence": 0.0, "method": "insufficient_quality_data"}

            # Statistical anomaly detection
            result = self.data_processor.detect_anomalies(point.value, values, threshold=2.5)

            # Add point-specific context
            result["point_id"] = point.point_id
            result["point_name"] = point.point_name
            result["current_value"] = point.value
            result["historical_mean"] = np.mean(values)
            result["historical_std"] = np.std(values)
            result["sample_size"] = len(values)

            return result

        except Exception as e:
            self.logger.error(f"Error detecting anomalies for point {point.point_id}: {e}")
            return {"is_anomaly": False, "confidence": 0.0, "method": "error", "error": str(e)}

    async def _update_turbine_status(self, point: ScadaDataPoint) -> Optional[Dict[str, Any]]:
        """Update turbine status based on data point."""
        try:
            if not point.turbine_id:
                return None

            key = point.turbine_id

            # Initialize turbine cache if needed
            if key not in self.turbine_cache:
                self.turbine_cache[key] = {
                    "wind_farm_id": point.wind_farm_id,
                    "turbine_id": point.turbine_id,
                    "status": "unknown",
                    "power_output": 0.0,
                    "wind_speed": 0.0,
                    "rotor_speed": 0.0,
                    "availability": 100.0,
                    "last_update": datetime.utcnow()
                }

            turbine_data = self.turbine_cache[key]
            updated = False

            # Update based on point type
            if "power" in point.point_name.lower():
                turbine_data["power_output"] = point.value
                updated = True
            elif "wind" in point.point_name.lower() and "speed" in point.point_name.lower():
                turbine_data["wind_speed"] = point.value
                updated = True
            elif "rotor" in point.point_name.lower() and "speed" in point.point_name.lower():
                turbine_data["rotor_speed"] = point.value
                updated = True
            elif "status" in point.point_name.lower():
                turbine_data["status"] = "running" if point.value else "stopped"
                updated = True

            if updated:
                turbine_data["last_update"] = datetime.utcnow()

                # Calculate availability
                if turbine_data["status"] == "running":
                    turbine_data["availability"] = 100.0
                else:
                    turbine_data["availability"] = 0.0

                return turbine_data.copy()

            return None

        except Exception as e:
            self.logger.error(f"Error updating turbine status for {point.turbine_id}: {e}")
            return None

    async def _generate_alarms(self, point: ScadaDataPoint) -> List[Dict[str, Any]]:
        """Generate alarms from data point."""
        try:
            alarms = []

            # Create alarm based on point alarm status
            alarm_data = {
                "alarm_code": f"POINT_ALARM_{point.point_id}",
                "alarm_name": f"Point Alarm: {point.point_name}",
                "description": f"Data point {point.point_name} triggered alarm with value {point.value}",
                "severity": "critical" if point.quality == "bad" else "warning",
                "wind_farm_id": point.wind_farm_id,
                "turbine_id": point.turbine_id,
                "point_id": point.point_id,
                "actual_value": point.value,
                "unit": getattr(point, 'unit', ''),
                "triggered_at": point.timestamp.isoformat()
            }

            alarms.append(alarm_data)

            return alarms

        except Exception as e:
            self.logger.error(f"Error generating alarms for point {point.point_id}: {e}")
            return []

    async def _generate_anomaly_alarms(self, point: ScadaDataPoint, anomaly_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alarms from anomaly detection."""
        try:
            alarms = []

            if anomaly_result.get("is_anomaly", False) and anomaly_result.get("confidence", 0) > 0.7:
                alarm_data = {
                    "alarm_code": f"ANOMALY_{point.point_id}",
                    "alarm_name": f"Anomaly Detected: {point.point_name}",
                    "description": f"Anomalous value detected: {point.value} (z-score: {anomaly_result.get('z_score', 0):.2f})",
                    "severity": "warning" if anomaly_result["confidence"] < 0.9 else "critical",
                    "wind_farm_id": point.wind_farm_id,
                    "turbine_id": point.turbine_id,
                    "point_id": point.point_id,
                    "actual_value": point.value,
                    "threshold_value": anomaly_result.get("historical_mean"),
                    "unit": getattr(point, 'unit', ''),
                    "triggered_at": point.timestamp.isoformat(),
                    "anomaly_details": {
                        "z_score": anomaly_result.get("z_score"),
                        "confidence": anomaly_result.get("confidence"),
                        "method": anomaly_result.get("method"),
                        "historical_mean": anomaly_result.get("historical_mean"),
                        "historical_std": anomaly_result.get("std_dev")
                    }
                }

                alarms.append(alarm_data)

            return alarms

        except Exception as e:
            self.logger.error(f"Error generating anomaly alarms for point {point.point_id}: {e}")
            return []

    async def get_turbine_status_data(self, turbine_id: str) -> Optional[TurbineStatusData]:
        """Get current turbine status data."""
        try:
            if turbine_id not in self.turbine_cache:
                return None

            cache_data = self.turbine_cache[turbine_id]
            return TurbineStatusData(**cache_data)

        except Exception as e:
            self.logger.error(f"Error getting turbine status data for {turbine_id}: {e}")
            return None

    async def get_processing_statistics(self) -> Dict[str, Any]:
        """Get data processing statistics."""
        return {
            "total_points_processed": self._processing_stats["total_points_processed"],
            "alarms_generated": self._processing_stats["alarms_generated"],
            "anomalies_detected": self._processing_stats["anomalies_detected"],
            "last_processing_time": self._processing_stats["last_processing_time"],
            "turbines_monitored": len(self.turbine_cache),
            "data_points_in_history": sum(len(h) for h in self.data_history.values()),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def cleanup_old_data(self, retention_hours: int = 24):
        """Clean up old data from history."""
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

            self.logger.info(f"Cleaned up {cleaned_count} old data points from history")

        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")


class RealtimeDataAggregator:
    """Real-time data aggregation service."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.aggregations: Dict[str, Dict[str, Any]] = {}
        self.aggregation_windows = {
            "1min": timedelta(minutes=1),
            "5min": timedelta(minutes=5),
            "15min": timedelta(minutes=15),
            "1hour": timedelta(hours=1),
            "1day": timedelta(days=1)
        }

    async def aggregate_data_points(self, data_points: List[ScadaDataPoint], window: str) -> Dict[str, Any]:
        """Aggregate data points for specified time window."""
        try:
            if window not in self.aggregation_windows:
                raise ValidationException(f"Invalid aggregation window: {window}")

            # Group by wind farm and point type
            grouped_data = defaultdict(list)
            for point in data_points:
                key = f"{point.wind_farm_id}:{point.point_name}"
                grouped_data[key].append(point.value)

            # Calculate aggregations
            aggregations = {}
            for key, values in grouped_data.items():
                if values:
                    values_array = np.array(values)
                    aggregations[key] = {
                        "count": len(values),
                        "mean": float(np.mean(values_array)),
                        "min": float(np.min(values_array)),
                        "max": float(np.max(values_array)),
                        "std": float(np.std(values_array)),
                        "sum": float(np.sum(values_array)),
                        "window": window,
                        "timestamp": datetime.utcnow().isoformat()
                    }

            return {
                "window": window,
                "aggregations": aggregations,
                "total_points": len(data_points),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error aggregating data points: {e}")
            raise InvalidScadaDataException(f"Data aggregation failed: {str(e)}")


__all__ = ["DataProcessor", "RealtimeDataAggregator"]