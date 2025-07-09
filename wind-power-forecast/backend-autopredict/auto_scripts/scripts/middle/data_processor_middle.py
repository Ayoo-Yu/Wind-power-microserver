# data_processor_middle.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
# from config import LAGS # Old import

import datetime
import gc  # 添加垃圾回收模块
import logging
import os # Added for file operations
# import sys # Removed sys.path manipulation from here

# --- Removed sys.path modification block from here ---

# --- DB Imports Start --- 
# Restore the try...except block for robustness # Re-commenting out for debugging
# try: 
from sqlalchemy.orm import Session 
from db_models import TrainPreMiddle, ActualPower 
from db_session import db_session 
DB_ACCESS_AVAILABLE = True # Assume true, let import fail explicitly
# except ImportError as e:
#    logging.error(f"数据库相关模块导入失败 (检查路径和依赖项): {e}. CSV更新功能将不可用。", exc_info=True) 
#    DB_ACCESS_AVAILABLE = False
# --- DB Imports End ---

lags = 4

def interpolate_and_ffill_wp_true(df, wp_true_col='wp_true'):
    """
    处理wp_true列中的空值：
    1. 先使用线性插值处理中间的空值(有前后值的情况)
    2. 对序列开头的空值使用后向填充(bfill)
    3. 对序列末尾的空值使用前向填充(ffill)
    
    Args:
        df (pd.DataFrame): 包含wp_true列的数据框
        wp_true_col (str): 列名，默认为'wp_true'
        
    Returns:
        pd.DataFrame: 处理后的数据框副本
    """
    if wp_true_col not in df.columns:
        logging.warning(f"'{wp_true_col}'列不存在，无法进行插值和填充处理")
        return df
        
    # 创建副本，避免修改原始数据
    result_df = df.copy()
    
    # 记录处理前的空值数量
    nan_before = result_df[wp_true_col].isna().sum()
    if nan_before == 0:
        logging.info(f"'{wp_true_col}'列没有空值，不需要处理")
        return result_df
        
    # 确保时间戳列是日期时间类型并且已排序
    if 'Timestamp' in result_df.columns:
        if not pd.api.types.is_datetime64_dtype(result_df['Timestamp']):
            result_df['Timestamp'] = pd.to_datetime(result_df['Timestamp'])
        result_df = result_df.sort_values('Timestamp')
    
    # 步骤1: 对有前后值的空值进行线性插值
    result_df[wp_true_col] = result_df[wp_true_col].interpolate(method='linear')
    
    # 记录插值后的空值数量
    nan_after_interpolate = result_df[wp_true_col].isna().sum()
    interpolated_count = nan_before - nan_after_interpolate
    
    # 步骤2: 对序列开头的空值进行后向填充(bfill)
    bfill_count = 0
    if nan_after_interpolate > 0:
        # 检查开头是否有空值
        has_head_nan = False
        for i in range(len(result_df)):
            if pd.isna(result_df[wp_true_col].iloc[i]):
                has_head_nan = True
                break
            if not pd.isna(result_df[wp_true_col].iloc[i]):
                break
                
        if has_head_nan:
            # 记录后向填充前的空值数量
            nan_before_bfill = result_df[wp_true_col].isna().sum()
            # 对开头的空值进行后向填充
            result_df[wp_true_col] = result_df[wp_true_col].fillna(method='bfill')
            nan_after_bfill = result_df[wp_true_col].isna().sum()
            bfill_count = nan_before_bfill - nan_after_bfill
            
    # 步骤3: 对序列末尾的空值进行前向填充(ffill)
    ffill_count = 0
    if result_df[wp_true_col].isna().sum() > 0:
        # 记录前向填充前的空值数量
        nan_before_ffill = result_df[wp_true_col].isna().sum()
        # 对末尾的空值进行前向填充
        result_df[wp_true_col] = result_df[wp_true_col].fillna(method='ffill')
        nan_after_ffill = result_df[wp_true_col].isna().sum()
        ffill_count = nan_before_ffill - nan_after_ffill
    
    # 记录处理后的空值数量
    nan_after = result_df[wp_true_col].isna().sum()
    
    logging.info(f"'{wp_true_col}'列空值处理: 共{nan_before}个空值, "
                 f"线性插值处理了{interpolated_count}个, "
                 f"后向填充处理了{bfill_count}个, "
                 f"前向填充处理了{ffill_count}个, "
                 f"剩余{nan_after}个空值")
                 
    return result_df

