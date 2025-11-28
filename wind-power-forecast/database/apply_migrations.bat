@echo off
setlocal

REM 数据库连接信息
set DB_USER=postgres
set DB_PASSWORD=yzz0216yh
set DB_NAME=windpower
set DB_HOST=localhost
set DB_PORT=5432

REM 路径设置
set SCRIPT_DIR=%~dp0
set MIGRATIONS_DIR=%SCRIPT_DIR%migrations
set INITIAL_SQL_DIR=%SCRIPT_DIR%initial_sql

REM 确保迁移目录存在
if not exist "%MIGRATIONS_DIR%" (
  mkdir "%MIGRATIONS_DIR%"
  echo 创建迁移目录: %MIGRATIONS_DIR%
)

REM 执行迁移
echo 开始执行数据库迁移...

REM 用户管理迁移（角色、用户）
echo 执行用户管理迁移...
set PGPASSWORD=%DB_PASSWORD%
psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -f "%INITIAL_SQL_DIR%\user_management_migration.sql"

REM 风场相关扩展迁移（datasets/models 等新增字段）
echo 执行风场扩展迁移...
psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -f "%MIGRATIONS_DIR%\20250101_add_wind_farm_support.sql"

echo 数据库迁移完成！

pause 