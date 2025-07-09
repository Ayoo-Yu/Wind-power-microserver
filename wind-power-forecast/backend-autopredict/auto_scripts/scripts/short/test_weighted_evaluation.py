#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修改后的evaluate_with_time_weights函数
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# 添加项目路径以便导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils_short import evaluate_with_time_weights

def test_weighted_evaluation():
    """测试时间加权评估函数"""
    print("测试时间加权评估函数...")
    
    # 创建测试数据
    n_points = 288  # 3天的数据，每天96个点
    
    # 生成时间戳（3天，每15分钟一个点）
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    timestamps = [start_time + timedelta(minutes=15*i) for i in range(n_points)]
    timestamps = pd.to_datetime(timestamps)
    
    # 生成测试数据
    np.random.seed(42)
    y_true = np.random.uniform(50, 400, n_points)  # 实际功率值
    # 预测值有一些误差
    y_pred = y_true + np.random.normal(0, 20, n_points)
    
    print(f"生成测试数据: {len(y_true)} 个点，时间跨度: {timestamps[0]} 到 {timestamps[-1]}")
    
    try:
        # 调用修改后的函数
        score, rmse, k, weighted_rmse, weighted_k = evaluate_with_time_weights(
            y_true, y_pred, timestamps, 
            rmse_weight=0.2, k_weight=0.8, time_decay=0.9, points_per_day=96
        )
        
        print(f"✅ 函数调用成功")
        print(f"综合评分: {score:.4f}")
        print(f"标准RMSE: {rmse:.4f}")
        print(f"标准K值: {k:.4f}")
        print(f"时间加权RMSE: {weighted_rmse:.4f}")
        print(f"时间加权K值: {weighted_k:.4f}")
        
        # 验证返回值类型
        assert isinstance(score, (int, float)), "score应该是数值"
        assert isinstance(rmse, (int, float)), "rmse应该是数值"
        assert isinstance(k, (int, float)), "k应该是数值"
        assert isinstance(weighted_rmse, (int, float)), "weighted_rmse应该是数值"
        assert isinstance(weighted_k, (int, float)), "weighted_k应该是数值"
        
        print("✅ 所有返回值类型检查通过")
        
        # 验证合理性检查
        assert 0 <= score <= 1, f"综合评分应该在0-1之间，实际: {score}"
        assert rmse >= 0, f"RMSE应该非负，实际: {rmse}"
        assert weighted_rmse >= 0, f"加权RMSE应该非负，实际: {weighted_rmse}"
        
        print("✅ 数值合理性检查通过")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_missing_data():
    """测试处理缺失数据的情况"""
    print("\n" + "="*60)
    print("测试缺失数据处理...")
    
    # 创建3天的测试数据，但第2天缺失一些数据
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    
    # 第1天：完整96个点
    day1_timestamps = [start_time + timedelta(minutes=15*i) for i in range(96)]
    
    # 第2天：只有50个点（缺失46个点）
    day2_start = start_time + timedelta(days=1)
    day2_timestamps = [day2_start + timedelta(minutes=15*i) for i in range(50)]
    
    # 第3天：只有30个点（但现在仍然会计算）
    day3_start = start_time + timedelta(days=2)
    day3_timestamps = [day3_start + timedelta(minutes=15*i) for i in range(30)]
    
    # 合并所有时间戳
    all_timestamps = day1_timestamps + day2_timestamps + day3_timestamps
    n_points = len(all_timestamps)
    
    # 生成对应的数据
    np.random.seed(42)
    y_true = np.random.uniform(50, 400, n_points)
    y_pred = y_true + np.random.normal(0, 20, n_points)
    
    print(f"生成缺失数据测试:")
    print(f"  第1天: 96/96 个点 (完整)")
    print(f"  第2天: 50/96 个点 (缺失46个点)")
    print(f"  第3天: 30/96 个点 (缺失66个点)")
    print(f"  总计: {n_points} 个点")
    
    try:
        # 调用修改后的函数
        score, rmse, k, weighted_rmse, weighted_k = evaluate_with_time_weights(
            y_true, y_pred, all_timestamps, 
            rmse_weight=0.2, k_weight=0.8, time_decay=0.9, points_per_day=96
        )
        
        print(f"✅ 缺失数据测试成功")
        print(f"综合评分: {score:.4f}")
        print(f"标准RMSE: {rmse:.4f}")
        print(f"标准K值: {k:.4f}")
        print(f"时间加权RMSE: {weighted_rmse:.4f}")
        print(f"时间加权K值: {weighted_k:.4f}")
        
        # 验证函数能正确处理缺失数据，现在所有天都应该参与计算
        assert weighted_k >= 0, f"时间加权K值应该非负，实际: {weighted_k}"
        assert weighted_k > 0, f"有数据的情况下，时间加权K值应该大于0，实际: {weighted_k}"
        
        print("✅ 缺失数据处理检查通过")
        
        return True
        
    except Exception as e:
        print(f"❌ 缺失数据测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_extreme_missing_data():
    """测试极端缺失数据情况（每天都只有很少数据点）"""
    print("\n" + "="*60)
    print("测试极端缺失数据（每天都只有很少数据点）...")
    
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    
    # 创建3天的数据，但每天都只有很少的点
    all_timestamps = []
    for day in range(3):
        day_start = start_time + timedelta(days=day)
        # 每天只有20个点
        day_timestamps = [day_start + timedelta(minutes=15*i) for i in range(20)]
        all_timestamps.extend(day_timestamps)
    
    n_points = len(all_timestamps)
    
    # 生成对应的数据
    np.random.seed(42)
    y_true = np.random.uniform(50, 400, n_points)
    y_pred = y_true + np.random.normal(0, 20, n_points)
    
    print(f"生成极端缺失数据测试:")
    print(f"  每天只有20/96个点，总计: {n_points} 个点")
    
    try:
        # 调用修改后的函数
        score, rmse, k, weighted_rmse, weighted_k = evaluate_with_time_weights(
            y_true, y_pred, all_timestamps, 
            rmse_weight=0.2, k_weight=0.8, time_decay=0.9, points_per_day=96
        )
        
        print(f"✅ 极端缺失数据测试成功")
        print(f"综合评分: {score:.4f}")
        print(f"标准RMSE: {rmse:.4f}")
        print(f"标准K值: {k:.4f}")
        print(f"时间加权RMSE: {weighted_rmse:.4f}")
        print(f"时间加权K值: {weighted_k:.4f}")
        
        # 现在即使数据很少，也应该计算K值，所以weighted_k应该大于0
        assert weighted_k >= 0, f"时间加权K值应该非负，实际: {weighted_k}"
        assert weighted_k > 0, f"有数据的情况下，时间加权K值应该大于0，实际: {weighted_k}"
        
        print("✅ 极端缺失数据处理检查通过")
        
        return True
        
    except Exception as e:
        print(f"❌ 极端缺失数据测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success1 = test_weighted_evaluation()
    success2 = test_missing_data()
    success3 = test_extreme_missing_data()
    
    all_success = success1 and success2 and success3
    
    if all_success:
        print("\n🎉 所有测试全部通过！修改后的函数工作正常。")
    else:
        print("\n💥 部分测试失败！请检查代码修改。")
    
    sys.exit(0 if all_success else 1) 