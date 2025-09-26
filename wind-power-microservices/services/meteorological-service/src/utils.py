"""
Utility functions for Meteorological Data Service
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any


def get_logger(name: str) -> logging.Logger:
    """Get configured logger instance."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


def generate_uuid() -> str:
    """Generate unique identifier."""
    return str(uuid.uuid4())


def format_datetime(dt: datetime) -> str:
    """Format datetime to ISO string."""
    return dt.isoformat()


def parse_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string."""
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def calculate_wind_chill(temperature: float, wind_speed: float) -> float:
    """Calculate wind chill temperature."""
    # Wind chill formula (°C)
    if temperature <= 10 and wind_speed > 4.8:
        wind_chill = (13.12 + 0.6215 * temperature -
                     11.37 * (wind_speed ** 0.16) +
                     0.3965 * temperature * (wind_speed ** 0.16))
        return round(wind_chill, 1)
    return temperature


def calculate_heat_index(temperature: float, humidity: float) -> float:
    """Calculate heat index."""
    # Heat index formula (°C)
    if temperature >= 27 and humidity >= 40:
        # Simplified heat index calculation
        heat_index = (temperature + (humidity / 100) * 5)
        return round(heat_index, 1)
    return temperature


def calculate_dew_point(temperature: float, humidity: float) -> float:
    """Calculate dew point temperature."""
    # Magnus formula for dew point
    a = 17.27
    b = 237.7

    alpha = ((a * temperature) / (b + temperature)) + (humidity / 100)
    dew_point = (b * alpha) / (a - alpha)

    return round(dew_point, 1)


def convert_wind_speed(speed: float, from_unit: str, to_unit: str) -> float:
    """Convert wind speed between different units."""
    # Convert to m/s first
    if from_unit.lower() in ['m/s', 'mps']:
        speed_mps = speed
    elif from_unit.lower() in ['km/h', 'kph']:
        speed_mps = speed / 3.6
    elif from_unit.lower() in ['mph']:
        speed_mps = speed * 0.44704
    elif from_unit.lower() in ['knots']:
        speed_mps = speed * 0.514444
    else:
        raise ValueError(f"Unsupported wind speed unit: {from_unit}")

    # Convert from m/s to target unit
    if to_unit.lower() in ['m/s', 'mps']:
        return speed_mps
    elif to_unit.lower() in ['km/h', 'kph']:
        return speed_mps * 3.6
    elif to_unit.lower() in ['mph']:
        return speed_mps / 0.44704
    elif to_unit.lower() in ['knots']:
        return speed_mps / 0.514444
    else:
        raise ValueError(f"Unsupported wind speed unit: {to_unit}")


def convert_temperature(temp: float, from_unit: str, to_unit: str) -> float:
    """Convert temperature between different units."""
    # Convert to Celsius first
    if from_unit.lower() in ['celsius', 'c']:
        temp_c = temp
    elif from_unit.lower() in ['fahrenheit', 'f']:
        temp_c = (temp - 32) * 5/9
    elif from_unit.lower() in ['kelvin', 'k']:
        temp_c = temp - 273.15
    else:
        raise ValueError(f"Unsupported temperature unit: {from_unit}")

    # Convert from Celsius to target unit
    if to_unit.lower() in ['celsius', 'c']:
        return temp_c
    elif to_unit.lower() in ['fahrenheit', 'f']:
        return (temp_c * 9/5) + 32
    elif to_unit.lower() in ['kelvin', 'k']:
        return temp_c + 273.15
    else:
        raise ValueError(f"Unsupported temperature unit: {to_unit}")


def calculate_wind_power_density(wind_speed: float, air_density: float = 1.225) -> float:
    """Calculate wind power density (W/m²)."""
    # P = 0.5 * ρ * v³
    power_density = 0.5 * air_density * (wind_speed ** 3)
    return round(power_density, 2)


def estimate_air_density(temperature: float, pressure: float, humidity: float = 0) -> float:
    """Estimate air density based on temperature, pressure, and humidity."""
    # Simplified air density calculation
    # ρ = P / (R * T) where R is specific gas constant for air
    R_dry = 287.05  # J/(kg·K) - specific gas constant for dry air

    # Convert temperature to Kelvin
    temp_k = temperature + 273.15

    # Convert pressure to Pascals
    pressure_pa = pressure * 100

    # Basic density calculation
    density = pressure_pa / (R_dry * temp_k)

    # Adjust for humidity (simplified)
    if humidity > 0:
        # Reduce density slightly for humidity
        density *= (1 - (humidity / 100) * 0.02)

    return round(density, 3)


def calculate_beaufort_scale(wind_speed: float) -> int:
    """Calculate Beaufort scale number from wind speed (m/s)."""
    if wind_speed < 0.3:
        return 0  # Calm
    elif wind_speed < 1.6:
        return 1  # Light air
    elif wind_speed < 3.4:
        return 2  # Light breeze
    elif wind_speed < 5.5:
        return 3  # Gentle breeze
    elif wind_speed < 8.0:
        return 4  # Moderate breeze
    elif wind_speed < 10.8:
        return 5  # Fresh breeze
    elif wind_speed < 13.9:
        return 6  # Strong breeze
    elif wind_speed < 17.2:
        return 7  # Near gale
    elif wind_speed < 20.8:
        return 8  # Gale
    elif wind_speed < 24.5:
        return 9  # Strong gale
    elif wind_speed < 28.5:
        return 10  # Storm
    elif wind_speed < 32.7:
        return 11  # Violent storm
    else:
        return 12  # Hurricane


def calculate_uv_index(uv_radiation: float) -> int:
    """Calculate UV index from UV radiation (W/m²)."""
    # Convert UV radiation to UV index
    # 1 UV index ≈ 0.025 W/m² of UV radiation
    uv_index = uv_radiation / 0.025
    return min(int(uv_index + 0.5), 11)  # Max UV index is 11


def validate_coordinates(latitude: float, longitude: float) -> bool:
    """Validate latitude and longitude coordinates."""
    return -90 <= latitude <= 90 and -180 <= longitude <= 180


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates using Haversine formula (km)."""
    from math import radians, cos, sin, asin, sqrt

    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    # Radius of earth in kilometers
    r = 6371

    return round(c * r, 2)


