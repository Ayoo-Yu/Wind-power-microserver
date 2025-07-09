import sys
import os

# Determine the correct path to 'backend-autopredict'
# current_file_dir is ...auto_scripts/scripts/supershort/
current_file_dir = os.path.dirname(os.path.abspath(__file__))
# target_path should be ...backend-autopredict/
# This navigates three levels up from 'supershort' directory to 'backend-autopredict'
path_to_backend_autopredict = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))

if path_to_backend_autopredict not in sys.path:
    sys.path.insert(0, path_to_backend_autopredict)
    # Optional: for debugging, you can add a print statement
    # print(f"[DEBUG data_processor_supershort] Added to sys.path: {path_to_backend_autopredict}")

import pandas as pd
import numpy as np  # 添加numpy导入，用于处理NaN值
import logging
from datetime import datetime, timedelta # Added for timestamp comparison in CSV update and prediction table backfill

# Assuming db_session.py and db_models.py are in a location accessible via PYTHONPATH
# or are in the same directory or a parent directory added to sys.path elsewhere.
# For this example, we'll follow the pattern in data_processor_short.py
# and assume they can be imported.

# --- DB Imports Start ---
try:
    from sqlalchemy.orm import Session
    # IMPORTANT: Changed TrainPreSupershort to TrainPreShort as per new requirement
    # 添加预测表的导入用于wp_true回填
    from db_models import TrainPreShort, ActualPower, SupershortlPower, ShortlPower, MidPower
    from db_session import db_session
    DB_ACCESS_AVAILABLE = True
    logging.info("Database modules (TrainPreShort, ActualPower, SupershortlPower, ShortlPower, MidPower) imported successfully for supershort processing.")
except ImportError as e:
    logging.error(f"Supershort DB related modules import failed (using TrainPreShort): {e}. DB operations will be unavailable.", exc_info=True)
    DB_ACCESS_AVAILABLE = False
# --- DB Imports End ---

