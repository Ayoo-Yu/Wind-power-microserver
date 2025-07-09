import schedule
import time
import os
import logging
import logging.handlers  # Added for TimedRotatingFileHandler
import sys
import subprocess
import json
from datetime import datetime

# 配置日志
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 创建文件处理器
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 日志文件直接放在 logs 目录下，名为 scheduler_supershort.log 以区分
# log_file = os.path.join(current_script_dir, "logs", "scheduler_supershort.log") # Old path
scheduler_supershort_log_dir = os.path.join(current_script_dir, "logs", "scheduler_supershort")
os.makedirs(scheduler_supershort_log_dir, exist_ok=True) # Ensure directory exists

log_file_path = os.path.join(scheduler_supershort_log_dir, "scheduler_supershort.log")

file_handler = logging.handlers.TimedRotatingFileHandler(
    log_file_path,
    when="midnight",
    interval=1,
    backupCount=30,
    encoding="utf-8"
)
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s") # 更详细的日志格式
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 任务状态
task_supershort_train_executed_today = False # 记录当天 "超短期" 训练任务是否执行 (对应 train_supershort.py)

# 开发模式：添加命令行参数解析
run_supershort_training_now = "--run-supershort-train-now" in sys.argv # 指的是超短期训练 (train_supershort.py)

# 定义日志目录路径
log_dir_base = os.path.join(current_script_dir, "logs") # 主日志目录
log_dir_supershort_train = os.path.join(log_dir_base, "supershort_train_flags") # 存放 train_supershort.py 相关flag

# 动态构建脚本路径，基于当前脚本的位置
train_supershort_script_path = os.path.join(current_script_dir, "train_supershort.py")
predict_supershort_script_path = os.path.join(current_script_dir, "predict_supershort.py")
logging.info(f"train_supershort.py脚本路径: {train_supershort_script_path}")
logging.info(f"predict_supershort.py脚本路径: {predict_supershort_script_path}")

