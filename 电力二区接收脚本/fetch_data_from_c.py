#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import sys
import re
import subprocess
import time
import tempfile
import stat
import pty  # 添加pty模块用于模拟终端
import signal
from pathlib import Path
from datetime import datetime, timedelta  # 添加 timedelta 用于日期计算
import pandas as pd  # 添加 pandas 用于数据处理
import numpy as np  # 添加 numpy 用于风速计算
try:
    from etext2csv import convert_etext_to_csv # 导入转换函数
    logging.info("成功导入 E 文本转换模块 (etext2csv)。")
except ImportError:
    # 这个错误理论上不应该发生，因为 install.sh 应该已处理依赖
    logging.critical("错误：无法导入 etext2csv 模块。请确保 etext2csv.py 在同一目录。")
    # 如果在启动时就失败，直接退出可能更安全
    sys.exit(1)
except Exception as import_err:
    logging.critical(f"导入 etext2csv 时发生未知错误: {import_err}", exc_info=True)
    sys.exit(1)
# --- 配置项 ---
# --- 服务器 C (源) ---
REMOTE_HOST = "120.26.142.227"
REMOTE_PORT = 22
REMOTE_USER = "root"
SSH_KEY_PATH = "/home/ecs-user/.ssh/id_rsa"  # SSH私钥路径 - 替换为你的实际密钥路径

# --- 服务器 C 上的文件路径 ---
REMOTE_BASE_DIR = "/data/from_server_c"

# --- 服务器 B (本机) 上的文件路径 ---
LOCAL_DOWNLOAD_DIR = "/data/from_server_c"
LOCAL_TEMP_DIR = "/data/from_server_c/temp"
STATE_FILE = "/opt/scripts/ecmwf_fetcher/downloaded_state.txt"
LOG_FILE = "/var/log/ecmwf_fetcher.log"
CSV_OUTPUT_DIR = "/data/from_server_c/csv"
DAILY_PRE_CSV_DIR = "/data/daily_pre_csv"  # 新建的预测输入文件根目录
SHORT_PRED_DIR = os.path.join(DAILY_PRE_CSV_DIR, "short")  # 短期预测输入子目录
MIDDLE_PRED_DIR = os.path.join(DAILY_PRE_CSV_DIR, "middle")  # 中期预测输入子目录
BATCH_FILE = os.path.join(tempfile.gettempdir(), "sftp_batch.txt") # SFTP批处理文件放临时目录

# --- 预测输入文件模板 ---
EXAMPLE_DIR_NAME = "example" # 样板文件所在子目录名
TEMPLATE_FILENAME = "template_predict_input.csv" # 样板文件名
TEMPLATE_FILE_PATH = os.path.join(DAILY_PRE_CSV_DIR, EXAMPLE_DIR_NAME, TEMPLATE_FILENAME) # 完整的样板文件路径

# --- 文件匹配规则 ---
# 修改批次目录匹配模式以适应YYYY_MMDD格式
BATCH_DIR_PATTERN = re.compile(r"(\d{4})_(\d{4})$")
# 预测文件模式：使用 C? 使 'C' 成为可选，匹配 _DQYC_ 或 _CDQYC_
PREDICTION_FILE_PATTERN = re.compile(r"^YCSJ_.*_C?DQYC_.*\.dat$")
# 气象文件模式（保持不变）
WEATHER_FILE_PATTERN = re.compile(r"^YCSJ_.*_QXYC_.*\.dat$")
# 用于从文件名提取 YYYYMMDD 的正则表达式
FILENAME_DATE_PATTERN = re.compile(r"_(\d{8})_")
# 时间戳列名，请根据实际CSV文件结构调整
TIMESTAMP_COLUMN_NAME = 'Timestamp'

# --- 其他配置 ---
LOCK_FILE = "/tmp/ecmwf_fetcher.lock" # 锁文件也建议放在临时目录或受控目录
MAX_RUNTIME_SECONDS = 600 # 脚本最长运行时间 (此脚本中未实际强制执行，但保留配置)
SFTP_TIMEOUT = 60 # SFTP命令本身的超时时间（秒）

# --- 日志设置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- 锁文件管理 ---
def acquire_lock():
    try:
        # 确保锁文件目录存在
        os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
        lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lock_fd, str(os.getpid()).encode())
        os.close(lock_fd)
        logging.info(f"成功获取锁文件: {LOCK_FILE}")
        return True
    except FileExistsError:
        logging.warning(f"锁文件 {LOCK_FILE} 已存在，可能已有实例在运行。")
        # 尝试读取PID
        try:
            with open(LOCK_FILE, 'r') as f:
                pid_in_lock = f.read().strip()
                logging.warning(f"锁文件包含PID: {pid_in_lock}")
                # 可以尝试检查该PID是否存在，但简单起见，这里直接退出
        except Exception as e:
            logging.warning(f"读取锁文件PID失败: {e}")
        return False
    except OSError as e:
        logging.error(f"获取锁文件时发生错误: {e}", exc_info=True)
        return False

def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.unlink(LOCK_FILE)
            logging.info(f"已释放锁文件: {LOCK_FILE}")
    except OSError as e:
        logging.error(f"释放锁文件失败: {e}")

# --- 状态管理 ---
def load_downloaded_state():
    state = set()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line:
                        state.add(stripped_line)
            logging.info(f"从 {STATE_FILE} 加载了 {len(state)} 条下载记录。")
        except Exception as e:
            logging.error(f"加载状态文件 {STATE_FILE} 失败: {e}", exc_info=True)
    else:
        logging.info(f"状态文件 {STATE_FILE} 不存在，将创建新的状态。")
    return state

def save_downloaded_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        # 使用临时文件确保原子写入
        temp_state_file = STATE_FILE + ".tmp"
        with open(temp_state_file, 'w', encoding='utf-8') as f:
            for remote_path in sorted(list(state)):
                f.write(f"{remote_path}\n")
        os.replace(temp_state_file, STATE_FILE) # 原子替换
        logging.info(f"成功将 {len(state)} 条下载记录保存到 {STATE_FILE}。")
    except Exception as e:
        logging.error(f"保存状态文件 {STATE_FILE} 失败: {e}", exc_info=True)

# --- SFTP命令执行 (使用SSH密钥) ---
def execute_sftp_cmd(commands):
    """执行SFTP命令并返回结果 (使用SSH密钥认证)"""
    batch_file_path = None # 用于确保清理

    try:
        # 1. 创建临时批处理文件
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".txt", prefix="sftp_batch_") as f:
            batch_file_path = f.name
            for cmd in commands:
                f.write(f"{cmd}\n")
        logging.debug(f"已创建SFTP批处理文件: {batch_file_path}")

        # 2. 构建SFTP命令 (使用SSH密钥)
        sftp_cmd = [
            "sftp", 
            "-o", "StrictHostKeyChecking=no",
            "-o", "IdentitiesOnly=yes",  # 只使用指定的密钥
            "-i", SSH_KEY_PATH,  # 指定SSH私钥
            "-b", batch_file_path,
            "-P", str(REMOTE_PORT),
            f"{REMOTE_USER}@{REMOTE_HOST}"
        ]
        
        logging.info(f"准备使用SSH密钥执行SFTP命令")
        
        # 3. 执行命令
        process = subprocess.run(
            sftp_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=SFTP_TIMEOUT
        )
        
        # 4. 处理结果
        if process.returncode != 0:
            logging.error(f"SFTP命令执行失败，返回码: {process.returncode}")
            logging.error(f"SFTP STDERR:\n{process.stderr.strip()}")
            logging.error(f"SFTP STDOUT:\n{process.stdout.strip()}")
            return False, process.stdout
        
        logging.info(f"SFTP 命令执行成功")
        return True, process.stdout

    except subprocess.TimeoutExpired:
        logging.error(f"SFTP命令执行超时 (超过 {SFTP_TIMEOUT} 秒)。", exc_info=True)
        return False, "Timeout"
    except Exception as e:
        logging.error(f"执行SFTP命令时发生未知错误: {e}", exc_info=True)
        return False, str(e)
    finally:
        # 清理临时文件
        if batch_file_path and os.path.exists(batch_file_path):
            try:
                os.unlink(batch_file_path)
                logging.debug(f"已删除SFTP批处理文件: {batch_file_path}")
            except OSError as e:
                logging.warning(f"删除SFTP批处理文件失败: {e}")


