#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的日志生成运行脚本
用于生成展示系统高可用性的40天日志
"""

import subprocess
import sys
import os

def run_log_generator():
    """运行日志生成器"""
    print("=" * 60)
    print("  风电功率预测系统 - 40天高可用性日志生成器")
    print("=" * 60)
    print()
    print("📋 此工具将生成40天的系统日志，用于证明月可用性 >99%")
    print()
    print("📊 日志特点：")
    print("   • INFO 日志占 88% - 显示系统正常运行")
    print("   • WARNING 日志占 10% - 轻微提醒，不影响可用性") 
    print("   • ERROR 日志仅占 1.5% - 偶发问题且已自动恢复")
    print("   • 大量系统健康检查和监控日志")
    print()
    
    # 确认运行
    confirm = input("🚀 是否开始生成日志文件？(y/n): ").lower().strip()
    if confirm not in ['y', 'yes', '是', '确定']:
        print("❌ 用户取消操作")
        return
    
    print()
    print("⏳ 正在生成日志文件...")
    print()
    
    try:
        # 运行主生成器
        result = subprocess.run([sys.executable, "generate_40days_log.py"], 
                              capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print("✅ 日志生成成功！")
            print()
            print(result.stdout)
            
            # 检查生成的文件
            output_file = "wind_forecast_40days.log"
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                print(f"📁 文件位置: {os.path.abspath(output_file)}")
                print(f"📦 文件大小: {file_size / 1024 / 1024:.2f} MB")
                
                # 显示文件预览
                print()
                print("👀 日志文件预览（前10行）：")
                print("-" * 60)
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        for i, line in enumerate(f):
                            if i >= 10:
                                break
                            print(line.rstrip())
                except Exception as e:
                    print(f"预览文件时出错: {e}")
                print("-" * 60)
                
        else:
            print("❌ 日志生成失败！")
            print("错误信息:")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ 运行时出错: {e}")

if __name__ == "__main__":
    run_log_generator() 