@echo off
REM 风功率预测系统 - 快速启动工具（修复版）
REM 解决乱码和运行失败问题

:: 设置控制台代码页为UTF-8
chcp 65001 >nul 2>&1

:: 设置标题
title 风功率预测系统启动工具

echo ========================================
echo 风功率预测系统 - 快速启动工具
echo ========================================
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo 错误：请以管理员身份运行此脚本
    echo    右键点击脚本，选择"以管理员身份运行"
    pause
    exit /b 1
)

:: 检查Docker
where docker >nul 2>&1
if %errorLevel% neq 0 (
    echo 错误：Docker未安装
    echo 请访问：https://docs.docker.com/desktop/install/windows-install/
    pause
    exit /b 1
)

:: 检查Docker Compose
where docker-compose >nul 2>&1
if %errorLevel% neq 0 (
    echo 错误：Docker Compose未安装
    echo 请确保Docker Desktop已正确安装
    pause
    exit /b 1
)

echo [√] 环境检查通过
echo.

:: 主菜单
:menu
echo 请选择启动模式：
echo 1. 开发环境（推荐）- 快速体验所有功能
echo 2. 微服务架构 - 企业级完整部署
echo 3. 仅基础设施 - 数据库和中间件
echo 4. 系统状态检查
echo 5. 停止所有服务
echo 6. 查看日志
echo 7. 退出
echo.

set /p choice=请输入选项（1-7）：

if "%choice%"=="1" goto dev_env
if "%choice%"=="2" goto microservices
if "%choice%"=="3" goto infrastructure
if "%choice%"=="4" goto status_check
if "%choice%"=="5" goto stop_all
if "%choice%"=="6" goto view_logs
if "%choice%"=="7" goto end

echo 无效选项，请重新输入
goto menu

:: 开发环境启动
:dev_env
echo 正在启动开发环境...

if not exist "wind-power-forecast" (
    echo 错误：未找到wind-power-forecast目录
    echo 请确保在项目根目录运行此脚本
    pause
    goto menu
)

cd wind-power-forecast

:: 检查配置文件
if not exist ".env" (
    echo 创建默认配置文件...
    if exist ".env.example" (
        copy .env.example .env >nul 2>&1
    ) else (
        echo 警告：未找到.env.example文件
    )
)

echo 启动基础设施服务...
start cmd /k "title 基础设施服务 && docker-compose -f database\docker-compose.yaml up"
timeout /t 30 /nobreak >nul

echo 启动应用服务...

:: 检查Node.js并启动前端
where npm >nul 2>&1
if %errorLevel% equ 0 (
    echo 启动前端服务...
    start cmd /k "title 前端服务 && cd frontend && npm install && npm run dev"
) else (
    echo 警告：Node.js未安装，跳过前端服务
)

:: 检查Python并启动后端
where python >nul 2>&1
if %errorLevel% equ 0 (
    echo 启动后端服务...
    start cmd /k "title 后端服务 && cd backend && pip install -r requirements.txt && python app.py"
) else (
    echo 警告：Python未安装，跳过后端服务
)

echo [√] 开发环境启动完成！
echo.
echo 访问地址：
echo  前端应用: http://localhost:8080
echo  后端API:  http://localhost:5000
echo  数据库管理: http://localhost:5050
echo  文件存储: http://localhost:9001
echo.
echo 服务启动需要30-60秒
echo 按任意键返回主菜单
pause >nul
goto menu

:: 微服务架构启动
:microservices
echo 正在启动微服务架构...

if not exist "wind-power-microservices" (
    echo 错误：未找到wind-power-microservices目录
    pause
    goto menu
)

cd wind-power-microservices

echo 启动基础设施...
start cmd /k "title 基础设施 && docker-compose up"
timeout /t 60 /nobreak >nul

echo [√] 微服务架构启动完成！
echo.
echo 访问地址：
echo  API网关:   http://localhost:8000
echo  Grafana:   http://localhost:3000
echo  Kafka UI:  http://localhost:8090
echo  Prometheus: http://localhost:9090
echo.
echo 服务启动需要1-2分钟
echo 按任意键返回主菜单
pause >nul
goto menu

:: 仅基础设施
:infrastructure
echo 正在启动基础设施...

if not exist "wind-power-forecast" (
    echo 错误：未找到wind-power-forecast目录
    pause
    goto menu
)

cd wind-power-forecast
start cmd /k "title 基础设施 && docker-compose -f database\docker-compose.yaml up"
echo [√] 基础设施启动完成！
echo 按任意键返回主菜单
pause >nul
goto menu

:: 系统状态检查
:status_check
echo 正在检查系统状态...
echo.

:: 检查Docker服务
echo 1. Docker服务状态：
docker version >nul 2>&1
if %errorLevel% equ 0 (
    echo    [√] Docker运行正常
) else (
    echo    [×] Docker未运行
)

:: 检查容器状态
echo.
echo 2. 容器运行状态：
docker ps --format "table {{.Names}}	{{.Status}}	{{.Ports}}" 2>nul || echo    无运行中的容器

:: 检查端口占用
echo.
echo 3. 端口占用检查：
netstat -an | findstr ":8080 :5000 :8000 :3000" >nul 2>&1
if %errorLevel% equ 0 (
    echo    [√] 系统端口已监听
) else (
    echo    [!] 系统端口未监听
)

echo.
echo 按任意键返回主菜单
pause >nul
goto menu

:: 停止所有服务
:stop_all
echo 正在停止所有服务...

:: 停止开发环境服务
taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

:: 停止Docker容器
if exist "wind-power-forecast" (
    cd wind-power-forecast
    docker-compose -f database\docker-compose.yaml down >nul 2>&1
    cd ..
)

if exist "wind-power-microservices" (
    cd wind-power-microservices
    docker-compose down >nul 2>&1
    cd ..
)

echo [√] 所有服务已停止
echo 按任意键返回主菜单
pause >nul
goto menu

:: 查看日志
:view_logs
echo 日志查看选项：
echo 1. 前端日志
echo 2. 后端日志
echo 3. Docker容器日志
echo 4. 返回主菜单
echo.

set /p log_choice=请输入选项（1-4）：

if "%log_choice%"=="1" (
    echo 前端日志：
    type wind-power-forecast\frontend\logs\app.log 2>nul || echo 日志文件不存在
)
if "%log_choice%"=="2" (
    echo 后端日志：
    type wind-power-forecast\backend\logs\app.log 2>nul || echo 日志文件不存在
)
if "%log_choice%"=="3" (
    echo Docker容器日志：
    docker ps --format "{{.Names}}" 2>nul
    echo.
    set /p container_name=请输入容器名称：
    docker logs %container_name% --tail 50
)
if "%log_choice%"=="4" goto menu

echo 按任意键返回主菜单
pause >nul
goto menu

:: 退出
:end
echo 感谢使用风功率预测系统！
echo 详细使用指南请查看：PROJECT_DOCUMENTATION.md
echo 运维手册请查看：OPERATIONS_MANUAL.md
pause
exit /b 0