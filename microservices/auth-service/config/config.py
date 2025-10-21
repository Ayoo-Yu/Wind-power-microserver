import os
from datetime import timedelta

class Config:
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database Configuration
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'postgresql://auth_user:auth_password@postgres-auth:5432/windpower_auth'

    # Redis Configuration
    REDIS_HOST = os.environ.get('REDIS_HOST') or 'redis-master'
    REDIS_PORT = int(os.environ.get('REDIS_PORT') or 6379)
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD') or 'redis123'
    REDIS_DB = int(os.environ.get('REDIS_DB') or 0)

    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-string'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'

    # Service Configuration
    SERVICE_NAME = 'auth-service'
    SERVICE_PORT = int(os.environ.get('SERVICE_PORT') or 5001)
    SERVICE_HOST = os.environ.get('SERVICE_HOST') or '0.0.0.0'

    # Consul Configuration
    CONSUL_HOST = os.environ.get('CONSUL_HOST') or 'consul-server'
    CONSUL_PORT = int(os.environ.get('CONSUL_PORT') or 8500)

    # Rate Limiting
    RATELIMIT_STORAGE_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    RATELIMIT_DEFAULT = "100/hour"

    # Security Configuration
    BCRYPT_LOG_ROUNDS = 12
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_ATTEMPT_TIMEOUT = 300  # 5 minutes

    # Session Configuration
    SESSION_TYPE = 'redis'
    SESSION_REDIS = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # CORS Configuration
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS') or '*'
    CORS_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    CORS_HEADERS = ['Content-Type', 'Authorization']

    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Metrics Configuration
    METRICS_PORT = int(os.environ.get('METRICS_PORT') or 8001)

    # Two-Factor Authentication
    TOTP_ISSUER = 'WindPower Auth'
    TOTP_VALIDITY_WINDOW = 1

    # Password Policy
    MIN_PASSWORD_LENGTH = 8
    PASSWORD_COMPLEXITY = True

    # Audit Configuration
    AUDIT_ENABLED = True
    AUDIT_RETENTION_DAYS = 365

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = 'INFO'

class TestingConfig(Config):
    TESTING = True
    DATABASE_URL = 'sqlite:///:memory:'
    REDIS_DB = 1

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}