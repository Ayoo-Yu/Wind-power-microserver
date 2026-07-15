import os
from dotenv import load_dotenv

load_dotenv()


def _env(name, default):
    value = os.environ.get(name, default)
    return str(value).strip() if value is not None else str(default).strip()


DB_HOST = _env('DB_HOST', 'localhost')
DB_PORT = _env('DB_PORT', '54321')
DB_USER = _env('DB_USER', 'system')
DB_PASSWORD = _env('DB_PASSWORD', '')
DB_NAME = _env('DB_NAME', 'windpower')

print(f"数据库连接配置: {DB_HOST}:{DB_PORT}/{DB_NAME}")

KINGBASE_CONFIG = {
    "host": _env('DB_HOST_OVERRIDE', DB_HOST),
    "port": _env('DB_PORT_OVERRIDE', DB_PORT),
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME
}

if not KINGBASE_CONFIG['password']:
    raise RuntimeError("DB_PASSWORD environment variable is required")


class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'forecasts')
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'pkl', 'json', 'joblib', 'h5', 'hdf5', 'pb', 'pt', 'pth'}

    # 跨区统一数据接入默认关闭，部署时必须显式启用并设置独立令牌。
    INTEGRATION_API_ENABLED = _env('INTEGRATION_API_ENABLED', 'false').lower() == 'true'
    INTEGRATION_API_TOKEN = _env('INTEGRATION_API_TOKEN', '')
    INTEGRATION_SPOOL_DIR = _env(
        'INTEGRATION_SPOOL_DIR',
        os.path.join(BASE_DIR, 'runtime', 'integration'),
    )
    INTEGRATION_MAX_PAYLOAD_BYTES = int(
        _env('INTEGRATION_MAX_PAYLOAD_BYTES', str(256 * 1024 * 1024))
    )
    DEPLOYMENT_MODE = _env('DEPLOYMENT_MODE', 'development')
    SCADA_REALTIME_ENABLED = _env('SCADA_REALTIME_ENABLED', 'false').lower() == 'true'
    NWP_INGESTION_ENABLED = _env('NWP_INGESTION_ENABLED', 'false').lower() == 'true'
    EXTREME_WEATHER_LIVE_ENABLED = _env(
        'EXTREME_WEATHER_LIVE_ENABLED', 'false'
    ).lower() == 'true'
    PHYSICAL_SIMULATION_ENABLED = _env(
        'PHYSICAL_SIMULATION_ENABLED', 'false'
    ).lower() == 'true'
    REPORT_SCHEDULER_MODE = _env('REPORT_SCHEDULER_MODE', 'embedded').lower()

    KINGBASE_CONFIG = KINGBASE_CONFIG

    MODEL_STORAGE = {
        'model_dir': os.path.join(BASE_DIR, 'saved_models'),
        'scaler_dir': os.path.join(BASE_DIR, 'saved_scalers'),
        'metrics_dir': os.path.join(BASE_DIR, 'saved_metrics')
    }

    AUTOSCRIPT_BASE_DIR = os.path.join(BASE_DIR, 'auto_scripts', 'scripts')
    SCRIPT_PATHS = {
        'short': os.path.join(AUTOSCRIPT_BASE_DIR, 'short', 'auto_pre_train.py'),
        'medium': os.path.join(AUTOSCRIPT_BASE_DIR, 'middle', 'auto_pre_train.py'),
        'supershort_train': os.path.join(AUTOSCRIPT_BASE_DIR, 'supershort', 'train_supershort.py'),
        'supershort_predict': os.path.join(AUTOSCRIPT_BASE_DIR, 'supershort', 'predict_supershort.py'),
        'middle_merge': os.path.join(AUTOSCRIPT_BASE_DIR, 'middle', 'run_auto_predict.py'),
    }

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

    REDIS_HOST = _env('REDIS_HOST', 'localhost')
    REDIS_PORT = _env('REDIS_PORT', '6379')
    REDIS_PASSWORD = _env('REDIS_PASSWORD', '')
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    API_BASE_URL = _env('API_BASE_URL', 'http://localhost:5000')

    SECRET_KEY = _env('SECRET_KEY', '')
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is required")

    SQLALCHEMY_DATABASE_URI = f"postgresql+kingbase://{DB_USER}:***@{KINGBASE_CONFIG['host']}:{KINGBASE_CONFIG['port']}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = _env('FLASK_DEBUG', 'True').lower() == 'true'
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = 1800
