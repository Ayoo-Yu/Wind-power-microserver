import json
import subprocess
import datetime
import glob
from flask import Blueprint, request, jsonify, current_app
import os
import sys
import shutil
import traceback
import uuid
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from database_config import Base, get_db
from db_session import db_session  # 导入上下文管理器
from db_models import TaskHistory
from config import Config  # 导入Config类

# 全局状态字典，其他代码依赖这个变量
prediction_status = {
    'short': False,
    'medium': False,
    'supershort': False
}
# 添加线程锁以确保线程安全
status_lock = threading.Lock()

DEFAULT_FARM_CODE = "DEFAULT_FARM"

# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 在Docker环境中，脚本应该在/app目录下
if os.path.exists('/app'):
    # Docker环境
    base_dir = '/app'
else:
    # 本地开发环境
    base_dir = os.path.abspath(os.path.join(current_dir, '../..'))

# 从Config类中获取脚本路径
scripts = {
    'short': Config.SCRIPT_PATHS.get('short'),
    'medium': Config.SCRIPT_PATHS.get('medium'),
    'supershort': Config.SCRIPT_PATHS.get('supershort')
}

# 检查脚本是否存在
for name, path in scripts.items():
    if path and os.path.exists(path):
        print(f"[OK] 脚本存在: {name} -> {path}")
    else:
        print(f"[MISSING] 脚本不存在: {name} -> {path}")
        # 尝试查找可能的位置
        possible_locations = [
            os.path.join(base_dir, 'auto_scripts', 'scripts', name, f'scheduler_{name}.py'),
            os.path.join(base_dir, 'scripts', name, f'scheduler_{name}.py'),
            os.path.join(base_dir, 'scripts', f'scheduler_{name}.py')
        ]
        for loc in possible_locations:
            if os.path.exists(loc):
                print(f"[OK] 找到替代脚本: {loc}")
                scripts[name] = loc
                break

# 使用配置中定义的日志目录路径
log_dirs = Config.LOG_DIRS

# 确保所有日志目录都存在
for type_dirs in log_dirs.values():
    for dir_path in type_dirs.values():
        os.makedirs(dir_path, exist_ok=True)

# 根据操作系统动态确定 Python 解释器路径
def get_python_interpreter():
    """
    根据当前操作系统环境动态确定Python解释器路径
    
    Returns:
        str: 适合当前平台的Python解释器路径
    """
    if sys.platform.startswith('linux'):
        # 假设在 Linux/Docker 环境中，使用固定的 Conda 环境路径
        interpreter = '/opt/conda/envs/wind-power-env/bin/python'
        print(f"检测到 Linux/Docker 环境，使用Python解释器: {interpreter}")
        return interpreter
    elif sys.platform.startswith('win'):
        # 在 Windows 开发环境中，优先使用当前Python解释器
        interpreter = sys.executable
        print(f"检测到 Windows 环境，使用当前Python解释器: {interpreter}")
        return interpreter
    elif sys.platform.startswith('darwin'):
        # macOS环境，与Windows类似
        interpreter = sys.executable
        print(f"检测到 macOS 环境，使用当前Python解释器: {interpreter}")
        return interpreter
    else:
        # 其他未知操作系统，使用系统默认Python
        print(f"未知的操作系统平台 '{sys.platform}'，使用系统默认'python'")
        return 'python'

# 初始化时获取Python解释器路径
python_interpreter = get_python_interpreter()
print(f"初始化完成，将使用Python解释器: {python_interpreter}")

# 改进PM2路径检测
def find_pm2_path():
    # 使用shutil.which查找可执行文件路径
    pm2_path = shutil.which('pm2')
    if pm2_path:
        print(f"找到PM2路径: {pm2_path}")
        return pm2_path
    
    # 尝试从环境变量获取
    pm2_path = os.environ.get('PM2_PATH')
    if pm2_path and os.path.exists(pm2_path) and os.access(pm2_path, os.X_OK):
        print(f"从环境变量获取PM2路径: {pm2_path}")
        return pm2_path
    
    # 尝试常见的安装位置
    common_paths = [
        '/usr/local/bin/pm2',
        '/usr/bin/pm2',
        '/opt/node/bin/pm2',
        '/opt/nodejs/bin/pm2',
        '/opt/conda/bin/pm2',
        '/usr/local/nodejs/bin/pm2',
        os.path.expanduser('~/.nvm/versions/node/*/bin/pm2'),
        os.path.expanduser('~/node_modules/.bin/pm2')
    ]
    
    for path_pattern in common_paths:
        # 处理可能包含通配符的路径
        if '*' in path_pattern:
            import glob
            matching_paths = glob.glob(path_pattern)
            for path in matching_paths:
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    print(f"在扩展路径中找到PM2: {path}")
                    return path
        elif os.path.isfile(path_pattern) and os.access(path_pattern, os.X_OK):
            print(f"在常见位置找到PM2: {path_pattern}")
            return path_pattern
    
    # 如果在Windows上运行
    if sys.platform.startswith('win'):
        # 尝试使用npm路径
        npm_path = shutil.which('npm')
        if npm_path:
            npm_dir = os.path.dirname(npm_path)
            pm2_win_path = os.path.join(npm_dir, 'pm2.cmd')
            if os.path.exists(pm2_win_path):
                print(f"在Windows上找到PM2: {pm2_win_path}")
                return pm2_win_path
    
    # 最后的回退选项
    print(f"未找到PM2可执行文件，使用默认命令: pm2")
    return 'pm2'

# 使用改进的函数获取PM2路径
pm2_cmd = find_pm2_path()

