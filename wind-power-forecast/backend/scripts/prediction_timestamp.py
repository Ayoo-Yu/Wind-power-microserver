import pandas as pd
import os
from flask import current_app
def post_process_predictions(original_data_path, predictions_path):

    # 读取原始数据集和预测数据集
    original_data = pd.read_csv(original_data_path)
    predictions = pd.read_csv(predictions_path)
    
    # 检查数据完整性
    required_original_columns = {'wp_true', 'Timestamp'}
    if not required_original_columns.issubset(original_data.columns):
        missing = required_original_columns - set(original_data.columns)
        raise ValueError(f"原始数据集缺少列: {', '.join(missing)}。")
    
    required_predictions_columns = {'Actual Power', 'Predicted Power'}
    if not required_predictions_columns.issubset(predictions.columns):
        missing = required_predictions_columns - set(predictions.columns)
        raise ValueError(f"预测数据集缺少列: {', '.join(missing)}。")
    
    # 初始化用于记录匹配位置的变量
    last_matched_index = 0  # 记录上一次匹配的起始位置
    
    # 定义一个函数来顺序查找最佳匹配时间戳
    def find_sequential_timestamp(target_value, next_target_value=None):
        nonlocal last_matched_index
        # 从上一次匹配的位置开始查找
        for idx in range(last_matched_index, len(original_data) - (1 if next_target_value else 0)):
            # 检查是否匹配当前值和下一行值（如果有要求）
            if original_data.at[idx, 'wp_true'] == target_value:
                if next_target_value is None or (idx + 1 < len(original_data) and original_data.at[idx + 1, 'wp_true'] == next_target_value):
                    last_matched_index = idx + 1  # 更新匹配位置
                    return original_data.at[idx, 'Timestamp']
        return None
    
    # 应用函数找到最佳时间戳
    timestamps = []
    for i in range(len(predictions) - 1):
        current_actual = predictions.at[i, 'Actual Power']
        next_actual = predictions.at[i + 1, 'Actual Power']
        timestamp = find_sequential_timestamp(current_actual, next_actual)
        timestamps.append(timestamp)
    
    # 对于最后一行，只使用单行匹配
    last_actual = predictions.iloc[-1]['Actual Power']
    last_timestamp = find_sequential_timestamp(last_actual)
    timestamps.append(last_timestamp)
    
    # 将找到的时间戳添加到预测数据集中
    predictions['Timestamp'] = timestamps
    
    # 检查是否有未找到的时间戳
    missing_timestamps = predictions['Timestamp'].isnull().sum()
    if missing_timestamps > 0:
        current_app.logger.warning(f"有 {missing_timestamps} 条记录未找到对应的时间戳。")
    
    # 固定字符串
    suffix = "timestamp"

    # 拆分路径和文件名
    base, ext = os.path.splitext(predictions_path)

    # 拼接新的路径
    new_predictions_path = f"{base}_{suffix}{ext}"

    # 保存文件
    predictions.to_csv(new_predictions_path, index=False)
    
    current_app.logger.info(f"已经为测试集预测结果匹配时间戳 '{new_predictions_path}'")

    return new_predictions_path
