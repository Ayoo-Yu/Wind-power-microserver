#!/usr/bin/env python3
"""
数据库索引优化迁移脚本 - Phase 1: 高优先级时间序列索引
为多场站查询优化关键的时间序列表
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接使用数据库连接配置，避免依赖问题
def get_database_url():
    """获取数据库连接URL"""
    import os
    # 导入KingBase方言
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        import kingbase_dialect
    except:
        pass

    # 使用项目配置
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '54321')  # KingBase默认端口
    db_name = os.getenv('DB_NAME', 'windpower')
    db_user = os.getenv('DB_USER', 'system')
    db_password = os.getenv('DB_PASSWORD', '12345678ab')

    return f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('index_migration_phase1.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IndexMigrationPhase1:
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
        """检查现有索引"""
        try:
            with self.engine.connect() as conn:
                # 检查PostgreSQL索引
                if 'postgresql' in get_database_url():
                    result = conn.execute(text("""
                        SELECT indexname, tablename
                        FROM pg_indexes
                        WHERE tablename IN (
                            'actual_power', 'supershortl_power', 'shortl_power',
                            'mid_power', 'daily_metrics'
                        )
                        ORDER BY tablename, indexname;
                    """)).fetchall()
                # 检查KingBase索引 (语法类似PostgreSQL)
                elif 'kingbase' in get_database_url():
                    result = conn.execute(text("""
                        SELECT indexname, tablename
                        FROM pg_indexes
                        WHERE tablename IN (
                            'actual_power', 'supershortl_power', 'shortl_power',
                            'mid_power', 'daily_metrics'
                        )
                        ORDER BY tablename, indexname;
                    """)).fetchall()
                else:
                    logger.warning("不支持的数据库类型，跳过索引检查")
                    return True

                logger.info("现有索引:")
                for row in result:
                    logger.info(f"  - {row[1]}.{row[0]}")

                return True

        except Exception as e:
            logger.error(f"检查现有索引失败: {e}")
            return False

    def create_phase1_indexes(self):
        """创建Phase 1的高优先级时间序列索引"""
        indexes_to_create = [
            {
                'name': 'idx_actual_power_timestamp_farm',
                'table': 'actual_power',
                'columns': 'timestamp, farm_code',
                'description': '实际功率表时间戳+场站复合索引'
            },
            {
                'name': 'idx_supershortl_power_timestamp_farm',
                'table': 'supershortl_power',
                'columns': 'timestamp, farm_code',
                'description': '超短期预测表时间戳+场站复合索引'
            },
            {
                'name': 'idx_shortl_power_timestamp_farm',
                'table': 'shortl_power',
                'columns': 'timestamp, farm_code',
                'description': '短期预测表时间戳+场站复合索引'
            },
            {
                'name': 'idx_mid_power_timestamp_farm',
                'table': 'mid_power',
                'columns': 'timestamp, farm_code',
                'description': '中期预测表时间戳+场站复合索引'
            },
            {
                'name': 'idx_daily_metrics_date_farm',
                'table': 'daily_metrics',
                'columns': 'date, farm_code',
                'description': '每日指标表日期+场站复合索引'
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

                logger.info(f"\nPhase 1 索引创建完成:")
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
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT tablename, indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename IN (
                        'actual_power', 'supershortl_power', 'shortl_power',
                        'mid_power', 'daily_metrics'
                    )
                    AND indexname LIKE '%_timestamp_farm' OR indexname LIKE '%_date_farm'
                    ORDER BY tablename, indexname;
                """)).fetchall()

                logger.info("\n验证创建的索引:")
                for row in result:
                    logger.info(f"  ✓ {row[0]}.{row[1]}")
                    logger.info(f"    定义: {row[2]}")

                return len(result) > 0

        except Exception as e:
            logger.error(f"验证索引失败: {e}")
            return False

    def generate_report(self):
        """生成迁移报告"""
        try:
            with self.engine.connect() as conn:
                # 获取索引统计信息
                stats_sql = text("""
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                        idx_scan as index_scans,
                        idx_tup_read as tuples_read,
                        idx_tup_fetch as tuples_fetched
                    FROM pg_stat_user_indexes
                    WHERE tablename IN (
                        'actual_power', 'supershortl_power', 'shortl_power',
                        'mid_power', 'daily_metrics'
                    )
                    AND indexname LIKE '%_timestamp_farm' OR indexname LIKE '%_date_farm'
                    ORDER BY tablename, indexname;
                """)

                try:
                    stats = conn.execute(stats_sql).fetchall()

                    logger.info("\n索引统计信息:")
                    for stat in stats:
                        logger.info(f"  {stat[1]}.{stat[2]}:")
                        logger.info(f"    大小: {stat[3]}")
                        logger.info(f"    扫描次数: {stat[4]}")
                        logger.info(f"    读取元组: {stat[5]}")
                        logger.info(f"    获取元组: {stat[6]}")
                except:
                    logger.info("无法获取索引统计信息（可能需要更长时间的统计收集）")

                # 记录迁移完成时间
                completion_time = datetime.now().isoformat()
                logger.info(f"\nPhase 1 迁移完成时间: {completion_time}")

                return True

        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return False

def main():
    """主函数"""
    print("风电功率预测系统 - 数据库索引优化 Phase 1")
    print("=" * 50)
    print("Phase 1: 高优先级时间序列索引")
    print("目标: 为功率预测数据表添加时间戳+场站复合索引")

    migrator = IndexMigrationPhase1()

    # 执行迁移步骤
    migration_steps = [
        ("数据库连接测试", migrator.test_database_connection),
        ("检查现有索引", migrator.check_existing_indexes),
        ("创建Phase 1索引", migrator.create_phase1_indexes),
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
    logger.info(f"Phase 1 迁移结果: {passed_steps}/{total_steps} 项通过")

    if passed_steps == total_steps:
        logger.info("🎉 Phase 1 索引迁移成功完成！")
        print("\n✅ Phase 1 索引优化完成！")
        print("下一步可以执行 Phase 2: 运营数据表索引")
        return True
    else:
        logger.error(f"❌ 有 {total_steps - passed_steps} 项步骤失败")
        print("\n❌ Phase 1 迁移失败，请检查错误信息")
        return False

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)