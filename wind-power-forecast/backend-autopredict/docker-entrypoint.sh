#!/bin/bash
set -e

# 检查PM2安装状态
python check_pm2.py

# 创建utils目录（如果不存在）
mkdir -p /app/utils

# 确保子目录中的__init__.py文件存在
touch /app/utils/__init__.py

# 创建Conda环境符号链接（确保脚本能找到正确的环境路径）
mkdir -p /app/backend
if [ ! -L "/app/backend/env" ]; then
    echo "创建Conda环境符号链接: /app/backend/env -> /opt/conda/envs/wind-power-env"
    ln -sf /opt/conda/envs/wind-power-env /app/backend/env
fi

# 检查文件路径是否存在，并显示详细信息
echo "检查关键文件路径..."
python check_file_paths.py || echo "⚠️ 部分文件路径不存在，但容器将继续启动"

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

# 确保工作目录存在
mkdir -p /app/data

# 启动应用
echo "启动自动预测应用..."
pm2-runtime start ecosystem.config.js 