import schedule
import time
import os
import logging
import logging.handlers  # Added for TimedRotatingFileHandler
import sys
import subprocess
from datetime import datetime, timedelta, timezone
import threading
import argparse

# 定义业务时区（北京时间，UTC+8）
BUSINESS_TIMEZONE = timezone(timedelta(hours=8))

# 获取当前脚本的绝对路径和目录
current_script_path = os.path.abspath(__file__)
current_script_dir = os.path.dirname(current_script_path)

# 导入配置，确保标志文件路径一致性
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(current_script_dir))))
    from auto_scripts.scripts.short.config_short import AUTO_PRE_TRAIN_LOG_DIR
except ImportError:
    # 如果导入失败，使用相对路径
    AUTO_PRE_TRAIN_LOG_DIR = os.path.join(current_script_dir, 'logs')
    logging.warning(f"无法导入config_short，使用默认日志目录: {AUTO_PRE_TRAIN_LOG_DIR}")

# 基于脚本位置设置绝对路径

base_log_dir = os.path.dirname(AUTO_PRE_TRAIN_LOG_DIR)
scheduler_log_dir = os.path.join(base_log_dir, 'scheduler')  # Directory for scheduler logs
# log_file_path = os.path.join(current_script_dir, "scheduler.log") # Removed old log file path

# 确保日志目录存在
os.makedirs(scheduler_log_dir, exist_ok=True)  # Ensure scheduler log directory exists

# 配置日志
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 创建文件处理器，使用绝对路径
scheduler_base_log_file = os.path.join(scheduler_log_dir, 'scheduler.log')
file_handler = logging.handlers.TimedRotatingFileHandler(
    scheduler_base_log_file,
    when="midnight",      # Rotate at midnight
    interval=1,           # Daily rotation
    backupCount=30,       # Keep 30 backup files
    encoding="utf-8"
)
file_handler.setLevel(logging.INFO)

# 定义日志格式
formatter = logging.Formatter("%(asctime)s - %(message)s")
file_handler.setFormatter(formatter)

# 将处理器添加到日志记录器
logger.addHandler(file_handler)

# 添加控制台处理器，使日志同时显示在控制台
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 任务状态
task_executed = False  # 记录当天训练任务是否成功执行
prediction_triggered_today = False # 记录当天预测任务是否已被触发
# 记录连续失败的次数
prediction_launch_failures = 0
MAX_RETRY_ATTEMPTS = 3

DEFAULT_WIND_FARM_CODE = os.environ.get('DEFAULT_WIND_FARM_CODE', 'default-farm')


def _normalize_wind_farm_code(value: str) -> str:
    value = (value or '').strip()
    return value or DEFAULT_WIND_FARM_CODE


parser = argparse.ArgumentParser(description='Scheduler for short term auto prediction.')
parser.add_argument('--wind-farm-code', dest='wind_farm_code', default=os.environ.get('WIND_FARM_CODE'))
parser.add_argument('--run-train-now', action='store_true', help='立即执行训练任务')
parser.add_argument('--run-predict-now', action='store_true', help='立即执行预测任务')
parsed_args, remaining_argv = parser.parse_known_args()
WIND_FARM_CODE = _normalize_wind_farm_code(parsed_args.wind_farm_code)
os.environ['WIND_FARM_CODE'] = WIND_FARM_CODE

# 重写 sys.argv，保留未解析的参数以兼容 schedule 库等
sys.argv = [sys.argv[0]] + remaining_argv

# 开发模式：添加命令行参数解析
run_training_now = parsed_args.run_train_now

logging.info(f"scheduler_short 启动，风场编码: {WIND_FARM_CODE}")

# 动态构建脚本路径，基于当前脚本的位置
auto_pre_train_script = os.path.join(current_script_dir, "auto_pre_train.py")
logging.info(f"auto_pre_train脚本路径: {auto_pre_train_script}")

# 发送告警的函数
def send_alert(message, severity="warning"):
    """向监控系统发送告警
    
    Args:
        message: 告警消息
        severity: 严重程度，如 "info", "warning", "error", "critical"
    """
    try:
        alert_message = f"【风电预测系统】【{severity.upper()}】: {message}"
        logging.error(f"发送告警: {alert_message}")
        
        # 在此添加实际的告警发送逻辑，如发送邮件、短信、钉钉、企业微信等
        # 例如:
        # import requests
        # webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=xxxx"
        # data = {"msgtype": "text", "text": {"content": alert_message}}
        # response = requests.post(webhook_url, json=data)
        # if response.status_code != 200:
        #     logging.error(f"钉钉告警发送失败: {response.text}")
    except Exception as e:
        logging.error(f"发送告警时出错: {e}")

