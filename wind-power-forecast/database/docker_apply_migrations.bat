@echo off
setlocal

REM 数据库容器名称
set DB_CONTAINER=wind-power-postgres

echo 开始执行数据库迁移...

REM 复制迁移文件到容器
echo 复制迁移文件到容器...
docker cp "%~dp0migrations" %DB_CONTAINER%:/tmp/

REM 执行用户管理迁移
echo 执行用户管理迁移...
docker exec %DB_CONTAINER% psql -U postgres -d windpower -f /tmp/migrations/user_management_migration.sql

echo 数据库迁移完成！

pause 