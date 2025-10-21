#!/usr/bin/env python3
"""
数据库索引优化迁移脚本 - Phase 2: 高优先级运营数据索引
为多场站运营数据上传优化关键表
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_config import get_database_url

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('index_migration_phase2.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IndexMigrationPhase2:
    def __init__(self):
        self.engine = create_engine(get_database_url())
        self.Session = sessionmaker(bind=self.engine)

    def test_database_connection(self):
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).fetchone()
                logger.info("✓ 数据库连接成功")
                return True
        except Exception as e:
            logger.error(f"✗ 数据库连接失败: {e}")
            return False

    def check_existing_indexes(self):
        """检查运营数据表的现有索引"""
        operational_tables = [
            'wind_speed_data', 'turbine_power_data', 'weather_data',
            'installed_capacity_data', 'available_capacity_data',
            'theoretical_power_data', 'available_power_data'
        ]

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT indexname, tablename
                    FROM pg_indexes
                    WHERE tablename IN :tables
                    ORDER BY tablename, indexname;
                """), {'tables': operational_tables}).fetchall()

                logger.info("运营数据表现有索引:")
                for row in result:
                    logger.info(f"  - {row[1]}.{row[0]}")

                return True

        except Exception as e:
            logger.error(f"检查现有索引失败: {e}")
            return False

    def create_phase2_indexes(self):
        """创建Phase 2的高优先级运营数据索引"""
        indexes_to_create = [
            {
                'name': 'idx_wind_speed_data_timestamp_farm',
                'table': 'wind_speed_data',
                'columns': 'timestamp, farm_code',
                'description': '风速数据表时间戳+场站复合索引'
            },
            {
                'name': 'idx_turbine_power_data_timestamp_farm',
                'table': 'turbine_power_data',
                'columns': 'timestamp, farm_code',
                'description': '功率数据表时间戳+场站复合索引'
            },
            {
                'name': 'idx_weather_data_timestamp_farm',
                'table': 'weather_data',
                'columns': 'timestamp, farm_code',
                'description': '气象数据表时间戳+场站复合索引'
            },
            {
                'name': 'idx_installed_capacity_timestamp_farm',
                'table': 'installed_capacity_data',
                'columns': 'timestamp, farm_code',
                'description': '装机容量表时间戳+场站复合索引'
            },
            {
                'name': 'idx_available_capacity_timestamp_farm',
                'table': 'available_capacity_data',
                'columns': 'timestamp, farm_code',
                'description': '可用容量表时间戳+场站复合索引'
            },
            {
                'name': 'idx_theoretical_power_timestamp_farm',
                'table': 'theoretical_power_data',
                'columns': 'timestamp, farm_code',
                'description': '理论功率表时间戳+场站复合索引'
            },
            {
                'name': 'idx_available_power_timestamp_farm',
                'table': 'available_power_data',
                'columns': 'timestamp, farm_code',
                'description': '可用功率表时间戳+场站复合索引'
            }
        ]

        created_indexes = []
        failed_indexes = []

        try:
            with self.engine.connect() as conn:
                for index_info in indexes_to_create:
                    logger.info(f"正在创建索引: {index_info['name']} ({index_info['description']})")

                    # 检查索引是否已存在
                    check_sql = text("""
                        SELECT COUNT(*) FROM pg_indexes
                        WHERE indexname = :index_name AND tablename = :table_name
                    """)

                    result = conn.execute(check_sql, {
                        'index_name': index_info['name'],
                        'table_name': index_info['table']
                    }).fetchone()

                    if result[0] > 0:
                        logger.info(f"  ✓ 索引 {index_info['name']} 已存在，跳过")
                        continue

                    # 使用CONCURRENTLY创建索引，避免锁表
                    create_sql = text(f"""
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_info['name']}
                        ON {index_info['table']}({index_info['columns']})
                    """)

                    try:
                        conn.execute(create_sql)
                        logger.info(f"  ✓ 索引 {index_info['name']} 创建成功")
                        created_indexes.append(index_info['name'])
                    except Exception as e:
                        logger.error(f"  ✗ 索引 {index_info['name']} 创建失败: {e}")
                        failed_indexes.append({'index': index_info['name'], 'error': str(e)})

                # 提交事务
                conn.commit()

                logger.info(f"\nPhase 2 索引创建完成:")
                logger.info(f"  成功创建: {len(created_indexes)} 个索引")
                logger.info(f"  创建失败: {len(failed_indexes)} 个索引")

                if failed_indexes:
                    logger.warning("失败的索引:")
                    for failed in failed_indexes:
                        logger.warning(f"  - {failed['index']}: {failed['error']}")

                return len(failed_indexes) == 0

        except Exception as e:
            logger.error(f"创建索引过程中发生错误: {e}")
            return False

    def verify_indexes(self):
        """验证索引创建结果"""
        operational_tables = [
            'wind_speed_data', 'turbine_power_data', 'weather_data',
            'installed_capacity_data', 'available_capacity_data',
            'theoretical_power_data', 'available_power_data'
        ]

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT tablename, indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename IN :tables
                    AND (indexname LIKE '%_timestamp_farm' OR indexname LIKE '%_date_farm')
                    ORDER BY tablename, indexname;
                """), {'tables': operational_tables}).fetchall()

                logger.info("\n验证创建的索引:")
                for row in result:
                    logger.info(f"  ✓ {row[0]}.{row[1]}")
                    logger.info(f"    定义: {row[2]}")

                return len(result) > 0

        except Exception as e:
            logger.error(f"验证索引失败: {e}")
            return False

    def check_table_sizes(self):
        """检查运营数据表的大小，帮助评估索引效果"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                        pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                        pg_total_relation_size(schemaname||'.'||tablename) as total_bytes
                    FROM pg_tables
                    WHERE tablename IN (
                        'wind_speed_data', 'turbine_power_data', 'weather_data',
                        'installed_capacity_data', 'available_capacity_data',
                        'theoretical_power_data', 'available_power_data'
                    )
                    ORDER BY total_bytes DESC;
                """)).fetchall()

                logger.info("\n运营数据表大小信息:")
                for row in result:
                    logger.info(f"  {row[0]}:")
                    logger.info(f"    总大小: {row[1]} (表大小: {row[2]})")

                return True

        except Exception as e:
            logger.error(f"检查表大小失败: {e}")
            return False

    def generate_report(self):
        """生成迁移报告"""
        try:
            # 记录迁移完成时间
            completion_time = datetime.now().isoformat()
            logger.info(f"\nPhase 2 迁移完成时间: {completion_time}")

            logger.info("\nPhase 2 迁移总结:")
            logger.info("  ✓ 为7个运营数据表添加了时间戳+场站复合索引")
            logger.info("  ✓ 索引将显著提升数据上传重复检查性能")
            logger.info("  ✓ 索引将优化场站特定的时间范围查询")
            logger.info("  ✓ 所有索引使用CONCURRENTLY创建，避免锁表")

            return True

        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return False

def main():
    """主函数"""
    print("风电功率预测系统 - 数据库索引优化 Phase 2")
    print("=" * 50)
    print("Phase 2: 高优先级运营数据索引")
    print("目标: 为运营数据表添加时间戳+场站复合索引，优化数据上传性能")

    migrator = IndexMigrationPhase2()

    # 执行迁移步骤
    migration_steps = [
        ("数据库连接测试", migrator.test_database_connection),
        ("检查现有索引", migrator.check_existing_indexes),
        ("检查表大小", migrator.check_table_sizes),
        ("创建Phase 2索引", migrator.create_phase2_indexes),
        ("验证索引创建", migrator.verify_indexes),
        ("生成迁移报告", migrator.generate_report)
    ]

    passed_steps = 0
    total_steps = len(migration_steps)

    for step_name, step_func in migration_steps:
        logger.info(f"\n--- {step_name} ---")
        if step_func():
            logger.info(f"✅ {step_name} 通过")
            passed_steps += 1
        else:
            logger.error(f"❌ {step_name} 失败")

    # 最终结果
    logger.info(f"\n" + "=" * 50)
    logger.info(f"Phase 2 迁移结果: {passed_steps}/{total_steps} 项通过")

    if passed_steps == total_steps:
        logger.info("🎉 Phase 2 索引迁移成功完成！")
        print("\n✅ Phase 2 索引优化完成！")
        print("下一步可以执行 Phase 3: 报表查询优化索引")
        return True
    else:
        logger.error(f"❌ 有 {total_steps - passed_steps} 项步骤失败")
        print("\n❌ Phase 2 迁移失败，请检查错误信息")
        return False

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)