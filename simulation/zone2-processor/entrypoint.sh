#!/bin/bash
set -e

echo "=== Zone2 Data Processor Service ==="

FETCH_INTERVAL=${FETCH_INTERVAL_MINUTES:-15}

# 创建状态文件
mkdir -p /opt/scripts/ecmwf_fetcher
touch /opt/scripts/ecmwf_fetcher/downloaded_state.txt

# 设置cron
echo "Setting up cron (every ${FETCH_INTERVAL} minutes)..."
cat > /etc/cron.d/ecmwf_processor << EOF
PATH=/usr/local/bin:/usr/bin:/bin
*/${FETCH_INTERVAL} * * * * root python3 /opt/scripts/ecmwf_fetcher/process_local.py >> /var/log/ecmwf_processor_cron.log 2>&1
EOF
chmod 0644 /etc/cron.d/ecmwf_processor

# 数据库引导：等待就绪 → 建库 → 建表
echo "Bootstrapping database..."
python3 /opt/scripts/ensure_db.py || echo "DB bootstrap failed (will retry via cron)"

# 初次运行
echo "Running initial processing..."
python3 /opt/scripts/ecmwf_fetcher/process_local.py || echo "Initial processing failed (will retry via cron)"

# 启动cron并跟踪日志
echo "Starting cron daemon (interval: ${FETCH_INTERVAL} min)..."
cron
tail -f /var/log/ecmwf_fetcher.log /var/log/ecmwf_processor_cron.log 2>/dev/null