def load_data(file_path):
    """
    加载数据并处理NaN值 (从CSV文件)
    """
    try:
        data = pd.read_csv(file_path)
        # 清洗数据，处理NaN值 (在原始数据加载后进行一次初步清理)
        if 'wp_true' in data.columns:
            # 使用插值和填充方法处理wp_true的空值，而不是均值填充
            data = interpolate_and_ffill_wp_true(data)
            # Drop rows if features have NaN (excluding wp_true)
            data.dropna(subset=[col for col in data.columns if col != 'wp_true'], inplace=True)
        else:
            # If wp_true is missing, maybe just drop all NaNs or handle differently
            logging.warning(f"CSV 文件 {file_path} 中缺少 'wp_true' 列。")
            data.dropna(inplace=True)
        # Drop record_id if it exists after loading
        if 'record_id' in data.columns:
            logging.info(f"从 CSV {file_path} 加载后删除 'record_id' 列")
            data.drop(columns=['record_id'], inplace=True)
        logging.info(f"成功从 {file_path} 加载 {len(data)} 条记录。")
        return data
    except FileNotFoundError:
        logging.error(f"训练 CSV 文件未找到: {file_path}")
        return pd.DataFrame() # Return empty DataFrame if file not found
    except Exception as e:
        logging.error(f"从 CSV 文件 {file_path} 加载数据时出错: {e}", exc_info=True)
        return pd.DataFrame()

