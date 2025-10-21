#!/usr/bin/env python3
"""
简单的数据库连接检查脚本
"""
import subprocess
import sys

def test_kingbase_connection():
    """测试KingBase连接"""
    print("尝试直接连接KingBase数据库...")

    try:
        # 使用Docker exec直接在容器中测试连接
        result = subprocess.run([
            'docker', 'exec', '-i', 'wind-power-kingbase',
            'ksql', '-U', 'system', '-d', 'windpower', '-c', 'SELECT 1;'
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            print("[OK] KingBase数据库连接正常！")
            print(f"输出: {result.stdout}")
            return True
        else:
            print(f"[ERROR] KingBase连接失败: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("[ERROR] 连接超时")
        return False
    except FileNotFoundError:
        print("[ERROR] Docker命令未找到")
        return False
    except Exception as e:
        print(f"[ERROR] 连接异常: {e}")
        return False

def show_database_info():
    """显示数据库信息"""
    print("\n=== 数据库容器信息 ===")
    try:
        result = subprocess.run(['docker', 'ps', '--filter', 'name=wind-power-kingbase'],
                              capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"获取容器信息失败: {e}")

def show_config_info():
    """显示配置信息"""
    print("\n=== 配置信息 ===")
    try:
        with open('config.py', 'r') as f:
            for line in f:
                if any(x in line for x in ['DB_HOST', 'DB_PORT', 'DB_USER', 'DB_NAME']):
                    print(line.strip())
    except Exception as e:
        print(f"读取配置失败: {e}")

if __name__ == "__main__":
    print("KingBase数据库连接检查")
    print("=" * 40)

    show_config_info()
    show_database_info()

    print("\n=== 连接测试 ===")
    if test_kingbase_connection():
        print("\n[OK] 数据库已就绪，可以执行迁移！")
        sys.exit(0)
    else:
        print("\n[ERROR] 数据库连接失败，请检查：")
        print("1. Docker容器是否正在运行")
        print("2. 数据库是否完全启动")
        print("3. 用户名密码是否正确")
        sys.exit(1)