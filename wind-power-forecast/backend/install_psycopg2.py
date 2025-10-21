#!/usr/bin/env python3
"""
安装psycopg2二进制包以避免编译问题
"""
import subprocess
import sys

def install_psycopg2_binary():
    """安装psycopg2-binary"""
    print("正在安装psycopg2-binary...")

    try:
        result = subprocess.run([
            './wind-power-env/python.exe', '-m', 'pip', 'install', 'psycopg2-binary'
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print("[OK] psycopg2-binary安装成功！")
            return True
        else:
            print(f"[ERROR] 安装失败: {result.stderr}")
            return False

    except Exception as e:
        print(f"[ERROR] 安装异常: {e}")
        return False

def install_sqlalchemy():
    """安装SQLAlchemy"""
    print("正在安装SQLAlchemy...")

    try:
        result = subprocess.run([
            './wind-power-env/python.exe', '-m', 'pip', 'install', 'SQLAlchemy'
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print("[OK] SQLAlchemy安装成功！")
            return True
        else:
            print(f"[ERROR] 安装失败: {result.stderr}")
            return False

    except Exception as e:
        print(f"[ERROR] 安装异常: {e}")
        return False

if __name__ == "__main__":
    print("安装数据库连接依赖")
    print("=" * 40)

    success = True

    if not install_psycopg2_binary():
        success = False

    if not install_sqlalchemy():
        success = False

    if success:
        print("\n[OK] 所有依赖安装完成！")
        print("现在可以测试数据库连接了。")
    else:
        print("\n[ERROR] 部分依赖安装失败！")