# --- 远程目录列表 (使用 ls -1 进行简化解析) ---
def list_remote_dir(remote_path):
    """列出远程目录内容 (使用 ls -1)"""
    # 使用 ls -1 获取简单列表，每行一个条目
    commands = [
        f"ls -1 \"{remote_path}\"", # 给路径加上引号以防包含空格
        "quit"
    ]

    success, output = execute_sftp_cmd(commands)
    if not success:
        logging.warning(f"无法列出远程目录: {remote_path}")
        return None # 返回 None 表示失败

    # 解析输出
    items = []
    # 过滤掉 sftp 提示符、连接信息和空行
    lines = [line.strip() for line in output.splitlines() if line.strip() and not line.startswith("sftp>") and "Connecting to" not in line and "Connected to" not in line and "Changing to" not in line and "Fetching" not in line and "Retrieving" not in line and "remote host" not in line and "Cannot stat" not in line] # 添加 Cannot stat 过滤

    if not lines:
        # 区分是真 K 空目录还是 ls 命令本身有问题
        if "No such file or directory" in output: # 检查 stderr 或 stdout 是否包含错误信息
             logging.error(f"远程路径不存在或无法访问: {remote_path}")
             return None # 路径问题，返回 None
        else:
             logging.info(f"远程目录 {remote_path} 为空或未找到任何项目。")
             return [] # 明确是空列表

    logging.debug(f"为 {remote_path} 解析出的远程项目: {lines}")

    # ls -1 不区分目录和文件，调用者需要根据模式判断
    # 返回 (名称, is_dir_flag) 元组列表，is_dir_flag 暂时为 None
    return [(name, None) for name in lines]


# --- 文件下载 ---
def download_file(remote_path, local_path):
    """下载指定文件"""
    local_dir = os.path.dirname(local_path)
    try:
        # 确保本地目标目录存在
        os.makedirs(local_dir, exist_ok=True)
    except OSError as e:
        logging.error(f"创建本地目录失败 {local_dir}: {e}")
        return False

    # 给路径加上引号，处理可能存在的空格
    commands = [
        f"get \"{remote_path}\" \"{local_path}\"",
        "quit"
    ]

    success, output = execute_sftp_cmd(commands)
    if not success:
         # 记录失败时的输出以供调试
         logging.error(f"SFTP 'get' 命令失败。远程: '{remote_path}', 本地: '{local_path}'. SFTP输出:\n{output}")
    return success


