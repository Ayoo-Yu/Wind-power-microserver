@echo off
chcp 65001 > nul
setlocal

set "PROJECT_DIR=%~dp0"
set "COMPOSE_FILE=%PROJECT_DIR%compose.local-infra.yaml"
set "COMPOSE_PROJECT=wind-power-local"
set "ACTION=%~1"
if not defined LOCAL_DB_USER set "LOCAL_DB_USER=system"
set "LOCAL_DB_NAME=windpower"

if not defined ACTION set "ACTION=status"

docker version > nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker is unavailable. Start Docker Desktop and run this script again.
  exit /b 1
)

if /I "%ACTION%"=="start" goto :start
if /I "%ACTION%"=="stop" goto :stop
if /I "%ACTION%"=="status" goto :status
if /I "%ACTION%"=="logs" goto :logs
if /I "%ACTION%"=="tools" goto :tools
goto :usage

:start
docker compose -p "%COMPOSE_PROJECT%" -f "%COMPOSE_FILE%" up -d --wait --wait-timeout 120 kingbase redis
if errorlevel 1 exit /b 1
call :ensure_database
exit /b %ERRORLEVEL%

:stop
docker compose -p "%COMPOSE_PROJECT%" -f "%COMPOSE_FILE%" --profile tools stop
exit /b %ERRORLEVEL%

:status
docker compose -p "%COMPOSE_PROJECT%" -f "%COMPOSE_FILE%" --profile tools ps
exit /b %ERRORLEVEL%

:logs
docker compose -p "%COMPOSE_PROJECT%" -f "%COMPOSE_FILE%" logs -f --tail 200 kingbase redis
exit /b %ERRORLEVEL%

:tools
docker compose -p "%COMPOSE_PROJECT%" -f "%COMPOSE_FILE%" --profile tools up -d --wait --wait-timeout 120 pgadmin
if errorlevel 1 exit /b 1
echo [OK] pgAdmin: http://localhost:5050
exit /b 0

:usage
echo Usage: %~nx0 start^|stop^|status^|logs^|tools
exit /b 2

:ensure_database
set "DATABASE_EXISTS="
for /f "tokens=*" %%r in ('docker compose -p "%COMPOSE_PROJECT%" -f "%COMPOSE_FILE%" exec -T kingbase /home/kingbase/install/kingbase/bin/ksql -U%LOCAL_DB_USER% -d test -tAc "SELECT 1 FROM pg_database WHERE datname='%LOCAL_DB_NAME%';" 2^>nul') do (
  if "%%r"=="1" set "DATABASE_EXISTS=1"
)
if defined DATABASE_EXISTS (
  echo [OK] Database %LOCAL_DB_NAME% is ready.
  exit /b 0
)

echo [INFO] Creating database %LOCAL_DB_NAME%...
docker compose -p "%COMPOSE_PROJECT%" -f "%COMPOSE_FILE%" exec -T kingbase /home/kingbase/install/kingbase/bin/ksql -U%LOCAL_DB_USER% -d test -c "CREATE DATABASE %LOCAL_DB_NAME%;"
if errorlevel 1 exit /b 1
echo [OK] Database %LOCAL_DB_NAME% created.
exit /b 0