# 根据操作系统动态确定 Python 解释器路径和Conda环境
def get_python_interpreter():
    """
    Determines the Python interpreter and command prefix based on the OS.
    Returns:
        tuple: (conda_env_path_or_name, python_command_prefix_or_direct_path)
               conda_env_path_or_name can be a path or an environment name (or None).
               python_command_prefix_or_direct_path is the command string or direct path to python.
    """
    if sys.platform.startswith('linux'):
        # Docker environment, use a fixed Conda environment path
        # Prefer direct path if possible, but ensure it works in Docker
        conda_env_path = "/opt/conda/envs/wind-power-env"
        direct_python_path = os.path.join(conda_env_path, "bin", "python")
        if os.path.exists(direct_python_path):
            logging.info(f"检测到 Linux/Docker 环境，使用直接Python路径: {direct_python_path}")
            return conda_env_path, direct_python_path
        else:
            logging.warning(f"Linux/Docker: 直接Python路径 {direct_python_path} 未找到，回退到 conda run 命令")
            return conda_env_path, f"conda run -p {conda_env_path} python"

    elif sys.platform.startswith('win') or sys.platform.startswith('darwin'): # macOS and Windows
        platform_name = "Windows" if sys.platform.startswith('win') else "macOS"
        python_exe_name = "python.exe" if sys.platform.startswith('win') else "python"

        # 1. 尝试从当前激活的 Conda 环境 (CONDA_PREFIX) 获取直接路径
        if 'CONDA_PREFIX' in os.environ:
            conda_env_path = os.environ['CONDA_PREFIX']
            direct_python_path = os.path.join(conda_env_path, python_exe_name)
            if sys.platform.startswith('darwin'): # macOS bin folder
                direct_python_path = os.path.join(conda_env_path, 'bin', python_exe_name)
            
            if os.path.exists(direct_python_path):
                logging.info(f"检测到 {platform_name} 环境，使用当前激活的 Conda 环境的直接Python路径: {direct_python_path}")
                return conda_env_path, direct_python_path
            else:
                logging.warning(f"{platform_name}: CONDA_PREFIX ({conda_env_path}) 中的Python路径 {direct_python_path} 未找到。将尝试其他方法。")

        # 2. 尝试通过名称查找 Conda 环境并获取其 python.exe/python 路径
        conda_env_name = "wind-power-env" 
        try:
            # 获取 conda 环境列表及其路径
            env_list_cmd = "conda env list --json"
            proc_env_list = subprocess.run(env_list_cmd, shell=True, capture_output=True, text=True, check=True)
            env_data = json.loads(proc_env_list.stdout)
            envs = env_data.get("envs", [])
            found_env_path = None
            for env_path in envs:
                if conda_env_name == os.path.basename(env_path.rstrip('/\\')):
                    found_env_path = env_path
                    break
            
            if found_env_path:
                direct_python_path_from_name = os.path.join(found_env_path, python_exe_name)
                if sys.platform.startswith('darwin'): # macOS bin folder
                     direct_python_path_from_name = os.path.join(found_env_path, 'bin', python_exe_name)
                if os.path.exists(direct_python_path_from_name):
                    logging.info(f"检测到 {platform_name} 环境，通过名称 '{conda_env_name}' 找到直接Python路径: {direct_python_path_from_name}")
                    return conda_env_name, direct_python_path_from_name
                else:
                    logging.warning(f"{platform_name}: 在名为 '{conda_env_name}' ({found_env_path}) 的Conda环境中未找到Python路径 {direct_python_path_from_name}。回退到 conda run。")
                    # 如果通过名称找到了环境但找不到python，则回退到 conda run -n <name> python
                    return conda_env_name, f"conda run -n {conda_env_name} python"
            else:
                 logging.warning(f"{platform_name}: 未在 Conda 环境列表中找到名为 '{conda_env_name}' 的环境。")

        except Exception as e:
            logging.error(f"检查Conda环境 (通过名称 '{conda_env_name}') 时出错 ({platform_name}): {e}. 将尝试回退方案。")

        # 3. 如果上述方法都失败，回退到 sys.executable (当前Python解释器)
        #    这通常意味着要么不在Conda环境中，要么无法可靠地确定Conda环境的Python路径
        logging.warning(f"检测到 {platform_name} 环境，但无法确定 Conda 环境 '{conda_env_name}' 的直接Python路径，将使用当前Python解释器: {sys.executable}")
        return None, sys.executable
    else:
        logging.warning(f"未知的操作系统平台 '{sys.platform}'，尝试使用系统默认'python'")
        return None, "python"

# 获取适用于当前平台的Python解释器命令
conda_env_identifier, python_cmd = get_python_interpreter() # python_cmd 现在可能是直接路径或 conda run 命令
logging.info(f"将使用以下命令执行Python脚本: {python_cmd}")

