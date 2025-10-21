#!/usr/bin/env python3
"""
风电功率预测系统 - 端到端系统集成测试脚本
用于验证多场站系统的完整功能链路
"""

import os
import sys
import json
import time
import logging
import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, 'wind-power-forecast', 'backend')
sys.path.append(backend_dir)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('end_to_end_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EndToEndSystemTester:
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.autopredict_url = "http://localhost:5001"
        self.test_results = []
        self.farm_codes = ['DEFAULT_FARM', 'zyx01', 'zyx02']

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

    def test_backend_health(self):
        """测试后端服务健康状态"""
        logger.info("\n" + "=" * 50)
        logger.info("测试后端服务健康状态")
        logger.info("=" * 50)

        start_time = time.time()
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return self.log_test_result(
                    "后端服务健康检查",
                    True,
                    f"服务状态: {data.get('status', 'unknown')}",
                    time.time() - start_time
                )
            else:
                return self.log_test_result(
                    "后端服务健康检查",
                    False,
                    f"HTTP状态码: {response.status_code}",
                    time.time() - start_time
                )
        except Exception as e:
            return self.log_test_result(
                "后端服务健康检查",
                False,
                f"连接失败: {str(e)}",
                time.time() - start_time
            )

    def test_autopredict_health(self):
        """测试自动预测服务健康状态"""
        logger.info("\n" + "=" * 50)
        logger.info("测试自动预测服务健康状态")
        logger.info("=" * 50)

        start_time = time.time()
        try:
            response = requests.get(f"{self.autopredict_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return self.log_test_result(
                    "自动预测服务健康检查",
                    True,
                    f"服务状态: {data.get('status', 'unknown')}",
                    time.time() - start_time
                )
            else:
                return self.log_test_result(
                    "自动预测服务健康检查",
                    False,
                    f"HTTP状态码: {response.status_code}",
                    time.time() - start_time
                )
        except Exception as e:
            return self.log_test_result(
                "自动预测服务健康检查",
                False,
                f"连接失败: {str(e)}",
                time.time() - start_time
            )

    def test_farm_management(self):
        """测试风场管理功能"""
        logger.info("\n" + "=" * 50)
        logger.info("测试风场管理功能")
        logger.info("=" * 50)

        start_time = time.time()

        # 测试获取风场列表
        try:
            response = requests.get(f"{self.base_url}/api/farms", timeout=10)
            if response.status_code == 200:
                farms = response.json()
                active_farms = [f for f in farms if f.get('is_active')]

                success = len(farms) >= 3  # 至少应该有3个风场
                details = f"总风场数: {len(farms)}, 活跃风场: {len(active_farms)}"

                # 显示风场信息
                for farm in farms:
                    status = "活跃" if farm.get('is_active') else "停用"
                    details += f"\n  - {farm.get('farm_code')}: {farm.get('farm_name')} ({status})"

                return self.log_test_result(
                    "风场列表获取",
                    success,
                    details,
                    time.time() - start_time
                )
            else:
                return self.log_test_result(
                    "风场列表获取",
                    False,
                    f"HTTP状态码: {response.status_code}",
                    time.time() - start_time
                )
        except Exception as e:
            return self.log_test_result(
                "风场列表获取",
                False,
                f"请求失败: {str(e)}",
                time.time() - start_time
            )

    def test_operational_data_upload(self):
        """测试运营数据上传功能"""
        logger.info("\n" + "=" * 50)
        logger.info("测试运营数据上传功能")
        logger.info("=" * 50)

        start_time = time.time()
        upload_results = []

        # 为每个场站创建测试数据
        for farm_code in self.farm_codes:
            try:
                # 创建测试风速数据
                wind_speed_data = []
                base_time = datetime.now() - timedelta(hours=24)

                for i in range(48):  # 48个时间点
                    timestamp = base_time + timedelta(minutes=30 * i)
                    for turbine_id in range(1, 4):  # 3个风机
                        wind_speed_data.append({
                            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            'farm_code': farm_code,
                            'turbine_id': f'T{turbine_id:03d}',
                            'wind_speed': round(np.random.uniform(3, 15), 2),
                            'wind_direction': round(np.random.uniform(0, 360), 1),
                            'temperature': round(np.random.uniform(15, 25), 1),
                            'humidity': round(np.random.uniform(40, 80), 1),
                            'pressure': round(np.random.uniform(990, 1020), 1)
                        })

                # 保存为CSV文件
                df = pd.DataFrame(wind_speed_data)
                test_file = f'test_wind_speed_{farm_code}.csv'
                df.to_csv(test_file, index=False, encoding='utf-8')

                # 上传文件
                with open(test_file, 'rb') as f:
                    files = {'file': (test_file, f, 'text/csv')}
                    data = {
                        'farm_code': farm_code,
                        'data_type': 'wind_speed',
                        'overwrite': 'true'
                    }

                    response = requests.post(
                        f"{self.base_url}/operational/api/upload_operational_csv",
                        files=files,
                        data=data,
                        timeout=30
                    )

                    if response.status_code == 200:
                        result = response.json()
                        upload_results.append(True)
                        logger.info(f"  ✓ {farm_code} 风速数据上传成功")
                    else:
                        upload_results.append(False)
                        logger.error(f"  ✗ {farm_code} 风速数据上传失败: {response.status_code}")

                # 清理测试文件
                os.remove(test_file)

            except Exception as e:
                upload_results.append(False)
                logger.error(f"  ✗ {farm_code} 风速数据上传异常: {str(e)}")

        success = sum(upload_results) == len(self.farm_codes)
        details = f"成功上传: {sum(upload_results)}/{len(self.farm_codes)} 个场站"

        return self.log_test_result(
            "运营数据上传",
            success,
            details,
            time.time() - start_time
        )

    def test_prediction_api(self):
        """测试预测API的多场站支持"""
        logger.info("\n" + "=" * 50)
        logger.info("测试预测API多场站支持")
        logger.info("=" * 50)

        start_time = time.time()
        api_results = []

        # 测试每个场站的预测API
        for farm_code in self.farm_codes:
            try:
                # 测试获取实际功率数据
                response = requests.get(
                    f"{self.base_url}/api/actual_power?farm_code={farm_code}&limit=10",
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    record_count = len(data.get('data', []))
                    api_results.append(True)
                    logger.info(f"  ✓ {farm_code} 实际功率数据: {record_count} 条记录")
                else:
                    api_results.append(False)
                    logger.error(f"  ✗ {farm_code} 实际功率数据获取失败: {response.status_code}")

                # 测试获取超短期预测数据
                response = requests.get(
                    f"{self.base_url}/api/prediction/supershortl?farm_code={farm_code}&limit=10",
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    record_count = len(data.get('data', []))
                    logger.info(f"  ✓ {farm_code} 超短期预测: {record_count} 条记录")
                else:
                    logger.warning(f"  ⚠ {farm_code} 超短期预测: {response.status_code}")

            except Exception as e:
                api_results.append(False)
                logger.error(f"  ✗ {farm_code} API测试异常: {str(e)}")

        success = sum(api_results) >= len(self.farm_codes) * 0.8  # 80%成功率即可
        details = f"API测试成功率: {sum(api_results)}/{len(self.farm_codes)*2} 项测试"

        return self.log_test_result(
            "预测API多场站支持",
            success,
            details,
            time.time() - start_time
        )

    def test_autopredict_status(self):
        """测试自动预测服务状态"""
        logger.info("\n" + "=" * 50)
        logger.info("测试自动预测服务状态")
        logger.info("=" * 50)

        start_time = time.time()

        # 测试各个预测类型的状态
        prediction_types = ['short', 'medium', 'supershort']
        status_results = []

        for pred_type in prediction_types:
            try:
                response = requests.get(
                    f"{self.autopredict_url}/api/prediction_status/{pred_type}",
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status', {})
                    running = status.get('running', False)
                    farm_code = status.get('farm_code', 'N/A')

                    status_results.append(True)
                    logger.info(f"  ✓ {pred_type} 预测: 运行状态={running}, 场站={farm_code}")
                else:
                    status_results.append(False)
                    logger.error(f"  ✗ {pred_type} 预测状态获取失败: {response.status_code}")

            except Exception as e:
                status_results.append(False)
                logger.error(f"  ✗ {pred_type} 预测状态异常: {str(e)}")

        success = sum(status_results) == len(prediction_types)
        details = f"状态检查成功率: {sum(status_results)}/{len(prediction_types)} 项测试"

        return self.log_test_result(
            "自动预测服务状态",
            success,
            details,
            time.time() - start_time
        )

    def test_data_consistency(self):
        """测试数据一致性"""
        logger.info("\n" + "=" * 50)
        logger.info("测试数据一致性")
        logger.info("=" * 50)

        start_time = time.time()

        try:
            # 检查各场站的数据分布
            endpoints = [
                ('/api/actual_power', '实际功率'),
                ('/api/prediction/supershortl', '超短期预测'),
                ('/api/prediction/shortl', '短期预测')
            ]

            consistency_results = []

            for endpoint, name in endpoints:
                farm_data_counts = {}

                for farm_code in self.farm_codes:
                    try:
                        response = requests.get(
                            f"{self.base_url}{endpoint}?farm_code={farm_code}&limit=1000",
                            timeout=10
                        )

                        if response.status_code == 200:
                            data = response.json()
                            count = len(data.get('data', []))
                            farm_data_counts[farm_code] = count
                        else:
                            farm_data_counts[farm_code] = 0

                    except Exception as e:
                        farm_data_counts[farm_code] = 0
                        logger.error(f"  ✗ {farm_code} {name} 数据检查失败: {str(e)}")

                # 检查数据分布是否合理
                total_count = sum(farm_data_counts.values())
                if total_count > 0:
                    # 至少有一个场站有数据
                    consistency_results.append(True)
                    logger.info(f"  ✓ {name}: 总记录数={total_count}")
                    for farm_code, count in farm_data_counts.items():
                        logger.info(f"    {farm_code}: {count} 条记录")
                else:
                    consistency_results.append(False)
                    logger.warning(f"  ⚠ {name}: 无数据")

            success = sum(consistency_results) >= len(endpoints) * 0.7  # 70%成功率
            details = f"数据一致性检查: {sum(consistency_results)}/{len(endpoints)} 项通过"

            return self.log_test_result(
                "数据一致性检查",
                success,
                details,
                time.time() - start_time
            )

        except Exception as e:
            return self.log_test_result(
                "数据一致性检查",
                False,
                f"检查失败: {str(e)}",
                time.time() - start_time
            )

    def generate_test_report(self):
        """生成测试报告"""
        logger.info("\n" + "=" * 60)
        logger.info("端到端系统集成测试报告")
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
            logger.info("  🎉 系统集成测试优秀！")
            logger.info("  ✅ 多场站功能完全正常")
            logger.info("  🚀 可以进行生产部署")
        elif success_rate >= 80:
            logger.info("  ⚠️ 系统集成测试良好")
            logger.info("  ✅ 基本功能正常，少数问题需要修复")
            logger.info("  📝 建议修复问题后再部署")
        elif success_rate >= 70:
            logger.info("  🟡 系统集成测试一般")
            logger.info("  ⚠️ 存在较多问题，需要重点修复")
            logger.info("  🔧 建议进行全面检查")
        else:
            logger.info("  🔴 系统集成测试不合格")
            logger.info("  ❌ 存在严重问题，需要重新开发")
            logger.info("  🛠️ 建议回滚版本并重新测试")

        # 保存详细报告
        report_data = {
            'test_time': datetime.now().isoformat(),
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': success_rate,
            'test_results': self.test_results
        }

        with open('end_to_end_test_report.json', 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info(f"\n📄 详细测试报告已保存: end_to_end_test_report.json")

        return success_rate >= 80

    def run_all_tests(self):
        """运行所有端到端测试"""
        logger.info("开始端到端系统集成测试")
        logger.info("=" * 50)

        # 测试序列
        test_sequence = [
            ("后端服务健康检查", self.test_backend_health),
            ("自动预测服务健康检查", self.test_autopredict_health),
            ("风场管理功能", self.test_farm_management),
            ("运营数据上传", self.test_operational_data_upload),
            ("预测API多场站支持", self.test_prediction_api),
            ("自动预测服务状态", self.test_autopredict_status),
            ("数据一致性检查", self.test_data_consistency)
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

        logger.info(f"\n端到端系统集成测试完成")
        return success

def main():
    """主函数"""
    print("风电功率预测系统 - 端到端系统集成测试")
    print("=" * 50)
    print("此脚本将测试多场站系统的完整功能链路")

    tester = EndToEndSystemTester()
    success = tester.run_all_tests()

    if success:
        print("\n✅ 端到端系统集成测试通过！")
        print("🎉 系统已准备好进行多场站运行")
        return True
    else:
        print("\n❌ 端到端系统集成测试失败")
        print("🔧 请检查日志并修复问题")
        return False

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)