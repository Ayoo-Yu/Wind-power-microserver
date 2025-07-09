#!/usr/bin/env python3
"""
用于检查项目中所有关键文件路径是否存在
"""

import os
import sys

# 定义要检查的文件路径
file_paths = [
    # 调度器脚本
    "/app/auto_scripts/scripts/supershort/scheduler_supershort.py",
    "/app/auto_scripts/scripts/short/scheduler_short.py",
    "/app/auto_scripts/scripts/middle/scheduler_middle.py",
    
    # 训练脚本 
    "/app/auto_scripts/scripts/supershort/auto_train.py",
    "/app/auto_scripts/scripts/short/auto_pre_train.py",
    "/app/auto_scripts/scripts/middle/auto_pre_train.py",
    
    # 参数优化脚本
    "/app/auto_scripts/scripts/supershort/param_optimizer.py",
    "/app/auto_scripts/scripts/short/param_optimizer.py",
    "/app/auto_scripts/scripts/middle/param_optimizer.py",
    
    # 链接目录
    "/app/backend/auto_scripts/scripts/supershort/",
    "/app/backend/auto_scripts/scripts/short/",
    "/app/backend/auto_scripts/scripts/middle/",
    
    # Conda环境路径
    "/opt/conda/envs/wind-power-env/bin/python"
]

def check_paths():
    """检查所有文件路径是否存在"""
    print("===== 文件路径检查 =====")
    
    all_paths_exist = True
    
    for path in file_paths:
        if os.path.exists(path):
            print(f"✅ 路径存在: {path}")
            
            # 如果是目录，检查它是否为符号链接
            if os.path.isdir(path) and path.startswith("/app/backend"):
                target = os.readlink(path) if os.path.islink(path) else "不是符号链接"
                print(f"   链接目标: {target}")
        else:
            print(f"❌ 路径不存在: {path}")
            all_paths_exist = False
    
    # 检查父目录是否存在 (如果子文件不存在)
    if not all_paths_exist:
        print("\n检查父目录...")
        parent_dirs = [
            "/app",
            "/app/auto_scripts",
            "/app/auto_scripts/scripts",
            "/app/auto_scripts/scripts/supershort",
            "/app/auto_scripts/scripts/short",
            "/app/auto_scripts/scripts/middle",
            "/app/backend",
            "/app/backend/auto_scripts",
            "/app/backend/auto_scripts/scripts"
        ]
        
        for directory in parent_dirs:
            if os.path.exists(directory):
                print(f"📁 目录存在: {directory}")
                # 列出目录内容
                try:
                    contents = os.listdir(directory)
                    print(f"   内容: {', '.join(contents[:5])}" + 
                          (f" ... (还有{len(contents)-5}个)" if len(contents) > 5 else ""))
                except Exception as e:
                    print(f"   无法列出内容: {e}")
            else:
                print(f"❌ 目录不存在: {directory}")
                
    return all_paths_exist

if __name__ == "__main__":
    if check_paths():
        print("\n所有路径检查通过!")
        sys.exit(0)
    else:
        print("\n有些路径不存在，请检查文件结构和符号链接.")
        sys.exit(1) 