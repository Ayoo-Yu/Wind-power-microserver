@echo off
chcp 65001 > nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR:~0,-1%"
set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "FRONTEND_DIR=%PROJECT_DIR%\frontend"
set "LOCAL_INFRA_COMPOSE=%PROJECT_DIR%\compose.local-infra.yaml"
set "LOCAL_INFRA_MANAGER=%PROJECT_DIR%\manage-local-infra.bat"
set "LOCAL_PROCESS_MANAGER=%PROJECT_DIR%\scripts\local-process-manager.ps1"

REM Local infrastructure
set "DB_HOST=localhost"
if not defined LOCAL_DB_PORT set "LOCAL_DB_PORT=15432"
if not defined LOCAL_DB_USER set "LOCAL_DB_USER=system"
if not defined LOCAL_DB_PASSWORD set "LOCAL_DB_PASSWORD=12345678ab"
set "DB_PORT=%LOCAL_DB_PORT%"
set "DB_USER=%LOCAL_DB_USER%"
set "DB_PASSWORD=%LOCAL_DB_PASSWORD%"
set "DB_NAME=windpower"
set "DB_SCHEMA_STRICT=true"
set "METRICS_ENABLED=false"
set "ACTUAL_POWER_RAW_FALLBACK_MAX_AGE_SECONDS=900"
set "ACTUAL_POWER_TURBINE_SOURCE_UNIT=kW"
if not defined LOCAL_SECRET_KEY set "LOCAL_SECRET_KEY=local-dev-secret-key-do-not-use-in-prod"
set "SECRET_KEY=%LOCAL_SECRET_KEY%"
set "JWT_SECRET_KEY=%LOCAL_SECRET_KEY%"
if not defined LOCAL_CREDENTIAL_ENCRYPTION_KEY set "LOCAL_CREDENTIAL_ENCRYPTION_KEY=local-dev-credential-encryption-key-32-chars"
set "CREDENTIAL_ENCRYPTION_KEY=%LOCAL_CREDENTIAL_ENCRYPTION_KEY%"
set "CREDENTIAL_ENCRYPTION_KEY_FILE="
if not defined LOCAL_FARM_CATALOG_ENABLED set "LOCAL_FARM_CATALOG_ENABLED=false"

REM Redis and Celery
set "REDIS_HOST=localhost"
if not defined LOCAL_REDIS_PORT set "LOCAL_REDIS_PORT=6379"
set "REDIS_PORT=%LOCAL_REDIS_PORT%"
set "CELERY_BROKER_URL=redis://%REDIS_HOST%:%REDIS_PORT%/0"
set "CELERY_RESULT_BACKEND=redis://%REDIS_HOST%:%REDIS_PORT%/0"
set "CELERY_BEAT_RELOAD_INTERVAL_SEC=30"
if not defined INTEGRATION_SPOOL_DIR set "INTEGRATION_SPOOL_DIR=%BACKEND_DIR%\runtime\integration"

REM Local service ports
set "MAIN_APP_HOST=127.0.0.1"
set "MAIN_APP_PORT=18080"
set "APP_DEBUG=false"

REM 前端开发代理使用主后端端口。
set "MAIN_BACKEND_PORT=%MAIN_APP_PORT%"
set "API_BASE_URL=http://%MAIN_APP_HOST%:%MAIN_APP_PORT%"
set "SCADA_BACKEND_URL=http://%MAIN_APP_HOST%:%MAIN_APP_PORT%"
set "APP_HOST=%MAIN_APP_HOST%"
set "APP_PORT=%MAIN_APP_PORT%"
set "PYTHONIOENCODING=utf-8"
set "NODE_OPTIONS=--trace-deprecation"

call :resolve_python MAIN_PY "%BACKEND_DIR%\wind-power-env\python.exe"
if errorlevel 1 exit /b 1

"%MAIN_PY%" -c "import alembic" > nul 2>&1
if errorlevel 1 (
  echo [ERROR] Alembic is missing from the selected Python environment.
  echo         Run: "%MAIN_PY%" -m pip install alembic==1.14.1
  pause
  exit /b 1
)

