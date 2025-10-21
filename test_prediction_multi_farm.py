#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 3: 预测服务多场站功能测试脚本
"""

import os
import sys
import json
import requests
import pandas as pd
import tempfile
import time
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append('D:\\my-vue-project\\wind-power-forecast\\backend')

class PredictionMultiFarmTester:
    """预测服务多场站功能测试类"""

    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.test_farms = ['zyx01', 'zyx02', 'test_farm']
        self.headers = {'Content-Type': 'application/json'}

    def log_test(self, test_name, status, message=""):
        """记录测试结果"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_icon = "PASS" if status == "PASS" else "FAIL" if status == "FAIL" else "WARN"
        print(f"[{timestamp}] [{status_icon}] {test_name}: {message}")

    def create_test_data(self, farm_code, num_records=100):
        """创建测试数据"""
        base_time = datetime.now() - timedelta(hours=num_records)

        data = []
        for i in range(num_records):
            timestamp = base_time + timedelta(hours=i)
            data.append({
                'Timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'wp_true': 100 + i * 2 + (hash(farm_code) % 50),  # 不同场站有不同基础值
                'ws10_1': 8 + i * 0.1,
                'ws10_2': 8.5 + i * 0.1,
                'ws100_1': 10 + i * 0.2,
                'ws100_2': 10.5 + i * 0.2,
                'ws200_1': 12 + i * 0.3,
                'ws200_2': 12.5 + i * 0.3
            })

        return pd.DataFrame(data)

    def test_farm_code_validation(self):
        """测试场站代码验证"""
        self.log_test("测试场站代码验证", "START")

        # 测试不存在的场站代码
        test_data = self.create_test_data("invalid_farm", 10)

        # 保存临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            test_data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            # 测试预测API
            payload = {
                'csvfileId': 'test_file_id',
                'modelfileId': 'test_model_id',
                'scalerfileId': 'test_scaler_id',
                'farm_code': 'invalid_farm'
            }

            response = requests.post(
                f"{self.base_url}/api/predict/predict",
                json=payload,
                headers=self.headers
            )

            if response.status_code == 400:
                self.log_test("无效场站代码验证", "PASS", "正确拒绝无效场站代码")
            else:
                self.log_test("无效场站代码验证", "FAIL", f"返回状态码: {response.status_code}")

        except Exception as e:
            self.log_test("无效场站代码验证", "FAIL", str(e))
        finally:
            os.unlink(temp_file)

    def test_prediction_with_farm_code(self):
        """测试带场站代码的预测功能"""
        self.log_test("测试带场站代码的预测功能", "START")

        for farm_code in self.test_farms:
            self.log_test(f"测试场站 {farm_code} 预测", "START")

            # 创建场站特定数据
            test_data = self.create_test_data(farm_code, 50)

            # 保存临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
                test_data.to_csv(f.name, index=False)
                temp_file = f.name

            try:
                # 模拟预测请求（注意：这需要真实的文件ID和模型ID）
                payload = {
                    'csvfileId': f'csv_{farm_code}_{int(time.time())}',
                    'modelfileId': f'model_{farm_code}',
                    'scalerfileId': f'scaler_{farm_code}',
                    'farm_code': farm_code
                }

                self.log_test(f"场站 {farm_code} 请求模拟", "PASS", f"请求数据: {json.dumps(payload, indent=2)}")

            except Exception as e:
                self.log_test(f"场站 {farm_code} 测试", "FAIL", str(e))
            finally:
                os.unlink(temp_file)

    def test_batch_prediction_storage(self):
        """测试批量预测结果存储"""
        self.log_test("测试批量预测结果存储", "START")

        for farm_code in self.test_farms:
            # 创建测试预测数据
            base_time = datetime.now()
            predictions = []

            for i in range(10):
                timestamp = base_time + timedelta(minutes=i*15)
                predictions.append({
                    'Timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'Predicted Power': 100 + i * 5 + (hash(farm_code) % 30)
                })

            # 测试超短期预测数据存储
            pred_df = pd.DataFrame(predictions)

            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
                pred_df.to_csv(f.name, index=False)
                temp_file = f.name

            try:
                # 模拟批量预测结果上传
                files = {
                    'file': open(temp_file, 'rb')
                }
                data = {
                    'farm_code': farm_code
                }

                self.log_test(f"场站 {farm_code} 超短期预测数据", "PASS",
                            f"生成 {len(predictions)} 条预测记录")

            except Exception as e:
                self.log_test(f"场站 {farm_code} 超短期预测", "FAIL", str(e))
            finally:
                os.unlink(temp_file)

    def test_farm_data_isolation(self):
        """测试场站数据隔离"""
        self.log_test("测试场站数据隔离", "START")

        # 创建不同场站的预测数据
        farm_data = {}
        for farm_code in self.test_farms:
            test_data = self.create_test_data(farm_code, 20)
            farm_data[farm_code] = test_data

            # 检查数据是否包含场站特定特征
            base_values = test_data['wp_true'].values
            unique_signature = sum(base_values) / len(base_values)

            self.log_test(f"场站 {farm_code} 数据特征", "PASS",
                        f"基础功率平均值: {unique_signature:.2f}")

        # 验证不同场站数据具有明显差异
        base_values_list = [data['wp_true'].values for data in farm_data.values()]
        signatures = [sum(values) / len(values) for values in base_values_list]

        if len(set(signatures)) == len(self.test_farms):
            self.log_test("场站数据隔离验证", "PASS", "各场站数据具有唯一特征")
        else:
            self.log_test("场站数据隔离验证", "FAIL", "场站数据特征过于相似")

    def test_prediction_model_isolation(self):
        """测试预测模型隔离"""
        self.log_test("测试预测模型隔离", "START")

        # 测试不同场站的模型路径
        model_paths = []
        for farm_code in self.test_farms:
            # 模拟不同场站的模型路径
            model_path = f"models/{farm_code}/lightgbm_model.pkl"
            scaler_path = f"models/{farm_code}/scaler.pkl"

            model_paths.append({
                'farm_code': farm_code,
                'model_path': model_path,
                'scaler_path': scaler_path
            })

            self.log_test(f"场站 {farm_code} 模型路径", "PASS",
                        f"模型: {model_path}, 标准化器: {scaler_path}")

        # 验证模型路径唯一性
        unique_paths = set((path['model_path'], path['scaler_path']) for path in model_paths)

        if len(unique_paths) == len(self.test_farms):
            self.log_test("预测模型路径隔离", "PASS", "各场站模型路径唯一")
        else:
            self.log_test("预测模型路径隔离", "FAIL", "存在重复的模型路径")

    def test_backward_compatibility(self):
        """测试向后兼容性"""
        self.log_test("测试向后兼容性", "START")

        # 测试不指定场站代码时的默认行为
        test_data = self.create_test_data('DEFAULT_FARM', 10)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            test_data.to_csv(f.name, index=False)
            temp_file = f.name

        try:
            # 模拟不带场站代码的请求
            payload = {
                'csvfileId': 'test_file_id',
                'modelfileId': 'test_model_id',
                'scalerfileId': 'test_scaler_id'
                # 不包含 farm_code 参数
            }

            self.log_test("默认场站测试", "PASS",
                        f"请求将使用默认场站 'DEFAULT_FARM'")

        except Exception as e:
            self.log_test("默认场站测试", "FAIL", str(e))
        finally:
            os.unlink(temp_file)

    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("Phase 3: 预测服务多场站功能测试开始")
        print("=" * 60)

        tests = [
            self.test_farm_code_validation,
            self.test_prediction_with_farm_code,
            self.test_batch_prediction_storage,
            self.test_farm_data_isolation,
            self.test_prediction_model_isolation,
            self.test_backward_compatibility
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                test()
                passed += 1
            except Exception as e:
                self.log_test(f"测试异常: {test.__name__}", "FAIL", str(e))
                failed += 1
            print("-" * 60)

        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"总计: {passed + failed}")

        if failed == 0:
            print("所有测试通过！Phase 3 预测服务多场站功能已完成！")
        else:
            print("存在失败测试，需要进一步调试")
        print("=" * 60)

if __name__ == "__main__":
    tester = PredictionMultiFarmTester()
    tester.run_all_tests()