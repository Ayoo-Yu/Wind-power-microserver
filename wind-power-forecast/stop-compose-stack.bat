@echo off
setlocal
chcp 65001 >nul 2>&1

set "ROOT=%~dp0"
set "DB_COMPOSE=%ROOT%database\docker-compose.yaml"
set "DEPLOY_COMPOSE=%ROOT%frontend-backend-compose.yaml"

echo [1/2] Stopping wind-power-deployment project...
docker compose -p wind-power-deployment -f "%DEPLOY_COMPOSE%" stop pgadmin

echo [2/2] Stopping database project...
docker compose -p database -f "%DB_COMPOSE%" stop kingbase

echo.
echo Current related containers:
docker ps -a --format "table {{.Names}}\t{{.Status}}" | findstr /I "wind-power-kingbase wind-power-pgadmin"
exit /b 0
