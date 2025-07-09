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
import io  # 用于Python 2兼容的文件编码处理
from datetime import datetime
import threading

# Python 2兼容性函数
def makedirs_exist_ok(path):
    """创建目录，如果目录已存在则忽略错误（Python 2兼容）"""
    try:
        os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            raise

def ensure_unicode(s):
    """确保字符串是unicode类型（Python 2兼容）"""
    if sys.version_info[0] == 2:
        if isinstance(s, str):
            return s.decode('utf-8')
        return s
    else:
        return s

# --- 配置项 ---
# --- 服务器 C (源) ---
REMOTE_HOST = "49.232.246.73"
REMOTE_PORT = 22
REMOTE_USER = "root"
REMOTE_PASSWORD = "yzz0216yhAAAA" # 密码
SSH_KEY_PATH = "/home/drhn/.ssh/id_rsa"  # SSH私钥路径 - 替换为你的实际密钥路径

# --- 服务器 C 上的文件路径 ---
REMOTE_BASE_DIR = "/ECMWF/processed_csv"

# --- 服务器 B (本机) 上的文件路径 ---
LOCAL_DOWNLOAD_DIR = "/data/from_server_c"
LOCAL_DATA_DIR = "/data/from_server_c/data"  # 修改：改为数据目录，不再是临时目录
STATE_FILE = "/opt/scripts/ecmwf_fetcher/downloaded_state.txt"
LOG_FILE = "/var/log/ecmwf_fetcher.log"
BATCH_FILE = os.path.join(tempfile.gettempdir(), "sftp_batch.txt") # SFTP批处理文件放临时目录

# --- 文件匹配规则 ---
BATCH_DIR_PATTERN = re.compile(r"^(\d{4})_(\d{8})$")
# 预测文件模式：使用 C? 使 'C' 成为可选，匹配 _DQYC_ 或 _CDQYC_
PREDICTION_FILE_PATTERN = re.compile(r"^YCSJ_.*_C?DQYC_.*\.dat$")
# 气象文件模式（保持不变）
WEATHER_FILE_PATTERN = re.compile(r"^YCSJ_.*_QXYC_.*\.dat$")

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
        makedirs_exist_ok(os.path.dirname(LOCK_FILE))
        lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lock_fd, str(os.getpid()).encode())
        os.close(lock_fd)
        logging.info("成功获取锁文件: {}".format(LOCK_FILE))
        return True
    except OSError as e:
        # Python 2兼容: 检查错误代码而不是异常类型
        if e.errno == 17:  # EEXIST - 文件已存在
            logging.warning("锁文件 {} 已存在，可能已有实例在运行。".format(LOCK_FILE))
            # 尝试读取PID
            try:
                with open(LOCK_FILE, 'r') as f:
                    pid_in_lock = f.read().strip()
                    logging.warning("锁文件包含PID: {}".format(pid_in_lock))
                    # 可以尝试检查该PID是否存在，但简单起见，这里直接退出
            except Exception as ex:
                logging.warning("读取锁文件PID失败: {}".format(ex))
            return False
        else:
            logging.error("获取锁文件时发生错误: {}".format(e), exc_info=True)
            return False

def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.unlink(LOCK_FILE)
            logging.info("已释放锁文件: {}".format(LOCK_FILE))
    except OSError as e:
        logging.error("释放锁文件失败: {}".format(e))

