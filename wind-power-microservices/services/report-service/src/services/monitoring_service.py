"""
Monitoring service for system analytics and metrics
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from ..database import report_crud, chart_crud, report_template_crud
from ..exceptions import ValidationException
from ..utils import get_logger, safe_divide

logger = get_logger(__name__)


class MonitoringService:
    """Service for system monitoring and analytics."""

    def __init__(self):
        self.is_initialized = False

    async def initialize(self):
        """Initialize the monitoring service."""
        try:
            logger.info("Initializing Monitoring Service...")
            self.is_initialized = True
            logger.info("Monitoring Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Monitoring Service: {e}")
            raise

    async def shutdown(self):
        """Shutdown the monitoring service."""
        try:
            logger.info("Shutting down Monitoring Service...")
            self.is_initialized = False
            logger.info("Monitoring Service shutdown completed")
        except Exception as e:
            logger.error(f"Error during Monitoring Service shutdown: {e}")

    async def get_system_status(self, db: AsyncSession) -> Dict[str, Any]:
        """Get overall system status and health metrics."""
        try:
            logger.info("Getting system status")

            # Get report statistics
            report_stats = await self._get_report_statistics_summary(db)

            # Get chart statistics
            chart_stats = await self._get_chart_statistics_summary(db)

            # Get template statistics
            template_stats = await self._get_template_statistics_summary(db)

            # Calculate system health score
            health_score = self._calculate_system_health_score(report_stats, chart_stats, template_stats)

            return {
                "status": "healthy" if health_score >= 80 else "degraded" if health_score >= 60 else "unhealthy",
                "health_score": round(health_score, 1),
                "timestamp": datetime.utcnow().isoformat(),
                "reports": report_stats,
                "charts": chart_stats,
                "templates": template_stats
            }

        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "status": "error",
                "health_score": 0,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    async def get_metrics(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        metric_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get system metrics and performance data."""
        try:
            logger.info(f"Getting metrics: start={start_date}, end={end_date}, type={metric_type}")

            metrics = {}

            if not metric_type or metric_type == "reports":
                metrics["reports"] = await self._get_report_metrics(db, start_date, end_date)

            if not metric_type or metric_type == "charts":
                metrics["charts"] = await self._get_chart_metrics(db, start_date, end_date)

            if not metric_type or metric_type == "templates":
                metrics["templates"] = await self._get_template_metrics(db, start_date, end_date)

            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "metrics": metrics
            }

        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "error": str(e)
            }

    async def get_report_statistics(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        report_type: Optional[str] = None,
        wind_farm_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get report generation statistics."""
        try:
            logger.info(f"Getting report statistics: type={report_type}, wind_farm={wind_farm_id}")

            # Build query conditions
            conditions = [
                report_crud.model.created_at >= start_date,
                report_crud.model.created_at <= end_date
            ]

            if report_type:
                conditions.append(report_crud.model.report_type == report_type)
            if wind_farm_id:
                conditions.append(report_crud.model.wind_farm_id == wind_farm_id)

            # Total reports
            total_query = select(func.count(report_crud.model.id)).where(and_(*conditions))
            total_result = await db.execute(total_query)
            total_reports = total_result.scalar()

            # Reports by status
            status_query = select(
                report_crud.model.status,
                func.count(report_crud.model.id).label('count')
            ).where(and_(*conditions)).group_by(report_crud.model.status)
            status_result = await db.execute(status_query)
            status_breakdown = {row.status: row.count for row in status_result}

            # Reports by type
            type_query = select(
                report_crud.model.report_type,
                func.count(report_crud.model.id).label('count')
            ).where(and_(*conditions)).group_by(report_crud.model.report_type)
            type_result = await db.execute(type_query)
            type_breakdown = {row.report_type: row.count for row in type_result}

            # Average generation time
            avg_time_query = select(
                func.avg(report_crud.model.generation_duration_seconds)
            ).where(
                and_(
                    *conditions,
                    report_crud.model.status == "completed",
                    report_crud.model.generation_duration_seconds.isnot(None)
                )
            )
            avg_time_result = await db.execute(avg_time_query)
            avg_generation_time = avg_time_result.scalar() or 0

            # Success rate
            completed = status_breakdown.get("completed", 0)
            failed = status_breakdown.get("failed", 0)
            success_rate = safe_divide(completed, completed + failed) * 100

            return {
                "total_reports": total_reports,
                "status_breakdown": status_breakdown,
                "type_breakdown": type_breakdown,
                "average_generation_time_seconds": round(avg_generation_time, 2),
                "success_rate_percent": round(success_rate, 2),
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Error getting report statistics: {e}")
            return {
                "error": str(e),
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }

    async def get_chart_statistics(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        chart_type: Optional[str] = None,
        backend: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get chart generation statistics."""
        try:
            logger.info(f"Getting chart statistics: type={chart_type}, backend={backend}")

            # Build query conditions
            conditions = [
                chart_crud.model.created_at >= start_date,
                chart_crud.model.created_at <= end_date
            ]

            if chart_type:
                conditions.append(chart_crud.model.chart_type == chart_type)
            if backend:
                conditions.append(chart_crud.model.backend == backend)

            # Total charts
            total_query = select(func.count(chart_crud.model.id)).where(and_(*conditions))
            total_result = await db.execute(total_query)
            total_charts = total_result.scalar()

            # Charts by type
            type_query = select(
                chart_crud.model.chart_type,
                func.count(chart_crud.model.id).label('count')
            ).where(and_(*conditions)).group_by(chart_crud.model.chart_type)
            type_result = await db.execute(type_query)
            type_breakdown = {row.chart_type: row.count for row in type_result}

            # Charts by backend
            backend_query = select(
                chart_crud.model.backend,
                func.count(chart_crud.model.id).label('count')
            ).where(and_(*conditions)).group_by(chart_crud.model.backend)
            backend_result = await db.execute(backend_query)
            backend_breakdown = {row.backend: row.count for row in backend_result}

            # Average data points
            avg_points_query = select(
                func.avg(chart_crud.model.data_points)
            ).where(and_(*conditions))
            avg_points_result = await db.execute(avg_points_query)
            avg_data_points = avg_points_result.scalar() or 0

            return {
                "total_charts": total_charts,
                "type_breakdown": type_breakdown,
                "backend_breakdown": backend_breakdown,
                "average_data_points": round(avg_data_points, 2),
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Error getting chart statistics: {e}")
            return {
                "error": str(e),
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }

    async def get_data_quality_metrics(
        self,
        db: AsyncSession,
        data_source: Optional[str] = None,
        wind_farm_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get data quality metrics."""
        try:
            logger.info(f"Getting data quality metrics: source={data_source}, wind_farm={wind_farm_id}")

            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # This is a simplified implementation
            # In a real system, you would analyze actual data quality from your data sources

            quality_metrics = {
                "completeness": 95.2,  # Percentage of expected data received
                "accuracy": 98.1,      # Percentage of valid data points
                "consistency": 96.8,   # Percentage of consistent data
                "timeliness": 94.5,    # Percentage of data received on time
                "validity": 97.3       # Percentage of data within expected ranges
            }

            # Calculate overall quality score
            overall_score = sum(quality_metrics.values()) / len(quality_metrics)

            return {
                "data_source": data_source or "all",
                "wind_farm_id": wind_farm_id,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": days
                },
                "quality_metrics": quality_metrics,
                "overall_quality_score": round(overall_score, 1),
                "quality_grade": self._get_quality_grade(overall_score)
            }

        except Exception as e:
            logger.error(f"Error getting data quality metrics: {e}")
            return {
                "error": str(e),
                "data_source": data_source,
                "wind_farm_id": wind_farm_id
            }

    async def get_performance_trends(
        self,
        db: AsyncSession,
        metric: str,
        time_period: str,
        aggregation: str
    ) -> Dict[str, Any]:
        """Get performance trends over time."""
        try:
            logger.info(f"Getting performance trends: metric={metric}, period={time_period}")

            # Determine time range based on period
            end_date = datetime.utcnow()
            if time_period == "1d":
                start_date = end_date - timedelta(days=1)
            elif time_period == "7d":
                start_date = end_date - timedelta(days=7)
            elif time_period == "30d":
                start_date = end_date - timedelta(days=30)
            elif time_period == "90d":
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=7)

            # Generate sample trend data
            # In a real system, you would query historical data
            trends = self._generate_sample_trends(metric, start_date, end_date, aggregation)

            return {
                "metric": metric,
                "time_period": time_period,
                "aggregation": aggregation,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "trends": trends
            }

        except Exception as e:
            logger.error(f"Error getting performance trends: {e}")
            return {
                "error": str(e),
                "metric": metric,
                "time_period": time_period
            }

    async def get_active_alerts(
        self,
        db: AsyncSession,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        wind_farm_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get active system alerts."""
        try:
            logger.info(f"Getting active alerts: severity={severity}, category={category}")

            # Generate sample alerts
            # In a real system, you would query from an alerts table
            sample_alerts = [
                {
                    "id": "alert_001",
                    "severity": "warning",
                    "category": "data_quality",
                    "title": "Data Quality Degradation",
                    "description": "SCADA data completeness dropped to 85%",
                    "wind_farm_id": "farm_001",
                    "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                    "status": "active"
                }
            ]

            # Filter by parameters
            filtered_alerts = sample_alerts
            if severity:
                filtered_alerts = [alert for alert in filtered_alerts if alert["severity"] == severity]
            if category:
                filtered_alerts = [alert for alert in filtered_alerts if alert["category"] == category]
            if wind_farm_id:
                filtered_alerts = [alert for alert in filtered_alerts if alert.get("wind_farm_id") == wind_farm_id]

            return {
                "total_alerts": len(filtered_alerts),
                "alerts": filtered_alerts,
                "severity_breakdown": self._count_by_severity(filtered_alerts),
                "category_breakdown": self._count_by_category(filtered_alerts)
            }

        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            return {
                "error": str(e),
                "total_alerts": 0,
                "alerts": []
            }

    async def get_alerts_history(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get alerts history."""
        try:
            logger.info(f"Getting alerts history: severity={severity}, category={category}")

            # Generate sample historical alerts
            sample_history = [
                {
                    "id": "alert_001",
                    "severity": "warning",
                    "category": "data_quality",
                    "title": "Data Quality Degradation",
                    "description": "SCADA data completeness dropped to 85%",
                    "created_at": (datetime.utcnow() - timedelta(days=3)).isoformat(),
                    "resolved_at": (datetime.utcnow() - timedelta(days=2)).isoformat(),
                    "status": "resolved"
                },
                {
                    "id": "alert_002",
                    "severity": "critical",
                    "category": "system_health",
                    "title": "Service Unavailable",
                    "description": "Report generation service was down for 15 minutes",
                    "created_at": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                    "resolved_at": (datetime.utcnow() - timedelta(hours=23)).isoformat(),
                    "status": "resolved"
                }
            ]

            # Filter by parameters
            filtered_history = sample_history
            if severity:
                filtered_history = [alert for alert in filtered_history if alert["severity"] == severity]
            if category:
                filtered_history = [alert for alert in filtered_history if alert["category"] == category]

            # Limit results
            filtered_history = filtered_history[:limit]

            return {
                "total_alerts": len(filtered_history),
                "alerts": filtered_history,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Error getting alerts history: {e}")
            return {
                "error": str(e),
                "total_alerts": 0,
                "alerts": [],
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }

    async def get_usage_analytics(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
        group_by: str
    ) -> Dict[str, Any]:
        """Get usage analytics and patterns."""
        try:
            logger.info(f"Getting usage analytics: group_by={group_by}")

            # Generate sample usage data
            usage_data = self._generate_sample_usage_data(start_date, end_date, group_by)

            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "grouping": group_by,
                "usage_patterns": usage_data
            }

        except Exception as e:
            logger.error(f"Error getting usage analytics: {e}")
            return {
                "error": str(e),
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }

    async def get_system_health(
        self,
        db: AsyncSession,
        detailed: bool = False
    ) -> Dict[str, Any]:
        """Get detailed system health status."""
        try:
            logger.info(f"Getting system health: detailed={detailed}")

            health_data = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "overall_health_score": 92.5,
                "components": {
                    "database": {
                        "status": "healthy",
                        "response_time_ms": 15,
                        "connection_pool_usage": 0.35
                    },
                    "chart_generator": {
                        "status": "healthy",
                        "active_generations": 2,
                        "queue_length": 0
                    }
                }
            }

            if detailed:
                health_data["detailed_metrics"] = {
                    "report_generation_rate": 0.8,
                    "chart_generation_rate": 2.1,
                    "average_response_time": 45,
                    "error_rate": 0.02,
                    "memory_usage_percent": 68.5,
                    "cpu_usage_percent": 35.2
                }

            return health_data

        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                "status": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    async def get_capacity_planning(
        self,
        db: AsyncSession,
        forecast_days: int
    ) -> Dict[str, Any]:
        """Get capacity planning metrics and forecasts."""
        try:
            logger.info(f"Getting capacity planning: forecast_days={forecast_days}")

            # Generate capacity planning data
            capacity_data = self._generate_capacity_forecast(forecast_days)

            return {
                "forecast_days": forecast_days,
                "current_capacity": {
                    "max_reports_per_hour": 100,
                    "max_charts_per_hour": 500,
                    "storage_usage_gb": 15.2,
                    "storage_capacity_gb": 100
                },
                "projected_usage": capacity_data,
                "recommendations": [
                    "Consider scaling storage if usage exceeds 80%",
                    "Monitor chart generation performance during peak hours",
                    "Implement additional caching for frequently accessed reports"
                ]
            }

        except Exception as e:
            logger.error(f"Error getting capacity planning: {e}")
            return {
                "error": str(e),
                "forecast_days": forecast_days
            }

    async def get_dashboard_summary(
        self,
        db: AsyncSession,
        time_period: str,
        wind_farm_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get dashboard summary data."""
        try:
            logger.info(f"Getting dashboard summary: period={time_period}, wind_farm={wind_farm_id}")

            # Determine time range
            end_date = datetime.utcnow()
            if time_period == "1h":
                start_date = end_date - timedelta(hours=1)
            elif time_period == "24h":
                start_date = end_date - timedelta(days=1)
            elif time_period == "7d":
                start_date = end_date - timedelta(days=7)
            elif time_period == "30d":
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=1)

            # Get summary statistics
            report_stats = await self.get_report_statistics(db, start_date, end_date, None, wind_farm_id)
            chart_stats = await self.get_chart_statistics(db, start_date, end_date, None, None)
            system_health = await self.get_system_health(db)

            return {
                "period": time_period,
                "time_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "wind_farm_id": wind_farm_id,
                "summary": {
                    "reports_generated": report_stats.get("total_reports", 0),
                    "charts_generated": chart_stats.get("total_charts", 0),
                    "success_rate": report_stats.get("success_rate_percent", 0),
                    "system_health": system_health.get("overall_health_score", 0)
                },
                "key_metrics": {
                    "active_reports": report_stats.get("status_breakdown", {}).get("completed", 0),
                    "pending_reports": report_stats.get("status_breakdown", {}).get("pending", 0),
                    "failed_reports": report_stats.get("status_breakdown", {}).get("failed", 0),
                    "avg_generation_time": report_stats.get("average_generation_time_seconds", 0)
                }
            }

        except Exception as e:
            logger.error(f"Error getting dashboard summary: {e}")
            return {
                "error": str(e),
                "period": time_period,
                "wind_farm_id": wind_farm_id
            }

    # Private helper methods

    async def _get_report_statistics_summary(self, db: AsyncSession) -> Dict[str, Any]:
        """Get report statistics summary."""
        try:
            # Total reports
            total_query = select(func.count(report_crud.model.id))
            total_result = await db.execute(total_query)
            total_reports = total_result.scalar()

            # Reports by status
            status_query = select(
                report_crud.model.status,
                func.count(report_crud.model.id).label('count')
            ).group_by(report_crud.model.status)
            status_result = await db.execute(status_query)
            status_breakdown = {row.status: row.count for row in status_result}

            return {
                "total": total_reports,
                "by_status": status_breakdown
            }
        except Exception as e:
            logger.error(f"Error getting report statistics summary: {e}")
            return {"total": 0, "by_status": {}}

    async def _get_chart_statistics_summary(self, db: AsyncSession) -> Dict[str, Any]:
        """Get chart statistics summary."""
        try:
            # Total charts
            total_query = select(func.count(chart_crud.model.id))
            total_result = await db.execute(total_query)
            total_charts = total_result.scalar()

            # Charts by type
            type_query = select(
                chart_crud.model.chart_type,
                func.count(chart_crud.model.id).label('count')
            ).group_by(chart_crud.model.chart_type)
            type_result = await db.execute(type_query)
            type_breakdown = {row.chart_type: row.count for row in type_result}

            return {
                "total": total_charts,
                "by_type": type_breakdown
            }
        except Exception as e:
            logger.error(f"Error getting chart statistics summary: {e}")
            return {"total": 0, "by_type": {}}

    async def _get_template_statistics_summary(self, db: AsyncSession) -> Dict[str, Any]:
        """Get template statistics summary."""
        try:
            # Total templates
            total_query = select(func.count(report_template_crud.model.id))
            total_result = await db.execute(total_query)
            total_templates = total_result.scalar()

            # Templates by type
            type_query = select(
                report_template_crud.model.report_type,
                func.count(report_template_crud.model.id).label('count')
            ).group_by(report_template_crud.model.report_type)
            type_result = await db.execute(type_query)
            type_breakdown = {row.report_type: row.count for row in type_result}

            # Active templates
            active_query = select(func.count(report_template_crud.model.id)).where(
                report_template_crud.model.is_active == True
            )
            active_result = await db.execute(active_query)
            active_templates = active_result.scalar()

            return {
                "total": total_templates,
                "active": active_templates,
                "by_type": type_breakdown
            }
        except Exception as e:
            logger.error(f"Error getting template statistics summary: {e}")
            return {"total": 0, "active": 0, "by_type": {}}

    def _calculate_system_health_score(
        self,
        report_stats: Dict[str, Any],
        chart_stats: Dict[str, Any],
        template_stats: Dict[str, Any]
    ) -> float:
        """Calculate overall system health score."""
        try:
            scores = []

            # Report health (based on completion rate)
            if report_stats.get("by_status"):
                completed = report_stats["by_status"].get("completed", 0)
                failed = report_stats["by_status"].get("failed", 0)
                total = sum(report_stats["by_status"].values())
                if total > 0:
                    report_health = (completed / total) * 100
                    scores.append(report_health)

            # Chart health (based on generation success)
            if chart_stats.get("total", 0) > 0:
                chart_health = min(100, (chart_stats["total"] / 1000) * 100)  # Normalize to 1000
                scores.append(chart_health)

            # Template health (based on active templates)
            if template_stats.get("total", 0) > 0:
                template_health = (template_stats.get("active", 0) / template_stats["total"]) * 100
                scores.append(template_health)

            return sum(scores) / len(scores) if scores else 0

        except Exception as e:
            logger.error(f"Error calculating system health score: {e}")
            return 0

    def _get_quality_grade(self, score: float) -> str:
        """Get quality grade based on score."""
        if score >= 95:
            return "Excellent"
        elif score >= 90:
            return "Good"
        elif score >= 80:
            return "Fair"
        elif score >= 70:
            return "Poor"
        else:
            return "Very Poor"

    def _generate_sample_trends(
        self,
        metric: str,
        start_date: datetime,
        end_date: datetime,
        aggregation: str
    ) -> List[Dict[str, Any]]:
        """Generate sample trend data."""
        trends = []
        current_date = start_date

        while current_date <= end_date:
            if aggregation == "hourly":
                value = 85 + (current_date.hour % 24) * 0.5 + (current_date.day % 7) * 2
                next_date = current_date + timedelta(hours=1)
            elif aggregation == "daily":
                value = 80 + (current_date.day % 30) * 1.5
                next_date = current_date + timedelta(days=1)
            elif aggregation == "weekly":
                value = 75 + (current_date.isocalendar()[1] % 52) * 1.2
                next_date = current_date + timedelta(weeks=1)
            else:
                value = 80 + (current_date.day % 30) * 1.5
                next_date = current_date + timedelta(days=1)

            trends.append({
                "timestamp": current_date.isoformat(),
                "value": round(value, 2)
            })

            current_date = next_date

        return trends

    def _count_by_severity(self, alerts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count alerts by severity."""
        severity_counts = {}
        for alert in alerts:
            severity = alert.get("severity", "unknown")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        return severity_counts

    def _count_by_category(self, alerts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count alerts by category."""
        category_counts = {}
        for alert in alerts:
            category = alert.get("category", "unknown")
            category_counts[category] = category_counts.get(category, 0) + 1
        return category_counts

    def _generate_sample_usage_data(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: str
    ) -> List[Dict[str, Any]]:
        """Generate sample usage data."""
        usage_data = []
        current_date = start_date

        while current_date <= end_date:
            if group_by == "hourly":
                reports = 10 + (current_date.hour % 24) * 2
                charts = 50 + (current_date.hour % 24) * 5
                next_date = current_date + timedelta(hours=1)
            elif group_by == "daily":
                reports = 200 + (current_date.day % 30) * 10
                charts = 1000 + (current_date.day % 30) * 50
                next_date = current_date + timedelta(days=1)
            elif group_by == "weekly":
                reports = 1400 + (current_date.isocalendar()[1] % 52) * 50
                charts = 7000 + (current_date.isocalendar()[1] % 52) * 300
                next_date = current_date + timedelta(weeks=1)
            else:
                reports = 6000 + (current_date.day % 30) * 200
                charts = 30000 + (current_date.day % 30) * 1000
                next_date = current_date + timedelta(days=30)

            usage_data.append({
                "timestamp": current_date.isoformat(),
                "reports_generated": reports,
                "charts_generated": charts,
                "active_users": 25 + (current_date.day % 30)
            })

            current_date = next_date

        return usage_data

    def _generate_capacity_forecast(self, forecast_days: int) -> List[Dict[str, Any]]:
        """Generate capacity forecast."""
        forecast = []
        current_date = datetime.utcnow()

        for day in range(forecast_days):
            forecast_date = current_date + timedelta(days=day)

            # Simulate growing usage over time
            growth_factor = 1 + (day / forecast_days) * 0.2

            forecast.append({
                "date": forecast_date.isoformat(),
                "projected_reports": int(100 * growth_factor),
                "projected_charts": int(500 * growth_factor),
                "storage_usage_gb": 15.2 * growth_factor,
                "capacity_utilization_percent": min(100, 35 * growth_factor)
            })

        return forecast


# Global monitoring service instance
monitoring_service = MonitoringService()