def update_training_csv_from_db(csv_file_path):
    """
    从数据库获取新数据并更新本地训练 CSV 文件。

    Args:
        csv_file_path (str): 要更新的 CSV 文件的路径。

    Returns:
        bool: 如果更新（或检查无需更新）成功则返回 True，否则返回 False。
    """
    if not DB_ACCESS_AVAILABLE:
        logging.error("数据库模块不可用，无法更新 CSV 文件。")
        return False

    logging.info(f"开始检查并更新训练 CSV 文件: {csv_file_path}")
    latest_timestamp_in_csv = None
    existing_df = pd.DataFrame()
    file_exists = os.path.exists(csv_file_path)
    initial_creation = not file_exists

    # 1. 读取现有 CSV 并获取最新时间戳 (统一为大写 Timestamp)
    if file_exists:
        try:
            existing_df = pd.read_csv(csv_file_path)
            # Find timestamp column case-insensitively
            ts_col = None
            for col in existing_df.columns:
                if col.lower() == 'timestamp':
                    ts_col = col
                    break
            
            if not existing_df.empty and ts_col:
                # Standardize to uppercase 'Timestamp'
                if ts_col != 'Timestamp':
                    logging.info(f"将 CSV 列 '{ts_col}' 重命名为 'Timestamp'")
                    existing_df.rename(columns={ts_col: 'Timestamp'}, inplace=True)
                
                existing_df['Timestamp'] = pd.to_datetime(existing_df['Timestamp'])
                latest_timestamp_in_csv = existing_df['Timestamp'].max()
                logging.info(f"CSV 文件中最新的时间戳: {latest_timestamp_in_csv}")
            else:
                logging.warning(f"CSV 文件为空或缺少 'Timestamp' 列: {csv_file_path}")
                initial_creation = True # Treat as initial creation if empty/invalid
        except Exception as e:
            logging.error(f"读取现有 CSV 文件时出错: {csv_file_path} - {e}", exc_info=True)
            return False # Don't proceed if CSV is corrupted
    else:
        logging.info(f"CSV 文件不存在，将尝试从数据库获取所有数据创建: {csv_file_path}")

    # 2. 从数据库获取新数据
    features_new_df = pd.DataFrame()
    actual_new_df = pd.DataFrame()
    try:
        with db_session() as session:
            logging.info("正在查询数据库获取新数据...")
            # --- 查询 TrainPreMiddle (Assuming model uses uppercase 'Timestamp') --- 
            query_features = session.query(TrainPreMiddle)
            if latest_timestamp_in_csv is not None:
                logging.info(f"  筛选 train_pre_middle 时间戳 > {latest_timestamp_in_csv}")
                # Use uppercase Timestamp for filtering (assuming model attribute is uppercase)
                query_features = query_features.filter(TrainPreMiddle.Timestamp > latest_timestamp_in_csv)
            
            features_new_df = pd.read_sql(query_features.statement, session.bind)
            # Ensure the timestamp column is uppercase 'Timestamp'
            if 'timestamp' in features_new_df.columns and 'Timestamp' not in features_new_df.columns:
                 features_new_df.rename(columns={'timestamp': 'Timestamp'}, inplace=True)
            logging.info(f"从 train_pre_middle 获取了 {len(features_new_df)} 条新记录。")

            # --- 查询 ActualPower (Use lowercase 'timestamp' for query, then rename) --- 
            # Query using the correct lowercase attribute from the model
            query_actual = session.query(ActualPower.timestamp, ActualPower.wp_true) # Use lowercase model attribute
            if latest_timestamp_in_csv is not None:
                logging.info(f"  筛选 actual_power 时间戳 > {latest_timestamp_in_csv}")
                # Filter using the correct lowercase attribute from the model
                query_actual = query_actual.filter(ActualPower.timestamp > latest_timestamp_in_csv) 
            
            actual_new_df = pd.read_sql(query_actual.statement, session.bind)
            # Ensure the column name in the resulting DataFrame is uppercase 'Timestamp' for consistency
            if 'timestamp' in actual_new_df.columns and 'Timestamp' not in actual_new_df.columns:
                 logging.info("Renaming 'timestamp' column from ActualPower query to 'Timestamp'")
                 actual_new_df.rename(columns={'timestamp': 'Timestamp'}, inplace=True)
            elif 'Timestamp' not in actual_new_df.columns and len(actual_new_df.columns) > 0:
                 # If query didn't return expected names, try renaming first col
                 logging.warning("ActualPower query result missing 'Timestamp' after query, attempting rename of first column.")
                 actual_new_df.rename(columns={actual_new_df.columns[0]: 'Timestamp'}, inplace=True)
            
            logging.info(f"从 actual_power 获取了 {len(actual_new_df)} 条新记录。")

    except Exception as e:
        logging.error(f"从数据库查询新数据时出错: {e}", exc_info=True)
        return False # Return False if DB query fails

    # 3. 合并新数据
    if features_new_df.empty or actual_new_df.empty:
        logging.info("数据库中没有找到需要添加到 CSV 的新数据（或其中一个表为空）。")
        # Ensure the file exists even if no new data, especially if it was initial creation attempt
        if initial_creation and not os.path.exists(csv_file_path):
             logging.warning("数据库无数据，无法创建初始CSV文件。")
             # Depending on requirements, might return False or True here.
             # Returning True assuming it's not an error state if DB is just empty.
             return True
        return True # No new data is not an error

    logging.info("开始合并从数据库获取的新数据...")
    try:
        # Ensure timestamp columns exist and are datetime (use uppercase 'Timestamp')
        if 'Timestamp' not in features_new_df.columns:
             logging.error("从 TrainPreMiddle 获取的数据缺少 'Timestamp' 列")
             return False
        if 'Timestamp' not in actual_new_df.columns:
             logging.error("从 ActualPower 获取的数据缺少 'Timestamp' 列")
             return False
             
        features_new_df['Timestamp'] = pd.to_datetime(features_new_df['Timestamp'])
        actual_new_df['Timestamp'] = pd.to_datetime(actual_new_df['Timestamp'])

        # 内连接合并新数据 (use uppercase 'Timestamp')
        merged_new_data = pd.merge(features_new_df, actual_new_df, on='Timestamp', how='inner')
        logging.info(f"合并后得到 {len(merged_new_data)} 条新记录。")

        # ---> 新增：删除合并数据中的 record_id 列 <---
        if 'record_id' in merged_new_data.columns:
            logging.info("从合并的新数据中删除 'record_id' 列")
            merged_new_data.drop(columns=['record_id'], inplace=True)
        # --------------------------------------------

        if merged_new_data.empty:
            logging.info("合并后的新数据为空 (可能因为删除了 record_id 或时间戳不匹配)。") # 更新日志信息
            return True # Not an error

        # 清理新数据中的 NaN (使用插值和填充方法)
        if 'wp_true' in merged_new_data.columns:
            # 使用插值和填充方法处理wp_true的空值，而不是均值填充
            merged_new_data = interpolate_and_ffill_wp_true(merged_new_data)
            # Use uppercase Timestamp in subset check
            merged_new_data.dropna(subset=[col for col in merged_new_data.columns if col not in ['Timestamp', 'wp_true']], inplace=True) 
        else:
            logging.warning("合并的新数据中缺少 'wp_true' 列。")
            merged_new_data.dropna(inplace=True)
            
        # 确保新数据按时间戳排序 (Use uppercase 'Timestamp')
        merged_new_data.sort_values(by='Timestamp', inplace=True) 

    except Exception as e:
        logging.error(f"合并或清理新数据时出错: {e}", exc_info=True)
        return False

    # 4. 将新数据写入/追加到 CSV
    logging.info("将新数据写入/追加到 CSV 文件...")
    try:
        # Standardize column names to uppercase 'Timestamp' before writing/appending
        if 'timestamp' in merged_new_data.columns and 'Timestamp' not in merged_new_data.columns:
             merged_new_data.rename(columns={'timestamp': 'Timestamp'}, inplace=True)
             
        if initial_creation:
            merged_new_data.to_csv(csv_file_path, index=False, header=True)
            logging.info(f"已创建新的 CSV 文件并写入 {len(merged_new_data)} 条记录: {csv_file_path}")
        else:
            if not existing_df.empty:
                 # existing_df timestamp column was already renamed to 'Timestamp' above
                 existing_cols = existing_df.columns.tolist()
                 try:
                     # Ensure new data columns match existing, including uppercase 'Timestamp'
                     current_new_cols = merged_new_data.columns.tolist()
                     if 'timestamp' in current_new_cols and 'Timestamp' not in current_new_cols:
                         merged_new_data.rename(columns={'timestamp': 'Timestamp'}, inplace=True)
                         
                     merged_new_data = merged_new_data[existing_cols]
                 except KeyError as ke:
                     logging.error(f"新数据与现有CSV列不匹配: 缺少列 {ke}。现有列: {existing_cols}, 新数据列: {merged_new_data.columns.tolist()}。将不追加数据。")
                     return False 

            merged_new_data.to_csv(csv_file_path, mode='a', index=False, header=False)
            logging.info(f"已向 CSV 文件追加 {len(merged_new_data)} 条新记录: {csv_file_path}")
        
        return True # Update successful

    except Exception as e:
        logging.error(f"写入 CSV 文件时出错: {csv_file_path} - {e}", exc_info=True)
        return False

