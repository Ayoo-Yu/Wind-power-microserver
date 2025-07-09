#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试时间权重计算的详细过程
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

from utils_middle import evaluate_with_time_weights

def test_time_weights_detail():
    """详细展示时间权重的计算过程"""
    print("=" * 80)
    print("时间权重计算过程详解")
    print("=" * 80)
    
    # 创建简单的3天测试数据，每天只有少量点便于观察
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    
    all_timestamps = []
    for day in range(3):
        day_start = start_time + timedelta(days=day)
        # 每天只有5个点，便于观察
        day_timestamps = [day_start + timedelta(hours=i*2) for i in range(5)]
        all_timestamps.extend(day_timestamps)
    
    n_points = len(all_timestamps)
    
    # 生成简单的测试数据
    np.random.seed(42)
    y_true = np.random.uniform(100, 200, n_points)
    y_pred = y_true + np.random.normal(0, 10, n_points)
    
    print(f"测试数据:")
    print(f"  总共 {n_points} 个数据点，分布在3天")
    print(f"  每天5个点，时间间隔2小时")
    print(f"  时间范围: {all_timestamps[0]} 到 {all_timestamps[-1]}")
    print()
    
    # 手动展示权重计算过程
    print("🔍 手动计算时间权重过程:")
    
    # 转换为DataFrame
    df = pd.DataFrame({
        'timestamp': pd.to_datetime(all_timestamps),
        'y_true': y_true,
        'y_pred': y_pred
    })
    
    # 计算时间差（小时）
    latest_time = df['timestamp'].max()
    time_deltas_hours = []
    for t in df['timestamp']:
        delta = (latest_time - t).total_seconds() / 3600
        time_deltas_hours.append(delta)
    
    print(f"各数据点距离最新时间的小时数: {time_deltas_hours}")
    
    # 计算原始时间权重
    time_decay = 0.9
    max_delta = max(time_deltas_hours)
    raw_weights = [time_decay ** (delta / max_delta) for delta in time_deltas_hours]
    print(f"原始时间权重 (time_decay^(delta/max_delta)): {[f'{w:.6f}' for w in raw_weights]}")
    
    # 归一化权重
    normalized_weights = np.array(raw_weights) / sum(raw_weights)
    print(f"归一化后的时间权重 (总和=1): {[f'{w:.6f}' for w in normalized_weights]}")
    print(f"归一化权重总和: {sum(normalized_weights):.6f}")
    print()
    
    # 按天分组展示
    df['date'] = df['timestamp'].dt.date
    df['time_weight'] = normalized_weights
    
    print("🔍 按天分组的权重分布:")
    for date, group in df.groupby('date'):
        day_weights = group['time_weight'].values
        avg_weight = np.mean(day_weights)
        print(f"  {date}: 权重={[f'{w:.6f}' for w in day_weights]}, 平均={avg_weight:.6f}")
    print()
    
    # 调用实际函数
    print("🔍 调用实际函数:")
    score, rmse, k, weighted_rmse, weighted_k = evaluate_with_time_weights(
        y_true, y_pred, all_timestamps, 
        rmse_weight=0.2, k_weight=0.8, time_decay=0.9, points_per_day=96
    )
    
    print()
    print("=" * 80)
    print("总结:")
    print(f"- 每个数据点的权重很小是因为要在{n_points}个点中分配")
    print(f"- 每天的平均权重看起来小，但经过第二次归一化后变成合理的相对权重")
    print(f"- 最终的时间加权K值: {weighted_k:.4f}")
    print("=" * 80)

if __name__ == "__main__":
    test_time_weights_detail() 