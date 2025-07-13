#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KingBase 数据库试用期自动续期脚本 - Windows版
采用最可靠的"全局重建"策略，为无人值守的自动化任务设计。

设计原则：
- 极简性：只使用 docker-compose down 和 up
- 可预测性：所有容器都是全新的，状态完全一致
- 可靠性：避免复杂的服务依赖检查逻辑
- 原子性：将整个环境视为一个原子单元
"""

import subprocess
import datetime
import os
import sys
import time

# --- 配置 ---
# Docker Compose 文件名（相对于脚本所在目录的上两级目录）
COMPOSE_FILE = "frontend-backend-compose.yaml"

# 日志文件路径（相对于脚本目录）
LOG_FILE = "logs/kingbase_renewal.log"

# 服务启动等待时间（秒）
STARTUP_WAIT_TIME = 60

def log(message):
    """记录日志信息到控制台和文件"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    
    try:
        # 计算日志文件的绝对路径（基于脚本所在目录）
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_file_path = os.path.join(script_dir, LOG_FILE)
        
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file_path)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        with open(log_file_path, "a", encoding='utf-8') as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"[{timestamp}] CRITICAL: 无法写入日志文件 {log_file_path}: {e}")

def run_docker_command(command, description):
    """执行Docker命令并记录结果 - Windows兼容版本"""
    log(f"执行: {description}...")
    try:
        result = subprocess.run(command, capture_output=True, text=True, 
                              timeout=300, encoding='utf-8', errors='ignore')
        if result.returncode != 0:
            log(f"❌ {description} 失败:")
            log(f"--- STDERR ---")
            log(f"{result.stderr.strip()}")
            log(f"--------------")
            return False
        log(f"✅ {description} 成功")
        return True
    except subprocess.TimeoutExpired:
        log(f"⏰ {description} 超时（超过300秒）")
        return False
    except Exception as e:
        log(f"❌ {description} 发生未知错误: {e}")
        return False

def check_docker_environment():
    """检查Docker环境是否可用"""
    log("检查Docker环境...")
    
    # 检查 docker-compose 命令
    try:
        result = subprocess.run(['docker-compose', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            log("❌ docker-compose 命令不可用")
            return False
        log(f"✅ Docker Compose 版本: {result.stdout.strip()}")
    except Exception as e:
        log(f"❌ 无法执行 docker-compose 命令: {e}")
        return False
    
    return True

def main():
    """主函数，执行全局重建策略"""
    log("=" * 60)
    log("KingBase 试用期自动续期任务启动 (Windows版)")
    log("策略: 全局重建 (down & up) - 最可靠方案")
    log("设计原则: 极简、可预测、可靠、原子性")
    log("=" * 60)

    # 切换到项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.join(script_dir, '..', '..')
    project_dir = os.path.abspath(project_dir)
    
    compose_file_path = os.path.join(project_dir, COMPOSE_FILE)
    
    # 检查 compose 文件是否存在
    if not os.path.isfile(compose_file_path):
        log(f"FATAL: Docker Compose 文件未找到: {compose_file_path}")
        log(f"请确认文件路径正确，或修改脚本中的 COMPOSE_FILE 配置")
        sys.exit(1)

    # 切换工作目录
    os.chdir(project_dir)
    log(f"工作目录: {project_dir}")
    log(f"Compose文件: {COMPOSE_FILE}")

    # 检查Docker环境
    if not check_docker_environment():
        log("FATAL: Docker环境检查失败")
        sys.exit(1)

    # ===== 核心流程：全局重建策略 =====
    
    # 步骤 1: 全局 down - 彻底清理所有容器
    log("步骤 1/3: 执行全局 down，移除所有容器和网络...")
    if not run_docker_command([
        'docker-compose', '-f', COMPOSE_FILE, 'down'
    ], "停止并移除所有服务"):
        log("❌ 续期流程因 'down' 失败而中止")
        sys.exit(1)

    # 等待确保完全清理
    log("等待 5 秒，确保所有资源完全清理...")
    time.sleep(5)

    # 步骤 2: 全局 up - 重新创建所有容器
    log("步骤 2/3: 执行全局 up，创建并启动所有服务...")
    if not run_docker_command([
        'docker-compose', '-f', COMPOSE_FILE, 'up', '-d'
    ], "创建并启动所有服务"):
        log("❌ 续期流程因 'up' 失败而中止")
        sys.exit(1)

    # 步骤 3: 等待并验证
    log(f"步骤 3/3: 等待 {STARTUP_WAIT_TIME} 秒，让所有服务完成启动和初始化...")
    time.sleep(STARTUP_WAIT_TIME)

    # 最终状态检查
    log("检查最终服务状态:")
    run_docker_command([
        'docker-compose', '-f', COMPOSE_FILE, 'ps'
    ], "列出所有服务状态")

    log("🎉 KingBase试用期续期流程成功完成！")
    log("所有容器均为全新状态，确保最大稳定性")
    log("=" * 60)
    log("续期任务结束")
    log("=" * 60)
    
    sys.exit(0)

if __name__ == "__main__":
    main() 