# 安全的PM2命令执行函数
def safe_pm2_command(cmd_args, timeout=30, capture_output=True):
    """
    安全地执行PM2命令，添加超时和错误处理
    
    Args:
        cmd_args: PM2命令参数列表
        timeout: 命令执行超时时间（秒）
        capture_output: 是否捕获输出
        
    Returns:
        tuple: (成功与否, 结果对象或错误消息)
    """
    full_cmd = [pm2_cmd] + cmd_args
    try:
        print(f"执行命令: {' '.join(full_cmd)}")
        
        # Special handling for 'pm2 logs' encoding
        is_logs_command = 'logs' in cmd_args and cmd_args[0].lower() == 'logs' # More specific check

        if capture_output:
            if is_logs_command:
                # Get raw bytes for logs to handle encoding manually
                # print(f"DEBUG: Executing logs command, getting raw bytes: {' '.join(full_cmd)}")
                proc = subprocess.run(
                    full_cmd,
                    capture_output=True,
                    timeout=timeout,
                    check=False # Check manually after decoding
                )
                # Attempt to decode stdout and stderr
                stdout_decoded, stderr_decoded = "", ""
                if proc.stdout:
                    try:
                        stdout_decoded = proc.stdout.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            # print("DEBUG: UTF-8 decode failed for stdout, trying GBK...")
                            stdout_decoded = proc.stdout.decode('gbk') 
                        except UnicodeDecodeError:
                            # print("DEBUG: GBK decode failed for stdout, trying latin-1...")
                            stdout_decoded = proc.stdout.decode('latin-1', errors='replace')
                if proc.stderr:
                    try:
                        stderr_decoded = proc.stderr.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            # print("DEBUG: UTF-8 decode failed for stderr, trying GBK...")
                            stderr_decoded = proc.stderr.decode('gbk')
                        except UnicodeDecodeError:
                            # print("DEBUG: GBK decode failed for stderr, trying latin-1...")
                            stderr_decoded = proc.stderr.decode('latin-1', errors='replace')
                
                # Mimic subprocess.CompletedProcess structure for consistent handling
                class DecodedProcessResult:
                    def __init__(self, stdout_text, stderr_text, return_code):
                        self.stdout = stdout_text
                        self.stderr = stderr_text
                        self.returncode = return_code
                
                decoded_result = DecodedProcessResult(stdout_decoded, stderr_decoded, proc.returncode)
                
                if proc.returncode != 0:
                    # print(f"DEBUG: Logs command failed with exit code {proc.returncode}. stderr: {stderr_decoded}")
                    # Re-raise a CalledProcessError-like exception or return a failure indicator
                    # For simplicity with current structure, we return False and the decoded result (which contains stderr)
                    return False, decoded_result # Error message will be constructed by caller based on this

                return True, decoded_result
            else: # Original behavior for other commands
                result = subprocess.run(
                    full_cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=timeout,
                    check=True
                )
                return True, result
        else: # Not capturing output
            result = subprocess.run(
                full_cmd,
                timeout=timeout,
                check=True
            )
            return True, result
    except subprocess.TimeoutExpired as e:
        error_msg = f"命令执行超时 ({timeout}秒): {' '.join(full_cmd)}"
        print(error_msg)
        return False, error_msg
    except subprocess.CalledProcessError as e:
        error_msg = f"命令执行失败: {e}\n输出: {e.stdout if hasattr(e, 'stdout') else '无'}\n错误: {e.stderr if hasattr(e, 'stderr') else '无'}"
        print(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"命令执行异常: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return False, error_msg

# 添加周期性更新PM2状态的函数
def update_pm2_status_periodically():
    """周期性查询PM2并更新全局状态字典"""
    print(f"[{datetime.datetime.now()}] 后台任务：正在更新PM2状态...")
    local_status = {}  # 先操作局部变量
    
    success, result = safe_pm2_command(['jlist'])  # 调用一次jlist
    processes = []
    if success:
        output = result.stdout.strip() if result.stdout else ''
        if output:
            try:
                processes = json.loads(output)
                if not isinstance(processes, list):
                    print(f"警告: PM2 jlist 输出不是预期的列表格式")
                    processes = []
            except json.JSONDecodeError as e:
                print(f"警告: 解析PM2 jlist输出失败: {e}")
                processes = []
    else:
        print(f"后台任务：执行pm2 jlist失败: {result}")
        # 如果命令失败，保留原状态
        return
    
    # 根据找到的进程计算状态
    for key, script_path in scripts.items():
        script_basename = os.path.basename(script_path)
        is_online = any(
            (script_path in proc.get('pm2_env', {}).get('pm_exec_path', '') or 
             script_basename == proc.get('pm2_env', {}).get('name', ''))
            and proc.get('pm2_env', {}).get('status', '') == "online"
            for proc in processes
        )
        local_status[key] = is_online
    
    # 安全地更新全局字典
    with status_lock:  # 获取锁
        global prediction_status
        prediction_status.update(local_status)  # 更新全局状态
    
    print(f"[{datetime.datetime.now()}] 后台任务：PM2状态已更新: {prediction_status}")

# 初始化后台调度器
scheduler = BackgroundScheduler(daemon=True)  # daemon=True确保主程序退出时调度器也退出
# 每10秒运行一次更新函数 (可根据需要调整)
scheduler.add_job(update_pm2_status_periodically, 'interval', seconds=10, id='pm2_status_updater')
# 确保应用退出时关闭调度器
import atexit
atexit.register(lambda: scheduler.shutdown())

def _get_running_farm_code(prediction_type):
    """获取正在运行的预测任务的场站代码"""
    script_path = scripts[prediction_type]
    success, result = safe_pm2_command(['jlist'])

    if not success:
        return None

    try:
        processes = json.loads(result.stdout) if result.stdout else []
        script_basename = os.path.basename(script_path)

        for proc in processes:
            pm2_env = proc.get('pm2_env', {})
            proc_name = pm2_env.get('name', '')
            status = pm2_env.get('status', '')

            # 从进程名称中提取场站代码
            if status == "online" and script_basename in proc_name:
                # 进程名称格式: farm_type_scriptname
                if '_' in proc_name:
                    farm_code = proc_name.split('_')[0]
                    if is_valid_farm_code(farm_code):
                        return farm_code
    except:
        pass

    return None


def get_active_farm_codes():
    """
    从 wind_farms 表读取有效场站编码。
    回退策略：
    1) 查询失败时返回 DEFAULT_FARM_CODE
    2) 查询为空时返回 DEFAULT_FARM_CODE
    """
    try:
        with db_session() as db:
            has_deleted_at = db.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM information_schema.columns
                    WHERE table_name = 'wind_farms'
                      AND column_name = 'deleted_at'
                    """
                )
            ).scalar()

            if has_deleted_at:
                query_sql = """
                    SELECT farm_code
                    FROM wind_farms
                    WHERE COALESCE(is_active, TRUE) = TRUE
                      AND deleted_at IS NULL
                    ORDER BY farm_code
                """
            else:
                query_sql = """
                    SELECT farm_code
                    FROM wind_farms
                    WHERE COALESCE(is_active, TRUE) = TRUE
                    ORDER BY farm_code
                """

            rows = db.execute(text(query_sql)).fetchall()

        farm_codes = [row[0] for row in rows if row and row[0]]
        if not farm_codes:
            return [DEFAULT_FARM_CODE]
        return farm_codes
    except Exception as e:
        print(f"警告: 读取场站列表失败，使用默认场站: {e}")
        return [DEFAULT_FARM_CODE]


def is_valid_farm_code(farm_code):
    if not farm_code:
        return False
    return farm_code in set(get_active_farm_codes())


def resolve_farm_code(raw_farm_code):
    """
    解析请求中的 farm_code：
    - 为空时使用 DEFAULT_FARM_CODE（若存在），否则使用首个有效场站
    - 非空时原样返回
    """
    if raw_farm_code:
        return raw_farm_code

    active_farms = get_active_farm_codes()
    if DEFAULT_FARM_CODE in active_farms:
        return DEFAULT_FARM_CODE
    return active_farms[0]

def query_pm2_state(script_path):
    """
    查询 pm2 中指定脚本的运行状态，
    只有当进程的 pm_exec_path 包含指定脚本且状态为 "online" 时才返回 True
    """
    success, result = safe_pm2_command(['jlist'])
    if not success:
        print(f"查询PM2状态失败: {result}")
        return False
        
    try:
        output = result.stdout
        if not output or output.strip() == '[]':
            print("PM2列表为空或未返回有效数据")
            return False
            
        processes = json.loads(output)
        script_basename = os.path.basename(script_path)
        
        for proc in processes:
            pm2_env = proc.get('pm2_env', {})
            exec_path = pm2_env.get('pm_exec_path', '')
            proc_name = pm2_env.get('name', '')
            status = pm2_env.get('status', '')
            
            # 检查脚本路径或进程名是否匹配
            path_match = script_path in exec_path
            name_match = script_basename == proc_name
            
            if (path_match or name_match) and status == "online":
                print(f"找到匹配的运行中进程: {proc_name}")
                return True
                
        return False
    except Exception as e:
        print(f"解析PM2状态时出错: {e}")
        return False

# 记录操作历史的辅助函数
def record_task_history(task_type, action, status, details=None, user=None):
    """记录任务操作历史
    
    Args:
        task_type: 任务类型 (supershort, short, medium)
        action: 操作类型 (start, stop, delete, schedule, etc.)
        status: 操作状态 (success, failed)
        details: 操作详情，可选
        user: 操作用户，可选
        
    Returns:
        UUID: 任务历史ID
    """
    task_id = str(uuid.uuid4())
    try:
        with db_session() as db:
            task_history = TaskHistory(
                task_id=task_id,
                task_type=task_type,
                action=action,
                status=status,
                details=details,
                user=user
            )
            db.add(task_history)
            db.commit()
            return task_id
    except Exception as e:
        print(f"记录任务历史出错: {e}")
        return None

# 新建蓝图，所有接口的 URL 前缀为 /api
autopredict_bp = Blueprint('autopredict', __name__)

# 启动后台任务调度器
# 应用启动时首先执行一次更新
update_pm2_status_periodically()
# 启动调度器
scheduler.start()
print(f"[{datetime.datetime.now()}] PM2状态监控后台任务已启动")

# 获取预测任务状态，同时更新全局字典 prediction_status
@autopredict_bp.route('/status', methods=['GET'])
def get_status():
    try:
        # 查询指定场站的状态
        farm_code = resolve_farm_code(request.args.get('farm_code'))
        prediction_type = request.args.get('type')

        # 更新全局状态
        _update_prediction_status()

        # 使用线程锁安全地获取当前状态的副本
        with status_lock:
            current_status = prediction_status.copy()

        # 如果指定了预测类型，只返回该类型的状态
        if prediction_type:
            if prediction_type in current_status:
                return jsonify({
                    prediction_type: current_status[prediction_type],
                    'farm_code': farm_code
                })
            else:
                return jsonify({'error': '无效的预测类型'}), 400

        # 添加场站信息到返回结果
        current_status['farm_code'] = farm_code
        return jsonify(current_status)
    except Exception as e:
        error_msg = f"获取状态时出错: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({'error': error_msg}), 500

# 启动指定预测任务
@autopredict_bp.route('/start', methods=['POST'])
def start_prediction():
    data = request.get_json() or {}
    prediction_type = data.get('type')
    farm_code = resolve_farm_code(data.get('farm_code'))

    if prediction_type not in prediction_status:
        return jsonify({'error': '无效的预测类型'}), 400

    # 验证场站代码
    if not is_valid_farm_code(farm_code):
        return jsonify({'error': f'无效的场站代码: {farm_code}'}), 400

    script_path = scripts[prediction_type]

    # 检查脚本是否存在
    if not os.path.exists(script_path):
        error_msg = f'脚本文件不存在: {script_path}'
        record_task_history(prediction_type, 'start', 'failed', error_msg)
        return jsonify({'error': error_msg}), 400

    # 使用场站信息作为进程名称的一部分
    process_name = f"{farm_code}_{os.path.splitext(os.path.basename(script_path))[0]}"

    # 先检查进程是否已经运行（包括相同场站和类型）
    if query_pm2_state(script_path):
        # 检查是否为相同场站的进程
        existing_farm_status = _get_running_farm_code(prediction_type)
        if existing_farm_status == farm_code:
            with status_lock:  # 获取锁
                prediction_status[prediction_type] = True
            record_task_history(prediction_type, 'start', 'success', f'场站 {farm_code} 进程已在运行中: {process_name}')
            return jsonify({'message': f'{prediction_type} 预测任务已经在运行 (场站: {farm_code})', 'status': True})
        else:
            return jsonify({
                'error': f'{prediction_type} 预测任务正在为场站 {existing_farm_status} 运行，请先停止再启动新场站'
            }), 400

    # 为脚本传递场站参数
    env_vars = {
        'FARM_CODE': farm_code,
        'PYTHONPATH': base_dir  # 确保模块路径正确
    }

    # 使用动态确定的Python解释器路径，并传递环境变量
    success, result = safe_pm2_command([
        'start', script_path,
        '--name', process_name,
        '--interpreter', python_interpreter,
        '--merge-logs'  # 合并日志以便调试
    ])

    if success:
        # 启动命令执行成功，但需要验证进程是否真的启动
        verify_success, _ = safe_pm2_command(['list'])
        if verify_success:
            # 再次检查进程状态
            if query_pm2_state(script_path):
                with status_lock:  # 获取锁
                    prediction_status[prediction_type] = True
                record_task_history(prediction_type, 'start', 'success', f'场站 {farm_code} 进程启动成功: {process_name}')
                return jsonify({
                    'message': f'{prediction_type} 预测任务已启动 (场站: {farm_code})',
                    'output': result.stdout if hasattr(result, 'stdout') else '',
                    'farm_code': farm_code  # 返回场站信息
                })
            else:
                # 命令成功但进程可能没有正常启动
                warning_msg = f'{prediction_type} 启动命令成功，但进程可能未正常运行 (场站: {farm_code})'
                record_task_history(prediction_type, 'start', 'warning', warning_msg)
                return jsonify({
                    'warning': warning_msg,
                    'output': result.stdout if hasattr(result, 'stdout') else '',
                    'farm_code': farm_code
                }), 202
        else:
            warning_msg = f'{prediction_type} 启动命令成功，但无法验证进程状态'
            record_task_history(prediction_type, 'start', 'warning', warning_msg)
            return jsonify({
                'warning': warning_msg,
                'output': result.stdout if hasattr(result, 'stdout') else ''
            }), 202
    else:
        # 启动命令执行失败
        error_msg = f'启动任务失败: {result}'
        record_task_history(prediction_type, 'start', 'failed', error_msg)
        return jsonify({'error': error_msg}), 500

# 停止预测任务
@autopredict_bp.route('/stop', methods=['POST'])
def stop_prediction():
    data = request.json
    prediction_type = data.get('type')
    
    if not prediction_type or prediction_type not in prediction_status:
        return jsonify({'error': '无效的预测类型'}), 400
    
    try:
        # 正常停止单个脚本
        script_path = scripts[prediction_type]
        script_name = os.path.splitext(os.path.basename(script_path))[0]  # 去掉.py后缀
        
        success, result = safe_pm2_command(['stop', script_name])
            
        if success:
            with status_lock:  # 获取锁
                prediction_status[prediction_type] = False
            # 更新全局状态
            _update_prediction_status()
            
            message = f'{script_name} 已停止'
            record_task_history(prediction_type, 'stop', 'success', message)
            
            return jsonify({
                'message': f'{prediction_type}预测任务已停止'
            })
        else:
            error_msg = f'停止任务失败: {result}'
            record_task_history(prediction_type, 'stop', 'failed', error_msg)
            
            return jsonify({
                'error': '停止预测任务失败',
                'details': str(result)
            }), 500
    except Exception as e:
        error_msg = f'停止预测任务异常: {str(e)}'
        record_task_history(prediction_type, 'stop', 'failed', error_msg)
        
        return jsonify({
            'error': '停止预测任务失败',
            'details': str(e)
        }), 500

# 设置定时重启任务
@autopredict_bp.route('/schedule', methods=['POST'])
def schedule_restart():
    data = request.get_json() or {}
    prediction_type = data.get('type')
    schedule_time = data.get('time')  # 格式应为 HH:mm

    if prediction_type not in prediction_status:
        return jsonify({'error': '无效的预测类型'}), 400
    if not schedule_time:
        return jsonify({'error': '缺少重启时间参数'}), 400

    try:
        time_obj = datetime.datetime.strptime(schedule_time, '%H:%M')
    except ValueError:
        error_msg = '时间格式错误，要求 HH:mm'
        record_task_history(prediction_type, 'schedule', 'failed', error_msg)
        return jsonify({'error': error_msg}), 400

    script_path = scripts[prediction_type]
    # 使用 os.path.splitext 获取脚本文件名，去掉.py后缀作为进程名称
    process_name = os.path.splitext(os.path.basename(script_path))[0]
    
    # 先停止现有进程
    stop_success, _ = safe_pm2_command(['stop', process_name])
    if not stop_success:
        print(f"警告: 无法停止现有进程 {process_name}, 将尝试继续设置定时任务")
    
    # 使用动态确定的Python解释器路径
    
    # 启动带定时重启的任务
    cron_expression = f'0 {time_obj.minute} {time_obj.hour} * * *'
    success, result = safe_pm2_command(['start', script_path, '--name', process_name, '--cron', cron_expression, '--interpreter', python_interpreter])
    
    if success:
        with status_lock:  # 获取锁
            prediction_status[prediction_type] = True
        record_task_history(
            prediction_type, 
            'schedule', 
            'success', 
            f'设置定时重启: {schedule_time}'
        )
        return jsonify({'message': f'为 {prediction_type} 设置了每日 {schedule_time} 的定时重启'})
    else:
        error_msg = f'设置定时重启失败: {result}'
        record_task_history(prediction_type, 'schedule', 'failed', error_msg)
        return jsonify({'error': error_msg}), 500

# 从 PM2 中删除任务
@autopredict_bp.route('/delete', methods=['POST'])
def delete_prediction():
    data = request.json
    prediction_type = data.get('type')
    if not prediction_type or prediction_type not in prediction_status:
        return jsonify({'error': '无效的预测类型'}), 400
    
    try:
        script_path = scripts[prediction_type]
        script_name = os.path.splitext(os.path.basename(script_path))[0]  # 去掉.py后缀
        
        success, result = safe_pm2_command(['delete', script_name])
        
        if success:
            with status_lock:  # 获取锁
                prediction_status[prediction_type] = False
            # 更新全局状态
            _update_prediction_status()
            
            message = f'{script_name} 已从PM2删除'
            record_task_history(prediction_type, 'delete', 'success', message)
            
            return jsonify({
                'message': f'{prediction_type}预测任务已从PM2删除'
            })
        else:
            error_msg = f'删除任务失败: {result}'
            record_task_history(prediction_type, 'delete', 'failed', error_msg)
            
            return jsonify({
                'error': '从PM2删除预测任务失败',
                'details': str(result)
            }), 500
    except Exception as e:
        error_msg = f'删除预测任务异常: {str(e)}'
        record_task_history(prediction_type, 'delete', 'failed', error_msg)
        
        return jsonify({
            'error': '从PM2删除预测任务失败',
            'details': str(e)
        }), 500

# 保存当前 PM2 任务配置
@autopredict_bp.route('/save', methods=['POST'])
def save_pm2_config():
    success, result = safe_pm2_command(['save'])
    
    if success:
        record_task_history('all', 'save', 'success', '保存PM2配置')
        return jsonify({'message': 'PM2 任务配置已保存'})
    else:
        error_msg = f'保存配置失败: {result}'
        record_task_history('all', 'save', 'failed', error_msg)
        return jsonify({'error': error_msg}), 500

# 删除PM2保存的配置文件（新增）
@autopredict_bp.route('/clearsave', methods=['POST'])
def clear_pm2_save():
    success, result = safe_pm2_command(['cleardump'])
    
    if success:
        record_task_history('all', 'clearsave', 'success', '删除PM2保存的配置')
        return jsonify({'message': 'PM2 保存的配置已删除'})
    else:
        error_msg = f'删除保存配置失败: {result}'
        record_task_history('all', 'clearsave', 'failed', error_msg)
        return jsonify({'error': error_msg}), 500

# 查询指定脚本的详细 PM2 信息
@autopredict_bp.route('/script_info', methods=['GET'])
def get_script_info():
    prediction_type = request.args.get('type')
    if not prediction_type or prediction_type not in prediction_status:
        return jsonify({'error': '无效的预测类型'}), 400

    try:
        # 获取进程名称（去掉.py后缀）
        process_name = os.path.splitext(os.path.basename(scripts[prediction_type]))[0]
        print(f"正在查询进程: {process_name}")  # 调试日志
        
        # 先检查进程是否存在
        list_success, list_result = safe_pm2_command(['list'])
        
        if not list_success:
            error_msg = '无法获取PM2进程列表'
            record_task_history(prediction_type, 'script_info', 'failed', error_msg)
            return jsonify({
                'error': error_msg,
                'details': str(list_result)
            }), 500
            
        list_output = list_result.stdout if hasattr(list_result, 'stdout') else ''
        print(f"PM2 进程列表: {list_output}")  # 输出所有进程列表
        
        # 检查是否在进程列表中找到对应进程
        if process_name not in list_output:
            # 尝试使用describe命令无论如何获取信息
            describe_success, describe_result = safe_pm2_command(['describe', process_name], timeout=10)
            
            if describe_success:
                # 即使进程名不在列表中，describe命令可能仍然返回信息
                record_task_history(prediction_type, 'script_info', 'warning', '进程未在PM2列表中找到，但describe命令返回了信息')
                return jsonify({
                    'info': describe_result.stdout,
                    'process_name': process_name,
                    'warning': '进程未在PM2列表中找到，但describe命令返回了信息'
                })
            else:
                error_msg = f'进程 {process_name} 未运行'
                record_task_history(prediction_type, 'script_info', 'failed', error_msg)
                return jsonify({
                    'error': error_msg,
                    'pm2_list': list_output,
                    'describe_error': str(describe_result)
                }), 404
            
        # 使用进程名称查询详情
        describe_success, describe_result = safe_pm2_command(['describe', process_name])
        
        if not describe_success:
            error_msg = '查询进程详情失败'
            record_task_history(prediction_type, 'script_info', 'failed', error_msg)
            return jsonify({
                'error': error_msg,
                'details': str(describe_result)
            }), 500
            
        describe_output = describe_result.stdout if hasattr(describe_result, 'stdout') else ''
        
        if not describe_output.strip():
            error_msg = '进程信息为空'
            record_task_history(prediction_type, 'script_info', 'failed', error_msg)
            return jsonify({
                'error': error_msg,
                'process_name': process_name
            }), 404
            
        record_task_history(prediction_type, 'script_info', 'success', '查询进程详情成功')
        return jsonify({
            'info': describe_output,
            'process_name': process_name
        })
        
    except Exception as e:
        error_msg = f"获取脚本详情出错: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        record_task_history(prediction_type, 'script_info', 'failed', error_msg)
        return jsonify({
            'error': '查询脚本详情失败',
            'details': error_msg
        }), 500

# 获取指定脚本的近期日志信息
@autopredict_bp.route('/logs', methods=['GET'])
def get_logs():
    prediction_type = request.args.get('type')
    log_type = request.args.get('logType', 'train') # train, main, predict, param
    date_str = request.args.get('date', datetime.datetime.now().strftime('%Y%m%d'))
    lines = request.args.get('lines', 500, type=int)
    
    if not prediction_type or prediction_type not in prediction_status:
        return jsonify({'error': '无效的预测类型'}), 400
    
    try:
        # 如果是通过PM2查询主日志
        if log_type == 'main':
            script_path = scripts[prediction_type]
            process_name = os.path.splitext(os.path.basename(script_path))[0]  # 去掉.py后缀
            
            success, result = safe_pm2_command(['logs', '--nostream', '--lines', str(lines), process_name])
            
            if success:
                record_task_history(prediction_type, 'logs', 'success', f'获取主日志 ({lines} 行)')
                return jsonify({'logs': result.stdout if hasattr(result, 'stdout') else '没有日志输出'})
            else:
                # 尝试只获取错误日志
                error_success, error_result = safe_pm2_command(['logs', '--nostream', '--err', '--lines', str(lines), process_name])
                if error_success:
                    warning_msg = '无法获取完整日志，仅显示错误日志'
                    record_task_history(prediction_type, 'logs', 'warning', warning_msg)
                    return jsonify({
                        'logs': f"警告: {warning_msg}:\n{error_result.stdout if hasattr(error_result, 'stdout') else '没有错误日志'}"
                    })
                else:
                    error_msg = '获取日志失败'
                    details = {
                        'details': str(result),
                        'error_log_details': str(error_result) if 'error_result' in locals() else '未尝试获取错误日志'
                    }
                    record_task_history(prediction_type, 'logs', 'failed', json.dumps(details))
                    return jsonify({
                        'error': error_msg, 
                        'details': str(result),
                        'error_log_details': str(error_result) if 'error_result' in locals() else '未尝试获取错误日志'
                    }), 500
        else:
            # 从对应的日志目录读取文件
            log_dir = log_dirs[prediction_type].get(log_type)
            if not log_dir:
                return jsonify({'error': f'无效的日志类型: {log_type}'}), 400
            
            # 查找日志文件
            log_files = []
            if prediction_type == 'supershort':
                if log_type == 'train':
                    # 超短期训练日志文件名格式: YYYYMMDD_train_supershort.log
                    # date_str 来自前端，已经是 YYYYMMDD 格式
                    log_files = glob.glob(os.path.join(log_dir, f"{date_str}_train_supershort.log"))
                elif log_type == 'predict':
                    # 超短期预测日志文件名格式: YYYYMMDD_predict_supershort.log
                    # Logs are in an 'auto_predict' subdirectory
                    log_files = glob.glob(os.path.join(log_dir, f"{date_str}_predict_supershort.log"))
                # 'main' type for supershort is handled by PM2 logs section above
            elif log_type == 'train': # For short and medium
                # 训练日志格式可能是 YYYYMMDD.log 或包含日期的其他格式 (维持旧逻辑)
                log_files = glob.glob(os.path.join(log_dir, f"{date_str}*.log"))
                # For short/medium, also consider the _train_done.flag logic if needed for disambiguation
                # The existing logic for train_flag_path for short/medium seems okay to keep as is.
                train_flag_path = os.path.join(log_dir, f"{date_str}_train_done.flag")
            elif log_type == 'predict':
                # 预测日志格式
                log_files = glob.glob(os.path.join(log_dir, f"{date_str}*.log"))
            # elif log_type == 'param':
            #     # 参数优化日志 - 根据param_opt_day计算正确的周期
            #     try:
            #         # 获取参数优化执行日（0-6 表示周一到周日）
            #         param_opt_day = request.args.get('param_opt_day', None)
            #         if param_opt_day is not None:
            #             param_opt_day = int(param_opt_day)
            #         else:
            #             # 默认参数优化日
            #             param_opt_day_map = {
            #                 'short': 4,        # 周五
            #                 'medium': 3,       # 周四
            #                 'supershort': 6    # 周日
            #             }
            #             param_opt_day = param_opt_day_map.get(prediction_type, 5)
                    
            #         # 解析所选日期
            #         selected_date = datetime.datetime.strptime(date_str, '%Y%m%d')
            #         # 计算所选日期在其所在周的星期几（0-6表示周一到周日）
            #         selected_weekday = selected_date.weekday()
                    
            #         # 计算参数优化周期的开始日期
            #         days_diff = 0
            #         if selected_weekday >= param_opt_day:
            #             # 计算到本周参数优化日的天数差
            #             days_diff = selected_weekday - param_opt_day
            #         else:
            #             # 计算到上周参数优化日的天数差
            #             days_diff = selected_weekday + 7 - param_opt_day
                    
            #         # 找到对应的参数优化日期
            #         param_opt_date = selected_date - datetime.timedelta(days=days_diff)
            #         param_opt_date_str = param_opt_date.strftime('%Y%m%d')
                    
            #         # 查找参数优化完成标志文件
            #         param_flag_path = os.path.join(log_dir, f"{param_opt_date_str}_param_opt_done.flag")
                    
            #         # 如果找不到精确日期的标志文件，尝试查找当周的标志文件（兼容现有逻辑）
            #         if not os.path.exists(param_flag_path):
            #             # 计算该参数优化日所在周的周一
            #             param_opt_monday = param_opt_date - datetime.timedelta(days=param_opt_date.weekday())
            #             monday_str = param_opt_monday.strftime('%Y%m%d')
            #             param_flag_path = os.path.join(log_dir, f"{monday_str}_param_opt_done.flag")
                    
            #         if os.path.exists(param_flag_path):
            #             # 存在标志文件，先尝试查找精确日期的日志
            #             date_logs = glob.glob(os.path.join(log_dir, f"{param_opt_date_str}*.log"))
            #             if date_logs:
            #                 # 找到了精确日期的日志
            #                 log_files = date_logs
            #             else:
            #                 # 尝试查找该周的参数优化日志
            #                 monday = param_opt_date - datetime.timedelta(days=param_opt_date.weekday())
            #                 monday_str = monday.strftime('%Y%m%d')
            #                 week_logs = glob.glob(os.path.join(log_dir, f"{monday_str}*.log"))
            #                 if week_logs:
            #                     log_files = week_logs
            #                 else:
            #                     # 尝试查找该月的所有参数优化日志
            #                     year_month = param_opt_date_str[:6]  # 提取年月
            #                     month_logs = glob.glob(os.path.join(log_dir, f"{year_month}*.log"))
            #                     if month_logs:
            #                         # 找到最接近参数优化日期的日志
            #                         closest_log = None
            #                         min_diff = float('inf')
            #                         for log in month_logs:
            #                             log_date_str = os.path.basename(log).split('.')[0][:8]
            #                             try:
            #                                 log_date = datetime.datetime.strptime(log_date_str, '%Y%m%d')
            #                                 diff = abs((param_opt_date - log_date).days)
            #                                 if diff < min_diff:
            #                                     min_diff = diff
            #                                     closest_log = log
            #                             except ValueError:
            #                                 continue
            #                         if closest_log:
            #                             log_files = [closest_log]
                # except ValueError:
                #     # 日期格式错误，返回错误信息
                #     record_task_history(prediction_type, 'logs', 'failed', f'日期格式无效: {date_str}')
                #     return jsonify({'error': f'日期格式无效: {date_str}'}), 400
            
            if not log_files:
                record_task_history(prediction_type, 'logs', 'failed', f'未找到{date_str}的{log_type}类型日志文件')
                return jsonify({'logs': f'未找到{date_str}的{log_type}日志文件'})
            
            # 读取最新的日志文件
            latest_log = max(log_files, key=os.path.getmtime)
            try:
                with open(latest_log, 'r', encoding='utf-8', errors='replace') as f:
                    # 如果文件太大，只读取最后N行
                    all_lines = f.readlines()
                    log_content = ''.join(all_lines[-lines:]) if len(all_lines) > lines else ''.join(all_lines)
                
                # 添加日志文件信息到内容中
                file_info = f"文件: {os.path.basename(latest_log)}\n日期: {datetime.datetime.fromtimestamp(os.path.getmtime(latest_log)).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                log_content = file_info + log_content
                
                record_task_history(prediction_type, 'logs', 'success', f'获取{log_type}日志 ({lines} 行)')
                return jsonify({'logs': log_content})
            except Exception as e:
                error_msg = f'读取日志文件失败: {str(e)}'
                record_task_history(prediction_type, 'logs', 'failed', error_msg)
                return jsonify({'error': error_msg}), 500
    except Exception as e:
        error_msg = f'获取日志失败: {str(e)}'
        record_task_history(prediction_type, 'logs', 'failed', error_msg)
        return jsonify({'error': error_msg}), 500

# 加载已保存的 PM2 配置（基于 pm2 resurrect）
@autopredict_bp.route('/resurrect', methods=['POST'])
def resurrect():
    success, result = safe_pm2_command(['resurrect'])
    
    if success:
        # 更新状态字典，但不直接使用路由函数
        try:
            # 获取PM2状态并更新全局字典，但不返回响应
            _update_prediction_status()
            record_task_history('all', 'resurrect', 'success', '恢复PM2配置')
            return jsonify({"message": "成功恢复PM2配置"}), 200
        except Exception as e:
            error_msg = f"恢复配置后更新状态失败: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            record_task_history('all', 'resurrect', 'warning', error_msg)
            # 尽管更新状态失败，但resurrect命令已经成功执行，所以仍然返回成功
            return jsonify({"message": "PM2配置已恢复，但更新状态失败", "warning": "状态可能不准确，请刷新页面"}), 200
    else:
        error_msg = f"恢复PM2配置失败: {result}"
        record_task_history('all', 'resurrect', 'failed', error_msg)
        return jsonify({"error": error_msg}), 500

# 添加一个内部函数用于更新状态，但不返回HTTP响应
def _update_prediction_status():
    """更新全局prediction_status字典，但不返回响应"""
    try:
        success, result = safe_pm2_command(['jlist'])
        if not success:
            print(f"更新状态失败: {result}")
            return False
            
        output = result.stdout
        if not output or output.strip() == '[]':
            # PM2可能没有运行任何进程，但不一定是错误
            processes = []
        else:
            processes = json.loads(output)
            
        # 更新每个预测任务的状态
        local_status = {}
        for key, script_path in scripts.items():
            script_basename = os.path.basename(script_path)
            is_online = any(
                (script_path in proc.get('pm2_env', {}).get('pm_exec_path', '') or 
                 script_basename == proc.get('pm2_env', {}).get('name', ''))
                and proc.get('pm2_env', {}).get('status', '') == "online"
                for proc in processes
            )
            local_status[key] = is_online
        
        # 安全地更新全局字典
        with status_lock:  # 获取锁
            global prediction_status
            prediction_status.update(local_status)
        
        return True
    except Exception as e:
        error_msg = f"更新状态时出错: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return False

# 获取任务历史记录
@autopredict_bp.route('/history', methods=['GET'])
def get_task_history():
    task_type = request.args.get('type')    # 可选，筛选特定类型
    action = request.args.get('action')   # 可选，筛选特定操作
    limit = request.args.get('limit', 50, type=int)  # 默认返回最近50条记录
    offset = request.args.get('offset', 0, type=int)  # 分页偏移量
    
    try:
        with db_session() as db:
            query = db.query(TaskHistory).order_by(TaskHistory.created_at.desc())
            
            # 应用筛选条件
            if task_type:
                query = query.filter(TaskHistory.task_type == task_type)
            if action:
                query = query.filter(TaskHistory.action == action)
                
            # 应用分页
            total = query.count()
            history = query.offset(offset).limit(limit).all()
            
            # 转换为可序列化的字典
            result = []
            for item in history:
                result.append({
                    'id': item.id,
                    'task_id': item.task_id,
                    'task_type': item.task_type,
                    'action': item.action,
                    'status': item.status,
                    'created_at': item.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'details': item.details,
                    'user': item.user
                })
            
            return jsonify({
                'total': total,
                'offset': offset,
                'limit': limit,
                'data': result
            })
        
    except Exception as e:
        error_msg = f"获取任务历史记录出错: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({'error': error_msg}), 500

# 查询任务状态（训练、预测、参数优化）
@autopredict_bp.route('/task_status', methods=['GET'])
def get_task_status():
    prediction_type = request.args.get('type')
    date_str = request.args.get('date', datetime.datetime.now().strftime('%Y%m%d'))
    # 获取参数优化执行日（0-6 表示周一到周日）
    param_opt_day = request.args.get('param_opt_day', None)
    if param_opt_day is not None:
        param_opt_day = int(param_opt_day)
    else:
        # 默认参数优化日
        param_opt_day_map = {
            'short': 4,        # 周五
            'medium': 3,       # 周四
            'supershort': 6    # 周日
        }
        param_opt_day = param_opt_day_map.get(prediction_type, 5)
    
    if not prediction_type or prediction_type not in prediction_status:
        return jsonify({'error': '无效的预测类型'}), 400
    
    # 初始化状态对象
    status = {
        'training': False,
        'prediction': False,
        'paramOpt': False,
        'trainingTime': '',
        'predictionTime': '',
        'paramOptTime': '',
        'predictionCount': 0,
        'predictionCompleted': False # 新增字段，用于区分 short/medium 的完成与运行中
    }
    
    try:
        # 解析日期
        try:
            selected_date = datetime.datetime.strptime(date_str, '%Y%m%d')
        except ValueError:
            return jsonify({'error': '日期格式无效，请使用YYYYMMDD格式'}), 400
        
        is_today = selected_date.date() == datetime.datetime.now().date()
        is_current_week = (datetime.datetime.now() - selected_date).days < 7
        
        # 检查训练任务状态（通过flag文件）
        train_flag_path = os.path.join(log_dirs[prediction_type]['train'], f"{date_str}_train_done.flag")
        if os.path.exists(train_flag_path):
            status['training'] = True
            status['trainingTime'] = datetime.datetime.fromtimestamp(os.path.getmtime(train_flag_path)).strftime('%Y-%m-%d %H:%M:%S')
        
        # 检查参数优化任务状态 - 修改为根据参数优化日计算周期
        # 计算所选日期在其所在周的星期几（0-6表示周一到周日）
        selected_weekday = selected_date.weekday()
        
        # 计算参数优化周期的开始日期
        # 如果当前日期的星期几大于等于参数优化日，就查找本周的参数优化记录
        # 否则查找上周的参数优化记录
        days_diff = 0
        if selected_weekday >= param_opt_day:
            # 计算到本周参数优化日的天数差
            days_diff = selected_weekday - param_opt_day
        else:
            # 计算到上周参数优化日的天数差
            days_diff = selected_weekday + 7 - param_opt_day
        
        # 找到对应的参数优化日期
        param_opt_date = selected_date - datetime.timedelta(days=days_diff)
        param_opt_date_str = param_opt_date.strftime('%Y%m%d')
        
        # 查找参数优化完成标志
        param_flag_path = os.path.join(log_dirs[prediction_type]['param'], f"{param_opt_date_str}_param_opt_done.flag")
        
        # 如果找不到精确日期的标志文件，尝试查找当周的标志文件（兼容现有逻辑）
        if not os.path.exists(param_flag_path):
            # 计算该参数优化日所在周的周一
            param_opt_monday = param_opt_date - datetime.timedelta(days=param_opt_date.weekday())
            monday_str = param_opt_monday.strftime('%Y%m%d')
            param_flag_path = os.path.join(log_dirs[prediction_type]['param'], f"{monday_str}_param_opt_done.flag")
        
        if os.path.exists(param_flag_path):
            status['paramOpt'] = True
            status['paramOptTime'] = datetime.datetime.fromtimestamp(os.path.getmtime(param_flag_path)).strftime('%Y-%m-%d %H:%M:%S')
        
        # 检查预测任务状态
        if prediction_type == 'supershort':
            # 超短期预测需要检查预测日志
            predict_log_dir = log_dirs[prediction_type]['predict']
            
            # 查找指定日期的所有日志文件 (用于获取最新时间)
            date_logs = glob.glob(os.path.join(predict_log_dir, f"{date_str}*.log"))

            # 通过检查auto_predict目录下的flag文件来计算预测完成次数和状态
            predict_flag_dir = os.path.join(log_dirs[prediction_type]['base'], 'auto_predict')
            predict_done_flags = []
            if os.path.exists(predict_flag_dir):
                # 查找指定日期的所有预测完成标志文件
                 predict_done_flags = glob.glob(os.path.join(predict_flag_dir, f"predict_{date_str}*.flag"))
                 status['predictionCount'] = len(predict_done_flags)
            else:
                 status['predictionCount'] = 0 # Default to 0 if flag dir doesn't exist

            # 超短期的 'prediction' 状态表示任务是否 *应该* 在运行或已完成当天次数
            # 如果当天完成次数 >= 96，则标记为 True (完成)
            # 如果当天完成次数 < 96 但 > 0，或者 PM2 进程在运行 (仅限今天)，也标记为 True (运行中)
            status['prediction'] = status['predictionCount'] >= 96

            if status['predictionCount'] > 0:
                 # If any prediction was done, get the time of the latest flag
                 latest_flag = max(predict_done_flags, key=os.path.getmtime)
                 status['predictionTime'] = datetime.datetime.fromtimestamp(os.path.getmtime(latest_flag)).strftime('%Y-%m-%d %H:%M:%S')
            elif date_logs: # Fallback to log time if no flags but logs exist
                 latest_log = max(date_logs, key=os.path.getmtime)
                 status['predictionTime'] = datetime.datetime.fromtimestamp(os.path.getmtime(latest_log)).strftime('%Y-%m-%d %H:%M:%S')

            # 只有当天才检查PM2进程状态，并用来判断是否 "运行中"
            if is_today:
                predict_online = query_pm2_state(scripts[prediction_type])
                if predict_online and status['predictionCount'] < 96:
                    status['prediction'] = True # Mark as 'running'
        elif prediction_type == 'supershort':
            # 超短超期预测需要检查预测日志
            predict_log_dir = log_dirs[prediction_type]['predict']
            
            # 查找指定日期的所有日志文件 (用于获取最新时间)
            date_logs = glob.glob(os.path.join(predict_log_dir, f"{date_str}*.log"))

            # 通过检查auto_predict目录下的flag文件来计算预测完成次数和状态
            predict_flag_dir = os.path.join(log_dirs[prediction_type]['base'], 'auto_predict')
            predict_done_flags = []
            if os.path.exists(predict_flag_dir):
                # 查找指定日期的所有预测完成标志文件
                predict_done_flags = glob.glob(os.path.join(predict_flag_dir, f"predict_{date_str}*.flag"))
                status['predictionCount'] = len(predict_done_flags)
            else:
                status['predictionCount'] = 0 # Default to 0 if flag dir doesn't exist

            # 超短超期预测每15分钟一次，一天应该有96次
            status['prediction'] = status['predictionCount'] >= 96

            if status['predictionCount'] > 0:
                # If any prediction was done, get the time of the latest flag
                latest_flag = max(predict_done_flags, key=os.path.getmtime)
                status['predictionTime'] = datetime.datetime.fromtimestamp(os.path.getmtime(latest_flag)).strftime('%Y-%m-%d %H:%M:%S')
            elif date_logs: # Fallback to log time if no flags but logs exist
                latest_log = max(date_logs, key=os.path.getmtime)
                status['predictionTime'] = datetime.datetime.fromtimestamp(os.path.getmtime(latest_log)).strftime('%Y-%m-%d %H:%M:%S')
                
            # 只有当天才检查PM2进程状态，并用来判断是否 "运行中"
            if is_today:
                predict_online = query_pm2_state(scripts[prediction_type])
                if predict_online and status['predictionCount'] < 96:
                    status['prediction'] = True # Mark as 'running'
        else: # short and medium
            # 短期和中期预测查找完成标志文件
            # predict_flag_dir = os.path.join(log_dirs[prediction_type]['base'], 'predictions') # 旧逻辑：错误的目录假设
            # 使用训练日志目录查找标志文件，因为标志文件似乎在此处生成
            predict_flag_dir = log_dirs[prediction_type].get('train') # 获取训练日志目录路径
            
            if not predict_flag_dir:
                # 如果找不到训练日志目录配置，记录错误并跳过检查
                print(f"错误：未找到 {prediction_type} 类型的训练日志目录配置")
                status['prediction'] = False
                status['predictionCompleted'] = False
            else:
                # 假设完成标志文件名为 YYYYMMDD_predict_done.flag
                predict_flag_path = os.path.join(predict_flag_dir, f"{date_str}_predict_done.flag")

                # --- 添加调试日志 ---
                print(f"DEBUG: Checking for prediction flag: {predict_flag_path}")
                flag_exists = os.path.exists(predict_flag_path)
                print(f"DEBUG: Flag exists result: {flag_exists}")
                # --- 结束调试日志 ---

                if flag_exists: # 使用变量简化后续判断
                    status['prediction'] = True 
                    status['predictionCompleted'] = True # 标记为真正完成
                    status['predictionTime'] = datetime.datetime.fromtimestamp(os.path.getmtime(predict_flag_path)).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    status['prediction'] = False 
                    status['predictionCompleted'] = False # 默认未完成

                # 只有当天才检查PM2进程状态作为补充（但主要依赖flag）
                # 如果flag不存在，但PM2进程在运行（仅限今天），可能表示正在运行但未完成
                if is_today and not status['predictionCompleted']: # 仅在今天且未完成时检查PM2
                    script_online = query_pm2_state(scripts[prediction_type])
                    if script_online:
                         status['prediction'] = True # 任务状态是存在的 (运行中)
                         # predictionCompleted 保持 False

        # --- 添加调试日志 ---
        print(f"DEBUG: Final status for {prediction_type} on {date_str}: {status}")
        # --- 结束调试日志 ---
        return jsonify({'status': status})
    except Exception as e:
        print(f"获取任务状态失败: {str(e)}")
        return jsonify({'error': '获取任务状态失败', 'details': str(e)}), 500