# 使用subprocess执行命令的辅助函数
def run_command(command_str_or_list):
    """
    Executes a command using subprocess, captures output, and logs status.
    Args:
        command_str_or_list: The command to execute (string or list of strings).
    Returns:
        bool: True if the command was successful (return code 0), False otherwise.
        int: The return code of the command.
    """
    logging.info(f"执行命令: {command_str_or_list}")
    try:
        is_shell_cmd = isinstance(command_str_or_list, str)
        result = subprocess.run(
            command_str_or_list,
            shell=is_shell_cmd, # Use shell=True if command is a string
            text=True,
            capture_output=True,
            check=False # We check returncode manually
        )

        # 添加详细日志
        logging.info(f"命令执行完毕。返回码: {result.returncode}")
        if result.stdout:
            # 为了避免日志过长，可以考虑只记录部分stdout，或者在特定条件下记录
            # 例如，只在调试模式下完整记录，或者截断超长输出
            stdout_to_log = result.stdout
            if len(stdout_to_log) > 2000: # 例如，截断超过2000字符的stdout
                stdout_to_log = stdout_to_log[:1000] + "... (stdout truncated) ..." + stdout_to_log[-1000:]
            logging.info(f"命令标准输出 (stdout):\n---- STDOUT START ----\n{stdout_to_log}\n---- STDOUT END ----")
        else:
            logging.info("命令标准输出 (stdout) 为空。")

        if result.stderr:
            # stderr 通常更重要，可以考虑完整记录，或者至少比stdout更长
            stderr_to_log = result.stderr
            if len(stderr_to_log) > 2000: # 例如，截断超过2000字符的stderr
                stderr_to_log = stderr_to_log[:1000] + "... (stderr truncated) ..." + stderr_to_log[-1000:]
            logging.warning(f"命令标准错误 (stderr):\n---- STDERR START ----\n{stderr_to_log}\n---- STDERR END ----")
        else:
            logging.info("命令标准错误 (stderr) 为空。")


        if result.returncode == 0:
            logging.info(f"命令判断为执行成功 (基于返回码0)。")
            return True, result.returncode
        else:
            logging.error(f"命令判断为执行失败 (基于返回码 {result.returncode})。")
            return False, result.returncode
    except FileNotFoundError as e: # Specific error for command not found
        logging.error(f"执行命令时发生错误: 命令或程序未找到 - {e}")
        return False, -1 # Or e.errno
    except Exception as e:
        logging.error(f"执行命令时发生异常: {e}", exc_info=True)
        return False, -1 # Generic error code for other exceptions

# --- 超短期每日训练 (train_supershort.py) 标志文件函数 ---
def get_supershort_train_flag_file_for_date(date_str):
    return os.path.join(log_dir_supershort_train, f"{date_str}_supershort_train_done.flag")

def is_supershort_train_done_today():
    today_date_str = datetime.now().strftime('%Y%m%d')
    flag_file = get_supershort_train_flag_file_for_date(today_date_str)
    if os.path.exists(flag_file):
        logging.info(f"检测到今天 ({today_date_str}) 的超短期训练(train_supershort)已经执行过 (标志文件: {flag_file})")
        return True
    return False

def mark_supershort_train_done_today():
    today_date_str = datetime.now().strftime('%Y%m%d')
    flag_file = get_supershort_train_flag_file_for_date(today_date_str)
    os.makedirs(os.path.dirname(flag_file), exist_ok=True) #确保目录存在
    with open(flag_file, 'w') as f:
        f.write(f'Supershort training (train_supershort.py) done for day {today_date_str} on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\\n')
    logging.info(f"超短期训练(train_supershort)完成 ({today_date_str})，已创建标志文件: {flag_file}")
# --- 结束：超短期每日训练标志文件函数 ---

def run_supershort_train_script():
    """执行超短期训练脚本 train_supershort.py (每日)"""
    global task_supershort_train_executed_today
    
    if is_supershort_train_done_today():
        logging.info("今天的超短期训练(train_supershort)已执行过，无需重复执行。")
        task_supershort_train_executed_today = True
        return

    logging.info("开始执行超短期模型训练任务 (train_supershort.py - 每日)")
    # 使用动态构建的脚本路径和Python命令
    # command = f'{python_cmd} "{train_supershort_script_path}"' # Add quotes for paths with spaces

    # --- 临时测试：直接使用 sys.executable ---
    original_command = f'{python_cmd} "{train_supershort_script_path}"' # 这是原来的命令
    # test_command = f'{sys.executable} "{train_supershort_script_path}"' # 使用当前调度器的Python解释器
    
    # logging.info(f"原计划命令: {original_command}")
    # logging.info(f"临时测试 - 将使用直接命令执行: {test_command}")
    # command_to_run = test_command #  <<<< 在这里选择要运行的命令
    command_to_run = original_command # 现在 python_cmd 可能已经是直接路径了，所以恢复使用它
    # --- 临时测试结束 ---

    success, exit_code = run_command(command_to_run)
    if success:
        logging.info("train_supershort.py (每日超短期训练) 执行成功")
        mark_supershort_train_done_today()
        task_supershort_train_executed_today = True
    else:
        logging.error(f"train_supershort.py (每日超短期训练) 执行失败，退出码: {exit_code}")

