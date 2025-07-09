#!/usr/bin/env python3
"""
运营数据诊断脚本
检查数据库中运营数据表的实际情况
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db_session import db_session
from models import (
    WindSpeedData, TurbinePowerData, WeatherData, 
    InstalledCapacityData, AvailableCapacityData, 
    TheoreticalPowerData, AvailablePowerData,
    WindFarm
)
from sqlalchemy import text
from datetime import datetime, timedelta

def check_table_exists(db, table_name):
    """检查表是否存在"""
    try:
        result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        count = result.scalar()
        return True, count
    except Exception as e:
        return False, str(e)

def check_farm_codes(db):
    """检查风电场站编码"""
    try:
        farms = db.query(WindFarm).all()
        print("=== 风电场站信息 ===")
        for farm in farms:
            print(f"ID: {farm.id}, 场站编码: {farm.farm_code}, 场站名称: {farm.farm_name}")
        return [farm.farm_code for farm in farms]
    except Exception as e:
        print(f"查询风电场站失败: {e}")
        return []

def check_operational_data(db, farm_codes):
    """检查运营数据表"""
    tables = [
        ("wind_speed_data", WindSpeedData),
        ("turbine_power_data", TurbinePowerData), 
        ("weather_data", WeatherData),
        ("installed_capacity_data", InstalledCapacityData),
        ("available_capacity_data", AvailableCapacityData),
        ("theoretical_power_data", TheoreticalPowerData),
        ("available_power_data", AvailablePowerData)
    ]
    
    print("\n=== 运营数据表检查 ===")
    
    for table_name, model_class in tables:
        exists, result = check_table_exists(db, table_name)
        if exists:
            print(f"✅ {table_name}: 存在，总记录数: {result}")
            
            # 检查每个场站的数据
            for farm_code in farm_codes:
                try:
                    count = db.query(model_class).filter(model_class.farm_code == farm_code).count()
                    print(f"   场站 {farm_code}: {count} 条记录")
                    
                    # 显示最新的几条记录的时间
                    if count > 0:
                        latest_records = db.query(model_class)\
                            .filter(model_class.farm_code == farm_code)\
                            .order_by(model_class.timestamp.desc())\
                            .limit(3).all()
                        
                        print(f"   最新记录时间:")
                        for record in latest_records:
                            print(f"     - {record.timestamp}")
                            
                except Exception as e:
                    print(f"   查询场站 {farm_code} 数据失败: {e}")
        else:
            print(f"❌ {table_name}: 不存在或查询失败: {result}")

def check_time_range_data(db, farm_code="FD01"):
    """检查特定时间范围的数据"""
    target_time = datetime(2025, 7, 7, 22, 0, 0)  # 对应日志中的时间
    time_window_start = target_time - timedelta(minutes=10)
    time_window_end = target_time + timedelta(minutes=10)
    
    print(f"\n=== 时间范围数据检查 (场站: {farm_code}) ===")
    print(f"目标时间: {target_time}")
    print(f"查询窗口: {time_window_start} 到 {time_window_end}")
    
    tables = [
        ("风速数据", WindSpeedData),
        ("单机功率数据", TurbinePowerData),
        ("气象数据", WeatherData),
        ("装机容量数据", InstalledCapacityData),
        ("可用容量数据", AvailableCapacityData),
        ("理论功率数据", TheoreticalPowerData),
        ("可用功率数据", AvailablePowerData)
    ]
    
    for table_name, model_class in tables:
        try:
            # 查询该时间窗口内的数据
            records = db.query(model_class)\
                .filter(model_class.farm_code == farm_code)\
                .filter(model_class.timestamp >= time_window_start)\
                .filter(model_class.timestamp <= time_window_end)\
                .all()
            
            print(f"{table_name}: {len(records)} 条记录")
            for record in records:
                print(f"  - {record.timestamp}")
                
        except Exception as e:
            print(f"{table_name}: 查询失败 - {e}")

def main():
    print("开始诊断运营数据...")
    
    try:
        with db_session() as db:
            # 检查风电场站
            farm_codes = check_farm_codes(db)
            
            # 检查运营数据表
            check_operational_data(db, farm_codes)
            
            # 检查特定时间范围的数据
            if "FD01" in farm_codes:
                check_time_range_data(db, "FD01")
            else:
                print(f"\n警告: 未找到场站编码 'FD01'，可用的场站编码: {farm_codes}")
                
    except Exception as e:
        print(f"诊断失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 