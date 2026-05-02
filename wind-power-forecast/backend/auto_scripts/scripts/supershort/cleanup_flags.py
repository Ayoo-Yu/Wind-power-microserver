#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速清理脚本：清理训练状态文件和锁文件
"""

import os
import sys
import time
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanup_all_flags():
    """清理所有训练相关的标志文件"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    flags_dir = os.path.join(current_dir, "logs", "supershort_train_flags")
    
    if not os.path.exists(flags_dir):
        logger.info("标志文件目录不存在，无需清理")
        return
    
    logger.info(f"开始清理标志文件目录: {flags_dir}")
    
    cleaned_count = 0
    
    try:
        for filename in os.listdir(flags_dir):
            file_path = os.path.join(flags_dir, filename)
            
            if os.path.isfile(file_path):
                try:
                    # 多次尝试删除文件
                    for attempt in range(3):
                        try:
                            os.remove(file_path)
                            logger.info(f"✅ 删除文件: {filename}")
                            cleaned_count += 1
                            break
                        except PermissionError:
                            if attempt < 2:
                                time.sleep(0.1)
                                continue
                            else:
                                logger.warning(f"⚠️ 无法删除文件（权限问题）: {filename}")
                        except Exception as e:
                            logger.error(f"❌ 删除文件失败: {filename} - {e}")
                            break
                            
                except Exception as e:
                    logger.error(f"❌ 处理文件时发生错误: {filename} - {e}")
    
    except Exception as e:
        logger.error(f"❌ 清理过程中发生错误: {e}")
    
    logger.info(f"清理完成，共删除 {cleaned_count} 个文件")

def cleanup_today_flags():
    """只清理今天的训练相关标志文件"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    flags_dir = os.path.join(current_dir, "logs", "supershort_train_flags")
    today_date_str = datetime.now().strftime('%Y%m%d')
    
    if not os.path.exists(flags_dir):
        logger.info("标志文件目录不存在，无需清理")
        return
    
    logger.info(f"开始清理今天 ({today_date_str}) 的标志文件")
    
    cleaned_count = 0
    
    try:
        for filename in os.listdir(flags_dir):
            if today_date_str in filename:
                file_path = os.path.join(flags_dir, filename)
                
                if os.path.isfile(file_path):
                    try:
                        # 多次尝试删除文件
                        for attempt in range(3):
                            try:
                                os.remove(file_path)
                                logger.info(f"✅ 删除今天的文件: {filename}")
                                cleaned_count += 1
                                break
                            except PermissionError:
                                if attempt < 2:
                                    time.sleep(0.1)
                                    continue
                                else:
                                    logger.warning(f"⚠️ 无法删除文件（权限问题）: {filename}")
                            except Exception as e:
                                logger.error(f"❌ 删除文件失败: {filename} - {e}")
                                break
                                
                    except Exception as e:
                        logger.error(f"❌ 处理文件时发生错误: {filename} - {e}")
    
    except Exception as e:
        logger.error(f"❌ 清理过程中发生错误: {e}")
    
    logger.info(f"清理完成，共删除 {cleaned_count} 个今天的文件")

def show_current_flags():
    """显示当前的标志文件状态"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    flags_dir = os.path.join(current_dir, "logs", "supershort_train_flags")
    today_date_str = datetime.now().strftime('%Y%m%d')
    
    if not os.path.exists(flags_dir):
        logger.info("标志文件目录不存在")
        return
    
    logger.info(f"当前标志文件状态 (目录: {flags_dir}):")
    
    try:
        files = os.listdir(flags_dir)
        if not files:
            logger.info("📁 目录为空，没有标志文件")
            return
        
        today_files = []
        other_files = []
        
        for filename in files:
            file_path = os.path.join(flags_dir, filename)
            if os.path.isfile(file_path):
                try:
                    stat_info = os.stat(file_path)
                    file_time = datetime.fromtimestamp(stat_info.st_mtime)
                    file_size = stat_info.st_size
                    
                    file_info = f"{filename} (大小: {file_size} 字节, 修改时间: {file_time.strftime('%Y-%m-%d %H:%M:%S')})"
                    
                    if today_date_str in filename:
                        today_files.append(file_info)
                    else:
                        other_files.append(file_info)
                        
                except Exception as e:
                    logger.error(f"❌ 无法获取文件信息: {filename} - {e}")
        
        if today_files:
            logger.info(f"📅 今天 ({today_date_str}) 的文件:")
            for file_info in today_files:
                logger.info(f"  - {file_info}")
        else:
            logger.info(f"📅 今天 ({today_date_str}) 没有标志文件")
        
        if other_files:
            logger.info("📋 其他日期的文件:")
            for file_info in other_files:
                logger.info(f"  - {file_info}")
        
    except Exception as e:
        logger.error(f"❌ 读取目录时发生错误: {e}")

def main():
    """主函数"""
    print("超短期训练标志文件清理工具")
    print("=" * 50)
    
    # 显示当前状态
    show_current_flags()
    print("\n" + "=" * 50)
    
    # 获取用户选择
    print("请选择操作：")
    print("1. 清理今天的标志文件")
    print("2. 清理所有标志文件")
    print("3. 只查看状态（不清理）")
    print("4. 退出")
    
    try:
        choice = input("\n请输入选择 (1-4): ").strip()
        
        if choice == "1":
            print("\n清理今天的标志文件...")
            cleanup_today_flags()
        elif choice == "2":
            confirm = input("\n确认要清理所有标志文件吗？(y/N): ").strip().lower()
            if confirm in ['y', 'yes']:
                print("\n清理所有标志文件...")
                cleanup_all_flags()
            else:
                print("已取消清理操作")
        elif choice == "3":
            print("\n只查看状态，不进行清理")
        elif choice == "4":
            print("\n退出程序")
            return
        else:
            print("\n无效的选择")
            return
    
    except KeyboardInterrupt:
        print("\n\n操作被中断")
        return
    except Exception as e:
        logger.error(f"❌ 操作过程中发生错误: {e}")
        return
    
    # 显示清理后的状态
    if choice in ["1", "2"]:
        print("\n" + "=" * 50)
        print("清理后的状态：")
        show_current_flags()
    
    print("\n操作完成！")

if __name__ == "__main__":
    main() 