# --- 核心同步逻辑 (基本不变，适配 list_remote_dir 返回值) ---
def sync_latest_files():
    logging.info("======== 开始同步任务 ========")
    downloaded_count = 0
    processed_count = 0
    downloaded_state = load_downloaded_state()
    newly_downloaded = set()

    try:
        # --- 1. 查找最新的批次目录 ---
        logging.info(f"正在查找远程目录 {REMOTE_BASE_DIR} 下最新的批次目录...")

        items_result = list_remote_dir(REMOTE_BASE_DIR)

        if items_result is None: # list_remote_dir 失败
             logging.error(f"无法获取远程目录 {REMOTE_BASE_DIR} 的列表，任务中止。")
             return False # 表示任务失败
        if not items_result: # 目录为空
             logging.info(f"远程目录 {REMOTE_BASE_DIR} 为空或未找到任何项目。")
             return True # 任务正常结束，只是没找到东西

        batch_dirs = []
        potential_items = [item[0] for item in items_result] # 获取所有名称
        logging.info(f"远程目录列表: {potential_items}")
        
        for name in potential_items:
            # 提取目录名部分（如果是完整路径)
            dir_name = os.path.basename(name.rstrip('/')) if '/' in name else name
            logging.debug(f"处理目录: {name}, 提取的目录名: {dir_name}")
            
            # 对目录名进行批次目录模式匹配
            match = BATCH_DIR_PATTERN.search(dir_name)
            if match:
                year = match.group(1)  # 年份 (YYYY)
                mmdd = match.group(2)  # 月日 (MMDD)
                # 记录原始完整名称、年份和月日
                batch_dirs.append((name, year, mmdd))
                logging.debug(f"匹配成功: {name} -> 年份={year}, 月日={mmdd}")
            else:
                logging.debug(f"目录 {dir_name} 不匹配批次目录模式")
                
        if not batch_dirs:
            logging.warning(f"在 {REMOTE_BASE_DIR} 未找到匹配日期格式的批次目录。找到的项目: {potential_items}")
            return True # 任务正常结束
            
        logging.info(f"找到的批次目录: {batch_dirs}")

        # 按年份和日期排序，找到最新的
        batch_dirs.sort(key=lambda x: (x[1], x[2]), reverse=True)
        latest_batch_dirname = batch_dirs[0][0]
        # 构造路径，如果latest_batch_dirname已经是完整路径，则直接使用
        if latest_batch_dirname.startswith('/'):
            latest_batch_path = latest_batch_dirname
        else:
            latest_batch_path = f"{REMOTE_BASE_DIR}/{latest_batch_dirname}"
        logging.info(f"找到最新的批次目录: {latest_batch_path}")

        # 提取日期信息，用于本地目录组织
        batch_year = batch_dirs[0][1]
        batch_mmdd = batch_dirs[0][2]
        # 从MMDD格式中提取月份
        batch_month = batch_mmdd[:2]
        local_date_dir = os.path.join(LOCAL_DOWNLOAD_DIR, f"{batch_year}_{batch_month}")
        logging.info(f"将在本地创建或使用日期目录: {local_date_dir}")

        # --- 2. 查找批次目录中的目标文件 ---
        logging.info(f"正在查找目录 {latest_batch_path} 中的目标文件...")

        files_in_batch_result = list_remote_dir(latest_batch_path)

        if files_in_batch_result is None:
            logging.error(f"无法获取最新批次目录 {latest_batch_path} 的列表，任务中止。")
            return False
        if not files_in_batch_result:
            logging.info(f"最新的批次目录 {latest_batch_path} 为空。")
            return True # 正常结束

        files_in_batch = [item[0] for item in files_in_batch_result] # 获取文件名列表
        # 使用 remote_path 作为 key 来确保唯一性，并存储 local_path
        files_to_download = {}
        new_files_count = 0
        checked_files_count = 0

        logging.info(f"开始在目录 {latest_batch_path} 中查找所有需要下载的新文件...")

        for name in files_in_batch:
            checked_files_count += 1
            # 提取文件名部分（如果是完整路径）
            file_name = os.path.basename(name) if '/' in name else name

            # 构造完整的远程路径
            if name.startswith('/'): # 假设 ls 返回了绝对路径
                remote_path = name
            else: # 假设 ls 返回了相对名称
                remote_path = f"{latest_batch_path}/{name}"

            # 检查是否匹配任一模式
            is_prediction = PREDICTION_FILE_PATTERN.match(file_name)
            is_weather = WEATHER_FILE_PATTERN.match(file_name)

            if is_prediction or is_weather:
                file_type_str = "预测" if is_prediction else "气象"
                logging.debug(f"检查 {file_type_str} 文件候选: {remote_path}")

                # 核心逻辑：检查状态文件
                if remote_path not in downloaded_state:
                    # 是新文件！添加到下载列表
                    local_final_path = os.path.join(local_date_dir, file_name)
                    files_to_download[remote_path] = local_final_path
                    logging.info(f"发现新的 {file_type_str} 文件，添加到下载列表: {remote_path}")
                    new_files_count += 1
                    # 继续检查下一个文件，可能有更多新文件
                else:
                    # 文件已下载过
                    logging.info(f"{file_type_str} 文件 {remote_path} 已下载过，跳过。")
                    # 继续检查下一个文件

        logging.info(f"文件查找完成。检查了 {checked_files_count} 个条目，发现 {new_files_count} 个新文件需要下载。")

        if not files_to_download:
            logging.info("没有找到需要下载的新文件。")
            return True # 正常结束

        # --- 3. 下载并转换新文件 ---
        try:
            # 确保基础下载和临时目录存在
            os.makedirs(LOCAL_DOWNLOAD_DIR, exist_ok=True)
            os.makedirs(LOCAL_TEMP_DIR, exist_ok=True)
            # 确保E文本的日期子目录存在
            os.makedirs(local_date_dir, exist_ok=True)
            logging.info(f"本地目录已准备就绪: {local_date_dir}")
        except OSError as e:
            logging.error(f"创建本地下载目录失败: {e}", exc_info=True)
            return False # 无法创建目录，任务失败

        # 注意：processed_count 现在基于找到的新文件数
        processed_count = len(files_to_download)
        downloaded_count = 0 # 重置计数器，用于实际成功下载的文件
        newly_downloaded = set() # 重置集合，用于本次成功处理的文件

        # 调整下载循环以遍历字典
        for remote_path, local_final_path in files_to_download.items():
            # 从 local_final_path 获取文件名用于临时文件和类型判断
            file_name = os.path.basename(local_final_path)
            # 判断文件类型，用于日志
            file_type = "unknown"
            if "_CDQYC_" in file_name:
                file_type = "超短期预测"
            elif "_DQYC_" in file_name: # 注意这里的 elif
                file_type = "短期预测"
            elif "_QXYC_" in file_name:
                file_type = "气象预测"

            local_temp_path = os.path.join(LOCAL_TEMP_DIR, file_name)
            logging.info(f"开始下载 [{file_type}] 文件: \"{remote_path}\" -> \"{local_temp_path}\"")

            download_successful = False
            try:
                # 先清理可能存在的旧临时文件
                if os.path.exists(local_temp_path): os.unlink(local_temp_path)
                download_successful = download_file(remote_path, local_temp_path)
            except Exception as download_err:
                logging.error(f"下载文件 {remote_path} 时发生异常: {download_err}", exc_info=True)
                # 再次尝试清理临时文件
                if os.path.exists(local_temp_path):
                    try: os.unlink(local_temp_path)
                    except OSError: pass
                continue # 处理下一个文件

            if download_successful:
                logging.info(f"SFTP 'get' 命令成功完成: \"{remote_path}\"")

                # 验证文件是否存在且非空
                if not os.path.exists(local_temp_path):
                     logging.error(f"下载声称成功，但本地临时文件不存在: \"{local_temp_path}\"。跳过此文件。")
                     continue
                try:
                    if os.path.getsize(local_temp_path) == 0:
                        logging.warning(f"下载的文件为空: \"{local_temp_path}\"。将删除临时文件。")
                        os.unlink(local_temp_path)
                        continue
                except OSError as e:
                    logging.error(f"检查文件大小失败: \"{local_temp_path}\", 错误: {e}. 跳过此文件.")
                    continue

                # --- 移动到最终的 E 文本存放位置 ---
                try:
                    logging.info(f"移动文件到 E 文本存放位置: \"{local_temp_path}\" -> \"{local_final_path}\"")
                    os.rename(local_temp_path, local_final_path) # 移动成功

                    # --- 开始转换逻辑 ---
                    logging.info(f"开始转换 E 文本文件: {local_final_path}")
                    conversion_successful = False # 转换成功标志，先置为 False
                    target_csv_dir = None         # 目标 CSV 子目录路径
                    etext_filename = os.path.basename(local_final_path) # 保存原始E文本文件名

                    # 确定目标子目录
                    if "_CDQYC_" in etext_filename:
                        target_subdir_name = "CDQ"
                        target_csv_dir = os.path.join(CSV_OUTPUT_DIR, target_subdir_name)
                        logging.info(f"文件 '{etext_filename}' 归类为超短期，目标目录: {target_csv_dir}")
                    elif "_DQYC_" in etext_filename: # 使用 elif 避免重复匹配 CDQYC
                        target_subdir_name = "DQ"
                        target_csv_dir = os.path.join(CSV_OUTPUT_DIR, target_subdir_name)
                        logging.info(f"文件 '{etext_filename}' 归类为短期，目标目录: {target_csv_dir}")
                    elif "_QXYC_" in etext_filename:
                        target_subdir_name = "QXYC"
                        target_csv_dir = os.path.join(CSV_OUTPUT_DIR, target_subdir_name)
                        logging.info(f"文件 '{etext_filename}' 归类为气象预测，目标目录: {target_csv_dir}")
                    else:
                        logging.warning(f"文件名 '{etext_filename}' 不匹配任何已知模式 (_CDQYC_, _DQYC_, _QXYC_)，无法确定目标子目录。将跳过此文件的转换。")

                    # 如果确定了目标目录，则执行转换
                    if target_csv_dir:
                        try:
                            # 1. 确保目标 CSV 子目录存在
                            os.makedirs(target_csv_dir, exist_ok=True)

                            # 2. 调用转换函数，输出到目标子目录
                            csv_output_path = convert_etext_to_csv(
                                etext_filepath=local_final_path,
                                output_dir=target_csv_dir # 传递包含子目录的路径
                            )

                            if csv_output_path:
                                logging.info(f"成功将 '{etext_filename}' 转换为 CSV: '{csv_output_path}'")
                                conversion_successful = True # 标记转换成功

                                # --- 新增：对 CSV 文件添加风速特征 ---
                                ws_function_called = False
                                ws_added = False
                                try:
                                    # 根据 target_subdir_name 判断调用哪个函数
                                    if target_subdir_name == "QXYC":
                                        logging.info(f"尝试为 QXYC CSV (简单格式) 添加风速特征: {csv_output_path}")
                                        ws_added = add_wind_speed_features_simple(str(csv_output_path))
                                        ws_function_called = True
                                    elif target_subdir_name in ["DQ", "CDQ"]:
                                        logging.info(f"尝试为 {target_subdir_name} CSV (宽格式) 添加风速特征: {csv_output_path}")
                                        ws_added = add_wind_speed_features_wide(str(csv_output_path))
                                        ws_function_called = True
                                    else:
                                        # 如果遇到未知的子目录名，则不进行风速计算
                                        logging.warning(f"未知的 target_subdir_name '{target_subdir_name}'，跳过风速特征添加步骤。")

                                    # 记录调用结果 (如果函数被调用了)
                                    if ws_function_called:
                                        if ws_added:
                                            logging.info(f"成功为 {csv_output_path} 添加或检查了风速特征。")
                                        else:
                                            # 函数内部应记录失败或未执行的具体原因
                                            logging.warning(f"为 {csv_output_path} 添加风速特征失败或未执行。")
                                    
                                except Exception as ws_err:
                                    # 捕获调用风速函数本身的意外错误
                                    logging.error(f"调用风速特征添加函数处理 {csv_output_path} 时发生意外错误: {ws_err}", exc_info=True)

                                # --- 新增：对于DQ类型文件，调用DQ CSV处理函数 ---
                                if target_subdir_name == "DQ":
                                    logging.info(f"检测到已生成并处理（含风速检查）的 DQ CSV，准备进行补全和预测输入文件生成...")
                                    try:
                                        # 调用DQ CSV处理函数，传入CSV文件路径和原始E文本文件名
                                        process_dq_csv(str(csv_output_path), etext_filename)
                                    except Exception as processing_err:
                                        logging.error(f"处理DQ CSV {csv_output_path} 时出错: {processing_err}", exc_info=True)
                                        # 继续执行主流程，处理其他文件

                                # --- （可选）删除原始 E 文本文件 ---
                                # 如果不再需要原始文件，取消下面代码的注释
                                # try:
                                #     os.unlink(local_final_path)
                                #     logging.info(f"已删除已成功转换的原始 E 文本文件: {local_final_path}")
                                # except OSError as e_del:
                                #     logging.warning(f"删除原始 E 文本文件失败 {local_final_path}: {e_del}")
                                # ------------------------------------
                            else:
                                # convert_etext_to_csv 返回 None，表示转换失败
                                logging.error(f"E 文本文件转换失败 (函数返回 None): {local_final_path}")
                                # conversion_successful 保持 False
                        except Exception as convert_err:
                            # 捕获转换过程中的其他异常
                            logging.error(f"处理或转换文件 {local_final_path} 到 {target_csv_dir} 时出错: {convert_err}", exc_info=True)
                            # conversion_successful 保持 False
                    # --- 转换逻辑结束 ---

                    # --- 根据转换结果更新状态 ---
                    if conversion_successful:
                        # 只有下载、移动、转换都成功，才记录状态
                        newly_downloaded.add(remote_path)
                        downloaded_count += 1
                        logging.info(f"文件下载和转换处理完成: \"{remote_path}\"")
                    elif target_csv_dir: # 如果尝试了转换但失败了
                         logging.warning(f"由于转换失败，文件 {remote_path} 的状态未更新，将保留 E 文本文件 {local_final_path} 以供下次重试。")
                    # 如果 target_csv_dir 为 None (因为文件名不匹配)，则不执行任何操作，也不更新状态

                except OSError as move_err:
                     # 这是 os.rename 失败的情况
                     logging.error(f"移动下载的文件失败: {move_err}。文件可能保留在临时目录: \"{local_temp_path}\"", exc_info=True)
                     # 清理临时文件
                     if os.path.exists(local_temp_path):
                         try: os.unlink(local_temp_path)
                         except OSError: pass
            else: # download_successful is False
                logging.error(f"下载文件失败 (download_file 返回 False): \"{remote_path}\"")
                # 清理临时文件
                if os.path.exists(local_temp_path):
                    try: os.unlink(local_temp_path)
                    except OSError: pass

        # --- 4. 更新状态文件 ---
        if newly_downloaded:
            # 确保从加载的状态开始合并
            current_state = load_downloaded_state() # 重新加载以防万一
            updated_state = current_state.union(newly_downloaded)
            save_downloaded_state(updated_state)

        logging.info(f"本次任务计划下载 {processed_count} 个文件，成功下载并处理了 {downloaded_count} 个文件。")
        # 只要没有发生让任务无法继续的错误，就返回 True
        return True

    except Exception as e:
        logging.error(f"同步任务执行过程中发生未捕获的严重错误: {e}", exc_info=True)
        return False # 任务异常失败
    finally:
        logging.info("======== 同步任务结束 ========")


