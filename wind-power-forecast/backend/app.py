
import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, request, jsonify, current_app
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv
from database_config import Base, engine
from config import Config
from db_models import Dataset
from datetime import datetime,timedelta
from services.file_service import allowed_file, save_uploaded_file
import os
from db_session import db_session
from connection_middleware import register_middleware
from sqlalchemy import text
from flask_jwt_extended import JWTManager
from common.api_response import success

load_dotenv()

def is_running_in_docker():
    try:
        with open('/proc/1/cgroup', 'r') as f:
            return any('docker' in line for line in f)
    except (FileNotFoundError, PermissionError, OSError):
        return False

if not is_running_in_docker():
    if not os.environ.get('DB_HOST'):
        os.environ['DB_HOST'] = 'localhost'
    if not os.environ.get('DB_PORT'):
        os.environ['DB_PORT'] = '54321'
    if not os.environ.get('DB_USER'):
        os.environ['DB_USER'] = 'system'
    if not os.environ.get('DB_PASSWORD'):
        raise RuntimeError('DB_PASSWORD not set. Create a .env file or set the environment variable.')
    if not os.environ.get('DB_NAME'):
        os.environ['DB_NAME'] = 'windpower'

from logging_config import configure_logging
from db_session import get_db, db_session
from connection_middleware import register_middleware

app = Flask(__name__, static_folder='./static')
app.config.from_object(Config)
METRICS_ENABLED = os.environ.get("METRICS_ENABLED", "false").lower() == "true"

jwt_secret = os.environ.get("JWT_SECRET_KEY") or os.environ.get("SECRET_KEY")
if not jwt_secret:
    raise RuntimeError('JWT_SECRET_KEY or SECRET_KEY not set. Create a .env file or set the environment variable.')
app.config["JWT_SECRET_KEY"] = jwt_secret
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
jwt = JWTManager(app)