def filter_data_by_date(data, months_back=None):
    """
    根据月份数过滤数据
    
    参数:
    data: 输入的DataFrame，必须包含'Timestamp'列
    months_back: 往回追溯的月数，如1表示只用最近1个月的数据，None表示使用全部数据
    
    返回:
    过滤后的DataFrame
    """
    if months_back is None:
        return data
    
    # 确保Timestamp列是datetime类型
    if not pd.api.types.is_datetime64_any_dtype(data['Timestamp']):
        data['Timestamp'] = pd.to_datetime(data['Timestamp'])
    
    # 计算截止日期
    latest_date = data['Timestamp'].max()
    if months_back > 0:
        cutoff_date = latest_date - pd.DateOffset(months=months_back)
        return data[data['Timestamp'] >= cutoff_date]
    return data

def preprocess_data(data):
    """
    数据预处理：转换时间戳，提取时间特征，分离特征和目标变量
    增加数据类型优化减少内存占用
    """
    data['Timestamp'] = pd.to_datetime(data['Timestamp'])
    data['Year'] = data['Timestamp'].dt.year
    data['Month'] = data['Timestamp'].dt.month
    data['Day'] = data['Timestamp'].dt.day
    data['Hour'] = data['Timestamp'].dt.hour
    
    # 分离特征和目标变量 - 创建显式副本避免SettingWithCopyWarning
    features = [col for col in data.columns if col not in ['Timestamp','wp_true','ws_all']]
    X = data[features].copy() # 显式创建副本
    
    # 处理wp_true中的空值，使用插值和填充方法替代均值填充
    if 'wp_true' in data.columns:
        # 创建一个临时DataFrame，只包含Timestamp和wp_true
        temp_df = pd.DataFrame({'Timestamp': data['Timestamp'], 'wp_true': data['wp_true']})
        # 应用插值和填充
        temp_df = interpolate_and_ffill_wp_true(temp_df)
        # 提取处理后的wp_true列
        y = temp_df['wp_true'].copy()
    else:
        y = pd.Series(np.nan, index=data.index) # 创建一个空的Series
    
    # 内存优化：将X和y的数据类型从float64转换为float32
    for col in X.select_dtypes(include=['float64']).columns:
        X[col] = X[col].astype(np.float32)
    y = y.astype(np.float32)
    
    return X, y

