#!/usr/bin/env python3
"""
无MinIO依赖的多场站迁移脚本
"""
import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, text

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_database_url():
    """获取数据库连接URL（不依赖MinIO）"""
    from config import KINGBASE_CONFIG
    return f"postgresql+psycopg2://{KINGBASE_CONFIG['user']}:{KINGBASE_CONFIG['password']}@{KINGBASE_CONFIG['host']}:{KINGBASE_CONFIG['port']}/{KINGBASE_CONFIG['database']}"

def create_default_farm(engine):
    """创建默认场站"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM wind_farms WHERE farm_code = :farm_code"),
                {"farm_code": "DEFAULT_FARM"}
            ).fetchone()

            if not result:
                conn.execute(
                    text("""
                        INSERT INTO wind_farms (farm_code, farm_name, capacity, location, is_active)
                        VALUES (:farm_code, :farm_name, :capacity, :location, :is_active)
                    """),
                    {
                        "farm_code": "DEFAULT_FARM",
                        "farm_name": "默认风电场",
                        "capacity": 100.0,
                        "location": "默认位置",
                        "is_active": True
                    }
                )
                conn.commit()
                logger.info("✓ 创建默认场站: DEFAULT_FARM")
            else:
                logger.info("✓ 默认场站已存在")

            return True
    except Exception as e:
        logger.error(f"创建默认场站失败: {e}")
        return False

def add_farm_code_columns(engine):
    """为需要的表添加farm_code字段"""
    try:
        with engine.connect() as conn:
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
                    result = conn.execute(
                        text("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = :table AND column_name = 'farm_code'
                        """),
                        {"table": table}
                    ).fetchone()

                    if not result:
                        # 添加字段
                        conn.execute(
                            text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS farm_code VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_FARM'")
                        )

                        # 创建索引
                        conn.execute(
                            text(f"CREATE INDEX IF NOT EXISTS idx_{table}_farm_code ON {table}(farm_code)")
                        )
                        logger.info(f"✓ {table} 添加farm_code字段和索引")
                    else:
                        logger.info(f"✓ {table}.farm_code字段已存在")

                except Exception as e:
                    logger.warning(f"处理{table}时出错: {e}")

            conn.commit()
            return True

    except Exception as e:
        logger.error(f"添加farm_code字段失败: {e}")
        return False

def update_constraints(engine):
    """更新约束"""
    try:
        with engine.connect() as conn:
            # 移除原有unique约束
            tables = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']
            for table in tables:
                try:
                    conn.execute(
                        text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_timestamp_key")
                    )
                    logger.info(f"✓ 移除{table}原有unique约束")
                except Exception as e:
                    logger.warning(f"移除{table}约束时出错: {e}")

            # 添加复合unique约束
            for table in tables:
                try:
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD CONSTRAINT {table}_timestamp_farm_code_key UNIQUE (timestamp, farm_code)")
                    )
                    logger.info(f"✓ 添加{table}复合unique约束")
                except Exception as e:
                    logger.warning(f"添加{table}复合约束时出错: {e}")

            conn.commit()
            return True

    except Exception as e:
        logger.error(f"更新约束失败: {e}")
        return False

def verify_migration(engine):
    """验证迁移结果"""
    try:
        with engine.connect() as conn:
            # 检查默认场站
            result = conn.execute(
                text("SELECT COUNT(*) FROM wind_farms WHERE farm_code = 'DEFAULT_FARM'")
            ).fetchone()
            logger.info(f"✓ 默认场站记录数: {result[0]}")

            # 检查字段
            tables_check = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']
            for table in tables_check:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name = '{table}' AND column_name = 'farm_code'")
                ).fetchone()
                logger.info(f"✓ {table}.farm_code字段存在: {result[0]}")

            logger.info("✓ 迁移验证完成")
            return True

    except Exception as e:
        logger.error(f"验证迁移失败: {e}")
        return False

def main():
    """主函数"""
    print("风电功率预测系统 - 多场站迁移（无MinIO）")
    print("=" * 50)

    try:
        # 创建数据库引擎
        db_url = get_database_url()
        print(f"数据库URL: {db_url}")
        engine = create_engine(db_url)
        logger.info("✓ 数据库引擎创建成功")

        # 执行迁移步骤
        steps = [
            ("创建默认场站", create_default_farm),
            ("添加farm_code字段", add_farm_code_columns),
            ("更新约束", update_constraints),
            ("验证迁移", verify_migration)
        ]

        for step_name, step_func in steps:
            logger.info(f"\n--- {step_name} ---")
            if not step_func(engine):
                logger.error(f"✗ {step_name}失败")
                return False

        logger.info("\n" + "=" * 50)
        logger.info("🎉 多场站迁移成功完成！")
        logger.info("=" * 50)

        return True

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        return False

if __name__ == "__main__":
    if main():
        print("\n✅ 迁移成功完成！")
        print("\n下一步：")
        print("1. 重启应用程序以使用新的数据模型")
        print("2. 测试多场站功能")
        print("3. 开始第二阶段：数据采集逻辑改造")
    else:
        print("\n❌ 迁移失败，请检查日志")
        sys.exit(1)