def load_and_merge_data_from_db(days_to_load: int = None):
    """
    Loads feature data from TrainPreShort and actual power from ActualPower,
    merges them, and returns a pandas DataFrame.
    (This function might be less used if training always reads from an updated CSV)

    Args:
        days_to_load (int, optional): Number of past days of data to load. 
                                      If None, loads all available data. Defaults to None.
    Returns:
        pd.DataFrame: Merged DataFrame with features and actual power, or an empty
                      DataFrame if an error occurs or no data is found.
    """
    if not DB_ACCESS_AVAILABLE:
        logging.error("Database modules not available. Cannot load data directly for supershort model.")
        return pd.DataFrame()

    logging.info("Starting to load data directly from database for supershort model (using TrainPreShort)...")

    features_df = pd.DataFrame()
    actual_df = pd.DataFrame()

    try:
        with db_session() as session:
            # Query changed to TrainPreShort
            logging.info("Querying TrainPreShort table...")
            query_features = session.query(TrainPreShort)
            # Optional: Filter by date if days_to_load is specified
            # from datetime import timedelta # Ensure datetime is imported
            # if days_to_load is not None and hasattr(TrainPreShort, 'Timestamp'):
            #     cutoff_date = datetime.utcnow() - timedelta(days=days_to_load)
            #     query_features = query_features.filter(TrainPreShort.Timestamp >= cutoff_date)
            
            features_df = pd.read_sql(query_features.statement, session.bind)
            if 'timestamp' in features_df.columns and 'Timestamp' not in features_df.columns:
                features_df.rename(columns={'timestamp': 'Timestamp'}, inplace=True)
            logging.info(f"Retrieved {len(features_df)} records from TrainPreShort.")

            logging.info("Querying ActualPower table...")
            query_actual = session.query(ActualPower.timestamp, ActualPower.wp_true)
            # Optional: Filter by date
            # if days_to_load is not None and hasattr(ActualPower, 'timestamp'):
            #     cutoff_date_actual = datetime.utcnow() - timedelta(days=days_to_load)
            #     query_actual = query_actual.filter(ActualPower.timestamp >= cutoff_date_actual)

            actual_df = pd.read_sql(query_actual.statement, session.bind)
            if 'timestamp' in actual_df.columns and 'Timestamp' not in actual_df.columns:
                actual_df.rename(columns={'timestamp': 'Timestamp'}, inplace=True)
            elif 'Timestamp' not in actual_df.columns and not actual_df.empty:
                 logging.warning("ActualPower query result missing 'Timestamp' column after potential rename. Trying to rename first column if it exists.")
                 if actual_df.columns.any():
                     actual_df.rename(columns={actual_df.columns[0]: 'Timestamp'}, inplace=True)
            logging.info(f"Retrieved {len(actual_df)} records from ActualPower.")

    except Exception as e:
        logging.error(f"Error querying database for supershort data (using TrainPreShort): {e}", exc_info=True)
        return pd.DataFrame()

    if features_df.empty and actual_df.empty:
        logging.warning("No data retrieved from either TrainPreShort or ActualPower.")
        return pd.DataFrame()
    if features_df.empty:
        logging.warning("No data retrieved from TrainPreShort. Cannot create training set.")
        return pd.DataFrame()
    if actual_df.empty:
        logging.warning("No data retrieved from ActualPower (wp_true). Cannot create training set.")
        return pd.DataFrame()

    logging.info("Merging data from TrainPreShort and ActualPower...")
    try:
        if 'Timestamp' not in features_df.columns:
            logging.error("Features DataFrame (TrainPreShort) is missing 'Timestamp' column for merge.")
            return pd.DataFrame()
        if 'Timestamp' not in actual_df.columns:
            logging.error("Actual power DataFrame (ActualPower) is missing 'Timestamp' column for merge.")
            return pd.DataFrame()

        features_df['Timestamp'] = pd.to_datetime(features_df['Timestamp'])
        actual_df['Timestamp'] = pd.to_datetime(actual_df['Timestamp'])
        merged_df = pd.merge(features_df, actual_df, on='Timestamp', how='inner')
        logging.info(f"Successfully merged data. Resulting DataFrame has {len(merged_df)} records.")

        if merged_df.empty:
            logging.warning("Merged DataFrame is empty. Check timestamp alignment and data availability in both tables.")
            return pd.DataFrame()

        for col_name in ['record_id', 'record_id_x', 'record_id_y']:
            if col_name in merged_df.columns:
                logging.info(f"Dropping '{col_name}' column from merged supershort data.")
                merged_df.drop(columns=[col_name], inplace=True)
        
        merged_df.sort_values(by='Timestamp', inplace=True)
        merged_df.reset_index(drop=True, inplace=True)
        return merged_df
    except Exception as e:
        logging.error(f"Error merging or post-processing supershort data (from TrainPreShort): {e}", exc_info=True)
        return pd.DataFrame()

