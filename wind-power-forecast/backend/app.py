# 纭繚鍦ㄧ涓€鏃堕棿杩涜gevent monkey patch
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
# 瀵煎叆JWT鎵╁睍
from flask_jwt_extended import JWTManager
from common.api_response import success

# 鍔犺浇鐜鍙橀噺
load_dotenv()

# 妫€鏌ユ槸鍚﹀湪Docker鐜涓繍琛?
def is_running_in_docker():
    try:
        with open('/proc/1/cgroup', 'r') as f:
            return any('docker' in line for line in f)
    except:
        return False

# 濡傛灉鍦ㄦ湰鍦扮幆澧冭繍琛屼笖鏈缃暟鎹簱杩炴帴淇℃伅锛屽垯璁剧疆涓烘湰鍦癉ocker杩炴帴
if not is_running_in_docker():
    # 浠呭湪鏈缃幆澧冨彉閲忔椂璁剧疆榛樿鍊?
    if not os.environ.get('DB_HOST'):
        os.environ['DB_HOST'] = 'localhost'  # 鎴朌ocker瀹瑰櫒鐨処P
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
# 瀵煎叆浼氳瘽绠＄悊妯″潡鍜岃繛鎺ヤ腑闂翠欢
from db_session import get_db, db_session
from connection_middleware import register_middleware

app = Flask(__name__, static_folder='./static')
app.config.from_object(Config)
METRICS_ENABLED = os.environ.get("METRICS_ENABLED", "false").lower() == "true"

# --- JWT閰嶇疆 ---
# 璁剧疆JWT瀵嗛挜锛屼紭鍏堜粠鐜鍙橀噺鑾峰彇
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "wind-power-forecast-secret-key")
# 璁剧疆浠ょ墝杩囨湡鏃堕棿锛?2灏忔椂锛?
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
# 鍒濆鍖朖WTManager
jwt = JWTManager(app)
# --- JWT閰嶇疆缁撴潫 ---

