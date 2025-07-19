#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基准特征统计数据指纹生成脚本
用于从授权场站的训练数据中生成feature_scaling_parameters.json文件
"""

import pandas as pd
import numpy as np
import json
import os
import sys
from datetime import datetime

def calculate_feature_stats(data_df, feature_columns):
    """
    计算特征的统计信息（均值和标准差）
    
    参数:
    data_df: pandas DataFrame，包含特征数据
    feature_columns: list，要计算统计信息的特征列名列表
    
    返回:
    dict: 特征统计信息字典
    """
    stats_dict = {}
    
    print(f"开始计算 {len(feature_columns)} 个特征的统计信息...")
    
    for i, feature in enumerate(feature_columns):
        if feature not in data_df.columns:
            print(f"警告: 特征 '{feature}' 在数据中不存在，跳过")
            continue
            
        feature_data = data_df[feature]
        
        # 过滤掉无效值
        valid_data = feature_data.dropna()
        
        if len(valid_data) == 0:
            print(f"警告: 特征 '{feature}' 没有有效数据，跳过")
            continue
            
        # 计算统计信息
        mean_val = float(valid_data.mean())
        std_val = float(valid_data.std())
        
        # 处理标准差为0的情况
        if std_val == 0:
            std_val = 1e-6  # 设置一个很小的值避免除零
            
        stats_dict[feature] = {
            "mean": round(mean_val, 6),
            "std": round(std_val, 6)
        }
        
        if (i + 1) % 500 == 0:
            print(f"已处理 {i + 1}/{len(feature_columns)} 个特征")
    
    print(f"完成统计计算，共生成 {len(stats_dict)} 个特征的统计信息")
    return stats_dict

def generate_baseline_fingerprint(csv_file_path, output_json_path, sample_ratio=1.0, prediction_type="short", adaptation_threshold=0.15):
    """
    从CSV文件生成基准特征统计数据指纹（增强版，支持自适应决策系统）
    
    参数:
    csv_file_path: str，输入的CSV数据文件路径
    output_json_path: str，输出的JSON文件路径
    sample_ratio: float，数据采样比例（0-1），用于大数据集
    prediction_type: str，预测类型（'short' 或 'middle'），用于生成对应的配置文件
    adaptation_threshold: float，自适应决策阈值（0-1），默认0.15表示15%的偏移阈值
    """
    
    print("=" * 60)
    print("基准特征统计数据指纹生成工具")
    print("=" * 60)
    
    # 检查输入文件
    if not os.path.exists(csv_file_path):
        print(f"错误：输入文件不存在: {csv_file_path}")
        return False
        
    print(f"输入文件: {csv_file_path}")
    print(f"输出文件: {output_json_path}")
    print(f"预测类型: {prediction_type}")
    print(f"采样比例: {sample_ratio}")
    print(f"自适应阈值: {adaptation_threshold}")
    print()
    
    try:
        # 读取数据
        print("正在读取数据文件...")
        data_df = pd.read_csv(csv_file_path)
        print(f"原始数据形状: {data_df.shape}")
        
        # 数据采样（如果需要）
        if sample_ratio < 1.0:
            print(f"正在进行 {sample_ratio*100:.1f}% 采样...")
            data_df = data_df.sample(frac=sample_ratio, random_state=42)
            print(f"采样后数据形状: {data_df.shape}")
        
        # 获取所有数值型特征列
        numeric_columns = data_df.select_dtypes(include=[np.number]).columns.tolist()
        
        # 排除一些不需要的列（如ID、时间戳等）
        exclude_patterns = ['id', 'ID', 'timestamp', 'Timestamp', 'time', 'Time', 'date', 'Date']
        feature_columns = []
        
        for col in numeric_columns:
            # 排除包含特定模式的列
            if not any(pattern.lower() in col.lower() for pattern in exclude_patterns):
                feature_columns.append(col)
        
        print(f"识别到 {len(feature_columns)} 个特征列用于统计计算")
        print(f"前10个特征列: {feature_columns[:10]}")
        
        if len(feature_columns) == 0:
            print("错误：没有找到有效的特征列")
            return False
        
        # 计算统计信息
        baseline_stats = calculate_feature_stats(data_df, feature_columns)
        
        if len(baseline_stats) == 0:
            print("错误：没有生成任何有效的统计信息")
            return False
        
        # 添加增强版元数据（支持自适应决策系统）
        output_data = {
            "metadata": {
                "generated_time": datetime.now().isoformat(),
                "source_file": os.path.basename(csv_file_path),
                "prediction_type": prediction_type,
                "total_features": len(baseline_stats),
                "data_rows": len(data_df),
                "sample_ratio": sample_ratio,
                "adaptation_threshold": adaptation_threshold,
                "auto_update_enabled": True,
                "backup_generations": 5,
                "last_update_time": datetime.now().isoformat(),
                "update_count": 0,
                "description": f"Baseline feature statistics with adaptive decision capability for {prediction_type} prediction",
                "version": "2.0_adaptive",
                "compatible_models": [prediction_type]
            },
            "feature_stats": baseline_stats,
            "decision_history": []
        }
        
        # 保存到JSON文件
        print(f"\n正在保存统计数据到: {output_json_path}")
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print("=" * 60)
        print("✅ 自适应基准数据指纹生成完成！")
        print(f"📁 输出文件: {output_json_path}")
        print(f"📊 特征数量: {len(baseline_stats)}")
        print(f"🎯 自适应阈值: {adaptation_threshold}")
        print(f"🔄 自动更新: 启用")
        print(f"💾 文件大小: {os.path.getsize(output_json_path) / 1024:.1f} KB")
        print("=" * 60)
        
        # 显示前几个特征的统计信息作为验证
        print("\n前5个特征的统计信息预览:")
        for i, (feature, stats) in enumerate(list(baseline_stats.items())[:5]):
            print(f"  {i+1}. {feature}: mean={stats['mean']:.3f}, std={stats['std']:.3f}")
        
        return True
        
    except Exception as e:
        print(f"错误：处理过程中出现异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """
    主函数 - 处理命令行参数或提供交互式输入
    """
    if len(sys.argv) >= 3:
        # 命令行模式
        csv_file = sys.argv[1]
        output_file = sys.argv[2]
        sample_ratio = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
        prediction_type = sys.argv[4] if len(sys.argv) > 4 else "short"
        adaptation_threshold = float(sys.argv[5]) if len(sys.argv) > 5 else 0.15
    else:
        # 交互式模式
        print("基准特征统计数据指纹生成工具")
        print("=" * 40)
        
        csv_file = input("请输入训练数据CSV文件路径: ").strip()
        if not csv_file:
            print("错误：必须提供CSV文件路径")
            return
        
        prediction_type = input("请输入预测类型 (short/middle, 默认short): ").strip()
        if not prediction_type:
            prediction_type = "short"
        elif prediction_type not in ['short', 'middle']:
            print("警告：预测类型必须是 'short' 或 'middle'，使用默认值 'short'")
            prediction_type = "short"
            
        output_file = input(f"请输入输出JSON文件路径 (默认: ./wind-power-forecast/backend-autopredict/config/feature_scaling_parameters_{prediction_type}.json): ").strip()
        if not output_file:
            output_file = f"./wind-power-forecast/backend-autopredict/config/feature_scaling_parameters_{prediction_type}.json"
            
        sample_input = input("请输入数据采样比例 (0-1, 默认1.0使用全部数据): ").strip()
        sample_ratio = float(sample_input) if sample_input else 1.0
        
        threshold_input = input("请输入自适应决策阈值 (0-1, 默认0.15表示15%偏移阈值): ").strip()
        adaptation_threshold = float(threshold_input) if threshold_input else 0.15
    
    # 执行生成
    success = generate_baseline_fingerprint(csv_file, output_file, sample_ratio, prediction_type, adaptation_threshold)
    
    if success:
        print("\n🎉 自适应基准指纹生成完成！现在可以将JSON文件部署到目标系统中。")
        print("⚠️  重要提醒：")
        print("   1. 请确保此JSON文件基于授权场站的真实数据生成")
        print("   2. 生成后请妥善保管原始数据和此配置文件")
        print("   3. 部署时请确认文件路径与代码中的路径一致")
        print(f"   4. 此配置文件适用于 {prediction_type} 预测，请勿混用")
        print(f"   5. 自适应阈值设置为 {adaptation_threshold}，可根据实际情况调整")
        print("   6. 系统将自动学习和更新基准指纹，实现智能适应")
    else:
        print("\n❌ 生成失败，请检查输入文件和参数")

if __name__ == "__main__":
    main() 