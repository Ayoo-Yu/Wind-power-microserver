"""
Utility functions for Report Service
"""

import logging
import json
import uuid
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import asyncio
import aiohttp
from pathlib import Path
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


def create_error_response(message: str, error_code: str = "ERROR", details: Optional[Dict[str, Any]] = None) -> Dict:
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


def calculate_percentage(value: float, total: float, default: float = 0.0) -> float:
    """Calculate percentage safely."""
    return safe_divide(value * 100, total, default)


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f} {size_names[i]}"


def calculate_hash(data: Union[str, bytes, dict]) -> str:
    """Calculate MD5 hash of data."""
    if isinstance(data, dict):
        data = json.dumps(data, sort_keys=True)

    if isinstance(data, str):
        data = data.encode('utf-8')

    return hashlib.md5(data).hexdigest()


def encode_base64(data: bytes) -> str:
    """Encode bytes to base64 string."""
    return base64.b64encode(data).decode('utf-8')


def decode_base64(data: str) -> bytes:
    """Decode base64 string to bytes."""
    return base64.b64decode(data)


def validate_email(email: str) -> bool:
    """Validate email address format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system usage."""
    import re
    # Remove or replace unsafe characters
    filename = re.sub(r'[\/:*?"\u003c\u003e|]', '_', filename)
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    return filename or 'unnamed'


def create_directory(path: str) -> bool:
    """Create directory if it doesn't exist."""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to create directory {path}: {e}")
        return False


def delete_file(file_path: str) -> bool:
    """Delete file safely."""
    try:
        Path(file_path).unlink(missing_ok=True)
        return True
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to delete file {file_path}: {e}")
        return False


def file_exists(file_path: str) -> bool:
    """Check if file exists."""
    return Path(file_path).exists()


def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    try:
        return Path(file_path).stat().st_size
    except Exception:
        return 0


def read_file(file_path: str, encoding: str = 'utf-8') -> str:
    """Read text file."""
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            return f.read()
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to read file {file_path}: {e}")
        return ""


def write_file(file_path: str, content: str, encoding: str = 'utf-8') -> bool:
    """Write text file."""
    try:
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
        return True
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to write file {file_path}: {e}")
        return False


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


def parse_cron_expression(cron_expr: str) -> Dict[str, Any]:
    """Parse cron expression and return schedule details."""
    try:
        # Simple cron parser (minute hour day month weekday)
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError("Invalid cron expression format")

        minute, hour, day, month, weekday = parts

        return {
            "minute": minute,
            "hour": hour,
            "day": day,
            "month": month,
            "weekday": weekday,
            "expression": cron_expr
        }
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to parse cron expression {cron_expr}: {e}")
        return {}


def get_next_run_time(cron_expr: str, current_time: Optional[datetime] = None) -> datetime:
    """Calculate next run time from cron expression."""
    try:
        if current_time is None:
            current_time = datetime.utcnow()

        # This is a simplified implementation
        # In production, use a proper cron library like croniter

        # For now, just add 1 hour as a placeholder
        return current_time + timedelta(hours=1)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to calculate next run time for {cron_expr}: {e}")
        return current_time + timedelta(hours=1)


def validate_report_parameters(parameters: Dict[str, Any], report_type: str) -> bool:
    """Validate report parameters."""
    try:
        from .config import REPORT_TYPES

        report_config = REPORT_TYPES.get(report_type, {})
        required_params = report_config.get("required_parameters", [])

        for param in required_params:
            if param not in parameters:
                return False

        return True
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to validate report parameters: {e}")
        return False


def calculate_data_quality_score(data: List[Dict[str, Any]]) -> float:
    """Calculate data quality score."""
    try:
        if not data:
            return 0.0

        total_records = len(data)
        if total_records == 0:
            return 0.0

        # Check for missing values
        completeness_scores = []
        for record in data:
            if isinstance(record, dict):
                missing_count = sum(1 for v in record.values() if v is None)
                total_fields = len(record)
                completeness = safe_divide(total_fields - missing_count, total_fields)
                completeness_scores.append(completeness)

        avg_completeness = np.mean(completeness_scores) if completeness_scores else 0.0

        # Check for data validity (no extreme outliers)
        validity_score = 1.0  # Simplified - would need more sophisticated validation

        # Calculate overall quality score
        quality_score = (avg_completeness + validity_score) / 2.0 * 100

        return min(100.0, max(0.0, quality_score))

    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to calculate data quality score: {e}")
        return 0.0


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


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple dictionaries."""
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def sanitize_html(html: str) -> str:
    """Sanitize HTML content."""
    import re
    # Remove potentially dangerous tags and attributes
    html = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'javascript:', '', html, flags=re.IGNORECASE)
    html = re.sub(r'on\w+\s*=', '', html, flags=re.IGNORECASE)
    return html


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def generate_random_string(length: int = 8) -> str:
    """Generate random alphanumeric string."""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def is_valid_url(url: str) -> bool:
    """Validate URL format."""
    import re
    pattern = r'^https?://[^\/\s]+(/[^\s]*)?$'
    return re.match(pattern, url) is not None


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean DataFrame by removing empty rows and columns."""
    # Remove completely empty rows
    df = df.dropna(how='all')

    # Remove completely empty columns
    df = df.dropna(axis=1, how='all')

    # Replace infinite values with NaN
    df = df.replace([np.inf, -np.inf], np.nan)

    return df


def format_number(value: Union[int, float], decimals: int = 2) -> str:
    """Format number with specified decimal places."""
    if isinstance(value, int):
        return str(value)
    elif isinstance(value, float):
        return f"{value:.{decimals}f}"
    else:
        return str(value)


def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """Calculate basic statistics for a list of numbers."""
    if not values:
        return {}

    try:
        import numpy as np

        values_array = np.array(values)

        return {
            "count": len(values),
            "mean": float(np.mean(values_array)),
            "median": float(np.median(values_array)),
            "std": float(np.std(values_array)),
            "min": float(np.min(values_array)),
            "max": float(np.max(values_array)),
            "sum": float(np.sum(values_array))
        }
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to calculate statistics: {e}")
        return {}


# Global logger
logger = get_logger(__name__)