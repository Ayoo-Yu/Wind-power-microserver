#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试脚本：手动测试训练脚本并查看具体错误
"""

import os
import sys
import subprocess
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_training_script():
    """测试训练脚本"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    train_script = os.path.join(current_dir, "train_supershort.py")
    
    if not os.path.exists(train_script):
        logger.error(f"训练脚本不存在: {train_script}")
        return False
    
    logger.info(f"测试训练脚本: {train_script}")
    
    # 获取Python解释器路径
    python_exe = sys.executable
    logger.info(f"使用Python解释器: {python_exe}")
    
    # 构建命令
    cmd = [python_exe, train_script]
    logger.info(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 运行训练脚本
        result = subprocess.run(
            cmd,
            cwd=current_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300  # 5分钟超时
        )
        
        logger.info(f"训练脚本返回码: {result.returncode}")
        
        # 输出stdout
        if result.stdout:
            logger.info("训练脚本输出 (stdout):")
            print("=" * 50)
            print(result.stdout)
            print("=" * 50)
        else:
            logger.info("训练脚本没有stdout输出")
        
        # 输出stderr
        if result.stderr:
            logger.error("训练脚本错误 (stderr):")
            print("=" * 50)
            print(result.stderr)
            print("=" * 50)
        else:
            logger.info("训练脚本没有stderr输出")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        logger.error("训练脚本执行超时（5分钟）")
        return False
    except Exception as e:
        logger.error(f"执行训练脚本时发生错误: {e}")
        return False

def check_dependencies():
    """检查依赖项"""
    logger.info("检查依赖项...")
    
    # 检查数据库连接
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.join(current_dir, '..', '..', '..'))
        
        from data_processor_supershort import load_and_merge_data_from_db
        logger.info("✅ 数据处理模块导入成功")
        
        # 尝试从数据库加载数据
        data = load_and_merge_data_from_db()
        if data is not None and not data.empty:
            logger.info(f"✅ 数据库连接正常，数据行数: {len(data)}")
        else:
            logger.warning("⚠️ 数据库连接正常但数据为空")
            
    except Exception as e:
        logger.error(f"❌ 数据库连接或数据处理模块有问题: {e}")
    
    # 检查模型目录
    try:
        from config_supershort import DATASET_FOLDER, MODEL_FOLDER
        logger.info(f"✅ 配置文件导入成功")
        logger.info(f"数据集目录: {DATASET_FOLDER}")
        logger.info(f"模型目录: {MODEL_FOLDER}")
        
        # 检查目录是否存在
        if not os.path.exists(DATASET_FOLDER):
            os.makedirs(DATASET_FOLDER)
            logger.info(f"✅ 创建数据集目录: {DATASET_FOLDER}")
        
        if not os.path.exists(MODEL_FOLDER):
            os.makedirs(MODEL_FOLDER)
            logger.info(f"✅ 创建模型目录: {MODEL_FOLDER}")
            
    except Exception as e:
        logger.error(f"❌ 配置文件或目录有问题: {e}")

def check_training_environment():
    """检查训练环境"""
    logger.info("检查训练环境...")
    
    # 检查Python版本
    logger.info(f"Python版本: {sys.version}")
    
    # 检查必要的包
    required_packages = ['pandas', 'numpy', 'sklearn', 'joblib']
    for package in required_packages:
        try:
            __import__(package)
            logger.info(f"✅ {package} 已安装")
        except ImportError:
            logger.error(f"❌ {package} 未安装")
    
    # 检查当前工作目录
    logger.info(f"当前工作目录: {os.getcwd()}")
    
    # 检查日志目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(current_dir, "logs", "auto_train")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        logger.info(f"✅ 创建日志目录: {log_dir}")
    else:
        logger.info(f"✅ 日志目录存在: {log_dir}")

def main():
    """主函数"""
    print("超短期训练调试脚本")
    print("=" * 50)
    
    # 检查环境
    check_training_environment()
    print("\n" + "=" * 50)
    
    # 检查依赖项
    check_dependencies()
    print("\n" + "=" * 50)
    
    # 测试训练脚本
    success = test_training_script()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 训练脚本测试成功！")
    else:
        print("❌ 训练脚本测试失败，请查看上方的错误信息")
    
    return success

if __name__ == "__main__":
    main() 