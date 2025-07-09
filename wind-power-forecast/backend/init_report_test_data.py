#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上报管理测试数据初始化脚本
"""

from db_session import db_session
from models import WindFarm, ReportConfig
from datetime import datetime

def init_test_data():
    """初始化上报管理测试数据"""
    
    with db_session() as db:
        # 检查是否已存在测试数据
        existing_farm = db.query(WindFarm).filter(WindFarm.farm_code == 'HUST001').first()
        if existing_farm:
            print("测试数据已存在，跳过初始化")
            return
        
        # 创建测试风电场站
        test_farms = [
            WindFarm(
                farm_code='HUST001',
                farm_name='华中科技大学示例风电场',
                capacity=100.0,
                location='湖北省武汉市洪山区',
                is_active=True
            ),
            WindFarm(
                farm_code='TEST002',
                farm_name='测试风电场2号',
                capacity=50.0,
                location='江苏省南京市',
                is_active=True
            ),
            WindFarm(
                farm_code='DEMO003',
                farm_name='演示风电场',
                capacity=80.0,
                location='山东省青岛市',
                is_active=False
            )
        ]
        
        # 添加风电场站
        for farm in test_farms:
            db.add(farm)
        
        db.commit()
        print("✅ 风电场站测试数据创建成功")
        
        # 创建测试上报配置
        test_configs = [
            ReportConfig(
                farm_id=1,  # HUST001
                report_type='actual_power',
                target_ip='192.168.1.100',
                target_port=8080,
                report_interval=15,
                is_enabled=True,
                report_format='json',
                timeout_seconds=30,
                retry_count=3
            ),
            ReportConfig(
                farm_id=1,  # HUST001
                report_type='forecast_short',
                target_ip='192.168.1.100',
                target_port=8080,
                report_interval=15,
                is_enabled=True,
                report_format='json',
                timeout_seconds=30,
                retry_count=3
            ),
            ReportConfig(
                farm_id=2,  # TEST002
                report_type='actual_power',
                target_ip='10.0.0.50',
                target_port=9090,
                report_interval=30,
                is_enabled=False,
                report_format='xml',
                timeout_seconds=60,
                retry_count=5
            )
        ]
        
        # 添加上报配置
        for config in test_configs:
            db.add(config)
        
        db.commit()
        print("✅ 上报配置测试数据创建成功")
        
        print(f"总共创建了 {len(test_farms)} 个风电场站和 {len(test_configs)} 个上报配置")

if __name__ == '__main__':
    init_test_data() 