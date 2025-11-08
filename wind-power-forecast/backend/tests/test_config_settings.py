from __future__ import annotations

from pathlib import Path

import pytest

from backend.libs.config.settings import AppSettings, get_settings


def test_default_settings_paths():
    settings = get_settings()

    expected_base = Path(__file__).resolve().parents[1]
    assert settings.base_dir == expected_base
    assert settings.upload_folder == expected_base / "uploads"
    assert settings.download_folder == expected_base / "forecasts"

    model_dirs = settings.model_storage_dirs
    assert model_dirs["model_dir"] == str(expected_base / "saved_models")
    assert model_dirs["scaler_dir"] == str(expected_base / "saved_scalers")
    assert model_dirs["metrics_dir"] == str(expected_base / "saved_metrics")


def test_env_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DB_HOST", "db.internal")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_USER", "forecast")
    monkeypatch.setenv("DB_PASSWORD", "secure-pass")
    monkeypatch.setenv("DB_NAME", "wind")
    monkeypatch.setenv("MINIO_ENDPOINT", "minio.internal")
    monkeypatch.setenv("MINIO_PORT", "9000")
    monkeypatch.setenv("MINIO_SECURE", "true")
    monkeypatch.setenv("DEFAULT_WIND_FARM_CODE", "farm-001")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://cache:6380/1")

    settings = get_settings()

    assert settings.db_host == "db.internal"
    assert settings.db_port == 5432
    assert settings.db_user == "forecast"
    assert settings.db_password == "secure-pass"
    assert settings.db_name == "wind"
    assert settings.sqlalchemy_database_uri.endswith("@db.internal:5432/wind")

    minio = settings.minio_config
    assert minio["endpoint"] == "minio.internal"
    assert minio["port"] == "9000"
    assert minio["secure"] is True
    assert minio["default_wind_farm_code"] == "farm-001"

    assert settings.celery_backend == "redis://cache:6380/1"


def test_cors_and_queue_parsing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/5")
    monkeypatch.setenv("CELERY_TASK_DEFAULT_QUEUE", "forecasting")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.example.com, https://b.example.com")
    monkeypatch.setenv("CORS_ALLOWED_METHODS", "GET,POST")
    monkeypatch.setenv("CORS_ALLOWED_HEADERS", "Authorization, Content-Type")

    settings = get_settings()

    assert settings.redis_url == "redis://redis:6379/5"
    assert settings.celery_task_default_queue == "forecasting"
    assert settings.cors_origins_list == ["https://a.example.com", "https://b.example.com"]
    assert settings.cors_allowed_methods == "GET,POST"
    assert settings.cors_allowed_headers == "Authorization, Content-Type"


