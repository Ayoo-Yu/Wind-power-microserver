# data_processor.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from .config import LAGS

lags = LAGS


def _normalize_column_name(column_name: str) -> str:
    """去除列名首尾空格并保持原大小写用于比较。"""
    return column_name.strip() if isinstance(column_name, str) else ''


def _resolve_required_column(data: pd.DataFrame, target: str, aliases=None) -> str:
    """
    查找并标准化必需列名称。如果找到别名则重命名为目标列名。
    未找到时抛出 KeyError。
    """
    aliases = aliases or []
    normalized_map = {_normalize_column_name(col).lower(): col for col in data.columns}
    search_keys = [_normalize_column_name(target).lower()] + [
        _normalize_column_name(alias).lower() for alias in aliases
    ]

    for key in search_keys:
        if key in normalized_map:
            original = normalized_map[key]
            if original != target:
                data.rename(columns={original: target}, inplace=True)
            return target

    raise KeyError(target)


def _resolve_optional_column(data: pd.DataFrame, target: str, aliases=None):
    """查找并标准化可选列名称，未找到返回 None。"""
    try:
        return _resolve_required_column(data, target, aliases)
    except KeyError:
        return None


def load_data(file_path):
    """
    加载数据并处理NaN值，顺便清理列名首尾空格。
    """
    data = pd.read_csv(file_path)
    cleaned_mapping = {col: _normalize_column_name(col) for col in data.columns}
    if any(new != old for old, new in cleaned_mapping.items()):
        data.rename(columns=cleaned_mapping, inplace=True)
    data = data.dropna()
    return data


def preprocess_data(data):
    """
    数据预处理：转换时间戳，提取时间特征，分离特征和目标变量。
    支持常见的时间戳别名，如 timestamp、time、datetime 等。
    """
    timestamp_col = _resolve_required_column(
        data,
        'Timestamp',
        aliases=['timestamp', 'time', 'datetime', 'date']
    )
    data[timestamp_col] = pd.to_datetime(data[timestamp_col])
    data['Year'] = data[timestamp_col].dt.year
    data['Month'] = data[timestamp_col].dt.month
    data['Day'] = data[timestamp_col].dt.day
    data['Hour'] = data[timestamp_col].dt.hour

    wp_true_col = _resolve_required_column(
        data,
        'wp_true',
        aliases=['wp', 'actual_power', 'power', 'true_power']
    )

    ws_all_col = _resolve_optional_column(
        data,
        'ws_all',
        aliases=['wind_speed', 'ws']
    )

    exclusion_list = ['Timestamp', wp_true_col]
    if ws_all_col:
        exclusion_list.append(ws_all_col)

    features = [col for col in data.columns if col not in exclusion_list]
    X = data[features]
    y = data[wp_true_col].fillna(data[wp_true_col].mean())

    return X, y


def preprocess_data_pre(data):
    """
    数据预处理（预测阶段）：转换时间戳并保留时间序列。
    """
    timestamp_col = _resolve_required_column(
        data,
        'Timestamp',
        aliases=['timestamp', 'time', 'datetime', 'date']
    )
    data[timestamp_col] = pd.to_datetime(data[timestamp_col])
    data['Year'] = data[timestamp_col].dt.year
    data['Month'] = data[timestamp_col].dt.month
    data['Day'] = data[timestamp_col].dt.day
    data['Hour'] = data[timestamp_col].dt.hour
    features = [col for col in data.columns if col not in ['Timestamp']]
    X = data[features]
    timestamps = data[timestamp_col]  # 保存时间戳
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