def preprocess_data_pre(data):
    """
    数据预处理：转换时间戳，提取时间特征，分离特征和目标变量
    增加数据类型优化减少内存占用
    """
    data['Timestamp'] = pd.to_datetime(data['Timestamp'])
    data['Year'] = data['Timestamp'].dt.year
    data['Month'] = data['Timestamp'].dt.month
    data['Day'] = data['Timestamp'].dt.day
    data['Hour'] = data['Timestamp'].dt.hour
    
    # 分离特征和目标变量 - 创建显式副本避免SettingWithCopyWarning
    features = [col for col in data.columns if col not in ['Timestamp']]
    X = data[features].copy() # 显式创建副本
    
    # 内存优化：将X的数据类型从float64转换为float32
    for col in X.select_dtypes(include=['float64']).columns:
        X[col] = X[col].astype(np.float32)
    
    return X, data['Timestamp']

def split_data(X, y, train_ratio=0.9):
    """
    按顺序拆分训练集和验证集
    """
    split_index = int(len(X) * train_ratio)
    X_train, X_val = X[:split_index].copy(), X[split_index:].copy()
    y_train, y_val = y[:split_index].copy(), y[split_index:].copy()
    return X_train, X_val, y_train, y_val

def feature_engineering(X, lags):
    """
    特征工程：为单个DataFrame创建特征组合、滞后特征等。

    参数:
        X (pd.DataFrame): 输入的特征DataFrame。
        lags (int): 需要创建的滞后特征的最大阶数 (例如 lags=3 会创建 lag1, lag2, lag3)。

    返回:
        pd.DataFrame: 包含原始特征和工程特征的DataFrame。
        pd.Index: 由于滞后特征产生的NaN值的索引。
    """
    print(f"开始特征工程，输入维度: {X.shape}, lags: {lags}")
    logging.info(f"开始特征工程，输入维度: {X.shape}, lags: {lags}")
    X_processed = X.copy() # 使用副本进行操作

    # 动态确定风速点数量 (基于传入的 X)
    # 使用 setdefault 避免 KeyErrror，如果列不存在则 n_points 为 0
    n_points = len([col for col in X_processed.columns if col.startswith('ws10_')])
    if n_points == 0:
         print("警告: 未在输入数据中找到 'ws10_' 开头的列，无法生成风速相关特征工程。")
         logging.warning("警告: 未在输入数据中找到 'ws10_' 开头的列，无法生成风速相关特征工程。")
         # 如果没有风速特征，可能无法生成滞后和差异特征，需要决定如何处理
         # 这里选择继续，但后面依赖 wind_speeds_* 的代码可能不会执行

    wind_speeds_10 = [f'ws10_{i}' for i in range(1, n_points + 1)]
    wind_speeds_100 = [f'ws100_{i}' for i in range(1, n_points + 1)]
    wind_speeds_200 = [f'ws200_{i}' for i in range(1, n_points + 1)]

    # 检查需要的列是否存在
    required_cols_100 = [col for col in wind_speeds_100 if col not in X_processed.columns]
    required_cols_200 = [col for col in wind_speeds_200 if col not in X_processed.columns]
    required_cols_10 = [col for col in wind_speeds_10 if col not in X_processed.columns]

    if required_cols_100 or required_cols_200 or required_cols_10:
        missing_str = f"缺少风速列: {required_cols_100 + required_cols_200 + required_cols_10}"
        print(f"警告: {missing_str}。部分特征工程可能无法执行。")
        logging.warning(f"警告: {missing_str}。部分特征工程可能无法执行。")

    # -- 生成差异特征 --
    combined_features = {}

    # 高度100和200之间的差异
    valid_ws_100 = [col for col in wind_speeds_100 if col in X_processed.columns]
    valid_ws_200 = [col for col in wind_speeds_200 if col in X_processed.columns]
    valid_ws_10 = [col for col in wind_speeds_10 if col in X_processed.columns]

    if len(valid_ws_100) >= 2:
        for i in range(len(valid_ws_100)):
            for j in range(i + 1, len(valid_ws_100)):
                col1 = valid_ws_100[i]
                col2 = valid_ws_100[j]
                combined_features[f'{col1}_{col2}_diff1'] = X_processed[col1] - X_processed[col2]

    if len(valid_ws_200) >= 2:
         for i in range(len(valid_ws_200)):
            for j in range(i + 1, len(valid_ws_200)):
                col1 = valid_ws_200[i]
                col2 = valid_ws_200[j]
                combined_features[f'{col1}_{col2}_diff1'] = X_processed[col1] - X_processed[col2]

    # 高度10和200之间的差异
    if valid_ws_10 and valid_ws_200:
        for col10 in valid_ws_10:
            for col200 in valid_ws_200:
                 combined_features[f'{col10}_{col200}_diff2'] = X_processed[col10] - X_processed[col200]

    # -- 生成滞后特征 --
    lag_features = {}
    cols_for_lag = valid_ws_10 + valid_ws_100 + valid_ws_200
    # 如果还有其他特征需要滞后，添加到 cols_for_lag 列表中

    if cols_for_lag: # 只有在有可用于滞后的列时才执行
        # lags 参数指的是最大滞后阶数，所以循环到 lags (包含)
        for lag in range(1, lags + 1): # 注意这里是 lags + 1
            for col in cols_for_lag:
                # 检查列是否存在以防万一
                if col in X_processed.columns:
                     lag_features[f'{col}_lag{lag}'] = X_processed[col].shift(lag)
                else:
                     print(f"警告: 尝试为不存在的列 {col} 创建 lag{lag} 特征")
                     logging.warning(f"警告: 尝试为不存在的列 {col} 创建 lag{lag} 特征")

    # -- 合并特征 --
    # 只有在生成了特征时才合并
    if combined_features:
        combined_features_df = pd.DataFrame(combined_features, index=X_processed.index)
        X_processed = pd.concat([X_processed, combined_features_df], axis=1)
        del combined_features_df # 清理内存
        gc.collect()

    if lag_features:
        lag_features_df = pd.DataFrame(lag_features, index=X_processed.index)
        X_processed = pd.concat([X_processed, lag_features_df], axis=1)
        del lag_features_df # 清理内存
        gc.collect()

    # 确保新生成的特征也是float32类型
    for col in X_processed.select_dtypes(include=['float64']).columns:
        X_processed[col] = X_processed[col].astype(np.float32)

    # 处理因 Lag 特征引入的 NaN
    nan_indices = X_processed[X_processed.isnull().any(axis=1)].index
    # 注意：这里不再 dropna，让调用者决定如何处理

    print(f"特征工程完成，输出维度: {X_processed.shape}, 发现 {len(nan_indices)} 行含NaN")
    logging.info(f"特征工程完成，输出维度: {X_processed.shape}, 发现 {len(nan_indices)} 行含NaN")
    logging.info("--- Auto Script: Engineered Columns (Before Return) ---")
    auto_engineered_cols = X_processed.columns.tolist()
    logging.info(f"Total columns: {len(auto_engineered_cols)}")
    # 可选：保存到文件以便比较
    # with open('auto_cols.txt', 'w') as f:
    #     for col in auto_engineered_cols:
    #         f.write(f"{col}\n")
    logging.info(auto_engineered_cols[:20]) # 打印前20个看看
    logging.info(auto_engineered_cols[-20:])# 打印后20个看看
    # 返回处理后的 DataFrame 和 NaN 索引
    return X_processed, nan_indices

