import pandas as pd
import os
import numpy as np
import time # For sleep
import sys
from datetime import datetime, timedelta, timezone # For time calculations
import logging
import requests  # 为API调用导入requests
import socket  # 为环境检测导入socket

# 添加backend到sys.path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
# 这将导航到backend目录（从supershort向上三级）
path_to_backend = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
if path_to_backend not in sys.path:
    sys.path.insert(0, path_to_backend)
    # print(f"[DEBUG predict_supershort] 已添加到sys.path: {path_to_backend}")

# 添加scripts目录到sys.path以导入utils_base
_path_to_scripts = os.path.abspath(os.path.join(current_file_dir, '..'))
if _path_to_scripts not in sys.path:
    sys.path.insert(0, _path_to_scripts)

from utils_base import get_farm_capacity

from predictor_model import WindPowerPredictor, preprocess_data # 从本地文件导入
# 导入interpolate_and_ffill_wp_true函数，用于与训练一致的空值处理
# 同时导入新的预测表回填函数
from data_processor_supershort import interpolate_and_ffill_wp_true, get_backfill_value_from_prediction_tables

# --- Database Imports (assuming similar setup to data_processor_supershort.py) ---
try:
    from sqlalchemy.orm import Session
    # 添加预测表的导入用于wp_true回填
    from db_models import TrainPreShort, ActualPower, SupershortlPower, ShortlPower, MidPower # Using TrainPreShort for features
    from db_session import db_session
    DB_ACCESS_AVAILABLE = True
    logging.info("Database modules (TrainPreShort, ActualPower, SupershortlPower, ShortlPower, MidPower) imported successfully for predict_supershort.")
except ImportError as e:
    logging.error(f"Predict_supershort DB related modules import failed: {e}. DB operations will be unavailable.", exc_info=True)
    DB_ACCESS_AVAILABLE = False
# --- End Database Imports ---
from config_supershort import MODEL_FOLDER, PREC_SV_FOLDER, OUTPUT_DIR_PRE
# --- 配置参数 ---
# PREDICTION_INPUT_DATA_PATH = 'new_data_for_prediction.csv' # No longer reading a single CSV for raw input

# --- 全局日志配置 ---
# 获取当前脚本文件所在的目录
current_script_dir_for_log = os.path.dirname(os.path.abspath(__file__))

# 定义日志目录和文件路径
log_dir_base_for_predict = os.path.join(current_script_dir_for_log, "logs")
auto_predict_log_dir = os.path.join(log_dir_base_for_predict, "auto_predict")
os.makedirs(auto_predict_log_dir, exist_ok=True) # 创建 auto_predict 目录
# predict_log_file_path = os.path.join(auto_predict_log_dir, "predict_supershort.log") # 旧的固定文件名

# 使用当前日期生成日志文件名
from datetime import datetime # 确保导入
today_date_str_predict = datetime.now().strftime("%Y%m%d")
predict_log_file_name = f"{today_date_str_predict}_predict_supershort.log"
predict_log_file_path = os.path.join(auto_predict_log_dir, predict_log_file_name)

# 获取根日志记录器
predict_logger = logging.getLogger() # Use global logger
# 如果已经有处理器，为了避免重复添加，可以先清除 (或者在父/调用脚本中统一配置)
# if predict_logger.hasHandlers():
#     predict_logger.handlers.clear()
predict_logger.setLevel(logging.INFO) # 设置日志级别

# 创建并设置文件处理器
predict_file_handler = logging.FileHandler(predict_log_file_path, encoding="utf-8")
predict_file_handler.setLevel(logging.INFO)
predict_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
predict_file_handler.setFormatter(predict_formatter)

# 创建并设置控制台处理器
predict_console_handler = logging.StreamHandler()
predict_console_handler.setLevel(logging.INFO)
predict_console_handler.setFormatter(predict_formatter)

# 添加处理器到日志记录器 (仅当没有被其他方式配置时)
# 检查是否已经有同类型的处理器，避免重复添加，尤其是在被其他脚本导入时
has_file_handler_already = any(isinstance(h, logging.FileHandler) and h.baseFilename == predict_log_file_path for h in predict_logger.handlers)
has_console_handler_already = any(isinstance(h, logging.StreamHandler) for h in predict_logger.handlers)

if not has_file_handler_already:
    predict_logger.addHandler(predict_file_handler)
if not has_console_handler_already:
    predict_logger.addHandler(predict_console_handler)
# 移除旧的 basicConfig
# logging.basicConfig(level=logging.INFO, 
#                     format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
# --- 配置结束 ---

MODEL_INPUT_DIR = MODEL_FOLDER  # Directory where trained models for each shift are stored
PREDICTION_INPUT_SAVE_DIR = PREC_SV_FOLDER # Directory to save the 36-row input
PREDICTION_OUTPUT_SAVE_DIR = OUTPUT_DIR_PRE # Directory to save prediction results

MIN_SHIFT = 1  # Corresponds to prediction_horizon_1 (actual N in power_diff_N)
MAX_SHIFT = 16 # Corresponds to prediction_horizon_16

