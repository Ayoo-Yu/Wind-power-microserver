@echo off
chcp 65001 > nul

REM Local infrastructure
SET DB_HOST=localhost
SET DB_PORT=54321
SET DB_USER=system
SET DB_PASSWORD=12345678ab
SET DB_NAME=windpower
SET MINIO_ENDPOINT=localhost
SET MINIO_PORT=9900

REM Local service ports (avoid restricted 500x ports on some Windows setups)
SET MAIN_APP_HOST=127.0.0.1
SET MAIN_APP_PORT=18080
SET AUTO_APP_HOST=127.0.0.1
SET AUTO_APP_PORT=18081
SET APP_DEBUG=false

REM Frontend dev proxy target ports
SET MAIN_BACKEND_PORT=%MAIN_APP_PORT%
SET AUTO_BACKEND_PORT=%AUTO_APP_PORT%

REM Python executables in D drive local envs
SET MAIN_PY=D:\my-vue-project\wind-power-forecast\backend\wind-power-env\python.exe
SET AUTO_PY=D:\my-vue-project\wind-power-forecast\backend-autopredict\wind-power-env\python.exe

d:

REM Wait for infra dependencies to be ready before starting backends
CALL :wait_tcp %DB_HOST% %DB_PORT% Kingbase
IF ERRORLEVEL 1 (
  echo [ERROR] Kingbase is not ready. Abort startup.
  pause
  exit /b 1
)

CALL :wait_http http://%MINIO_ENDPOINT%:%MINIO_PORT% MinIO
IF ERRORLEVEL 1 (
  echo [ERROR] MinIO is not ready. Abort startup.
  pause
  exit /b 1
)

REM Start main backend
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\backend && set DB_HOST=%DB_HOST% && set DB_PORT=%DB_PORT% && set DB_USER=%DB_USER% && set DB_PASSWORD=%DB_PASSWORD% && set DB_NAME=%DB_NAME% && set MINIO_ENDPOINT=%MINIO_ENDPOINT% && set MINIO_PORT=%MINIO_PORT% && set APP_HOST=%MAIN_APP_HOST% && set APP_PORT=%MAIN_APP_PORT% && set APP_DEBUG=%APP_DEBUG% && set PYTHONIOENCODING=utf-8 && %MAIN_PY% app.py"

REM Start autopredict backend
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\backend-autopredict && set DB_HOST=%DB_HOST% && set DB_PORT=%DB_PORT% && set DB_USER=%DB_USER% && set DB_PASSWORD=%DB_PASSWORD% && set DB_NAME=%DB_NAME% && set MINIO_ENDPOINT=%MINIO_ENDPOINT% && set MINIO_PORT=%MINIO_PORT% && set APP_HOST=%AUTO_APP_HOST% && set APP_PORT=%AUTO_APP_PORT% && set APP_DEBUG=%APP_DEBUG% && set PYTHONIOENCODING=utf-8 && %AUTO_PY% app.py"

REM Start frontend
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\frontend && set NODE_OPTIONS=--trace-deprecation && set MAIN_BACKEND_PORT=%MAIN_BACKEND_PORT% && set AUTO_BACKEND_PORT=%AUTO_BACKEND_PORT% && npm run serve"

echo Services are starting...
echo Main backend:  http://%MAIN_APP_HOST%:%MAIN_APP_PORT%
echo Auto backend:  http://%AUTO_APP_HOST%:%AUTO_APP_PORT%
echo Frontend:      http://localhost:8080
echo.
pause > nul
exit

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

:wait_http
set "_url=%~1"
set "_name=%~2"
set /a "_elapsed=0"
set /a "_max_wait=90"

echo [INFO] Waiting for %_name% (%_url%)...
:wait_http_loop
for /f %%i in ('curl.exe -s -o NUL -w "%%{http_code}" "%_url%"') do set "_http_code=%%i"
if "%_http_code%"=="200" (
  echo [OK] %_name% is ready (HTTP %_http_code%).
  exit /b 0
)
if "%_http_code%"=="400" (
  echo [OK] %_name% is ready (HTTP %_http_code%).
  exit /b 0
)
if "%_http_code%"=="403" (
  echo [OK] %_name% is ready (HTTP %_http_code%).
  exit /b 0
)
if %_elapsed% GEQ %_max_wait% (
  echo [ERROR] Timeout waiting for %_name%, last HTTP code: %_http_code%
  exit /b 1
)
timeout /t 2 > nul
set /a "_elapsed+=2"
goto :wait_http_loop
