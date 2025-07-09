@echo off
chcp 65001 > nul
echo 正在启动金仓数据库和MinIO服务...

REM 切换到项目目录
cd /d D:\my-vue-project\wind-power-forecast

REM 启动数据库和MinIO服务
docker-compose -f frontend-backend-compose.yaml up -d kingbase minio pgadmin

echo.
echo 服务启动成功！
echo.
echo 金仓数据库: localhost:54321
echo MinIO: http://localhost:9000 (API) 和 http://localhost:9001 (管理界面)
echo PgAdmin: http://localhost:5050
echo.
echo 凭据信息:
echo - MinIO: minioadmin/minioadmin
echo - 金仓数据库: system/12345678ab
echo - PgAdmin: admin@admin.com/admin
echo.
echo 按任意键退出...
pause > nul 