def interpolate_weather_data(
    data_points: List[Dict[str, Any]],
    target_time: datetime,
    method: str = "linear"
) -> Optional[Dict[str, Any]]:
    """Interpolate weather data to target time."""
    if not data_points or len(data_points) < 2:
        return None

    # Sort by time
    sorted_points = sorted(data_points, key=lambda x: x["timestamp"])

    # Find surrounding points
    before = None
    after = None

    for point in sorted_points:
        if point["timestamp"] <= target_time:
            before = point
        else:
            after = point
            break

    if not before or not after:
        return None

    # Linear interpolation
    if method == "linear":
        time_diff = (after["timestamp"] - before["timestamp"]).total_seconds()
        target_diff = (target_time - before["timestamp"]).total_seconds()

        if time_diff == 0:
            return before

        ratio = target_diff / time_diff

        interpolated = {
            "timestamp": target_time,
            "interpolated": True
        }

        # Interpolate numeric values
        for key, value in before.items():
            if key not in ["timestamp", "interpolated"] and isinstance(value, (int, float)):
                after_value = after.get(key)
                if after_value is not None:
                    interpolated[key] = value + ratio * (after_value - value)
                else:
                    interpolated[key] = value
            else:
                interpolated[key] = value

        return interpolated

    return None


class WeatherDataValidator:
    """Weather data validation utilities."""

    @staticmethod
    def validate_temperature(temp: float) -> bool:
        """Validate temperature range."""
        return -80 <= temp <= 80

    @staticmethod
    def validate_humidity(humidity: float) -> bool:
        """Validate humidity range."""
        return 0 <= humidity <= 100

    @staticmethod
    def validate_wind_speed(speed: float) -> bool:
        """Validate wind speed range."""
        return 0 <= speed <= 150  # m/s (very high upper limit)

    @staticmethod
    def validate_wind_direction(direction: float) -> bool:
        """Validate wind direction range."""
        return 0 <= direction <= 360

    @staticmethod
    def validate_pressure(pressure: float) -> bool:
        """Validate atmospheric pressure range."""
        return 800 <= pressure <= 1100  # hPa