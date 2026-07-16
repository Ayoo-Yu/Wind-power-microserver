#!/usr/bin/env bash
set -euo pipefail

cd /app
export PYTHONPATH="/app:${PYTHONPATH:-}"

echo "等待数据库服务..."
python manage_db.py wait --timeout "${DB_WAIT_TIMEOUT_SECONDS:-60}"

SCHEMA_ACTION="${DB_SCHEMA_ACTION:-check}"
case "${SCHEMA_ACTION}" in
    check)
        python manage_db.py check
        ;;
    skip)
        echo "已按配置跳过数据库结构检查"
        ;;
    *)
        echo "Web 容器只允许 DB_SCHEMA_ACTION=check 或 skip。请通过 deployment-init 服务执行迁移。" >&2
        exit 2
        ;;
esac

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
  wsgi_app:app
