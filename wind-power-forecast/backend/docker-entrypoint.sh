#!/bin/bash
set -e

# 移除PM2检查，因为backend容器不需要PM2
# python check_pm2.py

# 创建utils目录（如果不存在）
mkdir -p /app/backend/utils

# 确保子目录中的__init__.py文件存在
touch /app/backend/utils/__init__.py

# 创建用于检查数据库连接的临时Python脚本
cat > check_db.py << EOL
import psycopg2
import os
import sys
import time

# 从环境变量获取数据库连接信息
host = os.environ.get('DB_HOST', 'kingbase')
port = os.environ.get('DB_PORT', '54321')
user = os.environ.get('DB_USER', 'system')
password = os.environ.get('DB_PASSWORD', '12345678ab')
dbname = os.environ.get('DB_NAME', 'windpower')

try:
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        connect_timeout=3
    )
    conn.close()
    print("数据库连接成功")
    sys.exit(0)
except Exception as e:
    print(f"数据库连接失败: {e}")
    sys.exit(1)
EOL

# 等待PostgreSQL和MinIO服务可用
echo "等待数据库服务就绪..."
for i in {1..30}; do
  if python check_db.py; then
    echo "数据库服务已就绪"
    break
  fi
  echo "等待数据库服务启动... $i/30"
  sleep 2
done

# 初始化数据库和用户
echo "初始化数据库和用户..."
python -m init_users

# 修复管理员权限
echo "检查并修复管理员权限..."
python -m fix_admin_permissions

# 修复所有角色权限
echo "检查并修复所有角色权限..."
python -m fix_user_permissions

# 使用标记文件判断是否为首次部署
# 确保工作目录存在
mkdir -p /app/backend/data

# 使用相对于应用的稳定路径
INIT_FLAG_FILE="/app/backend/data/admin_initialized.flag"
if [ ! -f "$INIT_FLAG_FILE" ]; then
    echo "首次部署：重置管理员密码为默认值(admin123)..."
    python -m reset_admin
    # 创建标记文件，表示已完成初始化
    touch "$INIT_FLAG_FILE"
    echo "已完成管理员密码初始化"
else
    echo "检测到已初始化标记，跳过管理员密码重置"
fi

# 创建monkey patch预加载文件
cat > /app/wsgi_app.py << EOL
# 首先确保gevent monkey patching已应用
import gevent.monkey
gevent.monkey.patch_all()

# 从app.py导入Flask应用实例
from app import app as application

# 这个文件会被Gunicorn直接导入
print("✅ WSGI应用已成功预加载，gevent monkey patching已应用")

# 导出app变量用于Gunicorn
app = application
EOL

# 计算worker数量：(2 * CPU核心数) + 1
CORES=$(grep -c ^processor /proc/cpuinfo)
# 为了测试，我们将worker数量设置为4，避免系统资源过度消耗
WORKERS=3
echo "系统检测到 $CORES 个CPU核心，将启动 $WORKERS 个Gunicorn工作进程"

# 启动应用
echo "使用Gunicorn启动应用..."
exec gunicorn \
  --workers $WORKERS \
  --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
  --worker-connections 2000 \
  --timeout 180 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 200 \
  --log-level info \
  --bind 0.0.0.0:5000 \
  --preload \
  wsgi_app:app 