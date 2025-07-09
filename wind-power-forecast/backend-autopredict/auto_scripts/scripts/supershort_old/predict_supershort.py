import pandas as pd
import os
import numpy as np
import time # For sleep
import sys
from datetime import datetime, timedelta, timezone # For time calculations
import logging
import requests  # 为API调用导入requests
import socket  # 为环境检测导入socket

# 添加backend-autopredict到sys.path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
# 这将导航到backend-autopredict目录（从supershort向上三级）
path_to_backend_autopredict = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
if path_to_backend_autopredict not in sys.path:
    sys.path.insert(0, path_to_backend_autopredict)
    # print(f"[DEBUG predict_supershort] 已添加到sys.path: {path_to_backend_autopredict}")

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

MIN_SHIFT = 2  # Corresponds to prediction_horizon_2 (actual N in power_diff_N)
MAX_SHIFT = 17 # Corresponds to prediction_horizon_17

HISTORICAL_ROWS_NEEDED = 20 # Number of 15-min intervals before the first target point
PREDICTION_POINTS = 16    # Number of future 15-min intervals to predict
TOTAL_ROWS_FOR_MODEL_INPUT = HISTORICAL_ROWS_NEEDED + PREDICTION_POINTS # 36 rows

# WP_TRUE_WAIT_TIMEOUT_SECONDS = 13 * 60 # 13 minutes
WP_TRUE_WAIT_MAX_ATTEMPTS = 26 # Roughly 13 minutes if checking every 30s
WP_TRUE_WAIT_SLEEP_SECONDS = 30 # Sleep duration between checks

def get_current_beijing_time():
    """Returns the current time in Beijing time without timezone info."""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(timezone.utc).astimezone(beijing_tz).replace(tzinfo=None)

