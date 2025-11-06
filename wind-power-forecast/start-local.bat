@echo off
chcp 65001 > nul
REM 设置环境变量
SET DB_HOST=localhost
SET DB_PORT=54321
SET DB_USER=system
SET DB_PASSWORD=12345678ab
SET DB_NAME=windpower
SET MINIO_ENDPOINT=localhost
SET MINIO_PORT=9900

REM 设置conda环境中的Python路径
SET PYTHON_PATH=D:\my-vue-project\wind-power-forecast\backend\wind-power-env\python.exe
REDIS_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
REM 切换到D盘
d:

REM 启动第一个后端 - 直接使用环境中的Python解释器
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\backend && "%PYTHON_PATH%" app.py"

REM 启动第二个后端
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\backend-autopredict && "%PYTHON_PATH%" app.py"

REM 启动前端
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\frontend && set NODE_OPTIONS=--trace-deprecation && npm run serve"

REM 提示用户
echo 前后端服务启动中，请稍等...
echo 后端将在: http://localhost:5000
echo 前端将在: http://localhost:8080
echo.
echo 按任意键关闭此窗口...
pause > nul
exit