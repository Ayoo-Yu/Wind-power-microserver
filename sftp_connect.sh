#!/bin/bash
# 简单的SFTP连接脚本
PASSWORD="yzz0216yhAAAA"
BATCH_FILE="$1"

# 使用管道将密码和命令发送到sftp
(
  echo "$PASSWORD"  # 先发送密码
  cat "$BATCH_FILE" # 然后发送批处理命令
) | sftp -o StrictHostKeyChecking=no -P 22 root@49.232.246.73