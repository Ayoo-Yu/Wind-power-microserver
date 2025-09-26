"""
Utility functions for Power Prediction Service
"""

import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import asyncio
import aiohttp
from contextlib import asynccontextmanager


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


def generate_id() -> str:
    """Generate unique ID."""
    return str(uuid.uuid4())


def format_datetime(dt: datetime) -> str:
    """Format datetime to ISO string."""
    return dt.isoformat()


def parse_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string."""
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def calculate_time_difference(start_time: datetime, end_time: datetime) -> timedelta:
    """Calculate time difference."""
    return end_time - start_time


def get_time_range(hours: int, end_time: Optional[datetime] = None) -> tuple:
    """Get time range for specified hours."""
    if end_time is None:
        end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    return start_time, end_time


def validate_prediction_horizon(horizon: str) -> bool:
    """Validate prediction horizon format."""
    valid_horizons = ['1h', '6h', '12h', '24h', '48h', '72h']
    return horizon in valid_horizons


def convert_power_units(power: float, from_unit: str, to_unit: str) -> float:
    """Convert power between different units."""
    # Conversion factors
    conversions = {
        ('W', 'kW'): 0.001,
        ('kW', 'W'): 1000,
        ('kW', 'MW'): 0.001,
        ('MW', 'kW'): 1000,
        ('W', 'MW'): 0.000001,
        ('MW', 'W'): 1000000
    }

    if from_unit == to_unit:
        return power

    key = (from_unit, to_unit)
    if key in conversions:
        return power * conversions[key]

    raise ValueError(f"Unsupported power unit conversion: {from_unit} to {to_unit}")


def calculate_accuracy_metrics(actual: List[float], predicted: List[float]) -> Dict[str, float]:
    """Calculate accuracy metrics."""
    import numpy as np
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    actual = np.array(actual)
    predicted = np.array(predicted)

    mae = mean_absolute_error(actual, predicted)
    mse = mean_squared_error(actual, predicted)
    rmse = np.sqrt(mse)
    r2 = r2_score(actual, predicted)

    # MAPE (Mean Absolute Percentage Error)
    mape = np.mean(np.abs((actual - predicted) / actual)) * 100 if np.all(actual != 0) else float('inf')

    # MAE percentage
    mae_pct = (mae / np.mean(actual)) * 100 if np.mean(actual) != 0 else 0

    return {
        "mae": float(mae),
        "mse": float(mse),
        "rmse": float(rmse),
        "r2": float(r2),
        "mape": float(mape),
        "mae_percentage": float(mae_pct)
    }


def detect_outliers(data: List[float], method: str = "iqr") -> List[int]:
    """Detect outliers in data."""
    import numpy as np

    data = np.array(data)

    if method == "iqr":
        Q1 = np.percentile(data, 25)
        Q3 = np.percentile(data, 75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        outliers = np.where((data < lower_bound) | (data > upper_bound))[0]

    elif method == "zscore":
        z_scores = np.abs((data - np.mean(data)) / np.std(data))
        outliers = np.where(z_scores > 3)[0]

    else:
        raise ValueError(f"Unknown outlier detection method: {method}")

    return outliers.tolist()


def smooth_data(data: List[float], window_size: int = 3, method: str = "moving_average") -> List[float]:
    """Smooth data using various methods."""
    import numpy as np
    from scipy import signal

    data = np.array(data)

    if method == "moving_average":
        smoothed = np.convolve(data, np.ones(window_size) / window_size, mode='same')

    elif method == "savitzky_golay":
        smoothed = signal.savgol_filter(data, window_size, 2)

    elif method == "gaussian":
        smoothed = signal.gaussian_filter1d(data, window_size)

    else:
        raise ValueError(f"Unknown smoothing method: {method}")

    return smoothed.tolist()


def interpolate_missing_values(data: List[float], method: str = "linear") -> List[float]:
    """Interpolate missing values in data."""
    import numpy as np
    from scipy import interpolate

    data = np.array(data)
    mask = ~np.isnan(data)

    if not np.any(mask):
        return data.tolist()

    indices = np.arange(len(data))

    if method == "linear":
        interpolator = interpolate.interp1d(indices[mask], data[mask], kind='linear',
                                           bounds_error=False, fill_value='extrapolate')

    elif method == "cubic":
        interpolator = interpolate.interp1d(indices[mask], data[mask], kind='cubic',
                                           bounds_error=False, fill_value='extrapolate')

    else:
        raise ValueError(f"Unknown interpolation method: {method}")

    interpolated = interpolator(indices)
    return interpolated.tolist()


class APIClient:
    """HTTP client for external API calls."""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.logger = get_logger(__name__)

    @asynccontextmanager
    async def get_session(self):
        """Get aiohttp session."""
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            yield session

    async def get(self, endpoint: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict:
        """Make GET request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        async with self.get_session() as session:
            try:
                async with session.get(url, params=params, headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                self.logger.error(f"GET request failed: {e}")
                raise

    async def post(self, endpoint: str, data: Dict, headers: Optional[Dict] = None) -> Dict:
        """Make POST request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        async with self.get_session() as session:
            try:
                async with session.post(url, json=data, headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                self.logger.error(f"POST request failed: {e}")
                raise


def create_error_response(message: str, error_code: str = "ERROR", details: Optional[Dict] = None) -> Dict:
    """Create standardized error response."""
    return {
        "success": False,
        "message": message,
        "error_code": error_code,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat()
    }


def create_success_response(message: str, data: Optional[Any] = None) -> Dict:
    """Create standardized success response."""
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division with default value."""
    try:
        return numerator / denominator if denominator != 0 else default
    except (TypeError, ValueError):
        return default


def normalize_data(data: List[float], min_val: Optional[float] = None, max_val: Optional[float] = None) -> List[float]:
    """Normalize data to [0, 1] range."""
    import numpy as np

    data = np.array(data)

    if min_val is None:
        min_val = np.min(data)
    if max_val is None:
        max_val = np.max(data)

    if max_val == min_val:
        return [0.5] * len(data)

    normalized = (data - min_val) / (max_val - min_val)
    return normalized.tolist()


def calculate_confidence_intervals(predictions: List[float], confidence_level: float = 0.95) -> Dict[str, float]:
    """Calculate confidence intervals for predictions."""
    import numpy as np
    from scipy import stats

    predictions = np.array(predictions)

    mean_pred = np.mean(predictions)
    std_pred = np.std(predictions)
    n = len(predictions)

    # Calculate confidence interval
    alpha = 1 - confidence_level
    t_critical = stats.t.ppf(1 - alpha/2, n - 1)
    margin_error = t_critical * (std_pred / np.sqrt(n))

    return {
        "mean": float(mean_pred),
        "std": float(std_pred),
        "lower_bound": float(mean_pred - margin_error),
        "upper_bound": float(mean_pred + margin_error),
        "confidence_level": confidence_level
    }


def validate_model_performance(metrics: Dict[str, float], thresholds: Dict[str, float]) -> bool:
    """Validate model performance against thresholds."""
    for metric, threshold in thresholds.items():
        if metric in metrics:
            if metric in ['mae', 'mse', 'rmse', 'mape']:
                # Lower is better
                if metrics[metric] > threshold:
                    return False
            elif metric in ['r2', 'accuracy']:
                # Higher is better
                if metrics[metric] < threshold:
                    return False

    return True


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def retry_async(max_retries: int = 3, delay: float = 1.0):
    """Async retry decorator."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
            return None
        return wrapper
    return decorator