@echo off
chcp 65001 >nul
echo ========================================
echo KingBase试用期自动续期 - Windows定时任务设置
echo ========================================
echo.

set SCRIPT_PATH=%~dp0kingbase_renewal_windows.py
set LOG_PATH=%~dp0logs
set TASK_NAME=KingBase_Auto_Renewal

echo 当前脚本路径: %SCRIPT_PATH%
echo 日志存储路径: %LOG_PATH%
echo.

:: 创建日志目录
if not exist "%LOG_PATH%" (
    mkdir "%LOG_PATH%"
    echo ✅ 创建日志目录: %LOG_PATH%
)

echo.
echo 📋 全局重建策略说明：
echo    - 极简性：只使用 docker-compose down 和 up
echo    - 可预测性：所有容器都是全新的，状态完全一致
echo    - 可靠性：避免复杂的服务依赖检查逻辑
echo    - 原子性：将整个环境视为一个原子单元
echo.
echo 设置选项：
echo 1. 每天凌晨2点自动续期 (适合测试环境)
echo 2. 每3天凌晨2点自动续期 (推荐生产环境)
echo 3. 每周日凌晨2点自动续期 (轻量级维护)
echo 4. 自定义时间设置
echo 5. 删除现有定时任务
echo 6. 查看当前定时任务状态
echo 7. 手动执行一次测试
echo.
set /p choice=请选择 (1-7): 

if "%choice%"=="1" goto daily
if "%choice%"=="2" goto every3days
if "%choice%"=="3" goto weekly
if "%choice%"=="4" goto custom
if "%choice%"=="5" goto delete
if "%choice%"=="6" goto status
if "%choice%"=="7" goto test
echo 无效选择！
pause
exit /b 1

:daily
echo 设置每天凌晨2点自动续期...
schtasks /create /tn "%TASK_NAME%" /tr "python \"%SCRIPT_PATH%\"" /sc daily /st 02:00 /f
goto success

:every3days
echo 设置每3天凌晨2点自动续期...
schtasks /create /tn "%TASK_NAME%" /tr "python \"%SCRIPT_PATH%\"" /sc daily /mo 3 /st 02:00 /f
goto success

:weekly
echo 设置每周日凌晨2点自动续期...
schtasks /create /tn "%TASK_NAME%" /tr "python \"%SCRIPT_PATH%\"" /sc weekly /d SUN /st 02:00 /f
goto success

:custom
echo.
set /p custom_time=请输入执行时间 (格式: HH:MM, 如 03:30): 
set /p custom_days=请输入执行间隔天数 (1=每天, 3=每3天, 7=每周): 
echo 设置每%custom_days%天%custom_time%自动续期...
schtasks /create /tn "%TASK_NAME%" /tr "python \"%SCRIPT_PATH%\"" /sc daily /mo %custom_days% /st %custom_time% /f
goto success

:delete
echo 删除现有定时任务...
schtasks /delete /tn "%TASK_NAME%" /f
echo ✅ 定时任务已删除
goto end

:status
echo 当前定时任务状态：
schtasks /query /tn "%TASK_NAME%" 2>nul
if errorlevel 1 (
    echo ❌ 未找到定时任务：%TASK_NAME%
) else (
    echo ✅ 定时任务存在
    echo.
    echo 📄 详细信息：
    schtasks /query /tn "%TASK_NAME%" /fo LIST /v
)
goto end

:test
echo 执行手动测试...
echo.
echo ⚠️  警告：这将重启所有Docker服务，请确认：
set /p confirm=继续执行？ (y/N): 
if /i "%confirm%" NEQ "y" (
    echo 测试已取消
    goto end
)
echo.
echo 开始执行全局重建策略测试...
python "%SCRIPT_PATH%"
echo.
echo 测试完成，请检查上述输出
goto end

:success
if errorlevel 1 (
    echo ❌ 定时任务创建失败！
    echo 请以管理员身份运行此脚本
    pause
    exit /b 1
) else (
    echo ✅ 定时任务创建成功！
    echo.
    echo 📝 任务详情：
    echo    任务名称: %TASK_NAME%
    echo    执行脚本: %SCRIPT_PATH%
    echo    策略: 全局重建 (down + up)
    echo    日志文件: %LOG_PATH%\kingbase_renewal.log
    echo.
    echo 🔧 管理命令：
    echo    查看任务: schtasks /query /tn "%TASK_NAME%"
    echo    删除任务: schtasks /delete /tn "%TASK_NAME%" /f
    echo    手动运行: schtasks /run /tn "%TASK_NAME%"
    echo.
    echo 📖 查看日志: type "%LOG_PATH%\kingbase_renewal.log"
    echo.
    echo 💡 建议：首次部署后，请执行选项7进行手动测试
)

:end
echo.
pause 