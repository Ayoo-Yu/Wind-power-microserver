"""自动预测服务应用工厂。"""

import eventlet

eventlet.monkey_patch()

from datetime import timedelta
from pathlib import Path
import sys

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from dotenv import load_dotenv

# 确保项目根目录在模块搜索路径
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import Config
from connection_middleware import register_middleware
from logging_config import configure_logging


load_dotenv()

socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")
jwt = JWTManager()


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__, static_folder="./static")
    app.config.from_object(config_object)

    _configure_jwt(app)
    _configure_cors(app)

    socketio.init_app(app, cors_allowed_origins="*")
    configure_logging(app, socketio)
    register_middleware(app)

    _register_blueprints(app)
    _register_internal_routes(app)

    return app


def _configure_jwt(app: Flask) -> None:
    app.config["JWT_SECRET_KEY"] = app.config.get("JWT_SECRET_KEY", "wind-power-forecast-secret-key")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)
    jwt.init_app(app)


def _configure_cors(app: Flask) -> None:
    CORS(
        app,
        resources={
            r"/*": {
                "origins": "*",
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "X-Requested-With",
                    "Accept",
                    "Origin",
                ],
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
    from routes.autopredict import autopredict_bp
    from routes.autotask import autotask_bp
    from routes.auth import auth_bp

    app.register_blueprint(autopredict_bp, url_prefix="/api")
    app.register_blueprint(autotask_bp, url_prefix="/")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")


def _register_internal_routes(app: Flask) -> None:
    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok", "service": "backend-autopredict"})

    @app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
    @app.route("/<path:path>", methods=["OPTIONS"])
    def handle_options(path):  # pragma: no cover
        return "", 200

    @app.errorhandler(413)
    def request_entity_too_large(error):  # pragma: no cover
        return jsonify({"error": "File too large (max 200MB)"}), 413


@socketio.on("connect")
def handle_connect():  # pragma: no cover
    socketio.emit("response", {"message": "连接成功！"})


@socketio.on("disconnect")
def handle_disconnect():  # pragma: no cover
    pass


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):  # pragma: no cover
    return jsonify({"message": "令牌已过期，请重新登录"}), 401


@jwt.invalid_token_loader
def invalid_token_callback(error):  # pragma: no cover
    return jsonify({"message": "无效的令牌"}), 401


@jwt.unauthorized_loader
def missing_token_callback(error):  # pragma: no cover
    return jsonify({"message": "缺少认证令牌"}), 401


__all__ = ["create_app", "socketio"]


