@echo off
chcp 65001 > nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR:~0,-1%"
set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "FRONTEND_DIR=%PROJECT_DIR%\frontend"

REM Local infrastructure
set "DB_HOST=localhost"
set "DB_PORT=15432"
set "DB_USER=system"
set "DB_PASSWORD=12345678ab"
set "DB_NAME=windpower"
set "METRICS_ENABLED=false"
set "SECRET_KEY=local-dev-secret-key-do-not-use-in-prod"

REM Redis and Celery
set "REDIS_HOST=localhost"
set "REDIS_PORT=6379"
set "CELERY_BROKER_URL=redis://%REDIS_HOST%:%REDIS_PORT%/0"
set "CELERY_RESULT_BACKEND=redis://%REDIS_HOST%:%REDIS_PORT%/0"
set "CELERY_BEAT_RELOAD_INTERVAL_SEC=30"

REM Local service ports
set "MAIN_APP_HOST=127.0.0.1"
set "MAIN_APP_PORT=18080"
set "APP_DEBUG=false"

REM Frontend dev proxy target ports. Keep AUTO_BACKEND_PORT for vue.config.js compatibility.
set "MAIN_BACKEND_PORT=%MAIN_APP_PORT%"
set "AUTO_BACKEND_PORT=%MAIN_APP_PORT%"
set "BACKEND_ENV_CMD=set DB_HOST=%DB_HOST% && set DB_PORT=%DB_PORT% && set DB_USER=%DB_USER% && set DB_PASSWORD=%DB_PASSWORD% && set DB_NAME=%DB_NAME% && set METRICS_ENABLED=%METRICS_ENABLED% && set SECRET_KEY=%SECRET_KEY% && set REDIS_HOST=%REDIS_HOST% && set REDIS_PORT=%REDIS_PORT% && set CELERY_BROKER_URL=%CELERY_BROKER_URL% && set CELERY_RESULT_BACKEND=%CELERY_RESULT_BACKEND% && set CELERY_BEAT_RELOAD_INTERVAL_SEC=%CELERY_BEAT_RELOAD_INTERVAL_SEC% && set API_BASE_URL=http://%MAIN_APP_HOST%:%MAIN_APP_PORT% && set APP_HOST=%MAIN_APP_HOST% && set APP_PORT=%MAIN_APP_PORT% && set APP_DEBUG=%APP_DEBUG% && set PYTHONIOENCODING=utf-8"

call :resolve_python MAIN_PY "%BACKEND_DIR%\wind-power-env\python.exe"
if errorlevel 1 exit /b 1

set "FRONTEND_CMD="
if exist "%FRONTEND_DIR%\package.json" (
  set "FRONTEND_CMD=npm run serve"
) else if exist "%FRONTEND_DIR%\node_modules\.bin\vue-cli-service.cmd" (
  set "FRONTEND_CMD=%FRONTEND_DIR%\node_modules\.bin\vue-cli-service.cmd serve"
)

if not exist "%BACKEND_DIR%\app.py" (
  echo [ERROR] Backend entry not found: "%BACKEND_DIR%\app.py"
  pause
  exit /b 1
)

if not exist "%BACKEND_DIR%\celery_app\__init__.py" (
  echo [ERROR] Celery app not found: "%BACKEND_DIR%\celery_app"
  pause
  exit /b 1
)

if not exist "%FRONTEND_DIR%\vue.config.js" (
  echo [ERROR] Frontend directory is incomplete: "%FRONTEND_DIR%"
  pause
  exit /b 1
)

REM Release stale local app ports.
CALL :free_port %MAIN_APP_PORT% MainBackend
CALL :free_port 8080 Frontend

REM Start Redis locally if port 6379 is not available.
CALL :ensure_redis
IF ERRORLEVEL 1 (
  echo [ERROR] Redis is not ready. Abort startup.
  pause
  exit /b 1
)

REM Wait for database before starting backend and Celery.
CALL :wait_tcp %DB_HOST% %DB_PORT% Kingbase
IF ERRORLEVEL 1 (
  echo [ERROR] Kingbase is not ready. Abort startup.
  pause
  exit /b 1
)

REM Seed farms and historical data.
echo [INFO] Running seed script...
cd /D "%BACKEND_DIR%" && set DB_HOST=%DB_HOST% && set DB_PORT=%DB_PORT% && set DB_USER=%DB_USER% && set DB_PASSWORD=%DB_PASSWORD% && set DB_NAME=%DB_NAME% && ""%MAIN_PY%"" seed_farms.py
IF ERRORLEVEL 1 (
  echo [ERROR] Seed script failed.
  pause
  exit /b 1
)
echo [OK] Seed data initialized.