def scale_data(X_train, X_val, pre_fitted_scaler=None):
    """
    标准化数据
    
    参数:
    X_train: 训练数据
    X_val: 验证数据
    pre_fitted_scaler: 预训练的标准化器，如果提供则直接使用它进行转换
    
    返回:
    X_train_scaled: 标准化后的训练数据
    X_val_scaled: 标准化后的验证数据
    scaler: 标准化器对象
    """
    # 确保输入是 DataFrame
    is_train_df = isinstance(X_train, pd.DataFrame)
    is_val_df = isinstance(X_val, pd.DataFrame)
    original_train_cols = X_train.columns if is_train_df else None
    original_val_cols = X_val.columns if is_val_df else None
    original_train_index = X_train.index if is_train_df else None
    original_val_index = X_val.index if is_val_df else None

    # 如果没有提供预训练的scaler，则创建并拟合
    if pre_fitted_scaler is None:
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        print("在训练数据上拟合StandardScaler")
        logging.info("在训练数据上拟合StandardScaler")
    else:
        # 如果提供了，直接使用它（假设它已经fit过）
        scaler = pre_fitted_scaler
        # 注意：通常预测时只转换验证/测试集，但如果函数设计需要，也转换训练集
        X_train_scaled = scaler.transform(X_train)
        print("使用预训练的StandardScaler转换训练数据")
        logging.info("使用预训练的StandardScaler转换训练数据")

    # 转换验证集/测试集
    X_val_scaled = scaler.transform(X_val)
    print("转换验证/测试数据")
    logging.info("转换验证/测试数据")

    # 如果原始输入是DataFrame，尝试恢复列名和索引
    if is_train_df and original_train_cols is not None and original_train_index is not None:
        X_train_scaled = pd.DataFrame(X_train_scaled, columns=original_train_cols, index=original_train_index)
    if is_val_df and original_val_cols is not None and original_val_index is not None:
        X_val_scaled = pd.DataFrame(X_val_scaled, columns=original_val_cols, index=original_val_index)

    return X_train_scaled, X_val_scaled, scaler

