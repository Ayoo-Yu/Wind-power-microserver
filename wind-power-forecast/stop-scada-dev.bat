@echo off
chcp 65001 > nul
setlocal

call "%~dp0stop-local.bat"
set "LOCAL_EXIT=%ERRORLEVEL%"
call "%~dp0stop-scada-test.bat"
set "SCADA_EXIT=%ERRORLEVEL%"

if not "%LOCAL_EXIT%"=="0" exit /b %LOCAL_EXIT%
if not "%SCADA_EXIT%"=="0" exit /b %SCADA_EXIT%
echo [OK] 本地开发环境已全部停止。
exit /b 0
