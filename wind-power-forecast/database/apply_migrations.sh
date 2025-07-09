#!/bin/bash

# 数据库连接信息
DB_USER="postgres"
DB_PASSWORD="yzz0216yh"
DB_NAME="windpower"
DB_HOST="localhost"
DB_PORT="5432"

# 确保迁移目录存在
MIGRATIONS_DIR="$(dirname "$0")/migrations"
if [ ! -d "$MIGRATIONS_DIR" ]; then
  mkdir -p "$MIGRATIONS_DIR"
  echo "创建迁移目录: $MIGRATIONS_DIR"
fi

# 执行迁移
echo "开始执行数据库迁移..."

# 用户管理迁移
echo "执行用户管理迁移..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f "$MIGRATIONS_DIR/user_management_migration.sql"

echo "数据库迁移完成！" 