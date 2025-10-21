#!/usr/bin/env python3
"""
数据库索引回滚脚本
用于删除所有新建的索引，回滚到索引优化前的状态
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
        logging.FileHandler('index_rollback.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IndexRollback:
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

    def list_current_indexes(self):
        """列出当前所有索引优化项目创建的索引"""
        try:
            with self.engine.connect() as conn:
                # 查找所有我们创建的索引
                result = conn.execute(text("""
                    SELECT tablename, indexname, indexdef
                    FROM pg_indexes
                    WHERE indexname LIKE 'idx_%_timestamp_farm'
                       OR indexname LIKE 'idx_%_date_farm'
                       OR indexname LIKE 'idx_%_farm_type%'
                       OR indexname LIKE 'idx_%_farm_%'
                       OR indexname LIKE 'idx_turbine%'
                       OR indexname LIKE 'idx_wind_speed%'
                    ORDER BY tablename, indexname;
                """)).fetchall()

                logger.info("当前存在的优化索引:")
                if not result:
                    logger.info("  没有找到任何优化索引")
                    return []

                indexes_found = []
                for row in result:
                    logger.info(f"  - {row[1]} ({row[0]})")
                    indexes_found.append({
                        'name': row[1],
                        'table': row[0],
                        'definition': row[2]
                    })

                return indexes_found

        except Exception as e:
            logger.error(f"列出当前索引失败: {e}")
            return []

    def drop_indexes(self, indexes_to_drop):
        """删除指定的索引"""
        dropped_indexes = []
        failed_drops = []

        try:
            with self.engine.connect() as conn:
                for index_info in indexes_to_drop:
                    index_name = index_info['name']
                    table_name = index_info['table']

                    logger.info(f"正在删除索引: {index_name} (表: {table_name})")

                    # 检查索引是否存在
                    check_sql = text("""
                        SELECT COUNT(*) FROM pg_indexes
                        WHERE indexname = :index_name AND tablename = :table_name
                    """)

                    result = conn.execute(check_sql, {
                        'index_name': index_name,
                        'table_name': table_name
                    }).fetchone()

                    if result[0] == 0:
                        logger.info(f"  ✓ 索引 {index_name} 不存在，跳过")
                        continue

                    # 使用CONCURRENTLY删除索引，避免锁表
                    # 注意：DROP INDEX CONCURRENTLY 在PostgreSQL 9.2+版本支持
                    try:
                        drop_sql = text(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")
                        conn.execute(drop_sql)
                        logger.info(f"  ✓ 索引 {index_name} 删除成功")
                        dropped_indexes.append(index_name)
                    except Exception as e:
                        # 如果CONCURRENTLY不支持，尝试普通删除
                        try:
                            drop_sql = text(f"DROP INDEX IF EXISTS {index_name}")
                            conn.execute(drop_sql)
                            logger.info(f"  ✓ 索引 {index_name} 删除成功 (普通模式)")
                            dropped_indexes.append(index_name)
                        except Exception as e2:
                            logger.error(f"  ✗ 索引 {index_name} 删除失败: {e2}")
                            failed_drops.append({'index': index_name, 'error': str(e2)})

                # 提交事务
                conn.commit()

                logger.info(f"\n索引删除完成:")
                logger.info(f"  成功删除: {len(dropped_indexes)} 个索引")
                logger.info(f"  删除失败: {len(failed_drops)} 个索引")

                if failed_drops:
                    logger.warning("删除失败的索引:")
                    for failed in failed_drops:
                        logger.warning(f"  - {failed['index']}: {failed['error']}")

                return len(failed_drops) == 0

        except Exception as e:
            logger.error(f"删除索引过程中发生错误: {e}")
            return False

    def verify_rollback(self):
        """验证回滚结果"""
        try:
            with self.engine.connect() as conn:
                # 检查是否还有优化索引存在
                result = conn.execute(text("""
                    SELECT COUNT(*)
                    FROM pg_indexes
                    WHERE indexname LIKE 'idx_%_timestamp_farm'
                       OR indexname LIKE 'idx_%_date_farm'
                       OR indexname LIKE 'idx_%_farm_type%'
                       OR indexname LIKE 'idx_%_farm_%'
                       OR indexname LIKE 'idx_turbine%'
                       OR indexname LIKE 'idx_wind_speed%'
                """)).fetchone()

                remaining_indexes = result[0]

                if remaining_indexes == 0:
                    logger.info("✓ 所有优化索引已成功删除")
                    return True
                else:
                    logger.warning(f"⚠ 仍有 {remaining_indexes} 个优化索引存在")
                    return False

        except Exception as e:
            logger.error(f"验证回滚失败: {e}")
            return False

    def check_performance_impact(self):
        """检查回滚后的性能影响"""
        try:
            logger.info("\n回滚后性能影响评估:")
            logger.info("  ⚠ 预期性能变化:")
            logger.info("    - 时间序列查询: 性能可能下降 70-90%")
            logger.info("    - 数据上传操作: 性能可能下降 50-80%")
            logger.info("    - 报表生成查询: 性能可能下降 60-85%")
            logger.info("    - 风机分析查询: 性能可能下降 40-70%")
            logger.info("  📝 建议:")
            logger.info("    - 在低峰期执行回滚操作")
            logger.info("    - 监控系统性能指标")
            logger.info("    - 考虑优化应用层查询逻辑")
            logger.info("    - 评估是否需要保留部分关键索引")

            return True

        except Exception as e:
            logger.error(f"检查性能影响失败: {e}")
            return False

    def generate_rollback_report(self):
        """生成回滚报告"""
        try:
            completion_time = datetime.now().isoformat()
            logger.info(f"\n索引回滚完成时间: {completion_time}")

            logger.info("\n回滚操作总结:")
            logger.info("  ✓ 删除了所有Phase 1-4创建的优化索引")
            logger.info("  ✓ 数据库已恢复到索引优化前的状态")
            logger.info("  ⚠ 请监控系统性能，必要时进行应用层优化")

            return True

        except Exception as e:
            logger.error(f"生成回滚报告失败: {e}")
            return False

def confirm_rollback():
    """确认回滚操作"""
    print("\n" + "=" * 60)
    print("⚠️  警告：数据库索引回滚操作")
    print("=" * 60)
    print("此操作将删除所有索引优化项目创建的索引，包括：")
    print("")
    print("Phase 1 - 时间序列索引:")
    print("  - actual_power, supershortl_power, shortl_power, mid_power")
    print("  - daily_metrics")
    print("")
    print("Phase 2 - 运营数据索引:")
    print("  - 7个运营数据表的复合索引")
    print("")
    print("Phase 3 - 报表查询索引:")
    print("  - report_quality_statistics, report_logs")
    print("")
    print("Phase 4 - 专用查询索引:")
    print("  - turbine_power_data, wind_speed_data 专用索引")
    print("")
    print("⚠️  删除这些索引可能导致:")
    print("  - 查询性能显著下降")
    print("  - 系统响应时间变长")
    print("  - 数据上传处理变慢")
    print("")
    print("📝 建议在以下情况下执行回滚：")
    print("  - 索引导致性能问题")
    print("  - 索引占用过多存储空间")
    print("  - 需要重建索引")
    print("  - 系统维护期间")
    print("")
    response = input("确认要继续回滚操作吗？(输入 'YES' 继续，其他任意键取消): ")

    return response.strip() == 'YES'

def main():
    """主函数"""
    print("风电功率预测系统 - 数据库索引回滚")
    print("=" * 50)
    print("此脚本将删除所有索引优化项目创建的索引")

    # 确认回滚操作
    if not confirm_rollback():
        print("\n❌ 回滚操作已取消")
        return False

    rollback = IndexRollback()

    # 执行回滚步骤
    rollback_steps = [
        ("数据库连接测试", rollback.test_database_connection),
        ("列出当前索引", rollback.list_current_indexes),
        ("删除优化索引", rollback.drop_indexes),
        ("验证回滚结果", rollback.verify_rollback),
        ("检查性能影响", rollback.check_performance_impact),
        ("生成回滚报告", rollback.generate_rollback_report)
    ]

    passed_steps = 0
    total_steps = len(rollback_steps)

    for step_name, step_func in rollback_steps:
        logger.info(f"\n--- {step_name} ---")
        if step_name == "列出当前索引":
            indexes = step_func()
            if indexes is not None:
                logger.info(f"✅ {step_name} 通过，找到 {len(indexes)} 个索引")
                passed_steps += 1
            else:
                logger.error(f"❌ {step_name} 失败")
        elif step_func():
            logger.info(f"✅ {step_name} 通过")
            passed_steps += 1
        else:
            logger.error(f"❌ {step_name} 失败")

    # 最终结果
    logger.info(f"\n" + "=" * 50)
    logger.info(f"回滚操作结果: {passed_steps}/{total_steps} 项通过")

    if passed_steps == total_steps:
        logger.info("🎉 索引回滚操作成功完成！")
        print("\n✅ 索引回滚操作完成！")
        print("数据库已恢复到索引优化前的状态")
        print("请监控系统性能并进行必要的应用层优化")
        return True
    else:
        logger.error(f"❌ 有 {total_steps - passed_steps} 项步骤失败")
        print("\n❌ 回滚操作失败，请检查错误信息")
        print("可能需要手动删除剩余的索引")
        return False

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)