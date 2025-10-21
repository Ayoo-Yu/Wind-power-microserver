#!/usr/bin/env python3
"""
简化的多场站迁移脚本
"""
import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, text

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_config import get_database_url

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_default_farm(engine):
    """创建默认场站"""
    try:
        with engine.connect() as conn:
            # 检查是否已存在默认场站
            result = conn.execute(
                text("SELECT * FROM wind_farms WHERE farm_code = :farm_code"),
                {"farm_code": "DEFAULT_FARM"}
            ).fetchone()

            if not result:
                # 创建默认场站
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
                logger.info("✓ 默认场站已存在: DEFAULT_FARM")

            return True
    except Exception as e:
        logger.error(f"创建默认场站失败: {e}")
        return False

def add_farm_code_columns(engine):
    """为需要的表添加farm_code字段"""
    try:
        with engine.connect() as conn:
            # 需要添加farm_code字段的表
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
                    # 检查字段是否已存在
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
                        logger.info(f"✓ 为 {table} 添加 farm_code 字段")

                        # 创建索引
                        conn.execute(
                            text(f"CREATE INDEX IF NOT EXISTS idx_{table}_farm_code ON {table}(farm_code)")
                        )
                        logger.info(f"✓ 为 {table} 创建 farm_code 索引")
                    else:
                        logger.info(f"✓ {table}.farm_code 字段已存在")

                except Exception as e:
                    logger.warning(f"处理表 {table} 时出错: {e}")

            conn.commit()
            return True

    except Exception as e:
        logger.error(f"添加farm_code字段失败: {e}")
        return False

def remove_unique_constraints(engine):
    """移除原有的unique约束"""
    try:
        with engine.connect() as conn:
            # 需要移除unique约束的表
            tables = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']

            for table in tables:
                try:
                    # 移除原有的unique约束
                    conn.execute(
                        text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_timestamp_key")
                    )
                    logger.info(f"✓ 移除 {table} 的原有unique约束")
                except Exception as e:
                    logger.warning(f"移除 {table} 约束时出错: {e}")

            conn.commit()
            return True

    except Exception as e:
        logger.error(f"移除unique约束失败: {e}")
        return False

def add_composite_constraints(engine):
    """添加复合唯一约束"""
    try:
        with engine.connect() as conn:
            # 需要添加复合唯一约束的表
            tables = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']

            for table in tables:
                try:
                    # 添加复合唯一约束
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD CONSTRAINT {table}_timestamp_farm_code_key UNIQUE (timestamp, farm_code)")
                    )
                    logger.info(f"✓ 为 {table} 添加复合唯一约束")
                except Exception as e:
                    logger.warning(f"为 {table} 添加复合约束时出错: {e}")

            conn.commit()
            return True

    except Exception as e:
        logger.error(f"添加复合唯一约束失败: {e}")
        return False

def verify_migration(engine):
    """验证迁移结果"""
    try:
        with engine.connect() as conn:
            # 检查默认场站
            result = conn.execute(
                text("SELECT * FROM wind_farms WHERE farm_code = 'DEFAULT_FARM'")
            ).fetchone()

            if result:
                logger.info(f"✓ 默认场站存在: {result.farm_name}")
            else:
                logger.warning("✗ 默认场站不存在")

            # 检查字段数量
            tables_to_check = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']
            for table in tables_to_check:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name = '{table}' AND column_name = 'farm_code'")
                ).fetchone()

                if result[0] > 0:
                    logger.info(f"✓ {table}.farm_code 字段存在")
                else:
                    logger.warning(f"✗ {table}.farm_code 字段不存在")

            return True

    except Exception as e:
        logger.error(f"验证迁移失败: {e}")
        return False

def main():
    """主函数"""
    print("风电功率预测系统 - 简化多场站迁移")
    print("=" * 50)

    try:
        # 创建数据库引擎
        engine = create_engine(get_database_url())
        logger.info("✓ 数据库引擎创建成功")

        # 执行迁移步骤
        steps = [
            ("创建默认场站", create_default_farm),
            ("添加farm_code字段", add_farm_code_columns),
            ("移除原有约束", remove_unique_constraints),
            ("添加复合约束", add_composite_constraints),
            ("验证迁移结果", verify_migration)
        ]

        for step_name, step_func in steps:
            logger.info(f"\n--- {step_name} ---")
            if step_func(engine):
                logger.info(f"✓ {step_name} 成功")
            else:
                logger.error(f"✗ {step_name} 失败")
                return False

        logger.info("\n" + "=" * 50)
        logger.info("🎉 多场站迁移完成！")
        logger.info("=" * 50)

        return True

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        return False

if __name__ == "__main__":
    if main():
        print("\n迁移成功完成！")
        print("下一步：运行功能测试")
        print("命令: python db_models/test_multi_station.py")
    else:
        print("\n迁移失败，请检查日志")
        sys.exit(1)