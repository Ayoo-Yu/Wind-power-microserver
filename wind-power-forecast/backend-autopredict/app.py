import eventlet
eventlet.monkey_patch()
from flask import Flask, request, jsonify, current_app
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv
from config import Config
import os
from connection_middleware import register_middleware
from sqlalchemy import text
# 导入JWT扩展
from flask_jwt_extended import JWTManager
from datetime import timedelta

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

app = Flask(__name__, static_folder='./static')
app.config.from_object(Config)

# --- JWT配置 ---
# 设置JWT密钥，与backend服务使用相同的密钥
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "wind-power-forecast-secret-key")
# 设置与backend服务相同的令牌过期时间（12小时）
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
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 配置日志
configure_logging(app, socketio)

# 注册数据库连接中间件
register_middleware(app)

# 只注册自动预测相关的蓝图
from routes.autopredict import autopredict_bp
from routes.autotask import autotask_bp
from routes.auth import auth_bp  # 保留认证蓝图

app.register_blueprint(autopredict_bp, url_prefix='/api')
app.register_blueprint(autotask_bp, url_prefix='/')
app.register_blueprint(auth_bp, url_prefix='/api/auth')  # 认证是必要的

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

# 添加健康检查路由
@app.route('/health', methods=['GET'])
def health_check():
    """Docker容器健康检查接口"""
    return jsonify({"status": "ok", "service": "backend-autopredict"}), 200

# 添加全局 OPTIONS 请求处理器
@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 200
    
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large (max 200MB)'}), 413

@socketio.on('connect')
def handle_connect():
    app.logger.info("成功连接服务器！")
    socketio.emit('response', {'message': '连接成功！'})

@socketio.on('disconnect')
def handle_disconnect():
    app.logger.info("与服务器断开连接！")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
