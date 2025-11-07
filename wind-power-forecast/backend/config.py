import os
from minio import Minio
from minio.commonconfig import ENABLED
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取环境变量，如果不存在则使用默认值
DB_HOST = os.environ.get('DB_HOST', 'kingbase')
DB_PORT = os.environ.get('DB_PORT', '54321')
DB_USER = os.environ.get('DB_USER', 'system')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '12345678ab')
DB_NAME = os.environ.get('DB_NAME', 'windpower')

# MinIO配置
MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'minio')
MINIO_PORT = os.environ.get('MINIO_PORT', '9900')
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', 'minioadmin')
MINIO_SECURE = os.environ.get('MINIO_SECURE', 'False').lower() == 'true'

# 默认场站配置
DEFAULT_WIND_FARM_CODE = os.environ.get('DEFAULT_WIND_FARM_CODE', 'default-farm')

# Redis / Celery 配置
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)
CELERY_TASK_DEFAULT_QUEUE = os.environ.get('CELERY_TASK_DEFAULT_QUEUE', 'windpower-default')
CELERY_TIMEZONE = os.environ.get('CELERY_TIMEZONE', 'Asia/Shanghai')

# 打印配置信息用于调试
print(f"数据库连接配置: {DB_HOST}:{DB_PORT}/{DB_NAME}")
print(f"MinIO连接配置: {'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}:{MINIO_PORT}")
print(f"任务队列配置: {REDIS_URL}")

KINGBASE_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME
}

MINIO_CONFIG = {
    "endpoint": MINIO_ENDPOINT,
    "port": MINIO_PORT,
    "access_key": MINIO_ACCESS_KEY,
    "secret_key": MINIO_SECRET_KEY,
    "secure": MINIO_SECURE,
    "default_wind_farm_code": DEFAULT_WIND_FARM_CODE,
    "buckets": {
        "datasets": "wind-datasets",
        "models": "wind-models",
        "predictions": "wind-predictions",
        "scalers": "wind-scalers",
        "metrics": "wind-metrics",
        "logs": "wind-logs"
    },
    "policies": {
        "wind-datasets": "private",
        "wind-models": "public-read",
        "wind-predictions": "private",
        "wind-scalers": "private",
        "wind-metrics": "public-read",
        "wind-logs": "public-read"
    }
}

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'forecasts')
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'pkl', 'json', 'joblib', 'h5', 'hdf5', 'pb', 'pt', 'pth'}

    KINGBASE_CONFIG = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "database": DB_NAME
    }
    
    MINIO_CONFIG = {
        "endpoint": MINIO_ENDPOINT,
        "port": MINIO_PORT,
        "access_key": MINIO_ACCESS_KEY,
        "secret_key": MINIO_SECRET_KEY,
        "secure": MINIO_SECURE,
        "default_wind_farm_code": DEFAULT_WIND_FARM_CODE,
        "buckets": {
            "datasets": "wind-datasets",
            "models": "wind-models",
            "predictions": "wind-predictions",
            "scalers": "wind-scalers",
            "metrics": "wind-metrics",
            "logs": "wind-logs"
        },
        "policies": {
            "wind-datasets": "private",
            "wind-models": "public-read",
            "wind-predictions": "private",
            "wind-scalers": "private",
            "wind-metrics": "public-read",
            "wind-logs": "public-read"
        }
    }

    MODEL_STORAGE = {
        'model_dir': os.path.join(BASE_DIR, 'saved_models'),
        'scaler_dir': os.path.join(BASE_DIR, 'saved_scalers'),
        'metrics_dir': os.path.join(BASE_DIR, 'saved_metrics')
    }

    DEFAULT_WIND_FARM_CODE = DEFAULT_WIND_FARM_CODE

    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key')
    SQLALCHEMY_DATABASE_URI = f"postgresql+kingbase://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
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
