from __future__ import annotations

import os
from typing import Iterable

import pytest

from backend.libs.config.settings import get_settings


_ENV_KEYS: Iterable[str] = (
    "APP_ENV",
    "DB_HOST",
    "DB_PORT",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
    "MINIO_ENDPOINT",
    "MINIO_PORT",
    "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY",
    "MINIO_SECURE",
    "DEFAULT_WIND_FARM_CODE",
    "REDIS_URL",
    "CELERY_RESULT_BACKEND",
    "CELERY_TASK_DEFAULT_QUEUE",
    "CELERY_TIMEZONE",
    "SECRET_KEY",
    "FLASK_DEBUG",
    "JWT_SECRET_KEY",
    "JWT_ACCESS_TOKEN_EXPIRES_HOURS",
    "UPLOAD_FOLDER",
    "DOWNLOAD_FOLDER",
    "MODEL_DIR",
    "SCALER_DIR",
    "METRICS_DIR",
    "CORS_ALLOWED_ORIGINS",
    "CORS_ALLOWED_METHODS",
    "CORS_ALLOWED_HEADERS",
)


@pytest.fixture(autouse=True)
def reset_settings_cache(monkeypatch: pytest.MonkeyPatch):
    """
    在每个测试前后清空配置缓存，避免环境变量污染。
    """

    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


