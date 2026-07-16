#!/bin/bash

# 金仓数据库初始化脚本
echo "开始初始化金仓数据库..."

: "${DB_PASSWORD:?必须设置 DB_PASSWORD}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-54321}"
DB_USER="${DB_USER:-system}"
DB_NAME="${DB_NAME:-windpower}"

# 等待金仓数据库启动
echo "等待金仓数据库服务启动..."
sleep 10

# 连接到默认数据库并创建应用数据库
echo "创建应用数据库..."
PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -c "CREATE DATABASE ${DB_NAME} WITH ENCODING='UTF8';" || echo "数据库已存在，跳过创建步骤"

# 运行数据库迁移
echo "运行数据库迁移..."
cd "$(dirname "$0")" || exit
alembic upgrade head

echo "数据库初始化完成！"
