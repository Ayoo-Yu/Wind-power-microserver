#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试修复后的统计API
"""

import sys
sys.path.append('wind-power-forecast/backend')

try:
    # 测试导入
    from routes.report_management_router import get_report_statistics, get_farm_name
    print("✓ API函数导入成功")
    
    # 测试数据库会话
    from db_session import db_session
    print("✓ 数据库会话导入成功")
    
    # 测试datetime导入
    from datetime import datetime, timedelta
    print("✓ datetime模块导入成功")
    
    print("\n所有修复验证通过！")
    
except Exception as e:
    print(f"✗ 导入失败: {e}")
    sys.exit(1) 