def get_backfill_value_from_prediction_tables(target_timestamp, session=None):
    """
    从预测表中获取指定时间戳的回填值
    
    优先级：
    1. SupershortlPower表 (wp_pred2 到 wp_pred17，按照时间戳对应关系)
    2. ShortlPower表 (对应时间戳的wp_pred)
    3. MidPower表 (对应时间戳的wp_pred)
    
    Args:
        target_timestamp (datetime): 需要回填的目标时间戳
        session: 数据库会话，如果为None则创建新会话
        
    Returns:
        float or None: 找到的预测值，如果都没有则返回None
    """
    # 调试：打印导入的SupershortlPower模型的来源和其列
    try:
        logging.debug(f"DEBUG: SupershortlPower module loaded from: {SupershortlPower.__module__}")
        if hasattr(SupershortlPower, '__init__') and hasattr(SupershortlPower.__init__, '__globals__') and '__file__' in SupershortlPower.__init__.__globals__:
             logging.debug(f"DEBUG: SupershortlPower class definition file: {SupershortlPower.__init__.__globals__['__file__']}")
        
        # 尝试获取 SQLAlchemy InstrumentedAttribute (列定义)
        from sqlalchemy.inspection import inspect as sqlalchemy_inspect
        mapper = sqlalchemy_inspect(SupershortlPower)
        column_names = [c.key for c in mapper.attrs if hasattr(c, 'key')] # More robust way to get column keys
        logging.debug(f"DEBUG: SupershortlPower SQLAlchemy mapped columns: {column_names}")

    except Exception as e_debug:
        logging.debug(f"DEBUG: Error while inspecting SupershortlPower: {e_debug}")
        
    if not DB_ACCESS_AVAILABLE:
        return None
        
    # 确保target_timestamp是datetime类型
    if isinstance(target_timestamp, str):
        target_timestamp = pd.to_datetime(target_timestamp)
    
    # 创建会话管理器
    should_close_session = session is None
    if session is None:
        try:
            session = next(db_session())
        except:
            logging.error("无法创建数据库会话用于预测值回填")
            return None
    
    try:
        # 1. 尝试从SupershortlPower表获取值
        # 优先使用wp_pred2（对应相同时间戳）
        supershort_record = session.query(SupershortlPower).filter(
            SupershortlPower.timestamp == target_timestamp
        ).first()
        
        if supershort_record:
            # 按优先级检查wp_pred2到wp_pred17
            for pred_num in range(2, 18):  # 2到17
                pred_value = getattr(supershort_record, f'wp_pred{pred_num}', None)
                if pred_value is not None and not pd.isna(pred_value):
                    logging.info(f"从SupershortlPower表获取回填值: 时间戳={target_timestamp}, wp_pred{pred_num}={pred_value}")
                    return float(pred_value)
        
        # 2. 尝试从不同时间戳的SupershortlPower记录获取值
        # wp_pred3对应前15分钟，wp_pred4对应前30分钟，依次类推
        for pred_num in range(3, 18):  # 3到17
            offset_minutes = (pred_num - 2) * 15  # pred3对应15分钟前，pred4对应30分钟前
            source_timestamp = target_timestamp - timedelta(minutes=offset_minutes)
            
            offset_record = session.query(SupershortlPower).filter(
                SupershortlPower.timestamp == source_timestamp
            ).first()
            
            if offset_record:
                pred_value = getattr(offset_record, f'wp_pred{pred_num}', None)
                if pred_value is not None and not pd.isna(pred_value):
                    logging.info(f"从SupershortlPower表获取回填值: 源时间戳={source_timestamp}, wp_pred{pred_num}={pred_value} (目标时间戳={target_timestamp})")
                    return float(pred_value)
        
        # 3. 尝试从ShortlPower表获取值
        short_record = session.query(ShortlPower).filter(
            ShortlPower.timestamp == target_timestamp
        ).first()
        
        if short_record and short_record.wp_pred is not None and not pd.isna(short_record.wp_pred):
            logging.info(f"从ShortlPower表获取回填值: 时间戳={target_timestamp}, wp_pred={short_record.wp_pred}")
            return float(short_record.wp_pred)
        
        # 4. 尝试从MidPower表获取值
        mid_record = session.query(MidPower).filter(
            MidPower.timestamp == target_timestamp
        ).first()
        
        if mid_record and mid_record.wp_pred is not None and not pd.isna(mid_record.wp_pred):
            logging.info(f"从MidPower表获取回填值: 时间戳={target_timestamp}, wp_pred={mid_record.wp_pred}")
            return float(mid_record.wp_pred)
        
        # 如果都没有找到
        logging.debug(f"在所有预测表中都未找到时间戳 {target_timestamp} 的有效预测值")
        return None
        
    except Exception as e:
        logging.error(f"从预测表获取回填值时发生错误: {e}", exc_info=True)
        return None
    finally:
        if should_close_session and session:
            session.close()