HISTORICAL_ROWS_NEEDED = 20 # Number of 15-min intervals before the first target point
PREDICTION_POINTS = 16    # Number of future 15-min intervals to predict
TOTAL_ROWS_FOR_MODEL_INPUT = HISTORICAL_ROWS_NEEDED + PREDICTION_POINTS # 36 rows

# WP_TRUE_WAIT_TIMEOUT_SECONDS = 13 * 60 # 13 minutes # REMOVED
# WP_TRUE_WAIT_MAX_ATTEMPTS = 26 # Roughly 13 minutes if checking every 30s # REMOVED
# WP_TRUE_WAIT_SLEEP_SECONDS = 30 # Sleep duration between checks # REMOVED
TARGET_TRIGGER_SECOND = 30 # Script aims to run logic at XX:YY:30

def get_current_beijing_time():
    """Returns the current time in Beijing time without timezone info."""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(timezone.utc).astimezone(beijing_tz).replace(tzinfo=None)

def get_current_farm_code():
    return str(os.environ.get('FARM_CODE') or os.environ.get('DEFAULT_FARM_CODE') or 'DEFAULT_FARM').strip()

def calculate_prediction_timestamps(current_trigger_time_beijing: datetime):
    """
    Calculates key timestamps for the prediction cycle based on the script's trigger time in Beijing.
    The script is expected to be triggered by the scheduler at times like XX:14:00, XX:29:00, etc.,
    and then sleeps until XX:YY:30. So current_trigger_time_beijing here is the XX:YY:30 time.

    The first prediction target time will be 15 minutes after the current_trigger_time_beijing,
    rounded up to the next 15-minute interval. (Effectively, 15min 30sec after the scheduler's minute-trigger)

    Example:
    - Scheduler triggers at 12:14:00. Script sleeps until 12:14:30. current_trigger_time_beijing = 12:14:30.
    - first_target_prediction_time = 12:14:30 + 15 minutes = 12:29:30, rounded up to 12:30:00.

    Returns timestamps in Beijing time without timezone info.
    """
    if current_trigger_time_beijing.tzinfo is not None:
        current_trigger_time_beijing = current_trigger_time_beijing.replace(tzinfo=None)

    # The first target is 15 minutes after the effective trigger time (which is at YY:30 seconds)
    first_target_prediction_time = current_trigger_time_beijing + timedelta(minutes=15)
    
    # Round up to the next 15-minute interval.
    first_target_prediction_time = first_target_prediction_time.replace(second=0, microsecond=0)
    minutes_past_hour = first_target_prediction_time.minute
    if minutes_past_hour % 15 != 0:
        minutes_to_add = 15 - (minutes_past_hour % 15)
        first_target_prediction_time += timedelta(minutes=minutes_to_add)
        # Ensure minute is correctly set after adding (e.g., 29 + 1 -> 30, not 44)
        first_target_prediction_time = first_target_prediction_time.replace(minute=(first_target_prediction_time.minute // 15) * 15)


    # The latest actual power data required is for the timestamp 15 minutes *before* the first_target_prediction_time.
    # This is the "预估的实测值" for t-1.
    # Example: If first_target is 12:30:00, this required_latest_actual_timestamp is 12:15:00.
    # This 12:15:00 value is expected to be uploaded by current_trigger_time_beijing (e.g. 12:14:30).
    required_latest_actual_timestamp = first_target_prediction_time - timedelta(minutes=15)

    last_target_prediction_time = first_target_prediction_time + timedelta(minutes=15 * (PREDICTION_POINTS - 1))
    # earliest_historical_time_needed is based on the first_target_prediction_time, not required_latest_actual_timestamp
    earliest_historical_time_needed = first_target_prediction_time - timedelta(minutes=15 * HISTORICAL_ROWS_NEEDED) 

    current_processing_slot_start = current_trigger_time_beijing # Script's effective start time after sleep

    return {
        "first_target_prediction_time": first_target_prediction_time,
        "required_latest_actual_timestamp": required_latest_actual_timestamp,
        "earliest_historical_time_needed": earliest_historical_time_needed,
        "last_target_prediction_time": last_target_prediction_time,
        "current_processing_slot_start": current_processing_slot_start
    }

def fetch_actual_power(session, start_beijing, end_beijing, farm_code=None):
    """
    Fetches ActualPower data (timestamp, wp_true) within the Beijing time range.
    
    Args:
        session: Database session object
        start_beijing: Start time in Beijing time without timezone info
        end_beijing: End time in Beijing time without timezone info
    """
    farm_code = farm_code or get_current_farm_code()
    logging.info(f"Fetching ActualPower from {start_beijing} to {end_beijing}, farm_code={farm_code}")
    query = session.query(ActualPower.timestamp, ActualPower.wp_true)\
                   .filter(
                       ActualPower.farm_code == farm_code,
                       ActualPower.timestamp >= start_beijing,
                       ActualPower.timestamp <= end_beijing
                   )
    df = pd.read_sql(query.statement, session.bind)
    if 'timestamp' in df.columns and 'Timestamp' not in df.columns:
        df.rename(columns={'timestamp': 'Timestamp'}, inplace=True)
    if 'Timestamp' in df.columns:
        # 保持时间戳为北京时间，不进行时区转换
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    logging.info(f"Retrieved {len(df)} records from ActualPower.")
    return df

def fetch_train_pre_short(session, start_beijing, end_beijing):
    """
    Fetches TrainPreShort data (all features) within the Beijing time range.
    
    Args:
        session: Database session object
        start_beijing: Start time in Beijing time without timezone info
        end_beijing: End time in Beijing time without timezone info
    """
    logging.info(f"Fetching TrainPreShort from {start_beijing} to {end_beijing}")
    query = session.query(TrainPreShort).filter(TrainPreShort.Timestamp >= start_beijing, TrainPreShort.Timestamp <= end_beijing)
    df = pd.read_sql(query.statement, session.bind)
    if 'timestamp' in df.columns and 'Timestamp' not in df.columns:
        df.rename(columns={'timestamp': 'Timestamp'}, inplace=True)
    if 'Timestamp' in df.columns:
        # 保持时间戳为北京时间，不进行时区转换
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    logging.info(f"Retrieved {len(df)} records from TrainPreShort.")
    return df

# wait_for_wp_true function is now removed as per new logic.
# def wait_for_wp_true(session, target_timestamp_beijing, current_slot_start_beijing):
# ... (function code removed) ...


def handle_wp_true_missing(data: pd.DataFrame, wp_true_col: str = 'wp_true', farm_code=None) -> pd.DataFrame:
    """
    处理wp_true列中的空值，使用增强版方法：
    1. 优先使用预测表中的历史预测值进行回填
    2. 然后使用线性插值处理中间的空值
    3. 最后使用前向/后向填充处理边界空值
    
    Args:
        data (pd.DataFrame): 包含wp_true列的数据框
        wp_true_col (str): 列名，默认为'wp_true'
        
    Returns:
        pd.DataFrame: 处理后的数据框
    """
    if wp_true_col not in data.columns:
        logging.warning(f"'{wp_true_col}' column not found in data for interpolation/ffill. Creating it with NaNs.")
        data[wp_true_col] = np.nan # Ensure the column exists for later steps
        return data

    # 使用增强版的interpolate_and_ffill_wp_true函数，它会优先使用预测表回填
    logging.info(f"Handling missing values in '{wp_true_col}' using enhanced method (prediction table backfill + interpolation + ffill)")
    processed_data = interpolate_and_ffill_wp_true(data, wp_true_col, farm_code=farm_code)
    
    # 检查处理后是否还有空值
    nan_after = processed_data[wp_true_col].isna().sum()
    if nan_after > 0:
        if processed_data[wp_true_col].isna().all():
            logging.critical(f"'{wp_true_col}' column is ALL NaNs even after enhanced processing. Predictions will likely fail or be all NaN.")
        else:
            logging.warning(f"'{wp_true_col}' still has {nan_after} NaNs after enhanced processing.")
    else:
        logging.info(f"Successfully handled all missing values in '{wp_true_col}' using enhanced method.")
        
    return processed_data

def main():
    """Main prediction function triggered by scheduler (e.g., at XX:14:00, then sleeps to XX:14:30)."""
    farm_code = get_current_farm_code()
    
    # --- Sleep to achieve second-level precision ---
    now_beijing = get_current_beijing_time()
    current_second = now_beijing.second
    
    seconds_to_wait = 0
    if current_second < TARGET_TRIGGER_SECOND:
        seconds_to_wait = TARGET_TRIGGER_SECOND - current_second
    elif current_second > TARGET_TRIGGER_SECOND: # Script started a bit late within the minute
        seconds_to_wait = (60 - current_second) + TARGET_TRIGGER_SECOND # Wait for next minute's target second
        
    if seconds_to_wait > 0:
        logging.info(f"Current time {now_beijing.strftime('%H:%M:%S')}. Waiting for {seconds_to_wait} seconds to align with target second ({TARGET_TRIGGER_SECOND})...")
        time.sleep(seconds_to_wait)
    
    # This is the effective time the core logic starts (e.g., XX:14:30, XX:29:30)
    effective_trigger_time_beijing = get_current_beijing_time()
    logging.info(f"Effective trigger time for prediction logic: {effective_trigger_time_beijing.strftime('%Y-%m-%d %H:%M:%S')}")

    if not DB_ACCESS_AVAILABLE:
        logging.critical("Database modules not available. Prediction cannot proceed.")
        return

    time_params = calculate_prediction_timestamps(effective_trigger_time_beijing)
    first_target_beijing = time_params["first_target_prediction_time"]
    required_latest_actual_beijing = time_params["required_latest_actual_timestamp"]
    earliest_hist_beijing = time_params["earliest_historical_time_needed"]
    last_target_beijing = time_params["last_target_prediction_time"]
    
    logging.info(f"  Script effective trigger time: {effective_trigger_time_beijing.strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"  First prediction target time: {first_target_beijing.strftime('%Y-%m-%d %H:%M')}")
    logging.info(f"  Required latest actual data timestamp (t-1 for first target): {required_latest_actual_beijing.strftime('%Y-%m-%d %H:%M')}")
    logging.info(f"  Earliest historical data needed: {earliest_hist_beijing.strftime('%Y-%m-%d %H:%M')}")
    logging.info(f"  Last prediction target time: {last_target_beijing.strftime('%Y-%m-%d %H:%M')}")

    # --- Data Fetching and Preparation ---
    input_csv_filename = f"model_input_{farm_code}_target_{first_target_beijing.strftime('%Y%m%d%H%M')}.csv"
    input_csv_filepath = os.path.join(PREDICTION_INPUT_SAVE_DIR, input_csv_filename)
    os.makedirs(PREDICTION_INPUT_SAVE_DIR, exist_ok=True)

    logging.info(f"Attempting to fetch data from database to create/overwrite: {input_csv_filepath}")
    
    try:
        df_for_csv = pd.DataFrame()
        with db_session() as session:
            # 1. Fetch ActualPower data (historical wp_true up to required_latest_actual_beijing)
            actual_power_fetch_start_beijing = earliest_hist_beijing - timedelta(hours=1) # Fetch a little extra for ffill robustness
            
            logging.info(f"Using Beijing time for database queries:")
            logging.info(f"  ActualPower fetch range: {actual_power_fetch_start_beijing} to {required_latest_actual_beijing}")
            actual_power_df = fetch_actual_power(session, actual_power_fetch_start_beijing, required_latest_actual_beijing, farm_code=farm_code)
            
            # Check if the crucial required_latest_actual_beijing wp_true was fetched
            # Ensure Timestamp column exists and is datetime before checking
            if not actual_power_df.empty and 'Timestamp' in actual_power_df.columns and pd.api.types.is_datetime64_any_dtype(actual_power_df['Timestamp']):
                # Convert required_latest_actual_beijing to the same timezone awareness as actual_power_df['Timestamp'] if necessary
                # Assuming both are naive Beijing time here based on current setup.
                required_data_point = actual_power_df[actual_power_df['Timestamp'] == required_latest_actual_beijing]
                if not required_data_point.empty:
                    wp_true_at_required_time = required_data_point['wp_true'].iloc[0]
                    if pd.isna(wp_true_at_required_time):
                        logging.warning(f"wp_true for the required latest actual timestamp {required_latest_actual_beijing.strftime('%Y-%m-%d %H:%M')} was fetched but is NaN.")
                    else:
                        logging.info(f"Successfully fetched wp_true ({wp_true_at_required_time}) for the required latest actual timestamp {required_latest_actual_beijing.strftime('%Y-%m-%d %H:%M')}.")
                else:
                    logging.error(f"Data for the required latest actual timestamp {required_latest_actual_beijing.strftime('%Y-%m-%d %H:%M')} is missing in fetched ActualPower. This is critical for t-1 input.")
            elif actual_power_df.empty :
                 logging.error(f"Fetched ActualPower data is empty. Cannot verify wp_true for {required_latest_actual_beijing.strftime('%Y-%m-%d %H:%M')}")
            else: # Timestamp column missing or not datetime
                 logging.error(f"ActualPower DataFrame is missing 'Timestamp' column or it's not datetime. Cannot verify wp_true for {required_latest_actual_beijing.strftime('%Y-%m-%d %H:%M')}")


            # 2. Fetch TrainPreShort data (features for history and future)
            # The features should cover the range from earliest_hist_beijing up to last_target_beijing
            logging.info(f"  TrainPreShort fetch range: {earliest_hist_beijing.strftime('%Y-%m-%d %H:%M')} to {last_target_beijing.strftime('%Y-%m-%d %H:%M')}")
            features_df = fetch_train_pre_short(session, earliest_hist_beijing, last_target_beijing)

        if features_df.empty:
            logging.error("No feature data (TrainPreShort) retrieved. Cannot create CSV or proceed.")
            return

        # 3. Merge features and actual power
        merged_df = pd.merge(features_df, actual_power_df, on='Timestamp', how='left')
        logging.info(f"Merged features and actual power. Resulting shape: {merged_df.shape}")
            
        merged_df.sort_values(by='Timestamp', inplace=True)
        merged_df.drop_duplicates(subset=['Timestamp'], keep='first', inplace=True)
        merged_df.reset_index(drop=True, inplace=True)

        # 4. Data Slicing: Get the 36 rows for model input CSV
        try:
            # Simplified logging for compactness and readability
            if not merged_df.empty and 'Timestamp' in merged_df.columns and pd.api.types.is_datetime64_any_dtype(merged_df['Timestamp']):
                min_ts, max_ts = merged_df['Timestamp'].min(), merged_df['Timestamp'].max()
                min_ts_str = min_ts.strftime('%Y-%m-%d %H:%M') if pd.notna(min_ts) else 'N/A'
                max_ts_str = max_ts.strftime('%Y-%m-%d %H:%M') if pd.notna(max_ts) else 'N/A'
                logging.info(f"Searching for target {first_target_beijing.strftime('%Y-%m-%d %H:%M')} in merged_df. Range: {min_ts_str} to {max_ts_str}.")
            else:
                logging.info(f"Searching for target {first_target_beijing.strftime('%Y-%m-%d %H:%M')} in merged_df (df is empty or has no valid Timestamp column).")
            
            # Ensure comparison is between naive datetimes if one is naive
            first_target_naive = first_target_beijing.replace(tzinfo=None) if first_target_beijing.tzinfo is not None else first_target_beijing
            
            if merged_df['Timestamp'].dt.tz is not None:
                first_target_index = merged_df[merged_df['Timestamp'].dt.tz_localize(None) == first_target_naive].index[0]
            else:
                first_target_index = merged_df[merged_df['Timestamp'] == first_target_naive].index[0]
                        
            logging.info(f"Found first_target_beijing at index {first_target_index}")
        except IndexError:
            logging.error(f"Timestamp {first_target_beijing.strftime('%Y-%m-%d %H:%M')} not found in merged data. Cannot slice for model input CSV.")
            if not merged_df.empty and 'Timestamp' in merged_df.columns and pd.api.types.is_datetime64_any_dtype(merged_df['Timestamp']) and len(merged_df) < 100:
                logging.info(f"Available timestamp range in merged_df: {merged_df['Timestamp'].min().strftime('%Y-%m-%d %H:%M') if merged_df['Timestamp'].min() is not pd.NaT else 'N/A'} to {merged_df['Timestamp'].max().strftime('%Y-%m-%d %H:%M') if merged_df['Timestamp'].max() is not pd.NaT else 'N/A'}")
            return

        start_slice_idx = first_target_index - HISTORICAL_ROWS_NEEDED
        end_slice_idx = first_target_index + PREDICTION_POINTS

        if start_slice_idx < 0:
            logging.warning(f"Not enough historical data for CSV. Available: {first_target_index} rows before target. Required: {HISTORICAL_ROWS_NEEDED}. Using all available historical data from index 0.")
            start_slice_idx = 0
            # Check if this results in too few rows overall for the model later
            if (end_slice_idx - start_slice_idx) < TOTAL_ROWS_FOR_MODEL_INPUT and first_target_index < HISTORICAL_ROWS_NEEDED :
                 logging.error(f"Critically insufficient historical data: only {first_target_index} points before first target. Model input will be too short ({end_slice_idx - start_slice_idx} rows). Aborting.")
                 return
        
        if end_slice_idx > len(merged_df):
            logging.warning(f"Not enough future data points in merged_df for CSV. Required up to index {end_slice_idx-1}, available up to {len(merged_df)-1}. Using all available future data.")
            end_slice_idx = len(merged_df)

        df_for_csv = merged_df.iloc[start_slice_idx:end_slice_idx].copy()
        logging.info(f"Sliced {len(df_for_csv)} rows for CSV input (target {TOTAL_ROWS_FOR_MODEL_INPUT} rows).")

        if len(df_for_csv) < TOTAL_ROWS_FOR_MODEL_INPUT:
             logging.warning(f"Could not obtain the full {TOTAL_ROWS_FOR_MODEL_INPUT} rows for CSV input. Only got {len(df_for_csv)}. Predictions might be compromised.")
        
        if df_for_csv.empty:
             logging.error("Data sliced for CSV is empty. Cannot create CSV or proceed.")
             return

        df_for_csv.to_csv(input_csv_filepath, index=False)
        logging.info(f"Saved data fetched from DB to: {input_csv_filepath}")

    except Exception as e_fetch_save:
        logging.error(f"Error during data fetching from DB or saving to {input_csv_filepath}: {e_fetch_save}", exc_info=True)
        return

    raw_input_df_for_models = pd.DataFrame()
    try:
        logging.info(f"Loading model input from CSV: {input_csv_filepath}")
        # First, read the CSV without parsing dates automatically.
        raw_input_df_for_models = pd.read_csv(input_csv_filepath)

        if 'Timestamp' not in raw_input_df_for_models.columns:
            logging.error(f"'Timestamp' column not found in {input_csv_filepath}. Prediction cannot proceed.")
            return

        # Next, explicitly and robustly convert the 'Timestamp' column to datetime objects.
        # 'errors='coerce'' will turn any unparseable date strings into NaT (Not a Time).
        raw_input_df_for_models['Timestamp'] = pd.to_datetime(raw_input_df_for_models['Timestamp'], errors='coerce')

        # Check if all timestamp values failed to parse, which indicates a critical issue with the data.
        if not raw_input_df_for_models.empty and raw_input_df_for_models['Timestamp'].isna().all():
            logging.error(f"All 'Timestamp' values in {input_csv_filepath} failed to parse into dates. Check the CSV content. Prediction cannot proceed.")
            return

        # If the dataframe is not empty, proceed with timezone localization.
        # This is now safe because we've ensured the 'Timestamp' column has a datetime-like dtype.
        if not raw_input_df_for_models.empty:
            if raw_input_df_for_models['Timestamp'].dt.tz is not None:
                raw_input_df_for_models['Timestamp'] = raw_input_df_for_models['Timestamp'].dt.tz_localize(None)
        
        logging.info(f"Successfully loaded {len(raw_input_df_for_models)} rows from {input_csv_filepath}. Shape: {raw_input_df_for_models.shape}")

        if not raw_input_df_for_models.empty and len(raw_input_df_for_models) != TOTAL_ROWS_FOR_MODEL_INPUT :
             logging.warning(f"Loaded CSV {input_csv_filepath} has {len(raw_input_df_for_models)} rows, but expected {TOTAL_ROWS_FOR_MODEL_INPUT} based on configuration.")
    except Exception as e_load:
        logging.error(f"Failed to load or process data from {input_csv_filepath}: {e_load}", exc_info=True)
        return
    
    if raw_input_df_for_models.empty:
        logging.error(f"Model input DataFrame is empty after attempting to load/create from {input_csv_filepath}. Prediction cannot proceed.")
        return
 
    logging.info("Starting general preprocessing on the loaded input data...")
    processed_input_for_models = preprocess_data(raw_input_df_for_models) 
    logging.info("General preprocessing complete.")

    logging.info("Applying specific 'wp_true' handling (backfill/interpolation/ffill) on the processed input data...")
    # This step is crucial, especially if the required_latest_actual_beijing wp_true was NaN or missing.
    processed_input_for_models = handle_wp_true_missing(processed_input_for_models, wp_true_col='wp_true', farm_code=farm_code)
    logging.info("'wp_true' handling complete.")

    # Check if the critical t-1 wp_true value for the *first* prediction point is now present after all processing.
    # The first prediction point's features are derived from the (HISTORICAL_ROWS_NEEDED)-th row of processed_input_for_models.
    # The `power_actual_at_t_minus_1` for this row would come from `wp_true` at index `HISTORICAL_ROWS_NEEDED - 1`
    # (assuming n_shift=1 for the first model).
    # More generally, the model expects `wp_true` to be non-NaN at indices that serve as basis for `power_actual_at_t_minus_N`.
    if HISTORICAL_ROWS_NEEDED < len(processed_input_for_models) and \
       pd.isna(processed_input_for_models.iloc[HISTORICAL_ROWS_NEEDED -1]['wp_true']): # Check t-1 for the first model (shift=1)
        logging.warning(f"After all processing, wp_true for the t-1 point (index {HISTORICAL_ROWS_NEEDED-1}) relative to the first prediction target is still NaN. "
                        "Model for shift=1 might produce NaN or poor results if it relies on this heavily.")


    prediction_target_timestamps = pd.Series(dtype='datetime64[ns]') # Initialize as empty
    if HISTORICAL_ROWS_NEEDED <= len(raw_input_df_for_models):
        prediction_target_timestamps = raw_input_df_for_models['Timestamp'].iloc[HISTORICAL_ROWS_NEEDED : min(len(raw_input_df_for_models), HISTORICAL_ROWS_NEEDED + PREDICTION_POINTS)].copy()
    
    if len(prediction_target_timestamps) < PREDICTION_POINTS:
        logging.warning(f"Could only identify {len(prediction_target_timestamps)} target timestamps for results out of {PREDICTION_POINTS} expected from raw input.")
        if prediction_target_timestamps.empty:
            logging.error("No target timestamps identified from input data. Cannot create results DataFrame.")
            return 
    
    results_df = pd.DataFrame({'Timestamp': prediction_target_timestamps.values})

    successful_model_loads = 0
    for n_shift_value in range(MIN_SHIFT, MAX_SHIFT + 1):
        model_horizon_name = f'prediction_horizon_{n_shift_value}'
        logging.info(f"{'='*10} Predicting for Horizon (Shift) = {n_shift_value} {'='*10}")

        model_n_dir = os.path.join(MODEL_INPUT_DIR, f'shift_{n_shift_value}')
        if not os.path.isdir(model_n_dir):
            logging.warning(f"Model directory not found for Shift={n_shift_value} at {model_n_dir}. Skipping.")
            results_df[model_horizon_name] = np.nan 
            continue

        predictor = WindPowerPredictor(n_shift=n_shift_value)
        if predictor.load_state(model_n_dir):
            successful_model_loads +=1
            predictions_series_for_shift_n = predictor.predict(processed_input_for_models)

            # 分位数预测
            pred_lower = None
            pred_upper = None
            if hasattr(predictor, 'q_models') and predictor.q_models:
                try:
                    wfcapacity = get_farm_capacity(os.environ.get('FARM_CODE', 'DEFAULT_FARM'))
                    # 复用 predict() 内部相同的特征准备流程
                    features_cleaned_q, valid_idx_q, original_idx_q = predictor._prepare_features_common(processed_input_for_models)
                    if (not valid_idx_q.empty
                            and predictor.numeric_features
                            and all(c in features_cleaned_q.columns for c in predictor.numeric_features)):
                        X_test_q = features_cleaned_q.loc[valid_idx_q, predictor.numeric_features]
                        X_test_q.columns = X_test_q.columns.astype(str)
                        X_test_scaled_q = predictor.scaler.transform(X_test_q)

                        q05_diff = predictor.q_models[0.05].predict(X_test_scaled_q)
                        q95_diff = predictor.q_models[0.95].predict(X_test_scaled_q)

                        # 与 predict() 相同的逆变换: pred_diff + power_actual_at_t_minus_N, 然后 clip >= 0
                        reconstruct_col = predictor.feature_power_t_minus_N_col_name
                        if reconstruct_col in features_cleaned_q.columns:
                            power_t_minus_N = features_cleaned_q.loc[valid_idx_q, reconstruct_col]
                        else:
                            power_t_minus_N = pd.Series(np.nan, index=valid_idx_q)

                        q05_reconstructed = pd.Series(q05_diff, index=valid_idx_q) + power_t_minus_N
                        q95_reconstructed = pd.Series(q95_diff, index=valid_idx_q) + power_t_minus_N
                        q05_reconstructed = np.maximum(q05_reconstructed, 0)
                        q95_reconstructed = np.maximum(q95_reconstructed, 0)

                        # 对齐到原始索引（与 predict() 相同的模式）
                        q05_aligned = pd.Series(np.nan, index=original_idx_q, dtype=float)
                        q95_aligned = pd.Series(np.nan, index=original_idx_q, dtype=float)
                        q05_aligned.update(q05_reconstructed)
                        q95_aligned.update(q95_reconstructed)

                        # 提取与点预测相同行的分位数值
                        target_row_idx_q = HISTORICAL_ROWS_NEEDED + (n_shift_value - MIN_SHIFT)
                        results_df_row_index_q = n_shift_value - MIN_SHIFT
                        if (0 <= target_row_idx_q < len(q05_aligned)
                                and 0 <= results_df_row_index_q < len(results_df)):
                            val_lower = q05_aligned.iloc[target_row_idx_q]
                            val_upper = q95_aligned.iloc[target_row_idx_q]
                            if pd.notna(val_lower) and pd.notna(val_upper):
                                # 确保点预测在区间内
                                point_val = predictions_series_for_shift_n.iloc[target_row_idx_q] if target_row_idx_q < len(predictions_series_for_shift_n) else np.nan
                                if pd.notna(point_val):
                                    val_lower = min(val_lower, point_val)
                                    val_upper = max(val_upper, point_val)
                                val_lower = np.clip(val_lower, 0, wfcapacity)
                                val_upper = np.clip(val_upper, 0, wfcapacity)
                                pred_lower = val_lower
                                pred_upper = val_upper
                    else:
                        logging.warning("shift %d 分位数预测跳过: 特征准备后无有效数据或特征列缺失", n_shift_value)
                except Exception as qe:
                    logging.warning("shift %d 分位数预测失败: %s", n_shift_value, qe)

            target_row_index_in_input_block = HISTORICAL_ROWS_NEEDED + (n_shift_value - MIN_SHIFT)

            if 0 <= target_row_index_in_input_block < len(predictions_series_for_shift_n):
                actual_prediction_value = predictions_series_for_shift_n.iloc[target_row_index_in_input_block]
                results_df_row_index = n_shift_value - MIN_SHIFT
                if 0 <= results_df_row_index < len(results_df):
                    results_df.loc[results_df_row_index, model_horizon_name] = actual_prediction_value
                    # 写入分位数区间列
                    if pred_lower is not None:
                        results_df.loc[results_df_row_index, f'{model_horizon_name}_lower'] = pred_lower
                        results_df.loc[results_df_row_index, f'{model_horizon_name}_upper'] = pred_upper
                else:
                    logging.error(f"Shift={n_shift_value}: Calculated results_df_row_index {results_df_row_index} is out of bounds for results_df (len {len(results_df)}). Prediction not stored.")
                    # Ensure column exists with NaN if specific assignment fails but column was expected
                    if model_horizon_name not in results_df.columns: results_df[model_horizon_name] = np.nan
            else:
                logging.error(f"Shift={n_shift_value}: Calculated target_row_index_in_input_block {target_row_index_in_input_block} is out of bounds for predictions_series (len {len(predictions_series_for_shift_n)}). Prediction not stored.")
                if model_horizon_name not in results_df.columns: results_df[model_horizon_name] = np.nan
        else:
            logging.warning(f"Failed to load model state for Shift={n_shift_value}. Skipping.")
            if model_horizon_name not in results_df.columns: results_df[model_horizon_name] = np.nan

    logging.info(f"Successfully loaded states for {successful_model_loads} models out of {MAX_SHIFT - MIN_SHIFT + 1} expected.")

    os.makedirs(PREDICTION_OUTPUT_SAVE_DIR, exist_ok=True)
    
    timestamp_str = effective_trigger_time_beijing.strftime('%Y%m%d%H%M%S')
    target_str = first_target_beijing.strftime('%Y%m%d%H%M')
    
    date_folder = effective_trigger_time_beijing.strftime('%Y%m%d')
    
    original_dir = os.path.join(PREDICTION_OUTPUT_SAVE_DIR, 'original', date_folder)
    long_dir = os.path.join(PREDICTION_OUTPUT_SAVE_DIR, 'long', date_folder)
    wide_dir = os.path.join(PREDICTION_OUTPUT_SAVE_DIR, 'wide', date_folder)
    
    os.makedirs(original_dir, exist_ok=True)
    os.makedirs(long_dir, exist_ok=True)
    os.makedirs(wide_dir, exist_ok=True)
    
    try:
        if 'wp_true_original_in_slot' in results_df.columns: # Should not exist anymore
            results_df = results_df.drop(columns=['wp_true_original_in_slot'])
        
        original_filename = f"pred_output_{farm_code}_{timestamp_str}_target_{target_str}.csv"
        original_path = os.path.join(original_dir, original_filename)
        results_df.to_csv(original_path, index=False)
        logging.info(f"Saved consolidated prediction results to: {original_path}")
        
        long_format_rows = []
        if not results_df.empty and 'Timestamp' in results_df.columns :
            for idx, row in results_df.iterrows():
                for col in results_df.columns:
                    if col.startswith('prediction_horizon_') and not pd.isna(row[col]):
                        long_format_rows.append({
                            'Timestamp': row['Timestamp'],
                            'wp_pred': row[col]
                        })
        
        long_format_df = pd.DataFrame(long_format_rows)
        if not long_format_df.empty:
            long_format_df = long_format_df.sort_values(by='Timestamp').reset_index(drop=True)
        
        long_filename = f"pred_long_{farm_code}_{timestamp_str}_target_{target_str}.csv"
        long_path = os.path.join(long_dir, long_filename)
        long_format_df.to_csv(long_path, index=False)
        logging.info(f"Saved long format prediction results to: {long_path}")
        
        wide_row = {}
        if not results_df.empty and 'Timestamp' in results_df.columns and len(results_df) > 0:
             wide_row['Timestamp'] = results_df['Timestamp'].iloc[0]
        else:
             wide_row['Timestamp'] = pd.NaT # Or handle as error if no timestamp
             logging.warning("Result df empty or missing timestamp for wide format, wide_row['Timestamp'] set to NaT.")


        for shift_value in range(MIN_SHIFT, MAX_SHIFT + 1):
            col_name = f'prediction_horizon_{shift_value}'
            row_idx = shift_value - MIN_SHIFT # This is the index in results_df for this shift's prediction (0 to 15)

            # New column name for the wide CSV, mapping internal shift 1 to output column wp_pred2, etc.
            wide_csv_col_name = f'wp_pred{shift_value + 1}'

            # Check if results_df has enough rows and the column exists
            if row_idx < len(results_df) and col_name in results_df.columns:
                wide_row[wide_csv_col_name] = results_df.iloc[row_idx][col_name]
            else:
                # Log if data is missing for expected prediction point
                if row_idx >= len(results_df):
                    logging.warning(f"Wide format: row_idx {row_idx} for internal shift {shift_value} (output {wide_csv_col_name}) is out of bounds for results_df (len {len(results_df)}). {wide_csv_col_name} will be NaN.")
                elif col_name not in results_df.columns:
                     logging.warning(f"Wide format: column {col_name} for internal shift {shift_value} (output {wide_csv_col_name}) not in results_df. {wide_csv_col_name} will be NaN.")
                wide_row[wide_csv_col_name] = np.nan

            # 分位数区间列
            lower_col = f'{col_name}_lower'
            upper_col = f'{col_name}_upper'
            if row_idx < len(results_df) and lower_col in results_df.columns:
                wide_row[f'wp_pred{shift_value + 1}_lower'] = results_df.iloc[row_idx][lower_col]
            if row_idx < len(results_df) and upper_col in results_df.columns:
                wide_row[f'wp_pred{shift_value + 1}_upper'] = results_df.iloc[row_idx][upper_col]

        wide_format_df = pd.DataFrame([wide_row])
        
        wide_filename = f"supershortl_wide_{farm_code}_{target_str}.csv" # This filename seems specific for DB upload
        wide_path = os.path.join(wide_dir, wide_filename)
        wide_format_df.to_csv(wide_path, index=False)
        logging.info(f"Saved wide format prediction results to: {wide_path}")
        
        try:
            api_base_url = os.environ.get('API_BASE_URL')
            if not api_base_url:
                backend_host = 'backend'
                backend_port = 5000
                try:
                    socket.gethostbyname(backend_host)
                    api_base_url = f"http://{backend_host}:{backend_port}"
                except socket.gaierror:
                    api_host = os.environ.get('BACKEND_API_HOST', 'localhost')
                    api_port = os.environ.get('BACKEND_API_PORT', 5000)
                    api_base_url = f"http://{api_host}:{api_port}"
            logging.info(f"API base URL: {api_base_url}")
            
            api_url = f"{api_base_url}/prediction2database/batch_supershortl_power"
            
            with open(wide_path, 'rb') as f:
                files = {'file': (os.path.basename(wide_path), f, 'text/csv')} # Use os.path.basename for filename
                response = requests.post(api_url, files=files, data={'farm_code': farm_code})
                
                if response.status_code == 201:
                    logging.info(f"Successfully uploaded wide format predictions to database. Response: {response.json()}")
                else:
                    logging.error(f"Failed to upload predictions to database. Status code: {response.status_code}, Response: {response.text}")
        
        except Exception as api_e:
            logging.error(f"Error calling prediction2database API: {api_e}", exc_info=True)
            
    except Exception as e:
        logging.error(f"Error saving prediction results: {e}", exc_info=True)

    logging.info(f"Prediction cycle completed for first target Beijing time: {first_target_beijing.strftime('%Y-%m-%d %H:%M')}")

if __name__ == '__main__':
    logging.info("Running predict_supershort.py directly...")
    main()
