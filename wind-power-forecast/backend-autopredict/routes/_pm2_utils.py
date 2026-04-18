"""PM2 process management utilities for the autopredict module."""

import json
import subprocess
import datetime
import os
import sys
import shutil
import threading
import logging

from flask import current_app
from config import Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state shared with autopredict.py
# ---------------------------------------------------------------------------
prediction_status = {
    'short': False,
    'medium': False,
    'supershort': False
}
status_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Python interpreter detection
# ---------------------------------------------------------------------------

def get_python_interpreter():
    """
    根据当前操作系统环境动态确定Python解释器路径

    Returns:
        str: 适合当前平台的Python解释器路径
    """
    if sys.platform.startswith('linux'):
        # 假设在 Linux/Docker 环境中，使用固定的 Conda 环境路径
        interpreter = '/opt/conda/envs/wind-power-env/bin/python'
        logger.info("检测到 Linux/Docker 环境，使用Python解释器: %s", interpreter)
        return interpreter
    elif sys.platform.startswith('win'):
        # 在 Windows 开发环境中，优先使用当前Python解释器
        interpreter = sys.executable
        logger.info("检测到 Windows 环境，使用当前Python解释器: %s", interpreter)
        return interpreter
    elif sys.platform.startswith('darwin'):
        # macOS环境，与Windows类似
        interpreter = sys.executable
        logger.info("检测到 macOS 环境，使用当前Python解释器: %s", interpreter)
        return interpreter
    else:
        # 其他未知操作系统，使用系统默认Python
        logger.info("未知的操作系统平台 '%s'，使用系统默认'python'", sys.platform)
        return 'python'


# 初始化时获取Python解释器路径
python_interpreter = get_python_interpreter()
logger.info("初始化完成，将使用Python解释器: %s", python_interpreter)

# ---------------------------------------------------------------------------
# PM2 path detection
# ---------------------------------------------------------------------------

def find_pm2_path():
    # 使用shutil.which查找可执行文件路径
    pm2_path = shutil.which('pm2')
    if pm2_path:
        logger.info("找到PM2路径: %s", pm2_path)
        return pm2_path

    # 尝试从环境变量获取
    pm2_path = os.environ.get('PM2_PATH')
    if pm2_path and os.path.exists(pm2_path) and os.access(pm2_path, os.X_OK):
        logger.info("从环境变量获取PM2路径: %s", pm2_path)
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
                    logger.info("在扩展路径中找到PM2: %s", path)
                    return path
        elif os.path.isfile(path_pattern) and os.access(path_pattern, os.X_OK):
            logger.info("在常见位置找到PM2: %s", path_pattern)
            return path_pattern

    # 如果在Windows上运行
    if sys.platform.startswith('win'):
        # 尝试使用npm路径
        npm_path = shutil.which('npm')
        if npm_path:
            npm_dir = os.path.dirname(npm_path)
            pm2_win_path = os.path.join(npm_dir, 'pm2.cmd')
            if os.path.exists(pm2_win_path):
                logger.info("在Windows上找到PM2: %s", pm2_win_path)
                return pm2_win_path

    # 最后的回退选项
    logger.info("未找到PM2可执行文件，使用默认命令: pm2")
    return 'pm2'


# 使用改进的函数获取PM2路径
pm2_cmd = find_pm2_path()

