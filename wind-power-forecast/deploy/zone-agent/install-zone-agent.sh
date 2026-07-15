#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "错误：请使用 root 权限安装分区代理"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RELEASE_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VERSION="$(tr -d '\r\n' < "$RELEASE_DIR/VERSION")"
SOURCE_AGENT="$RELEASE_DIR/agents/integration"
TARGET_RELEASE="/opt/windpower-zone-agent/releases/$VERSION"

if [ ! -d "$SOURCE_AGENT" ]; then
    echo "错误：发布包缺少 agents/integration"
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "错误：服务器需要 Python 3.10 或更高版本"
    exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "错误：检测到的 Python 版本低于 3.10"
    exit 1
fi

if ! id windpower-agent >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/windpower-zone-agent --shell /usr/sbin/nologin windpower-agent
fi

install -d -m 0755 "$TARGET_RELEASE/integration"
install -m 0644 "$SOURCE_AGENT"/*.py "$TARGET_RELEASE/integration/"
install -m 0755 "$SCRIPT_DIR/run-agent.sh" "$TARGET_RELEASE/run-agent.sh"
ln -sfn "$TARGET_RELEASE" /opt/windpower-zone-agent/current

install -m 0644 "$SCRIPT_DIR/windpower-zone-agent.service" /etc/systemd/system/
if [ ! -f /etc/windpower-zone-agent.env ]; then
    install -m 0640 -o root -g windpower-agent \
        "$SCRIPT_DIR/zone-agent.env.example" /etc/windpower-zone-agent.env
fi
if [ ! -f /etc/windpower-zone-agent.token ]; then
    install -m 0640 -o root -g windpower-agent /dev/null /etc/windpower-zone-agent.token
fi

install -d -m 0750 -o windpower-agent -g windpower-agent /var/lib/windpower-zone-agent
systemctl daemon-reload
systemctl enable windpower-zone-agent.service

echo "分区代理版本 $VERSION 已安装"
echo "请填写 /etc/windpower-zone-agent.env 和令牌文件，然后执行："
echo "systemctl restart windpower-zone-agent.service"
