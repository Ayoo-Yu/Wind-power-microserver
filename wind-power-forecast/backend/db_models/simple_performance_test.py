#!/usr/bin/env python3
"""
简化版索引性能测试脚本
用于验证索引优化前后的查询性能改进
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta

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
        logging.FileHandler('index_performance_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IndexPerformanceTester:
    def __init__(self):
        try:
            from sqlalchemy import create_engine, text, func
            from sqlalchemy.orm import sessionmaker

            self.engine = create_engine(get_database_url())
            self.Session = sessionmaker(bind=self.engine)
            self.results = []
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

    def get_test_farm_codes(self):
        """获取测试用的场站代码"""
        try:
            with self.engine.connect() as conn:
                # 获取所有场站代码
                result = conn.execute(text("SELECT DISTINCT farm_code FROM wind_farms WHERE is_active = TRUE LIMIT 3")).fetchall()
                farm_codes = [row[0] for row in result]

                if not farm_codes:
                    logger.warning("没有找到活跃场站，使用默认值")
                    return ['DEFAULT_FARM']

                logger.info(f"找到测试场站: {farm_codes}")
                return farm_codes

        except Exception as e:
            logger.error(f"获取场站代码失败: {e}")
            return ['DEFAULT_FARM']

    def execute_query_with_timing(self, query_name, query_func, description=""):
        """执行查询并记录执行时间"""
        logger.info(f"执行查询: {query_name} - {description}")

        # 预热查询
        try:
            query_func()
        except:
            pass

        # 执行3次取平均值
        times = []
        for i in range(3):
            start_time = time.time()
            try:
                result = query_func()
                execution_time = time.time() - start_time
                times.append(execution_time)

                if i == 0:  # 第一次查询记录结果信息
                    if hasattr(result, '__len__'):
                        logger.info(f"  返回 {len(result)} 行数据")
                    elif hasattr(result, 'scalar'):
                        logger.info(f"  返回标量值")
                    else:
                        logger.info(f"  查询成功执行")
            except Exception as e:
                logger.error(f"  查询执行失败: {e}")
                times.append(float('inf'))

        # 计算平均时间
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            logger.info(f"  平均执行时间: {avg_time:.3f}秒 (最小: {min_time:.3f}秒, 最大: {max_time:.3f}秒)")

            self.results.append({
                'query_name': query_name,
                'description': description,
                'avg_time': avg_time,
                'min_time': min_time,
                'max_time': max_time,
                'success': times[0] != float('inf')
            })

            return avg_time
        return float('inf')

    def test_power_prediction_queries(self):
        """测试功率预测相关查询"""
        logger.info("\n" + "=" * 50)
        logger.info("测试功率预测查询性能")
        logger.info("=" * 50)

        farm_codes = self.get_test_farm_codes()

        with self.engine.connect() as conn:
            # 测试1: 单场站时间范围查询 (ActualPower)
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)

            for farm_code in farm_codes:
                self.execute_query_with_timing(
                    f"actual_power_time_range_{farm_code}",
                    lambda: conn.execute(text(f"""
                        SELECT * FROM actual_power
                        WHERE farm_code = '{farm_codes[0]}'
                        AND timestamp BETWEEN '{start_time}' AND '{end_time}'
                        ORDER BY timestamp DESC
                        LIMIT 1000
                    """)).fetchall(),
                    f"场站 {farm_codes[0]} 实际功率时间范围查询"
                )

            # 测试2: 多场站聚合查询
            self.execute_query_with_timing(
                "multi_farm_power_stats",
                lambda: conn.execute(text(f"""
                    SELECT
                        farm_code,
                        COUNT(*) as record_count,
                        AVG(wp_true) as avg_power,
                        MAX(wp_true) as max_power
                    FROM actual_power
                    WHERE timestamp >= '{start_time}'
                    GROUP BY farm_code
                """)).fetchall(),
                "多场站功率统计查询"
            )

            # 测试3: 超短期预测查询
            self.execute_query_with_timing(
                "supershortl_power_latest",
                lambda: conn.execute(text(f"""
                    SELECT * FROM supershortl_power
                    WHERE farm_code = '{farm_codes[0]}'
                    ORDER BY timestamp DESC
                    LIMIT 100
                """)).fetchall(),
                f"场站 {farm_codes[0]} 最新超短期预测查询"
            )

    def test_operational_data_queries(self):
        """测试运营数据查询"""
        logger.info("\n" + "=" * 50)
        logger.info("测试运营数据查询性能")
        logger.info("=" * 50)

        farm_codes = self.get_test_farm_codes()

        with self.engine.connect() as conn:
            # 测试1: 风机功率数据查询
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)

            for farm_code in farm_codes:
                self.execute_query_with_timing(
                    f"turbine_power_time_range_{farm_code}",
                    lambda: conn.execute(text(f"""
                        SELECT * FROM turbine_power_data
                        WHERE farm_code = '{farm_codes[0]}'
                        AND timestamp BETWEEN '{start_time}' AND '{end_time}'
                        ORDER BY timestamp DESC
                        LIMIT 500
                    """)).fetchall(),
                    f"场站 {farm_codes[0]} 风机功率数据查询"
                )

            # 测试2: 风速数据查询
            self.execute_query_with_timing(
                "wind_speed_data_query",
                lambda: conn.execute(text(f"""
                    SELECT * FROM wind_speed_data
                    WHERE farm_code = '{farm_codes[0]}'
                    AND timestamp >= '{start_time}'
                    ORDER BY timestamp, turbine_id
                    LIMIT 1000
                """)).fetchall(),
                f"场站 {farm_codes[0]} 风速数据查询"
            )

    def test_reporting_queries(self):
        """测试报表相关查询"""
        logger.info("\n" + "=" * 50)
        logger.info("测试报表查询性能")
        logger.info("=" * 50)

        farm_codes = self.get_test_farm_codes()

        with self.engine.connect() as conn:
            # 测试1: 报表质量统计查询
            today = datetime.now().date()
            month_start = today.replace(day=1)

            self.execute_query_with_timing(
                "report_quality_monthly_stats",
                lambda: conn.execute(text(f"""
                    SELECT * FROM report_quality_statistics
                    WHERE farm_code = '{farm_codes[0]}'
                    AND date >= '{month_start}'
                    ORDER BY date DESC
                """)).fetchall(),
                f"场站 {farm_codes[0]} 月度质量统计查询"
            )

            # 测试2: 报表日志查询
            self.execute_query_with_timing(
                "report_logs_recent",
                lambda: conn.execute(text(f"""
                    SELECT * FROM report_logs
                    WHERE farm_code = '{farm_codes[0]}'
                    AND report_time >= '{datetime.now() - timedelta(days=7)}'
                    ORDER BY report_time DESC
                    LIMIT 100
                """)).fetchall(),
                f"场站 {farm_codes[0]} 最近一周报表日志查询"
            )

    def check_index_usage(self):
        """检查索引使用情况"""
        logger.info("\n" + "=" * 50)
        logger.info("检查索引使用统计")
        logger.info("=" * 50)

        try:
            with self.engine.connect() as conn:
                # 获取索引使用统计
                result = conn.execute(text("""
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        idx_scan as index_scans,
                        idx_tup_read as tuples_read,
                        idx_tup_fetch as tuples_fetched
                    FROM pg_stat_user_indexes
                    WHERE indexname LIKE 'idx_%'
                    ORDER BY idx_scan DESC, tablename, indexname;
                """)).fetchall()

                if result:
                    logger.info("索引使用统计:")
                    for stat in result:
                        logger.info(f"  {stat[1]}.{stat[2]}:")
                        logger.info(f"    扫描次数: {stat[3]}")
                        logger.info(f"    读取元组: {stat[4]}")
                        logger.info(f"    获取元组: {stat[5]}")
                else:
                    logger.info("没有找到索引使用统计 (可能需要更长时间的数据收集)")

        except Exception as e:
            logger.error(f"检查索引使用失败: {e}")

    def generate_performance_report(self):
        """生成性能测试报告"""
        logger.info("\n" + "=" * 60)
        logger.info("索引性能测试报告")
        logger.info("=" * 60)

        # 按类别汇总结果
        categories = {
            '功率预测查询': [],
            '运营数据查询': [],
            '报表查询': []
        }

        for result in self.results:
            if 'power' in result['query_name'] or 'supershortl' in result['query_name']:
                categories['功率预测查询'].append(result)
            elif 'turbine' in result['query_name'] or 'wind_speed' in result['query_name']:
                categories['运营数据查询'].append(result)
            else:
                categories['报表查询'].append(result)

        for category, queries in categories.items():
            if queries:
                logger.info(f"\n{category} ({len(queries)} 个查询):")
                successful_queries = [q for q in queries if q['success']]
                if successful_queries:
                    avg_time = sum(q['avg_time'] for q in successful_queries) / len(successful_queries)
                    fastest = min(successful_queries, key=lambda x: x['min_time'])
                    slowest = max(successful_queries, key=lambda x: x['max_time'])

                    logger.info(f"  平均执行时间: {avg_time:.3f}秒")
                    logger.info(f"  最快查询: {fastest['query_name']} ({fastest['min_time']:.3f}秒)")
                    logger.info(f"  最慢查询: {slowest['query_name']} ({slowest['max_time']:.3f}秒)")
                else:
                    logger.info("  所有查询都失败了")

        # 总体统计
        total_queries = len(self.results)
        successful_queries = len([r for r in self.results if r['success']])
        failed_queries = total_queries - successful_queries

        logger.info(f"\n总体统计:")
        logger.info(f"  总查询数: {total_queries}")
        logger.info(f"  成功查询: {successful_queries}")
        logger.info(f"  失败查询: {failed_queries}")
        logger.info(f"  成功率: {(successful_queries/total_queries*100):.1f}%")

        # 性能评估
        if successful_queries > 0:
            total_avg_time = sum(r['avg_time'] for r in self.results if r['success']) / successful_queries
            logger.info(f"  平均执行时间: {total_avg_time:.3f}秒")

            if total_avg_time < 0.1:
                logger.info("  性能评估: 🟢 优秀 (< 0.1秒)")
            elif total_avg_time < 0.5:
                logger.info("  性能评估: 🟡 良好 (< 0.5秒)")
            elif total_avg_time < 2.0:
                logger.info("  性能评估: 🟠 一般 (< 2.0秒)")
            else:
                logger.info("  性能评估: 🔴 需要优化 (>= 2.0秒)")

    def run_all_tests(self):
        """运行所有性能测试"""
        logger.info("开始索引性能测试")
        logger.info(f"测试时间: {datetime.now().isoformat()}")

        # 运行测试
        self.test_power_prediction_queries()
        self.test_operational_data_queries()
        self.test_reporting_queries()
        self.check_index_usage()
        self.generate_performance_report()

        logger.info("\n性能测试完成")

def main():
    """主函数"""
    print("风电功率预测系统 - 索引性能测试")
    print("=" * 50)
    print("此脚本将测试多场站查询性能")

    tester = IndexPerformanceTester()

    # 执行测试步骤
    test_steps = [
        ("数据库连接测试", tester.test_database_connection),
        ("运行性能测试", tester.run_all_tests)
    ]

    passed_steps = 0
    total_steps = len(test_steps)

    for step_name, step_func in test_steps:
        logger.info(f"\n--- {step_name} ---")
        if step_func():
            logger.info(f"✅ {step_name} 通过")
            passed_steps += 1
        else:
            logger.error(f"❌ {step_name} 失败")

    # 最终结果
    logger.info(f"\n" + "=" * 50)
    logger.info(f"性能测试结果: {passed_steps}/{total_steps} 项通过")

    if passed_steps == total_steps:
        logger.info("🎉 性能测试成功完成！")
        print("\n✅ 性能测试完成！")
        print("详细测试结果请查看日志文件: index_performance_test.log")
        return True
    else:
        logger.error(f"❌ 有 {total_steps - passed_steps} 项步骤失败")
        print("\n❌ 性能测试失败，请检查错误信息")
        return False

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)