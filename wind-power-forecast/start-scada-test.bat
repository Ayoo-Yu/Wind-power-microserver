@echo off
chcp 65001 > nul
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\scada-test.ps1" -Action up
if errorlevel 1 (
  echo [ERROR] SCADA 独立测试环境启动失败。
  pause
  exit /b 1
)
echo [OK] SCADA 独立测试环境已启动。
exit /b 0
