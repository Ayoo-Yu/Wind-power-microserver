@echo off
chcp 65001 > nul
setlocal

call "%~dp0db.bat" status
set "EXIT_CODE=%ERRORLEVEL%"

if not "%DB_NO_PAUSE%"=="true" pause
exit /b %EXIT_CODE%
