"""
Health check service for system health monitoring
"""

import asyncio
import logging
import psutil
import socket
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from ..database import get_db
from ..utils import get_logger

logger = get_logger(__name__)


class HealthService:
    """Service for system health monitoring."""

    def __init__(self):
        self.is_initialized = False
        self.startup_time = None

    async def initialize(self):
        """Initialize the health service."""
        try:
            logger.info("Initializing Health Service...")
            self.is_initialized = True
            self.startup_time = datetime.utcnow()
            logger.info("Health Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Health Service: {e}")
            raise

    async def shutdown(self):
        """Shutdown the health service."""
        try:
            logger.info("Shutting down Health Service...")
            self.is_initialized = False
            logger.info("Health Service shutdown completed")
        except Exception as e:
            logger.error(f"Error during Health Service shutdown: {e}")

    async def get_detailed_health(self, db: AsyncSession) -> Dict[str, Any]:
        """Get detailed health check information."""
        try:
            logger.info("Running detailed health check")

            health_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": self._get_uptime_seconds(),
                "database": await self._check_database_health(db),
                "chart_generator": await self._check_chart_generator_health(),
                "external_services": await self._check_external_services(),
                "system_resources": self._check_system_resources()
            }

            return health_data

        except Exception as e:
            logger.error(f"Error in detailed health check: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "database": {"status": "unhealthy", "error": str(e)},
                "chart_generator": {"status": "unknown", "error": str(e)},
                "external_services": {"status": "unknown", "error": str(e)},
                "system_resources": {"status": "unknown", "error": str(e)}
            }

    async def is_service_ready(self, db: AsyncSession) -> bool:
        """Check if service is ready to handle requests."""
        try:
            logger.info("Checking service readiness")

            # Check database connection
            db_health = await self._check_database_health(db)
            if db_health["status"] != "healthy":
                return False

            # Check chart generator
            chart_health = await self._check_chart_generator_health()
            if chart_health["status"] != "healthy":
                return False

            # Check if service has been running for at least 30 seconds
            if self.startup_time:
                uptime = (datetime.utcnow() - self.startup_time).total_seconds()
                if uptime < 30:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking service readiness: {e}")
            return False

    async def is_service_alive(self) -> bool:
        """Check if service is alive (basic health check)."""
        try:
            logger.info("Checking service liveness")

            # Basic checks
            if not self.is_initialized:
                return False

            # Check memory usage (fail if > 95%)
            memory = psutil.virtual_memory()
            if memory.percent > 95:
                return False

            # Check disk usage (fail if > 95%)
            disk = psutil.disk_usage('/')
            if disk.percent > 95:
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking service liveness: {e}")
            return False

    async def get_startup_status(self, db: AsyncSession) -> Dict[str, Any]:
        """Get startup status."""
        try:
            logger.info("Getting startup status")

            if not self.startup_time:
                return {
                    "status": "starting",
                    "message": "Service is starting up",
                    "uptime_seconds": 0
                }

            uptime = (datetime.utcnow() - self.startup_time).total_seconds()

            # Check database
            db_health = await self._check_database_health(db)
            db_ready = db_health["status"] == "healthy"

            # Check chart generator
            chart_health = await self._check_chart_generator_health()
            chart_ready = chart_health["status"] == "healthy"

            if db_ready and chart_ready and uptime > 60:
                return {
                    "status": "completed",
                    "message": "Service startup completed successfully",
                    "uptime_seconds": round(uptime, 2),
                    "startup_time": self.startup_time.isoformat()
                }
            elif db_ready and chart_ready:
                return {
                    "status": "initializing",
                    "message": "Service is initializing dependencies",
                    "uptime_seconds": round(uptime, 2),
                    "startup_time": self.startup_time.isoformat()
                }
            else:
                return {
                    "status": "starting",
                    "message": "Service is starting up",
                    "uptime_seconds": round(uptime, 2),
                    "startup_time": self.startup_time.isoformat(),
                    "dependencies_ready": {
                        "database": db_ready,
                        "chart_generator": chart_ready
                    }
                }

        except Exception as e:
            logger.error(f"Error getting startup status: {e}")
            return {
                "status": "failed",
                "message": f"Startup failed: {str(e)}",
                "error": str(e)
            }

    async def check_external_services(self) -> Dict[str, Any]:
        """Check health of external service dependencies."""
        try:
            logger.info("Checking external services health")

            external_services = {
                "power_prediction_service": {
                    "url": "http://power-prediction-service:8003/health",
                    "timeout": 5
                },
                "meteorological_service": {
                    "url": "http://meteorological-service:8001/health",
                    "timeout": 5
                },
                "scada_service": {
                    "url": "http://scada-service:8002/health",
                    "timeout": 5
                },
                "wind_farm_service": {
                    "url": "http://windfarm-service:8006/health",
                    "timeout": 5
                }
            }

            results = {}
            for service_name, config in external_services.items():
                try:
                    import aiohttp
                    timeout = aiohttp.ClientTimeout(total=config["timeout"])
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(config["url"]) as response:
                            if response.status == 200:
                                results[service_name] = {
                                    "status": "healthy",
                                    "response_time_ms": 0,  # Would measure actual time
                                    "status_code": response.status
                                }
                            else:
                                results[service_name] = {
                                    "status": "unhealthy",
                                    "response_time_ms": 0,
                                    "status_code": response.status,
                                    "error": f"HTTP {response.status}"
                                }
                except Exception as e:
                    results[service_name] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }

            return results

        except Exception as e:
            logger.error(f"Error checking external services: {e}")
            return {
                "error": str(e),
                "status": "error"
            }

    async def check_database_health(self, db: AsyncSession) -> Dict[str, Any]:
        """Check database health specifically."""
        try:
            logger.info("Checking database health")

            # Test database connection
            start_time = datetime.utcnow()
            result = await db.execute(text("SELECT 1"))
            await result.scalar()
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "connection_test": "passed"
            }

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    def get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage information."""
        try:
            logger.info("Getting resource usage")

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage = {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent": memory.percent
            }

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage = {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "percent": disk.percent
            }

            # Network statistics
            network = psutil.net_io_counters()
            network_stats = {
                "bytes_sent_gb": round(network.bytes_sent / (1024**3), 2),
                "bytes_recv_gb": round(network.bytes_recv / (1024**3), 2),
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            }

            return {
                "cpu_percent": cpu_percent,
                "memory": memory_usage,
                "disk": disk_usage,
                "network": network_stats,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def get_dependency_versions(self) -> Dict[str, Any]:
        """Get versions of key dependencies."""
        try:
            logger.info("Getting dependency versions")

            versions = {}

            # Python version
            import sys
            versions["python"] = sys.version

            # Key package versions
            try:
                import fastapi
                versions["fastapi"] = fastapi.__version__
            except ImportError:
                versions["fastapi"] = "not installed"

            try:
                import sqlalchemy
                versions["sqlalchemy"] = sqlalchemy.__version__
            except ImportError:
                versions["sqlalchemy"] = "not installed"

            try:
                import pandas
                versions["pandas"] = pandas.__version__
            except ImportError:
                versions["pandas"] = "not installed"

            try:
                import numpy
                versions["numpy"] = numpy.__version__
            except ImportError:
                versions["numpy"] = "not installed"

            try:
                import matplotlib
                versions["matplotlib"] = matplotlib.__version__
            except ImportError:
                versions["matplotlib"] = "not installed"

            try:
                import plotly
                versions["plotly"] = plotly.__version__
            except ImportError:
                versions["plotly"] = "not installed"

            return {
                "dependencies": versions,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting dependency versions: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    # Private helper methods

    def _get_uptime_seconds(self) -> float:
        """Get service uptime in seconds."""
        if not self.startup_time:
            return 0
        return (datetime.utcnow() - self.startup_time).total_seconds()

    async def _check_chart_generator_health(self) -> Dict[str, Any]:
        """Check chart generator health."""
        try:
            logger.info("Checking chart generator health")

            # Check if chart generator is initialized
            from ..chart_generator import chart_generator
            if chart_generator.is_initialized:
                return {
                    "status": "healthy",
                    "initialized": True,
                    "backends_loaded": len(chart_generator.chart_backends)
                }
            else:
                return {
                    "status": "unhealthy",
                    "initialized": False,
                    "error": "Chart generator not initialized"
                }

        except Exception as e:
            logger.error(f"Chart generator health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resources."""
        try:
            logger.info("Checking system resources")

            # Memory check
            memory = psutil.virtual_memory()
            memory_status = "healthy" if memory.percent < 80 else "degraded" if memory.percent < 95 else "unhealthy"

            # Disk check
            disk = psutil.disk_usage('/')
            disk_status = "healthy" if disk.percent < 80 else "degraded" if disk.percent < 95 else "unhealthy"

            # CPU check
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_status = "healthy" if cpu_percent < 80 else "degraded" if cpu_percent < 95 else "unhealthy"

            return {
                "status": "healthy" if all(s == "healthy" for s in [memory_status, disk_status, cpu_status]) else "degraded",
                "memory": {
                    "status": memory_status,
                    "percent": memory.percent,
                    "available_gb": round(memory.available / (1024**3), 2)
                },
                "disk": {
                    "status": disk_status,
                    "percent": disk.percent,
                    "free_gb": round(disk.free / (1024**3), 2)
                },
                "cpu": {
                    "status": cpu_status,
                    "percent": cpu_percent
                }
            }

        except Exception as e:
            logger.error(f"System resources check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Global health service instance
health_service = HealthService()