def create_time_window(X, y, window_size):
    """
    创建时间窗口 (传统方法，创建3D数组再扁平化)
    """
    # 确保X和y是NumPy数组
    X_values = X.values if isinstance(X, pd.DataFrame) else X
    y_values = y.values if hasattr(y, 'values') else y
    
    X_windows = []
    y_windows = []
    for i in range(len(X_values) - window_size + 1):
        X_windows.append(X_values[i:i + window_size])
        y_windows.append(y_values[i + window_size - 1])
    return np.array(X_windows), np.array(y_windows)

def create_flattened_windows_with_indices(X_scaled, y_series, window_size):
    """ 
    直接创建扁平化的2D窗口，避免3D数组的中间步骤，减少内存使用
    
    参数:
    X_scaled: 标准化后的特征矩阵 (NumPy数组或者pandas DataFrame)
    y_series: 目标变量Series或数组
    window_size: 窗口大小
    
    返回:
    X_flat: 扁平化的窗口特征矩阵
    y_windows: 对应的目标变量
    y_indices: 目标变量的原始索引
    """
    # 确保X_scaled是NumPy数组
    is_dataframe = isinstance(X_scaled, pd.DataFrame)
    if is_dataframe:
        X_scaled_values = X_scaled.values
    else:
        X_scaled_values = X_scaled
    
    num_samples = len(X_scaled_values) - window_size + 1
    num_features = X_scaled_values.shape[1]
    
    # 预分配内存 (float32!)
    X_flat = np.zeros((num_samples, window_size * num_features), dtype=np.float32)
    y_windows = np.zeros(num_samples, dtype=np.float32)
    
    # 检查y_series是否为pandas Series（有索引）
    has_index = hasattr(y_series, 'index')
    if has_index:
        original_indices = y_series.index
        y_values = y_series.values
        y_indices = np.zeros(num_samples, dtype=np.int64)  # 通常索引是int64
    else:
        y_values = y_series
        y_indices = None

    for i in range(num_samples):
        window = X_scaled_values[i:i + window_size]
        X_flat[i] = window.reshape(1, -1)  # 扁平化窗口
        target_idx = i + window_size - 1
        y_windows[i] = y_values[target_idx]
        if has_index:
            y_indices[i] = original_indices[target_idx]

    # 清理内存
    gc.collect()
    
    return X_flat, y_windows, y_indices

