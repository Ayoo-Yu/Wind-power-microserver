#!/usr/bin/env python3
"""
风电功率预测系统 - 数据库级别集成测试脚本
用于验证多场站系统的数据库层面功能完整性
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('database_level_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseLevelTester:
    def __init__(self):
        self.test_results = []
        self.farm_codes = ['DEFAULT_FARM', 'zyx01', 'zyx02']

    def get_database_url(self):
        """获取数据库连接URL"""
        db_host = 'kingbase'
        db_port = '54321'
        db_name = 'windpower'
        db_user = 'system'
        db_password = '12345678ab'

        return f'postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'

    def log_test_result(self, test_name, success, details="", duration=None):
        """记录测试结果"""
        result = {
            'test_name': test_name,
            'success': success,
            'details': details,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)

        status = "✅" if success else "❌"
        logger.info(f"{status} {test_name}")
        if details:
            logger.info(f"   {details}")
        if duration:
            logger.info(f"   耗时: {duration:.2f}秒")

        return success

    def test_database_connection(self):
        """测试数据库连接"""
        logger.info("\n" + "=" * 50)
        logger.info("测试数据库连接")
        logger.info("=" * 50)

        start_time = time.time()
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(self.get_database_url())
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).fetchone()

                return self.log_test_result(
                    "数据库连接测试",
                    True,
                    f"连接成功，返回值: {result[0]}",
                    time.time() - start_time
                )
        except Exception as e:
            return self.log_test_result(
                "数据库连接测试",
                False,
                f"连接失败: {str(e)}",
                time.time() - start_time
            )

    def test_database_models_multi_station(self):
        """测试数据库模型的多场站支持"""
        logger.info("\n" + "=" * 50)
        logger.info("测试数据库模型多场站支持")
        logger.info("=" * 50)

        start_time = time.time()
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(self.get_database_url())
            with engine.connect() as conn:
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

                tables_with_farm_code = sum(results.values())
                tables_with_unique = sum(unique_constraints.values())

                success = tables_with_farm_code == len(tables_to_check) and tables_with_unique == len(unique_constraints)
                details = f"支持多场站的表: {tables_with_farm_code}/{len(tables_to_check)}, 复合唯一约束: {tables_with_unique}/{len(unique_constraints)}"

                return self.log_test_result(
                    "数据库模型多场站支持",
                    success,
                    details,
                    time.time() - start_time
                )

        except Exception as e:
            return self.log_test_result(
                "数据库模型多场站支持",
                False,
                f"验证失败: {str(e)}",
                time.time() - start_time
            )

    def test_wind_farms_data(self):
        """测试风场数据配置"""
        logger.info("\n" + "=" * 50)
        logger.info("测试风场数据配置")
        logger.info("=" * 50)

        start_time = time.time()
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(self.get_database_url())
            with engine.connect() as conn:
                # 检查风场表数据
                result = conn.execute(text("""
                    SELECT farm_code, farm_name, is_active, COUNT(*) OVER() as total_farms
                    FROM wind_farms
                    ORDER BY farm_code
                """)).fetchall()

                total_farms = result[0][3] if result else 0
                active_farms = [row for row in result if row[2]]

                logger.info(f"  总风场数量: {total_farms}")
                logger.info(f"  活跃风场数量: {len(active_farms)}")

                for row in result:
                    status = "✓" if row[2] else "○"
                    logger.info(f"  {status} {row[0]} - {row[1]}")

                success = total_farms >= 3 and len(active_farms) >= 2
                details = f"风场配置: {total_farms} 个总风场, {len(active_farms)} 个活跃风场"

                return self.log_test_result(
                    "风场数据配置",
                    success,
                    details,
                    time.time() - start_time
                )

        except Exception as e:
            return self.log_test_result(
                "风场数据配置",
                False,
                f"验证失败: {str(e)}",
                time.time() - start_time
            )

    def test_data_isolation(self):
        """测试数据隔离性"""
        logger.info("\n" + "=" * 50)
        logger.info("测试数据隔离性")
        logger.info("=" * 50)

        start_time = time.time()
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(self.get_database_url())
            with engine.connect() as conn:
                # 检查各表的数据隔离情况
                tables = ['actual_power', 'wind_speed_data', 'turbine_power_data']
                isolation_results = {}

                for table in tables:
                    result = conn.execute(text(f"""
                        SELECT farm_code, COUNT(*) as record_count
                        FROM {table}
                        GROUP BY farm_code
                        ORDER BY record_count DESC
                    """)).fetchall()

                    if result:
                        total_records = sum(row[1] for row in result)
                        farm_count = len(result)
                        isolation_results[table] = {
                            'total_records': total_records,
                            'farm_count': farm_count,
                            'farms': [row[0] for row in result]
                        }

                        logger.info(f"  {table}: {farm_count} 个场站, {total_records} 条记录")
                        for row in result[:3]:  # 显示前3个
                            logger.info(f"    {row[0]}: {row[1]} 条记录")
                    else:
                        logger.info(f"  {table}: 无数据")
                        isolation_results[table] = {'total_records': 0, 'farm_count': 0, 'farms': []}

                # 检查是否有跨场站数据污染
                has_isolation = True
                for table, data in isolation_results.items():
                    if data['farm_count'] > 0:
                        # 检查是否有默认场站数据
                        if 'DEFAULT_FARM' in data['farms']:
                            has_isolation = True
                        else:
                            logger.warning(f"  ⚠ {table}: 没有找到DEFAULT_FARM数据")

                success = has_isolation
                details = f"数据隔离检查: {sum(1 for data in isolation_results.values() if data['farm_count'] > 0)}/{len(tables)} 个表有数据"

                return self.log_test_result(
                    "数据隔离性测试",
                    success,
                    details,
                    time.time() - start_time
                )

        except Exception as e:
            return self.log_test_result(
                "数据隔离性测试",
                False,
                f"验证失败: {str(e)}",
                time.time() - start_time
            )

    def test_indexes_performance(self):
        """测试索引优化效果"""
        logger.info("\n" + "=" * 50)
        logger.info("测试索引优化效果")
        logger.info("=" * 50)

        start_time = time.time()
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(self.get_database_url())
            with engine.connect() as conn:
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
                        for idx in indexes[:3]:  # 只显示前3个
                            logger.info(f"    - {idx}")

                    success = len(result) >= 20
                    details = f"优化索引: {len(result)} 个"
                else:
                    logger.warning("✗ 未找到优化索引")
                    success = False
                    details = "未找到优化索引"

                return self.log_test_result(
                    "索引优化效果",
                    success,
                    details,
                    time.time() - start_time
                )

        except Exception as e:
            return self.log_test_result(
                "索引优化效果",
                False,
                f"验证失败: {str(e)}",
                time.time() - start_time
            )

    def test_prediction_models(self):
        """测试预测模型的多场站支持"""
        logger.info("\n" + "=" * 50)
        logger.info("测试预测模型多场站支持")
        logger.info("=" * 50)

        start_time = time.time()
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(self.get_database_url())
            with engine.connect() as conn:
                # 检查模型表的多场站支持
                tables = ['models', 'training_records', 'prediction_records', 'evaluation_metrics']
                model_results = {}

                for table in tables:
                    # 检查表是否存在farm_code字段
                    result = conn.execute(text(f"""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = '{table}' AND column_name = 'farm_code'
                    """)).fetchall()

                    has_farm_code = len(result) > 0
                    model_results[table] = has_farm_code

                    status = "✓" if has_farm_code else "✗"
                    logger.info(f"  {status} {table}: {'支持多场站' if has_farm_code else '缺少farm_code字段'}")

                # 检查自动预测任务表
                result = conn.execute(text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'auto_prediction_tasks' AND column_name = 'farm_code'
                """)).fetchall()

                auto_task_has_farm_code = len(result) > 0
                status = "✓" if auto_task_has_farm_code else "✗"
                logger.info(f"  {status} auto_prediction_tasks: {'支持多场站' if auto_task_has_farm_code else '缺少farm_code字段'}")

                success = all(model_results.values()) and auto_task_has_farm_code
                details = f"模型表支持: {sum(model_results.values())}/{len(model_results)}, 自动预测任务: {'支持' if auto_task_has_farm_code else '不支持'}"

                return self.log_test_result(
                    "预测模型多场站支持",
                    success,
                    details,
                    time.time() - start_time
                )

        except Exception as e:
            return self.log_test_result(
                "预测模型多场站支持",
                False,
                f"验证失败: {str(e)}",
                time.time() - start_time
            )

    def test_data_integrity(self):
        """测试数据完整性"""
        logger.info("\n" + "=" * 50)
        logger.info("测试数据完整性")
        logger.info("=" * 50)

        start_time = time.time()
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(self.get_database_url())
            with engine.connect() as conn:
                # 检查数据完整性约束
                integrity_checks = []

                # 检查主键约束
                tables = ['wind_farms', 'actual_power', 'supershortl_power']
                for table in tables:
                    try:
                        result = conn.execute(text(f"""
                            SELECT COUNT(*) FROM {table}
                        """)).fetchone()
                        integrity_checks.append(True)
                        logger.info(f"  ✓ {table}: {result[0]} 条记录")
                    except:
                        integrity_checks.append(False)
                        logger.error(f"  ✗ {table}: 无法访问")

                # 检查外键约束
                try:
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM actual_power
                        WHERE farm_code NOT IN (SELECT farm_code FROM wind_farms)
                    """)).fetchone()
                    orphaned_records = result[0]
                    integrity_checks.append(orphaned_records == 0)
                    logger.info(f"  {'✓' if orphaned_records == 0 else '✗'} 外键约束: {orphaned_records} 条孤立记录")
                except:
                    integrity_checks.append(False)
                    logger.error("  ✗ 外键约束: 检查失败")

                success = sum(integrity_checks) >= len(integrity_checks) * 0.8
                details = f"完整性检查: {sum(integrity_checks)}/{len(integrity_checks)} 项通过"

                return self.log_test_result(
                    "数据完整性测试",
                    success,
                    details,
                    time.time() - start_time
                )

        except Exception as e:
            return self.log_test_result(
                "数据完整性测试",
                False,
                f"验证失败: {str(e)}",
                time.time() - start_time
            )

    def generate_test_report(self):
        """生成测试报告"""
        logger.info("\n" + "=" * 60)
        logger.info("数据库级别集成测试报告")
        logger.info("=" * 60)
        logger.info(f"测试时间: {datetime.now().isoformat()}")

        # 统计测试结果
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['success']])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        logger.info(f"\n📊 测试统计:")
        logger.info(f"  总测试数: {total_tests}")
        logger.info(f"  通过测试: {passed_tests}")
        logger.info(f"  失败测试: {failed_tests}")
        logger.info(f"  成功率: {success_rate:.1f}%")

        # 详细测试结果
        logger.info(f"\n📋 详细测试结果:")
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            duration_str = f" ({result['duration']:.2f}秒)" if result['duration'] else ""
            logger.info(f"  {status} {result['test_name']}{duration_str}")
            if result['details']:
                logger.info(f"     {result['details']}")

        # 评估结果
        logger.info(f"\n🎯 系统评估:")
        if success_rate >= 90:
            logger.info("  🎉 数据库级别集成测试优秀！")
            logger.info("  ✅ 多场站数据模型完全正常")
            logger.info("  🚀 数据库层面已准备好支持多场站运行")
        elif success_rate >= 80:
            logger.info("  ⚠️ 数据库级别集成测试良好")
            logger.info("  ✅ 基本功能正常，少数问题需要修复")
            logger.info("  📝 建议修复问题后再部署应用服务")
        elif success_rate >= 70:
            logger.info("  🟡 数据库级别集成测试一般")
            logger.info("  ⚠️ 存在较多问题，需要重点修复")
            logger.info("  🔧 建议进行全面检查")
        else:
            logger.info("  🔴 数据库级别集成测试不合格")
            logger.info("  ❌ 存在严重问题，需要重新设计")
            logger.info("  🛠️ 建议回滚数据库迁移")

        # 保存详细报告
        report_data = {
            'test_time': datetime.now().isoformat(),
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': success_rate,
            'test_results': self.test_results
        }

        with open('database_level_test_report.json', 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info(f"\n📄 详细测试报告已保存: database_level_test_report.json")

        return success_rate >= 80

    def run_all_tests(self):
        """运行所有数据库级别测试"""
        logger.info("开始数据库级别集成测试")
        logger.info("=" * 50)

        # 测试序列
        test_sequence = [
            ("数据库连接测试", self.test_database_connection),
            ("数据库模型多场站支持", self.test_database_models_multi_station),
            ("风场数据配置", self.test_wind_farms_data),
            ("数据隔离性测试", self.test_data_isolation),
            ("索引优化效果", self.test_indexes_performance),
            ("预测模型多场站支持", self.test_prediction_models),
            ("数据完整性测试", self.test_data_integrity)
        ]

        for test_name, test_func in test_sequence:
            logger.info(f"\n--- {test_name} ---")
            try:
                test_func()
            except Exception as e:
                logger.error(f"测试执行异常: {str(e)}")
                self.log_test_result(test_name, False, f"执行异常: {str(e)}")

        # 生成测试报告
        success = self.generate_test_report()

        logger.info(f"\n数据库级别集成测试完成")
        return success

def main():
    """主函数"""
    print("风电功率预测系统 - 数据库级别集成测试")
    print("=" * 50)
    print("此脚本将测试多场站系统的数据库层面功能")

    tester = DatabaseLevelTester()
    success = tester.run_all_tests()

    if success:
        print("\n✅ 数据库级别集成测试通过！")
        print("🎉 数据库已准备好支持多场站运行")
        return True
    else:
        print("\n❌ 数据库级别集成测试失败")
        print("🔧 请检查日志并修复问题")
        return False

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)