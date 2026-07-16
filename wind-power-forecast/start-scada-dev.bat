@echo off
chcp 65001 > nul
setlocal

set "SCADA_TEST_UPDATE_INTERVAL_SECONDS=10"
set "SCADA_REALTIME_ENABLED=true"
set "SCADA_REQUIRED=true"
set "SCADA_DATA_STALE_AFTER_SECONDS=60"
set "SCADA_TIMESTAMP_POLICY=floor_quarter"
set "NWP_INGESTION_ENABLED=true"
set "NWP_INGESTION_REQUIRED=true"
set "NWP_FARM_CODES=CF,BNJ,SDS,DPLZ,ZYX"
set "INTEGRATION_SPOOL_DIR=%~dp0backend\runtime\integration"

if not defined NWP_DEV_MODE set "NWP_DEV_MODE=etext-shadow"
if /I "%NWP_DEV_MODE%"=="etext-shadow" (
  set "NWP_ETEXT_SHADOW_ENABLED=true"
  set "NWP_ETEXT_INPUT_DIR=%~dp0..\simulation\nwp-shadow\artifacts\etext-inbox"
  set "NWP_ETEXT_OUTPUT_ROOT=%~dp0..\simulation\nwp-shadow\artifacts"
  set "NWP_ETEXT_CONTRACT=%~dp0config\nwp-etext-contract-v1.json"
  if not defined NWP_ETEXT_SEED_FILE set "NWP_ETEXT_SEED_FILE=%~dp0..\data\YCSJ_YN.ZhuYXDC_DQYC_20260504_191500.dat"
  if not defined NWP_ETEXT_REPLAY_LATEST set "NWP_ETEXT_REPLAY_LATEST=true"
  if not defined NWP_ETEXT_GENERATE_SEED_IF_MISSING set "NWP_ETEXT_GENERATE_SEED_IF_MISSING=true"
  set "NWP_INPUT_ROOT=%~dp0..\simulation\nwp-shadow\artifacts\business"
) else if /I "%NWP_DEV_MODE%"=="long-csv" (
  set "NWP_ETEXT_SHADOW_ENABLED=false"
  set "NWP_INPUT_ROOT=%~dp0..\simulation\scada-test\artifacts\nwp-inbox"
) else (
  echo [ERROR] NWP_DEV_MODE 仅支持 etext-shadow 或 long-csv。
  pause
  exit /b 1
)

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
echo NWP mode: %NWP_DEV_MODE%
echo NWP data: %NWP_INPUT_ROOT%
echo Backend: http://127.0.0.1:18080
echo Frontend: http://127.0.0.1:8080
echo.
if /I not "%SCADA_DEV_NO_PAUSE%"=="true" (
  echo 按任意键关闭启动窗口，后台服务会继续运行。
  pause > nul
)
exit /b 0
