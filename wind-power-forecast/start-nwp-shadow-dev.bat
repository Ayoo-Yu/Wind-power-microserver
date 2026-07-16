@echo off
chcp 65001 > nul
setlocal

set "PROJECT_DIR=%~dp0"
set "MAIN_PY=%PROJECT_DIR%backend\wind-power-env\python.exe"
if not exist "%MAIN_PY%" (
  set "MAIN_PY="
  for /f "delims=" %%p in ('where python 2^>nul') do if not defined MAIN_PY set "MAIN_PY=%%p"
)
if not defined MAIN_PY (
  echo [ERROR] 未找到 Python。
  pause
  exit /b 1
)

set "NWP_ETEXT_INPUT_DIR=%PROJECT_DIR%..\simulation\nwp-shadow\artifacts\etext-inbox"
set "NWP_ETEXT_OUTPUT_ROOT=%PROJECT_DIR%..\simulation\nwp-shadow\artifacts"
set "NWP_ETEXT_CONTRACT=%PROJECT_DIR%config\nwp-etext-contract-v1.json"
if not defined NWP_ETEXT_SEED_FILE set "NWP_ETEXT_SEED_FILE=%PROJECT_DIR%..\data\YCSJ_YN.ZhuYXDC_DQYC_20260504_191500.dat"
set "NWP_ETEXT_REPLAY_LATEST=true"
set "NWP_ETEXT_GENERATE_SEED_IF_MISSING=true"
set "PYTHONIOENCODING=utf-8"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%scripts\local-process-manager.ps1" -Action start -Service nwp-shadow
if errorlevel 1 (
  echo [ERROR] NWP 影子适配器启动失败。
  pause
  exit /b 1
)

echo [OK] NWP 影子适配器已启动。
echo 输入目录: %NWP_ETEXT_INPUT_DIR%
echo 业务目录: %NWP_ETEXT_OUTPUT_ROOT%\business
echo.
echo 将 DQYC 文件复制到输入目录即可触发隔离转换。
pause
exit /b 0
