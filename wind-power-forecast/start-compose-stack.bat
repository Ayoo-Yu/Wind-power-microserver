@echo off
setlocal
chcp 65001 >nul 2>&1

set "ROOT=%~dp0"
set "DB_COMPOSE=%ROOT%database\docker-compose.yaml"
set "DEPLOY_COMPOSE=%ROOT%frontend-backend-compose.yaml"

echo [1/5] Checking Docker...
docker version >nul 2>&1
if errorlevel 1 (
  echo Docker is not running. Please start Docker Desktop first.
  exit /b 1
)

echo [2/5] Starting database project (kingbase)...
docker compose -p database -f "%DB_COMPOSE%" up -d kingbase
if errorlevel 1 (
  echo Failed to start database project.
  exit /b 1
)

echo [3/5] Waiting for kingbase to become reachable...
set "DB_READY=0"
for /L %%i in (1,1,40) do (
  docker exec wind-power-kingbase /home/kingbase/install/kingbase/bin/ksql -Usystem -d test -c "select 1;" >nul 2>&1
  if not errorlevel 1 (
    set "DB_READY=1"
    goto :db_ready
  )
  timeout /t 2 >nul
)

:db_ready
if "%DB_READY%"=="0" (
  echo Kingbase did not become ready in time.
  exit /b 1
)

echo Ensuring database windpower exists...
docker exec wind-power-kingbase /home/kingbase/install/kingbase/bin/ksql -Usystem -d test -c "create database windpower;" >nul 2>&1

echo [4/5] Starting wind-power-deployment project (minio + pgadmin)...
docker compose -p wind-power-deployment -f "%DEPLOY_COMPOSE%" up -d --no-deps minio pgadmin
if errorlevel 1 (
  echo Failed to start wind-power-deployment project.
  exit /b 1
)

echo [5/5] Stack status:
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | findstr /I "wind-power-kingbase wind-power-minio wind-power-pgadmin"

echo.
echo Done. Core stack is started in two projects:
echo - database (kingbase)
echo - wind-power-deployment (minio/pgadmin)
exit /b 0
