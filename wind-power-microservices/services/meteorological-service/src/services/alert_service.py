"""
Weather alert service for monitoring and processing weather alerts
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from ..models import (
    WeatherAlertCreate, WeatherAlertResponse, AlertSeverity, WeatherAlertStatus,
    WeatherDataSource
)
from ..database import weather_alert_crud
from ..config import get_settings
from ..utils import get_logger

logger = get_logger(__name__)


class WeatherAlertService:
    """Service for managing weather alerts."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self.alert_cache = {}
        self.processing_stats = {
            "total_alerts_processed": 0,
            "active_alerts": 0,
            "expired_alerts": 0,
            "last_processing_time": None,
        }

    async def process_weather_alerts(
        self,
        alerts_data: List[Dict[str, Any]],
        db_session=None
    ) -> Dict[str, Any]:
        """Process incoming weather alerts."""
        try:
            start_time = datetime.utcnow()
            self.logger.info(f"Processing {len(alerts_data)} weather alerts")

            processed_alerts = []
            new_alerts = 0
            updated_alerts = 0
            expired_alerts = 0

            for alert_data in alerts_data:
                try:
                    # Check if alert already exists
                    existing_alert = await self._find_existing_alert(
                        alert_data["alert_id"], alert_data["wind_farm_id"]
                    )

                    if existing_alert:
                        # Update existing alert
                        updated = await self._update_alert(existing_alert, alert_data, db_session)
                        if updated:
                            updated_alerts += 1
                    else:
                        # Create new alert
                        new_alert = await self._create_alert(alert_data, db_session)
                        if new_alert:
                            processed_alerts.append(new_alert)
                            new_alerts += 1

                except Exception as e:
                    self.logger.error(f"Error processing weather alert: {e}")

            # Expire old alerts
            expired_count = await weather_alert_crud.expire_old_alerts(db_session)
            expired_alerts += expired_count

            # Update statistics
            self.processing_stats["total_alerts_processed"] += len(alerts_data)
            self.processing_stats["active_alerts"] += new_alerts
            self.processing_stats["expired_alerts"] += expired_alerts
            self.processing_stats["last_processing_time"] = (datetime.utcnow() - start_time).total_seconds()

            self.logger.info(
                f"Weather alerts processing completed: {new_alerts} new, "
                f"{updated_alerts} updated, {expired_alerts} expired"
            )

            return {
                "processed_alerts": processed_alerts,
                "new_alerts": new_alerts,
                "updated_alerts": updated_alerts,
                "expired_alerts": expired_alerts,
                "processing_stats": self.processing_stats.copy(),
                "processing_time": (datetime.utcnow() - start_time).total_seconds()
            }

        except Exception as e:
            self.logger.error(f"Error processing weather alerts: {e}")
            raise

    async def _create_alert(self, alert_data: Dict[str, Any], db_session=None) -> Optional[WeatherAlertResponse]:
        """Create a new weather alert."""
        try:
            # Validate alert data
            validation_result = self._validate_alert_data(alert_data)
            if not validation_result["valid"]:
                logger.warning(f"Invalid alert data: {validation_result['issues']}")
                return None

            # Create alert object
            alert_create = WeatherAlertCreate(
                alert_id=alert_data["alert_id"],
                title=alert_data["title"],
                description=alert_data["description"],
                severity=alert_data["severity"],
                wind_farm_id=alert_data["wind_farm_id"],
                effective_time=alert_data["effective_time"],
                expires_time=alert_data["expires_time"],
                areas=alert_data["areas"],
                parameters=alert_data.get("parameters", {}),
                source=alert_data["source"]
            )

            # Store in database
            if db_session:
                alert = await weather_alert_crud.create(db_session, alert_create.dict())
                return WeatherAlertResponse.from_orm(alert)

            return None

        except Exception as e:
            self.logger.error(f"Error creating weather alert: {e}")
            return None

    async def _update_alert(
        self,
        existing_alert: WeatherAlertResponse,
        alert_data: Dict[str, Any],
        db_session=None
    ) -> bool:
        """Update existing weather alert."""
        try:
            # Only update if there are changes
            updates = {}

            if existing_alert.title != alert_data["title"]:
                updates["title"] = alert_data["title"]

            if existing_alert.description != alert_data["description"]:
                updates["description"] = alert_data["description"]

            if existing_alert.severity != alert_data["severity"]:
                updates["severity"] = alert_data["severity"]

            if existing_alert.expires_time != alert_data["expires_time"]:
                updates["expires_time"] = alert_data["expires_time"]

            if existing_alert.areas != alert_data["areas"]:
                updates["areas"] = alert_data["areas"]

            if updates:
                if db_session:
                    await weather_alert_crud.update(db_session, existing_alert, updates)
                    self.logger.info(f"Updated alert {existing_alert.id}")
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error updating weather alert: {e}")
            return False

    async def _find_existing_alert(self, alert_id: str, wind_farm_id: str) -> Optional[WeatherAlertResponse]:
        """Find existing alert by external ID and wind farm."""
        try:
            # This would typically query the database
            # For now, return None (simplified implementation)
            return None

        except Exception as e:
            self.logger.error(f"Error finding existing alert: {e}")
            return None

    def _validate_alert_data(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate alert data."""
        issues = []
        required_fields = ["alert_id", "title", "description", "severity", "wind_farm_id", "effective_time", "expires_time", "areas"]

        # Check required fields
        for field in required_fields:
            if field not in alert_data or not alert_data[field]:
                issues.append(f"Missing required field: {field}")

        # Validate severity
        if "severity" in alert_data:
            try:
                AlertSeverity(alert_data["severity"])
            except ValueError:
                issues.append(f"Invalid severity: {alert_data['severity']}")

        # Validate timestamps
        if "effective_time" in alert_data and "expires_time" in alert_data:
            effective = alert_data["effective_time"]
            expires = alert_data["expires_time"]

            if isinstance(effective, str):
                try:
                    effective = datetime.fromisoformat(effective.replace("Z", "+00:00"))
                except ValueError:
                    issues.append("Invalid effective_time format")

            if isinstance(expires, str):
                try:
                    expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                except ValueError:
                    issues.append("Invalid expires_time format")

            if effective >= expires:
                issues.append("effective_time must be before expires_time")

            if expires < datetime.utcnow():
                issues.append("expires_time is in the past")

        # Validate areas
        if "areas" in alert_data:
            if not isinstance(alert_data["areas"], list):
                issues.append("areas must be a list")
            elif not alert_data["areas"]:
                issues.append("areas cannot be empty")

        return {
            "valid": len(issues) == 0,
            "issues": issues
        }

    async def get_active_alerts(
        self,
        wind_farm_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        db_session=None
    ) -> List[WeatherAlertResponse]:
        """Get active weather alerts."""
        try:
            alerts = await weather_alert_crud.get_active_alerts(db_session, wind_farm_id)

            # Filter by severity if specified
            if severity:
                alerts = [alert for alert in alerts if alert.severity == severity]

            return alerts

        except Exception as e:
            self.logger.error(f"Error getting active alerts: {e}")
            return []

    async def get_alerts_summary(
        self,
        wind_farm_id: Optional[str] = None,
        days: int = 7,
        db_session=None
    ) -> Dict[str, Any]:
        """Get weather alerts summary."""
        try:
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            # Get alerts for the period
            # This would typically query the database with time range
            # For now, get all active alerts
            active_alerts = await self.get_active_alerts(wind_farm_id, db_session=db_session)

            # Calculate summary statistics
            total_alerts = len(active_alerts)
            severity_breakdown = {}
            status_breakdown = {}

            for alert in active_alerts:
                # Severity breakdown
                if alert.severity not in severity_breakdown:
                    severity_breakdown[alert.severity] = 0
                severity_breakdown[alert.severity] += 1

                # Status breakdown
                if alert.status not in status_breakdown:
                    status_breakdown[alert.status] = 0
                status_breakdown[alert.status] += 1

            # Calculate risk level
            risk_level = self._calculate_risk_level(active_alerts)

            return {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "days": days
                },
                "summary": {
                    "total_alerts": total_alerts,
                    "active_alerts": len([a for a in active_alerts if a.status == WeatherAlertStatus.ACTIVE]),
                    "severity_breakdown": severity_breakdown,
                    "status_breakdown": status_breakdown,
                    "risk_level": risk_level
                },
                "alerts": active_alerts
            }

        except Exception as e:
            self.logger.error(f"Error getting alerts summary: {e}")
            return {}

    def _calculate_risk_level(self, alerts: List[WeatherAlertResponse]) -> str:
        """Calculate overall risk level based on alerts."""
        if not alerts:
            return "low"

        # Check for extreme severity alerts
        extreme_alerts = [a for a in alerts if a.severity == AlertSeverity.EXTREME]
        if extreme_alerts:
            return "extreme"

        # Check for severe alerts
        severe_alerts = [a for a in alerts if a.severity == AlertSeverity.SEVERE]
        if severe_alerts:
            return "high"

        # Check for moderate alerts
        moderate_alerts = [a for a in alerts if a.severity == AlertSeverity.MODERATE]
        if moderate_alerts:
            return "moderate"

        # Only minor alerts
        return "low"

    async def check_alert_impact(
        self,
        wind_farm_id: str,
        turbine_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Check the impact of weather alerts on wind farm operations."""
        try:
            # Get active alerts for the wind farm
            alerts = await self.get_active_alerts(wind_farm_id)

            if not alerts:
                return {
                    "wind_farm_id": wind_farm_id,
                    "impact_level": "none",
                    "message": "No active weather alerts",
                    "recommendations": []
                }

            # Analyze impact
            impact_analysis = self._analyze_alert_impact(alerts)

            # Generate recommendations
            recommendations = self._generate_recommendations(alerts, impact_analysis)

            return {
                "wind_farm_id": wind_farm_id,
                "impact_level": impact_analysis["level"],
                "affected_turbines": turbine_ids or [],
                "alerts": alerts,
                "analysis": impact_analysis,
                "recommendations": recommendations,
                "assessment_time": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error checking alert impact: {e}")
            return {
                "wind_farm_id": wind_farm_id,
                "error": str(e),
                "impact_level": "unknown"
            }

    def _analyze_alert_impact(self, alerts: List[WeatherAlertResponse]) -> Dict[str, Any]:
        """Analyze the impact of weather alerts."""
        if not alerts:
            return {"level": "none", "description": "No alerts"}

        # Determine impact level based on severity and type
        max_severity = max(alerts, key=lambda x: self._severity_ranking(x.severity)).severity

        # Check for specific alert types
        high_wind_alerts = [a for a in alerts if "wind" in a.title.lower() or "wind" in a.description.lower()]
        lightning_alerts = [a for a in alerts if "lightning" in a.title.lower() or "thunderstorm" in a.title.lower()]
        ice_alerts = [a for a in alerts if "ice" in a.title.lower() or "freezing" in a.title.lower()]

        impact_factors = []

        if max_severity == AlertSeverity.EXTREME:
            impact_factors.append("Extreme weather conditions")
        elif max_severity == AlertSeverity.SEVERE:
            impact_factors.append("Severe weather conditions")

        if high_wind_alerts:
            impact_factors.append("High wind conditions")

        if lightning_alerts:
            impact_factors.append("Lightning risk")

        if ice_alerts:
            impact_factors.append("Ice accumulation risk")

        # Determine overall impact level
        if max_severity == AlertSeverity.EXTREME:
            level = "extreme"
        elif max_severity == AlertSeverity.SEVERE or len(impact_factors) > 2:
            level = "high"
        elif max_severity == AlertSeverity.MODERATE or len(impact_factors) > 0:
            level = "moderate"
        else:
            level = "low"

        return {
            "level": level,
            "description": f"Weather alert impact: {', '.join(impact_factors)}",
            "factors": impact_factors,
            "max_severity": max_severity
        }

    def _severity_ranking(self, severity: AlertSeverity) -> int:
        """Get numerical ranking for severity levels."""
        ranking = {
            AlertSeverity.MINOR: 1,
            AlertSeverity.MODERATE: 2,
            AlertSeverity.SEVERE: 3,
            AlertSeverity.EXTREME: 4
        }
        return ranking.get(severity, 0)

    def _generate_recommendations(
        self,
        alerts: List[WeatherAlertResponse],
        impact_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate operational recommendations based on alerts."""
        recommendations = []

        level = impact_analysis["level"]
        factors = impact_analysis["factors"]

        if level == "extreme":
            recommendations.extend([
                "Consider shutting down all turbines for safety",
                "Evacuate non-essential personnel from wind farm",
                "Monitor weather conditions continuously",
                "Coordinate with emergency services"
            ])

        elif level == "high":
            recommendations.extend([
                "Reduce turbine operation to minimum safe levels",
                "Increase monitoring frequency",
                "Prepare for potential shutdown",
                "Review emergency procedures"
            ])

        elif level == "moderate":
            recommendations.extend([
                "Maintain normal operations with increased vigilance",
                "Monitor turbine performance closely",
                "Prepare contingency plans"
            ])

        # Factor-specific recommendations
        if "High wind conditions" in factors:
            recommendations.append("Monitor turbine wind speed cut-out limits")

        if "Lightning risk" in factors:
            recommendations.append("Ensure lightning protection systems are active")

        if "Ice accumulation risk" in factors:
            recommendations.append("Monitor for ice formation on turbine blades")

        return recommendations

    async def expire_old_alerts(self, db_session=None) -> int:
        """Expire old alerts and return count."""
        try:
            expired_count = await weather_alert_crud.expire_old_alerts(db_session)
            self.processing_stats["expired_alerts"] += expired_count
            return expired_count

        except Exception as e:
            self.logger.error(f"Error expiring old alerts: {e}")
            return 0

    async def get_processing_statistics(self) -> Dict[str, Any]:
        """Get alert processing statistics."""
        return {
            **self.processing_stats,
            "timestamp": datetime.utcnow().isoformat(),
            "cache_size": len(self.alert_cache)
        }