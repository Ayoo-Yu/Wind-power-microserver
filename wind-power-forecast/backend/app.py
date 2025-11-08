"""应用入口，使用工厂模式初始化。"""

from app_factory import create_app, socketio
import os


app = create_app()


if __name__ == "__main__":  # pragma: no cover - 手动运行
    host = os.environ.get("APP_HOST", "0.0.0.0")
    port = int(os.environ.get("APP_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    socketio.run(app, host=host, port=port, debug=debug)
# 确保在第一时间进行gevent monkey patch
import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, request, jsonify, current_app
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv
from database_config import Base, engine, minio_client
try:
    from .config import Config, MINIO_CONFIG
except ImportError:  # 在脚本模式下回退到绝对导入
    from config import Config, MINIO_CONFIG
from s3_error import S3Error
try:
    from .db_models import Dataset
except ImportError:  # 在脚本模式下回退到绝对导入
    from db_models import Dataset
from datetime import datetime,timedelta
from services.file_service import allowed_file, save_uploaded_file
import os
from db_session import db_session
from connection_middleware import register_middleware
from sqlalchemy import text
# 导入JWT扩展
from flask_jwt_extended import JWTManager

# 加载环境变量
load_dotenv()

# 检查是否在Docker环境中运行
def is_running_in_docker():
    try:
        with open('/proc/1/cgroup', 'r') as f:
            return any('docker' in line for line in f)
    except:
        return False

# 如果在本地环境运行且未设置数据库连接信息，则设置为本地Docker连接
if not is_running_in_docker():
    # 仅在未设置环境变量时设置默认值
    if not os.environ.get('DB_HOST'):
        os.environ['DB_HOST'] = 'localhost'  # 或Docker容器的IP
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
# 导入会话管理模块和连接中间件
from db_session import get_db, db_session
from connection_middleware import register_middleware

app = Flask(__name__, static_folder='./static')
app.config.from_object(Config)

# --- JWT配置 ---
# 设置JWT密钥，优先从环境变量获取
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "wind-power-forecast-secret-key")
# 设置令牌过期时间（12小时）
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
# 初始化JWTManager
jwt = JWTManager(app)
# --- JWT配置结束 ---

# 配置 CORS，允许所有跨域请求
CORS(app, resources={r"/*": {
    "origins": "*",  # 允许所有来源
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
    "expose_headers": ["Content-Type", "Content-Length", "Authorization", "Accept", "X-Requested-With", "Origin"],
    "supports_credentials": False,  # 改为False，因为我们不使用凭证
    "max_age": 86400  # 预检请求结果缓存24小时
}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# 配置日志
configure_logging(app, socketio)

# 注册数据库连接中间件
register_middleware(app)

# 注册蓝图
from routes.upload import upload_bp
from routes.modeltrain import modeltrain_bp
from routes.download import download_bp
from routes.predict import predict_bp
from routes.training import training_bp
from routes.predict import predict_bp
from routes.autotask import autotask_bp
from routes.actual_power_router import actual_power_bp
from routes.prediction2database import prediction2database_bp
from routes.power_compare import bp as power_compare_bp
from routes.auth import auth_bp  # 导入认证蓝图
from routes.user import user_bp  # 导入用户路由蓝图
from routes.example_route import example_bp  # 导入示例路由
# 新增：导入特征上传蓝图
from routes.feature_upload import feature_upload_bp
# 新增：导入物理仿真路由
from routes.physical_simulation_router import physical_simulation_bp
# 新增：导入系统信息路由
from routes.system_info_router import system_info_bp
# 新增：导入上报管理路由
from routes.report_management_router import report_management_bp
# 新增：导入气象数据拉取路由
from routes.weather_fetch_router import weather_fetch_bp
# 新增：导入运营数据上传路由
from routes.operational_data_upload import operational_data_upload_bp

# app.register_blueprint(upload_bp, url_prefix='/')
app.register_blueprint(modeltrain_bp, url_prefix='/')
app.register_blueprint(download_bp, url_prefix='/')
app.register_blueprint(predict_bp, url_prefix='/')
app.register_blueprint(training_bp, url_prefix='/')
app.register_blueprint(autotask_bp, url_prefix='/')
app.register_blueprint(actual_power_bp)
app.register_blueprint(prediction2database_bp)
app.register_blueprint(power_compare_bp)
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(user_bp, url_prefix='/api/user')  # 注册用户路由蓝图，使用 /api/user 前缀
app.register_blueprint(example_bp, url_prefix='/api/example')  # 注册示例路由
# 新增：注册特征上传蓝图
app.register_blueprint(feature_upload_bp)
# 新增：注册物理仿真路由
app.register_blueprint(physical_simulation_bp)
# 新增：注册系统信息路由
app.register_blueprint(system_info_bp, url_prefix='/system')
# 新增：注册上报管理路由
app.register_blueprint(report_management_bp, url_prefix='/report')
# 新增：注册气象数据拉取路由
app.register_blueprint(weather_fetch_bp, url_prefix='/weather-fetch')
# 新增：注册运营数据上传路由
app.register_blueprint(operational_data_upload_bp, url_prefix='/operational')

# 新增：初始化气象数据拉取调度器
try:
    from services.scheduler_service import init_scheduler
    import os
    # 获取数据库URL
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = os.environ.get('DB_PORT', '54321')
    db_user = os.environ.get('DB_USER', 'system')
    db_password = os.environ.get('DB_PASSWORD', '12345678ab')
    db_name = os.environ.get('DB_NAME', 'windpower')
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    init_scheduler(database_url)
    print("✅ 气象数据拉取调度器初始化成功")
except Exception as e:
    print(f"警告: 气象数据拉取调度器初始化失败: {e}")

# 添加JWT错误处理
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({"message": "令牌已过期，请重新登录"}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({"message": "无效的令牌"}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({"message": "缺少认证令牌"}), 401

# 添加健康检查端点
@app.route('/health', methods=['GET'])
def health_check():
    health_status = {
        "status": "ok",
        "database": "unknown",
        "minio": "unknown"
    }
    
    # 检查数据库连接
    try:
        with db_session() as db:
            db.execute(text("SELECT 1"))
            health_status["database"] = "ok"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
    
    # 检查MinIO连接
    try:
        if minio_client is not None:
            # 尝试列出存储桶
            minio_client.list_buckets()
            health_status["minio"] = "ok"
        else:
            health_status["minio"] = "unavailable"
    except Exception as e:
        health_status["minio"] = f"error: {str(e)}"
    
    # 如果任何服务不可用，返回503状态码
    if "error" in health_status["database"] or "error" in health_status["minio"] or \
       health_status["database"] == "unavailable" or health_status["minio"] == "unavailable":
        return jsonify(health_status), 503
    
    return jsonify(health_status)

# 添加全局 OPTIONS 请求处理器
@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 200

# 初始化数据库和存储桶
def initialize():
    with app.app_context():
        # 创建数据库表
        if engine is not None:
            try:
                Base.metadata.create_all(bind=engine)
                print("✅ 数据库表创建完成")
                
                # 初始化用户和角色
                try:
                    from init_users import init_users_and_roles
                    init_users_and_roles()
                    print("✅ 初始用户和角色创建完成")
                except Exception as e:
                    print(f"警告: 初始用户创建失败: {e}")
                    
            except Exception as e:
                print(f"警告: 数据库表创建失败: {e}")
        else:
            print("警告: 数据库引擎不可用，跳过表创建")
        
        # 初始化MinIO存储桶（更新为新的配置结构）
        if minio_client is not None:
            try:
                required_buckets = list(MINIO_CONFIG["buckets"].values())
                existing_buckets = [b.name for b in minio_client.list_buckets()]
                
                for bucket in required_buckets:
                    if bucket not in existing_buckets:
                        minio_client.make_bucket(bucket)
                        print(f"✅ 成功创建存储桶: {bucket}")
                    else:
                        print(f"✅ 存储桶已存在: {bucket}")
            except Exception as e:
                print(f"警告: MinIO存储桶初始化失败: {e}")
        else:
            print("警告: MinIO客户端不可用，跳过存储桶创建")

# 执行初始化
initialize()

@app.route('/upload_train_csv', methods=['POST'])
def upload_train_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 新增文件类型校验（来自代码1）
    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    # 生成唯一文件ID（来自代码1）
    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        # 新增本地保存逻辑（来自代码1）
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])
        
        # 重置文件指针以便后续上传
        file.stream.seek(0)

        # 根据数据类型选择存储路径
        data_type = request.form.get('data_type', 'traincsv')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 更新后的存储桶引用
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        # 验证MinIO上传
        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 更新后的存储桶引用
            file_path
        )
        print(f"✅ MinIO验证 - 文件大小：{obj_info.size}")

        # 数据库操作
        with db_session() as db:
            # 生成本地路径（组合代码1和代码2的参数）
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
                "file_id": file_id  # 返回本地保存的ID
            })
            
    except Exception as e:
        print(f"全局异常：{str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/upload_predict_csv', methods=['POST'])
def upload_predict_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 新增文件类型校验（来自代码1）
    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    # 生成唯一文件ID（来自代码1）
    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        # 新增本地保存逻辑（来自代码1）
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])
        
        # 重置文件指针以便后续上传
        file.stream.seek(0)

        # 根据数据类型选择存储路径
        data_type = request.form.get('data_type', 'predictcsv')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 更新后的存储桶引用
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        # 验证MinIO上传
        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 更新后的存储桶引用
            file_path
        )
        print(f"✅ MinIO验证 - 文件大小：{obj_info.size}")

        # 数据库操作
        with db_session() as db:
            # 生成本地路径（组合代码1和代码2的参数）
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
                "file_id": file_id  # 返回本地保存的ID
            })
            
    except Exception as e:
        print(f"全局异常：{str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/upload_model', methods=['POST'])
def upload_model():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 新增文件类型校验（来自代码1）
    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    # 生成唯一文件ID（来自代码1）
    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        # 新增本地保存逻辑（来自代码1）
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])
        
        # 重置文件指针以便后续上传
        file.stream.seek(0)

        # 根据数据类型选择存储路径
        data_type = request.form.get('data_type', 'model')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 更新后的存储桶引用
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        # 验证MinIO上传
        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 更新后的存储桶引用
            file_path
        )
        print(f"✅ MinIO验证 - 文件大小：{obj_info.size}")

        # 数据库操作
        with db_session() as db:
            # 生成本地路径（组合代码1和代码2的参数）
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
                "file_id": file_id  # 返回本地保存的ID
            })
            
    except Exception as e:
        print(f"全局异常：{str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/upload_scaler', methods=['POST'])
def upload_scaler():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 新增文件类型校验（来自代码1）
    if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify({"error": "Invalid file type"}), 400

    # 生成唯一文件ID（来自代码1）
    file_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    try:
        # 新增本地保存逻辑（来自代码1）
        save_uploaded_file(file, file_id, current_app.config['UPLOAD_FOLDER'])
        
        # 重置文件指针以便后续上传
        file.stream.seek(0)

        # 根据数据类型选择存储路径
        data_type = request.form.get('data_type', 'scaler')
        file_path = f"datasets/{data_type}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        
        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 更新后的存储桶引用
            file_path,
            file.stream,
            length=-1,
            part_size=10*1024*1024
        )

        # 验证MinIO上传
        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],  # 更新后的存储桶引用
            file_path
        )
        print(f"✅ MinIO验证 - 文件大小：{obj_info.size}")

        # 数据库操作
        with db_session() as db:
            # 生成本地路径（组合代码1和代码2的参数）
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
                "file_id": file_id  # 返回本地保存的ID
            })
            
    except Exception as e:
        print(f"全局异常：{str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large (max 500MB)'}), 413

@socketio.on('connect')
def handle_connect():
    app.logger.info("成功连接服务器！")
    socketio.emit('response', {'message': '连接成功！'})

@socketio.on('disconnect')
def handle_disconnect():
    app.logger.info("与服务器断开连接！")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
