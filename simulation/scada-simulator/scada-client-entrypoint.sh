#!/bin/bash
# SCADA客户端启动脚本：动态解析模拟器容器名到IP，写入配置后启动

CONFIG_FILE=/app/config.ini
SIMULATOR_HOST="${SCADA_SERVER_HOSTNAME:-sim-scada-server}"
SIMULATOR_PORT="${SCADA_SERVER_PORT:-2404}"
UPLOAD_URL="${UPLOAD_URL:-http://host.docker.internal:5000/actual_power/}"

echo "=== SCADA Client Startup ==="

# 复制一份可写的配置文件（挂载的可能是只读的）
if [ -f /app/config.orig.ini ]; then
    cp /app/config.orig.ini "$CONFIG_FILE"
    echo "[OK] Copied config.orig.ini -> config.ini"
fi
resolved_ip=""
for i in $(seq 1 30); do
    resolved_ip=$(getent hosts "$SIMULATOR_HOST" | awk '{print $1}' | head -1)
    if [ -n "$resolved_ip" ]; then
        echo "[OK] Resolved $SIMULATOR_HOST -> $resolved_ip"
        break
    fi
    echo "[WAIT] Resolving $SIMULATOR_HOST... attempt $i"
    sleep 2
done

if [ -z "$resolved_ip" ]; then
    echo "[ERROR] Cannot resolve $SIMULATOR_HOST"
    exit 1
fi

# 更新配置文件中的IP和端口
sed -i "s/^SCADA_SERVER_IP = .*/SCADA_SERVER_IP = $resolved_ip/" "$CONFIG_FILE"
sed -i "s/^SCADA_SERVER_PORT = .*/SCADA_SERVER_PORT = $SIMULATOR_PORT/" "$CONFIG_FILE"
sed -i "s|^UPLOAD_URL = .*|UPLOAD_URL = $UPLOAD_URL|" "$CONFIG_FILE"

echo "[OK] Config updated: IP=$resolved_ip PORT=$SIMULATOR_PORT URL=$UPLOAD_URL"
echo "=== Starting SCADA Client ==="

# 启动客户端
exec python scada_c104.py
