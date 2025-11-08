import json
from .libs.config import settings

# ---- 基础配置导出 --------------------------------------------------------

_settings = settings

DB_HOST = _settings.db_host
DB_PORT = str(_settings.db_port)
DB_USER = _settings.db_user
DB_PASSWORD = _settings.db_password
DB_NAME = _settings.db_name

KINGBASE_CONFIG = _settings.kingbase_config
MINIO_CONFIG = _settings.minio_config

REDIS_URL = _settings.redis_url
CELERY_RESULT_BACKEND = _settings.celery_backend
CELERY_TASK_DEFAULT_QUEUE = _settings.celery_task_default_queue
CELERY_TIMEZONE = _settings.celery_timezone

DEFAULT_WIND_FARM_CODE = _settings.default_wind_farm_code

# ---- Flask 配置对象 -----------------------------------------------------


class Config:
    BASE_DIR = str(_settings.base_dir)
    UPLOAD_FOLDER = str(_settings.upload_folder)
    DOWNLOAD_FOLDER = str(_settings.download_folder)
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'pkl', 'json', 'joblib', 'h5', 'hdf5', 'pb', 'pt', 'pth'}

    KINGBASE_CONFIG = dict(KINGBASE_CONFIG)
    MINIO_CONFIG = dict(MINIO_CONFIG)

    MODEL_STORAGE = dict(_settings.model_storage_dirs)

    DEFAULT_WIND_FARM_CODE = DEFAULT_WIND_FARM_CODE

    SECRET_KEY = _settings.secret_key
    SQLALCHEMY_DATABASE_URI = _settings.sqlalchemy_database_uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = _settings.flask_debug
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = 1800  # 30分钟
    REDIS_URL = REDIS_URL
    CELERY_RESULT_BACKEND = CELERY_RESULT_BACKEND
    CELERY_TASK_DEFAULT_QUEUE = CELERY_TASK_DEFAULT_QUEUE
    CELERY_TIMEZONE = CELERY_TIMEZONE

def set_bucket_policy(client, bucket_name, policy):
    """更精确的策略配置"""
    if policy == "private":
        policy_json = json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": [
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:PutObjectAcl",
                        "s3:GetObjectAcl"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}",
                        f"arn:aws:s3:::{bucket_name}/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/*",
                    "Condition": {
                        "StringEquals": {
                            "aws:UserAgent": "WindPowerForecast/1.0"
                        }
                    }
                }
            ]
        })
    elif policy == "public-read":
        policy_json = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }]
        })
    client.set_bucket_policy(bucket_name, policy_json)
