
import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, request, jsonify, current_app
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv
from database_config import Base, engine, minio_client
from config import Config, MINIO_CONFIG
from s3_error import S3Error
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
    except:
        return False

if not is_running_in_docker():
    if not os.environ.get('DB_HOST'):
        os.environ['DB_HOST'] = 'localhost'
    if not os.environ.get('DB_PORT'):
        os.environ['DB_PORT'] = '54321'
    if not os.environ.get('DB_USER'):
        os.environ['DB_USER'] = 'system'
    if not os.environ.get('DB_PASSWORD'):
        os.environ['DB_PASSWORD'] = '12345678ab'
    if not os.environ.get('DB_NAME'):
        os.environ['DB_NAME'] = 'windpower'
    if not os.environ.get('MINIO_ENDPOINT'):
        os.environ['MINIO_ENDPOINT'] = 'localhost'
    if not os.environ.get('MINIO_PORT'):
        os.environ['MINIO_PORT'] = '9900'

from logging_config import configure_logging
from db_session import get_db, db_session
from connection_middleware import register_middleware

app = Flask(__name__, static_folder='./static')
app.config.from_object(Config)
METRICS_ENABLED = os.environ.get("METRICS_ENABLED", "false").lower() == "true"

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "wind-power-forecast-secret-key")
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

try:
    from services.scheduler_service import init_scheduler
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = os.environ.get('DB_PORT', '54321')
    db_user = os.environ.get('DB_USER', 'system')
    db_password = os.environ.get('DB_PASSWORD', '12345678ab')
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
        "database": "unknown",
        "minio": "unknown"
    }
    
    try:
        with db_session() as db:
            db.execute(text("SELECT 1"))
            health_status["database"] = "ok"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
    
    try:
        if minio_client is not None:
            minio_client.list_buckets()
            health_status["minio"] = "ok"
        else:
            health_status["minio"] = "unavailable"
    except Exception as e:
        health_status["minio"] = f"error: {str(e)}"
    
    return health_status


@app.route('/health', methods=['GET'])
def health_check():
    health_status = _build_health_status()

    if "error" in health_status["database"] or "error" in health_status["minio"] or \
       health_status["database"] == "unavailable" or health_status["minio"] == "unavailable":
        return jsonify(health_status), 503
    
    return jsonify(health_status)


@app.route('/api/v1/health', methods=['GET'])
def health_check_v1():
    health_status = _build_health_status()
    is_healthy = not (
        "error" in health_status["database"]
        or "error" in health_status["minio"]
        or health_status["database"] == "unavailable"
        or health_status["minio"] == "unavailable"
    )
    status_code = 200 if is_healthy else 503
    payload = success(data=health_status, message="ok" if is_healthy else "degraded")
    return jsonify(payload), status_code

@app.route('/metrics', methods=['GET'])
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

        if minio_client is not None:
            try:
                required_buckets = list(MINIO_CONFIG["buckets"].values())
                existing_buckets = [b.name for b in minio_client.list_buckets()]

                for bucket in required_buckets:
                    if bucket not in existing_buckets:
                        minio_client.make_bucket(bucket)
                        print(f"已创建存储桶: {bucket}")
                    else:
                        print(f"存储桶已存在: {bucket}")
            except Exception as e:
                print(f"MinIO 初始化失败: {e}")
        else:
            print("MinIO 客户端不可用，跳过存储桶初始化")

initialize()

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
        file.stream.seek(0)

        data_type = request.form.get('data_type', 'traincsv')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],
            file_path
        )
        print("文件已上传至 MinIO")

        with db_session() as db:
            ext = os.path.splitext(file.filename)[1]
            local_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'], 
                f"{file_id}{ext}"
            )

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
        file.stream.seek(0)

        data_type = request.form.get('data_type', 'predictcsv')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],
            file_path
        )
        print("文件已上传至 MinIO")

        with db_session() as db:
            ext = os.path.splitext(file.filename)[1]
            local_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'], 
                f"{file_id}{ext}"
            )

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
        file.stream.seek(0)

        data_type = request.form.get('data_type', 'model')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],
            file_path
        )
        print("文件已上传至 MinIO")

        with db_session() as db:
            ext = os.path.splitext(file.filename)[1]
            local_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'], 
                f"{file_id}{ext}"
            )

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
        file.stream.seek(0)

        data_type = request.form.get('data_type', 'scaler')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],
            file_path
        )
        print("文件已上传至 MinIO")

        with db_session() as db:
            ext = os.path.splitext(file.filename)[1]
            local_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'], 
                f"{file_id}{ext}"
            )

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
