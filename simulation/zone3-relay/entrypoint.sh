#!/bin/bash
set -e

echo "=== Zone3 Relay Service ==="

# 修复SSH密钥权限（忽略只读挂载的错误）
if [ -f /home/ecs-user/.ssh/id_rsa ]; then
    chmod 600 /home/ecs-user/.ssh/id_rsa 2>/dev/null || true
    echo "[OK] SSH key found"
else
    echo "[WARN] No SSH key at /home/ecs-user/.ssh/id_rsa"
    echo "       Zone3 relay cannot pull from Tencent Cloud"
fi

FETCH_INTERVAL=${FETCH_INTERVAL_MINUTES:-15}

# 创建状态文件目录
mkdir -p /opt/scripts/ecmwf_fetcher
touch /opt/scripts/ecmwf_fetcher/downloaded_state.txt

# 设置cron
echo "Setting up cron (every ${FETCH_INTERVAL} minutes)..."
cat > /etc/cron.d/ecmwf_fetcher << EOF
PATH=/usr/local/bin:/usr/bin:/bin
*/${FETCH_INTERVAL} * * * * root python3 /opt/scripts/ecmwf_fetcher/fetch_data_from_c.py >> /var/log/ecmwf_fetcher_cron.log 2>&1
EOF
chmod 0644 /etc/cron.d/ecmwf_fetcher

# 初次运行
echo "Running initial fetch..."
python3 /opt/scripts/ecmwf_fetcher/fetch_data_from_c.py || echo "Initial fetch failed (will retry via cron)"

# 启动cron并跟踪日志
echo "Starting cron daemon (interval: ${FETCH_INTERVAL} min)..."
cron
tail -f /var/log/ecmwf_fetcher.log /var/log/ecmwf_fetcher_cron.log 2>/dev/null
