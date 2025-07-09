@echo off
chcp 65001 > nul
echo Starting continuous database connection monitoring...
echo Press Ctrl+C to stop.
echo.

REM --- Configuration ---
set PROJECT_DIR=D:\my-vue-project\wind-power-forecast
set CONDA_ENV_NAME=env
set DOCKER_CONTAINER_NAME=wind-power-kingbase
set PYTHON_SCRIPT=db_connection_check.py
set CHECK_INTERVAL_SECONDS=30  REM Check every 30 seconds
set DB_START_WAIT_SECONDS=15   REM Wait 15 seconds after attempting DB start

REM --- Setup ---
REM Change to the project directory
cd /d "%PROJECT_DIR%"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to change directory to "%PROJECT_DIR%"
    goto end_error
)
echo Changed directory to: %CD%
echo.

REM Prepare Python environment ONCE
echo Preparing Python environment...
call conda activate %CONDA_ENV_NAME%
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Cannot activate conda environment '%CONDA_ENV_NAME%'.
    echo Please ensure conda is installed and the '%CONDA_ENV_NAME%' environment exists.
    goto end_error
)
echo Conda environment '%CONDA_ENV_NAME%' activated.
echo.

REM --- Monitoring Loop Starts Here ---
:monitor_loop

echo ============================================
echo [%TIME%] Starting check cycle...

REM Check if database service (Docker container) is running
echo [%TIME%] Checking database Docker container '%DOCKER_CONTAINER_NAME%' status...
docker ps | findstr %DOCKER_CONTAINER_NAME% > nul
if %ERRORLEVEL% NEQ 0 (
    echo [%TIME%] WARNING: Database container '%DOCKER_CONTAINER_NAME%' not found or not running. Attempting to start...
    REM Ensure start-docker-db.bat is in the PATH or specify its full/relative path if needed
    call start-docker-db.bat
    if %ERRORLEVEL% NEQ 0 (
        echo [%TIME%] ERROR: Failed to execute start-docker-db.bat. Check the script and Docker setup. Will retry next cycle.
    ) else (
        echo [%TIME%] Waiting %DB_START_WAIT_SECONDS% seconds for database to initialize after start attempt...
        timeout /t %DB_START_WAIT_SECONDS% /nobreak > nul
    )
) else (
    echo [%TIME%] Database container '%DOCKER_CONTAINER_NAME%' appears to be running.
)

REM Execute Python connection check script
echo [%TIME%] Running Python connection check (%PYTHON_SCRIPT%)...
python %PYTHON_SCRIPT%
if %ERRORLEVEL% NEQ 0 (
    echo [%TIME%] WARNING: Python script '%PYTHON_SCRIPT%' exited with error code %ERRORLEVEL%.
) else (
    echo [%TIME%] Python script completed (Check script output for connection status).
)

echo [%TIME%] Check cycle finished.
echo Waiting for %CHECK_INTERVAL_SECONDS% seconds until the next check...
echo ============================================
echo.

REM Wait before the next iteration
timeout /t %CHECK_INTERVAL_SECONDS% /nobreak > nul

REM Jump back to the start of the loop
goto monitor_loop

REM --- End of Script (Reached on error or manual stop) ---
:end_error
echo.
echo ERROR occurred. Monitoring stopped.
goto end_final

:end_final
echo.
echo Script finished or interrupted.
pause REM Optional: Keep window open to see final messages