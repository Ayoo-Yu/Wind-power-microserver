#!/usr/bin/env bash
set -euo pipefail

cd /app

echo "等待数据库服务..."
python manage_db.py wait --timeout "${DB_WAIT_TIMEOUT_SECONDS:-60}"

SCHEMA_ACTION="${DB_SCHEMA_ACTION:-prepare}"
case "${SCHEMA_ACTION}" in
    prepare)
        python manage_db.py prepare
        ;;
    upgrade)
        python manage_db.py upgrade
        ;;
    check)
        python manage_db.py check
        ;;
    skip)
        echo "已按配置跳过数据库结构检查"
        ;;
    *)
        echo "不支持的 DB_SCHEMA_ACTION: ${SCHEMA_ACTION}" >&2
        exit 2
        ;;
esac

echo "初始化默认角色；仅在显式提供引导密码时创建管理员账号..."
python -m init_users
python -m fix_admin_permissions
python -m fix_user_permissions

CORES="$(grep -c '^processor' /proc/cpuinfo || echo 1)"
WORKERS="${GUNICORN_WORKERS:-3}"
echo "检测到 ${CORES} 个 CPU 核心，启动 ${WORKERS} 个 Gunicorn 工作进程"

exec gunicorn \
  --workers "${WORKERS}" \
  --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
  --worker-connections 2000 \
  --timeout 600 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 200 \
  --log-level info \
  --bind 0.0.0.0:5000 \
  --preload \
  wsgi_app:app
