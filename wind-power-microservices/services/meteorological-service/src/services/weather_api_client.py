"""
Weather API client for integrating with external weather services
"""

import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import logging

from ..models import (
    WeatherDataSource, WeatherParameter, WeatherDataCreate,
    OpenWeatherMapResponse, WeatherAPIResponse, NOAAAlertResponse
)
from ..config import get_settings
from ..utils import get_logger

logger = get_logger(__name__)


class WeatherAPIClient:
    """Client for weather API integrations."""

    def __init__(self):
        self.settings = get_settings()
        self.session = None
        self.rate_limiters = {
            WeatherDataSource.OPENWEATHERMAP: asyncio.Semaphore(60),  # 60 requests per minute
            WeatherDataSource.WEATHERAPI: asyncio.Semaphore(100),     # 100 requests per month (free tier)
            WeatherDataSource.NOAA: asyncio.Semaphore(1000),          # 1000 requests per day
        }

    async def initialize(self):
        """Initialize the API client."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=10)
        )
        logger.info("Weather API client initialized")

    async def close(self):
        """Close the API client."""
        if self.session:
            await self.session.close()
        logger.info("Weather API client closed")

    async def get_current_weather(
        self,
        latitude: float,
        longitude: float,
        wind_farm_id: str,
        station_id: str
    ) -> List[WeatherDataCreate]:
        """Get current weather data from all enabled sources."""
        weather_data = []

        # OpenWeatherMap
        if WeatherDataSource.OPENWEATHERMAP in self.settings.weather_api_sources:
            try:
                data = await self._get_openweathermap_current(latitude, longitude, wind_farm_id, station_id)
                weather_data.extend(data)
            except Exception as e:
                logger.error(f"Error getting OpenWeatherMap data: {e}")

        # WeatherAPI
        if WeatherDataSource.WEATHERAPI in self.settings.weather_api_sources:
            try:
                data = await self._get_weatherapi_current(latitude, longitude, wind_farm_id, station_id)
                weather_data.extend(data)
            except Exception as e:
                logger.error(f"Error getting WeatherAPI data: {e}")

        return weather_data

    async def get_weather_forecast(
        self,
        latitude: float,
        longitude: float,
        hours: int,
        wind_farm_id: str,
        station_id: str
    ) -> List[Dict[str, Any]]:
        """Get weather forecast from all enabled sources."""
        forecasts = []

        # OpenWeatherMap
        if WeatherDataSource.OPENWEATHERMAP in self.settings.weather_api_sources:
            try:
                forecast = await self._get_openweathermap_forecast(latitude, longitude, hours, wind_farm_id, station_id)
                forecasts.extend(forecast)
            except Exception as e:
                logger.error(f"Error getting OpenWeatherMap forecast: {e}")

        # WeatherAPI
        if WeatherDataSource.WEATHERAPI in self.settings.weather_api_sources:
            try:
                forecast = await self._get_weatherapi_forecast(latitude, longitude, hours, wind_farm_id, station_id)
                forecasts.extend(forecast)
            except Exception as e:
                logger.error(f"Error getting WeatherAPI forecast: {e}")

        return forecasts

    async def get_weather_alerts(
        self,
        latitude: float,
        longitude: float,
        wind_farm_id: str
    ) -> List[Dict[str, Any]]:
        """Get weather alerts from all enabled sources."""
        alerts = []

        # NOAA alerts (US only)
        if WeatherDataSource.NOAA in self.settings.weather_api_sources:
            try:
                noaa_alerts = await self._get_noaa_alerts(latitude, longitude, wind_farm_id)
                alerts.extend(noaa_alerts)
            except Exception as e:
                logger.error(f"Error getting NOAA alerts: {e}")

        return alerts

    async def _get_openweathermap_current(
        self,
        latitude: float,
        longitude: float,
        wind_farm_id: str,
        station_id: str
    ) -> List[WeatherDataCreate]:
        """Get current weather from OpenWeatherMap."""
        if not self.settings.openweathermap_api_key:
            logger.warning("OpenWeatherMap API key not configured")
            return []

        async with self.rate_limiters[WeatherDataSource.OPENWEATHERMAP]:
            url = f"{self.settings.openweathermap_api_url}/weather"
            params = {
                "lat": latitude,
                "lon": longitude,
                "appid": self.settings.openweathermap_api_key,
                "units": "metric"
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_openweathermap_current(data, wind_farm_id, station_id)
                else:
                    logger.error(f"OpenWeatherMap API error: {response.status}")
                    return []

    async def _get_weatherapi_current(
        self,
        latitude: float,
        longitude: float,
        wind_farm_id: str,
        station_id: str
    ) -> List[WeatherDataCreate]:
        """Get current weather from WeatherAPI."""
        if not self.settings.weatherapi_key:
            logger.warning("WeatherAPI key not configured")
            return []

        async with self.rate_limiters[WeatherDataSource.WEATHERAPI]:
            url = f"{self.settings.weatherapi_url}/current.json"
            params = {
                "key": self.settings.weatherapi_key,
                "q": f"{latitude},{longitude}",
                "aqi": "yes"
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_weatherapi_current(data, wind_farm_id, station_id)
                else:
                    logger.error(f"WeatherAPI error: {response.status}")
                    return []

    async def _get_openweathermap_forecast(
        self,
        latitude: float,
        longitude: float,
        hours: int,
        wind_farm_id: str,
        station_id: str
    ) -> List[Dict[str, Any]]:
        """Get weather forecast from OpenWeatherMap."""
        if not self.settings.openweathermap_api_key:
            return []

        async with self.rate_limiters[WeatherDataSource.OPENWEATHERMAP]:
            url = f"{self.settings.openweathermap_api_url}/forecast"
            params = {
                "lat": latitude,
                "lon": longitude,
                "appid": self.settings.openweathermap_api_key,
                "units": "metric",
                "cnt": min(hours // 3, 40)  # OpenWeatherMap provides 3-hour forecasts
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_openweathermap_forecast(data, hours, wind_farm_id, station_id)
                else:
                    logger.error(f"OpenWeatherMap forecast error: {response.status}")
                    return []

    async def _get_weatherapi_forecast(
        self,
        latitude: float,
        longitude: float,
        hours: int,
        wind_farm_id: str,
        station_id: str
    ) -> List[Dict[str, Any]]:
        """Get weather forecast from WeatherAPI."""
        if not self.settings.weatherapi_key:
            return []

        async with self.rate_limiters[WeatherDataSource.WEATHERAPI]:
            url = f"{self.settings.weatherapi_url}/forecast.json"
            params = {
                "key": self.settings.weatherapi_key,
                "q": f"{latitude},{longitude}",
                "days": (hours + 23) // 24,  # Round up to full days
                "aqi": "yes",
                "alerts": "yes"
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_weatherapi_forecast(data, hours, wind_farm_id, station_id)
                else:
                    logger.error(f"WeatherAPI forecast error: {response.status}")
                    return []

    async def _get_noaa_alerts(
        self,
        latitude: float,
        longitude: float,
        wind_farm_id: str
    ) -> List[Dict[str, Any]]:
        """Get weather alerts from NOAA (US only)."""
        async with self.rate_limiters[WeatherDataSource.NOAA]:
            url = f"{self.settings.noaa_api_url}/alerts/active"
            params = {
                "point": f"{latitude},{longitude}"
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_noaa_alerts(data, wind_farm_id)
                else:
                    logger.error(f"NOAA alerts error: {response.status}")
                    return []

    def _parse_openweathermap_current(
        self,
        data: Dict[str, Any],
        wind_farm_id: str,
        station_id: str
    ) -> List[WeatherDataCreate]:
        """Parse OpenWeatherMap current weather data."""
        weather_data = []
        current_time = datetime.utcnow()

        # Temperature
        if "main" in data and "temp" in data["main"]:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.TEMPERATURE,
                value=data["main"]["temp"],
                unit="celsius",
                timestamp=current_time,
                source=WeatherDataSource.OPENWEATHERMAP
            ))

        # Humidity
        if "main" in data and "humidity" in data["main"]:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.HUMIDITY,
                value=data["main"]["humidity"],
                unit="percent",
                timestamp=current_time,
                source=WeatherDataSource.OPENWEATHERMAP
            ))

        # Wind speed
        if "wind" in data and "speed" in data["wind"]:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.WIND_SPEED,
                value=data["wind"]["speed"],
                unit="m/s",
                timestamp=current_time,
                source=WeatherDataSource.OPENWEATHERMAP
            ))

        # Wind direction
        if "wind" in data and "deg" in data["wind"]:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.WIND_DIRECTION,
                value=data["wind"]["deg"],
                unit="degrees",
                timestamp=current_time,
                source=WeatherDataSource.OPENWEATHERMAP
            ))

        # Pressure
        if "main" in data and "pressure" in data["main"]:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.PRESSURE,
                value=data["main"]["pressure"],
                unit="hPa",
                timestamp=current_time,
                source=WeatherDataSource.OPENWEATHERMAP
            ))

        # Cloud cover
        if "clouds" in data and "all" in data["clouds"]:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.CLOUD_COVER,
                value=data["clouds"]["all"],
                unit="percent",
                timestamp=current_time,
                source=WeatherDataSource.OPENWEATHERMAP
            ))

        # Visibility
        if "visibility" in data:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.VISIBILITY,
                value=data["visibility"] / 1000,  # Convert meters to kilometers
                unit="km",
                timestamp=current_time,
                source=WeatherDataSource.OPENWEATHERMAP
            ))

        return weather_data

    def _parse_weatherapi_current(
        self,
        data: Dict[str, Any],
        wind_farm_id: str,
        station_id: str
    ) -> List[WeatherDataCreate]:
        """Parse WeatherAPI current weather data."""
        weather_data = []
        current_time = datetime.utcnow()

        if "current" not in data:
            return weather_data

        current = data["current"]

        # Temperature
        if "temp_c" in current:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.TEMPERATURE,
                value=current["temp_c"],
                unit="celsius",
                timestamp=current_time,
                source=WeatherDataSource.WEATHERAPI
            ))

        # Humidity
        if "humidity" in current:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.HUMIDITY,
                value=current["humidity"],
                unit="percent",
                timestamp=current_time,
                source=WeatherDataSource.WEATHERAPI
            ))

        # Wind speed
        if "wind_kph" in current:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.WIND_SPEED,
                value=current["wind_kph"] / 3.6,  # Convert km/h to m/s
                unit="m/s",
                timestamp=current_time,
                source=WeatherDataSource.WEATHERAPI
            ))

        # Wind direction
        if "wind_degree" in current:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.WIND_DIRECTION,
                value=current["wind_degree"],
                unit="degrees",
                timestamp=current_time,
                source=WeatherDataSource.WEATHERAPI
            ))

        # Pressure
        if "pressure_mb" in current:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.PRESSURE,
                value=current["pressure_mb"],
                unit="hPa",
                timestamp=current_time,
                source=WeatherDataSource.WEATHERAPI
            ))

        # Cloud cover
        if "cloud" in current:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.CLOUD_COVER,
                value=current["cloud"],
                unit="percent",
                timestamp=current_time,
                source=WeatherDataSource.WEATHERAPI
            ))

        # Visibility
        if "vis_km" in current:
            weather_data.append(WeatherDataCreate(
                station_id=station_id,
                wind_farm_id=wind_farm_id,
                parameter=WeatherParameter.VISIBILITY,
                value=current["vis_km"],
                unit="km",
                timestamp=current_time,
                source=WeatherDataSource.WEATHERAPI
            ))

        return weather_data

    def _parse_openweathermap_forecast(
        self,
        data: Dict[str, Any],
        hours: int,
        wind_farm_id: str,
        station_id: str
    ) -> List[Dict[str, Any]]:
        """Parse OpenWeatherMap forecast data."""
        forecasts = []

        if "list" not in data:
            return forecasts

        for item in data["list"]:
            forecast_time = datetime.fromtimestamp(item["dt"])

            forecast = {
                "station_id": station_id,
                "wind_farm_id": wind_farm_id,
                "forecast_time": forecast_time,
                "forecast_hours": int((forecast_time - datetime.utcnow()).total_seconds() / 3600),
                "parameters": {},
                "source": WeatherDataSource.OPENWEATHERMAP
            }

            # Temperature
            if "main" in item and "temp" in item["main"]:
                forecast["parameters"]["temperature"] = item["main"]["temp"]

            # Humidity
            if "main" in item and "humidity" in item["main"]:
                forecast["parameters"]["humidity"] = item["main"]["humidity"]

            # Wind
            if "wind" in item:
                if "speed" in item["wind"]:
                    forecast["parameters"]["wind_speed"] = item["wind"]["speed"]
                if "deg" in item["wind"]:
                    forecast["parameters"]["wind_direction"] = item["wind"]["deg"]

            # Pressure
            if "main" in item and "pressure" in item["main"]:
                forecast["parameters"]["pressure"] = item["main"]["pressure"]

            # Cloud cover
            if "clouds" in item and "all" in item["clouds"]:
                forecast["parameters"]["cloud_cover"] = item["clouds"]["all"]

            # Visibility
            if "visibility" in item:
                forecast["parameters"]["visibility"] = item["visibility"] / 1000

            forecasts.append(forecast)

        return forecasts

    def _parse_weatherapi_forecast(
        self,
        data: Dict[str, Any],
        hours: int,
        wind_farm_id: str,
        station_id: str
    ) -> List[Dict[str, Any]]:
        """Parse WeatherAPI forecast data."""
        forecasts = []

        if "forecast" not in data or "forecastday" not in data["forecast"]:
            return forecasts

        for day in data["forecast"]["forecastday"]:
            if "hour" in day:
                for hour_data in day["hour"]:
                    forecast_time = datetime.strptime(hour_data["time"], "%Y-%m-%d %H:%M")

                    forecast = {
                        "station_id": station_id,
                        "wind_farm_id": wind_farm_id,
                        "forecast_time": forecast_time,
                        "forecast_hours": int((forecast_time - datetime.utcnow()).total_seconds() / 3600),
                        "parameters": {},
                        "source": WeatherDataSource.WEATHERAPI
                    }

                    # Temperature
                    if "temp_c" in hour_data:
                        forecast["parameters"]["temperature"] = hour_data["temp_c"]

                    # Humidity
                    if "humidity" in hour_data:
                        forecast["parameters"]["humidity"] = hour_data["humidity"]

                    # Wind
                    if "wind_kph" in hour_data:
                        forecast["parameters"]["wind_speed"] = hour_data["wind_kph"] / 3.6
                    if "wind_degree" in hour_data:
                        forecast["parameters"]["wind_direction"] = hour_data["wind_degree"]

                    # Pressure
                    if "pressure_mb" in hour_data:
                        forecast["parameters"]["pressure"] = hour_data["pressure_mb"]

                    # Cloud cover
                    if "cloud" in hour_data:
                        forecast["parameters"]["cloud_cover"] = hour_data["cloud"]

                    # Visibility
                    if "vis_km" in hour_data:
                        forecast["parameters"]["visibility"] = hour_data["vis_km"]

                    forecasts.append(forecast)

        return forecasts

    def _parse_noaa_alerts(
        self,
        data: Dict[str, Any],
        wind_farm_id: str
    ) -> List[Dict[str, Any]]:
        """Parse NOAA weather alerts."""
        alerts = []

        if "features" not in data:
            return alerts

        for feature in data["features"]:
            if "properties" not in feature:
                continue

            props = feature["properties"]

            alert = {
                "wind_farm_id": wind_farm_id,
                "alert_id": feature.get("id", ""),
                "title": props.get("event", ""),
                "description": props.get("description", ""),
                "severity": self._map_noaa_severity(props.get("severity", "")),
                "effective_time": datetime.fromisoformat(props.get("effective", "").replace("Z", "+00:00")),
                "expires_time": datetime.fromisoformat(props.get("expires", "").replace("Z", "+00:00")),
                "areas": props.get("areaDesc", "").split(";"),
                "parameters": {
                    "certainty": props.get("certainty", ""),
                    "urgency": props.get("urgency", ""),
                    "sender": props.get("senderName", "")
                },
                "source": WeatherDataSource.NOAA
            }

            alerts.append(alert)

        return alerts

    def _map_noaa_severity(self, noaa_severity: str) -> str:
        """Map NOAA severity to internal severity."""
        severity_map = {
            "Minor": "minor",
            "Moderate": "moderate",
            "Severe": "severe",
            "Extreme": "extreme"
        }
        return severity_map.get(noaa_severity, "moderate")

    async def ping(self) -> bool:
        """Ping API services to check connectivity."""
        try:
            # Test OpenWeatherMap
            if WeatherDataSource.OPENWEATHERMAP in self.settings.weather_api_sources:
                url = f"{self.settings.openweathermap_api_url}/weather"
                params = {"q": "London", "appid": self.settings.openweathermap_api_key or "test"}
                async with self.session.get(url, params=params) as response:
                    # We expect a 401 if no API key, but connection should work
                    return response.status in [200, 401]
            return True
        except Exception as e:
            logger.error(f"Weather API ping failed: {e}")
            return False