# 根据操作系统动态确定 Python 解释器路径和Conda环境
def get_python_interpreter():
    if sys.platform.startswith('linux'):
        # 假设在 Linux/Docker 环境中，使用固定的 Conda 环境路径
        conda_env_path = "/opt/conda/envs/wind-power-env"
        logging.info(f"检测到 Linux/Docker 环境，使用Conda环境: {conda_env_path}")
        return conda_env_path, f"conda run -p {conda_env_path} python"
    elif sys.platform.startswith('win'):
        # 在 Windows 开发环境中，尝试使用当前激活的Conda环境
        if 'CONDA_PREFIX' in os.environ:
            conda_env_path = os.environ['CONDA_PREFIX']
            logging.info(f"检测到 Windows 环境，使用当前激活的Conda环境: {conda_env_path}")
            return conda_env_path, f"conda run -p {conda_env_path} python"
        else:
            # 如果没有激活Conda环境，使用当前Python解释器
            logging.info(f"检测到 Windows 环境，但未找到激活的Conda环境，使用当前Python解释器: {sys.executable}")
            return None, sys.executable
    elif sys.platform.startswith('darwin'):
        # macOS环境，与Windows类似处理
        if 'CONDA_PREFIX' in os.environ:
            conda_env_path = os.environ['CONDA_PREFIX']
            logging.info(f"检测到 macOS 环境，使用当前激活的Conda环境: {conda_env_path}")
            return conda_env_path, f"conda run -p {conda_env_path} python"
        else:
            logging.info(f"检测到 macOS 环境，但未找到激活的Conda环境，使用当前Python解释器: {sys.executable}")
            return None, sys.executable
    else:
        # 其他未知操作系统，使用系统默认Python
        logging.warning(f"未知的操作系统平台 '{sys.platform}'，尝试使用系统默认Python")
        return None, "python"

# 获取适用于当前平台的Python解释器命令
conda_env_path, python_cmd = get_python_interpreter()
logging.info(f"将使用以下命令执行Python脚本: {python_cmd}")

