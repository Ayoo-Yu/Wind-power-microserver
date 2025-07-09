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

REM 切换到D盘
d:

REM 启动后端（在新窗口中运行）
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\backend && call conda activate wind-power-env && python app.py"

REM 启动后端（在新窗口中运行）
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\backend-autopredict && call conda activate wind-power-env && python app.py"

REM 启动前端（在新窗口中运行）
start cmd /k "chcp 65001 > nul && cd /d D:\my-vue-project\wind-power-forecast\frontend && set NODE_OPTIONS=--trace-deprecation && npm run serve"

REM 提示用户
echo 前后端服务启动中，请稍等...
echo 后端将在: http://localhost:5000
echo 前端将在: http://localhost:8080
echo.
echo 按任意键关闭此窗口...
pause > nul
exit 