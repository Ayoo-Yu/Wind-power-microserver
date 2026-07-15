@echo off
chcp 65001 > nul
setlocal

set "SCADA_TEST_UPDATE_INTERVAL_SECONDS=10"
set "SCADA_REALTIME_ENABLED=true"
set "SCADA_TIMESTAMP_POLICY=floor_quarter"

call "%~dp0start-scada-test.bat"
if errorlevel 1 exit /b 1

call "%~dp0start-local.bat"
if errorlevel 1 (
  echo [ERROR] 本地业务服务启动失败。
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\configure-scada-test.ps1"
if errorlevel 1 (
  echo [ERROR] 本地后端未能接入 SCADA 测试环境。
  pause
  exit /b 1
)

echo [OK] 风电预测开发环境与 SCADA 测试链路均已启动。
echo C104:   127.0.0.1:12404
echo Backend: http://127.0.0.1:18080
echo Frontend: http://127.0.0.1:8080
exit /b 0
