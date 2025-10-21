#!/usr/bin/env python3
"""
等待数据库启动的脚本
"""
import time
import subprocess
import sys

def wait_for_database(max_attempts=30, delay=5):
    """等待数据库启动"""
    print("等待数据库启动...")

    for attempt in range(max_attempts):
        try:
            # 使用python执行数据库检查
            result = subprocess.run(
                ['./wind-power-env/python.exe', 'check_db.py'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if "数据库连接正常" in result.stdout:
                print(f"✓ 数据库连接成功！")
                return True
            else:
                print(f"尝试 {attempt + 1}/{max_attempts}: 数据库连接失败...")
                print(f"输出: {result.stdout}")
                if result.stderr:
                    print(f"错误: {result.stderr}")

        except subprocess.TimeoutExpired:
            print(f"尝试 {attempt + 1}/{max_attempts}: 连接超时...")
        except Exception as e:
            print(f"尝试 {attempt + 1}/{max_attempts}: 异常 - {e}")

        if attempt < max_attempts - 1:
            print(f"等待 {delay} 秒后重试...")
            time.sleep(delay)

    print("✗ 数据库连接超时！")
    return False

if __name__ == "__main__":
    if wait_for_database():
        print("可以开始执行迁移了！")
        sys.exit(0)
    else:
        print("请检查数据库容器状态！")
        sys.exit(1)