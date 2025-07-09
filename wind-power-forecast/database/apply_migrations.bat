@echo off
setlocal

REM 数据库连接信息
set DB_USER=postgres
set DB_PASSWORD=yzz0216yh
set DB_NAME=windpower
set DB_HOST=localhost
set DB_PORT=5432

REM 确保迁移目录存在
set MIGRATIONS_DIR=%~dp0migrations
if not exist "%MIGRATIONS_DIR%" (
  mkdir "%MIGRATIONS_DIR%"
  echo 创建迁移目录: %MIGRATIONS_DIR%
)

REM 执行迁移
echo 开始执行数据库迁移...

REM 用户管理迁移
echo 执行用户管理迁移...
set PGPASSWORD=%DB_PASSWORD%
psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -f "%MIGRATIONS_DIR%\user_management_migration.sql"

echo 数据库迁移完成！

pause 