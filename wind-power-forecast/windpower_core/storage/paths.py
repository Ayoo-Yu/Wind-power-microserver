"""Helpers for building object storage and local filesystem paths scoped by wind farm."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

DATE_DIR_FMT = "%Y%m%d"
TIMESTAMP_FMT = "%Y%m%d%H%M%S"
_SEGMENT_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")


def _slug(value: Optional[str], fallback: str) -> str:
    if not value:
        return fallback
    candidate = value.strip()
    if not candidate:
        return fallback
    candidate = _SEGMENT_PATTERN.sub("-", candidate)
    candidate = candidate.strip("-_.")
    return candidate.lower() or fallback


def sanitize_filename(filename: str, fallback: str = "file") -> str:
    """Return a sanitized filename preserving a simple extension when possible."""

    name = Path(filename).name
    if not name:
        return f"{fallback}.dat"

    stem = _slug(Path(name).stem, fallback)
    suffix = Path(name).suffix

    if suffix and not re.fullmatch(r"\.[a-zA-Z0-9]{1,10}", suffix):
        suffix = ""

    return f"{stem}{suffix}"


def normalize_wind_farm_code(code: Optional[str], default_code: str) -> str:
    """Normalize a wind farm code with a fallback default."""

    default_slug = _slug(default_code, "default")
    return _slug(code, default_slug)


def _timestamp(value: Optional[datetime], fmt: str) -> str:
    return (value or datetime.utcnow()).strftime(fmt)


def dataset_object_key(
    *,
    wind_farm_code: str,
    data_type: str,
    filename: str,
    uploaded_at: Optional[datetime] = None,
) -> str:
    date_dir = _timestamp(uploaded_at, DATE_DIR_FMT)
    return f"{wind_farm_code}/datasets/{_slug(data_type, 'general')}/{date_dir}/{filename}"


def model_object_key(
    *,
    wind_farm_code: str,
    model_type: str,
    filename: str,
    trained_at: Optional[datetime] = None,
) -> str:
    date_dir = _timestamp(trained_at, DATE_DIR_FMT)
    return f"{wind_farm_code}/models/{_slug(model_type, 'general')}/{date_dir}/{filename}"


def scaler_object_key(
    *,
    wind_farm_code: str,
    model_type: str,
    filename: str,
    created_at: Optional[datetime] = None,
) -> str:
    ts = _timestamp(created_at, TIMESTAMP_FMT)
    return f"{wind_farm_code}/scalers/{_slug(model_type, 'general')}/{ts}/{filename}"


def prediction_object_key(
    *,
    wind_farm_code: str,
    prediction_type: str,
    model_identifier: str,
    filename: str,
    generated_at: Optional[datetime] = None,
) -> str:
    ts = _timestamp(generated_at, TIMESTAMP_FMT)
    return f"{wind_farm_code}/predictions/{_slug(prediction_type, 'batch')}/{_slug(model_identifier, 'model')}/{ts}/{filename}"


def metrics_object_key(
    *,
    wind_farm_code: str,
    model_identifier: str,
    filename: str,
    computed_at: Optional[datetime] = None,
) -> str:
    ts = _timestamp(computed_at, TIMESTAMP_FMT)
    return f"{wind_farm_code}/metrics/{_slug(model_identifier, 'model')}/{ts}/{filename}"


def ensure_local_subdir(
    base_dir: Path | str,
    wind_farm_code: str,
    *segments: str,
) -> Path:
    """Ensure a local directory exists for the given wind farm and return it."""

    base = Path(base_dir)
    subsegments = [wind_farm_code, *(_slug(segment, "general") for segment in segments if segment)]
    target = base.joinpath(*subsegments)
    target.mkdir(parents=True, exist_ok=True)
    return target

