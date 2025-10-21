#!/usr/bin/env python3
"""
详细的数据库连接测试脚本
"""
import os
import sys

# 添加当前目录到路径
sys.path.insert(0, '.')

def test_direct_connection():
    """测试直接数据库连接"""
    print("=== 测试直接数据库连接 ===")

    try:
        import psycopg2
        print("[OK] psycopg2模块导入成功")

        # 从配置文件读取连接信息
        DB_HOST = 'localhost'  # 使用localhost而不是kingbase
        DB_PORT = '54321'
        DB_USER = 'system'
        DB_PASSWORD = '12345678ab'
        DB_NAME = 'windpower'

        print(f"连接信息: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

        # 尝试连接
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connect_timeout=10
        )

        print("[OK] 数据库连接成功！")

        # 执行测试查询
        cursor = conn.cursor()
        cursor.execute("SELECT 1 as test_column")
        result = cursor.fetchone()
        print(f"[OK] 查询结果: {result}")

        cursor.close()
        conn.close()

        return True

    except ImportError as e:
        print(f"[ERROR] psycopg2导入失败: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] 连接失败: {e}")
        return False

def test_sqlalchemy_connection():
    """测试SQLAlchemy连接"""
    print("\n=== 测试SQLAlchemy连接 ===")

    try:
        from sqlalchemy import create_engine
        print("[OK] SQLAlchemy模块导入成功")

        # 构建连接URL
        DB_HOST = 'localhost'  # 使用localhost而不是kingbase
        DB_PORT = '54321'
        DB_USER = 'system'
        DB_PASSWORD = '12345678ab'
        DB_NAME = 'windpower'

        database_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        print(f"连接URL: {database_url}")

        # 创建引擎
        engine = create_engine(database_url)
        print("[OK] SQLAlchemy引擎创建成功")

        # 测试连接
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print(f"[OK] 查询结果: {result.fetchone()}")

        return True

    except ImportError as e:
        print(f"[ERROR] SQLAlchemy导入失败: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] 连接失败: {e}")
        return False

def test_kingbase_dialect():
    """测试KingBase方言"""
    print("\n=== 测试KingBase方言 ===")

    try:
        # 导入KingBase方言
        import kingbase_dialect
        print("[OK] KingBase方言导入成功")

        from sqlalchemy import create_engine

        # 使用KingBase方言
        DB_HOST = 'localhost'  # 使用localhost而不是kingbase
        DB_PORT = '54321'
        DB_USER = 'system'
        DB_PASSWORD = '12345678ab'
        DB_NAME = 'windpower'

        database_url = f"postgresql+kingbase://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        print(f"KingBase连接URL: {database_url}")

        engine = create_engine(database_url)
        print("[OK] KingBase引擎创建成功")

        # 测试连接
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print(f"[OK] 查询结果: {result.fetchone()}")

        return True

    except ImportError as e:
        print(f"[ERROR] KingBase方言导入失败: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] 连接失败: {e}")
        return False

if __name__ == "__main__":
    print("详细数据库连接测试")
    print("=" * 50)

    results = []

    # 测试各种连接方式
    results.append(("直接psycopg2", test_direct_connection()))
    results.append(("SQLAlchemy", test_sqlalchemy_connection()))
    results.append(("KingBase方言", test_kingbase_dialect()))

    # 输出结果
    print("\n" + "=" * 50)
    print("测试结果总结:")
    for name, success in results:
        status = "[OK]" if success else "[ERROR]"
        print(f"{status} {name}")

    # 如果有任一连接成功，就可以继续
    if any(success for _, success in results):
        print("\n[OK] 至少一种连接方式成功，可以执行迁移！")
        sys.exit(0)
    else:
        print("\n[ERROR] 所有连接方式都失败，需要进一步检查！")
        sys.exit(1)