# 閰嶇疆 CORS锛屽厑璁告墍鏈夎法鍩熻姹?
CORS(app, resources={r"/*": {
    "origins": "*",  # 鍏佽鎵€鏈夋潵婧?
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
    "expose_headers": ["Content-Type", "Content-Length", "Authorization", "Accept", "X-Requested-With", "Origin"],
    "supports_credentials": False,  # 鏀逛负False锛屽洜涓烘垜浠笉浣跨敤鍑瘉
    "max_age": 86400  # 棰勬璇锋眰缁撴灉缂撳瓨24灏忔椂
}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# 閰嶇疆鏃ュ織
configure_logging(app, socketio)

# 娉ㄥ唽鏁版嵁搴撹繛鎺ヤ腑闂翠欢
register_middleware(app)

# 鍒濆鍖栨寚鏍囨敹闆嗗櫒
if METRICS_ENABLED:
    try:
        from utils.metrics import init_metrics
        init_metrics()
        app.logger.info("Metrics collector initialized")
    except Exception as e:
        app.logger.error(f"Metrics collector init failed: {str(e)}")
else:
    app.logger.info("Metrics collector disabled by METRICS_ENABLED=false")

# 娉ㄥ唽钃濆浘
from routes.upload import upload_bp
from routes.download import download_bp
from routes.autotask import autotask_bp
from routes.actual_power_router import actual_power_bp
from routes.prediction2database import prediction2database_bp
from routes.power_compare import bp as power_compare_bp
from routes.auth import auth_bp  # 瀵煎叆璁よ瘉钃濆浘
from routes.user import user_bp  # 瀵煎叆鐢ㄦ埛璺敱钃濆浘
from routes.example_route import example_bp  # 瀵煎叆绀轰緥璺敱
# 鏂板锛氬鍏ョ壒寰佷笂浼犺摑鍥?
from routes.feature_upload import feature_upload_bp
# 鏂板锛氬鍏ョ墿鐞嗕豢鐪熻矾鐢?
from routes.physical_simulation_router import physical_simulation_bp
# 鏂板锛氬鍏ョ郴缁熶俊鎭矾鐢?
from routes.system_info_router import system_info_bp
# 鏂板锛氬鍏ヤ笂鎶ョ鐞嗚矾鐢?
from routes.report_management_router import report_management_bp
# 鏂板锛氬鍏ユ皵璞℃暟鎹媺鍙栬矾鐢?
from routes.weather_fetch_router import weather_fetch_bp
# 鏂板锛氬鍏ヨ繍钀ユ暟鎹笂浼犺矾鐢?
from routes.operational_data_upload import operational_data_upload_bp
# 鏂板锛氬鍏ュ満绔欑鐞嗚矾鐢?
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
# v1 auth namespace (compat bridge to same handlers)
app.register_blueprint(auth_bp, url_prefix='/api/v1/auth', name='auth_v1')
app.register_blueprint(user_bp, url_prefix='/api/user')  # 娉ㄥ唽鐢ㄦ埛璺敱钃濆浘锛屼娇鐢?/api/user 鍓嶇紑
app.register_blueprint(example_bp, url_prefix='/api/example')  # 娉ㄥ唽绀轰緥璺敱
# 鏂板锛氭敞鍐岀壒寰佷笂浼犺摑鍥?
app.register_blueprint(feature_upload_bp)
# 鏂板锛氭敞鍐岀墿鐞嗕豢鐪熻矾鐢?
app.register_blueprint(physical_simulation_bp)
# 鏂板锛氭敞鍐岀郴缁熶俊鎭矾鐢?
app.register_blueprint(system_info_bp, url_prefix='/system')
# 鏂板锛氭敞鍐屼笂鎶ョ鐞嗚矾鐢?
app.register_blueprint(report_management_bp, url_prefix='/report')
# 鏂板锛氭敞鍐屾皵璞℃暟鎹媺鍙栬矾鐢?
app.register_blueprint(weather_fetch_bp, url_prefix='/weather-fetch')
# 鏂板锛氭敞鍐岃繍钀ユ暟鎹笂浼犺矾鐢?
app.register_blueprint(operational_data_upload_bp, url_prefix='/operational')
# 鏂板锛氭敞鍐屽満绔欑鐞嗚矾鐢?
app.register_blueprint(farm_management_bp, url_prefix='/api')
app.register_blueprint(v1_compat_bp)  # compat bridge

# 鏂板锛氬垵濮嬪寲姘旇薄鏁版嵁鎷夊彇璋冨害鍣?
try:
    from services.scheduler_service import init_scheduler
    import os
    # 鑾峰彇鏁版嵁搴揢RL
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = os.environ.get('DB_PORT', '54321')
    db_user = os.environ.get('DB_USER', 'system')
    db_password = os.environ.get('DB_PASSWORD', '12345678ab')
    db_name = os.environ.get('DB_NAME', 'windpower')
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    init_scheduler(database_url)
    print("鉁?姘旇薄鏁版嵁鎷夊彇璋冨害鍣ㄥ垵濮嬪寲鎴愬姛")
except Exception as e:
    print(f"璀﹀憡: 姘旇薄鏁版嵁鎷夊彇璋冨害鍣ㄥ垵濮嬪寲澶辫触: {e}")

# 娣诲姞JWT閿欒澶勭悊
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({"message": "令牌已过期，请重新登录"}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({"message": "无效令牌"}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({"message": "缂哄皯璁よ瘉浠ょ墝"}), 401

# 娣诲姞鍋ュ悍妫€鏌ョ鐐?
def _build_health_status():
    health_status = {
        "status": "ok",
        "database": "unknown",
        "minio": "unknown"
    }
    
    # 妫€鏌ユ暟鎹簱杩炴帴
    try:
        with db_session() as db:
            db.execute(text("SELECT 1"))
            health_status["database"] = "ok"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
    
    # 妫€鏌inIO杩炴帴
    try:
        if minio_client is not None:
            # 灏濊瘯鍒楀嚭瀛樺偍妗?
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

    # 濡傛灉浠讳綍鏈嶅姟涓嶅彲鐢紝杩斿洖503鐘舵€佺爜
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

# 娣诲姞Prometheus鎸囨爣鎺ュ彛
@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus鎸囨爣鎺ュ彛"""
    if not METRICS_ENABLED:
        return jsonify({"message": "metrics disabled"}), 404
    try:
        from utils.metrics import get_metrics
        metrics_data = get_metrics()
        return metrics_data, 200, {'Content-Type': 'text/plain; version=0.0.4'}
    except Exception as e:
        current_app.logger.error(f"鑾峰彇鎸囨爣鏁版嵁澶辫触: {str(e)}")
        return jsonify({"error": "鑾峰彇鎸囨爣鏁版嵁澶辫触"}), 500

# 娣诲姞鍏ㄥ眬 OPTIONS 璇锋眰澶勭悊鍣?
@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 200

# 鍒濆鍖栨暟鎹簱鍜屽瓨鍌ㄦ《
def initialize():
    with app.app_context():
        # 鍒涘缓鏁版嵁搴撹〃
        if engine is not None:
            try:
                Base.metadata.create_all(bind=engine)
                print("鉁?鏁版嵁搴撹〃鍒涘缓瀹屾垚")
                
                # 鍒濆鍖栫敤鎴峰拰瑙掕壊
                try:
                    from init_users import init_users_and_roles
                    init_users_and_roles()
                    print("初始化用户和角色完成")
                except Exception as e:
                    print(f"璀﹀憡: 鍒濆鐢ㄦ埛鍒涘缓澶辫触: {e}")
                    
            except Exception as e:
                print(f"璀﹀憡: 鏁版嵁搴撹〃鍒涘缓澶辫触: {e}")
        else:
            print("璀﹀憡: 鏁版嵁搴撳紩鎿庝笉鍙敤锛岃烦杩囪〃鍒涘缓")
        
        # 鍒濆鍖朚inIO瀛樺偍妗讹紙鏇存柊涓烘柊鐨勯厤缃粨鏋勶級
        if minio_client is not None:
            try:
                required_buckets = list(MINIO_CONFIG["buckets"].values())
                existing_buckets = [b.name for b in minio_client.list_buckets()]
                
                for bucket in required_buckets:
                    if bucket not in existing_buckets:
                        minio_client.make_bucket(bucket)
                        print(f"鉁?鎴愬姛鍒涘缓瀛樺偍妗? {bucket}")
                    else:
                        print(f"鉁?瀛樺偍妗跺凡瀛樺湪: {bucket}")
            except Exception as e:
                print(f"璀﹀憡: MinIO瀛樺偍妗跺垵濮嬪寲澶辫触: {e}")
        else:
            print("璀﹀憡: MinIO瀹㈡埛绔笉鍙敤锛岃烦杩囧瓨鍌ㄦ《鍒涘缓")

# 鎵ц鍒濆鍖?
initialize()

@app.route('/upload_train_csv', methods=['POST'])
def upload_train_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 鏂板鏂囦欢绫诲瀷鏍￠獙锛堟潵鑷唬鐮?锛?
    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    # 鐢熸垚鍞竴鏂囦欢ID锛堟潵鑷唬鐮?锛?
    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        # 鏂板鏈湴淇濆瓨閫昏緫锛堟潵鑷唬鐮?锛?
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])
        
        # 閲嶇疆鏂囦欢鎸囬拡浠ヤ究鍚庣画涓婁紶
        file.stream.seek(0)

        # 鏍规嵁鏁版嵁绫诲瀷閫夋嫨瀛樺偍璺緞
        data_type = request.form.get('data_type', 'traincsv')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 鏇存柊鍚庣殑瀛樺偍妗跺紩鐢?
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        # 楠岃瘉MinIO涓婁紶
        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 鏇存柊鍚庣殑瀛樺偍妗跺紩鐢?
            file_path
        )
        print(f"MinIO验证 - 文件大小: {obj_info.size}")

        # 鏁版嵁搴撴搷浣?
        with db_session() as db:
            # 鐢熸垚鏈湴璺緞锛堢粍鍚堜唬鐮?鍜屼唬鐮?鐨勫弬鏁帮級
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
                "file_id": file_id  # 杩斿洖鏈湴淇濆瓨鐨処D
            })
            
    except Exception as e:
        print(f"全局异常: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/upload_predict_csv', methods=['POST'])
def upload_predict_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 鏂板鏂囦欢绫诲瀷鏍￠獙锛堟潵鑷唬鐮?锛?
    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    # 鐢熸垚鍞竴鏂囦欢ID锛堟潵鑷唬鐮?锛?
    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        # 鏂板鏈湴淇濆瓨閫昏緫锛堟潵鑷唬鐮?锛?
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])
        
        # 閲嶇疆鏂囦欢鎸囬拡浠ヤ究鍚庣画涓婁紶
        file.stream.seek(0)

        # 鏍规嵁鏁版嵁绫诲瀷閫夋嫨瀛樺偍璺緞
        data_type = request.form.get('data_type', 'predictcsv')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 鏇存柊鍚庣殑瀛樺偍妗跺紩鐢?
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        # 楠岃瘉MinIO涓婁紶
        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 鏇存柊鍚庣殑瀛樺偍妗跺紩鐢?
            file_path
        )
        print(f"MinIO验证 - 文件大小: {obj_info.size}")

        # 鏁版嵁搴撴搷浣?
        with db_session() as db:
            # 鐢熸垚鏈湴璺緞锛堢粍鍚堜唬鐮?鍜屼唬鐮?鐨勫弬鏁帮級
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
                "file_id": file_id  # 杩斿洖鏈湴淇濆瓨鐨処D
            })
            
    except Exception as e:
        print(f"全局异常: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/upload_model', methods=['POST'])
def upload_model():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 鏂板鏂囦欢绫诲瀷鏍￠獙锛堟潵鑷唬鐮?锛?
    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    # 鐢熸垚鍞竴鏂囦欢ID锛堟潵鑷唬鐮?锛?
    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        # 鏂板鏈湴淇濆瓨閫昏緫锛堟潵鑷唬鐮?锛?
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])
        
        # 閲嶇疆鏂囦欢鎸囬拡浠ヤ究鍚庣画涓婁紶
        file.stream.seek(0)

        # 鏍规嵁鏁版嵁绫诲瀷閫夋嫨瀛樺偍璺緞
        data_type = request.form.get('data_type', 'model')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 鏇存柊鍚庣殑瀛樺偍妗跺紩鐢?
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        # 楠岃瘉MinIO涓婁紶
        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 鏇存柊鍚庣殑瀛樺偍妗跺紩鐢?
            file_path
        )
        print(f"MinIO验证 - 文件大小: {obj_info.size}")

        # 鏁版嵁搴撴搷浣?
        with db_session() as db:
            # 鐢熸垚鏈湴璺緞锛堢粍鍚堜唬鐮?鍜屼唬鐮?鐨勫弬鏁帮級
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
                "file_id": file_id  # 杩斿洖鏈湴淇濆瓨鐨処D
            })
            
    except Exception as e:
        print(f"全局异常: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/upload_scaler', methods=['POST'])
def upload_scaler():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 鏂板鏂囦欢绫诲瀷鏍￠獙锛堟潵鑷唬鐮?锛?
    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    # 鐢熸垚鍞竴鏂囦欢ID锛堟潵鑷唬鐮?锛?
    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        # 鏂板鏈湴淇濆瓨閫昏緫锛堟潵鑷唬鐮?锛?
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])
        
        # 閲嶇疆鏂囦欢鎸囬拡浠ヤ究鍚庣画涓婁紶
        file.stream.seek(0)

        # 鏍规嵁鏁版嵁绫诲瀷閫夋嫨瀛樺偍璺緞
        data_type = request.form.get('data_type', 'scaler')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 鏇存柊鍚庣殑瀛樺偍妗跺紩鐢?
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        # 楠岃瘉MinIO涓婁紶
        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 鏇存柊鍚庣殑瀛樺偍妗跺紩鐢?
            file_path
        )
        print(f"MinIO验证 - 文件大小: {obj_info.size}")

        # 鏁版嵁搴撴搷浣?
        with db_session() as db:
            # 鐢熸垚鏈湴璺緞锛堢粍鍚堜唬鐮?鍜屼唬鐮?鐨勫弬鏁帮級
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
                "file_id": file_id  # 杩斿洖鏈湴淇濆瓨鐨処D
            })
            
    except Exception as e:
        print(f"全局异常: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large (max 500MB)'}), 413

@socketio.on('connect')
def handle_connect():
    app.logger.info("鎴愬姛杩炴帴鏈嶅姟鍣紒")
    socketio.emit('response', {'message': '连接成功'})

@socketio.on('disconnect')
def handle_disconnect():
    app.logger.info("与服务器断开连接")

if __name__ == '__main__':
    app_host = str(os.environ.get('APP_HOST', '0.0.0.0')).strip()
    app_port = int(str(os.environ.get('APP_PORT', '5000')).strip())
    app_debug = str(os.environ.get('APP_DEBUG', 'true')).strip().lower() in ('1', 'true', 'yes', 'on')
    socketio.run(app, host=app_host, port=app_port, debug=app_debug)
