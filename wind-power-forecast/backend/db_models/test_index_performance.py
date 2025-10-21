#!/usr/bin/env python3
"""
索引性能测试脚本
用于验证索引优化前后的查询性能改进
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_config import get_database_url
from db_models.power import ActualPower, SupershortlPower, ShortlPower, MidPower
from db_models.operational_data import TurbinePowerData, WindSpeedData, WeatherData
from db_models.report_config import ReportQualityStatistics, ReportLog

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
        self.engine = create_engine(get_database_url())
        self.Session = sessionmaker(bind=self.engine)
        self.results = []

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

    def get_test_farm_codes(self):
        """获取测试用的场站代码"""
        try:
            with self.Session() as session:
                # 获取所有场站代码
                from db_models.report_config import WindFarm
                farms = session.query(WindFarm.farm_code).filter(WindFarm.is_active == True).all()
                farm_codes = [farm.farm_code for farm in farms]

                if not farm_codes:
                    logger.warning("没有找到活跃场站，使用默认场站")
                    return ['DEFAULT_FARM']

                logger.info(f"找到 {len(farm_codes)} 个测试场站: {farm_codes[:3]}...")  # 只显示前3个
                return farm_codes[:3]  # 最多测试3个场站

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
                        logger.info(f"  返回标量值: {result.scalar()}")
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

        with self.Session() as session:
            # 测试1: 单场站时间范围查询 (ActualPower)
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)

            for farm_code in farm_codes:
                self.execute_query_with_timing(
                    f"actual_power_time_range_{farm_code}",
                    lambda: session.query(ActualPower)
                        .filter(ActualPower.farm_code == farm_code)
                        .filter(ActualPower.timestamp.between(start_time, end_time))
                        .order_by(ActualPower.timestamp.desc())
                        .limit(1000)
                        .all(),
                    f"场站 {farm_code} 实际功率时间范围查询"
                )

            # 测试2: 多场站聚合查询
            self.execute_query_with_timing(
                "multi_farm_power_stats",
                lambda: session.query(
                    ActualPower.farm_code,
                    func.count(ActualPower.id).label('record_count'),
                    func.avg(ActualPower.wp_true).label('avg_power'),
                    func.max(ActualPower.wp_true).label('max_power')
                )
                .filter(ActualPower.timestamp >= start_time)
                .group_by(ActualPower.farm_code)
                .all(),
                "多场站功率统计查询"
            )

            # 测试3: 超短期预测查询
            self.execute_query_with_timing(
                "supershortl_power_latest",
                lambda: session.query(SupershortlPower)
                    .filter(SupershortlPower.farm_code == farm_codes[0])
                    .order_by(SupershortlPower.timestamp.desc())
                    .limit(100)
                    .all(),
                f"场站 {farm_codes[0]} 最新超短期预测查询"
            )

            # 测试4: 时间戳精确查找 (模拟数据上传重复检查)
            test_timestamps = [start_time + timedelta(hours=i) for i in range(10)]
            self.execute_query_with_timing(
                "timestamp_exact_lookup",
                lambda: session.query(ActualPower.id)
                    .filter(ActualPower.farm_code == farm_codes[0])
                    .filter(ActualPower.timestamp.in_(test_timestamps))
                    .all(),
                "时间戳精确查找 (重复检查)"
            )

    def test_operational_data_queries(self):
        """测试运营数据查询"""
        logger.info("\n" + "=" * 50)
        logger.info("测试运营数据查询性能")
        logger.info("=" * 50)

        farm_codes = self.get_test_farm_codes()

        with self.Session() as session:
            # 测试1: 风机功率数据查询
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)

            for farm_code in farm_codes:
                self.execute_query_with_timing(
                    f"turbine_power_time_range_{farm_code}",
                    lambda: session.query(TurbinePowerData)
                        .filter(TurbinePowerData.farm_code == farm_code)
                        .filter(TurbinePowerData.timestamp.between(start_time, end_time))
                        .order_by(TurbinePowerData.timestamp.desc())
                        .limit(500)
                        .all(),
                    f"场站 {farm_code} 风机功率数据查询"
                )

            # 测试2: 风速数据查询
            self.execute_query_with_timing(
                "wind_speed_data_query",
                lambda: session.query(WindSpeedData)
                    .filter(WindSpeedData.farm_code == farm_codes[0])
                    .filter(WindSpeedData.timestamp >= start_time)
                    .order_by(WindSpeedData.timestamp, WindSpeedData.turbine_id)
                    .limit(1000)
                    .all(),
                f"场站 {farm_codes[0]} 风速数据查询"
            )

            # 测试3: 气象数据聚合
            self.execute_query_with_timing(
                "weather_data_aggregation",
                lambda: session.query(
                    func.date_trunc('hour', WeatherData.timestamp).label('hour'),
                    func.avg(WeatherData.temperature).label('avg_temp'),
                    func.avg(WeatherData.wind_speed_avg).label('avg_wind_speed'),
                    func.count(WeatherData.id).label('record_count')
                )
                .filter(WeatherData.farm_code == farm_codes[0])
                .filter(WeatherData.timestamp >= start_time)
                .group_by(func.date_trunc('hour', WeatherData.timestamp))
                .order_by(func.date_trunc('hour', WeatherData.timestamp))
                .all(),
                f"场站 {farm_codes[0]} 气象数据小时聚合"
            )

    def test_reporting_queries(self):
        """测试报表相关查询"""
        logger.info("\n" + "=" * 50)
        logger.info("测试报表查询性能")
        logger.info("=" * 50)

        farm_codes = self.get_test_farm_codes()

        with self.Session() as session:
            # 测试1: 报表质量统计查询
            today = datetime.now().date()
            month_start = today.replace(day=1)

            self.execute_query_with_timing(
                "report_quality_monthly_stats",
                lambda: session.query(ReportQualityStatistics)
                    .filter(ReportQualityStatistics.farm_code == farm_codes[0])
                    .filter(ReportQualityStatistics.date >= month_start.strftime('%Y-%m-%d'))
                    .order_by(ReportQualityStatistics.date.desc())
                    .all(),
                f"场站 {farm_codes[0]} 月度质量统计查询"
            )

            # 测试2: 报表日志查询
            self.execute_query_with_timing(
                "report_logs_recent",
                lambda: session.query(ReportLog)
                    .filter(ReportLog.farm_code == farm_codes[0])
                    .filter(ReportLog.report_time >= datetime.now() - timedelta(days=7))
                    .order_by(ReportLog.report_time.desc())
                    .limit(100)
                    .all(),
                f"场站 {farm_codes[0]} 最近一周报表日志查询"
            )

            # 测试3: 多场站报表成功率统计
            self.execute_query_with_timing(
                "multi_farm_success_rate",
                lambda: session.query(
                    ReportLog.farm_code,
                    ReportLog.report_type,
                    func.count(ReportLog.id).label('total_reports'),
                    func.sum(func.case([(ReportLog.status == 'success', 1)], else_=0)).label('success_count'),
                    (func.sum(func.case([(ReportLog.status == 'success', 1)], else_=0)) * 100.0 / func.count(ReportLog.id)).label('success_rate')
                )
                .filter(ReportLog.report_time >= datetime.now() - timedelta(days=30))
                .group_by(ReportLog.farm_code, ReportLog.report_type)
                .all(),
                "多场站报表成功率统计"
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
                        idx_tup_fetch as tuples_fetched,
                        pg_size_pretty(pg_relation_size(indexrelid)) as index_size
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
                        logger.info(f"    索引大小: {stat[6]}")
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
            elif 'turbine' in result['query_name'] or 'wind_speed' in result['query_name'] or 'weather' in result['query_name']:
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
                logger.info("  性能评估: 🟢 优秀")
            elif total_avg_time < 0.5:
                logger.info("  性能评估: 🟡 良好")
            elif total_avg_time < 2.0:
                logger.info("  性能评估: 🟠 一般")
            else:
                logger.info("  性能评估: 🔴 需要优化")

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