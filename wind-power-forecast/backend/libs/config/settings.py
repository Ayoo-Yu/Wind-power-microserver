from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseSettings, Field


class AppSettings(BaseSettings):
    """
    后端核心配置。

    通过 Pydantic BaseSettings 自动从环境变量与 .env 文件读取，提供默认值并暴露便捷方法：
      - ``kingbase_config`` / ``minio_config`` 等字典配置
      - ``sqlalchemy_database_uri`` 等派生属性
    """

    # 基础
    app_env: str = Field("development", env="APP_ENV")

    # 数据库 / Kingbase
    db_host: str = Field("kingbase", env="DB_HOST")
    db_port: int = Field(54321, env="DB_PORT")
    db_user: str = Field("system", env="DB_USER")
    db_password: str = Field("12345678ab", env="DB_PASSWORD")
    db_name: str = Field("windpower", env="DB_NAME")

    # MinIO
    minio_endpoint: str = Field("minio", env="MINIO_ENDPOINT")
    minio_port: int = Field(9900, env="MINIO_PORT")
    minio_access_key: str = Field("minioadmin", env="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field("minioadmin", env="MINIO_SECRET_KEY")
    minio_secure: bool = Field(False, env="MINIO_SECURE")
    default_wind_farm_code: str = Field("default-farm", env="DEFAULT_WIND_FARM_CODE")

    # Celery / 队列
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    celery_result_backend: Optional[str] = Field(None, env="CELERY_RESULT_BACKEND")
    celery_task_default_queue: str = Field("windpower-default", env="CELERY_TASK_DEFAULT_QUEUE")
    celery_timezone: str = Field("Asia/Shanghai", env="CELERY_TIMEZONE")

    # Flask
    flask_debug: bool = Field(True, env="FLASK_DEBUG")
    secret_key: str = Field("your-secret-key", env="SECRET_KEY")

    # JWT
    jwt_secret_key: str = Field("wind-power-forecast-secret-key", env="JWT_SECRET_KEY")
    jwt_access_token_expires_hours: int = Field(12, env="JWT_ACCESS_TOKEN_EXPIRES_HOURS")

    # 路径
    upload_folder_override: Optional[str] = Field(None, env="UPLOAD_FOLDER")
    download_folder_override: Optional[str] = Field(None, env="DOWNLOAD_FOLDER")
    model_dir_override: Optional[str] = Field(None, env="MODEL_DIR")
    scaler_dir_override: Optional[str] = Field(None, env="SCALER_DIR")
    metrics_dir_override: Optional[str] = Field(None, env="METRICS_DIR")

    # CORS
    cors_allowed_origins: str = Field("*", env="CORS_ALLOWED_ORIGINS")
    cors_allowed_methods: str = Field("GET,POST,PUT,DELETE,OPTIONS", env="CORS_ALLOWED_METHODS")
    cors_allowed_headers: str = Field(
        "Content-Type,Authorization,X-Requested-With,Accept,Origin",
        env="CORS_ALLOWED_HEADERS",
    )

    class Config:
        env_file = (".env", ".env.local")
        env_file_encoding = "utf-8"
        case_sensitive = False

    # ---- 派生属性 -----------------------------------------------------
    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def upload_folder(self) -> Path:
        return Path(self.upload_folder_override or (self.base_dir / "uploads"))

    @property
    def download_folder(self) -> Path:
        return Path(self.download_folder_override or (self.base_dir / "forecasts"))

    @property
    def model_storage_dirs(self) -> Dict[str, str]:
        return {
            "model_dir": str(self.model_dir_override or (self.base_dir / "saved_models")),
            "scaler_dir": str(self.scaler_dir_override or (self.base_dir / "saved_scalers")),
            "metrics_dir": str(self.metrics_dir_override or (self.base_dir / "saved_metrics")),
        }

    @property
    def kingbase_config(self) -> Dict[str, str]:
        return {
            "host": self.db_host,
            "port": str(self.db_port),
            "user": self.db_user,
            "password": self.db_password,
            "database": self.db_name,
        }

    @property
    def minio_buckets(self) -> Dict[str, str]:
        return {
            "datasets": "wind-datasets",
            "models": "wind-models",
            "predictions": "wind-predictions",
            "scalers": "wind-scalers",
            "metrics": "wind-metrics",
            "logs": "wind-logs",
        }

    @property
    def minio_policies(self) -> Dict[str, str]:
        return {
            "wind-datasets": "private",
            "wind-models": "public-read",
            "wind-predictions": "private",
            "wind-scalers": "private",
            "wind-metrics": "public-read",
            "wind-logs": "public-read",
        }

    @property
    def minio_config(self) -> Dict[str, object]:
        return {
            "endpoint": self.minio_endpoint,
            "port": str(self.minio_port),
            "access_key": self.minio_access_key,
            "secret_key": self.minio_secret_key,
            "secure": self.minio_secure,
            "default_wind_farm_code": self.default_wind_farm_code,
            "buckets": self.minio_buckets,
            "policies": self.minio_policies,
        }

    @property
    def sqlalchemy_database_uri(self) -> str:
        user = self.db_user
        password = self.db_password
        host = self.db_host
        port = self.db_port
        database = self.db_name
        return f"postgresql+kingbase://{user}:{password}@{host}:{port}/{database}"

    @property
    def celery_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> AppSettings:
    """
    返回 Settings 单例；使用 lru_cache 避免重复读取 .env。
    """

    return AppSettings()