REM Start merged backend.
start "Backend" /D "%BACKEND_DIR%" cmd /k "chcp 65001 > nul && %BACKEND_ENV_CMD% && ""%MAIN_PY%"" app.py"

REM Start Celery worker. Use solo pool for Windows local development.
start "Celery Worker" /D "%BACKEND_DIR%" cmd /k "chcp 65001 > nul && %BACKEND_ENV_CMD% && ""%MAIN_PY%"" -m celery -A celery_app.celery_app worker --loglevel=info --pool=solo"

REM Start Celery beat with DB-backed schedule reload.
start "Celery Beat" /D "%BACKEND_DIR%" cmd /k "chcp 65001 > nul && %BACKEND_ENV_CMD% && ""%MAIN_PY%"" -m celery -A celery_app.celery_app beat --loglevel=info"

REM Wait for backend before launching frontend.
CALL :wait_tcp %MAIN_APP_HOST% %MAIN_APP_PORT% Backend
IF ERRORLEVEL 1 (
  echo [ERROR] Backend is not ready. Abort frontend startup.
  pause
  exit /b 1
)

REM Start frontend.
if defined FRONTEND_CMD (
  start "Frontend" /D "%FRONTEND_DIR%" cmd /k "chcp 65001 > nul && set NODE_OPTIONS=--trace-deprecation && set MAIN_BACKEND_PORT=%MAIN_BACKEND_PORT% && set AUTO_BACKEND_PORT=%AUTO_BACKEND_PORT% && %FRONTEND_CMD%"
) else (
  echo [WARN] Frontend startup skipped. Neither package.json nor vue-cli-service.cmd was found.
)

echo Services are starting...
echo Backend:       http://%MAIN_APP_HOST%:%MAIN_APP_PORT%
echo Celery worker: local console window
echo Celery beat:   local console window
echo Redis:         %REDIS_HOST%:%REDIS_PORT%
echo Frontend:      http://localhost:8080
echo.
exit /b 0

:resolve_python
set "%~1="
if exist "%~2" (
  set "%~1=%~2"
  echo [OK] Using Python: %~2
  exit /b 0
)
for /f "delims=" %%p in ('where python 2^>nul') do (
  set "%~1=%%p"
  echo [WARN] Using system Python: %%p
  exit /b 0
)
echo [ERROR] Python executable not found for %~1.
echo         Checked: %~2
pause
exit /b 1

:ensure_redis
CALL :check_tcp %REDIS_HOST% %REDIS_PORT%
IF %ERRORLEVEL% EQU 0 exit /b 0

echo [INFO] Redis is not listening. Trying Docker container wind-power-local-redis...
docker version > nul 2>&1
IF ERRORLEVEL 1 (
  echo [ERROR] Docker is not available and Redis is not running on %REDIS_HOST%:%REDIS_PORT%.
  exit /b 1
)

docker start wind-power-local-redis > nul 2>&1
IF ERRORLEVEL 1 (
  docker run -d --name wind-power-local-redis -p %REDIS_PORT%:6379 redis:7-alpine > nul
  IF ERRORLEVEL 1 (
    echo [ERROR] Failed to start Redis container.
    exit /b 1
  )
)

CALL :wait_tcp %REDIS_HOST% %REDIS_PORT% Redis
exit /b %ERRORLEVEL%

:check_tcp
powershell -NoProfile -Command "$c = New-Object Net.Sockets.TcpClient; try { $c.Connect('%~1', %~2); if ($c.Connected) { $c.Close(); exit 0 } else { exit 1 } } catch { exit 1 }"
exit /b %ERRORLEVEL%

:wait_tcp
set "_host=%~1"
set "_port=%~2"
set "_name=%~3"
set /a "_elapsed=0"
set /a "_max_wait=90"

echo [INFO] Waiting for %_name% (%_host%:%_port%)...
:wait_tcp_loop
powershell -NoProfile -Command "$c = New-Object Net.Sockets.TcpClient; try { $c.Connect('%_host%', %_port%); if ($c.Connected) { $c.Close(); exit 0 } else { exit 1 } } catch { exit 1 }"
if %ERRORLEVEL% EQU 0 (
  echo [OK] %_name% is ready.
  exit /b 0
)
if %_elapsed% GEQ %_max_wait% (
  echo [ERROR] Timeout waiting for %_name%.
  exit /b 1
)
timeout /t 2 > nul
set /a "_elapsed+=2"
goto :wait_tcp_loop

:free_port
set "_target_port=%~1"
set "_target_name=%~2"

echo [INFO] Checking %_target_name% port (%_target_port%)...
for /f %%p in ('powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %_target_port% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"') do (
  echo [WARN] Port %_target_port% is occupied by PID %%p, terminating...
  taskkill /PID %%p /F > nul 2>&1
)
exit /b 0
