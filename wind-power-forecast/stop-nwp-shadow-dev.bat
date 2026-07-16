@echo off
chcp 65001 > nul
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local-process-manager.ps1" -Action stop -Service nwp-shadow
if errorlevel 1 (
  echo [ERROR] NWP 影子适配器停止失败。
  pause
  exit /b 1
)
echo [OK] NWP 影子适配器已停止。
exit /b 0
