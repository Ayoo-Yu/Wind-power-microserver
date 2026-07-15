@echo off
chcp 65001 > nul
setlocal

set "PROCESS_MANAGER=%~dp0scripts\local-process-manager.ps1"

echo [INFO] Stopping local application processes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROCESS_MANAGER%" -Action stop -Service all
if errorlevel 1 (
  echo [ERROR] Failed to stop local application processes.
  exit /b 1
)
echo [OK] Local application processes stopped.

if /I "%~1"=="all" (
  echo [INFO] Stopping local infrastructure...
  call "%~dp0manage-local-infra.bat" stop
  exit /b %ERRORLEVEL%
)

echo [INFO] KingBase and Redis remain running for faster development restarts.
echo        Run "%~nx0 all" to stop them as well.
exit /b 0
