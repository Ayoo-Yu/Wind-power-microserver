#!/bin/bash
# 设置ECMWF数据获取脚本的维护任务

# 脚本目录
SCRIPT_DIR=$(dirname $(readlink -f $0))
CLEANUP_SCRIPT="${SCRIPT_DIR}/cleanup_state.py"

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
  echo "请以root用户运行此脚本"
  exit 1
fi

# 设置logrotate配置
LOGROTATE_FILE="/etc/logrotate.d/ecmwf_fetcher"
if [ ! -f "$LOGROTATE_FILE" ]; then
  echo "正在设置logrotate配置..."
  cp "${SCRIPT_DIR}/ecmwf_fetcher" "$LOGROTATE_FILE"
  chmod 644 "$LOGROTATE_FILE"
  echo "logrotate配置已安装到: $LOGROTATE_FILE"
else
  echo "logrotate配置已存在: $LOGROTATE_FILE"
fi

# 确保状态清理脚本有执行权限
chmod +x "$CLEANUP_SCRIPT"

# 设置每月清理状态文件的cron任务
CRON_JOB="0 0 1 * * python3 ${CLEANUP_SCRIPT} --keep-days 180 >> /var/log/ecmwf_state_cleanup.log 2>&1"

# 检查是否已设置cron任务
if crontab -l 2>/dev/null | grep -q "$CLEANUP_SCRIPT"; then
  echo "状态清理cron任务已存在"
else
  echo "正在设置状态清理cron任务..."
  (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
  echo "每月自动清理任务已设置 (保留最近180天的记录)"
fi

echo "维护任务设置完成!"
echo ""
echo "logrotate将由系统每日自动执行"
echo "状态文件将每月1日自动清理，仅保留最近180天的记录"
echo ""
echo "如需测试状态文件清理效果，可以运行:"
echo "  python3 ${CLEANUP_SCRIPT} --keep-days 180 --dry-run"
echo ""
echo "如需手动运行日志轮转，可以执行:"
echo "  logrotate -f $LOGROTATE_FILE" 