def run_supershort_predict_script():
    """执行超短期预测脚本 predict_supershort.py (每15分钟)"""
    logging.info("开始执行超短期预测任务 (predict_supershort.py)")
    # 使用动态构建的脚本路径和Python命令
    command = f'{python_cmd} "{predict_supershort_script_path}"' # Add quotes for paths with spaces

    success, exit_code = run_command(command)
    if success:
        logging.info("predict_supershort.py 执行成功")
    else:
        logging.error(f"predict_supershort.py 执行失败，退出码: {exit_code}")

# 每日 04:00 执行超短期模型训练 (train_supershort.py)
schedule.every().day.at("04:00").do(run_supershort_train_script)

# 每15分钟执行一次超短期预测 (predict_supershort.py) -> 修改为特定分钟
# schedule.every(15).minutes.do(run_supershort_predict_script)
schedule.every().hour.at(":08").do(run_supershort_predict_script)
schedule.every().hour.at(":23").do(run_supershort_predict_script)
schedule.every().hour.at(":38").do(run_supershort_predict_script)
schedule.every().hour.at(":53").do(run_supershort_predict_script)

logging.info("定时任务启动成功 (scheduler_supershort.py):")
logging.info("  - 每日超短期训练 (train_supershort.py): 04:00")
# logging.info("  - 每15分钟超短期预测 (predict_supershort.py)")
logging.info("  - 超短期预测 (predict_supershort.py) 执行时间: 每小时的 08, 23, 38, 53 分")

# 确保日志目录存在
os.makedirs(log_dir_base, exist_ok=True)
os.makedirs(log_dir_supershort_train, exist_ok=True)

# 启动时根据标志文件初始化内存状态变量
today_date_str = datetime.now().strftime('%Y%m%d')
task_supershort_train_executed_today = is_supershort_train_done_today() # 超短期每日训练状态

now = datetime.now() # Get current time again for logging initial state
current_weekday = now.weekday()
weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
logging.info(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}, 星期: {weekday_names[current_weekday]}")
logging.info(f"当前任务状态初始化:")
logging.info(f"  - 每日超短期训练(train_supershort)今日已执行: {task_supershort_train_executed_today}")

# 开发模式：根据命令行参数立即执行任务
if run_supershort_training_now: # For supershort daily train (train_supershort.py)
    logging.info("收到立即执行每日超短期训练(train_supershort)的命令，准备立即执行...")
    run_supershort_train_script()

while True:
    try:
        schedule.run_pending()
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        today_date_str = now.strftime('%Y%m%d')

        if current_minute == 0: # 每小时0分时记录状态
            if current_hour == 0: # 每天0点重置每日任务状态 (通过重新检查flag)
                task_supershort_train_executed_today = is_supershort_train_done_today()
                
            logging.info(f"[每小时状态@{now.strftime('%H:%M')}] 超短期训练执行: {task_supershort_train_executed_today}")

        # --- 监控与补救逻辑 ---
        
        # 每日超短期训练 (train_supershort.py, 计划 02:00)
        if current_hour >= 2:
            supershort_train_flag_exists = is_supershort_train_done_today()
            if supershort_train_flag_exists and not task_supershort_train_executed_today:
                logging.info(f"检测到每日超短期训练(train_supershort)标志文件存在，更新内存状态为已执行。")
                task_supershort_train_executed_today = True
            elif not task_supershort_train_executed_today and not supershort_train_flag_exists:
                logging.warning(f"检测到 {today_date_str} 02:00 每日超短期训练(train_supershort)未执行且无标志，立即补救运行")
                run_supershort_train_script()

        time.sleep(28) # 略小于30秒，确保不会错过分钟边界

    except Exception as e:
        logging.error(f"调度器(scheduler_supershort.py)主循环发生错误: {e}", exc_info=True)
        time.sleep(60)
