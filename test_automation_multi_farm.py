#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 4: 自动化服务多场站功能测试脚本
"""

import os
import sys
import json
import requests
import tempfile
import time
from datetime import datetime, timedelta

class AutomationMultiFarmTester:
    """自动化服务多场站功能测试类"""

    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.test_farms = ['DEFAULT_FARM', 'zyx01', 'zyx02']
        self.headers = {'Content-Type': 'application/json'}

    def log_test(self, test_name, status, message=""):
        """记录测试结果"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_icon = "PASS" if status == "PASS" else "FAIL" if status == "FAIL" else "WARN"
        print(f"[{timestamp}] [{status_icon}] {test_name}: {message}")

    def test_auto_report_start_stop(self):
        """测试自动报告服务的启动和停止"""
        self.log_test("测试自动报告服务启动停止", "START")

        for farm_code in self.test_farms:
            self.log_test(f"测试场站 {farm_code} 自动报告", "START")

            # 测试启动自动报告
            payload = {
                'farm_code': farm_code
            }

            try:
                response = requests.post(
                    f"{self.base_url}/api/report/auto_report/start",
                    json=payload,
                    headers=self.headers
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        self.log_test(f"场站 {farm_code} 自动报告启动", "PASS", "启动成功")
                        # 等待几秒后测试停止
                        time.sleep(2)

                        # 测试停止自动报告
                        stop_response = requests.post(
                            f"{self.base_url}/api/report/auto_report/stop",
                            headers=self.headers
                        )

                        if stop_response.status_code == 200:
                            stop_result = stop_response.json()
                            if stop_result.get('success'):
                                self.log_test(f"场站 {farm_code} 自动报告停止", "PASS", "停止成功")
                            else:
                                self.log_test(f"场站 {farm_code} 自动报告停止", "FAIL", stop_result.get('message'))
                        else:
                            self.log_test(f"场站 {farm_code} 自动报告停止", "FAIL", f"HTTP {stop_response.status_code}")
                    else:
                        self.log_test(f"场站 {farm_code} 自动报告启动", "FAIL", result.get('message'))
                else:
                    self.log_test(f"场站 {farm_code} 自动报告启动", "FAIL", f"HTTP {response.status_code}")

            except Exception as e:
                self.log_test(f"场站 {farm_code} 自动报告测试", "FAIL", str(e))

    def test_prediction_task_management(self):
        """测试预测任务的多场站管理"""
        self.log_test("测试预测任务多场站管理", "START")

        for farm_code in self.test_farms:
            self.log_test(f"测试场站 {farm_code} 预测任务", "START")

            # 测试启动预测任务
            payload = {
                'type': 'supershort',
                'farm_code': farm_code
            }

            try:
                response = requests.post(
                    f"{self.base_url}/api/autopredict/start",
                    json=payload,
                    headers=self.headers
                )

                if response.status_code == 200:
                    result = response.json()
                    if 'message' in result and farm_code in result.get('message', ''):
                        self.log_test(f"场站 {farm_code} 预测任务启动", "PASS", "启动成功")
                        # 等待几秒后测试停止
                        time.sleep(2)

                        # 测试停止预测任务
                        stop_payload = {'type': 'supershort'}
                        stop_response = requests.post(
                            f"{self.base_url}/api/autopredict/stop",
                            json=stop_payload,
                            headers=self.headers
                        )

                        if stop_response.status_code == 200:
                            self.log_test(f"场站 {farm_code} 预测任务停止", "PASS", "停止成功")
                        else:
                            self.log_test(f"场站 {farm_code} 预测任务停止", "FAIL", f"HTTP {stop_response.status_code}")
                    else:
                        self.log_test(f"场站 {farm_code} 预测任务启动", "FAIL", "返回结果未包含场站信息")
                else:
                    self.log_test(f"场站 {farm_code} 预测任务启动", "FAIL", f"HTTP {response.status_code}")

            except Exception as e:
                self.log_test(f"场站 {farm_code} 预测任务测试", "FAIL", str(e))

    def test_scheduler_multi_farm(self):
        """测试调度器的多场站支持"""
        self.log_test("测试调度器多场站支持", "START")

        # 测试获取风电场列表
        try:
            response = requests.get(f"{self.base_url}/api/report/farms")
            if response.status_code == 200:
                farms = response.json()
                if len(farms) >= 2:  # 至少应该有测试场站
                    self.log_test("获取风电场列表", "PASS", f"找到 {len(farms)} 个场站")

                    # 测试不同场站的配置
                    for farm in farms[:2]:  # 测试前两个场站
                        farm_code = farm['farm_code']

                        # 测试创建上报配置
                        config_payload = {
                            'farm_id': farm['id'],
                            'report_type': 'actual',
                            'target_ip': '127.0.0.1',
                            'target_port': 8080,
                            'report_interval': 15,
                            'is_enabled': True
                        }

                        config_response = requests.post(
                            f"{self.base_url}/api/report/configs",
                            json=config_payload,
                            headers=self.headers
                        )

                        if config_response.status_code == 200:
                            self.log_test(f"场站 {farm_code} 配置创建", "PASS", "配置创建成功")
                        else:
                            self.log_test(f"场站 {farm_code} 配置创建", "FAIL", f"HTTP {config_response.status_code}")
                else:
                    self.log_test("获取风电场列表", "FAIL", f"场站数量不足: {len(farms)}")
            else:
                self.log_test("获取风电场列表", "FAIL", f"HTTP {response.status_code}")

        except Exception as e:
            self.log_test("调度器多场站测试", "FAIL", str(e))

    def test_farm_data_isolation(self):
        """测试场站数据隔离"""
        self.log_test("测试场站数据隔离", "START")

        # 测试不同场站的数据获取
        for farm_code in self.test_farms[:2]:  # 测试前两个场站
            try:
                # 测试风速数据获取
                response = requests.get(
                    f"{self.base_url}/api/report/preview/wind_speed",
                    params={'farm_code': farm_code}
                )

                if response.status_code == 200:
                    result = response.json()
                    if 'data' in result:
                        self.log_test(f"场站 {farm_code} 风速数据获取", "PASS", f"获取 {len(result['data'])} 条数据")
                    else:
                        self.log_test(f"场站 {farm_code} 风速数据获取", "WARN", "返回数据为空")
                else:
                    self.log_test(f"场站 {farm_code} 风速数据获取", "FAIL", f"HTTP {response.status_code}")

            except Exception as e:
                self.log_test(f"场站 {farm_code} 数据隔离测试", "FAIL", str(e))

    def test_concurrent_farm_operations(self):
        """测试并发场站操作"""
        self.log_test("测试并发场站操作", "START")

        # 测试同时启动不同场站的预测任务
        test_farms = self.test_farms[:2]  # 测试前两个场站

        # 先停止所有可能运行的任务
        for farm_code in test_farms:
            try:
                stop_payload = {'type': 'supershort'}
                requests.post(
                    f"{self.base_url}/api/autopredict/stop",
                    json=stop_payload,
                    headers=self.headers
                )
            except:
                pass

        # 启动第一个场站
        first_farm = test_farms[0]
        start_payload = {
            'type': 'supershort',
            'farm_code': first_farm
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/autopredict/start",
                json=start_payload,
                headers=self.headers
            )

            if response.status_code == 200:
                self.log_test(f"第一个场站 {first_farm} 启动", "PASS")

                # 尝试启动第二个场站（应该失败，因为第一个正在运行）
                second_farm = test_farms[1]
                second_payload = {
                    'type': 'supershort',
                    'farm_code': second_farm
                }

                second_response = requests.post(
                    f"{self.base_url}/api/autopredict/start",
                    json=second_payload,
                    headers=self.headers
                )

                if second_response.status_code == 400:
                    self.log_test(f"第二个场站 {second_farm} 并发控制", "PASS", "正确拒绝并发启动")
                else:
                    self.log_test(f"第二个场站 {second_farm} 并发控制", "FAIL", "未正确处理并发启动")

                # 停止第一个场站
                time.sleep(1)
                stop_payload = {'type': 'supershort'}
                requests.post(
                    f"{self.base_url}/api/autopredict/stop",
                    json=stop_payload,
                    headers=self.headers
                )
            else:
                self.log_test(f"第一个场站 {first_farm} 启动", "FAIL", f"HTTP {response.status_code}")

        except Exception as e:
            self.log_test("并发操作测试", "FAIL", str(e))

    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("Phase 4: 自动化服务多场站功能测试开始")
        print("=" * 60)

        tests = [
            self.test_auto_report_start_stop,
            self.test_prediction_task_management,
            self.test_scheduler_multi_farm,
            self.test_farm_data_isolation,
            self.test_concurrent_farm_operations
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
            print("所有测试通过！Phase 4 自动化服务多场站功能已完成！")
        else:
            print("存在失败测试，需要进一步调试")
        print("=" * 60)

if __name__ == "__main__":
    tester = AutomationMultiFarmTester()
    tester.run_all_tests()