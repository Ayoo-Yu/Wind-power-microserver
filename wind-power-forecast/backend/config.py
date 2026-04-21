import os
from minio import Minio
from minio.commonconfig import ENABLED
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 统一去掉环境变量首尾空格，避免连接串解析失败
def _env(name, default):
    value = os.environ.get(name, default)
    return str(value).strip() if value is not None else str(default).strip()

# 获取环境变量，如果不存在则使用默认值
DB_HOST = _env('DB_HOST', 'localhost')  # 本地默认 localhost
DB_PORT = _env('DB_PORT', '54321')
DB_USER = _env('DB_USER', 'system')
DB_PASSWORD = _env('DB_PASSWORD', '')
DB_NAME = _env('DB_NAME', 'windpower')

# MinIO 配置
MINIO_ENDPOINT = _env('MINIO_ENDPOINT', 'minio')
MINIO_PORT = _env('MINIO_PORT', '9900')
MINIO_ACCESS_KEY = _env('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = _env('MINIO_SECRET_KEY', 'minioadmin')
MINIO_SECURE = _env('MINIO_SECURE', 'False').lower() == 'true'

# 打印连接配置用于调试
print(f"数据库连接配置: {DB_HOST}:{DB_PORT}/{DB_NAME}")
print(f"MinIO 连接配置: {'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}:{MINIO_PORT}")

KINGBASE_CONFIG = {
    "host": _env('DB_HOST_OVERRIDE', DB_HOST),
    "port": _env('DB_PORT_OVERRIDE', DB_PORT),
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME
}

if not KINGBASE_CONFIG['password']:
    raise RuntimeError("DB_PASSWORD environment variable is required")

MINIO_CONFIG = {
    "endpoint": _env('MINIO_HOST_OVERRIDE', MINIO_ENDPOINT),
    "port": _env('MINIO_PORT_OVERRIDE', MINIO_PORT),
    "access_key": MINIO_ACCESS_KEY,
    "secret_key": MINIO_SECRET_KEY,
    "secure": MINIO_SECURE,
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

    KINGBASE_CONFIG = KINGBASE_CONFIG

    MINIO_CONFIG = MINIO_CONFIG

    MODEL_STORAGE = {
        'model_dir': os.path.join(BASE_DIR, 'saved_models'),
        'scaler_dir': os.path.join(BASE_DIR, 'saved_scalers'),
        'metrics_dir': os.path.join(BASE_DIR, 'saved_metrics')
    }

    SECRET_KEY = _env('SECRET_KEY', '')
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is required")
    # DEPRECATED: This URI is intentionally non-functional (masked password, no override host).
    # Real connections use database_config.py which reads KINGBASE_CONFIG with overrides.
    SQLALCHEMY_DATABASE_URI = f"postgresql+kingbase://{DB_USER}:***@{KINGBASE_CONFIG['host']}:{KINGBASE_CONFIG['port']}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = _env('FLASK_DEBUG', 'True').lower() == 'true'
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = 1800  # 30分钟

def set_bucket_policy(client, bucket_name, policy):
    """设置更精细的桶策略"""
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

