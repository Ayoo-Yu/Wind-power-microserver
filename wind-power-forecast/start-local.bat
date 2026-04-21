@echo off
chcp 65001 > nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR:~0,-1%"
set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "AUTO_BACKEND_DIR=%PROJECT_DIR%\backend-autopredict"
set "FRONTEND_DIR=%PROJECT_DIR%\frontend"

REM Local infrastructure
set "DB_HOST=localhost"
set "DB_PORT=15432"
set "DB_USER=system"
set "DB_PASSWORD=12345678ab"
set "DB_NAME=windpower"
set "MINIO_ENDPOINT=localhost"
set "MINIO_PORT=9900"
set "MINIO_ENABLED=false"
set "MINIO_REQUIRED=false"
set "MINIO_CONNECT_RETRIES=1"
set "MINIO_CONNECT_RETRY_DELAY=1"
set "METRICS_ENABLED=false"
set "SECRET_KEY=local-dev-secret-key-do-not-use-in-prod"

REM Local service ports (avoid restricted 500x ports on some Windows setups)
set "MAIN_APP_HOST=127.0.0.1"
set "MAIN_APP_PORT=18080"
set "AUTO_APP_HOST=127.0.0.1"
set "AUTO_APP_PORT=18081"
set "APP_DEBUG=false"

REM Frontend dev proxy target ports
set "MAIN_BACKEND_PORT=%MAIN_APP_PORT%"
set "AUTO_BACKEND_PORT=%AUTO_APP_PORT%"

call :resolve_python MAIN_PY "%BACKEND_DIR%\wind-power-env\python.exe" "D:\my-vue-project\wind-power-forecast\backend\wind-power-env\python.exe"
if errorlevel 1 exit /b 1

call :resolve_python AUTO_PY "%AUTO_BACKEND_DIR%\wind-power-env\python.exe" "D:\my-vue-project\wind-power-forecast\backend-autopredict\wind-power-env\python.exe"
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

if not exist "%AUTO_BACKEND_DIR%\app.py" (
  echo [ERROR] Auto backend entry not found: "%AUTO_BACKEND_DIR%\app.py"
  pause
  exit /b 1
)

if not exist "%FRONTEND_DIR%\vue.config.js" (
  echo [ERROR] Frontend directory is incomplete: "%FRONTEND_DIR%"
  pause
  exit /b 1
)

REM Release local backend ports if occupied by stale processes
CALL :free_port %MAIN_APP_PORT% MainBackend
CALL :free_port %AUTO_APP_PORT% AutoPredictBackend
CALL :free_port 8080 Frontend

REM Wait for infra dependencies to be ready before starting backends
CALL :wait_tcp %DB_HOST% %DB_PORT% Kingbase
IF ERRORLEVEL 1 (
  echo [ERROR] Kingbase is not ready. Abort startup.
  pause
  exit /b 1
)

REM Seed farms and historical data
echo [INFO] Running seed script...
cd /D "%BACKEND_DIR%" && set DB_HOST=%DB_HOST% && set DB_PORT=%DB_PORT% && set DB_USER=%DB_USER% && set DB_PASSWORD=%DB_PASSWORD% && set DB_NAME=%DB_NAME% && ""%MAIN_PY%"" seed_farms.py
echo [OK] Seed data initialized.

REM Start main backend
start "Main Backend" /D "%BACKEND_DIR%" cmd /k "chcp 65001 > nul && set DB_HOST=%DB_HOST% && set DB_PORT=%DB_PORT% && set DB_USER=%DB_USER% && set DB_PASSWORD=%DB_PASSWORD% && set DB_NAME=%DB_NAME% && set MINIO_ENDPOINT=%MINIO_ENDPOINT% && set MINIO_PORT=%MINIO_PORT% && set MINIO_ENABLED=%MINIO_ENABLED% && set MINIO_REQUIRED=%MINIO_REQUIRED% && set MINIO_CONNECT_RETRIES=%MINIO_CONNECT_RETRIES% && set MINIO_CONNECT_RETRY_DELAY=%MINIO_CONNECT_RETRY_DELAY% && set METRICS_ENABLED=%METRICS_ENABLED% && set SECRET_KEY=%SECRET_KEY% && set APP_HOST=%MAIN_APP_HOST% && set APP_PORT=%MAIN_APP_PORT% && set APP_DEBUG=%APP_DEBUG% && set PYTHONIOENCODING=utf-8 && ""%MAIN_PY%"" app.py"

REM Start autopredict backend
start "AutoPredict Backend" /D "%AUTO_BACKEND_DIR%" cmd /k "chcp 65001 > nul && set DB_HOST=%DB_HOST% && set DB_PORT=%DB_PORT% && set DB_USER=%DB_USER% && set DB_PASSWORD=%DB_PASSWORD% && set DB_NAME=%DB_NAME% && set MINIO_ENDPOINT=%MINIO_ENDPOINT% && set MINIO_PORT=%MINIO_PORT% && set MINIO_ENABLED=%MINIO_ENABLED% && set MINIO_REQUIRED=%MINIO_REQUIRED% && set MINIO_CONNECT_RETRIES=%MINIO_CONNECT_RETRIES% && set MINIO_CONNECT_RETRY_DELAY=%MINIO_CONNECT_RETRY_DELAY% && set METRICS_ENABLED=%METRICS_ENABLED% && set SECRET_KEY=%SECRET_KEY% && set APP_HOST=%AUTO_APP_HOST% && set APP_PORT=%AUTO_APP_PORT% && set APP_DEBUG=%APP_DEBUG% && set PYTHONIOENCODING=utf-8 && ""%AUTO_PY%"" app.py"

REM Wait for backend ports to be ready before launching frontend
CALL :wait_tcp %MAIN_APP_HOST% %MAIN_APP_PORT% MainBackend
IF ERRORLEVEL 1 (
  echo [ERROR] Main backend is not ready. Abort frontend startup.
  pause
  exit /b 1
)

CALL :wait_tcp %AUTO_APP_HOST% %AUTO_APP_PORT% AutoPredictBackend
IF ERRORLEVEL 1 (
  echo [ERROR] AutoPredict backend is not ready. Abort frontend startup.
  pause
  exit /b 1
)

REM Start frontend
if defined FRONTEND_CMD (
  start "Frontend" /D "%FRONTEND_DIR%" cmd /k "chcp 65001 > nul && set NODE_OPTIONS=--trace-deprecation && set MAIN_BACKEND_PORT=%MAIN_BACKEND_PORT% && set AUTO_BACKEND_PORT=%AUTO_BACKEND_PORT% && %FRONTEND_CMD%"
) else (
  echo [WARN] Frontend startup skipped. Neither package.json nor vue-cli-service.cmd was found.
)

echo Services are starting...
echo Main backend:  http://%MAIN_APP_HOST%:%MAIN_APP_PORT%
echo Auto backend:  http://%AUTO_APP_HOST%:%AUTO_APP_PORT%
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
if exist "%~3" (
  set "%~1=%~3"
  echo [WARN] Using fallback Python: %~3
  exit /b 0
)
for /f "delims=" %%p in ('where python 2^>nul') do (
  set "%~1=%%p"
  echo [WARN] Using system Python: %%p
  exit /b 0
)
echo [ERROR] Python executable not found for %~1.
echo         Checked:
echo         %~2
echo         %~3
pause
exit /b 1

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
