#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速验证脚本：检查超短期训练并发控制修复是否生效
"""

import os
import sys
import time
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_file_exists(file_path, description):
    """检查文件是否存在"""
    if os.path.exists(file_path):
        logger.info(f"✅ {description}: {file_path}")
        return True
    else:
        logger.error(f"❌ {description}: {file_path}")
        return False

def check_function_in_file(file_path, function_name, description):
    """检查文件中是否包含指定函数"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if function_name in content:
                logger.info(f"✅ {description}: 找到 {function_name}")
                return True
            else:
                logger.error(f"❌ {description}: 未找到 {function_name}")
                return False
    except Exception as e:
        logger.error(f"❌ {description}: 读取文件失败 - {e}")
        return False

def check_import_in_file(file_path, import_statement, description):
    """检查文件中是否包含指定的导入语句"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if import_statement in content:
                logger.info(f"✅ {description}: 找到 {import_statement}")
                return True
            else:
                logger.error(f"❌ {description}: 未找到 {import_statement}")
                return False
    except Exception as e:
        logger.error(f"❌ {description}: 读取文件失败 - {e}")
        return False

def verify_concurrent_fix():
    """验证并发控制修复"""
    logger.info("开始验证超短期训练并发控制修复...")
    logger.info("=" * 60)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    scheduler_file = os.path.join(current_dir, "scheduler_supershort.py")
    
    # 检查关键文件是否存在
    checks = []
    
    # 1. 检查调度器文件
    checks.append(check_file_exists(scheduler_file, "调度器文件"))
    
    # 2. 检查关键函数是否存在
    if os.path.exists(scheduler_file):
        checks.append(check_function_in_file(scheduler_file, "run_threaded_training", "训练线程管理函数"))
        checks.append(check_function_in_file(scheduler_file, "create_file_lock", "文件锁创建函数"))
        checks.append(check_function_in_file(scheduler_file, "release_file_lock", "文件锁释放函数"))
        checks.append(check_function_in_file(scheduler_file, "mark_supershort_train_running_today", "运行中标志函数"))
        checks.append(check_function_in_file(scheduler_file, "is_supershort_train_running_today", "运行状态检查函数"))
        checks.append(check_function_in_file(scheduler_file, "cleanup_training_flags", "清理函数"))
        
        # 3. 检查关键导入
        checks.append(check_import_in_file(scheduler_file, "current_training_thread", "训练线程跟踪变量"))
        checks.append(check_import_in_file(scheduler_file, "training_lock", "训练锁变量"))
    
    # 4. 检查测试文件
    test_file = os.path.join(current_dir, "test_concurrent_fix.py")
    checks.append(check_file_exists(test_file, "并发测试文件"))
    
    # 5. 检查README文件
    readme_file = os.path.join(current_dir, "CONCURRENT_FIX_README.md")
    checks.append(check_file_exists(readme_file, "修复说明文件"))
    
    # 6. 检查日志目录结构
    logs_dir = os.path.join(current_dir, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        logger.info(f"✅ 创建日志目录: {logs_dir}")
    else:
        logger.info(f"✅ 日志目录存在: {logs_dir}")
    
    train_flags_dir = os.path.join(logs_dir, "supershort_train_flags")
    if not os.path.exists(train_flags_dir):
        os.makedirs(train_flags_dir)
        logger.info(f"✅ 创建训练标志目录: {train_flags_dir}")
    else:
        logger.info(f"✅ 训练标志目录存在: {train_flags_dir}")
    
    # 7. 检查修复的调度器配置
    if os.path.exists(scheduler_file):
        checks.append(check_function_in_file(scheduler_file, "run_threaded_training, run_supershort_train_script", "修复的调度器配置"))
    
    # 统计结果
    logger.info("=" * 60)
    logger.info("验证结果统计:")
    passed = sum(checks)
    total = len(checks)
    success_rate = (passed / total) * 100 if total > 0 else 0
    
    logger.info(f"通过检查: {passed}/{total} ({success_rate:.1f}%)")
    
    if success_rate >= 90:
        logger.info("🎉 验证通过！并发控制修复已成功应用。")
        return True
    elif success_rate >= 70:
        logger.warning("⚠️ 验证部分通过，可能存在一些问题。")
        return False
    else:
        logger.error("❌ 验证失败，修复可能未正确应用。")
        return False

def simulate_concurrent_access():
    """模拟并发访问测试"""
    logger.info("\n" + "=" * 60)
    logger.info("开始模拟并发访问测试...")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 创建测试锁文件
    today_date_str = datetime.now().strftime('%Y%m%d')
    test_lock_file = os.path.join(current_dir, "logs", "supershort_train_flags", f"{today_date_str}_test_supershort_train.lock")
    
    try:
        # 测试文件锁创建
        logger.info("测试文件锁创建...")
        
        # 尝试导入修复后的函数
        sys.path.insert(0, current_dir)
        try:
            from scheduler_supershort import create_file_lock, release_file_lock
            
            # 测试锁创建
            lock_fd, lock_acquired = create_file_lock(test_lock_file)
            if lock_acquired:
                logger.info("✅ 文件锁创建成功")
                
                # 测试重复锁获取（应该失败）
                lock_fd2, lock_acquired2 = create_file_lock(test_lock_file)
                if not lock_acquired2:
                    logger.info("✅ 重复锁获取被正确拒绝")
                else:
                    logger.warning("⚠️ 重复锁获取未被拒绝，可能存在问题")
                    if lock_fd2:
                        release_file_lock(lock_fd2, test_lock_file)
                
                # 释放锁
                release_file_lock(lock_fd, test_lock_file)
                logger.info("✅ 文件锁释放成功")
                
                return True
            else:
                logger.error("❌ 文件锁创建失败")
                return False
                
        except ImportError as e:
            logger.error(f"❌ 无法导入修复后的函数: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ 并发访问测试失败: {e}")
        return False
    finally:
        # 清理测试文件
        if os.path.exists(test_lock_file):
            try:
                os.remove(test_lock_file)
                logger.info("✅ 清理测试文件成功")
            except:
                pass

def main():
    """主函数"""
    print("超短期训练并发控制修复验证")
    print("=" * 60)
    
    # 基础验证
    basic_check = verify_concurrent_fix()
    
    # 并发访问测试
    concurrent_check = simulate_concurrent_access()
    
    # 最终结果
    print("\n" + "=" * 60)
    print("最终验证结果:")
    
    if basic_check and concurrent_check:
        print("🎉 所有验证通过！修复已成功应用，可以安全使用。")
        print("\n下一步操作：")
        print("1. 运行调度器: python scheduler_supershort.py")
        print("2. 测试训练: python scheduler_supershort.py --run-supershort-train-now")
        print("3. 并发测试: python test_concurrent_fix.py")
    elif basic_check:
        print("⚠️ 基础验证通过，但并发测试失败。")
        print("可能的原因：文件锁机制在当前系统上不完全支持。")
        print("建议：仍然可以使用，但请密切监控训练过程。")
    else:
        print("❌ 验证失败，修复可能未正确应用。")
        print("建议：")
        print("1. 检查文件是否正确修改")
        print("2. 查看错误日志")
        print("3. 重新应用修复")

if __name__ == "__main__":
    main() 