CORS(app, resources={r"/*": {
    "origins": "*",
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
    "expose_headers": ["Content-Type", "Content-Length", "Authorization", "Accept", "X-Requested-With", "Origin"],
    "supports_credentials": False,
    "max_age": 86400
}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

configure_logging(app, socketio)

register_middleware(app)

if METRICS_ENABLED:
    try:
        from utils.metrics import init_metrics
        init_metrics()
        app.logger.info("Metrics collector initialized")
    except Exception as e:
        app.logger.error(f"Metrics collector init failed: {str(e)}")
else:
    app.logger.info("Metrics collector disabled by METRICS_ENABLED=false")

from routes.upload import upload_bp
from routes.download import download_bp
from routes.autotask import autotask_bp
from routes.actual_power_router import actual_power_bp
from routes.prediction2database import prediction2database_bp
from routes.power_compare import bp as power_compare_bp
from routes.auth import auth_bp
from routes.auth_extensions import auth_extensions_bp
from routes.user import user_bp
from routes.example_route import example_bp
from routes.feature_upload import feature_upload_bp
from routes.physical_simulation_router import physical_simulation_bp
from routes.system_info_router import system_info_bp
from routes.system_settings_router import system_settings_bp
from routes.alarm_router import alarm_bp
from routes.report_management_router import report_management_bp
from routes.weather_fetch_router import weather_fetch_bp
from routes.operational_data_upload import operational_data_upload_bp
from routes.farm_management import farm_management_bp
from routes.v1_compat import v1_compat_bp
from routes.ecmwf_data_router import ecmwf_data_bp
from routes.ecmwf_grid_router import ecmwf_grid_bp
from routes.autopredict import autopredict_bp
from routes.extreme_weather_router import extreme_weather_bp
from routes.scada_connection import scada_connection_bp
from routes.etext_pipeline_router import etext_pipeline_bp

# app.register_blueprint(upload_bp, url_prefix='/')
app.register_blueprint(download_bp, url_prefix='/')
app.register_blueprint(autotask_bp, url_prefix='/')
app.register_blueprint(actual_power_bp)
app.register_blueprint(prediction2database_bp)
app.register_blueprint(power_compare_bp)
# Legacy auth namespace (kept for compatibility)
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(auth_extensions_bp, url_prefix='/auth')
# v1 auth namespace (compat bridge to same handlers)
app.register_blueprint(auth_bp, url_prefix='/api/v1/auth', name='auth_v1')
app.register_blueprint(auth_extensions_bp, url_prefix='/api/v1/auth', name='auth_extensions_v1')
app.register_blueprint(user_bp, url_prefix='/api/user')
app.register_blueprint(example_bp, url_prefix='/api/example')
app.register_blueprint(feature_upload_bp)
app.register_blueprint(physical_simulation_bp)
app.register_blueprint(system_info_bp, url_prefix='/system')
app.register_blueprint(system_settings_bp, url_prefix='/system')
app.register_blueprint(alarm_bp, url_prefix='/system')
app.register_blueprint(alarm_bp, url_prefix='/api/v1/system', name='alarm_v1')
app.register_blueprint(report_management_bp, url_prefix='/report')
app.register_blueprint(weather_fetch_bp, url_prefix='/weather-fetch')
app.register_blueprint(operational_data_upload_bp, url_prefix='/operational')
app.register_blueprint(farm_management_bp, url_prefix='/api')
app.register_blueprint(v1_compat_bp)  # compat bridge
app.register_blueprint(ecmwf_data_bp)  # ECMWF气象数据API
app.register_blueprint(ecmwf_grid_bp)  # ECMWF格点数据API
app.register_blueprint(autopredict_bp, url_prefix='/api')  # 自动预测调度API
app.register_blueprint(extreme_weather_bp)  # 极端天气检测API
app.register_blueprint(scada_connection_bp)  # SCADA connection management API
app.register_blueprint(etext_pipeline_bp)  # E text pipeline config & trigger

try:
    from services.scheduler_service import init_scheduler
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = os.environ.get('DB_PORT', '54321')
    db_user = os.environ.get('DB_USER', 'system')
    db_password = os.environ.get('DB_PASSWORD')
    if not db_password:
        raise RuntimeError('DB_PASSWORD not set for scheduler.')
    db_name = os.environ.get('DB_NAME', 'windpower')
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    init_scheduler(database_url)
    print("调度器初始化成功")
except Exception as e:
    print(f"调度器初始化失败: {e}")

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({"message": "登录已过期"}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({"message": "令牌无效"}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({"message": "缺少认证令牌"}), 401

def _build_health_status():
    health_status = {
        "status": "ok",
        "database": "unknown"
    }

    try:
        with db_session() as db:
            db.execute(text("SELECT 1"))
            health_status["database"] = "ok"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"

    return health_status


@app.route('/health', methods=['GET'])
def health_check():
    health_status = _build_health_status()

    if "error" in health_status["database"] or health_status["database"] == "unavailable":
        return jsonify(health_status), 503
    
    return jsonify(health_status)


@app.route('/api/v1/health', methods=['GET'])
def health_check_v1():
    health_status = _build_health_status()
    is_healthy = not (
        "error" in health_status["database"]
        or health_status["database"] == "unavailable"
    )
    status_code = 200 if is_healthy else 503
    payload = success(data=health_status, message="ok" if is_healthy else "degraded")
    return jsonify(payload), status_code

@app.route('/api/v1/public/overview', methods=['GET'])
def public_overview():
    """登录页公开概览数据（无需认证）"""
    try:
        from db_session import db_session
        from db_models import WindFarm
        from sqlalchemy import text

        with db_session() as db:
            farm_count = db.query(WindFarm).filter(WindFarm.is_active == True).count()

            # 获取最新实际功率
            latest_power = 0.0
            try:
                result = db.execute(text(
                    "SELECT COALESCE(SUM(wp_true), 0) FROM actual_power "
                    "WHERE timestamp = (SELECT MAX(timestamp) FROM actual_power)"
                ))
                row = result.fetchone()
                latest_power = float(row[0]) if row and row[0] else 0.0
            except Exception:
                pass

            # 获取今日预测准确率
            accuracy = None
            try:
                result = db.execute(text("""
                    SELECT 1 - (
                        AVG(ABS(s.wp_pred - a.wp_true)::float) / NULLIF(AVG(ABS(a.wp_true)::float), 0)
                    ) as accuracy
                    FROM shortl_power s
                    JOIN actual_power a
                      ON a.farm_code = s.farm_code
                     AND a.timestamp = s.timestamp
                    WHERE s.timestamp >= CURRENT_DATE
                      AND s.wp_pred IS NOT NULL AND a.wp_true IS NOT NULL
                """))
                row = result.fetchone()
                if row and row[0] is not None:
                    accuracy = round(float(row[0]) * 100, 1)
            except Exception:
                pass

        return jsonify(success(data={
            'farm_count': farm_count,
            'total_power': round(latest_power, 1),
            'accuracy': accuracy
        }))
    except Exception as e:
        return jsonify(success(data={
            'farm_count': 0,
            'total_power': 0,
            'accuracy': None
        }))
def metrics():
    """Prometheus 指标接口"""
    if not METRICS_ENABLED:
        return jsonify({"message": "metrics disabled"}), 404
    try:
        from utils.metrics import get_metrics
        metrics_data = get_metrics()
        return metrics_data, 200, {'Content-Type': 'text/plain; version=0.0.4'}
    except Exception as e:
        current_app.logger.error(f"获取指标数据失败: {str(e)}")
        return jsonify({"error": "获取指标数据失败"}), 500

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 200

def initialize():
    with app.app_context():
        if engine is not None:
            try:
                Base.metadata.create_all(bind=engine)
                from db_models import (
                    AlarmNotificationPolicy,
                    AlarmRecord,
                    AlarmRule,
                    DataQualityMarker,
                    FarmProfileConfig,
                    ManualInterventionVersion,
                    OperationAuditLog,
                    ReportConfigMeta,
                    SystemSetting,
                    UserProfileMeta
                )

                runtime_tables = [
                    AlarmRecord.__table__,
                    AlarmRule.__table__,
                    AlarmNotificationPolicy.__table__,
                    DataQualityMarker.__table__,
                    UserProfileMeta.__table__,
                    OperationAuditLog.__table__,
                    SystemSetting.__table__,
                    ManualInterventionVersion.__table__,
                    FarmProfileConfig.__table__,
                    ReportConfigMeta.__table__
                ]

                for table in runtime_tables:
                    table.create(bind=engine, checkfirst=True)
                print("数据库表初始化成功")
                try:
                    from init_users import init_users_and_roles
                    init_users_and_roles()
                    print("默认用户与角色初始化成功")
                except Exception as e:
                    print(f"默认用户与角色初始化失败: {e}")
            except Exception as e:
                print(f"数据库初始化失败: {e}")
        else:
            print("数据库引擎不可用，跳过数据库初始化")

initialize()

# SCADA连接自动恢复：后端启动时重新启动之前运行中的Worker
try:
    from services.scada_manager import get_scada_manager
    _scada_mgr = get_scada_manager()
    _recovered = _scada_mgr.recover_on_startup()
    if _recovered:
        print(f"SCADA自动恢复: 重新启动 {_recovered} 个连接")
except Exception as e:
    print(f"SCADA自动恢复失败: {e}")

@app.route('/upload_train_csv', methods=['POST'])
def upload_train_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])

        data_type = request.form.get('data_type', 'traincsv')
        ext = os.path.splitext(file.filename)[1]
        local_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            f"{file_id}{ext}"
        )
        file_path = local_path

        with db_session() as db:

            db_dataset = Dataset(
                file_id=file_id,
                filename=file.filename,
                file_path=file_path,
                upload_time=datetime.now(),
                file_size=file.content_length,
                file_type='traincsv',
                local_path=local_path,
                description=request.form.get('description', ''),
                data_type=data_type,
                wind_farm=request.form.get('wind_farm', 'unknown')
            )
            
            db.add(db_dataset)
            db.commit()
            return jsonify({
                "message": "File uploaded successfully",
                "dataset_id": db_dataset.id,
                "file_id": file_id
            })
            
    except Exception as e:
        print(f"上传 traincsv 失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/upload_predict_csv', methods=['POST'])
def upload_predict_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])

        data_type = request.form.get('data_type', 'predictcsv')
        ext = os.path.splitext(file.filename)[1]
        local_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            f"{file_id}{ext}"
        )
        file_path = local_path

        with db_session() as db:

            db_dataset = Dataset(
                file_id=file_id,
                filename=file.filename,
                file_path=file_path,
                upload_time=datetime.now(),
                file_size=file.content_length,
                file_type='predictcsv',
                local_path=local_path,
                description=request.form.get('description', ''),
                data_type=data_type,
                wind_farm=request.form.get('wind_farm', 'unknown')
            )
            
            db.add(db_dataset)
            db.commit()
            return jsonify({
                "message": "File uploaded successfully",
                "dataset_id": db_dataset.id,
                "file_id": file_id
            })
            
    except Exception as e:
        print(f"上传 predictcsv 失败: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/upload_model', methods=['POST'])
def upload_model():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])

        data_type = request.form.get('data_type', 'model')
        ext = os.path.splitext(file.filename)[1]
        local_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            f"{file_id}{ext}"
        )
        file_path = local_path

        with db_session() as db:

            db_dataset = Dataset(
                file_id=file_id,
                filename=file.filename,
                file_path=file_path,
                upload_time=datetime.now(),
                file_size=file.content_length,
                file_type='model',
                local_path=local_path,
                description=request.form.get('description', ''),
                data_type=data_type,
                wind_farm=request.form.get('wind_farm', 'unknown')
            )
            
            db.add(db_dataset)
            db.commit()
            return jsonify({
                "message": "File uploaded successfully",
                "dataset_id": db_dataset.id,
                "file_id": file_id
            })
            
    except Exception as e:
        print(f"上传 model 失败: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/upload_scaler', methods=['POST'])
def upload_scaler():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])

        data_type = request.form.get('data_type', 'scaler')
        ext = os.path.splitext(file.filename)[1]
        local_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            f"{file_id}{ext}"
        )
        file_path = local_path

        with db_session() as db:

            db_dataset = Dataset(
                file_id=file_id,
                filename=file.filename,
                file_path=file_path,
                upload_time=datetime.now(),
                file_size=file.content_length,
                file_type='scaler',
                local_path=local_path,
                description=request.form.get('description', ''),
                data_type=data_type,
                wind_farm=request.form.get('wind_farm', 'unknown')
            )
            
            db.add(db_dataset)
            db.commit()
            return jsonify({
                "message": "File uploaded successfully",
                "dataset_id": db_dataset.id,
                "file_id": file_id
            })
            
    except Exception as e:
        print(f"上传 scaler 失败: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large (max 500MB)'}), 413

@socketio.on('connect')
def handle_connect():
    app.logger.info("客户端已连接")
    socketio.emit('response', {'message': '连接成功'})

@socketio.on('disconnect')
def handle_disconnect():
    app.logger.info("客户端已断开")

if __name__ == '__main__':
    app_host = str(os.environ.get('APP_HOST', '0.0.0.0')).strip()
    app_port = int(str(os.environ.get('APP_PORT', '5000')).strip())
    app_debug = str(os.environ.get('APP_DEBUG', 'true')).strip().lower() in ('1', 'true', 'yes', 'on')
    socketio.run(app, host=app_host, port=app_port, debug=app_debug)
