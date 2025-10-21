#!/usr/bin/env python3
"""
最终版本的多场站迁移脚本
"""
import psycopg2
import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_connection():
    """获取数据库连接"""
    try:
        conn = psycopg2.connect(
            host='localhost',
            port='54321',
            user='system',
            password='12345678ab',
            database='windpower',
            connect_timeout=10
        )
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None

def create_default_farm(conn):
    """创建默认场站"""
    try:
        with conn.cursor() as cur:
            # 检查是否存在默认场站
            cur.execute("SELECT * FROM wind_farms WHERE farm_code = %s", ('DEFAULT_FARM',))
            if not cur.fetchone():
                # 创建默认场站
                cur.execute("""
                    INSERT INTO wind_farms (farm_code, farm_name, capacity, location, is_active)
                    VALUES (%s, %s, %s, %s, %s)
                """, ('DEFAULT_FARM', '默认风电场', 100.0, '默认位置', True))
                conn.commit()
                logger.info("创建默认场站: DEFAULT_FARM")
            else:
                logger.info("默认场站已存在")
        return True
    except Exception as e:
        logger.error(f"创建默认场站失败: {e}")
        return False

def add_farm_code_columns(conn):
    """添加farm_code字段"""
    try:
        with conn.cursor() as cur:
            # 需要添加字段的表
            tables = [
                'actual_power',
                'supershortl_power',
                'shortl_power',
                'mid_power',
                'models',
                'training_records',
                'prediction_records',
                'auto_prediction_tasks',
                'evaluation_metrics',
                'daily_metrics',
                'weather_connections',
                'weather_tasks',
                'weather_logs',
                'weather_data_records'
            ]

            for table in tables:
                try:
                    # 检查字段是否存在
                    cur.execute("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = %s AND column_name = 'farm_code'
                    """, (table,))
                    if not cur.fetchone():
                        # 添加字段
                        cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM'")
                        logger.info(f"为 {table} 添加 farm_code 字段")
                    else:
                        logger.info(f"{table}.farm_code 字段已存在")
                except Exception as e:
                    logger.warning(f"处理 {table} 时出错: {e}")

            conn.commit()
        return True
    except Exception as e:
        logger.error(f"添加farm_code字段失败: {e}")
        return False

def update_constraints(conn):
    """更新约束"""
    try:
        with conn.cursor() as cur:
            # 移除原有unique约束
            tables = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']
            for table in tables:
                try:
                    cur.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_timestamp_key")
                    logger.info(f"移除 {table} 原有unique约束")
                except Exception as e:
                    logger.warning(f"移除 {table} 约束时出错: {e}")

            # 添加复合unique约束
            for table in tables:
                try:
                    cur.execute(f"ALTER TABLE {table} ADD CONSTRAINT {table}_timestamp_farm_code_key UNIQUE (timestamp, farm_code)")
                    logger.info(f"为 {table} 添加复合unique约束")
                except Exception as e:
                    logger.warning(f"为 {table} 添加复合约束时出错: {e}")

            conn.commit()
        return True
    except Exception as e:
        logger.error(f"更新约束失败: {e}")
        return False

def verify_migration(conn):
    """验证迁移结果"""
    try:
        with conn.cursor() as cur:
            # 检查默认场站
            cur.execute("SELECT COUNT(*) FROM wind_farms WHERE farm_code = 'DEFAULT_FARM'")
            count = cur.fetchone()[0]
            logger.info(f"默认场站记录数: {count}")

            # 检查字段
            tables = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']
            for table in tables:
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name = %s AND column_name = 'farm_code'
                """, (table,))
                field_count = cur.fetchone()[0]
                logger.info(f"{table}.farm_code字段存在: {field_count > 0}")

            # 显示场站信息
            cur.execute("SELECT farm_code, farm_name, capacity FROM wind_farms")
            farms = cur.fetchall()
            logger.info("场站列表:")
            for farm in farms:
                logger.info(f"  {farm[0]} - {farm[1]} ({farm[2]}MW)")

        return True
    except Exception as e:
        logger.error(f"验证迁移失败: {e}")
        return False

def main():
    """主函数"""
    print("风电功率预测系统 - 多场站迁移")
    print("=" * 40)

    # 获取数据库连接
    conn = get_connection()
    if not conn:
        print("数据库连接失败")
        return False

    try:
        # 执行迁移步骤
        steps = [
            ("创建默认场站", create_default_farm),
            ("添加farm_code字段", add_farm_code_columns),
            ("更新约束", update_constraints),
            ("验证迁移", verify_migration)
        ]

        for step_name, step_func in steps:
            logger.info(f"\n{step_name}...")
            if not step_func(conn):
                logger.error(f"{step_name}失败")
                return False

        logger.info("\n迁移成功完成！")
        return True

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    if main():
        print("\n[OK] 多场站迁移完成！")
        print("\n下一步操作:")
        print("1. 测试数据库连接: python check_db.py")
        print("2. 运行功能测试: python db_models/test_multi_station.py")
    else:
        print("\n[ERROR] 迁移失败")
        sys.exit(1)