# data_processor.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from .config import LAGS

lags = LAGS
def load_data(file_path):
    """
    加载数据并处理NaN值
    """
    data = pd.read_csv(file_path)
    data = data.dropna()
    return data

def preprocess_data(data):
    """
    数据预处理：转换时间戳，提取时间特征，分离特征和目标变量
    """
    data['Timestamp'] = pd.to_datetime(data['Timestamp'])
    data['Year'] = data['Timestamp'].dt.year
    data['Month'] = data['Timestamp'].dt.month
    data['Day'] = data['Timestamp'].dt.day
    data['Hour'] = data['Timestamp'].dt.hour
    features = [col for col in data.columns if col not in ['Timestamp','wp_true','ws_all']]
    X = data[features]
    y = data['wp_true'].fillna(data['wp_true'].mean())
    
    return X, y

def preprocess_data_pre(data):
    """
    数据预处理：转换时间戳，提取时间特征，分离特征和目标变量
    """
    data['Timestamp'] = pd.to_datetime(data['Timestamp'])
    data['Year'] = data['Timestamp'].dt.year
    data['Month'] = data['Timestamp'].dt.month
    data['Day'] = data['Timestamp'].dt.day
    data['Hour'] = data['Timestamp'].dt.hour
    features = [col for col in data.columns if col not in ['Timestamp']]
    X = data[features]
    timestamps = data['Timestamp']  # 保存时间戳
    return X, timestamps

def split_data(X, y, train_ratio=0.9):
    """
    按顺序拆分训练集和验证集
    """
    split_index = int(len(X) * train_ratio)
    X_train, X_val = X[:split_index], X[split_index:]
    y_train, y_val = y[:split_index], y[split_index:]
    return X_train, X_val, y_train, y_val

def feature_engineering(X_train, X_val, lags):
    """
    特征工程：特征组合、滞后特征等
    """
    # Attempt to identify wind speed columns, default to empty lists if not found
    ws10_cols = [col for col in X_train.columns if col.startswith('ws10_')]
    ws100_cols = [col for col in X_train.columns if col.startswith('ws100_')]
    ws200_cols = [col for col in X_train.columns if col.startswith('ws200_')]

    wind_speeds_10 = sorted(ws10_cols) # Sort to ensure consistent feature naming if order matters
    wind_speeds_100 = sorted(ws100_cols)
    wind_speeds_200 = sorted(ws200_cols)
    
    combined_features_train = {}
    
    # 生成高度100和200的风速差异特征
    # This loop iterates first with wind_speeds_100, then with wind_speeds_200
    for current_wind_speeds in [wind_speeds_100, wind_speeds_200]:
        if not current_wind_speeds: # Skip if no columns for this height
            continue
        for i in range(len(current_wind_speeds)):
            for j in range(i + 1, len(current_wind_speeds)):
                col_i = current_wind_speeds[i]
                col_j = current_wind_speeds[j]
                if col_i in X_train.columns and col_j in X_train.columns:
                    combined_features_train[f'{col_i}_{col_j}_diff1'] = X_train[col_i] - X_train[col_j]
    
    # 生成高度10和200的风速差异特征
    # This loop iterates first with wind_speeds_10, then with wind_speeds_200
    for current_wind_speeds in [wind_speeds_10, wind_speeds_200]:
        if not current_wind_speeds: # Skip if no columns for this height
            continue
        for i in range(len(current_wind_speeds)):
            for j in range(i + 1, len(current_wind_speeds)):
                col_i = current_wind_speeds[i]
                col_j = current_wind_speeds[j]
                if col_i in X_train.columns and col_j in X_train.columns:
                     combined_features_train[f'{col_i}_{col_j}_diff2'] = X_train[col_i] - X_train[col_j]
    
    # 引入滞后风速特征
    lag_features_train = {}
    all_present_wind_speeds = wind_speeds_10 + wind_speeds_100 + wind_speeds_200
    
    if all_present_wind_speeds: # Only proceed if there are any wind speed columns
        for lag in range(1, lags):
            for col in all_present_wind_speeds:
                if col in X_train.columns: # Double check, though they should be from X_train.columns
                    lag_features_train[f'{col}_lag{lag}'] = X_train[col].shift(lag)
    
    dataframes_to_concat_train = [X_train]
    if combined_features_train:
        combined_features_df_train = pd.DataFrame(combined_features_train, index=X_train.index)
        dataframes_to_concat_train.append(combined_features_df_train)
    if lag_features_train:
        lag_features_df_train = pd.DataFrame(lag_features_train, index=X_train.index)
        dataframes_to_concat_train.append(lag_features_df_train)
    
    if len(dataframes_to_concat_train) > 1:
        X_train = pd.concat(dataframes_to_concat_train, axis=1).dropna()
    
    # 对验证集进行相同的特征工程处理
    combined_features_val = {}
    lag_features_val = {}

    # Replicate for validation set - using the same column lists derived from X_train
    for current_wind_speeds in [wind_speeds_100, wind_speeds_200]:
        if not current_wind_speeds:
            continue
        for i in range(len(current_wind_speeds)):
            for j in range(i + 1, len(current_wind_speeds)):
                col_i = current_wind_speeds[i]
                col_j = current_wind_speeds[j]
                if col_i in X_val.columns and col_j in X_val.columns:
                    combined_features_val[f'{col_i}_{col_j}_diff1'] = X_val[col_i] - X_val[col_j]
    
    for current_wind_speeds in [wind_speeds_10, wind_speeds_200]:
        if not current_wind_speeds:
            continue
        for i in range(len(current_wind_speeds)):
            for j in range(i + 1, len(current_wind_speeds)):
                col_i = current_wind_speeds[i]
                col_j = current_wind_speeds[j]
                if col_i in X_val.columns and col_j in X_val.columns:
                    combined_features_val[f'{col_i}_{col_j}_diff2'] = X_val[col_i] - X_val[col_j]
    
    if all_present_wind_speeds:
        for lag in range(1, lags):
            for col in all_present_wind_speeds:
                if col in X_val.columns:
                    lag_features_val[f'{col}_lag{lag}'] = X_val[col].shift(lag)
    
    dataframes_to_concat_val = [X_val]
    if combined_features_val:
        combined_features_df_val = pd.DataFrame(combined_features_val, index=X_val.index)
        dataframes_to_concat_val.append(combined_features_df_val)
    if lag_features_val:
        lag_features_df_val = pd.DataFrame(lag_features_val, index=X_val.index)
        dataframes_to_concat_val.append(lag_features_df_val)
    
    if len(dataframes_to_concat_val) > 1:
        X_val = pd.concat(dataframes_to_concat_val, axis=1).dropna()
    
    return X_train, X_val

def scale_data(X_train, X_val):
    """
    标准化数据
    """
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    return X_train_scaled, X_val_scaled, scaler

def create_time_window(X, y, window_size):
    """
    创建时间窗口
    """
    X_windows = []
    y_windows = []
    for i in range(len(X) - window_size + 1):
        X_windows.append(X[i:i + window_size])
        y_windows.append(y[i + window_size + lags-2])  # 注意这里的索引
    return np.array(X_windows), np.array(y_windows)

def create_time_window_pre(X, window_size):
    """
    创建时间窗口
    """
    X_windows = []
    for i in range(len(X) - window_size + 1):
        X_windows.append(X[i:i + window_size])
    return np.array(X_windows)