def create_time_window_pre(X, window_size):
    """
    为预测创建时间窗口
    """
    # 确保X是NumPy数组
    X_values = X.values if isinstance(X, pd.DataFrame) else X
    
    X_windows = []
    for i in range(len(X_values) - window_size + 1):
        X_windows.append(X_values[i:i + window_size])
    return np.array(X_windows)

def create_flattened_windows_pre(X_scaled, window_size):
    """ 
    为预测直接创建扁平化的2D窗口，避免3D数组的中间步骤
    
    参数:
    X_scaled: 标准化后的特征矩阵
    window_size: 窗口大小
    
    返回:
    X_flat: 扁平化的窗口特征矩阵
    """
    # 确保X_scaled是NumPy数组
    is_dataframe = isinstance(X_scaled, pd.DataFrame)
    if is_dataframe:
        X_scaled_values = X_scaled.values
    else:
        X_scaled_values = X_scaled
    
    num_samples = len(X_scaled_values) - window_size + 1
    num_features = X_scaled_values.shape[1]
    
    # 预分配内存 (float32!)
    X_flat = np.zeros((num_samples, window_size * num_features), dtype=np.float32)

    for i in range(num_samples):
        window = X_scaled_values[i:i + window_size]
        X_flat[i] = window.reshape(1, -1)  # 扁平化窗口

    # 清理内存
    gc.collect()
    
    return X_flat