# --- 主程序入口 ---
def main():
    start_time = time.time()
    logging.info(f"脚本启动 (PID: {os.getpid()})。")

    # 检查 sftp 命令是否存在
    try:
        subprocess.run(["which", "sftp"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info("系统 'sftp' 命令已找到。")
    except (FileNotFoundError, subprocess.CalledProcessError):
         logging.critical("错误: 系统 'sftp' 命令未找到。请确保 OpenSSH 客户端已安装。脚本退出。")
         sys.exit(1)

    # 检查并创建必要的本地目录
    required_dirs = [
        os.path.dirname(LOG_FILE),
        LOCAL_DOWNLOAD_DIR,
        LOCAL_TEMP_DIR,
        CSV_OUTPUT_DIR,
        os.path.dirname(STATE_FILE),
        os.path.dirname(LOCK_FILE),
        tempfile.gettempdir(), # 确保临时目录存在
        DAILY_PRE_CSV_DIR,     # 新增：预测输入文件根目录
        SHORT_PRED_DIR,        # 新增：短期预测输入目录
        MIDDLE_PRED_DIR        # 新增：中期预测输入目录
    ]
    try:
        for d in required_dirs:
            # 检查路径非空且是目录
            if d and isinstance(d, str):
               os.makedirs(d, exist_ok=True)
    except OSError as e:
        logging.critical(f"创建本地目录失败: {e}。请检查权限。脚本退出。")
        sys.exit(1)

    # 获取运行锁
    if not acquire_lock():
        # acquire_lock 内部已记录警告
        sys.exit(1)

    exit_code = 1  # 默认为失败
    try:
        # 执行核心同步逻辑
        sync_successful = sync_latest_files()
        if sync_successful:
            exit_code = 0 # 同步过程正常完成（可能部分文件下载失败，但流程没中断）
        else:
            exit_code = 1 # 同步过程中发生严重错误导致中断

    except Exception as e:
        logging.critical(f"执行 sync_latest_files 时发生顶层错误: {e}", exc_info=True)
        exit_code = 1 # 确保顶层异常也标记为失败
    finally:
        # 确保释放锁
        release_lock()
        end_time = time.time()
        logging.info(f"脚本执行完毕，耗时 {end_time - start_time:.2f} 秒。退出码: {exit_code}")
        # 确保清理临时文件 (虽然 execute_sftp_cmd 的 finally 会做，这里再加一层保险)
        for fpath in [BATCH_FILE]:
             if os.path.exists(fpath):
                 try: os.unlink(fpath)
                 except OSError: pass
        sys.exit(exit_code)

# --- 用于处理DQ CSV的功能函数 ---
def find_latest_cdq_csv(cdq_dir):
    """在CDQ目录中查找最新的CSV文件"""
    latest_file = None
    latest_timestamp = datetime.min  # 初始化为最早时间

    cdq_path = Path(cdq_dir)
    if not cdq_path.is_dir():
        logging.warning(f"CDQ目录不存在: {cdq_dir}")
        return None

    try:
        # 遍历目录下的所有CSV文件
        for csv_file in cdq_path.glob("*.csv"):
            # 从文件名提取时间戳，假设格式为 ..._YYYYMMDD_HHMMSS.csv
            match = re.search(r"_(\d{8})_(\d{6})\.csv$", csv_file.name)
            if match:
                try:
                    # 组合日期和时间字符串
                    file_dt_str = f"{match.group(1)}{match.group(2)}"
                    # 解析为datetime对象
                    file_dt = datetime.strptime(file_dt_str, "%Y%m%d%H%M%S")
                    # 如果当前文件时间戳比记录的最新时间戳还要新，则更新
                    if file_dt > latest_timestamp:
                        latest_timestamp = file_dt
                        latest_file = csv_file
                except ValueError:
                    logging.warning(f"无法从文件名解析日期时间: {csv_file.name}")
                    continue  # 解析失败，跳过这个文件
            else:
                logging.debug(f"文件名 {csv_file.name} 不匹配CDQ时间戳模式。")

        if latest_file:
            logging.info(f"找到最新的CDQ CSV文件: {latest_file}")
        else:
            logging.warning(f"在目录 {cdq_dir} 中未找到有效的CDQ CSV文件。")

        return latest_file
    except Exception as e:
        logging.error(f"查找最新的CDQ CSV文件时出错: {e}", exc_info=True)
        return None

def process_dq_csv(dq_csv_path_str, original_etext_filename):
    """
    使用最新的CDQ数据补全DQ CSV，并生成预测输入文件。
    (现在包含列对齐步骤)

    Args:
        dq_csv_path_str (str): 新创建的DQ CSV文件的路径
        original_etext_filename (str): 原始E-text文件名 (例如: YCSJ_..._DQYC_20250501_191500.dat)
    """
    logging.info(f"开始处理DQ CSV文件: {dq_csv_path_str}")
    dq_csv_path = Path(dq_csv_path_str)
    # 假设CDQ CSV文件存放在 /data/from_server_c/csv/CDQ 目录下
    cdq_dir = os.path.join(CSV_OUTPUT_DIR, "CDQ")

    try:
        # --- 1. 读取DQ CSV ---
        if not dq_csv_path.exists():
            logging.error(f"输入的DQ CSV文件不存在: {dq_csv_path}")
            return
        dq_df = pd.read_csv(dq_csv_path)
        if dq_df.empty:
            logging.warning(f"DQ CSV文件为空: {dq_csv_path}，跳过处理。")
            return

        # 确保时间戳列存在并且是datetime类型
        if TIMESTAMP_COLUMN_NAME not in dq_df.columns:
             logging.error(f"DQ CSV文件 {dq_csv_path} 缺少指定的时间戳列 '{TIMESTAMP_COLUMN_NAME}'。无法处理。")
             return
        # 转换时间戳列，无法转换的设为NaT (Not a Time)
        dq_df[TIMESTAMP_COLUMN_NAME] = pd.to_datetime(dq_df[TIMESTAMP_COLUMN_NAME], errors='coerce')
        # 删除时间戳转换失败的行
        dq_df = dq_df.dropna(subset=[TIMESTAMP_COLUMN_NAME])
        if dq_df.empty:
             logging.warning(f"在DQ CSV {dq_csv_path} 中转换时间戳后没有有效数据。")
             return
        # 获取DQ数据中的最晚时间
        dq_latest_time = dq_df[TIMESTAMP_COLUMN_NAME].max()
        logging.info(f"DQ CSV最新时间: {dq_latest_time}")

        # --- 2. 查找并读取最新的CDQ CSV ---
        latest_cdq_csv_path = find_latest_cdq_csv(cdq_dir)
        # 默认情况下，补全后的数据框就是原始的DQ数据框
        df_complemented = dq_df.copy()

        if latest_cdq_csv_path:
            try:
                cdq_df = pd.read_csv(latest_cdq_csv_path)
                if not cdq_df.empty:
                    # 同样检查CDQ文件的时间戳列
                    if TIMESTAMP_COLUMN_NAME not in cdq_df.columns:
                         logging.error(f"CDQ CSV文件 {latest_cdq_csv_path} 缺少时间戳列 '{TIMESTAMP_COLUMN_NAME}'。")
                         # 如果CDQ文件无效，则不进行补全，继续使用原始DQ数据
                    else:
                        cdq_df[TIMESTAMP_COLUMN_NAME] = pd.to_datetime(cdq_df[TIMESTAMP_COLUMN_NAME], errors='coerce')
                        cdq_df = cdq_df.dropna(subset=[TIMESTAMP_COLUMN_NAME])

                        # --- 3. 补全数据 ---
                        # 筛选出CDQ中时间戳晚于DQ最晚时间的数据
                        cdq_complement_df = cdq_df[cdq_df[TIMESTAMP_COLUMN_NAME] > dq_latest_time].copy()

                        if not cdq_complement_df.empty:
                            logging.info(f"找到 {len(cdq_complement_df)} 行来自 {latest_cdq_csv_path} 的数据用于补全 (在 {dq_latest_time} 之后)。")

                            # --- 列对齐与排序保持 ---
                            # 获取 DQ 原始列顺序
                            dq_original_columns = list(dq_df.columns)
                            # 获取 CDQ 补全数据的列集合 (用于快速查找)
                            cdq_complement_columns_set = set(cdq_complement_df.columns)

                            # 找出共有的列，并按照 DQ 的原始顺序排列
                            # 遍历 DQ 的原始列，只保留那些也存在于 CDQ 补全数据中的列
                            ordered_common_columns = [
                                col for col in dq_original_columns
                                if col in cdq_complement_columns_set
                            ]

                            if not ordered_common_columns:
                                 logging.warning(f"DQ 文件 {dq_csv_path} 和 CDQ 补全数据 {latest_cdq_csv_path} 之间没有共同的列名。无法合并。")
                                 # 在这种情况下，df_complemented 保持为原始 dq_df，其列顺序是正确的
                            elif TIMESTAMP_COLUMN_NAME not in ordered_common_columns:
                                # 这种情况理论上不应该发生，因为前面已经检查过 dq_df 有时间戳列
                                # 但作为防御性检查加入
                                logging.error(f"关键的时间戳列 '{TIMESTAMP_COLUMN_NAME}' 不在共同列中，无法安全合并。")
                                # df_complemented 保持为原始 dq_df
                            else:
                                logging.info(f"将使用以下共同列（按DQ顺序）进行合并: {ordered_common_columns}")

                                # 选择并确保 DQ 和 CDQ 补全数据的列都按这个 `ordered_common_columns` 顺序排列
                                dq_df_ordered = dq_df[ordered_common_columns]
                                cdq_complement_df_ordered = cdq_complement_df[ordered_common_columns]

                                # 使用 concat 拼接数据，现在两个部分的列顺序是一致且正确的
                                df_complemented = pd.concat([dq_df_ordered, cdq_complement_df_ordered], ignore_index=True)
                                # 补全后按时间戳排序 (这只影响行顺序，不影响列顺序)
                                df_complemented = df_complemented.sort_values(by=TIMESTAMP_COLUMN_NAME).reset_index(drop=True)
                                logging.info(f"数据补全完成（保持DQ列序），补全后的数据框大小: {df_complemented.shape}")
                        else:
                            logging.info(f"最新的CDQ CSV ({latest_cdq_csv_path}) 没有比DQ CSV ({dq_latest_time}) 更晚的数据，无需补全。")
                            # 在这种情况下，df_complemented 保持为原始 dq_df，其列顺序是正确的
                else:
                    logging.warning(f"最新的CDQ CSV文件为空: {latest_cdq_csv_path}")
            except Exception as read_cdq_err:
                logging.error(f"读取或处理CDQ CSV {latest_cdq_csv_path} 时出错: {read_cdq_err}", exc_info=True)
                # 如果处理CDQ出错，则继续使用原始的DQ数据

        # --- 4. 从原始文件名提取日期并计算下一天 ---
        # 使用正则表达式匹配原始E-text文件名中的日期
        date_match = FILENAME_DATE_PATTERN.search(original_etext_filename)
        if not date_match:
            logging.error(f"无法从原始文件名 '{original_etext_filename}' 中提取日期。无法生成预测输入文件。")
            return

        yyyymmdd_str = date_match.group(1)  # 提取YYYYMMDD字符串
        try:
            # 将字符串解析为日期对象
            current_date = datetime.strptime(yyyymmdd_str, "%Y%m%d")
            # 计算下一天的日期
            next_date = current_date + timedelta(days=1)
            # 格式化下一天的日期为YYYYMMDD字符串
            next_day_str = next_date.strftime("%Y%m%d")
            logging.info(f"从文件名提取日期: {yyyymmdd_str}, 下一天: {next_day_str}")
        except ValueError:
            logging.error(f"从文件名提取的日期格式无效: {yyyymmdd_str}")
            return

        # --- 5. 创建输出目录 ---
        # 确保short和middle子目录存在
        os.makedirs(SHORT_PRED_DIR, exist_ok=True)
        os.makedirs(MIDDLE_PRED_DIR, exist_ok=True)
        # --- (可选) 检查样板目录是否存在，虽然脚本不创建样板文件 ---
        example_dir = os.path.dirname(TEMPLATE_FILE_PATH)
        if not os.path.exists(example_dir):
            logging.warning(f"样板文件目录 {example_dir} 不存在。请确保它包含 '{TEMPLATE_FILENAME}' 文件。")
            # 如果希望在没有模板时跳过对齐或中止，可以在这里添加逻辑

        # --- 6. 准备文件A (short) 数据 ---
        df_short_raw = df_complemented.head(116).copy() # 使用 .copy() 避免 SettingWithCopyWarning
        short_output_filename = f"predict_input_{next_day_str}.csv"
        short_output_path = os.path.join(SHORT_PRED_DIR, short_output_filename)

        # --- 6a. 对齐 Short 文件列 ---
        logging.info(f"尝试为 Short 预测文件对齐列: {short_output_path}")
        # 调用对齐函数，传入原始 short 数据和模板路径
        df_short_aligned = align_columns_to_template(df_short_raw, TEMPLATE_FILE_PATH)

        # 检查对齐是否成功
        if df_short_aligned is not None:
            try:
                # 将对齐后的数据写入CSV
                df_short_aligned.to_csv(short_output_path, index=False, encoding='utf-8')
                logging.info(f"成功生成 Short 预测输入文件 (已对齐): {short_output_path} (包含 {df_short_aligned.shape[0]} 行, {df_short_aligned.shape[1]} 列)")
            except Exception as e:
                logging.error(f"写入对齐后的 Short 预测输入文件 {short_output_path} 失败: {e}", exc_info=True)
        else:
            # 对齐失败 (模板未找到或处理错误)
            logging.error(f"Short 预测数据的列对齐失败。文件将不会被保存: {short_output_path}")
            # 如果希望在对齐失败时仍保存原始(未对齐)文件，取消下面一行的注释并调整日志
            # df_short_raw.to_csv(short_output_path, index=False, encoding='utf-8')
            # logging.warning(f"由于对齐失败，已保存未对齐的 Short 预测文件: {short_output_path}")

        # --- 7. 准备文件B (middle) 数据 ---
        # 注意：df_complemented 是补全后的完整数据
        middle_output_filename = f"predict_input_{next_day_str}.csv"
        middle_output_path = os.path.join(MIDDLE_PRED_DIR, middle_output_filename)

        # --- 7a. 对齐 Middle 文件列 ---
        logging.info(f"尝试为 Middle 预测文件对齐列: {middle_output_path}")
        # 对原始的完整补全数据 df_complemented 进行对齐
        df_middle_aligned = align_columns_to_template(df_complemented.copy(), TEMPLATE_FILE_PATH) # 使用 .copy()

        # 检查对齐是否成功
        if df_middle_aligned is not None:
            try:
                # 将对齐后的数据写入CSV
                df_middle_aligned.to_csv(middle_output_path, index=False, encoding='utf-8')
                logging.info(f"成功生成 Middle 预测输入文件 (已对齐): {middle_output_path} (包含 {df_middle_aligned.shape[0]} 行, {df_middle_aligned.shape[1]} 列)")
            except Exception as e:
                logging.error(f"写入对齐后的 Middle 预测输入文件 {middle_output_path} 失败: {e}", exc_info=True)
        else:
             # 对齐失败 (模板未找到或处理错误)
            logging.error(f"Middle 预测数据的列对齐失败。文件将不会被保存: {middle_output_path}")
            # 如果希望在对齐失败时仍保存原始(未对齐)文件，取消下面一行的注释并调整日志
            # df_complemented.to_csv(middle_output_path, index=False, encoding='utf-8')
            # logging.warning(f"由于对齐失败，已保存未对齐的 Middle 预测文件: {middle_output_path}")

    except pd.errors.EmptyDataError:
        logging.warning(f"尝试读取的DQ CSV文件为空或格式错误: {dq_csv_path}")
    except Exception as e:
        logging.error(f"处理DQ CSV {dq_csv_path} 时发生意外错误 (在预测文件生成阶段): {e}", exc_info=True)

# --- 用于计算和添加风速特征，并重命名 ws* 列的功能函数 (处理 '100u_lat_lon' 格式) ---
def add_wind_speed_features_wide(csv_path_str):
    """
    读取宽格式的 CSV 文件 (列名如 '100u_lat_lon'), 计算风速特征 (ws100_lat_lon),
    将 *仅 ws* 列的坐标部分替换为 ID (如 'ws100_13'), 并将更新后的 DataFrame
    写回（覆盖）原始 CSV 文件。确保原始ws坐标列被移除。

    Args:
        csv_path_str (str): 要处理的 CSV 文件的路径。

    Returns:
        bool: 如果成功处理并写回文件则返回 True，否则返回 False。
    """
    csv_path = Path(csv_path_str)
    logging.info(f"开始为宽格式 CSV 文件 ('数字字母_lat_lon') 添加风速特征并重命名 ws* 坐标: {csv_path}") # 日志更新

    if not csv_path.is_file():
        logging.error(f"输入 CSV 文件未找到，无法处理: {csv_path}")
        return False

    # --- 1. 定义坐标到 ID 的映射字典 ---
    coordinate_mapping = {
        '24.2_103.2': '13', '24.2_103.3': '14', '24.2_103.4': '15',
        '24.1_103.2': '10', '24.1_103.3': '11', '24.1_103.4': '12',
        '24.0_103.2': '7', '24.0_103.3': '8', '24.0_103.4': '9',
        '23.9_103.2': '4', '23.9_103.3': '5', '23.9_103.4': '6',
        '23.8_103.2': '1', '23.8_103.3': '2', '23.8_103.4': '3',
        # 如果有其他坐标点需要映射，继续在这里添加
    }
    # --- 映射定义结束 ---

    try:
        # --- 2. 读取 CSV 文件 ---
        df = pd.read_csv(csv_path)
        if df.empty:
            logging.warning(f"CSV 文件为空: {csv_path}，跳过处理。")
            return True # 文件为空，视为处理"成功"

        # --- 3. 解析列名并分组 u/v 分量 (用于计算风速) ---
        col_pattern_uv = re.compile(r"(\d+)([uv])_(-?\d+(?:\.\d+)?)_(-?\d+(?:\.\d+)?)")
        uv_pairs = {}
        logging.debug(f"开始解析文件 {csv_path.name} 的列名以查找 '数字字母_lat_lon' u/v 对...")
        for col in df.columns:
            match = col_pattern_uv.match(col)
            if match:
                height_str, component, lat_str, lon_str = match.groups()
                try: height = int(height_str)
                except ValueError: continue
                key = (height, lat_str, lon_str)
                if key not in uv_pairs: uv_pairs[key] = {}
                if component == 'u': uv_pairs[key]['u'] = col
                elif component == 'v': uv_pairs[key]['v'] = col

        # --- 4. 计算风速并创建新列 ---
        new_ws_columns = {}
        calculated_ws_col_names = [] # 存储计算出的原始ws列名 (ws...lat_lon)
        features_added = False
        logging.info(f"共找到 {len(uv_pairs)} 个潜在的坐标点。开始计算风速...")
        processed_pairs = 0
        for key, components in uv_pairs.items():
            height, lat_str, lon_str = key
            if 'u' in components and 'v' in components:
                u_col, v_col = components['u'], components['v']
                ws_col_name = f"ws{height}_{lat_str}_{lon_str}" # 构造带坐标的原始风速列名
                calculated_ws_col_names.append(ws_col_name) # 记录这个名字
                try:
                    u_numeric = pd.to_numeric(df[u_col], errors='coerce')
                    v_numeric = pd.to_numeric(df[v_col], errors='coerce')
                    ws_series = np.sqrt(u_numeric**2 + v_numeric**2)
                    nan_mask = u_numeric.isna() | v_numeric.isna()
                    ws_series[nan_mask] = np.nan
                    new_ws_columns[ws_col_name] = ws_series # 存储新计算的Series
                    features_added = True
                    processed_pairs += 1
                except Exception as calc_err:
                    logging.error(f"计算 {ws_col_name} 时出错: {calc_err}", exc_info=True)
            else:
                logging.debug(f"坐标点 {key} 缺少 u 或 v 分量。")
        logging.info(f"成功计算了 {processed_pairs} 个坐标点的风速。")

        # --- 5. 将新计算的风速列添加到 DataFrame ---
        if features_added:
            logging.info(f"正在将 {len(new_ws_columns)} 个新的风速列添加到 DataFrame...")
            for ws_col_name, ws_series in new_ws_columns.items():
                if ws_col_name in df.columns:
                    logging.warning(f"风速列 '{ws_col_name}' 已存在，将被覆盖。")
                df[ws_col_name] = ws_series
        else:
            logging.info("没有新的风速特征被计算或添加。")

        # --- 6. 执行列名重命名 (仅重命名 ws* 列的坐标为ID) ---
        logging.info("开始执行列名重命名（坐标替换为ID，仅限 ws* 列）...")
        rename_pattern = re.compile(r"(ws\d+)_(-?\d+(?:\.\d+)?)_(-?\d+(?:\.\d+)?)") # 修改模式以确保只匹配 ws 开头
        rename_map = {}
        original_ws_latlon_cols = [] # 存储要重命名的原始列名
        renamed_count = 0
        skipped_coord_count = 0

        # 再次迭代列名，构建精确的rename_map
        current_columns = list(df.columns) # 获取当前的列列表
        for original_col in current_columns:
            match = rename_pattern.match(original_col)
            if match:
                prefix_part, lat_str, lon_str = match.groups() # prefix_part is 'wsXXX'
                coord_key = f"{lat_str}_{lon_str}"
                coord_id = coordinate_mapping.get(coord_key)

                if coord_id is not None:
                    new_col_name = f"{prefix_part}_{coord_id}"
                    # 检查目标名称是否与原始名称不同，并且没有列已经叫这个名字了 (防止重命名冲突)
                    if new_col_name != original_col and new_col_name not in current_columns and new_col_name not in rename_map.values():
                        rename_map[original_col] = new_col_name
                        original_ws_latlon_cols.append(original_col) # 记录这个将被重命名的原始列名
                        renamed_count += 1
                    elif new_col_name == original_col:
                         # 如果新旧名字一样，也记录原始名字，可能需要检查是否需要保留
                         if original_col not in original_ws_latlon_cols:
                              original_ws_latlon_cols.append(original_col)
                    elif new_col_name in current_columns:
                         logging.warning(f"目标重命名列 '{new_col_name}' 已存在于DataFrame中，无法将 '{original_col}' 重命名。原始列将被保留。")
                         # 记录这个未被重命名的原始列
                         if original_col not in original_ws_latlon_cols:
                              original_ws_latlon_cols.append(original_col)
                    else: # new_col_name in rename_map.values()
                         logging.warning(f"尝试将列 '{original_col}' 重命名为 '{new_col_name}'，但目标名称已被用于其他列的重命名。跳过此重命名，保留原始列。")
                         # 记录这个未被重命名的原始列
                         if original_col not in original_ws_latlon_cols:
                              original_ws_latlon_cols.append(original_col)
                else:
                    # 坐标在映射表中未找到
                    logging.warning(f"ws 列 '{original_col}' 的坐标 '{coord_key}' 未找到对应的映射ID，该列将保持不变。")
                    skipped_coord_count += 1
                    # 记录这个未被重命名的原始列
                    if original_col not in original_ws_latlon_cols:
                         original_ws_latlon_cols.append(original_col)

        # --- 应用所有有效的重命名 ---
        if rename_map:
            logging.info(f"准备应用以下重命名映射: {rename_map}")
            df = df.rename(columns=rename_map) # 批量重命名
            logging.info(f"列名重命名完成。尝试重命名了 {renamed_count} 个 ws* 列。")
            if skipped_coord_count > 0:
                logging.warning(f"有 {skipped_coord_count} 个 ws* 列因未在映射表中找到对应ID而未被重命名。")

            # --- **新增：显式删除原始列名（保险措施）** ---
            # 获取 rename_map 中的原始列名 (keys)
            original_names_in_map = list(rename_map.keys())
            lingering_original_cols = [col for col in original_names_in_map if col in df.columns]

            if lingering_original_cols:
                logging.warning(f"检测到以下本应被重命名的列仍然存在: {lingering_original_cols}. 将尝试强制删除它们。")
                try:
                    df = df.drop(columns=lingering_original_cols)
                    logging.info(f"已成功强制删除残留的原始列: {lingering_original_cols}")
                except Exception as drop_err:
                    logging.error(f"尝试删除残留原始列时出错: {drop_err}", exc_info=True)
            else:
                logging.info("确认所有通过映射重命名的原始列已被成功替换。")
            # --- 显式删除结束 ---

        else:
            logging.info("没有构建有效的重命名映射，无需执行重命名操作。")

        # --- 7. 写回（覆盖）CSV 文件 ---
        logging.info(f"准备写回更新后的文件: {csv_path}")
        logging.debug(f"最终写回的列名: {list(df.columns)}") # 打印最终列名以供调试
        try:
            df.to_csv(csv_path, index=False, encoding='utf-8')
            logging.info(f"成功将数据写回到: {csv_path}")
            return True
        except Exception as write_err:
            logging.error(f"写回 CSV 文件失败: {csv_path} - {write_err}", exc_info=True)
            return False

    except pd.errors.EmptyDataError:
        logging.warning(f"尝试读取的 CSV 文件为空或格式错误: {csv_path}")
        return False
    except Exception as e:
        logging.error(f"处理宽格式 ('数字字母_lat_lon') CSV 文件 {csv_path} 时发生意外错误: {e}", exc_info=True)
        return False

# --- 用于计算和添加风速特征的功能函数 (处理简单列名) ---
def add_wind_speed_features_simple(csv_path_str):
    """
    读取 CSV 文件 (简单列名), 计算风速特征 (ws10, ws100, ws200),
    并写回（覆盖）原始 CSV 文件。
    
    Args:
        csv_path_str (str): 要处理的 CSV 文件的路径。
        
    Returns:
        bool: 如果成功处理并写回文件则返回 True，否则返回 False。
    """
    csv_path = Path(csv_path_str)
    logging.info(f"开始为 CSV 文件添加风速特征 (处理简单列名): {csv_path}")
    
    if not csv_path.is_file():
        logging.error(f"输入 CSV 文件未找到，无法添加风速特征: {csv_path}")
        return False
    
    try:
        # 1. 读取 CSV 文件
        df = pd.read_csv(csv_path)
        if df.empty:
            logging.warning(f"CSV 文件为空: {csv_path}，跳过风速计算。")
            return True
        
        # 2. 定义需要处理的 u/v 对及其对应的风速列名
        wind_pairs = [
            ('10u', '10v', 'ws10'),
            ('100u', '100v', 'ws100'),
            ('200u', '200v', 'ws200'),
            # 可根据需要添加其他简单格式对
        ]
        
        # 3. 计算风速并添加新列
        features_added = False
        for u_col, v_col, ws_col in wind_pairs:
            # 检查 u 和 v 列是否都存在
            if u_col in df.columns and v_col in df.columns:
                try:
                    # 确保列是数值类型
                    u_numeric = pd.to_numeric(df[u_col], errors='coerce')
                    v_numeric = pd.to_numeric(df[v_col], errors='coerce')
                    
                    # 计算风速 = sqrt(u² + v²)
                    logging.info(f"计算 {ws_col} 从 {u_col} 和 {v_col}")
                    df[ws_col] = np.sqrt(u_numeric**2 + v_numeric**2)
                    features_added = True
                    
                except Exception as calc_err:
                    logging.error(f"计算 {ws_col} 时出错: {calc_err}", exc_info=True)
            else:
                missing_cols = []
                if u_col not in df.columns:
                    missing_cols.append(u_col)
                if v_col not in df.columns:
                    missing_cols.append(v_col)
                logging.warning(f"无法计算 {ws_col}，缺少列: {', '.join(missing_cols)}")
        
        # 4. 如果有新特征被添加，则将更新后的 DataFrame 写回文件
        if features_added:
            logging.info(f"正在写回包含新风速特征的文件: {csv_path}")
            try:
                # 使用与读取时相同的路径来覆盖原文件
                df.to_csv(csv_path, index=False, encoding='utf-8')
                logging.info(f"成功将带有风速特征的数据写回到: {csv_path}")
                return True
            except Exception as write_err:
                logging.error(f"写回带有风速特征的 CSV 文件失败: {csv_path} - {write_err}", exc_info=True)
                return False
        else:
            logging.info(f"未计算新的风速特征 (可能缺少必要的列)，无需写回文件: {csv_path}")
            return True # 没有添加新特征也视为"成功"完成检查
        
    except pd.errors.EmptyDataError:
        logging.warning(f"尝试读取的 CSV 文件为空或格式错误: {csv_path}")
        return False # 读取失败
    except Exception as e:
        logging.error(f"处理简单格式 CSV 文件 {csv_path} 以添加风速特征时发生意外错误: {e}", exc_info=True)
        return False

# --- 用于列对齐的辅助函数 ---
def align_columns_to_template(df, template_path):
    """
    将 DataFrame 的列与模板 CSV 文件对齐。

    确保输出的 DataFrame 具有与模板文件完全相同的列，顺序也一致。
    缺失的列会被添加并填充 NaN 值。多余的列会被移除。

    Args:
        df (pd.DataFrame): 需要对齐的 DataFrame。
        template_path (str): 模板 CSV 文件的路径。

    Returns:
        pd.DataFrame or None: 对齐后的 DataFrame；如果对齐失败
                             （例如，模板未找到或无法读取），则返回 None。
    """
    if not os.path.exists(template_path):
        logging.error(f"模板文件未找到: {template_path}。无法对齐列。")
        return None

    try:
        # 只读取模板文件的标题行以获取列名和顺序
        template_cols = pd.read_csv(template_path, nrows=0).columns.tolist()
        logging.info(f"从 {template_path} 加载模板列: {len(template_cols)} 列。")
        logging.debug(f"模板列顺序: {template_cols}")

        if not template_cols:
            logging.error(f"模板文件 {template_path} 为空或没有标题行。无法对齐。")
            return None

        data_cols = df.columns.tolist()
        logging.info(f"原始数据列: {len(data_cols)} 列。")
        logging.debug(f"原始数据列: {data_cols}")

        template_cols_set = set(template_cols)
        data_cols_set = set(data_cols)

        # 识别缺失的列 (在模板中存在，但在数据中不存在)
        missing_cols = list(template_cols_set - data_cols_set)
        if missing_cols:
            logging.warning(f"数据中缺失的列 (将添加并填充 NaN): {missing_cols}")
            for col in missing_cols:
                df[col] = np.nan # 添加缺失列，填充 NaN

        # 识别多余的列 (在数据中存在，但在模板中不存在)
        extra_cols = list(data_cols_set - template_cols_set)
        if extra_cols:
            logging.warning(f"在数据中发现多余的列 (将被移除): {extra_cols}")
            df = df.drop(columns=extra_cols)

        # 重新排列列以精确匹配模板
        # 这也隐式地只选择了模板中存在的列
        logging.info("正在重新排列列以匹配模板。")
        aligned_df = df[template_cols] # 按模板的顺序选择列

        # 最后检查 (可选，但推荐)
        if list(aligned_df.columns) == template_cols:
            logging.info("列对齐成功。名称、顺序和数量与模板匹配。")
            return aligned_df
        else:
            # 这种情况理论上不应发生，如果前面的逻辑正确的话
            logging.error("在操作后列对齐意外失败。")
            logging.error(f"期望的列: {template_cols}")
            logging.error(f"结果列: {list(aligned_df.columns)}")
            return None

    except pd.errors.EmptyDataError:
        logging.error(f"模板文件 {template_path} 为空。无法对齐。")
        return None
    except Exception as e:
        logging.error(f"使用模板 {template_path} 进行列对齐时出错: {e}", exc_info=True)
        return None

if __name__ == "__main__":
    main()