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

# 打印配置信息用于调试
print(f"数据库连接配置: {DB_HOST}:{DB_PORT}/{DB_NAME}")
print(f"MinIO连接配置: {'https' if MINIO_SECURE else 'http'}://{MINIO_ENDPOINT}:{MINIO_PORT}")

# Database Configuration
# For local development, set DB_HOST_OVERRIDE and DB_PORT_OVERRIDE environment variables.
# Example for local: DB_HOST_OVERRIDE=localhost, DB_PORT_OVERRIDE=54321
# Docker containers will use defaults (service names) if these env vars are not set.
KINGBASE_CONFIG = {
    'host': os.environ.get('DB_HOST_OVERRIDE', DB_HOST),
    'port': int(os.environ.get('DB_PORT_OVERRIDE', DB_PORT)),
    'user': DB_USER,
    'password': DB_PASSWORD, # Consider better secret management
    'database': DB_NAME,
}

# MinIO Configuration
# For local development, set MINIO_HOST_OVERRIDE and MINIO_PORT_OVERRIDE environment variables.
# Example for local: MINIO_HOST_OVERRIDE=localhost, MINIO_PORT_OVERRIDE=9900 (host-mapped port)
# Docker containers will use defaults (service name 'minio' and internal port '9000').
MINIO_HOST_DEFAULT = 'minio'
MINIO_PORT_DEFAULT_INTERNAL = 9000 # MinIO service listens on 9000 internally

MINIO_CONFIG = {
    'endpoint_host': os.environ.get('MINIO_HOST_OVERRIDE', MINIO_ENDPOINT),
    'endpoint_port': int(os.environ.get('MINIO_PORT_OVERRIDE', MINIO_PORT)),
    'access_key': MINIO_ACCESS_KEY,
    'secret_key': MINIO_SECRET_KEY,
    'secure': MINIO_SECURE,
    'buckets': {
        'models': os.environ.get('MINIO_BUCKET_MODELS', 'models'),
        'scalers': os.environ.get('MINIO_BUCKET_SCALERS', 'scalers'),
        'metrics': os.environ.get('MINIO_BUCKET_METRICS', 'metrics'),
        'predict_inputs': os.environ.get('MINIO_BUCKET_PREDICT_INPUTS', 'predict-inputs'), # Example, adjust if needed
        'predict_outputs': os.environ.get('MINIO_BUCKET_PREDICT_OUTPUTS', 'predict-outputs'),# Example, adjust if needed
        # Add other buckets as defined in your actual MINIO_CONFIG
    },
    'policies': { # Example policies, ensure these match your requirements
        'models': 'readonly',
        'scalers': 'readonly',
        'metrics': 'readonly',
        'predict_inputs': 'readwrite',
        'predict_outputs': 'readwrite',
        # Add other policies as defined
    }
}

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'forecasts')
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'pkl', 'json', 'joblib', 'h5', 'hdf5', 'pb', 'pt', 'pth'}
    
    # 添加脚本路径配置
    AUTOSCRIPT_BASE_DIR = os.path.join(BASE_DIR, 'auto_scripts', 'scripts')
    SCRIPT_PATHS = {
        'short': os.path.join(AUTOSCRIPT_BASE_DIR, 'short', 'scheduler_short.py'),
        'medium': os.path.join(AUTOSCRIPT_BASE_DIR, 'middle', 'scheduler_middle.py'),
        'supershort': os.path.join(AUTOSCRIPT_BASE_DIR, 'supershort', 'scheduler_supershort.py'),
    }
    
    # 添加日志目录配置
    LOG_DIRS = {
        'short': {
            'base': os.path.join(AUTOSCRIPT_BASE_DIR, 'short', 'logs'),
            'train': os.path.join(AUTOSCRIPT_BASE_DIR, 'short', 'logs', 'auto_pre_train'),
        },
        'medium': {
            'base': os.path.join(AUTOSCRIPT_BASE_DIR, 'middle', 'logs'),
            'train': os.path.join(AUTOSCRIPT_BASE_DIR, 'middle', 'logs', 'auto_pre_train'),
        },
        'supershort': {
            'base': os.path.join(AUTOSCRIPT_BASE_DIR, 'supershort', 'logs'),
            'train': os.path.join(AUTOSCRIPT_BASE_DIR, 'supershort', 'logs', 'auto_train'),
            'predict': os.path.join(AUTOSCRIPT_BASE_DIR, 'supershort', 'logs', 'auto_predict'),
        }
    }

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

    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key')
    SQLALCHEMY_DATABASE_URI = f"postgresql+kingbase://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = 1800  # 30分钟

def set_bucket_policy(client, bucket_name, policy):
    """更精确的策略配置"""
    policy_json_str = None # Initialize to None

    if policy == "private":
        # A truly private policy: no anonymous access at all.
        # Owner (account that created the bucket) still has full control.
        policy_data = {
            "Version": "2012-10-17",
            "Statement": [] # Empty statement array effectively makes it private
        }
        policy_json_str = json.dumps(policy_data)

    elif policy == "public-read":
        policy_data = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }]
        }
        policy_json_str = json.dumps(policy_data)

    elif policy == "readonly": # Handling 'readonly'
        policy_data = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject", "s3:ListBucket"],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}/*", # For objects
                        f"arn:aws:s3:::{bucket_name}"    # For listing the bucket itself
                    ]
                }
            ]
        }
        policy_json_str = json.dumps(policy_data)

    elif policy == "readwrite": # Handling 'readwrite'
        # This is a very permissive policy, effectively public read-write.
        # Consider if this is truly needed. Often, authenticated write is preferred.
        policy_data = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": [
                        "s3:GetObject",
                        "s3:ListBucket",
                        "s3:PutObject",
                        "s3:DeleteObject" # Add other actions as needed for "write"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}/*",
                        f"arn:aws:s3:::{bucket_name}"
                    ]
                }
            ]
        }
        policy_json_str = json.dumps(policy_data)
    else:
        print(f"警告: 未知的存储桶策略类型 '{policy}' (存储桶: {bucket_name}). 将不会设置策略.")

    if policy_json_str:
        try:
            client.set_bucket_policy(bucket_name, policy_json_str)
            print(f"[OK] 成功为存储桶 '{bucket_name}' 设置策略: '{policy}'")
        except Exception as e:
            print(f"[ERROR] 为存储桶 '{bucket_name}' (策略: '{policy}') 设置策略失败: {e}")
    # else: policy_json_str is None, so we do nothing (already warned)
