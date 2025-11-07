from datetime import datetime
from typing import Optional

from config import MINIO_CONFIG
from windpower_core.storage import (
    metrics_object_key,
    model_object_key,
    normalize_wind_farm_code,
    prediction_object_key,
    sanitize_filename,
    scaler_object_key,
)


DEFAULT_WIND_FARM_CODE = MINIO_CONFIG.get("default_wind_farm_code", "default-farm")


def _resolve_farm_code(wind_farm_code: Optional[str]) -> str:
    return normalize_wind_farm_code(wind_farm_code, DEFAULT_WIND_FARM_CODE)


def get_model_path(
    model_type: str,
    model_name: str,
    *,
    wind_farm_code: Optional[str] = None,
    trained_at: Optional[datetime] = None,
) -> str:
    filename = sanitize_filename(f"{model_name}.joblib", fallback="model")
    return model_object_key(
        wind_farm_code=_resolve_farm_code(wind_farm_code),
        model_type=model_type,
        filename=filename,
        trained_at=trained_at,
    )


def get_scaler_path(
    model_type: str,
    *,
    wind_farm_code: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> str:
    filename = sanitize_filename("scaler.joblib", fallback="scaler")
    return scaler_object_key(
        wind_farm_code=_resolve_farm_code(wind_farm_code),
        model_type=model_type,
        filename=filename,
        created_at=created_at,
    )


def get_prediction_path(
    prediction_type: str,
    model_id: str,
    *,
    wind_farm_code: Optional[str] = None,
    generated_at: Optional[datetime] = None,
    filename: Optional[str] = None,
) -> str:
    resolved_filename = sanitize_filename(filename or "prediction.csv", fallback="prediction")
    return prediction_object_key(
        wind_farm_code=_resolve_farm_code(wind_farm_code),
        prediction_type=prediction_type,
        model_identifier=model_id,
        filename=resolved_filename,
        generated_at=generated_at,
    )


def get_metrics_path(
    model_id: str,
    *,
    wind_farm_code: Optional[str] = None,
    computed_at: Optional[datetime] = None,
    filename: Optional[str] = None,
) -> str:
    resolved_filename = sanitize_filename(filename or "metrics.json", fallback="metrics")
    return metrics_object_key(
        wind_farm_code=_resolve_farm_code(wind_farm_code),
        model_identifier=model_id,
        filename=resolved_filename,
        computed_at=computed_at,
    )