# ---------------------------------------------------------------------------
# Safe PM2 command execution
# ---------------------------------------------------------------------------

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
        logger.debug("执行命令: %s", ' '.join(full_cmd))

        # Special handling for 'pm2 logs' encoding
        is_logs_command = 'logs' in cmd_args and cmd_args[0].lower() == 'logs'

        if capture_output:
            if is_logs_command:
                # Get raw bytes for logs to handle encoding manually
                proc = subprocess.run(
                    full_cmd,
                    capture_output=True,
                    timeout=timeout,
                    check=False
                )
                # Attempt to decode stdout and stderr
                stdout_decoded, stderr_decoded = "", ""
                if proc.stdout:
                    try:
                        stdout_decoded = proc.stdout.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            stdout_decoded = proc.stdout.decode('gbk')
                        except UnicodeDecodeError:
                            stdout_decoded = proc.stdout.decode('latin-1', errors='replace')
                if proc.stderr:
                    try:
                        stderr_decoded = proc.stderr.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            stderr_decoded = proc.stderr.decode('gbk')
                        except UnicodeDecodeError:
                            stderr_decoded = proc.stderr.decode('latin-1', errors='replace')

                # Mimic subprocess.CompletedProcess structure for consistent handling
                class DecodedProcessResult:
                    def __init__(self, stdout_text, stderr_text, return_code):
                        self.stdout = stdout_text
                        self.stderr = stderr_text
                        self.returncode = return_code

                decoded_result = DecodedProcessResult(stdout_decoded, stderr_decoded, proc.returncode)

                if proc.returncode != 0:
                    return False, decoded_result

                return True, decoded_result
            else:  # Original behavior for other commands
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
        else:  # Not capturing output
            result = subprocess.run(
                full_cmd,
                timeout=timeout,
                check=True
            )
            return True, result
    except subprocess.TimeoutExpired as e:
        error_msg = f"命令执行超时 ({timeout}秒): {' '.join(full_cmd)}"
        logger.warning(error_msg)
        return False, error_msg
    except subprocess.CalledProcessError as e:
        error_msg = f"命令执行失败: {e}\n输出: {e.stdout if hasattr(e, 'stdout') else '无'}\n错误: {e.stderr if hasattr(e, 'stderr') else '无'}"
        logger.warning(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"命令执行异常: {str(e)}"
        try:
            current_app.logger.error(error_msg, exc_info=True)
        except RuntimeError:
            logger.error(error_msg, exc_info=True)
        return False, error_msg

# ---------------------------------------------------------------------------
# Periodic PM2 status updates
# ---------------------------------------------------------------------------

def update_pm2_status_periodically():
    """周期性查询PM2并更新全局状态字典"""
    # Avoid circular import — scripts and get_script_name live in autopredict.py
    from routes.autopredict import scripts, get_script_name

    logger.info("[%s] 后台任务：正在更新PM2状态...", datetime.datetime.now())
    local_status = {}  # 先操作局部变量

    processes = get_pm2_processes()

    # 根据找到的进程计算状态
    for key in scripts.keys():
        script_name = get_script_name(key)
        is_online = any(
            proc.get('pm2_env', {}).get('name', '').endswith(f"_{script_name}")
            and proc.get('pm2_env', {}).get('status', '') == "online"
            for proc in processes
        )
        local_status[key] = is_online

    # 安全地更新全局字典
    with status_lock:
        global prediction_status
        prediction_status.update(local_status)

    logger.info("[%s] 后台任务：PM2状态已更新: %s", datetime.datetime.now(), prediction_status)


def _get_running_farm_code(prediction_type, scripts, is_valid_farm_code_fn):
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
                    if is_valid_farm_code_fn(farm_code):
                        return farm_code
    except Exception:
        pass

    return None


def get_pm2_processes():
    success, result = safe_pm2_command(['jlist'])
    if not success:
        return []
    try:
        output = result.stdout.strip() if hasattr(result, 'stdout') and result.stdout else ''
        if not output:
            return []
        processes = json.loads(output)
        return processes if isinstance(processes, list) else []
    except Exception:
        return []


def is_process_online(process_name, processes=None):
    proc_list = processes if processes is not None else get_pm2_processes()
    for proc in proc_list:
        pm2_env = proc.get('pm2_env', {})
        if pm2_env.get('name', '') == process_name and pm2_env.get('status', '') == 'online':
            return True
    return False


def query_pm2_state(script_path):
    """
    查询 pm2 中指定脚本的运行状态，
    只有当进程的 pm_exec_path 包含指定脚本且状态为 "online" 时才返回 True
    """
    success, result = safe_pm2_command(['jlist'])
    if not success:
        logger.debug("查询PM2状态失败: %s", result)
        return False

    try:
        output = result.stdout
        if not output or output.strip() == '[]':
            logger.debug("PM2列表为空或未返回有效数据")
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
                logger.debug("找到匹配的运行中进程: %s", proc_name)
                return True

        return False
    except Exception as e:
        logger.warning("解析PM2状态时出错: %s", e)
        return False
