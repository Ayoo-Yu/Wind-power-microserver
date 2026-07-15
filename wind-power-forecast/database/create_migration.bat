@echo off
chcp 65001 > nul
setlocal

set "MESSAGE=%~1"
if not defined MESSAGE set /p "MESSAGE=Migration description: "
if not defined MESSAGE (
  echo [ERROR] Migration description is required.
  pause
  exit /b 1
)

call "%~dp0db.bat" create "%MESSAGE%"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%DB_NO_PAUSE%"=="true" pause
exit /b %EXIT_CODE%
