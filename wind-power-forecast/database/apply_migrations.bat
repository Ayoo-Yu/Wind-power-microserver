@echo off
chcp 65001 > nul
setlocal

call "%~dp0db.bat" upgrade
set "EXIT_CODE=%ERRORLEVEL%"

if not "%DB_NO_PAUSE%"=="true" pause
exit /b %EXIT_CODE%