def calculate_prediction_timestamps(current_time_beijing: datetime):
    """
    Calculates key timestamps for the prediction cycle based on Beijing time.
    The first prediction target time will be at least 15 minutes from the current_time_beijing,
    rounded up to the next 15-minute interval.
    The '8-minute rule' or specific scheduler offsets are NOT considered here;
    this function reacts purely to the current_time_beijing it's given.
    
    Returns timestamps in Beijing time without timezone info.
    """
    # 确保current_time_beijing没有时区信息
    if current_time_beijing.tzinfo is not None:
        current_time_beijing = current_time_beijing.replace(tzinfo=None)

    minimum_first_target_time = current_time_beijing + timedelta(minutes=15)
    
    temp_first_target = minimum_first_target_time.replace(second=0, microsecond=0)
    minutes_past_slot = temp_first_target.minute % 15
    
    if minutes_past_slot == 0 and minimum_first_target_time.second == 0 and minimum_first_target_time.microsecond == 0:
        first_target_prediction_time = temp_first_target
    else:
        minutes_to_add = 15 - minutes_past_slot
        if minutes_past_slot == 0: 
            minutes_to_add = 15 
        first_target_prediction_time = temp_first_target + timedelta(minutes=minutes_to_add)
        first_target_prediction_time = first_target_prediction_time.replace(minute=(first_target_prediction_time.minute // 15) * 15, second=0, microsecond=0)

    current_processing_slot_start = first_target_prediction_time - timedelta(minutes=30)
    expected_wp_true_timestamp = current_processing_slot_start
    last_target_prediction_time = first_target_prediction_time + timedelta(minutes=15 * (PREDICTION_POINTS - 1))
    earliest_historical_time_needed = first_target_prediction_time - timedelta(minutes=15 * HISTORICAL_ROWS_NEEDED)

    # 所有返回的时间都是北京时间
    return {
        "first_target_prediction_time": first_target_prediction_time,
        "expected_wp_true_timestamp": expected_wp_true_timestamp,
        "earliest_historical_time_needed": earliest_historical_time_needed,
        "last_target_prediction_time": last_target_prediction_time,
        "current_processing_slot_start": current_processing_slot_start
    }

def fetch_actual_power(session, start_beijing, end_beijing):
    """
    Fetches ActualPower data (timestamp, wp_true) within the Beijing time range.
    
    Args:
        session: Database session object
        start_beijing: Start time in Beijing time without timezone info
        end_beijing: End time in Beijing time without timezone info
    """
    logging.info(f"Fetching ActualPower from {start_beijing} to {end_beijing}")
    query = session.query(ActualPower.timestamp, ActualPower.wp_true)\
                   .filter(ActualPower.timestamp >= start_beijing, ActualPower.timestamp <= end_beijing)
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

def wait_for_wp_true(session, target_timestamp_beijing, current_slot_start_beijing):
    """
    Waits for wp_true data for the target_timestamp_beijing to appear in ActualPower.
    
    Args:
        session: Database session object
        target_timestamp_beijing: The timestamp (in Beijing time, no timezone info) to check for wp_true
        current_slot_start_beijing: Current processing slot start time (in Beijing time) for timeout calculation
    """
    logging.info(f"Waiting for wp_true for Beijing timestamp: {target_timestamp_beijing}")
    # Define the cutoff time for waiting: 13 minutes past the target_timestamp_beijing's hour and minute, 
    # but not exceeding the end of the current 15-min processing slot minus a safety margin.
    # Example: if target is 15:00:00, wait_deadline_minute is 13.
    # If current_slot_start_beijing is 15:00:00, the processing ends around 15:14:59. Safe stop is ~15:13:00.
    
    wait_deadline_beijing = target_timestamp_beijing.replace(minute=(target_timestamp_beijing.minute // 15) * 15, second=0, microsecond=0) + timedelta(minutes=13)
    
    # Ensure wait_deadline_beijing does not go into the next slot significantly
    # Max wait is effectively tied to the scheduler running every 15 mins. 
    # If scheduler runs at 15:00:XX for target 15:00:00 wp_true, it can wait until ~15:13:XX.
    absolute_max_wait_time_beijing = current_slot_start_beijing + timedelta(minutes=13, seconds=30) # Safety margin of 1.5 mins before next cycle

    # 两者都是北京时间，可以直接比较
    logging.info(f"wait_deadline_beijing: {wait_deadline_beijing}, absolute_max_wait_time_beijing: {absolute_max_wait_time_beijing}")
    final_wait_deadline_beijing = min(wait_deadline_beijing, absolute_max_wait_time_beijing)

    attempts = 0
    # get_current_beijing_time()返回北京时间
    while get_current_beijing_time() < final_wait_deadline_beijing:
        attempts += 1
        logging.info(f"Attempt {attempts}: Checking for wp_true for Beijing time {target_timestamp_beijing} (wait until Beijing time {final_wait_deadline_beijing})...")
        # Query for the specific timestamp - the database timestamp is in Beijing time without timezone
        power_data = session.query(ActualPower.wp_true)\
                              .filter(ActualPower.timestamp == target_timestamp_beijing)\
                              .first()
        if power_data and power_data.wp_true is not None:
            logging.info(f"SUCCESS: wp_true for Beijing time {target_timestamp_beijing} found.")
            return True
        
        if attempts >= WP_TRUE_WAIT_MAX_ATTEMPTS:
            logging.warning(f"TIMEOUT: Max attempts ({WP_TRUE_WAIT_MAX_ATTEMPTS}) reached waiting for wp_true for Beijing time {target_timestamp_beijing}.")
            return False
            
        time.sleep(WP_TRUE_WAIT_SLEEP_SECONDS)
    
    logging.warning(f"TIMEOUT: Deadline Beijing time {final_wait_deadline_beijing} reached waiting for wp_true for Beijing time {target_timestamp_beijing}.")
    return False


def handle_wp_true_missing(data: pd.DataFrame, wp_true_col: str = 'wp_true') -> pd.DataFrame:
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
    processed_data = interpolate_and_ffill_wp_true(data, wp_true_col)
    
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
    """Main prediction function triggered every 15 minutes."""
    if not DB_ACCESS_AVAILABLE:
        logging.critical("Database modules not available. Prediction cannot proceed.")
        return

    current_time_beijing = get_current_beijing_time()
    logging.info(f"Starting prediction cycle at Beijing time: {current_time_beijing.strftime('%Y-%m-%d %H:%M:%S')}")

    time_params = calculate_prediction_timestamps(current_time_beijing)
    first_target_beijing = time_params["first_target_prediction_time"]
    expected_wp_true_beijing = time_params["expected_wp_true_timestamp"]
    earliest_hist_beijing = time_params["earliest_historical_time_needed"]
    last_target_beijing = time_params["last_target_prediction_time"]
    current_slot_start_beijing = time_params["current_processing_slot_start"] 

    logging.info(f"  Current processing slot starts at: {current_slot_start_beijing.strftime('%Y-%m-%d %H:%M')}")
    logging.info(f"  First prediction target time: {first_target_beijing.strftime('%Y-%m-%d %H:%M')}")
    logging.info(f"  Expected wp_true timestamp: {expected_wp_true_beijing.strftime('%Y-%m-%d %H:%M')}")
    logging.info(f"  Earliest historical data needed: {earliest_hist_beijing.strftime('%Y-%m-%d %H:%M')}")
    logging.info(f"  Last prediction target time: {last_target_beijing.strftime('%Y-%m-%d %H:%M')}")

    # --- Data Fetching and Preparation ---
    # Define the path for the input CSV (this will be THE source for model input)
    # 文件名称使用北京时间
    input_csv_filename = f"model_input_target_{first_target_beijing.strftime('%Y%m%d%H%M')}.csv"
    input_csv_filepath = os.path.join(PREDICTION_INPUT_SAVE_DIR, input_csv_filename) # PREDICTION_INPUT_SAVE_DIR is PREC_SV_FOLDER
    os.makedirs(PREDICTION_INPUT_SAVE_DIR, exist_ok=True) # Ensure directory exists

    if not os.path.exists(input_csv_filepath):
        logging.info(f"Input CSV {input_csv_filepath} not found. Fetching data from database to create it.")
        try:
            df_for_csv = pd.DataFrame() # Initialize
            with db_session() as session:
                # 1. Wait for the expected wp_true
                wait_for_wp_true(session, expected_wp_true_beijing, current_slot_start_beijing)

                # 2. Fetch ActualPower data (historical wp_true)
                actual_power_fetch_start_beijing = earliest_hist_beijing - timedelta(hours=1) # Fetch a little extra for ffill robustness
                
                # 数据库和内部使用的都是北京时间，不需要转换
                logging.info(f"Using Beijing time for database queries:")
                logging.info(f"  actual_power_fetch_start: {actual_power_fetch_start_beijing}")
                logging.info(f"  expected_wp_true: {expected_wp_true_beijing}")
                logging.info(f"  earliest_hist: {earliest_hist_beijing}")
                logging.info(f"  last_target: {last_target_beijing}")
                
                # 使用北京时间查询数据库
                actual_power_df = fetch_actual_power(session, actual_power_fetch_start_beijing, expected_wp_true_beijing)
                
                # 3. Fetch TrainPreShort data (features for history and future)
                features_df = fetch_train_pre_short(session, earliest_hist_beijing, last_target_beijing)

            if features_df.empty:
                logging.error("No feature data (TrainPreShort) retrieved. Cannot create CSV or proceed.")
                return

            # 4. Merge features and actual power
            merged_df = pd.merge(features_df, actual_power_df, on='Timestamp', how='left')
            logging.info(f"Merged features and actual power. Resulting shape: {merged_df.shape}")
            
            merged_df.sort_values(by='Timestamp', inplace=True)
            merged_df.drop_duplicates(subset=['Timestamp'], keep='first', inplace=True)
            merged_df.reset_index(drop=True, inplace=True)

            # 5. Data Slicing: Get the 36 rows for model input CSV
            try:
                logging.info(f"Looking for first_target_beijing {first_target_beijing} in merged_df (min={merged_df['Timestamp'].min()}, max={merged_df['Timestamp'].max()})")
                if first_target_beijing.tzinfo is not None and pd.api.types.is_datetime64_dtype(merged_df['Timestamp']) and merged_df['Timestamp'].dt.tz is not None:
                    # Both have timezone info, make sure they're comparable
                    first_target_index = merged_df[merged_df['Timestamp'] == first_target_beijing].index[0]
                else:
                    # If either is naive, convert for comparison
                    logging.info("Converting timestamps to compatible format for comparison")
                    if first_target_beijing.tzinfo is not None:
                        first_target_naive = first_target_beijing.replace(tzinfo=None)
                    else:
                        first_target_naive = first_target_beijing
                        
                    if pd.api.types.is_datetime64_dtype(merged_df['Timestamp']) and merged_df['Timestamp'].dt.tz is not None:
                        merged_df['Timestamp_temp'] = merged_df['Timestamp'].dt.tz_convert('UTC').dt.tz_localize(None)
                        first_target_index = merged_df[merged_df['Timestamp_temp'] == first_target_naive].index[0]
                        merged_df.drop('Timestamp_temp', axis=1, inplace=True)
                    else:
                        first_target_index = merged_df[merged_df['Timestamp'] == first_target_naive].index[0]
                        
                logging.info(f"Found first_target_beijing at index {first_target_index}")
            except IndexError:
                logging.error(f"Timestamp {first_target_beijing.strftime('%Y-%m-%d %H:%M')} not found in merged data. Cannot slice for model input CSV.")
                if len(merged_df) < 100 and not merged_df.empty:
                    logging.info(f"Available timestamp range in merged_df: {merged_df['Timestamp'].min()} to {merged_df['Timestamp'].max()}")
                return

            start_slice_idx = first_target_index - HISTORICAL_ROWS_NEEDED
            end_slice_idx = first_target_index + PREDICTION_POINTS

            if start_slice_idx < 0:
                logging.warning(f"Not enough historical data for CSV. Available: {first_target_index} rows. Using all available historical data.")
                start_slice_idx = 0
            
            if end_slice_idx > len(merged_df):
                logging.warning(f"Not enough future data for CSV. Available until index {len(merged_df)-1}. Using all available future data.")
                end_slice_idx = len(merged_df)

            df_for_csv = merged_df.iloc[start_slice_idx:end_slice_idx].copy()
            logging.info(f"Sliced {len(df_for_csv)} rows for CSV input (target {TOTAL_ROWS_FOR_MODEL_INPUT} rows).")

            if len(df_for_csv) < TOTAL_ROWS_FOR_MODEL_INPUT:
                 logging.warning(f"Could not obtain the full {TOTAL_ROWS_FOR_MODEL_INPUT} rows for CSV input. Only got {len(df_for_csv)}. Predictions might be compromised if loaded.")
            
            if df_for_csv.empty:
                 logging.error("Data sliced for CSV is empty. Cannot create CSV or proceed.")
                 return

            # Save the fetched and processed data to the CSV
            df_for_csv.to_csv(input_csv_filepath, index=False)
            logging.info(f"Saved data fetched from DB to: {input_csv_filepath}")

        except Exception as e_fetch_save:
            logging.error(f"Error during data fetching from DB or saving to {input_csv_filepath}: {e_fetch_save}", exc_info=True)
            return # Cannot proceed if CSV creation fails

    # Now, load raw_input_df_for_models from the CSV (it should exist: pre-existing or just created)
    raw_input_df_for_models = pd.DataFrame()
    try:
        logging.info(f"Loading model input from CSV: {input_csv_filepath}")
        raw_input_df_for_models = pd.read_csv(input_csv_filepath, parse_dates=['Timestamp'])
        
        if not raw_input_df_for_models.empty and 'Timestamp' in raw_input_df_for_models.columns:
            # 确保Timestamp列是无时区信息的日期时间类型
            if raw_input_df_for_models['Timestamp'].dt.tz is not None:
                raw_input_df_for_models['Timestamp'] = raw_input_df_for_models['Timestamp'].dt.tz_localize(None)
        
        logging.info(f"Successfully loaded {len(raw_input_df_for_models)} rows from {input_csv_filepath}. Shape: {raw_input_df_for_models.shape}")

        if not raw_input_df_for_models.empty and len(raw_input_df_for_models) != TOTAL_ROWS_FOR_MODEL_INPUT :
             logging.warning(f"Loaded CSV {input_csv_filepath} has {len(raw_input_df_for_models)} rows, but expected {TOTAL_ROWS_FOR_MODEL_INPUT} based on configuration.")
             # Potentially add more robust handling if row count is critical and mismatch means failure

    except Exception as e_load:
        logging.error(f"Failed to load data from {input_csv_filepath}: {e_load}", exc_info=True)
        # raw_input_df_for_models will remain empty if load fails, handled by the check below.
    
    # Check if data loading (either from cache or fresh fetch+cache) was successful
    if raw_input_df_for_models.empty:
        logging.error(f"Model input DataFrame is empty after attempting to load/create from {input_csv_filepath}. Prediction cannot proceed.")
        return

    # --- Preprocessing and Prediction --- 
    # 7. General preprocessing (from predictor_model.py, should handle its own NaNs etc.)
    logging.info("Starting general preprocessing on the 36-row input...")
    # preprocess_data creates a copy, so raw_input_df_for_models is preserved if needed
    processed_input_for_models = preprocess_data(raw_input_df_for_models) 
    logging.info("General preprocessing complete.")

    # 8. Specific handling for wp_true (ffill) in the 36-row slice
    logging.info("Applying ffill to 'wp_true' in the 36-row input...")
    processed_input_for_models = handle_wp_true_missing(processed_input_for_models, wp_true_col='wp_true')
    logging.info("'wp_true' ffill complete.")

    # Prepare DataFrame to store final predictions for the 16 target points
    # Timestamps for these 16 points are from the latter part of raw_input_df_for_models
    prediction_target_timestamps = raw_input_df_for_models['Timestamp'].iloc[HISTORICAL_ROWS_NEEDED:HISTORICAL_ROWS_NEEDED + PREDICTION_POINTS].copy()
    
    # Check if we actually got 16 timestamps
    if len(prediction_target_timestamps) < PREDICTION_POINTS:
        logging.warning(f"Could only identify {len(prediction_target_timestamps)} target timestamps for results out of {PREDICTION_POINTS} expected.")
        # If there are absolutely no target timestamps, we can't form results meaningfully
        if prediction_target_timestamps.empty:
            logging.error("No target timestamps identified from input data. Cannot create results DataFrame.")
            return 

    # results_df = pd.DataFrame({'Timestamp': prediction_target_timestamps})
    # 关键修改：初始化 results_df 时使用 .values 来创建从0开始的索引
    results_df = pd.DataFrame({'Timestamp': prediction_target_timestamps.values})

    # If wp_true (after ffill) is available in processed_input_for_models for these future points (it shouldn't be, but for safety)
    # we add it for comparison. More likely, it will be NaN.
    if 'wp_true' in processed_input_for_models.columns:
        # Align wp_true_processed with the prediction_target_timestamps
        temp_wp_true = processed_input_for_models.set_index('Timestamp')['wp_true'].reindex(prediction_target_timestamps)
        results_df['wp_true_original_in_slot'] = temp_wp_true.values

    successful_model_loads = 0
    for n_shift_value in range(MIN_SHIFT, MAX_SHIFT + 1):
        model_horizon_name = f'prediction_horizon_{n_shift_value}'
        logging.info(f"\n{'='*10} Predicting for Horizon (Shift) = {n_shift_value} {'='*10}")

        model_n_dir = os.path.join(MODEL_INPUT_DIR, f'shift_{n_shift_value}')
        if not os.path.isdir(model_n_dir):
            logging.warning(f"Model directory not found for Shift={n_shift_value} at {model_n_dir}. Skipping.")
            results_df[model_horizon_name] = np.nan # Fill column with NaN for this missing model
            continue

        predictor = WindPowerPredictor(n_shift=n_shift_value)
        if predictor.load_state(model_n_dir):
            successful_model_loads +=1
            # Predictor's predict method handles its own feature engineering using the input
            # The input (processed_input_for_models) should be the 36-row block
            predictions_series_for_shift_n = predictor.predict(processed_input_for_models)
            
            # The predictions_series_for_shift_n is indexed by the original index of processed_input_for_models.
            # We need to get the single prediction value that corresponds to this shift's target time.
            # The Nth model (shift=N) predicts power_diff_N, which helps reconstruct power at time t.
            # The actual target point for shift N is the Nth point *within the PREDICTION_POINTS part of the 36 rows*.
            # Example: shift_2 model predicts for the 2nd point of the 16 future points.
            # The index in `predictions_series_for_shift_n` we care about is `HISTORICAL_ROWS_NEEDED + (n_shift_value - 1)`
            # if MIN_SHIFT is 1. If MIN_SHIFT is 2, then it's HISTORICAL_ROWS_NEEDED + (n_shift_value - MIN_SHIFT)
            
            # The `predictor.predict` should return a Series whose index matches the input `processed_input_for_models`.
            # The value at index `HISTORICAL_ROWS_NEEDED + (n_shift_value - MIN_SHIFT)` of this series is the one prediction we need.
            # This is the prediction for the (n_shift_value - MIN_SHIFT + 1)-th point in the 16-point future window.
            target_row_index_in_36_block = HISTORICAL_ROWS_NEEDED + (n_shift_value - MIN_SHIFT)

            if 0 <= target_row_index_in_36_block < len(predictions_series_for_shift_n):
                actual_prediction_value = predictions_series_for_shift_n.iloc[target_row_index_in_36_block]
                # The results_df is indexed 0 to 15 for the 16 prediction points.
                # The (n_shift_value - MIN_SHIFT)-th row in results_df gets this prediction.
                results_df_row_index = n_shift_value - MIN_SHIFT
                if 0 <= results_df_row_index < len(results_df):
                    results_df.loc[results_df_row_index, model_horizon_name] = actual_prediction_value
                else:
                    logging.error(f"Shift={n_shift_value}: Calculated results_df_row_index {results_df_row_index} is out of bounds for results_df (len {len(results_df)}). Prediction not stored.")
                    results_df[model_horizon_name] = np.nan # Fill if specific assignment fails
            else:
                logging.error(f"Shift={n_shift_value}: Calculated target_row_index_in_36_block {target_row_index_in_36_block} is out of bounds for predictions_series (len {len(predictions_series_for_shift_n)}). Prediction not stored.")
                results_df[model_horizon_name] = np.nan # Fill if specific assignment fails
        else:
            logging.warning(f"Failed to load model state for Shift={n_shift_value}. Skipping.")
            results_df[model_horizon_name] = np.nan # Fill column with NaN

    logging.info(f"Successfully loaded states for {successful_model_loads} models out of {MAX_SHIFT - MIN_SHIFT + 1} expected.")

    # Save the final prediction results
    # 基础输出目录
    os.makedirs(PREDICTION_OUTPUT_SAVE_DIR, exist_ok=True)
    
    # 生成当前时间的字符串（用于文件名）
    timestamp_str = current_time_beijing.strftime('%Y%m%d%H%M%S')
    # 生成目标时间的字符串（用于文件名）
    target_str = first_target_beijing.strftime('%Y%m%d%H%M')
    
    # 创建按类型和日期分类的目录结构
    date_folder = current_time_beijing.strftime('%Y%m%d')
    
    # 创建类型子目录
    original_dir = os.path.join(PREDICTION_OUTPUT_SAVE_DIR, 'original', date_folder)
    long_dir = os.path.join(PREDICTION_OUTPUT_SAVE_DIR, 'long', date_folder)
    wide_dir = os.path.join(PREDICTION_OUTPUT_SAVE_DIR, 'wide', date_folder)
    
    # 确保目录存在
    os.makedirs(original_dir, exist_ok=True)
    os.makedirs(long_dir, exist_ok=True)
    os.makedirs(wide_dir, exist_ok=True)
    
    # 生成文件名
    timestamp_str = current_time_beijing.strftime('%Y%m%d%H%M%S')
    target_str = first_target_beijing.strftime('%Y%m%d%H%M')
    
    try:
        # Remove wp_true_original_in_slot column if it exists
        if 'wp_true_original_in_slot' in results_df.columns:
            results_df = results_df.drop(columns=['wp_true_original_in_slot'])
        
        # 保存原始格式文件到对应目录
        original_filename = f"pred_output_{timestamp_str}_target_{target_str}.csv"
        original_path = os.path.join(original_dir, original_filename)
        results_df.to_csv(original_path, index=False)
        logging.info(f"Saved consolidated prediction results to: {original_path}")
        
        # Format 1: Long format with Timestamp and a single prediction column
        long_format_rows = []
        for idx, row in results_df.iterrows():
            for col in results_df.columns:
                if col.startswith('prediction_horizon_') and not pd.isna(row[col]):
                    long_format_rows.append({
                        'Timestamp': row['Timestamp'],
                        'wp_pred': row[col]
                    })
        
        # Create DataFrame from list of rows
        long_format_df = pd.DataFrame(long_format_rows)
        
        # Sort by Timestamp if not empty
        if not long_format_df.empty:
            long_format_df = long_format_df.sort_values(by='Timestamp').reset_index(drop=True)
        
        # 保存长格式文件到对应目录
        long_filename = f"pred_long_{timestamp_str}_target_{target_str}.csv"
        long_path = os.path.join(long_dir, long_filename)
        long_format_df.to_csv(long_path, index=False)
        logging.info(f"Saved long format prediction results to: {long_path}")
        
        # Format 2: Wide format with a single row
        wide_row = {'Timestamp': results_df['Timestamp'].iloc[0]}
        
        # Add prediction values from diagonal elements
        for shift_value in range(MIN_SHIFT, MAX_SHIFT + 1):
            col_name = f'prediction_horizon_{shift_value}'
            row_idx = shift_value - MIN_SHIFT
            if row_idx < len(results_df) and col_name in results_df.columns:
                wide_row[f'wp_pred{shift_value}'] = results_df.iloc[row_idx][col_name]
            else:
                wide_row[f'wp_pred{shift_value}'] = np.nan
        
        # Create DataFrame from single row
        wide_format_df = pd.DataFrame([wide_row])
        
        # 只保存一个宽格式文件（用于数据库上传）
        wide_filename = f"supershortl_wide_{target_str}.csv"
        wide_path = os.path.join(wide_dir, wide_filename)
        wide_format_df.to_csv(wide_path, index=False)
        logging.info(f"Saved wide format prediction results to: {wide_path}")
        
        # 上传到数据库
        try:
            # 动态判断环境：尝试解析'backend'主机名
            backend_host = 'backend'
            backend_port = 5000
            try:
                # 尝试解析Docker服务名
                socket.gethostbyname(backend_host)
                # 如果解析成功，说明在Docker环境中
                api_base_url = f"http://{backend_host}:{backend_port}"
                logging.info(f"Running in Docker environment, using API base URL: {api_base_url}")
            except socket.gaierror:
                # 如果解析失败，尝试检查环境变量
                api_host = os.environ.get('BACKEND_API_HOST', 'localhost')
                api_port = os.environ.get('BACKEND_API_PORT', 5000)
                api_base_url = f"http://{api_host}:{api_port}"
                logging.info(f"Running in local environment, using API base URL: {api_base_url}")
            
            # 构建完整的API URL
            api_url = f"{api_base_url}/prediction2database/batch_supershortl_power"
            
            # 打开宽格式文件准备上传
            with open(wide_path, 'rb') as f:
                files = {'file': (wide_filename, f, 'text/csv')}
                
                # 发送POST请求
                response = requests.post(api_url, files=files)
                
                # 检查响应
                if response.status_code == 201:
                    logging.info(f"Successfully uploaded wide format predictions to database. Response: {response.json()}")
                else:
                    logging.error(f"Failed to upload predictions to database. Status code: {response.status_code}, Response: {response.text}")
        
        except Exception as api_e:
            logging.error(f"Error calling prediction2database API: {api_e}", exc_info=True)
            
    except Exception as e:
        logging.error(f"Error saving prediction results: {e}", exc_info=True)

    logging.info(f"Prediction cycle completed for first target Beijing time: {first_target_beijing.strftime('%Y-%m-%d %H:%M')}\n")

if __name__ == '__main__':
    # This is usually run by the scheduler, but can be run directly for testing.
    # Ensure DB is accessible and models are in MODEL_INPUT_DIR.
    # Example: Create dummy db_models and db_session for direct execution IF NEEDED and DB_ACCESS_AVAILABLE is True.
    # For actual use, these should be correctly set up in your project structure.
    
    # Logging is now configured at the top of the script.
    # We can ensure handlers are present if needed, though global config should cover it.
    # Example: if not predict_logger.hasHandlers(): ... (add default console for direct run)
 
    logging.info("Running predict_supershort.py directly...")
    main()