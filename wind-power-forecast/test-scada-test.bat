@echo off
chcp 65001 > nul
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\scada-test.ps1" -Action test
if errorlevel 1 (
  echo [ERROR] SCADA 独立测试环境验收失败。
  pause
  exit /b 1
)
echo [OK] SCADA 独立测试环境验收通过。
exit /b 0
