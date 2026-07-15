@echo off
chcp 65001 > nul
setlocal

set "PROJECT_DIR=%~dp0.."
set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "PYTHON_EXE="

if exist "%BACKEND_DIR%\wind-power-env\python.exe" set "PYTHON_EXE=%BACKEND_DIR%\wind-power-env\python.exe"
if not defined PYTHON_EXE for /f "delims=" %%p in ('where python 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%p"

if not defined PYTHON_EXE (
  echo [ERROR] Python executable was not found.
  exit /b 1
)

pushd "%PROJECT_DIR%"
"%PYTHON_EXE%" backend\manage_db.py %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
