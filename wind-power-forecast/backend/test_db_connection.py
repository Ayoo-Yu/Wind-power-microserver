#!/usr/bin/env python3
"""
详细的数据库连接测试脚本
"""
import os
import sys

# 添加当前目录到路径
sys.path.insert(0, '.')


def database_settings():
    """从环境变量读取诊断连接配置。"""
    password = os.environ.get('DB_PASSWORD')
    if not password:
        raise RuntimeError('DB_PASSWORD 未配置')
    return {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': os.environ.get('DB_PORT', '54321'),
        'user': os.environ.get('DB_USER', 'system'),
        'password': password,
        'name': os.environ.get('DB_NAME', 'windpower'),
    }

def test_direct_connection():
    """测试直接数据库连接"""
    print("=== 测试直接数据库连接 ===")

    try:
        import psycopg2
        print("[OK] psycopg2模块导入成功")

        config = database_settings()

        print(f"连接信息: {config['user']}@{config['host']}:{config['port']}/{config['name']}")

        # 尝试连接
        conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            user=config['user'],
            password=config['password'],
            database=config['name'],
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

        config = database_settings()

        database_url = (
            f"postgresql+psycopg2://{config['user']}:{config['password']}"
            f"@{config['host']}:{config['port']}/{config['name']}"
        )
        print(
            f"连接信息: {config['user']}@{config['host']}:"
            f"{config['port']}/{config['name']}"
        )

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

        config = database_settings()

        database_url = (
            f"postgresql+kingbase://{config['user']}:{config['password']}"
            f"@{config['host']}:{config['port']}/{config['name']}"
        )
        print(
            f"KingBase连接信息: {config['user']}@{config['host']}:"
            f"{config['port']}/{config['name']}"
        )

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
