#!/usr/bin/env python3
import subprocess
import os
import sys
import shutil

def check_pm2():
    """检查PM2是否可用，并打印详细信息"""
    print("开始检查PM2...")
    
    # 使用shutil.which查找可执行文件
    pm2_path = shutil.which('pm2')
    if pm2_path:
        print(f"✅ PM2可执行文件路径: {pm2_path}")
    else:
        print("❌ 未找到PM2可执行文件")
    
    # 检查环境变量
    pm2_env = os.environ.get('PM2_PATH')
    if pm2_env:
        print(f"✅ 环境变量PM2_PATH: {pm2_env}")
    else:
        print("❌ 未设置环境变量PM2_PATH")
    
    # 尝试执行PM2命令
    try:
        result = subprocess.run(['pm2', '--version'], 
                               capture_output=True, 
                               text=True, 
                               check=True)
        print(f"✅ PM2版本: {result.stdout.strip()}")
    except Exception as e:
        print(f"❌ 执行PM2命令失败: {e}")
    
    # 检查常见路径
    common_paths = [
        '/usr/local/bin/pm2',
        '/usr/bin/pm2',
        '/opt/node/bin/pm2',
        '/opt/nodejs/bin/pm2',
        '/opt/conda/bin/pm2',
        '/usr/local/lib/node_modules/pm2/bin/pm2',
        '/usr/lib/node_modules/pm2/bin/pm2'
    ]
    
    for path in common_paths:
        if os.path.isfile(path):
            if os.access(path, os.X_OK):
                print(f"✅ 找到可执行的PM2: {path}")
            else:
                print(f"⚠️ 找到PM2但不可执行: {path}")
    
    # 检查Node.js
    try:
        node_result = subprocess.run(['node', '--version'], 
                                    capture_output=True, 
                                    text=True, 
                                    check=True)
        print(f"✅ Node.js版本: {node_result.stdout.strip()}")
    except Exception as e:
        print(f"❌ 执行Node.js命令失败: {e}")
    
    # 检查npm
    try:
        npm_result = subprocess.run(['npm', '--version'], 
                                   capture_output=True, 
                                   text=True, 
                                   check=True)
        print(f"✅ npm版本: {npm_result.stdout.strip()}")
    except Exception as e:
        print(f"❌ 执行npm命令失败: {e}")
    
    print("PM2检查完成")

if __name__ == "__main__":
    check_pm2() 