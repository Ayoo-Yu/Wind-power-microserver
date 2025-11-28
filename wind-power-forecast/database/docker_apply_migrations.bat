@echo off
setlocal

REM 数据库容器名称（与 docker-compose.yaml 中的 container_name 保持一致）
set DB_CONTAINER=wind-power-kingbase

echo 开始执行数据库迁移...

REM 复制迁移文件到容器
echo 复制迁移文件到容器...
docker cp "%~dp0migrations" %DB_CONTAINER%:/tmp/
docker cp "%~dp0initial_sql" %DB_CONTAINER%:/tmp/

REM 执行用户管理迁移（角色、用户）
echo 执行用户管理迁移...
docker exec %DB_CONTAINER% psql -U postgres -d windpower -f /tmp/initial_sql/user_management_migration.sql

REM 执行风场扩展迁移（datasets/models 等新增字段）
echo 执行风场扩展迁移...
docker exec %DB_CONTAINER% psql -U postgres -d windpower -f /tmp/migrations/20250101_add_wind_farm_support.sql

echo 数据库迁移完成！

pause