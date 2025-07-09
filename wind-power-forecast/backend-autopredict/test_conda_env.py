#!/usr/bin/env python3
"""
测试Conda环境配置
这个脚本用于验证环境路径和PM2配置。
"""
import os
import sys
import subprocess
import shutil

def check_paths():
    """检查当前环境的重要路径"""
    print("===== 环境路径检查 =====")
    # 检查当前工作目录
    print(f"当前工作目录: {os.getcwd()}")
    
    # 检查Python解释器
    print(f"Python解释器: {sys.executable}")
    print(f"Python版本: {sys.version}")
    
    # 检查Conda环境路径
    conda_prefix = os.environ.get('CONDA_PREFIX')
    if conda_prefix:
        print(f"✅ 当前Conda环境: {conda_prefix}")
    else:
        print("❌ 未找到当前Conda环境变量 (CONDA_PREFIX)")
    
    # 检查/opt/conda/envs/wind-power-env是否存在
    conda_env_path = "/opt/conda/envs/wind-power-env"
    if os.path.exists(conda_env_path):
        print(f"✅ 目标Conda环境路径存在: {conda_env_path}")
        # 检查Python解释器
        python_path = os.path.join(conda_env_path, "bin", "python")
        if os.path.exists(python_path):
            print(f"✅ 目标Python解释器存在: {python_path}")
        else:
            print(f"❌ 目标Python解释器不存在: {python_path}")
    else:
        print(f"❌ 目标Conda环境路径不存在: {conda_env_path}")
    
    # 检查PM2是否可用
    pm2_path = shutil.which('pm2')
    if pm2_path:
        print(f"✅ PM2可执行文件: {pm2_path}")
    else:
        print("❌ 未找到PM2可执行文件")
    
    # 检查是否存在/app/backend/env路径
    backend_env = "/app/backend/env"
    if os.path.exists(backend_env):
        print(f"✅ /app/backend/env路径存在")
    else:
        print(f"❌ /app/backend/env路径不存在")

def check_pm2_ecosystem():
    """检查当前PM2配置文件"""
    print("\n===== PM2配置检查 =====")
    
    # 检查ecosystem.config.js文件
    if os.path.exists("ecosystem.config.js"):
        print("✅ ecosystem.config.js文件存在")
        # 显示文件内容
        try:
            with open("ecosystem.config.js", "r") as f:
                content = f.read()
                print("ecosystem.config.js内容:")
                print(content)
        except Exception as e:
            print(f"❌ 无法读取ecosystem.config.js: {e}")
    else:
        print("❌ ecosystem.config.js文件不存在")
    
    # 列出正在运行的PM2进程
    try:
        print("\nPM2进程列表:")
        result = subprocess.run(['pm2', 'list'], 
                              capture_output=True, 
                              text=True)
        print(result.stdout)
    except Exception as e:
        print(f"❌ 无法获取PM2进程列表: {e}")

if __name__ == "__main__":
    check_paths()
    check_pm2_ecosystem() 