#!/bin/bash

# 金仓数据库初始化脚本
echo "开始初始化金仓数据库..."

# 等待金仓数据库启动
echo "等待金仓数据库服务启动..."
sleep 10

# 连接到默认数据库并创建应用数据库
echo "创建应用数据库..."
PGPASSWORD=12345678ab psql -h localhost -p 54321 -U system -c "CREATE DATABASE windpower WITH ENCODING='UTF8';" || echo "数据库已存在，跳过创建步骤"

# 运行数据库迁移
echo "运行数据库迁移..."
cd "$(dirname "$0")" || exit
alembic upgrade head

echo "数据库初始化完成！" 