@echo off
chcp 65001 > nul
setlocal
echo Starting KingBase and PgAdmin services...

cd /d "%~dp0"

docker-compose -f frontend-backend-compose.yaml up -d kingbase pgadmin

echo.
echo Services started.
echo.
echo KingBase: localhost:54321
echo PgAdmin: http://localhost:5050
echo.
echo Credentials:
echo - KingBase: system/12345678ab
echo - PgAdmin: admin@admin.com/admin
echo.
pause > nul
