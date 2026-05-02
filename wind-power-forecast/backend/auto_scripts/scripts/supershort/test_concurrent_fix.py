#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：验证超短期训练并发控制修复
此脚本模拟多个调度器同时启动的情况，验证是否能正确防止并发问题
"""

import os
import sys
import time
import threading
import multiprocessing
import logging
from datetime import datetime
import subprocess

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 获取当前脚本目录
current_dir = os.path.dirname(os.path.abspath(__file__))
scheduler_script = os.path.join(current_dir, "scheduler_supershort.py")

class ConcurrentTrainingTest:
    """并发训练测试类"""
    
    def __init__(self):
        self.test_results = []
        self.lock = threading.Lock()
        
    def run_scheduler_process(self, process_id, duration=60):
        """运行调度器进程"""
        try:
            logger.info(f"启动测试进程 {process_id}")
            
            # 启动调度器进程
            cmd = [sys.executable, scheduler_script, "--run-supershort-train-now"]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=current_dir
            )
            
            # 等待一段时间
            time.sleep(duration)
            
            # 终止进程
            process.terminate()
            
            # 获取输出
            try:
                output, _ = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                output, _ = process.communicate()
            
            with self.lock:
                self.test_results.append({
                    'process_id': process_id,
                    'return_code': process.returncode,
                    'output': output
                })
                
            logger.info(f"测试进程 {process_id} 完成，返回码: {process.returncode}")
            
        except Exception as e:
            logger.error(f"测试进程 {process_id} 发生错误: {e}")
            with self.lock:
                self.test_results.append({
                    'process_id': process_id,
                    'return_code': -1,
                    'error': str(e)
                })
    
    def run_concurrent_test(self, num_processes=3, duration=60):
        """运行并发测试"""
        logger.info(f"开始并发测试：{num_processes} 个进程，持续 {duration} 秒")
        
        # 清理之前的标志文件
        self.cleanup_test_files()
        
        # 启动多个进程
        processes = []
        for i in range(num_processes):
            p = multiprocessing.Process(
                target=self.run_scheduler_process,
                args=(i + 1, duration)
            )
            processes.append(p)
            p.start()
            time.sleep(1)  # 错开启动时间
        
        # 等待所有进程完成
        for p in processes:
            p.join()
        
        # 分析结果
        self.analyze_results()
    
    def cleanup_test_files(self):
        """清理测试文件"""
        try:
            today_date_str = datetime.now().strftime('%Y%m%d')
            log_dir = os.path.join(current_dir, "logs", "supershort_train_flags")
            
            if os.path.exists(log_dir):
                for filename in os.listdir(log_dir):
                    if today_date_str in filename:
                        file_path = os.path.join(log_dir, filename)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            logger.info(f"清理测试文件: {file_path}")
        except Exception as e:
            logger.warning(f"清理测试文件时发生错误: {e}")
    
    def analyze_results(self):
        """分析测试结果"""
        logger.info("=" * 50)
        logger.info("测试结果分析")
        logger.info("=" * 50)
        
        # 统计结果
        total_processes = len(self.test_results)
        successful_processes = sum(1 for r in self.test_results if r.get('return_code') == 0)
        
        logger.info(f"总进程数: {total_processes}")
        logger.info(f"成功进程数: {successful_processes}")
        
        # 检查输出中的关键信息
        training_started_count = 0
        lock_conflicts = 0
        
        for result in self.test_results:
            output = result.get('output', '')
            if '开始执行超短期模型训练任务' in output:
                training_started_count += 1
            if '无法获取文件锁' in output or '无法获取训练文件锁' in output:
                lock_conflicts += 1
        
        logger.info(f"实际启动训练的进程数: {training_started_count}")
        logger.info(f"遇到锁冲突的进程数: {lock_conflicts}")
        
        # 判断测试是否成功
        if training_started_count <= 1:
            logger.info("✅ 测试成功：并发控制机制有效，只有一个进程执行了训练")
        else:
            logger.error("❌ 测试失败：检测到多个进程同时执行训练")
        
        # 输出详细信息
        logger.info("\n详细结果:")
        for result in self.test_results:
            logger.info(f"进程 {result['process_id']}: 返回码 {result.get('return_code')}")
            if result.get('error'):
                logger.info(f"  错误: {result['error']}")
    
    def run_quick_test(self):
        """快速测试：模拟调度器启动多个训练任务"""
        logger.info("开始快速测试...")
        
        # 清理之前的标志文件
        self.cleanup_test_files()
        
        # 模拟多个线程同时调用训练函数
        threads = []
        for i in range(3):
            t = threading.Thread(target=self.simulate_training_call, args=(i + 1,))
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        logger.info("快速测试完成")
    
    def simulate_training_call(self, thread_id):
        """模拟训练调用"""
        try:
            # 这里需要导入并调用修复后的训练函数
            # 由于路径问题，我们使用subprocess来调用
            cmd = [sys.executable, "-c", f"""
import sys
import os
sys.path.insert(0, r'{current_dir}')

# 导入修复后的调度器模块
from scheduler_supershort import run_supershort_train_script

# 调用训练函数
run_supershort_train_script()
"""]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=current_dir)
            logger.info(f"线程 {thread_id} 完成，返回码: {result.returncode}")
            
        except Exception as e:
            logger.error(f"线程 {thread_id} 发生错误: {e}")

def main():
    """主函数"""
    print("超短期训练并发控制测试")
    print("=" * 50)
    
    if not os.path.exists(scheduler_script):
        print(f"错误：找不到调度器脚本 {scheduler_script}")
        return
    
    tester = ConcurrentTrainingTest()
    
    # 选择测试类型
    test_type = input("请选择测试类型 (1: 快速测试, 2: 完整并发测试): ").strip()
    
    if test_type == "1":
        tester.run_quick_test()
    elif test_type == "2":
        duration = int(input("请输入测试持续时间（秒，默认60）: ").strip() or "60")
        num_processes = int(input("请输入并发进程数（默认3）: ").strip() or "3")
        tester.run_concurrent_test(num_processes, duration)
    else:
        print("无效的选择")
        return
    
    print("\n测试完成！请查看上方的测试结果。")

if __name__ == "__main__":
    main() 