# --- 状态管理 ---
def load_downloaded_state():
    state = set()
    if os.path.exists(STATE_FILE):
        try:
            with io.open(STATE_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line:
                        state.add(stripped_line)
            logging.info("从 {} 加载了 {} 条下载记录。".format(STATE_FILE, len(state)))
        except Exception as e:
            logging.error("加载状态文件 {} 失败: {}".format(STATE_FILE, e), exc_info=True)
    else:
        logging.info("状态文件 {} 不存在，将创建新的状态。".format(STATE_FILE))
    return state

def save_downloaded_state(state):
    try:
        makedirs_exist_ok(os.path.dirname(STATE_FILE))
        # 使用临时文件确保原子写入
        temp_state_file = STATE_FILE + ".tmp"
        with io.open(temp_state_file, 'w', encoding='utf-8') as f:
            for remote_path in sorted(list(state)):
                # 确保字符串是unicode类型（Python 2兼容）
                unicode_path = ensure_unicode(remote_path)
                # 移除可能存在的BOM标记
                if unicode_path.startswith('\ufeff'):
                    unicode_path = unicode_path[1:]
                f.write(u"{}\n".format(unicode_path))
        # Python 2兼容: 使用os.rename而不是os.replace
        if os.path.exists(STATE_FILE):
            os.unlink(STATE_FILE)
        os.rename(temp_state_file, STATE_FILE)
        logging.info("成功将 {} 条下载记录保存到 {}。".format(len(state), STATE_FILE))
    except Exception as e:
        logging.error("保存状态文件 {} 失败: {}".format(STATE_FILE, e), exc_info=True)

# --- SFTP命令执行 (使用SSH密钥) ---
def execute_sftp_cmd(commands):
    """执行SFTP命令并返回结果 (使用SSH密钥认证)"""
    batch_file_path = None # 用于确保清理

    try:
        # 1. 创建临时批处理文件
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".txt", prefix="sftp_batch_") as f:
            batch_file_path = f.name
            for cmd in commands:
                f.write("{}\n".format(cmd))
        logging.debug("已创建SFTP批处理文件: {}".format(batch_file_path))

        # 2. 构建SFTP命令 (使用SSH密钥)
        sftp_cmd = [
            "sftp", 
            "-o", "StrictHostKeyChecking=no",
            "-o", "IdentitiesOnly=yes",  # 只使用指定的密钥
            "-i", SSH_KEY_PATH,  # 指定SSH私钥
            "-b", batch_file_path,
            "-P", str(REMOTE_PORT),
            "{}@{}".format(REMOTE_USER, REMOTE_HOST)
        ]
        
        logging.info("准备使用SSH密钥执行SFTP命令")
        
        # 3. 执行命令 (Python 2兼容，跨平台超时)
        process = subprocess.Popen(
            sftp_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # 跨平台超时实现
        timeout_occurred = [False]
        
        def kill_process():
            timeout_occurred[0] = True
            try:
                process.kill()
            except:
                pass
        
        timer = threading.Timer(SFTP_TIMEOUT, kill_process)
        timer.start()
        
        try:
            stdout, stderr = process.communicate()
            timer.cancel()
        except Exception as e:
            timer.cancel()
            if timeout_occurred[0]:
                logging.error("SFTP命令执行超时 (超过 {} 秒)。".format(SFTP_TIMEOUT), exc_info=True)
                return False, "Timeout"
            else:
                raise
        
        if timeout_occurred[0]:
            logging.error("SFTP命令执行超时 (超过 {} 秒)。".format(SFTP_TIMEOUT))
            return False, "Timeout"
        
        # 4. 处理结果
        if process.returncode != 0:
            logging.error("SFTP命令执行失败，返回码: {}".format(process.returncode))
            logging.error("SFTP STDERR:\n{}".format(stderr.strip()))
            logging.error("SFTP STDOUT:\n{}".format(stdout.strip()))
            return False, stdout
        
        logging.info("SFTP 命令执行成功")
        return True, stdout

    except Exception as e:
        logging.error("执行SFTP命令时发生未知错误: {}".format(e), exc_info=True)
        return False, str(e)
    finally:
        # 只清理SFTP批处理文件，不清理下载的数据文件
        if batch_file_path and os.path.exists(batch_file_path):
            try:
                os.unlink(batch_file_path)
                logging.debug("已删除SFTP批处理文件: {}".format(batch_file_path))
            except OSError as e:
                logging.warning("删除SFTP批处理文件失败: {}".format(e))


# --- 远程目录列表 (使用 ls -1 进行简化解析) ---
def list_remote_dir(remote_path):
    """列出远程目录内容 (使用 ls -1)"""
    # 使用 ls -1 获取简单列表，每行一个条目
    commands = [
        "ls -1 \"{}\"".format(remote_path), # 给路径加上引号以防包含空格
        "quit"
    ]

    success, output = execute_sftp_cmd(commands)
    if not success:
        logging.warning("无法列出远程目录: {}".format(remote_path))
        return None # 返回 None 表示失败

    # 解析输出
    items = []
    # 过滤掉 sftp 提示符、连接信息和空行
    lines = [line.strip() for line in output.splitlines() if line.strip() and not line.startswith("sftp>") and "Connecting to" not in line and "Connected to" not in line and "Changing to" not in line and "Fetching" not in line and "Retrieving" not in line and "remote host" not in line and "Cannot stat" not in line] # 添加 Cannot stat 过滤

    if not lines:
        # 区分是真 K 空目录还是 ls 命令本身有问题
        if "No such file or directory" in output: # 检查 stderr 或 stdout 是否包含错误信息
             logging.error("远程路径不存在或无法访问: {}".format(remote_path))
             return None # 路径问题，返回 None
        else:
             logging.info("远程目录 {} 为空或未找到任何项目。".format(remote_path))
             return [] # 明确是空列表

    logging.debug("为 {} 解析出的远程项目: {}".format(remote_path, lines))

    # ls -1 不区分目录和文件，调用者需要根据模式判断
    # 返回 (名称, is_dir_flag) 元组列表，is_dir_flag 暂时为 None
    return [(name, None) for name in lines]


# --- 文件下载 ---
def download_file(remote_path, local_path):
    """下载指定文件"""
    local_dir = os.path.dirname(local_path)
    try:
        # 确保本地目标目录存在
        makedirs_exist_ok(local_dir)
    except OSError as e:
        logging.error("创建本地目录失败 {}: {}".format(local_dir, e))
        return False

    # 给路径加上引号，处理可能存在的空格
    commands = [
        "get \"{}\" \"{}\"".format(remote_path, local_path),
        "quit"
    ]

    success, output = execute_sftp_cmd(commands)
    if not success:
         # 记录失败时的输出以供调试
         logging.error("SFTP 'get' 命令失败。远程: '{}', 本地: '{}'. SFTP输出:\n{}".format(remote_path, local_path, output))
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
        logging.info("正在查找远程目录 {} 下最新的批次目录...".format(REMOTE_BASE_DIR))

        items_result = list_remote_dir(REMOTE_BASE_DIR)

        if items_result is None: # list_remote_dir 失败
             logging.error("无法获取远程目录 {} 的列表，任务中止。".format(REMOTE_BASE_DIR))
             return False # 表示任务失败
        if not items_result: # 目录为空
             logging.info("远程目录 {} 为空或未找到任何项目。".format(REMOTE_BASE_DIR))
             return True # 任务正常结束，只是没找到东西

        batch_dirs = []
        potential_items = [item[0] for item in items_result] # 获取所有名称
        for name in potential_items:
            # 提取目录名部分（如果是完整路径)
            dir_name = os.path.basename(name) if '/' in name else name
            # 如果是完整路径但没有目录名部分，则使用整个名称
            if not dir_name and '/' in name:
                dir_name = name.rstrip('/')
                dir_name = os.path.basename(dir_name)
                
            # 或者可以直接从已知格式中提取年份和日期部分
            batch_dir_match = re.search(r'(\d{4})_(\d{8})', name)
            if batch_dir_match:
                year = batch_dir_match.group(1)
                date = batch_dir_match.group(2)
                # 构造批次目录信息元组 (完整目录名, 年份, 日期)
                # 如果name是完整路径，直接使用
                batch_dirs.append((name, year, date))
                
        if not batch_dirs:
            logging.warning("在 {} 未找到匹配日期格式的批次目录。找到的项目: {}".format(REMOTE_BASE_DIR, potential_items))
            return True # 任务正常结束

        # 按年份和日期排序，找到最新的
        batch_dirs.sort(key=lambda x: (x[1], x[2]), reverse=True)
        latest_batch_dirname = batch_dirs[0][0]
        # 构造路径，如果latest_batch_dirname已经是完整路径，则直接使用
        if latest_batch_dirname.startswith('/'):
            latest_batch_path = latest_batch_dirname
        else:
            latest_batch_path = "{}/{}".format(REMOTE_BASE_DIR, latest_batch_dirname)
        logging.info("找到最新的批次目录: {}".format(latest_batch_path))

        # 所有文件直接保存到数据目录
        logging.info("所有文件将保存到数据目录: {}".format(LOCAL_DATA_DIR))

        # --- 2. 查找批次目录中的目标文件 ---
        logging.info("正在查找目录 {} 中的目标文件...".format(latest_batch_path))

        files_in_batch_result = list_remote_dir(latest_batch_path)

        if files_in_batch_result is None:
            logging.error("无法获取最新批次目录 {} 的列表，任务中止。".format(latest_batch_path))
            return False
        if not files_in_batch_result:
            logging.info("最新的批次目录 {} 为空。".format(latest_batch_path))
            return True # 正常结束

        files_in_batch = [item[0] for item in files_in_batch_result] # 获取文件名列表
        files_to_download = {}  # key: file_type, value: (remote_path, local_path)

        # --- 查找预测文件 ---
        found_pred_candidate = None
        for name in files_in_batch:
            # 提取文件名部分（如果是完整路径）
            file_name = os.path.basename(name) if '/' in name else name
            
            if PREDICTION_FILE_PATTERN.match(file_name):
                remote_path = "{}/{}".format(latest_batch_path, file_name) if '/' in name else "{}/{}".format(latest_batch_path, name)
                # 使用完整路径
                if name.startswith('/'):
                    remote_path = name
                    
                if remote_path not in downloaded_state:
                    local_final_path = os.path.join(LOCAL_DATA_DIR, file_name)
                    files_to_download['prediction'] = (remote_path, local_final_path)
                    logging.info("发现新的预测文件: {}".format(remote_path))
                    found_pred_candidate = remote_path
                    break # 找到第一个新的就停止
                else:
                    logging.info("预测文件 {} 已下载过，标记为找到但跳过下载。".format(remote_path))
                    found_pred_candidate = remote_path
                    break # 找到第一个（无论新旧）就停止

        if not found_pred_candidate:
            logging.warning("在 {} 未找到名称匹配 {} 的预测文件。找到的文件: {}".format(latest_batch_path, PREDICTION_FILE_PATTERN.pattern, files_in_batch))

        # --- 查找气象文件 ---
        found_weather_candidate = None
        for name in files_in_batch:
            # 提取文件名部分（如果是完整路径）
            file_name = os.path.basename(name) if '/' in name else name
            
            if WEATHER_FILE_PATTERN.match(file_name):
                remote_path = "{}/{}".format(latest_batch_path, file_name) if '/' in name else "{}/{}".format(latest_batch_path, name)
                # 使用完整路径
                if name.startswith('/'):
                    remote_path = name
                    
                if remote_path not in downloaded_state:
                    local_final_path = os.path.join(LOCAL_DATA_DIR, file_name)
                    files_to_download['weather'] = (remote_path, local_final_path)
                    logging.info("发现新的气象文件: {}".format(remote_path))
                    found_weather_candidate = remote_path
                    break
                else:
                    logging.info("气象文件 {} 已下载过，标记为找到但跳过下载。".format(remote_path))
                    found_weather_candidate = remote_path
                    break

        if not found_weather_candidate:
            logging.warning("在 {} 未找到名称匹配 {} 的气象文件。找到的文件: {}".format(latest_batch_path, WEATHER_FILE_PATTERN.pattern, files_in_batch))

        if not files_to_download:
            logging.info("没有找到需要下载的新文件。")
            return True # 正常结束

        # --- 3. 下载新文件 ---
        try:
            makedirs_exist_ok(LOCAL_DOWNLOAD_DIR)
            makedirs_exist_ok(LOCAL_DATA_DIR)
        except OSError as e:
            logging.error("创建本地下载目录失败: {}".format(e), exc_info=True)
            return False # 无法创建目录，任务失败

        processed_count = len(files_to_download)

        for file_type, (remote_path, local_final_path) in files_to_download.items():
            logging.info("开始下载 [{}] 文件: \"{}\" -> \"{}\"".format(file_type, remote_path, local_final_path))

            download_successful = False
            try:
                # 先清理可能存在的旧文件
                if os.path.exists(local_final_path):
                    os.unlink(local_final_path)

                download_successful = download_file(remote_path, local_final_path)
            except Exception as download_err:
                logging.error("下载文件 {} 时发生异常: {}".format(remote_path, download_err), exc_info=True)
                # 再次尝试清理文件
                if os.path.exists(local_final_path):
                    try: os.unlink(local_final_path)
                    except OSError: pass
                continue # 跳过处理此文件

            if download_successful:
                logging.info("SFTP 'get' 命令成功完成: \"{}\"".format(remote_path))

                # 验证文件是否存在且非空
                if not os.path.exists(local_final_path):
                     logging.error("下载声称成功，但本地文件不存在: \"{}\"。SFTP 可能内部出错或未实际传输。跳过此文件。".format(local_final_path))
                     continue
                try:
                    if os.path.getsize(local_final_path) == 0:
                        logging.warning("下载的文件为空: \"{}\"。可能远程文件为空或下载中断。将删除文件。".format(local_final_path))
                        os.unlink(local_final_path) # 删除空文件
                        continue # 跳过处理此文件
                except OSError as e:
                    logging.error("检查文件大小失败: \"{}\", 错误: {}. 跳过此文件.".format(local_final_path, e))
                    continue

                # 文件已经在最终位置，直接记录状态
                newly_downloaded.add(remote_path)
                downloaded_count += 1
                logging.info("文件下载完成: \"{}\"".format(local_final_path))
            else:
                logging.error("下载文件失败 (download_file 返回 False): \"{}\"".format(remote_path))
                # 下载失败，清理可能残留的文件
                if os.path.exists(local_final_path):
                    try: os.unlink(local_final_path)
                    except OSError: pass

        # --- 4. 更新状态文件 ---
        if newly_downloaded:
            updated_state = downloaded_state.union(newly_downloaded)
            save_downloaded_state(updated_state)

        logging.info("本次任务计划下载 {} 个文件，成功下载并处理了 {} 个文件。".format(processed_count, downloaded_count))
        # 只要没有发生让任务无法继续的错误，就返回 True
        return True

    except Exception as e:
        logging.error("同步任务执行过程中发生未捕获的严重错误: {}".format(e), exc_info=True)
        return False # 任务异常失败
    finally:
        logging.info("======== 同步任务结束 ========")


# --- 主程序入口 ---
def main():
    start_time = time.time()
    logging.info("脚本启动 (PID: {})。".format(os.getpid()))

    # 检查 sftp 命令是否存在
    try:
        subprocess.call(["which", "sftp"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info("系统 'sftp' 命令已找到。")
    except (OSError, subprocess.CalledProcessError):
         logging.critical("错误: 系统 'sftp' 命令未找到。请确保 OpenSSH 客户端已安装。脚本退出。")
         sys.exit(1)

    # 检查并创建必要的本地目录
    required_dirs = [
        os.path.dirname(LOG_FILE),
        LOCAL_DOWNLOAD_DIR,
        LOCAL_DATA_DIR,  # 修改：使用LOCAL_DATA_DIR替代LOCAL_TEMP_DIR
        os.path.dirname(STATE_FILE),
        os.path.dirname(LOCK_FILE),
        tempfile.gettempdir() # 确保临时目录存在
    ]
    try:
        for d in required_dirs:
            # 检查路径非空且是目录
            if d and isinstance(d, str):
               makedirs_exist_ok(d)
    except OSError as e:
        logging.critical("创建本地目录失败: {}。请检查权限。脚本退出。".format(e))
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
        logging.critical("执行 sync_latest_files 时发生顶层错误: {}".format(e), exc_info=True)
        exit_code = 1 # 确保顶层异常也标记为失败
    finally:
        # 确保释放锁
        release_lock()
        end_time = time.time()
        logging.info("脚本执行完毕，耗时 {:.2f} 秒。退出码: {}".format(end_time - start_time, exit_code))
        # 只清理SFTP批处理临时文件，不清理下载的数据文件
        # BATCH_FILE已经在execute_sftp_cmd函数中清理了，这里不需要重复清理
        logging.info("程序正常结束，数据文件保留在: {}".format(LOCAL_DATA_DIR))
        sys.exit(exit_code)

if __name__ == "__main__":
    main() 