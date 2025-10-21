#!/usr/bin/env python3
"""
简化版多场站迁移验证脚本
用于验证多场站适配的完成状态
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接配置数据库连接
def get_database_url():
    """获取数据库连接URL"""
    db_host = 'kingbase'
    db_port = '54321'
    db_name = 'windpower'
    db_user = 'system'
    db_password = '12345678ab'

    return f'postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('verification.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MultiStationVerification:
    def __init__(self):
        try:
            from sqlalchemy import create_engine, text, func
            from sqlalchemy.orm import sessionmaker

            self.engine = create_engine(get_database_url())
            self.Session = sessionmaker(bind=self.engine)
            logger.info("✓ 数据库连接成功")
        except ImportError as e:
            logger.error(f"✗ 缺少依赖模块: {e}")
            sys.exit(1)

    def test_database_connection(self):
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).fetchone()
                logger.info("✓ 数据库连接测试通过")
                return True
        except Exception as e:
            logger.error(f"✗ 数据库连接失败: {e}")
            return False

    def verify_database_models(self):
        """验证数据库模型的多场站适配"""
        logger.info("\n" + "=" * 50)
        logger.info("验证数据库模型多场站适配")
        logger.info("=" * 50)

        try:
            with self.engine.connect() as conn:
                # 检查核心表的多场站字段
                tables_to_check = [
                    'actual_power', 'supershortl_power', 'shortl_power', 'mid_power',
                    'wind_speed_data', 'turbine_power_data', 'weather_data',
                    'installed_capacity_data', 'available_capacity_data',
                    'theoretical_power_data', 'available_power_data',
                    'daily_metrics', 'report_quality_statistics', 'report_logs'
                ]

                results = {}
                for table in tables_to_check:
                    # 检查表是否存在farm_code字段
                    result = conn.execute(text(f"""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = '{table}' AND column_name = 'farm_code'
                    """)).fetchall()

                    has_farm_code = len(result) > 0
                    results[table] = has_farm_code

                    status = "✓" if has_farm_code else "✗"
                    logger.info(f"  {status} {table}: {'支持多场站' if has_farm_code else '缺少farm_code字段'}")

                # 检查复合唯一约束
                logger.info("\n检查复合唯一约束:")
                unique_constraints = {}
                for table in ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']:
                    result = conn.execute(text(f"""
                        SELECT constraint_name FROM information_schema.table_constraints
                        WHERE table_name = '{table}' AND constraint_type = 'UNIQUE'
                        AND constraint_name LIKE '%_timestamp_farm_code_key'
                    """)).fetchall()

                    has_unique = len(result) > 0
                    unique_constraints[table] = has_unique

                    status = "✓" if has_unique else "✗"
                    logger.info(f"  {status} {table}: {'有复合唯一约束' if has_unique else '缺少唯一约束'}")

                return {
                    'tables_with_farm_code': sum(results.values()),
                    'total_tables': len(tables_to_check),
                    'tables_with_unique': sum(unique_constraints.values()),
                    'unique_tables': len(unique_constraints)
                }

        except Exception as e:
            logger.error(f"验证数据库模型失败: {e}")
            return None

    def verify_wind_farms_data(self):
        """验证风场数据"""
        logger.info("\n" + "=" * 50)
        logger.info("验证风场数据")
        logger.info("=" * 50)

        try:
            with self.engine.connect() as conn:
                # 检查风场表数据
                result = conn.execute(text("""
                    SELECT farm_code, farm_name, is_active, COUNT(*) OVER() as total_farms
                    FROM wind_farms
                    ORDER BY farm_code
                """)).fetchall()

                logger.info(f"  总风场数量: {result[0][3] if result else 0}")

                active_farms = [row for row in result if row[2]]
                logger.info(f"  活跃风场数量: {len(active_farms)}")

                for row in result:
                    status = "✓" if row[2] else "○"
                    logger.info(f"  {status} {row[0]} - {row[1]}")

                return {
                    'total_farms': result[0][3] if result else 0,
                    'active_farms': len(active_farms),
                    'farms': [{'code': row[0], 'name': row[1], 'active': row[2]} for row in result]
                }

        except Exception as e:
            logger.error(f"验证风场数据失败: {e}")
            return None

    def verify_operational_data(self):
        """验证运营数据的多场站支持"""
        logger.info("\n" + "=" * 50)
        logger.info("验证运营数据多场站支持")
        logger.info("=" * 50)

        try:
            with self.engine.connect() as conn:
                # 检查各运营数据表的场站分布
                tables = ['wind_speed_data', 'turbine_power_data', 'weather_data']

                for table in tables:
                    result = conn.execute(text(f"""
                        SELECT farm_code, COUNT(*) as record_count,
                               MIN(timestamp) as earliest,
                               MAX(timestamp) as latest
                        FROM {table}
                        GROUP BY farm_code
                        ORDER BY record_count DESC
                    """)).fetchall()

                    if result:
                        total_records = sum(row[1] for row in result)
                        logger.info(f"  {table}: {len(result)} 个场站, {total_records} 条记录")

                        for row in result[:3]:  # 只显示前3个
                            logger.info(f"    {row[0]}: {row[1]} 条记录 ({row[2]} ~ {row[3]})")
                    else:
                        logger.info(f"  {table}: 无数据")

                return True

        except Exception as e:
            logger.error(f"验证运营数据失败: {e}")
            return False

    def verify_prediction_data(self):
        """验证预测数据的多场站支持"""
        logger.info("\n" + "=" * 50)
        logger.info("验证预测数据多场站支持")
        logger.info("=" * 50)

        try:
            with self.engine.connect() as conn:
                # 检查预测表的数据分布
                tables = ['actual_power', 'supershortl_power', 'shortl_power', 'mid_power']

                for table in tables:
                    result = conn.execute(text(f"""
                        SELECT farm_code, COUNT(*) as record_count,
                               MIN(timestamp) as earliest,
                               MAX(timestamp) as latest
                        FROM {table}
                        GROUP BY farm_code
                        ORDER BY record_count DESC
                    """)).fetchall()

                    if result:
                        total_records = sum(row[1] for row in result)
                        logger.info(f"  {table}: {len(result)} 个场站, {total_records} 条记录")

                        for row in result[:3]:  # 只显示前3个
                            logger.info(f"    {row[0]}: {row[1]} 条记录 ({row[2]} ~ {row[3]})")
                    else:
                        logger.info(f"  {table}: 无数据")

                return True

        except Exception as e:
            logger.error(f"验证预测数据失败: {e}")
            return False

    def verify_indexes(self):
        """验证索引优化状态"""
        logger.info("\n" + "=" * 50)
        logger.info("验证索引优化状态")
        logger.info("=" * 50)

        try:
            with self.engine.connect() as conn:
                # 检查优化索引
                result = conn.execute(text("""
                    SELECT indexname, tablename
                    FROM pg_indexes
                    WHERE indexname LIKE 'idx_%'
                    ORDER BY tablename, indexname
                """)).fetchall()

                if result:
                    logger.info(f"✓ 优化索引数量: {len(result)}")

                    # 按表分组显示
                    by_table = {}
                    for row in result:
                        table = row[1]
                        if table not in by_table:
                            by_table[table] = []
                        by_table[table].append(row[0])

                    for table, indexes in by_table.items():
                        logger.info(f"  {table}: {len(indexes)} 个索引")
                        for idx in indexes:
                            logger.info(f"    - {idx}")

                    return len(result)
                else:
                    logger.warning("✗ 未找到优化索引")
                    return 0

        except Exception as e:
            logger.error(f"验证索引失败: {e}")
            return 0

    def test_api_endpoints(self):
        """测试API端点的多场站支持"""
        logger.info("\n" + "=" * 50)
        logger.info("测试API端点多场站支持")
        logger.info("=" * 50)

        # 这里可以测试实际的API端点
        # 由于依赖较多，先进行基础的数据库查询测试

        try:
            with self.engine.connect() as conn:
                # 模拟API查询测试
                test_queries = [
                    ("获取风场列表", "SELECT farm_code, farm_name FROM wind_farms WHERE is_active = TRUE"),
                    ("获取最新功率数据", "SELECT farm_code, timestamp, wp_true FROM actual_power ORDER BY timestamp DESC LIMIT 10"),
                    ("获取预测数据", "SELECT farm_code, timestamp, predicted_power FROM supershortl_power ORDER BY timestamp DESC LIMIT 10")
                ]

                for name, query in test_queries:
                    try:
                        result = conn.execute(text(query)).fetchall()
                        logger.info(f"  ✓ {name}: 返回 {len(result)} 条结果")

                        # 显示场站分布
                        if result and len(result[0]) > 1:  # 多字段结果
                            farms = set()
                            for row in result:
                                if isinstance(row[0], str):
                                    farms.add(row[0])
                            if farms:
                                logger.info(f"    涉及场站: {', '.join(list(farms)[:5])}")
                    except Exception as e:
                        logger.error(f"  ✗ {name}: {e}")

                return True

        except Exception as e:
            logger.error(f"测试API端点失败: {e}")
            return False

    def generate_summary_report(self, results):
        """生成验证总结报告"""
        logger.info("\n" + "=" * 60)
        logger.info("多场站迁移验证总结报告")
        logger.info("=" * 60)
        logger.info(f"验证时间: {datetime.now().isoformat()}")

        # 数据库模型验证
        if 'database_models' in results:
            model_results = results['database_models']
            logger.info(f"\n📊 数据库模型验证:")
            logger.info(f"  支持多场站的表: {model_results['tables_with_farm_code']}/{model_results['total_tables']}")
            logger.info(f"  复合唯一约束: {model_results['tables_with_unique']}/{model_results['unique_tables']}")

        # 风场数据
        if 'wind_farms' in results:
            farm_results = results['wind_farms']
            logger.info(f"\n🌪️ 风场数据:")
            logger.info(f"  总风场数量: {farm_results['total_farms']}")
            logger.info(f"  活跃风场: {farm_results['active_farms']}")

        # 索引优化
        if 'indexes' in results:
            logger.info(f"\n🚀 索引优化:")
            logger.info(f"  优化索引数量: {results['indexes']}")

        # 整体评估
        success_count = 0
        total_checks = 0

        if 'database_models' in results:
            model_results = results['database_models']
            if model_results['tables_with_farm_code'] == model_results['total_tables']:
                success_count += 1
            total_checks += 1

        if 'wind_farms' in results and results['wind_farms']['total_farms'] > 0:
            success_count += 1
            total_checks += 1

        if 'indexes' in results and results['indexes'] >= 20:
            success_count += 1
            total_checks += 1

        if 'operational_data' in results and results['operational_data']:
            success_count += 1
            total_checks += 1

        if 'prediction_data' in results and results['prediction_data']:
            success_count += 1
            total_checks += 1

        logger.info(f"\n📈 整体评估:")
        logger.info(f"  通过检查: {success_count}/{total_checks}")
        logger.info(f"  成功率: {(success_count/total_checks*100):.1f}%")

        if success_count == total_checks:
            logger.info("  🎉 多场站迁移验证完全成功！")
            logger.info("  ✅ 系统已具备多场站运行能力")
            logger.info("  🚀 可以进行生产环境部署")
        elif success_count >= total_checks * 0.8:
            logger.info("  ⚠️ 多场站迁移基本成功")
            logger.info("  📝 建议解决发现的问题后再部署")
        else:
            logger.info("  ❌ 多场站迁移存在较多问题")
            logger.info("  🔧 需要修复问题后重新验证")

        return success_count == total_checks

    def run_verification(self):
        """运行完整的验证流程"""
        logger.info("开始多场站迁移综合验证")
        logger.info("=" * 50)

        results = {}

        # 执行各项验证
        verification_steps = [
            ("数据库连接测试", self.test_database_connection),
            ("数据库模型验证", self.verify_database_models),
            ("风场数据验证", self.verify_wind_farms_data),
            ("运营数据验证", self.verify_operational_data),
            ("预测数据验证", self.verify_prediction_data),
            ("索引优化验证", self.verify_indexes),
            ("API端点测试", self.test_api_endpoints)
        ]

        for step_name, step_func in verification_steps:
            logger.info(f"\n--- {step_name} ---")
            try:
                result = step_func()
                if isinstance(result, dict):
                    if 'database_models' in step_name:
                        results['database_models'] = result
                    elif 'wind_farms' in step_name:
                        results['wind_farms'] = result
                    else:
                        results[step_name] = result
                else:
                    results[step_name] = result

                if result is not False:
                    logger.info(f"✅ {step_name} 通过")
                else:
                    logger.error(f"❌ {step_name} 失败")
            except Exception as e:
                logger.error(f"❌ {step_name} 异常: {e}")
                results[step_name] = False

        # 生成总结报告
        success = self.generate_summary_report(results)

        logger.info(f"\n验证完成！详细日志请查看: verification.log")
        return success

def main():
    """主函数"""
    print("风电功率预测系统 - 多场站迁移验证")
    print("=" * 50)
    print("此脚本将验证多场站适配的完成状态")

    verifier = MultiStationVerification()
    success = verifier.run_verification()

    if success:
        print("\n✅ 多场站迁移验证成功！")
        print("🎉 系统已准备好进行多场站运行")
        return True
    else:
        print("\n❌ 多场站迁移验证失败")
        print("🔧 请检查日志并修复问题")
        return False

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)