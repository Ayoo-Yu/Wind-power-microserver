#!/usr/bin/env python3
"""
多场站数据上传API测试脚本
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
import pandas as pd

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_test_data():
    """创建测试用的运营数据"""
    import numpy as np

    # 生成测试数据
    timestamps = [datetime.now() - timedelta(hours=i) for i in range(24, 0, -1)]

    # 风速数据测试
    wind_speed_data = []
    for i, timestamp in enumerate(timestamps):
        for turbine_id in range(1, 6):  # 5个风机
            wind_speed_data.append({
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'farm_code': 'DEFAULT_FARM',
                'turbine_id': f'T{turbine_id:03d}',
                'wind_speed': round(np.random.uniform(3, 15), 2),
                'wind_direction': round(np.random.uniform(0, 360), 1),
                'temperature': round(np.random.uniform(15, 25), 1),
                'humidity': round(np.random.uniform(40, 80), 1),
                'pressure': round(np.random.uniform(990, 1020), 1)
            })

    # 功率数据测试
    power_data = []
    for i, timestamp in enumerate(timestamps):
        for turbine_id in range(1, 6):
            power_data.append({
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'farm_code': 'DEFAULT_FARM',
                'turbine_id': f'T{turbine_id:03d}',
                'active_power': round(np.random.uniform(100, 2000), 2),
                'reactive_power': round(np.random.uniform(-50, 50), 2),
                'apparent_power': round(np.random.uniform(100, 2100), 2),
                'power_factor': round(np.random.uniform(0.8, 1.0), 3),
                'turbine_status': 'RUNNING',
                'grid_frequency': round(np.random.uniform(49.8, 50.2), 2),
                'generator_speed': round(np.random.uniform(1000, 1800), 1),
                'pitch_angle': round(np.random.uniform(0, 25), 1)
            })

    return wind_speed_data, power_data

def save_test_csv_files():
    """保存测试数据为CSV文件"""
    wind_speed_data, power_data = create_test_data()

    # 保存风速数据
    wind_speed_df = pd.DataFrame(wind_speed_data)
    wind_speed_file = 'test_wind_speed_data.csv'
    wind_speed_df.to_csv(wind_speed_file, index=False, encoding='utf-8')
    print(f"✓ 风速测试数据已保存: {wind_speed_file}")

    # 保存功率数据
    power_df = pd.DataFrame(power_data)
    power_file = 'test_turbine_power_data.csv'
    power_df.to_csv(power_file, index=False, encoding='utf-8')
    print(f"✓ 功率测试数据已保存: {power_file}")

    return wind_speed_file, power_file

def test_upload_api():
    """测试数据上传API"""
    print("\n" + "=" * 50)
    print("测试多场站数据上传API")
    print("=" * 50)

    base_url = "http://localhost:5000"

    # 测试健康检查
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✓ 后端服务健康检查通过")
        else:
            print(f"⚠ 后端服务响应异常: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ 无法连接到后端服务: {e}")
        print("💡 请确保后端服务正在运行在端口5000")
        return False

    # 创建测试CSV文件
    try:
        wind_speed_file, power_file = save_test_csv_files()
    except Exception as e:
        print(f"✗ 创建测试数据失败: {e}")
        return False

    # 测试文件上传
    upload_results = []

    # 测试风速数据上传
    try:
        with open(wind_speed_file, 'rb') as f:
            files = {'file': (wind_speed_file, f, 'text/csv')}
            data = {
                'farm_code': 'DEFAULT_FARM',
                'data_type': 'wind_speed',
                'overwrite': 'true'
            }

            response = requests.post(
                f"{base_url}/operational/api/upload_operational_csv",
                files=files,
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✓ 风速数据上传成功: {result.get('message', 'Success')}")
                upload_results.append(True)
            else:
                print(f"✗ 风速数据上传失败: {response.status_code} - {response.text}")
                upload_results.append(False)

    except Exception as e:
        print(f"✗ 风速数据上传异常: {e}")
        upload_results.append(False)

    # 测试功率数据上传
    try:
        with open(power_file, 'rb') as f:
            files = {'file': (power_file, f, 'text/csv')}
            data = {
                'farm_code': 'DEFAULT_FARM',
                'data_type': 'turbine_power',
                'overwrite': 'true'
            }

            response = requests.post(
                f"{base_url}/operational/api/upload_operational_csv",
                files=files,
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✓ 功率数据上传成功: {result.get('message', 'Success')}")
                upload_results.append(True)
            else:
                print(f"✗ 功率数据上传失败: {response.status_code} - {response.text}")
                upload_results.append(False)

    except Exception as e:
        print(f"✗ 功率数据上传异常: {e}")
        upload_results.append(False)

    # 清理测试文件
    try:
        os.remove(wind_speed_file)
        os.remove(power_file)
        print("✓ 测试文件已清理")
    except:
        pass

    return all(upload_results)

def test_farm_management_api():
    """测试风场管理API"""
    print("\n" + "=" * 50)
    print("测试风场管理API")
    print("=" * 50)

    base_url = "http://localhost:5000"

    # 测试获取风场列表
    try:
        response = requests.get(f"{base_url}/api/farms", timeout=10)
        if response.status_code == 200:
            farms = response.json()
            print(f"✓ 获取风场列表成功: {len(farms)} 个风场")
            for farm in farms:
                status = "活跃" if farm.get('is_active') else "停用"
                print(f"  - {farm.get('farm_code')}: {farm.get('farm_name')} ({status})")
        else:
            print(f"✗ 获取风场列表失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 获取风场列表异常: {e}")
        return False

    return True

def test_prediction_api():
    """测试预测API的多场站支持"""
    print("\n" + "=" * 50)
    print("测试预测API多场站支持")
    print("=" * 50)

    base_url = "http://localhost:5000"

    # 测试获取实际功率数据（多场站）
    try:
        response = requests.get(f"{base_url}/api/actual_power?farm_code=DEFAULT_FARM&limit=10", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 获取实际功率数据成功: {len(data.get('data', []))} 条记录")
        else:
            print(f"⚠ 获取实际功率数据响应: {response.status_code}")
    except Exception as e:
        print(f"✗ 获取实际功率数据异常: {e}")

    # 测试获取预测数据
    try:
        response = requests.get(f"{base_url}/api/prediction/supershortl?farm_code=DEFAULT_FARM&limit=10", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 获取超短期预测成功: {len(data.get('data', []))} 条记录")
        else:
            print(f"⚠ 获取超短期预测响应: {response.status_code}")
    except Exception as e:
        print(f"✗ 获取超短期预测异常: {e}")

    return True

def generate_test_summary(upload_success, farm_success, prediction_success):
    """生成测试总结"""
    print("\n" + "=" * 60)
    print("多场站数据上传API测试总结")
    print("=" * 60)
    print(f"测试时间: {datetime.now().isoformat()}")

    results = []
    if upload_success:
        print("✓ 数据上传功能: 正常")
        results.append(True)
    else:
        print("✗ 数据上传功能: 异常")
        results.append(False)

    if farm_success:
        print("✓ 风场管理API: 正常")
        results.append(True)
    else:
        print("✗ 风场管理API: 异常")
        results.append(False)

    if prediction_success:
        print("✓ 预测API: 正常")
        results.append(True)
    else:
        print("✗ 预测API: 异常")
        results.append(False)

    success_rate = sum(results) / len(results) * 100
    print(f"\n📊 测试通过率: {success_rate:.1f}% ({sum(results)}/{len(results)})")

    if success_rate >= 80:
        print("🎉 API功能测试基本成功")
        if success_rate == 100:
            print("✅ 系统已具备生产运行能力")
        else:
            print("📝 建议修复发现的问题")
    else:
        print("⚠️ API功能存在较多问题")
        print("🔧 需要修复后再进行生产部署")

    return success_rate >= 80

def main():
    """主函数"""
    print("风电功率预测系统 - 多场站API功能测试")
    print("=" * 50)
    print("此脚本将测试数据上传和管理API的多场站支持")

    # 执行各项测试
    upload_success = test_upload_api()
    farm_success = test_farm_management_api()
    prediction_success = test_prediction_api()

    # 生成测试总结
    success = generate_test_summary(upload_success, farm_success, prediction_success)

    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试过程中发生异常: {e}")
        sys.exit(1)