# 使用subprocess执行命令的辅助函数
def run_command(command, timeout=3600, async_run=False):
    """
    使用subprocess执行命令，捕获输出并记录状态
    
    Args:
        command: 要执行的命令列表或字符串
        timeout: 命令执行超时时间（秒），默认1小时
        async_run: 是否异步执行（不等待命令完成）
    
    Returns:
        bool: 命令是否成功（返回码为0）
        int: 命令的返回码
    """
    logging.info(f"执行命令: {command}")
    
    if async_run:
        # 异步执行模式，不等待命令完成
        try:
            if isinstance(command, str):
                # 使用Popen在后台运行命令
                process = subprocess.Popen(
                    command, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                logging.info(f"命令已在后台启动，进程ID: {process.pid}")
                return True, 0
            else:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                logging.info(f"命令已在后台启动，进程ID: {process.pid}")
                return True, 0
        except Exception as e:
            logging.error(f"启动后台命令时发生异常: {str(e)}")
            return False, -1
    
    # 同步执行模式，等待命令完成但有超时限制
    try:
        # 如果是字符串命令，我们需要设置shell=True
        if isinstance(command, str):
            result = subprocess.run(command, shell=True, text=True, 
                                   capture_output=True, check=False,
                                   timeout=timeout)
        else:
            result = subprocess.run(command, text=True, 
                                   capture_output=True, check=False,
                                   timeout=timeout)
        
        # 记录标准输出和错误
        if result.stdout:
            logging.info(f"命令输出: {result.stdout}")
        if result.stderr:
            logging.warning(f"命令错误: {result.stderr}")
            
        # 检查返回状态
        if result.returncode == 0:
            logging.info(f"命令执行成功，返回码: {result.returncode}")
            return True, result.returncode
        else:
            logging.error(f"命令执行失败，返回码: {result.returncode}")
            return False, result.returncode
    except subprocess.TimeoutExpired:
        logging.error(f"命令执行超时 (>{timeout}秒)，但将继续在后台运行")
        return False, -2
    except Exception as e:
        logging.error(f"执行命令时发生异常: {str(e)}")
        return False, -1

def get_train_flag_file(date_str):
    """获取训练完成标志文件的路径"""
    # 与auto_pre_train.py使用相同路径
    return os.path.join(AUTO_PRE_TRAIN_LOG_DIR, f"{date_str}_train_done.flag")

def is_train_done(date_str):
    """检查指定日期的训练是否已完成"""
    flag_file = get_train_flag_file(date_str)
    predict_file = get_short_term_predict_file(date_str)
    
    # 首先检查标志文件
    if os.path.exists(flag_file):
        logging.info(f"检测到{date_str}的训练已经执行过 (标志文件: {flag_file})")
        return True
    
    # 其次直接检查预测结果文件是否存在并且有内容
    if os.path.exists(predict_file):
        try:
            file_size = os.path.getsize(predict_file)
            if file_size > 100:  # 文件大小大于100字节，认为有有效内容
                logging.info(f"检测到{date_str}的预测文件存在且非空 (文件: {predict_file}, 大小: {file_size}字节)")
                # 创建标志文件以记录发现
                with open(flag_file, 'w') as f:
                    f.write(f"Found existing prediction file on {datetime.now(BUSINESS_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}")
                return True
        except Exception as e:
            logging.warning(f"检查预测文件时发生错误: {str(e)}")
    
    return False

def get_predict_flag_file(date_str):
    """获取预测完成标志文件的路径"""
    # 与auto_pre_train.py使用相同路径
    return os.path.join(AUTO_PRE_TRAIN_LOG_DIR, f"{date_str}_predict_done.flag")

def is_predict_done(date_str):
    """检查指定日期的预测是否已完成"""
    flag_file = get_predict_flag_file(date_str)
    if os.path.exists(flag_file):
        logging.info(f"检测到{date_str}的预测已经执行过 (标志文件: {flag_file})")
        return True
    return False

def get_short_term_predict_file(date_str):
    """获取短期预测结果文件路径"""
    # 根据项目实际路径结构调整
    short_pred_dir = os.path.join(current_script_dir, "predict_outputs", date_str)
    # 确保目录存在
    os.makedirs(short_pred_dir, exist_ok=True)
    short_pred_path = os.path.join(short_pred_dir, f"predict_output_{date_str}.csv")
    return short_pred_path

# 在后台执行run_script的函数
def run_script_in_background(mode='train'): # Default to train
    thread = threading.Thread(target=run_script, args=(mode,))
    thread.daemon = True  # 使线程成为守护线程，这样主程序退出时线程也会退出
    thread.start()
    logging.info(f"已在后台线程启动 {mode} 任务")

def run_script(mode='train'): # Default to train
    global task_executed, prediction_triggered_today, prediction_launch_failures
    
    today_date = datetime.now(BUSINESS_TIMEZONE).strftime('%Y%m%d')

    if mode == 'train':
        # 检查今天的训练是否都已完成
        if is_train_done(today_date):
            logging.info(f"今天({today_date})的训练已执行过，无需重复执行")
            if not task_executed: 
                task_executed = True
                logging.info("训练任务状态更新为已执行 (基于标志文件)")
            return
        
        if task_executed:
            logging.info("检测到训练任务已在本次调度器运行中尝试执行，跳过")
            return
        
        logging.info(f"执行 auto_pre_train.py --mode {mode}")
        task_executed = True
        logging.info("标记当天训练任务为正在执行/已尝试执行...")
        command = f"{python_cmd} {auto_pre_train_script} --wind-farm-code {WIND_FARM_CODE} --mode {mode}"
        success, exit_code = run_command(command, async_run=True)
            
        if success:
            logging.info(f"auto_pre_train.py --mode {mode} 已开始在后台执行")
            # 成功启动，重置失败计数
            prediction_launch_failures = 0
        else:
            logging.error(f"启动 auto_pre_train.py --mode {mode} 失败，退出码: {exit_code}")
            task_executed = False # Allow re-try if launch failed
            
            # 增加失败计数并考虑发送告警
            prediction_launch_failures += 1
            if prediction_launch_failures >= MAX_RETRY_ATTEMPTS:
                send_alert(f"短期训练启动连续{prediction_launch_failures}次失败，需要人工干预", "critical")

    elif mode == 'predict':
        if is_predict_done(today_date):
            logging.info(f"今天({today_date})的预测已执行过，无需重复执行")
            prediction_triggered_today = True # Ensure it's marked if already done
            # 成功完成，重置失败计数
            prediction_launch_failures = 0
            return
        
        # Prediction trigger logic is slightly different, it might be called multiple times
        # until the prediction input file is ready. The script itself handles the wait.
        logging.info(f"执行 auto_pre_train.py --mode {mode}")
        # We don't set prediction_triggered_today here, let the main loop control it
        # or the script itself will create a done flag.
        command = f"{python_cmd} {auto_pre_train_script} --wind-farm-code {WIND_FARM_CODE} --mode {mode}"
        success, exit_code = run_command(command, async_run=True)

        if success:
            logging.info(f"auto_pre_train.py --mode {mode} 已开始在后台执行")
            prediction_triggered_today = True # Mark that we've attempted to trigger it
            # 成功启动，重置失败计数
            prediction_launch_failures = 0
        else:
            logging.error(f"启动 auto_pre_train.py --mode {mode} 失败，退出码: {exit_code}")
            # 增加失败计数并考虑发送告警
            prediction_launch_failures += 1
            if prediction_launch_failures >= MAX_RETRY_ATTEMPTS:
                send_alert(f"短期预测启动连续{prediction_launch_failures}次失败，需要人工干预", "critical")

# 每天 3:00 执行训练任务，使用后台执行方式
schedule.every().day.at("03:00").do(run_script_in_background, mode='train')

logging.info("定时任务启动成功，每天 3:00 运行训练，8:00后尝试运行预测")

# 记录当前时间和状态
now = datetime.now(BUSINESS_TIMEZONE)
current_weekday = now.weekday()
weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
today_date = now.strftime('%Y%m%d')

logging.info(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}, 星期: {weekday_names[current_weekday]}")
logging.info(f"当前任务状态: 训练任务已执行={is_train_done(today_date)}, 预测任务已执行={is_predict_done(today_date)},今日预测已触发={prediction_triggered_today}")


if run_training_now:
    logging.info("收到立即执行训练的命令，准备立即执行")
    run_script_in_background(mode='train') 

# Add a new command-line argument for running prediction now
run_prediction_now = parsed_args.run_predict_now
if run_prediction_now:
    logging.info("收到立即执行预测的命令，准备立即执行")
    run_script_in_background(mode='predict')

while True:
    try:
        schedule.run_pending()
        now = datetime.now(BUSINESS_TIMEZONE)
        current_hour = now.hour
        current_minute = now.minute
        current_weekday = now.weekday()
        today_date = now.strftime('%Y%m%d')

        if current_minute == 0:
            logging.info(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}, 星期: {weekday_names[current_weekday]}")
            logging.info(f"当前任务状态: 训练任务已执行={is_train_done(today_date)}, 预测任务已执行={is_predict_done(today_date)}, 今日预测已触发={prediction_triggered_today}")
            # Add file existence checks for clarity
            predict_file = get_short_term_predict_file(today_date)
            logging.info(f"文件状态: 短期CSV存在={os.path.exists(predict_file)}")

        # 补救每日训练任务 (after 03:00, e.g., at 04:00)
        if current_hour >= 4: 
            if not is_train_done(today_date):
                logging.warning(f"检测到 {current_hour}:00 训练未执行或未成功启动，立即补救运行训练")
                run_script_in_background(mode='train')
            elif not task_executed and is_train_done(today_date):
                 # If flag exists but task_executed is false, it means scheduler restarted
                 # or script was run manually. Update status.
                task_executed = True
                logging.info("补救检查：发现今天训练已执行过，更新训练任务状态")
                # 成功完成，重置失败计数
                prediction_launch_failures = 0

        # 每日预测任务 (after 08:00)
        if current_hour >= 8:
            if not is_predict_done(today_date) and not prediction_triggered_today:
                logging.info(f"到达 {current_hour}:{current_minute}，尝试启动预测任务 (如果尚未完成或触发)")
                run_script_in_background(mode='predict')
                # prediction_triggered_today will be set in run_script if successful
            elif not prediction_triggered_today and is_predict_done(today_date):
                # If predict is done but not triggered by this scheduler run, update flag
                prediction_triggered_today = True
                logging.info("补救检查：发现今天预测已执行过，更新预测触发状态")
                # 成功完成，重置失败计数
                prediction_launch_failures = 0

        if current_hour == 0 and current_minute == 0:
            task_executed = False
            prediction_triggered_today = False # Reset for the new day
            prediction_launch_failures = 0  # 每天重置失败计数
            logging.info("任务状态已重置，准备执行新一天的任务")

        # 动态调整睡眠时间
        sleep_interval = 30  # 默认30秒
        if 8 <= current_hour < 9:  # 早上8点到9点是预测文件生成的关键时间
            sleep_interval = 15  # 缩短检查间隔到15秒
        elif 0 <= current_hour < 6:  # 凌晨非关键时间
            sleep_interval = 60  # 延长到60秒
        
        time.sleep(sleep_interval)

    except Exception as e:
        logging.error(f"运行时发生错误: {e}")
        import traceback
        error_trace = traceback.format_exc()
        logging.error(error_trace)
        
        # 对于严重运行时错误发送告警
        send_alert(f"调度器运行时错误：{str(e)[:100]}", "critical")
        
        # 等待一分钟后继续
        time.sleep(60)
