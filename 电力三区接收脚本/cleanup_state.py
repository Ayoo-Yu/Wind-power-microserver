#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
状态文件清理脚本 - 从downloaded_state.txt中清理旧记录

这个脚本会清理状态文件中那些不再需要的记录:
1. 基于远程批次目录的存在性检查: 如果远程服务器上批次目录已被删除，则移除对应记录
2. 基于时间阈值: 可选地，移除超过一定时间阈值的记录

使用方法:
python cleanup_state.py [--keep-days 天数] [--dry-run]

参数:
--keep-days 天数: 只保留最近N天的记录(可选，基于批次目录名称中的日期)
--dry-run: 测试模式，只显示会删除哪些记录，不实际修改文件
"""

import os
import sys
import re
import logging
import argparse
import subprocess
import threading  # 用于跨平台超时实现
import io  # 用于Python 2兼容的文件编码处理
from datetime import datetime, timedelta

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

# 导入与主脚本相同的配置
try:
    from fetch_data_from_c import (
        REMOTE_HOST, REMOTE_PORT, REMOTE_USER, REMOTE_PASSWORD,
        REMOTE_BASE_DIR, STATE_FILE, BATCH_DIR_PATTERN,
        BATCH_FILE, SSH_KEY_PATH  # 添加了SSH_KEY_PATH
    )
except ImportError:
    # 如果无法导入，使用默认值
    REMOTE_HOST = "49.232.246.73"
    REMOTE_PORT = 22
    REMOTE_USER = "root"
    REMOTE_PASSWORD = "yzz0216yhAAAA"
    SSH_KEY_PATH = "/home/ecs-user/.ssh/id_rsa"  # 添加默认SSH密钥路径
    REMOTE_BASE_DIR = "/ECMWF/processed_csv"
    STATE_FILE = "/opt/scripts/ecmwf_fetcher/downloaded_state.txt"
    BATCH_DIR_PATTERN = re.compile(r"^(\d{4})_(\d{8})$")  # 捕获年份和MMDDHHMM
    BATCH_FILE = "/tmp/sftp_batch.txt"  # SFTP批处理文件

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def parse_batch_date(path_str):
    """从状态文件记录中提取批次日期"""
    # 状态文件中的记录格式如: /ECMWF/processed_csv/2025_04131800/YCSJ_YN.ZhuYXDC_YC_MT_20250415_000000.dat
    match = re.search(r'/(\d{4}_\d{8})/', path_str)
    if match:
        batch_dir = match.group(1)
        year_match = BATCH_DIR_PATTERN.match(batch_dir)
        if year_match:
            year = int(year_match.group(1))
            # 从MMDDHHMM格式提取月和日
            mmdd = year_match.group(2)[:4]
            month = int(mmdd[:2])
            day = int(mmdd[2:4])
            try:
                return datetime(year, month, day)
            except ValueError:
                # 无效日期
                return None
    return None

def execute_sftp_cmd(commands):
    """执行SFTP命令并返回结果 (使用SSH密钥认证)"""
    try:
        # 创建临时批处理文件
        with open(BATCH_FILE, 'w') as f:
            for cmd in commands:
                f.write("{}\n".format(cmd))
        
        # 构建sftp命令 (使用SSH密钥)
        sftp_cmd = [
            "sftp", 
            "-o", "StrictHostKeyChecking=no",  # 禁用主机密钥检查
            "-o", "UserKnownHostsFile=/dev/null",  # 不使用known_hosts文件
            "-o", "IdentitiesOnly=yes",  # 只使用指定的密钥
            "-i", SSH_KEY_PATH,  # 指定SSH私钥
            "-b", BATCH_FILE,
            "-P", str(REMOTE_PORT),
            "{}@{}".format(REMOTE_USER, REMOTE_HOST)
        ]
        
        # 执行命令
        logging.info("执行SFTP命令: {}".format(' '.join(sftp_cmd)))
        process = subprocess.Popen(
            sftp_cmd, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True  # 等同于text=True
        )
        
        # 跨平台超时实现
        timeout_occurred = [False]
        
        def kill_process():
            timeout_occurred[0] = True
            try:
                process.kill()
            except:
                pass
        
        timer = threading.Timer(60, kill_process)  # 设置超时时间
        timer.start()
        
        try:
            stdout, stderr = process.communicate()
            timer.cancel()
        except Exception as e:
            timer.cancel()
            if timeout_occurred[0]:
                logging.error("SFTP命令执行超时")
                return False, "Timeout"
            else:
                raise
        
        if timeout_occurred[0]:
            logging.error("SFTP命令执行超时")
            return False, "Timeout"
        
        if process.returncode != 0:
            logging.error("SFTP命令失败，返回码: {}".format(process.returncode))
            logging.error("错误信息: {}".format(stderr))
            return False, stdout
        
        return True, stdout
            
    except Exception as e:
        logging.error("执行SFTP命令时出错: {}".format(e), exc_info=True)
        return False, str(e)
    finally:
        # 清理批处理文件
        if os.path.exists(BATCH_FILE):
            try:
                os.unlink(BATCH_FILE)
            except:
                pass

def list_remote_dir(remote_path):
    """列出远程目录内容"""
    commands = [
        "ls -l {}".format(remote_path),
        "quit"
    ]
    
    success, output = execute_sftp_cmd(commands)
    if not success:
        return []
    
    # 解析输出
    items = []
    for line in output.split('\n'):
        if line and not line.startswith("sftp>") and not "Not connected" in line:
            parts = line.split()
            if len(parts) >= 9:
                # 解析类似 "drwxr-xr-x  1 root  wheel  999 Jan  1 00:00 dirname" 的输出
                is_dir = line.startswith('d')
                name = ' '.join(parts[8:])
                items.append((name, is_dir))
    
    return items

def get_remote_batch_dirs():
    """获取远程服务器上所有的批次目录名"""
    try:
        items = list_remote_dir(REMOTE_BASE_DIR)
        return set(name for name, is_dir in items 
                   if is_dir and BATCH_DIR_PATTERN.match(name))
    except Exception as e:
        logging.error("获取远程批次目录失败: {}".format(e))
        return set()

def load_state_file():
    """加载状态文件内容"""
    state_records = set()
    if not os.path.exists(STATE_FILE):
        logging.warning("状态文件不存在: {}".format(STATE_FILE))
        return state_records
    
    try:
        with io.open(STATE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    state_records.add(line)
        logging.info("已加载 {} 条记录".format(len(state_records)))
        return state_records
    except Exception as e:
        logging.error("加载状态文件失败: {}".format(e))
        return set()

def save_state_file(records, dry_run=False):
    """保存过滤后的记录到状态文件"""
    if dry_run:
        logging.info("[测试模式] 将保存 {} 条记录到 {}".format(len(records), STATE_FILE))
        return
    
    try:
        # 备份原文件
        backup_file = "{}.bak".format(STATE_FILE)
        if os.path.exists(STATE_FILE):
            os.rename(STATE_FILE, backup_file)
            logging.info("已备份原状态文件到 {}".format(backup_file))
        
        # 写入新文件
        makedirs_exist_ok(os.path.dirname(STATE_FILE))
        with io.open(STATE_FILE, 'w', encoding='utf-8') as f:
            for record in sorted(records):
                # 确保字符串是unicode类型（Python 2兼容）
                unicode_record = ensure_unicode(record)
                f.write(ensure_unicode("{}\n".format(unicode_record)))
        logging.info("已保存 {} 条记录到 {}".format(len(records), STATE_FILE))
    except Exception as e:
        logging.error("保存状态文件失败: {}".format(e))

def cleanup_state(keep_days=None, dry_run=False):
    """清理状态文件中的过期记录"""
    # 加载状态文件
    all_records = load_state_file()
    if not all_records:
        return
    
    # 获取远程批次目录
    logging.info("连接到远程服务器 {}:{}".format(REMOTE_HOST, REMOTE_PORT))
    remote_batch_dirs = get_remote_batch_dirs()
    logging.info("远程服务器有 {} 个批次目录".format(len(remote_batch_dirs)))
    
    # 过滤记录
    filtered_records = set()
    removed_records = set()
    
    # 定义截止日期(如果有)
    cutoff_date = None
    if keep_days is not None and keep_days > 0:
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        logging.info("保留 {} 天内的记录 (截止日期: {})".format(keep_days, cutoff_date.strftime('%Y-%m-%d')))
    
    for record in all_records:
        # 提取记录中的批次目录名
        batch_dir_match = re.search(r'/([^/]+)/', record.replace(REMOTE_BASE_DIR, ''))
        
        # 检查批次目录是否还存在于远程服务器
        if batch_dir_match and batch_dir_match.group(1) not in remote_batch_dirs and remote_batch_dirs:
            removed_records.add(record)
            continue
        
        # 检查日期阈值
        if cutoff_date:
            record_date = parse_batch_date(record)
            if record_date and record_date < cutoff_date:
                removed_records.add(record)
                continue
        
        # 保留这条记录
        filtered_records.add(record)
    
    # 输出统计信息
    removed_count = len(all_records) - len(filtered_records)
    if removed_count > 0:
        logging.info("将从状态文件中移除 {} 条记录 ({:.1f}%)".format(removed_count, removed_count / len(all_records) * 100))
        
        # 显示一些被移除的记录示例
        if removed_records:
            sample_size = min(5, len(removed_records))
            logging.info("被移除记录示例 (前 {} 条):".format(sample_size))
            for i, record in enumerate(list(removed_records)[:sample_size]):
                logging.info("  {}. {}".format(i+1, record))
    else:
        logging.info("没有记录需要移除")
    
    # 保存过滤后的记录
    if filtered_records != all_records:
        save_state_file(filtered_records, dry_run)
    else:
        logging.info("状态文件无需更新")

def main():
    parser = argparse.ArgumentParser(description="清理ECMWF数据获取脚本的状态文件")
    parser.add_argument("--keep-days", type=int, 
                      help="保留最近N天的记录 (基于批次目录日期)")
    parser.add_argument("--dry-run", action="store_true", 
                      help="测试模式，不实际修改文件")
    
    args = parser.parse_args()
    
    if args.dry_run:
        logging.info("运行在测试模式，不会修改实际文件")
    
    cleanup_state(args.keep_days, args.dry_run)

if __name__ == "__main__":
    main() 