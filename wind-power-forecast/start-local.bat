@echo off
chcp 65001 > nul
REM 设置环境变量
SET MINIO_ENDPOINT=localhost
SET MINIO_PORT=9900
SET BACKEND_PORT=5111
SET AUTOPREDICT_PORT=5112
SET FRONTEND_PORT=8088

REM 设置conda环境中的Python路径
SET PYTHON_PATH=D:\my-vue-project\wind-power-forecast\backend\wind-power-env\python.exe
SET REDIS_URL=redis://localhost:6379/0
SET CELERY_RESULT_BACKEND=redis://localhost:6379/0
REM 切换到D盘
d:

REM 启动第一个后端 - 直接使用环境中的Python解释器
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\backend && set APP_PORT=%BACKEND_PORT% && "%PYTHON_PATH%" app.py"

REM 启动第二个后端
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\backend-autopredict && set AUTOPREDICT_PORT=%AUTOPREDICT_PORT% && "%PYTHON_PATH%" app.py"

REM 启动前端
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\frontend && set NODE_OPTIONS=--trace-deprecation && npm run serve -- --port %FRONTEND_PORT%"

REM 提示用户
echo 前后端服务启动中，请稍等...
echo 后端将在: http://localhost:%BACKEND_PORT%
echo 前端将在: http://localhost:%FRONTEND_PORT%
echo.
echo 按任意键关闭此窗口...
pause > nul
exit