set "FRONTEND_CMD="
if exist "%FRONTEND_DIR%\package.json" (
  set "FRONTEND_CMD=npm run serve"
) else if exist "%FRONTEND_DIR%\node_modules\.bin\vite.cmd" (
  set "FRONTEND_CMD=%FRONTEND_DIR%\node_modules\.bin\vite.cmd"
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

if not exist "%FRONTEND_DIR%\vite.config.mjs" (
  echo [ERROR] Frontend directory is incomplete: "%FRONTEND_DIR%"
  pause
  exit /b 1
)

if not exist "%LOCAL_INFRA_COMPOSE%" (
  echo [ERROR] Local infrastructure compose file not found: "%LOCAL_INFRA_COMPOSE%"
  pause
  exit /b 1
)

if not exist "%LOCAL_INFRA_MANAGER%" (
  echo [ERROR] Local infrastructure manager not found: "%LOCAL_INFRA_MANAGER%"
  pause
  exit /b 1
)

if not exist "%LOCAL_PROCESS_MANAGER%" (
  echo [ERROR] Local process manager not found: "%LOCAL_PROCESS_MANAGER%"
  pause
  exit /b 1
)

if /I "%START_LOCAL_VALIDATE_ONLY%"=="true" (
  echo [OK] start-local.bat validation passed.
  exit /b 0
)

REM 关闭由本项目上一次启动并记录的本地进程。
powershell -NoProfile -ExecutionPolicy Bypass -File "%LOCAL_PROCESS_MANAGER%" -Action stop -Service all
IF ERRORLEVEL 1 (
  echo [ERROR] Failed to stop stale local processes.
  pause
  exit /b 1
)

REM 发现未知进程占用端口时终止启动，避免误杀其他开发服务。
CALL :require_free_port %MAIN_APP_PORT% MainBackend
IF ERRORLEVEL 1 (
  pause
  exit /b 1
)
CALL :require_free_port 8080 Frontend
IF ERRORLEVEL 1 (
  pause
  exit /b 1
)

REM 启动本地基础设施并等待健康检查通过。
CALL :ensure_local_infra
IF ERRORLEVEL 1 (
  echo [ERROR] Local infrastructure is not ready. Abort startup.
  pause
  exit /b 1
)

REM 在启动业务进程前完成数据库初始化、纳管或版本升级。
echo [INFO] Preparing database schema...
cd /D "%BACKEND_DIR%" && set DB_HOST=%DB_HOST% && set DB_PORT=%DB_PORT% && set DB_USER=%DB_USER% && set DB_PASSWORD=%DB_PASSWORD% && set DB_NAME=%DB_NAME% && ""%MAIN_PY%"" manage_db.py prepare
IF ERRORLEVEL 1 (
  echo [ERROR] Database schema preparation failed.
  pause
  exit /b 1
)

echo [INFO] Initializing local roles and administrator...
cd /D "%BACKEND_DIR%" && set DB_HOST=%DB_HOST% && set DB_PORT=%DB_PORT% && set DB_USER=%DB_USER% && set DB_PASSWORD=%DB_PASSWORD% && set DB_NAME=%DB_NAME% && ""%MAIN_PY%"" -m init_users
IF ERRORLEVEL 1 (
  echo [ERROR] Local user initialization failed.
  pause
  exit /b 1
)

REM SCADA 开发环境可显式补充场站目录，普通本地启动不写入业务数据。
if /I "%LOCAL_FARM_CATALOG_ENABLED%"=="true" (
  echo [INFO] Preparing local SCADA farm catalog...
  cd /D "%BACKEND_DIR%" && set DB_HOST=%DB_HOST% && set DB_PORT=%DB_PORT% && set DB_USER=%DB_USER% && set DB_PASSWORD=%DB_PASSWORD% && set DB_NAME=%DB_NAME% && ""%MAIN_PY%"" provision_local_farms.py
  IF ERRORLEVEL 1 (
    echo [ERROR] Local SCADA farm catalog preparation failed.
    pause
    exit /b 1
  )
  echo [OK] Local SCADA farm catalog is ready.
) else (
  echo [INFO] Local startup will not create farm catalog or synthetic business data.
)

REM Start merged backend.
CALL :start_local_process backend
IF ERRORLEVEL 1 (
  pause
  exit /b 1
)

REM Start Celery worker. Use solo pool for Windows local development.
CALL :start_local_process worker
IF ERRORLEVEL 1 (
  pause
  exit /b 1
)

REM Start Celery beat with DB-backed schedule reload.
CALL :start_local_process beat
IF ERRORLEVEL 1 (
  pause
  exit /b 1
)

REM NWP 输入启用时启动统一接入业务处理器。
if /I "%NWP_INGESTION_ENABLED%"=="true" (
  if not defined NWP_INPUT_ROOT (
    echo [ERROR] NWP_INPUT_ROOT is required when NWP_INGESTION_ENABLED=true.
    pause
    exit /b 1
  )
  if not defined NWP_FARM_CODES (
    echo [ERROR] NWP_FARM_CODES is required when NWP_INGESTION_ENABLED=true.
    pause
    exit /b 1
  )
  if /I "%NWP_ETEXT_SHADOW_ENABLED%"=="true" (
    CALL :start_local_process nwp-shadow
    IF ERRORLEVEL 1 (
      pause
      exit /b 1
    )
  )
  CALL :start_local_process integration
  IF ERRORLEVEL 1 (
    pause
    exit /b 1
  )
)

REM Wait for backend before launching frontend.
CALL :wait_tcp %MAIN_APP_HOST% %MAIN_APP_PORT% Backend
IF ERRORLEVEL 1 (
  echo [ERROR] Backend is not ready. Abort frontend startup.
  pause
  exit /b 1
)

REM SCADA 启用时启动独立管理进程。
if /I "%SCADA_REALTIME_ENABLED%"=="true" (
  CALL :start_local_process scada-manager
  IF ERRORLEVEL 1 (
    pause
    exit /b 1
  )
)

REM Start frontend.
if defined FRONTEND_CMD (
  CALL :start_local_process frontend
  IF ERRORLEVEL 1 (
    pause
    exit /b 1
  )
) else (
  echo [WARN] Frontend startup skipped. Neither package.json nor vite.cmd was found.
)

echo Services are starting...
echo Backend:       http://%MAIN_APP_HOST%:%MAIN_APP_PORT%
echo Celery worker: local console window
echo Celery beat:   local console window
echo KingBase:      %DB_HOST%:%DB_PORT%
echo Redis:         %REDIS_HOST%:%REDIS_PORT%
echo Frontend:      http://localhost:8080
if /I "%NWP_ETEXT_SHADOW_ENABLED%"=="true" echo NWP shadow:    %NWP_ETEXT_INPUT_DIR%
echo Infrastructure management: manage-local-infra.bat status^|stop^|logs^|tools
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

:ensure_local_infra
echo [INFO] Starting local KingBase and Redis...
call "%LOCAL_INFRA_MANAGER%" start
IF ERRORLEVEL 1 (
  echo [ERROR] Failed to start or prepare the local infrastructure.
  exit /b 1
)
echo [OK] Local infrastructure is healthy.
exit /b 0

:start_local_process
powershell -NoProfile -ExecutionPolicy Bypass -File "%LOCAL_PROCESS_MANAGER%" -Action start -Service %~1
if errorlevel 1 (
  echo [ERROR] Failed to start local process: %~1
  exit /b 1
)
exit /b 0

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
powershell -NoProfile -Command "Start-Sleep -Seconds 2"
set /a "_elapsed+=2"
goto :wait_tcp_loop

:require_free_port
set "_target_port=%~1"
set "_target_name=%~2"

echo [INFO] Checking %_target_name% port (%_target_port%)...
for /f %%p in ('powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %_target_port% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"') do (
  echo [ERROR] Port %_target_port% is occupied by unknown PID %%p.
  echo         Stop that process or configure another local port before retrying.
  exit /b 1
)
exit /b 0
