import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
# from sklearn.model_selection import train_test_split # Not used for sequential split
from sklearn.metrics import mean_squared_error
import lightgbm as lgb
import psutil
import os
import gc  # 添加垃圾回收模块
import pickle  # 用于保存特征重要性
import re  # 用于解析特征名

# 定义内存监控函数
def get_memory_usage():
    """返回当前进程的内存使用量（MB）"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return memory_info.rss / 1024 / 1024  # 转换为MB

# 记录初始内存
initial_memory = get_memory_usage()
print(f"初始内存占用: {initial_memory:.2f} MB")

# 加载数据
file_path = 'ecmwf_data_ws_beijing_15min_v3.csv'  # 替换为你的文件路径
data = pd.read_csv(file_path)
print(f"数据加载后内存占用: {get_memory_usage():.2f} MB (增加: {get_memory_usage() - initial_memory:.2f} MB)")

# 清洗数据，处理NaN值 (在原始数据加载后进行一次初步清理)
data['wp_true'] = data['wp_true'].fillna(data['wp_true'].mean())
data = data.dropna(subset=[col for col in data.columns if col != 'wp_true']) # Drop rows if features have NaN

# 1. 数据预处理
# 转换时间戳为日期时间格式，并提取年、月、日、小时等特征
data['Timestamp'] = pd.to_datetime(data['Timestamp'])
data['Year'] = data['Timestamp'].dt.year
data['Month'] = data['Timestamp'].dt.month
data['Day'] = data['Timestamp'].dt.day
data['Hour'] = data['Timestamp'].dt.hour

# 确保存储原始索引以便后续对齐 y (Reset index *after* initial cleaning and timestamp conversion)
data = data.reset_index(drop=True)

# 分离特征和目标变量 - 创建显式副本避免SettingWithCopyWarning
features = [col for col in data.columns if col not in ['Timestamp','wp_true']]
X = data[features].copy()  # 显式创建副本
y = data['wp_true'].copy() # 显式创建副本
timestamps = data['Timestamp'] # Store timestamps separately

# 记录转换前内存
before_conversion_memory = get_memory_usage()
print(f"类型转换前内存占用: {before_conversion_memory:.2f} MB")
print(f"转换前X数据类型: {X.dtypes.value_counts()}")
print(f"转换前X内存使用详情: {X.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")

# 内存优化：将X和y的数据类型从float64转换为float32
for col in X.select_dtypes(include=['float64']).columns:
    X[col] = X[col].astype(np.float32)
y = y.astype(np.float32)

# 记录转换后内存
after_conversion_memory = get_memory_usage()
print(f"类型转换后内存占用: {after_conversion_memory:.2f} MB (节省: {before_conversion_memory - after_conversion_memory:.2f} MB)")
print(f"转换后X数据类型: {X.dtypes.value_counts()}")
print(f"转换后X内存使用详情: {X.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")

# 按顺序拆分训练集和验证集
split_index = int(len(X) * 0.9)
X_train, X_val = X[:split_index].copy(), X[split_index:].copy()
y_train, y_val = y[:split_index].copy(), y[split_index:].copy()
# Keep track of the original timestamps corresponding to the validation set y_val
# The index of y_val matches the index in the `data` DataFrame at this point
val_timestamps_initial = timestamps[y_val.index]

print(f"数据分割后内存占用: {get_memory_usage():.2f} MB")

# --- 特征工程 ---
wind_speeds_10 = [f'ws10_{i}' for i in range(1, 16)]
wind_speeds_100 = [f'ws100_{i}' for i in range(1, 16)]
wind_speeds_200 = [f'ws200_{i}' for i in range(1, 16)]

# 特征工程前内存
before_feature_engineering = get_memory_usage()
print(f"特征工程前内存占用: {before_feature_engineering:.2f} MB")

# --- 特征工程 for Training Set ---
combined_features_train = {}
for wind_speeds in [wind_speeds_100, wind_speeds_200]:
    for i in range(len(wind_speeds)):
        for j in range(i + 1, len(wind_speeds)):
            combined_features_train[f'{wind_speeds[i]}_{wind_speeds[j]}_diff1'] = X_train[wind_speeds[i]] - X_train[wind_speeds[j]]

for wind_speeds in [wind_speeds_10]:
     for i in range(len(wind_speeds)):
         for k in range(len(wind_speeds_200)):
            combined_features_train[f'{wind_speeds[i]}_{wind_speeds_200[k]}_diff2'] = X_train[wind_speeds[i]] - X_train[wind_speeds_200[k]]

lag_features_train = {}
for lag in range(1, 4):
    for col in wind_speeds_10 + wind_speeds_100 + wind_speeds_200:
        lag_features_train[f'{col}_lag{lag}'] = X_train[col].shift(lag)

combined_features_df_train = pd.DataFrame(combined_features_train, index=X_train.index)
lag_features_df_train = pd.DataFrame(lag_features_train, index=X_train.index)
X_train_with_features = pd.concat([X_train, combined_features_df_train, lag_features_df_train], axis=1)

# --- 特征工程 for Validation Set ---
combined_features_val = {}
for wind_speeds in [wind_speeds_100, wind_speeds_200]:
    for i in range(len(wind_speeds)):
        for j in range(i + 1, len(wind_speeds)):
            combined_features_val[f'{wind_speeds[i]}_{wind_speeds[j]}_diff1'] = X_val[wind_speeds[i]] - X_val[wind_speeds[j]]

for wind_speeds in [wind_speeds_10]:
     for i in range(len(wind_speeds)):
         for k in range(len(wind_speeds_200)):
            combined_features_val[f'{wind_speeds[i]}_{wind_speeds_200[k]}_diff2'] = X_val[wind_speeds[i]] - X_val[wind_speeds_200[k]]

lag_features_val = {}
for lag in range(1, 4):
    for col in wind_speeds_10 + wind_speeds_100 + wind_speeds_200:
        lag_features_val[f'{col}_lag{lag}'] = X_val[col].shift(lag)

combined_features_df_val = pd.DataFrame(combined_features_val, index=X_val.index)
lag_features_df_val = pd.DataFrame(lag_features_val, index=X_val.index)
X_val_with_features = pd.concat([X_val, combined_features_df_val, lag_features_df_val], axis=1)

# 特征工程后内存
after_feature_engineering = get_memory_usage()
print(f"特征工程后内存占用: {after_feature_engineering:.2f} MB (增加: {after_feature_engineering - before_feature_engineering:.2f} MB)")

# 记录特征工程后新数据框的内存使用和数据类型
print(f"X_train_with_features转换前类型: {X_train_with_features.dtypes.value_counts()}")
print(f"X_train_with_features内存: {X_train_with_features.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
print(f"X_val_with_features内存: {X_val_with_features.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")

# 确保新生成的特征也是float32类型
before_type_conversion = get_memory_usage()
for col in X_train_with_features.select_dtypes(include=['float64']).columns:
    X_train_with_features[col] = X_train_with_features[col].astype(np.float32)
for col in X_val_with_features.select_dtypes(include=['float64']).columns:
    X_val_with_features[col] = X_val_with_features[col].astype(np.float32)
after_type_conversion = get_memory_usage()
print(f"X_train_with_features转换后类型: {X_train_with_features.dtypes.value_counts()}")
print(f"特征类型转换后内存: {after_type_conversion:.2f} MB (节省: {before_type_conversion - after_type_conversion:.2f} MB)")

# --- 处理因 Lag 特征引入的 NaN，并保持 X 和 y 对齐 ---
nan_indices_train = X_train_with_features[X_train_with_features.isnull().any(axis=1)].index
nan_indices_val = X_val_with_features[X_val_with_features.isnull().any(axis=1)].index

# 从 X 和 y 中同时删除这些行
X_train = X_train_with_features.drop(index=nan_indices_train)
y_train = y_train.drop(index=nan_indices_train) # Maintain alignment

X_val = X_val_with_features.drop(index=nan_indices_val)
y_val = y_val.drop(index=nan_indices_val) # Maintain alignment
feature_names = X_train.columns.tolist()
# 验证对齐
print(f"Aligned X_train shape: {X_train.shape}, y_train shape: {y_train.shape}")
print(f"Aligned X_val shape: {X_val.shape}, y_val shape: {y_val.shape}")
assert len(X_train) == len(y_train), "Training data X and y are misaligned!"
assert len(X_val) == len(y_val), "Validation data X and y are misaligned!"
# Note: y_val now contains the target values *after* removing NaNs,
# but importantly, it *retains the original index* from the `data` DataFrame
# for the rows that were kept.

# 记录处理NaN后的内存
print(f"删除NaN后内存占用: {get_memory_usage():.2f} MB")

# --- 标准化数据 ---
before_scaling = get_memory_usage()
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train).astype(np.float32)  # 确保缩放后的数据也是float32
X_val_scaled = scaler.transform(X_val).astype(np.float32)  # 确保缩放后的数据也是float32
after_scaling = get_memory_usage()
print(f"标准化后内存占用: {after_scaling:.2f} MB (变化: {after_scaling - before_scaling:.2f} MB)")

# --- 创建时间窗口 (优化版本，直接创建扁平化数组) ---
def create_flattened_windows_with_indices(X_scaled, y_series, window_size):
    """ 
    直接创建扁平化的2D窗口，避免3D数组的中间步骤，减少内存使用
    """
    num_samples = len(X_scaled) - window_size + 1
    num_features = X_scaled.shape[1]
    # 预分配内存 (float32!)
    X_flat = np.zeros((num_samples, window_size * num_features), dtype=np.float32)
    y_windows = np.zeros(num_samples, dtype=np.float32)
    y_indices = np.zeros(num_samples, dtype=np.int64)  # 通常索引是int64

    original_indices = y_series.index
    y_values = y_series.values

    for i in range(num_samples):
        window = X_scaled[i : i + window_size]
        X_flat[i] = window.reshape(1, -1)  # 扁平化窗口
        target_y_index_in_series = i + window_size - 1
        y_windows[i] = y_values[target_y_index_in_series]
        y_indices[i] = original_indices[target_y_index_in_series]

    return X_flat, y_windows, y_indices

# 使用时间窗口大小为16
window_size = 16

# 记录窗口创建前内存
before_windowing = get_memory_usage()
print(f"窗口创建前内存占用: {before_windowing:.2f} MB")

# 使用优化后的函数直接创建扁平化窗口
X_train_flat, y_train_windows, _ = create_flattened_windows_with_indices(
    X_train_scaled, y_train, window_size
)
X_val_flat, y_val_windows, y_val_target_indices = create_flattened_windows_with_indices(
    X_val_scaled, y_val, window_size
)

# 清理不再需要的数据以释放内存
del X_train_scaled, X_val_scaled
gc.collect()

# 记录窗口创建后内存
after_windowing = get_memory_usage()
print(f"窗口(扁平化)创建后内存占用: {after_windowing:.2f} MB (增加: {after_windowing - before_windowing:.2f} MB)")
print(f"X_train_flat内存: {X_train_flat.nbytes / 1024 / 1024:.2f} MB")
print(f"X_val_flat内存: {X_val_flat.nbytes / 1024 / 1024:.2f} MB")

print(f"Flattened X_train shape: {X_train_flat.shape}, y_train shape: {y_train_windows.shape}")
print(f"Flattened X_val shape: {X_val_flat.shape}, y_val shape: {y_val_windows.shape}, indices shape: {y_val_target_indices.shape}")
# 打印数据类型以确认内存优化
print(f"X_train_flat dtype: {X_train_flat.dtype}")
print(f"y_train_windows dtype: {y_train_windows.dtype}")

# --- 特征选择逻辑 ---
# 获取完整的特征名列表（用于后续特征选择）
original_feature_names = X_train.columns.tolist()
print(f"原始特征数量: {len(original_feature_names)}")

# 生成扁平化特征名称
flat_feature_names = []
for i in range(window_size):
    time_lag_label = window_size - 1 - i # Goes from 15 down to 0 for window_size=16
    for name in original_feature_names:
        flat_feature_names.append(f"{name}_t-{time_lag_label}")

print(f"扁平化后特征数量: {len(flat_feature_names)}")

# 尝试加载预先计算的特征重要性（如果有的话）
feature_importance_file = 'feature_importance.pkl'
try:
    with open(feature_importance_file, 'rb') as f:
        feature_importance_dict = pickle.load(f)
    print("加载了预先计算的特征重要性")
    # 从导入的数据中重建特征重要性DataFrame
    feature_importance_df = pd.DataFrame({
        'feature': feature_importance_dict['features'],
        'importance': feature_importance_dict['importances']
    }).sort_values(by='importance', ascending=False)
    has_feature_importance = True
except (FileNotFoundError, EOFError, pickle.UnpicklingError):
    print("没有找到预先计算的特征重要性，将在模型训练后计算")
    feature_importance_df = None
    has_feature_importance = False

# 定义特征选择函数
def select_features_by_importance(X_flat, top_n=5000):
    """根据特征重要性选择前N个特征"""
    if not has_feature_importance or feature_importance_df is None:
        print(f"没有特征重要性信息，无法选择特征。返回所有特征。")
        return X_flat
    
    top_features = feature_importance_df.head(top_n)['feature'].values
    # 获取特征在flat_feature_names中的索引
    selected_indices = [flat_feature_names.index(feature) for feature in top_features]
    # 选择这些索引对应的列
    X_flat_selected = X_flat[:, selected_indices]
    print(f"基于重要性选择了{top_n}个特征，形状变为: {X_flat_selected.shape}")
    return X_flat_selected, selected_indices

def select_features_by_type(X_flat, feature_type='original_only'):
    """根据特征类型选择特征"""
    selected_indices = []
    
    if feature_type == 'original_only':
        # 只选择原始特征（所有时间步）
        pattern = r'^(?!.*_lag|.*_diff).*$'  # 不包含_lag或_diff的特征
    elif feature_type == 'lag1_only':
        # 只选择lag1特征
        pattern = r'.*_lag1_t-\d+$'
    elif feature_type == 'important_diff':
        # 重要的diff特征（这里需要根据具体情况调整）
        pattern = r'.*_diff\d+_t-\d+$'
    else:
        print(f"未知的特征类型: {feature_type}，返回所有特征")
        return X_flat, list(range(X_flat.shape[1]))
    
    # 找到匹配模式的特征索引
    for i, feature_name in enumerate(flat_feature_names):
        if re.match(pattern, feature_name):
            selected_indices.append(i)
    
    # 如果没有找到匹配的特征，返回原始特征
    if not selected_indices:
        print(f"未找到匹配'{feature_type}'的特征，返回所有特征")
        return X_flat, list(range(X_flat.shape[1]))
    
    # 选择这些索引对应的列
    X_flat_selected = X_flat[:, selected_indices]
    print(f"基于类型'{feature_type}'选择了{len(selected_indices)}个特征，形状变为: {X_flat_selected.shape}")
    return X_flat_selected, selected_indices

# 选择特征策略模式：'importance', 'type', 'none'
feature_selection_strategy = 'importance'  # 可以修改为其他策略
top_n_features = 3000  # 重要性策略下选择的特征数量
feature_type = 'original_only'  # 类型策略下选择的特征类型

# 应用特征选择
if feature_selection_strategy == 'importance' and has_feature_importance:
    X_train_flat_selected, selected_indices = select_features_by_importance(X_train_flat, top_n=top_n_features)
    X_val_flat_selected = X_val_flat[:, selected_indices]
    # 更新扁平化特征名
    flat_feature_names_selected = [flat_feature_names[i] for i in selected_indices]
    
    # 删除原始的大型数组以释放内存
    del X_train_flat, X_val_flat
    gc.collect()
    
elif feature_selection_strategy == 'type':
    X_train_flat_selected, selected_indices = select_features_by_type(X_train_flat, feature_type=feature_type)
    X_val_flat_selected = X_val_flat[:, selected_indices]
    # 更新扁平化特征名
    flat_feature_names_selected = [flat_feature_names[i] for i in selected_indices]
    
    # 删除原始的大型数组以释放内存
    del X_train_flat, X_val_flat
    gc.collect()
    
else:
    # 不做特征选择
    X_train_flat_selected = X_train_flat
    X_val_flat_selected = X_val_flat
    flat_feature_names_selected = flat_feature_names
    # 这里不删除原始数组，因为它们就是我们要使用的数组

# 记录特征选择后的内存使用
after_feature_selection = get_memory_usage()
print(f"特征选择后内存占用: {after_feature_selection:.2f} MB (变化: {after_feature_selection - after_windowing:.2f} MB)")
print(f"X_train_flat_selected内存: {X_train_flat_selected.nbytes / 1024 / 1024:.2f} MB")
print(f"X_val_flat_selected内存: {X_val_flat_selected.nbytes / 1024 / 1024:.2f} MB")
print(f"Selected features shape: train={X_train_flat_selected.shape}, val={X_val_flat_selected.shape}")

# --- 模型训练与评估 ---
params_list = [
    # (Params lists remain the same as before)
    {
        'boosting_type': 'gbdt', 'objective': 'regression', 'metric': 'rmse', 'num_leaves': 31,
        'learning_rate': 0.05, 'feature_fraction': 0.9, 'random_state': 42
    },
    # {
    #     'boosting_type': 'dart', 'objective': 'regression', 'metric': 'rmse', 'num_leaves': 31,
    #     'learning_rate': 0.05, 'feature_fraction': 0.9, 'drop_rate': 0.1, 'random_state': 42
    # },
    {
        'boosting_type': 'goss', 'objective': 'regression', 'metric': 'rmse', 'num_leaves': 31,
        'learning_rate': 0.05, 'feature_fraction': 0.9, 'top_rate': 0.2, 'other_rate': 0.1, 'random_state': 42
    }
]
results_dict = {}

# X_train_flat和X_val_flat已经是扁平化的，不需要再reshape

print(f"使用特征选择后的形状: X_train={X_train_flat_selected.shape}, X_val={X_val_flat_selected.shape}")
print(f"X_train_flat_selected dtype: {X_train_flat_selected.dtype}")
print(f"X_val_flat_selected dtype: {X_val_flat_selected.dtype}")

# 记录训练前内存峰值
before_training = get_memory_usage()
print(f"训练前内存占用: {before_training:.2f} MB")

# 记录峰值内存变量
peak_memory = before_training

for params in params_list:
    model_name = params['boosting_type'].upper()
    print(f"\n--- Training {model_name} model ---")
    current_params = params.copy()
    model = lgb.LGBMRegressor(**current_params)
    model.fit(X_train_flat_selected, y_train_windows,
              eval_set=[(X_val_flat_selected, y_val_windows)],
              eval_metric='rmse',
              callbacks=[lgb.early_stopping(10, verbose=True)])
    
    # 检查和更新峰值内存
    current_memory = get_memory_usage()
    if current_memory > peak_memory:
        peak_memory = current_memory
    print(f"{model_name}训练后内存占用: {current_memory:.2f} MB")

    y_pred = model.predict(X_val_flat_selected)
    mse = mean_squared_error(y_val_windows, y_pred)
    rmse = np.sqrt(mse)

    results_dict[model_name] = {
        'model': model,
        'y_pred': y_pred,
        'mse': mse,
        'rmse': rmse
    }
    print(f"{model_name} Validation Mean Squared Error: {mse}")
    print(f"{model_name} Validation Root Mean Squared Error: {rmse}")
    
    # 如果是第一次运行且没有预先计算的特征重要性，保存特征重要性
    if not has_feature_importance and feature_importance_df is None:
        importances = model.feature_importances_
        # 确保长度匹配
        if len(flat_feature_names_selected) == len(importances):
            feature_importance_dict = {
                'features': flat_feature_names_selected,
                'importances': importances
            }
            with open(feature_importance_file, 'wb') as f:
                pickle.dump(feature_importance_dict, f)
            print(f"已保存特征重要性到{feature_importance_file}")
            
            # 创建特征重要性DataFrame供当前使用
            feature_importance_df = pd.DataFrame({
                'feature': flat_feature_names_selected,
                'importance': importances
            }).sort_values(by='importance', ascending=False)
            has_feature_importance = True

# 记录训练结束后内存
after_training = get_memory_usage()
print(f"\n训练结束后内存占用: {after_training:.2f} MB (训练期间变化: {after_training - before_training:.2f} MB)")
print(f"整个过程中的峰值内存占用: {peak_memory:.2f} MB")
print(f"与初始内存相比增加了: {peak_memory - initial_memory:.2f} MB")
print(f"特征选择策略: {feature_selection_strategy}")
if feature_selection_strategy == 'importance':
    print(f"选择的特征数量: {top_n_features}")
elif feature_selection_strategy == 'type':
    print(f"选择的特征类型: {feature_type}")


# --- 保存带时间戳的预测结果 ---

# Retrieve the actual timestamps using the indices collected during windowing
# Use the original `data` DataFrame and the collected `y_val_target_indices`
target_timestamps = data.loc[y_val_target_indices, 'Timestamp'].values

# Verify lengths before creating DataFrame
print(f"Length of target timestamps: {len(target_timestamps)}")
print(f"Length of actual y_val_windows: {len(y_val_windows)}")


for model_name, result in results_dict.items():
    print(f"Length of {model_name} predictions: {len(result['y_pred'])}")
    # Ensure all arrays have the same length (should be guaranteed by create_flattened_windows_with_indices)
    assert len(target_timestamps) == len(y_val_windows) == len(result['y_pred']), \
        f"Length mismatch for {model_name}: Timestamps={len(target_timestamps)}, Actual={len(y_val_windows)}, Pred={len(result['y_pred'])}"

    results_df = pd.DataFrame({
        'Timestamp': target_timestamps, # Add the timestamp column
        'Predicted Power': result['y_pred'],
        'Actual Power': y_val_windows
    })
    # Sort by timestamp just in case indices weren't perfectly sequential (though they should be here)
    results_df = results_df.sort_values(by='Timestamp')

    selection_suffix = f"_{feature_selection_strategy}"
    if feature_selection_strategy == 'importance':
        selection_suffix += f"_top{top_n_features}"
    elif feature_selection_strategy == 'type':
        selection_suffix += f"_{feature_type}"
        
    output_filename = f'{model_name}_predicted_vs_actual_power{selection_suffix}.csv'
    results_df.to_csv(output_filename, index=False)
    print(f"预测结果（含时间戳）已保存到 {output_filename}")


# --- 可视化结果 ---
plt.figure(figsize=(20, 10))

# Use the retrieved timestamps for the x-axis if desired, or stick to index plotting
# Plotting with index is often clearer for direct comparison over steps
plot_len = len(y_val_windows)
plot_indices = range(plot_len)
# plot_timestamps = target_timestamps # Alternative for x-axis

plt.plot(plot_indices, y_val_windows, label='Actual Power', linestyle='--', color='black', linewidth=2)

for model_name, result in results_dict.items():
    plt.plot(plot_indices, result['y_pred'],
             label=f"{model_name} Predicted Power (RMSE: {result['rmse']:.2f})",
             alpha=0.8)

plt.xlabel('Time Step Index (in validation window set)') # Or 'Timestamp' if using plot_timestamps
plt.ylabel('Power')
plt.title(f'Validation Set Power Predictions - {feature_selection_strategy.capitalize()} Feature Selection')
plt.legend()
plt.grid(True)

# 保存图像
plt.savefig(f'power_predictions_comparison{selection_suffix}.png')
print(f"图像已保存为 power_predictions_comparison{selection_suffix}.png")

# 显示图像
plt.show()

# --- Feature Importances ---
print("\n--- Feature Importances ---")

print(f"训练完成后特征数量: {len(flat_feature_names_selected)}")

# 为当前模型显示特征重要性
for model_name, result in results_dict.items():
    print(f"\n--- {model_name} Model ---")
    model = result['model']
    importances = model.feature_importances_

    print(f"Length of feature importance array from model: {len(importances)}") # Diagnostic print

    # --- Add a check here for safety ---
    if len(flat_feature_names_selected) != len(importances):
        raise ValueError(
            f"FATAL: Mismatch between generated flat feature names ({len(flat_feature_names_selected)}) "
            f"and model importances ({len(importances)}). "
            f"Check window_size ({window_size}) and feature selection."
        )
    # --- End check ---

    # 创建包含特征名称和重要性的 DataFrame using the *flattened* names
    current_feature_importance_df = pd.DataFrame({
        'feature': flat_feature_names_selected, # Use the correctly generated names
        'importance': importances
    })

    # 按重要性降序排序
    current_feature_importance_df = current_feature_importance_df.sort_values(by='importance', ascending=False)

    # 打印最重要的 N 个特征
    top_n = 30 # 你可以调整想显示的特征数量
    print(f"Top {top_n} features:")
    print(current_feature_importance_df.head(top_n))

    # 可视化最重要的 N 个特征
    plt.figure(figsize=(12, max(6, top_n / 2))) # 调整图形大小
    # Plot only the top N features for clarity
    top_features = current_feature_importance_df.head(top_n)
    plt.barh(top_features['feature'], top_features['importance'])
    plt.xlabel("Feature Importance (Gain/Split based)")
    plt.ylabel("Feature Name (OriginalFeature_TimeStepInWindow)")
    plt.title(f"{model_name} - Top {top_n} Feature Importances ({feature_selection_strategy})")
    plt.gca().invert_yaxis() # 将最重要的特征显示在顶部
    plt.tight_layout() # 调整布局防止标签重叠
    plt.savefig(f'{model_name}_top_{top_n}_feature_importance{selection_suffix}.png')
    print(f"{model_name} 的 Top {top_n} 特征重要性图已保存为 {model_name}_top_{top_n}_feature_importance{selection_suffix}.png")
    plt.show()

# 打印最终内存使用情况
final_memory = get_memory_usage()
print(f"\n最终内存占用: {final_memory:.2f} MB")
print(f"与初始内存相比净增加: {final_memory - initial_memory:.2f} MB")
print(f"内存峰值与最终内存差异: {peak_memory - final_memory:.2f} MB")
print(f"特征选择策略: {feature_selection_strategy}")
if feature_selection_strategy == 'importance':
    print(f"选择的特征数量: {top_n_features}, RMSE: {list(results_dict.values())[0]['rmse']:.4f}")
elif feature_selection_strategy == 'type':
    print(f"选择的特征类型: {feature_type}, RMSE: {list(results_dict.values())[0]['rmse']:.4f}")