"""应用工厂，集中后端初始化逻辑。"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import gevent.monkey

gevent.monkey.patch_all()

# 确保项目根目录在模块搜索路径中
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, current_app, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from sqlalchemy import text

try:
    from .config import Config, MINIO_CONFIG
except ImportError:  # 在作为脚本运行时回退到绝对导入
    from config import Config, MINIO_CONFIG
from connection_middleware import register_middleware
from database_config import Base, engine, minio_client
try:
    from .db_models import Dataset
except ImportError:  # 在作为脚本运行时回退到绝对导入
    from db_models import Dataset
from db_session import db_session
from logging_config import configure_logging
from services.file_service import allowed_file, save_uploaded_file
from windpower_core.storage import dataset_object_key, normalize_wind_farm_code, sanitize_filename
from task_queue import init_celery
try:
    from .libs.config import settings as app_settings
except ImportError:  # 在作为脚本运行时回退到绝对导入
    from libs.config import settings as app_settings

_settings = app_settings
_cors_methods = [method.strip() for method in _settings.cors_allowed_methods.split(",") if method.strip()]
_cors_headers = [header.strip() for header in _settings.cors_allowed_headers.split(",") if header.strip()]
_cors_origins = _settings.cors_origins_list or ["*"]
_socketio_cors = "*" if _cors_origins == ["*"] else _cors_origins

socketio = SocketIO(cors_allowed_origins=_socketio_cors, async_mode="gevent")
jwt = JWTManager()


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__, static_folder="./static")
    app.config.from_object(config_object)

    _configure_jwt(app)
    _configure_cors(app)

    socketio.init_app(app, cors_allowed_origins="*")
    configure_logging(app, socketio)
    register_middleware(app)

    # 初始化 Celery
    app.celery_app = init_celery(app)
    import backend.tasks  # noqa: F401 确保任务注册

    _register_blueprints(app)
    _register_internal_routes(app)
    _initialize_resources(app)
    _initialize_scheduler(app)

    return app


def _configure_jwt(app: Flask) -> None:
    app.config["JWT_SECRET_KEY"] = _settings.jwt_secret_key
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=_settings.jwt_access_token_expires_hours)
    jwt.init_app(app)


def _configure_cors(app: Flask) -> None:
    CORS(
        app,
        resources={
            r"/*": {
                "origins": "*" if _cors_origins == ["*"] else _cors_origins,
                "methods": _cors_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": _cors_headers
                or ["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
                "expose_headers": [
                    "Content-Type",
                    "Content-Length",
                    "Authorization",
                    "Accept",
                    "X-Requested-With",
                    "Origin",
                ],
                "supports_credentials": False,
                "max_age": 86400,
            }
        },
    )


def _register_blueprints(app: Flask) -> None:
    """按业务域注册蓝图。"""

    # 训练与模型管理
    from routes.modeltrain import modeltrain_bp
    from routes.training import training_bp
    from routes.autotask import autotask_bp

    # 预测与数据发布
    from routes.predict import predict_bp
    from routes.power_compare import bp as power_compare_bp
    from routes.prediction2database import prediction2database_bp
    from routes.actual_power_router import actual_power_bp
    from routes.download import download_bp

    # 数据接入
    from routes.feature_upload import feature_upload_bp
    from routes.operational_data_upload import operational_data_upload_bp

    # 系统能力
    from routes.auth import auth_bp
    from routes.user import user_bp
    from routes.report_management_router import report_management_bp
    from routes.system_info_router import system_info_bp
    from routes.weather_fetch_router import weather_fetch_bp
    from routes.physical_simulation_router import physical_simulation_bp
    from routes.example_route import example_bp
    from routes.jobs import jobs_bp

    app.register_blueprint(modeltrain_bp, url_prefix="/")
    app.register_blueprint(training_bp, url_prefix="/")
    app.register_blueprint(autotask_bp, url_prefix="/")

    app.register_blueprint(predict_bp, url_prefix="/")
    app.register_blueprint(power_compare_bp)
    app.register_blueprint(prediction2database_bp)
    app.register_blueprint(actual_power_bp)
    app.register_blueprint(download_bp, url_prefix="/")

    app.register_blueprint(feature_upload_bp)
    app.register_blueprint(operational_data_upload_bp, url_prefix="/operational")

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(user_bp, url_prefix="/api/user")
    app.register_blueprint(report_management_bp, url_prefix="/report")
    app.register_blueprint(system_info_bp, url_prefix="/system")
    app.register_blueprint(weather_fetch_bp, url_prefix="/weather-fetch")
    app.register_blueprint(physical_simulation_bp)
    app.register_blueprint(example_bp, url_prefix="/api/example")
    app.register_blueprint(jobs_bp)


def _register_internal_routes(app: Flask) -> None:
    @app.route("/health", methods=["GET"])
    def health_check():
        health_status = {
            "status": "ok",
            "database": "unknown",
            "minio": "unknown",
        }

        try:
            with db_session() as db:
                db.execute(text("SELECT 1"))
                health_status["database"] = "ok"
        except Exception as exc:  # pragma: no cover - 健康检查日志
            health_status["database"] = f"error: {exc}"

        try:
            if minio_client is not None:
                minio_client.list_buckets()
                health_status["minio"] = "ok"
            else:
                health_status["minio"] = "unavailable"
        except Exception as exc:  # pragma: no cover
            health_status["minio"] = f"error: {exc}"

        if any(
            status in ("unavailable",) or "error" in str(status)
            for status in (health_status["database"], health_status["minio"])
        ):
            return jsonify(health_status), 503

        return jsonify(health_status)

    @app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
    @app.route("/<path:path>", methods=["OPTIONS"])
    def handle_options(path):  # pragma: no cover - 仅用于预检
        return "", 200

    _register_file_upload_routes(app)


def _register_file_upload_routes(app: Flask) -> None:
    def _handle_upload(file_key: str, default_type: str):
        if file_key not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files[file_key]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        if not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
            return jsonify({"error": "Invalid file type"}), 400

        file_id = datetime.now().strftime("%Y%m%d%H%M%S%f")

        data_type = request.form.get("data_type", default_type)
        uploaded_at = datetime.now()
        default_wind_farm_code = MINIO_CONFIG.get("default_wind_farm_code", "default-farm")
        raw_wind_farm_code = request.form.get("wind_farm_code") or request.form.get("wind_farm")
        normalized_wind_farm_code = normalize_wind_farm_code(raw_wind_farm_code, default_wind_farm_code)
        sanitized_filename = sanitize_filename(file.filename, fallback="dataset.csv")

        local_path = save_uploaded_file(
            file,
            file_id,
            current_app.config["UPLOAD_FOLDER"],
            wind_farm_code=normalized_wind_farm_code,
            default_wind_farm_code=default_wind_farm_code,
            subdirs=("datasets", data_type, uploaded_at.strftime("%Y%m%d")),
        )
        file.stream.seek(0)

        file_path = dataset_object_key(
            wind_farm_code=normalized_wind_farm_code,
            data_type=data_type,
            filename=sanitized_filename,
            uploaded_at=uploaded_at,
        )

        if minio_client is None:
            return jsonify({"error": "Object storage is unavailable"}), 503

        minio_client.put_object(
            MINIO_CONFIG["buckets"]["datasets"],
            file_path,
            file.stream,
            length=-1,
            part_size=10 * 1024 * 1024,
        )

        obj_info = minio_client.stat_object(
            MINIO_CONFIG["buckets"]["datasets"],
            file_path,
        )
        current_app.logger.info("✅ MinIO验证 - 文件大小：%s", obj_info.size)

        with db_session() as db:
            dataset = Dataset(
                file_id=file_id,
                filename=file.filename,
                file_path=file_path,
                upload_time=uploaded_at,
                file_size=file.content_length,
                file_type=data_type,
                local_path=str(local_path),
                description=request.form.get("description", ""),
                data_type=data_type,
                wind_farm=request.form.get("wind_farm", "unknown"),
                wind_farm_code=normalized_wind_farm_code,
            )
            db.add(dataset)
            db.commit()

            return jsonify({
                "message": "File uploaded successfully",
                "dataset_id": dataset.id,
                "file_id": file_id,
            })

    def upload_train_csv():
        return _handle_upload("file", "traincsv")

    def upload_predict_csv():
        return _handle_upload("file", "predictcsv")

    def upload_model():
        return _handle_upload("file", "model")

    def upload_scaler():
        return _handle_upload("file", "scaler")

    app.add_url_rule("/upload_train_csv", view_func=upload_train_csv, methods=["POST"])
    app.add_url_rule("/upload_predict_csv", view_func=upload_predict_csv, methods=["POST"])
    app.add_url_rule("/upload_model", view_func=upload_model, methods=["POST"])
    app.add_url_rule("/upload_scaler", view_func=upload_scaler, methods=["POST"])


def _initialize_resources(app: Flask) -> None:
    with app.app_context():
        if engine is not None:
            try:
                Base.metadata.create_all(bind=engine)
                from init_users import init_users_and_roles

                try:
                    init_users_and_roles()
                    print("✅ 初始用户和角色创建完成")
                except Exception as exc:  # pragma: no cover
                    print(f"警告: 初始用户创建失败: {exc}")
            except Exception as exc:  # pragma: no cover
                print(f"警告: 数据库表创建失败: {exc}")
        else:
            print("警告: 数据库引擎不可用，跳过表创建")

        if minio_client is not None:
            try:
                required_buckets = list(MINIO_CONFIG["buckets"].values())
                existing_buckets = [bucket.name for bucket in minio_client.list_buckets()]

                for bucket in required_buckets:
                    if bucket not in existing_buckets:
                        minio_client.make_bucket(bucket)
                        print(f"✅ 成功创建存储桶: {bucket}")
                    else:
                        print(f"✅ 存储桶已存在: {bucket}")
            except Exception as exc:  # pragma: no cover
                print(f"警告: MinIO存储桶初始化失败: {exc}")
        else:
            print("警告: MinIO客户端不可用，跳过存储桶创建")


def _initialize_scheduler(app: Flask) -> None:
    try:
        from services.scheduler_service import init_scheduler

        db_host = os.environ.get("DB_HOST", "localhost")
        db_port = os.environ.get("DB_PORT", "54321")
        db_user = os.environ.get("DB_USER", "system")
        db_password = os.environ.get("DB_PASSWORD", "12345678ab")
        db_name = os.environ.get("DB_NAME", "windpower")

        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        init_scheduler(database_url)
        app.logger.info("✅ 气象数据拉取调度器初始化成功")
    except Exception as exc:  # pragma: no cover
        app.logger.warning("气象数据拉取调度器初始化失败: %s", exc)


@socketio.on("connect")
def handle_connect():  # pragma: no cover - 依赖 SocketIO 客户端
    current_app.logger.info("成功连接服务器！")
    socketio.emit("response", {"message": "连接成功！"})


@socketio.on("disconnect")
def handle_disconnect():  # pragma: no cover
    current_app.logger.info("与服务器断开连接！")


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):  # pragma: no cover
    return jsonify({"message": "令牌已过期，请重新登录"}), 401


@jwt.invalid_token_loader
def invalid_token_callback(error):  # pragma: no cover
    return jsonify({"message": "无效的令牌"}), 401


@jwt.unauthorized_loader
def missing_token_callback(error):  # pragma: no cover
    return jsonify({"message": "缺少认证令牌"}), 401


@socketio.on_error_default
def default_socketio_error_handler(e):  # pragma: no cover
    current_app.logger.error("SocketIO 错误: %s", e)


__all__ = ["create_app", "socketio"]