def interpolate_and_ffill_wp_true(df, wp_true_col='wp_true'):
    """
    处理wp_true列中的空值，增强版本：
    1. 首先尝试使用预测表中的历史预测值进行回填
    2. 然后使用线性插值处理中间的空值(有前后值的情况)
    3. 对序列开头的空值使用后向填充(bfill)
    4. 对序列末尾的空值使用前向填充(ffill)
    
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
    
    logging.info(f"开始处理'{wp_true_col}'列的{nan_before}个空值")
    
    # 步骤1: 使用预测表回填空值
    backfill_count = 0
    if DB_ACCESS_AVAILABLE and 'Timestamp' in result_df.columns:
        logging.info("步骤1: 尝试使用预测表回填空值...")
        
        try:
            with db_session() as session:
                for idx in result_df.index:
                    if pd.isna(result_df.loc[idx, wp_true_col]):
                        timestamp = result_df.loc[idx, 'Timestamp']
                        backfill_value = get_backfill_value_from_prediction_tables(timestamp, session)
                        
                        if backfill_value is not None:
                            result_df.loc[idx, wp_true_col] = backfill_value
                            backfill_count += 1
                            
        except Exception as e:
            logging.error(f"使用预测表回填时发生错误: {e}", exc_info=True)
    else:
        if not DB_ACCESS_AVAILABLE:
            logging.warning("数据库不可用，跳过预测表回填步骤")
        else:
            logging.warning("缺少Timestamp列，跳过预测表回填步骤")
    
    # 记录预测表回填后的空值数量
    nan_after_backfill = result_df[wp_true_col].isna().sum()
    logging.info(f"预测表回填处理了{backfill_count}个空值，剩余{nan_after_backfill}个空值")
    
    # 步骤2: 对有前后值的空值进行线性插值
    interpolated_count = 0
    if nan_after_backfill > 0:
        logging.info("步骤2: 进行线性插值...")
        nan_before_interpolate = result_df[wp_true_col].isna().sum()
        result_df[wp_true_col] = result_df[wp_true_col].interpolate(method='linear')
        nan_after_interpolate = result_df[wp_true_col].isna().sum()
        interpolated_count = nan_before_interpolate - nan_after_interpolate
        logging.info(f"线性插值处理了{interpolated_count}个空值，剩余{nan_after_interpolate}个空值")
    
    # 步骤3: 对序列开头的空值进行后向填充(bfill)
    bfill_count = 0
    nan_current = result_df[wp_true_col].isna().sum()
    if nan_current > 0:
        logging.info("步骤3: 进行后向填充...")
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
            logging.info(f"后向填充处理了{bfill_count}个空值，剩余{nan_after_bfill}个空值")
            
    # 步骤4: 对序列末尾的空值进行前向填充(ffill)
    ffill_count = 0
    if result_df[wp_true_col].isna().sum() > 0:
        logging.info("步骤4: 进行前向填充...")
        # 记录前向填充前的空值数量
        nan_before_ffill = result_df[wp_true_col].isna().sum()
        # 对末尾的空值进行前向填充
        result_df[wp_true_col] = result_df[wp_true_col].fillna(method='ffill')
        nan_after_ffill = result_df[wp_true_col].isna().sum()
        ffill_count = nan_before_ffill - nan_after_ffill
        logging.info(f"前向填充处理了{ffill_count}个空值，剩余{nan_after_ffill}个空值")
    
    # 记录处理后的空值数量
    nan_after = result_df[wp_true_col].isna().sum()
    
    logging.info(f"'{wp_true_col}'列空值处理完成: "
                 f"原始{nan_before}个空值, "
                 f"预测表回填{backfill_count}个, "
                 f"线性插值{interpolated_count}个, "
                 f"后向填充{bfill_count}个, "
                 f"前向填充{ffill_count}个, "
                 f"最终剩余{nan_after}个空值")
                 
    return result_df

def update_supershort_training_csv_from_db(csv_file_path: str):
    """
    Updates the local supershort training CSV file from the database (TrainPreShort and ActualPower).
    Fetches new data based on the latest timestamp in the CSV.
    Creates the CSV if it doesn't exist.

    Args:
        csv_file_path (str): Path to the supershort training CSV file.

    Returns:
        bool: True if update/creation was successful or no new data was needed, False otherwise.
    """
    if not DB_ACCESS_AVAILABLE:
        logging.error("Database modules not available. Cannot update/create supershort training CSV.")
        return False

    logging.info(f"Starting to check and update supershort training CSV: {csv_file_path}")
    latest_timestamp_in_csv = None
    existing_df = pd.DataFrame()
    file_exists = os.path.exists(csv_file_path)
    initial_creation = not file_exists

    if file_exists:
        try:
            existing_df = pd.read_csv(csv_file_path)
            ts_col = None
            for col in existing_df.columns: # Find timestamp column case-insensitively
                if col.lower() == 'timestamp':
                    ts_col = col
                    break
            
            if not existing_df.empty and ts_col:
                if ts_col != 'Timestamp': # Standardize to 'Timestamp'
                    logging.info(f"Renaming CSV column '{ts_col}' to 'Timestamp' for supershort data.")
                    existing_df.rename(columns={ts_col: 'Timestamp'}, inplace=True)
                existing_df['Timestamp'] = pd.to_datetime(existing_df['Timestamp'])
                latest_timestamp_in_csv = existing_df['Timestamp'].max()
                logging.info(f"Latest timestamp in existing supershort CSV '{csv_file_path}': {latest_timestamp_in_csv}")
            else:
                logging.warning(f"Supershort CSV '{csv_file_path}' is empty or missing 'Timestamp' column. Will treat as initial creation.")
                initial_creation = True
        except Exception as e:
            logging.error(f"Error reading existing supershort CSV '{csv_file_path}': {e}. Aborting update.", exc_info=True)
            return False
    else:
        logging.info(f"Supershort CSV file '{csv_file_path}' not found. Will attempt to create it from database.")

    # Query database for new data
    features_new_df = pd.DataFrame()
    actual_new_df = pd.DataFrame()
    try:
        with db_session() as session:
            logging.info("Querying TrainPreShort for new supershort data...")
            query_features = session.query(TrainPreShort)
            if latest_timestamp_in_csv is not None:
                # Ensure TrainPreShort.Timestamp is the correct attribute name
                query_features = query_features.filter(TrainPreShort.Timestamp > latest_timestamp_in_csv)
            
            features_new_df = pd.read_sql(query_features.statement, session.bind)
            if 'timestamp' in features_new_df.columns and 'Timestamp' not in features_new_df.columns:
                 features_new_df.rename(columns={'timestamp': 'Timestamp'}, inplace=True)
            logging.info(f"Retrieved {len(features_new_df)} new records from TrainPreShort for supershort CSV.")

            logging.info("Querying ActualPower for new supershort data...")
            # Assuming ActualPower.timestamp is the correct attribute name
            query_actual = session.query(ActualPower.timestamp, ActualPower.wp_true)
            if latest_timestamp_in_csv is not None:
                query_actual = query_actual.filter(ActualPower.timestamp > latest_timestamp_in_csv)
            
            actual_new_df = pd.read_sql(query_actual.statement, session.bind)
            if 'timestamp' in actual_new_df.columns and 'Timestamp' not in actual_new_df.columns:
                 actual_new_df.rename(columns={'timestamp': 'Timestamp'}, inplace=True)
            elif 'Timestamp' not in actual_new_df.columns and not actual_new_df.empty and actual_new_df.columns.any():
                 actual_new_df.rename(columns={actual_new_df.columns[0]: 'Timestamp'}, inplace=True)
            logging.info(f"Retrieved {len(actual_new_df)} new records from ActualPower for supershort CSV.")

    except Exception as e:
        logging.error(f"Error querying database for new supershort data: {e}", exc_info=True)
        return False

    if features_new_df.empty or actual_new_df.empty:
        if initial_creation and features_new_df.empty and actual_new_df.empty:
            logging.warning("Database has no data from TrainPreShort or ActualPower to create initial supershort CSV.")
        else:
            logging.info("No new data found in database to add to supershort CSV (or one table was empty).")
        # If initial creation and no data, still return True as it's not an error state unless file MUST be created.
        # If file must exist, an empty df could be written or return False. For now, True.
        if initial_creation and not os.path.exists(csv_file_path):
             logging.warning(f"Initial CSV creation for {csv_file_path} attempted, but DB had no data. File will not be created.")
        return True 

    logging.info("Merging new data for supershort CSV...")
    try:
        if 'Timestamp' not in features_new_df.columns:
             logging.error("New features data (TrainPreShort) is missing 'Timestamp' for supershort CSV merge.")
             return False
        if 'Timestamp' not in actual_new_df.columns:
             logging.error("New actual power data (ActualPower) is missing 'Timestamp' for supershort CSV merge.")
             return False

        features_new_df['Timestamp'] = pd.to_datetime(features_new_df['Timestamp'])
        actual_new_df['Timestamp'] = pd.to_datetime(actual_new_df['Timestamp'])
        
        merged_new_data = pd.merge(features_new_df, actual_new_df, on='Timestamp', how='inner')
        logging.info(f"Merged new data for supershort CSV, {len(merged_new_data)} new records obtained.")

        if 'record_id' in merged_new_data.columns: # Drop record_id from merged new data
            merged_new_data.drop(columns=['record_id'], inplace=True)
        # Also check for _x, _y suffixes if merge creates them due to overlapping non-key columns
        for col_name_suffix in ['_x', '_y']:
            cols_to_drop = [col for col in merged_new_data.columns if col.startswith('record_id') and col.endswith(col_name_suffix)]
            if cols_to_drop:
                merged_new_data.drop(columns=cols_to_drop, inplace=True)
        
        if merged_new_data.empty:
            logging.info("No new records after merging (possibly due to timestamp mismatches or data cleaning). Supershort CSV not updated.")
            return True

        # Clean NaNs from new data - replace mean fill with interpolate_and_ffill
        merged_new_data = interpolate_and_ffill_wp_true(merged_new_data)
        
        # 仍然需要处理其他特征列的空值
        merged_new_data.dropna(subset=[col for col in merged_new_data.columns 
                                     if col not in ['Timestamp', 'wp_true']], 
                             inplace=True)
                             
        merged_new_data.sort_values(by='Timestamp', inplace=True)

    except Exception as e:
        logging.error(f"Error merging or cleaning new supershort data: {e}", exc_info=True)
        return False

    if merged_new_data.empty: # Check again after cleaning
        logging.info("New data became empty after cleaning. Supershort CSV not updated.")
        return True
        
    logging.info(f"Writing/Appending {len(merged_new_data)} new records to supershort CSV: {csv_file_path}")
    try:
        if initial_creation:
            merged_new_data.to_csv(csv_file_path, index=False, header=True)
            logging.info(f"Created new supershort CSV '{csv_file_path}' with {len(merged_new_data)} records.")
        else:
            # Ensure columns match existing CSV if appending
            if not existing_df.empty:
                existing_cols = existing_df.columns.tolist()
                try:
                    merged_new_data = merged_new_data[existing_cols]
                except KeyError as ke:
                    logging.error(f"Column mismatch: New supershort data columns {merged_new_data.columns.tolist()} do not match existing CSV columns {existing_cols}. Missing: {ke}. Cannot append.")
                    return False
            merged_new_data.to_csv(csv_file_path, mode='a', index=False, header=False)
            logging.info(f"Appended {len(merged_new_data)} new records to existing supershort CSV '{csv_file_path}'.")
        return True
    except Exception as e:
        logging.error(f"Error writing to supershort CSV '{csv_file_path}': {e}", exc_info=True)
        return False

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Example for load_and_merge_data_from_db
    # print("\nAttempting to load supershort data directly from DB (using TrainPreShort)...")
    # if DB_ACCESS_AVAILABLE:
    #     all_data = load_and_merge_data_from_db()
    #     if not all_data.empty:
    #         print(f"Successfully loaded {len(all_data)} records directly.")
    #         print(all_data.head())
    #     else:
    #         print("Failed to load data directly or data is empty.")
    # else:
    #     print("DB_ACCESS_AVAILABLE is False. Cannot run direct load example.")

    # Example for update_supershort_training_csv_from_db
    print("\nAttempting to update/create 'training_data_supershort_example.csv'...")
    if DB_ACCESS_AVAILABLE:
        # Make sure current dir is where you want the CSV or provide full path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        example_csv_path = os.path.join(script_dir, 'training_data_supershort_example.csv')
        
        # To test incremental, run once, then potentially add new data to DB and run again.
        # To test creation, delete the example CSV before running.
        if os.path.exists(example_csv_path):
            print(f"Example CSV '{example_csv_path}' exists. Update will be attempted.")
        else:
            print(f"Example CSV '{example_csv_path}' does not exist. Creation will be attempted.")

        success = update_supershort_training_csv_from_db(example_csv_path)
        if success:
            print(f"Update/Create process for '{example_csv_path}' completed.")
            if os.path.exists(example_csv_path):
                 df_check = pd.read_csv(example_csv_path)
                 print(f"CSV now contains {len(df_check)} records. Last 5 rows:")
                 print(df_check.tail())
            else:
                 print(f"CSV {example_csv_path} was not created (likely no data in DB for initial creation).")

        else:
            print(f"Update/Create process for '{example_csv_path}' failed. Check logs.")
    else:
        print("DB_ACCESS_AVAILABLE is False. Cannot run CSV update example.") 