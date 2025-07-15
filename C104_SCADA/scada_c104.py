import c104
import time
import logging
import threading
import configparser
import os
from datetime import datetime, timezone, timedelta
import requests
import csv

# --- 北京时区常量和转换函数 ---
BEIJING_TZ = timezone(timedelta(hours=8), name='Asia/Shanghai')

def to_beijing_time(dt):
    """将datetime对象转换为北京时间"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # 假设naive datetime是UTC时间
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING_TZ)

def now_beijing():
    """获取当前北京时间"""
    return datetime.now(BEIJING_TZ)

def now_utc():
    """获取当前UTC时间"""
    return datetime.now(timezone.utc)

# --- 默认配置参数 ---
DEFAULT_SCADA_SERVER_IP = "127.0.0.1"
DEFAULT_SCADA_SERVER_PORT = 2404
DEFAULT_COMMON_ADDRESS = 1
DEFAULT_ORIGINATOR_ADDRESS = 0
DEFAULT_INTERROGATION_INTERVAL_SECONDS = 60
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FILE = "logs/scada_client.log" # 注意：实际路径由 configure_scada_logging 处理
DEFAULT_BACKUP_COUNT = 30
DEFAULT_CONSOLE_OUTPUT = True
DEFAULT_POINTS_CONFIG = {}
DEFAULT_UPLOAD_TARGET_IOA = None
DEFAULT_API_UPLOAD_URL = None
# UPLOAD_INTERVAL_MINUTES 对于刻钟上传不再是主要配置，但可以保留或移除

# --- 读取配置文件 ---
config = configparser.ConfigParser()
CONFIG_FILE_PATH = 'config.ini'
script_dir = os.path.dirname(os.path.abspath(__file__))
absolute_config_path = os.path.join(script_dir, CONFIG_FILE_PATH)

# 添加调试信息
print(f"DEBUG: Script directory: {script_dir}")
print(f"DEBUG: Config file path: {absolute_config_path}")
print(f"DEBUG: Config file exists: {os.path.exists(absolute_config_path)}")
if os.path.exists(script_dir):
    print(f"DEBUG: Files in script directory: {os.listdir(script_dir)}")

# 初始化配置变量为默认值
SCADA_SERVER_IP = DEFAULT_SCADA_SERVER_IP
SCADA_SERVER_PORT = DEFAULT_SCADA_SERVER_PORT
COMMON_ADDRESS = DEFAULT_COMMON_ADDRESS
ORIGINATOR_ADDRESS = DEFAULT_ORIGINATOR_ADDRESS
INTERROGATION_INTERVAL_SECONDS = DEFAULT_INTERROGATION_INTERVAL_SECONDS
LOG_LEVEL_STR = DEFAULT_LOG_LEVEL
LOG_FILE_PATH_CFG = DEFAULT_LOG_FILE # _CFG 后缀表示从配置文件读取或其默认值
BACKUP_COUNT_CFG = DEFAULT_BACKUP_COUNT
CONSOLE_OUTPUT_CFG = DEFAULT_CONSOLE_OUTPUT
points_config_from_file = DEFAULT_POINTS_CONFIG.copy()
UPLOAD_TARGET_IOA_STR = None # 用于从配置读取目标IOA的字符串
API_UPLOAD_URL = DEFAULT_API_UPLOAD_URL

if os.path.exists(absolute_config_path):
    try:
        config.read(absolute_config_path, encoding='utf-8')
        print(f"Successfully read config file: {absolute_config_path}") # 在 logger 配置前用 print

        if config.has_section('IEC104_Connection'):
            iec_conn_section = config['IEC104_Connection']
            SCADA_SERVER_IP = iec_conn_section.get('SCADA_SERVER_IP', DEFAULT_SCADA_SERVER_IP)
            SCADA_SERVER_PORT = iec_conn_section.getint('SCADA_SERVER_PORT', DEFAULT_SCADA_SERVER_PORT)
            COMMON_ADDRESS = iec_conn_section.getint('CASDU_ADDRESS', DEFAULT_COMMON_ADDRESS)
            print(f"DEBUG: Loaded IEC104_Connection - IP: {SCADA_SERVER_IP}, PORT: {SCADA_SERVER_PORT}")
        else: print("Config section [IEC104_Connection] not found. Using defaults.")

        if config.has_section('Client_Config'):
            ORIGINATOR_ADDRESS = config['Client_Config'].getint('ORIGINATOR_ADDRESS', DEFAULT_ORIGINATOR_ADDRESS)
        else: print("Config section [Client_Config] not found. Using defaults.")
        
        if config.has_section('Points'): 
            points_config_from_file = dict(config.items('Points'))
            print(f"DEBUG: Loaded Points section: {points_config_from_file}")
        else: print("Config section [Points] not found.")

        if config.has_section('TaskConfig'):
            task_cfg_section = config['TaskConfig']
            INTERROGATION_INTERVAL_SECONDS = task_cfg_section.getint('INNER_LOOP_FETCH_INTERVAL_SECONDS', DEFAULT_INTERROGATION_INTERVAL_SECONDS)
            UPLOAD_TARGET_IOA_STR = task_cfg_section.get('UPLOAD_TARGET_IOA') # 可能为 None
            print(f"DEBUG: Loaded TaskConfig - UPLOAD_TARGET_IOA_STR: {UPLOAD_TARGET_IOA_STR}")
        else: print("Config section [TaskConfig] not found. Using defaults.")

        if config.has_section('API'): 
            API_UPLOAD_URL = config['API'].get('UPLOAD_URL', DEFAULT_API_UPLOAD_URL)
            print(f"DEBUG: Loaded API section - UPLOAD_URL: {API_UPLOAD_URL}")
        else: print("Config section [API] not found. Using defaults.")

        if config.has_section('Logging'):
            logging_section = config['Logging']
            LOG_LEVEL_STR = logging_section.get('LOG_LEVEL', DEFAULT_LOG_LEVEL).upper()
            LOG_FILE_PATH_CFG = logging_section.get('LOG_FILE', DEFAULT_LOG_FILE)
            BACKUP_COUNT_CFG = logging_section.getint('BACKUP_COUNT', DEFAULT_BACKUP_COUNT)
            CONSOLE_OUTPUT_CFG = logging_section.getboolean('CONSOLE_OUTPUT', DEFAULT_CONSOLE_OUTPUT)
        else: print("Config section [Logging] not found. Using defaults.")
    except Exception as e:
        print(f"Error reading config file '{absolute_config_path}': {e}. Using defaults.")
else:
    print(f"Config file '{absolute_config_path}' not found. Using defaults.")

# --- 日志配置模块 (logging_config.py) ---
# 假设 logging_config.py 与此脚本在同一目录或Python路径中
try:
    from logging_config import configure_scada_logging
    logger = configure_scada_logging(
        logger_name="SCADAClient", log_file_path=LOG_FILE_PATH_CFG, log_level=LOG_LEVEL_STR,
        script_dir=script_dir, backup_count=BACKUP_COUNT_CFG, console_output=CONSOLE_OUTPUT_CFG
    )
except ImportError:
    print("CRITICAL: logging_config.py not found. Using basic logging.")
    logging.basicConfig(level=getattr(logging, LOG_LEVEL_STR, logging.INFO),
                        format='%(asctime)s - %(levelname)s - [%(threadName)s] %(message)s')
    logger = logging.getLogger("SCADAClient_Fallback") # 使用一个回退的logger

logger.info("--- SCADA Client Logging Initialized ---")
logger.info(f"Using config file: {absolute_config_path if os.path.exists(absolute_config_path) else 'Not found, using defaults'}")

# --- 将字符串类型的点类型转换为 c104.Type 枚举 ---
PRE_DEFINE_POINTS = {}
for ioa_str, type_name_str in points_config_from_file.items():
    try:
        ioa = int(ioa_str)
        point_type_enum = getattr(c104.Type, type_name_str.strip().upper(), None)
        if point_type_enum: PRE_DEFINE_POINTS[ioa] = point_type_enum
        else: logger.warning(f"Invalid point type name '{type_name_str}' for IOA {ioa}. Skipping.")
    except ValueError: logger.warning(f"Invalid IOA '{ioa_str}'. Skipping.")

# --- 转换配置中的目标IOA ---
TARGET_IOA_FOR_UPLOAD = None
if UPLOAD_TARGET_IOA_STR:
    try: TARGET_IOA_FOR_UPLOAD = int(UPLOAD_TARGET_IOA_STR)
    except ValueError: logger.error(f"Invalid UPLOAD_TARGET_IOA in config: '{UPLOAD_TARGET_IOA_STR}'. Upload disabled.")
else: logger.info("UPLOAD_TARGET_IOA not configured. Upload disabled.")


# --- 打印加载的配置 ---
logger.info("--- Configuration Loaded ---")
logger.info(f"SCADA_SERVER_IP: {SCADA_SERVER_IP}")
logger.info(f"SCADA_SERVER_PORT: {SCADA_SERVER_PORT}")
logger.info(f"COMMON_ADDRESS: {COMMON_ADDRESS}")
logger.info(f"ORIGINATOR_ADDRESS: {ORIGINATOR_ADDRESS}")
logger.info(f"INTERROGATION_INTERVAL_SECONDS: {INTERROGATION_INTERVAL_SECONDS}")
logger.info(f"PRE_DEFINE_POINTS (from config): { {k: v.name for k, v in PRE_DEFINE_POINTS.items()} }")
logger.info(f"LOG_LEVEL: {LOG_LEVEL_STR}")
logger.info(f"LOG_FILE_PATH: {LOG_FILE_PATH_CFG}") # 使用 _CFG 后缀的变量名
logger.info(f"TARGET_IOA_FOR_UPLOAD: {TARGET_IOA_FOR_UPLOAD}")
logger.info(f"API_UPLOAD_URL: {API_UPLOAD_URL}")
logger.info("--- End Configuration ---")

# --- 全局变量 (运行时状态) ---
stop_event = threading.Event()
station_initial_interrogation_done = {}
connection_unmuted_flags = {}
latest_point_data = {} # key: ioa, value: {"value": data, "timestamp": datetime, "quality_good": bool}
last_upload_quarter_minute = -1 # 跟踪上次 GI 触发的刻钟上传分钟数
last_pre_quarter_approximation_minute_processed = -1 # 跟踪上次预上传的分钟数 (14, 29, 44, 59)
global_persistence = None # 全局数据持久化对象

# --- CSV文件写入函数 (增强版，支持状态记录) ---
def write_to_csv(timestamp_beijing, value, logger, persistence=None):
    """
    将时间戳和数据写入CSV文件
    CSV文件按日生成，使用北京时间
    支持状态记录和错误恢复
    """
    # 记录写入尝试
    csv_data = {
        'timestamp': timestamp_beijing.isoformat() if hasattr(timestamp_beijing, 'isoformat') else str(timestamp_beijing),
        'value': value,
        'attempt_time': datetime.now(BEIJING_TZ).isoformat()
    }
    
    try:
        # 创建CSV文件目录 - 使用相对于data目录的路径
        csv_dir = os.path.join("data", "csv_data")
        if not os.path.exists(csv_dir):
            os.makedirs(csv_dir)
            logger.info(f"CSV WRITE: Created directory {csv_dir}")
        
        # 生成文件名（按日期）
        date_str = timestamp_beijing.strftime("%Y%m%d")
        csv_filename = f"scada_data_{date_str}.csv"
        csv_filepath = os.path.join(csv_dir, csv_filename)
        
        # 检查文件是否存在，如果不存在则创建并写入表头
        file_exists = os.path.exists(csv_filepath)
        
        with open(csv_filepath, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # 如果是新文件，写入表头
            if not file_exists:
                writer.writerow(['timestamp', 'value'])
                logger.info(f"CSV WRITE: Created new CSV file with header: {csv_filepath}")
            
            # 写入数据
            timestamp_str = timestamp_beijing.strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([timestamp_str, value])
            logger.info(f"CSV WRITE: Successfully wrote data to {csv_filepath}: {timestamp_str}, {value}")
            
        # 记录成功写入
        if persistence:
            success_data = csv_data.copy()
            success_data.update({
                'success': True,
                'file_path': csv_filepath,
                'completed_time': datetime.now(BEIJING_TZ).isoformat()
            })
            # 不需要记录成功的操作到pending_operations中
            
        return True
        
    except Exception as e:
        error_msg = f"CSV WRITE: Error writing to CSV file: {e}"
        logger.error(error_msg, exc_info=True)
        
        # 记录失败的写入
        if persistence:
            csv_data.update({
                'success': False,
                'error': error_msg,
                'error_type': 'CSVWriteError'
            })
            persistence.add_pending_operation('failed_csv_write', datetime.now(BEIJING_TZ), csv_data)
            
        return False

# --- API 上传函数 (增强版，支持状态记录) ---
def upload_to_api(timestamp_to_log, value_to_log, api_url_to_use, persistence=None):
    if not api_url_to_use:
        logger.error("API upload URL is not configured. Cannot upload data.")
        return False
    
    # 记录上传尝试
    upload_data = {
        'timestamp': timestamp_to_log,
        'value': value_to_log,
        'api_url': api_url_to_use,
        'attempt_time': datetime.now(BEIJING_TZ).isoformat()
    }
    
    try:
        # 处理时间戳参数
        if isinstance(timestamp_to_log, str):
            # 如果传入的是字符串，直接使用
            iso_timestamp = timestamp_to_log
            logger.info(f"UPLOAD API DEBUG: 接收到时间字符串: {iso_timestamp}")
        else:
            # 如果传入的是datetime对象，转换为ISO格式
            logger.info(f"UPLOAD API DEBUG: 接收到时间戳对象: {timestamp_to_log}")
            logger.info(f"UPLOAD API DEBUG: 时区信息: {timestamp_to_log.tzinfo}")
            
            if timestamp_to_log.tzinfo is None:
                logger.error(f"UPLOAD API: 接收到naive时间戳 {timestamp_to_log}. 无法安全创建带时区的ISO格式用于API.")
                if persistence:
                    # 记录失败的上传尝试
                    upload_data['error'] = "Invalid timestamp format"
                    persistence.add_pending_operation('failed_upload', datetime.now(BEIJING_TZ), upload_data)
                return False
            
            iso_timestamp = timestamp_to_log.isoformat()
            logger.info(f"UPLOAD API DEBUG: 生成的ISO时间戳: {iso_timestamp}")

        payload = {"Timestamp": iso_timestamp, "wp_true": float(value_to_log)}
        logger.info(f"准备上传数据到 API {api_url_to_use}: {payload}")
        
        response = requests.post(api_url_to_use, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"数据成功上传到 API: {response.status_code} - {response.text[:200]}")
        
        # 记录成功上传
        if persistence:
            success_data = upload_data.copy()
            success_data.update({
                'success': True,
                'response_status': response.status_code,
                'completed_time': datetime.now(BEIJING_TZ).isoformat()
            })
            # 不需要记录成功的操作到pending_operations中
            
        return True
        
    except requests.exceptions.HTTPError as http_err:
        response_text = "N/A"
        if http_err.response is not None:
            try: response_text = http_err.response.text
            except Exception: pass
        error_msg = f"API HTTP错误: {http_err} - 响应: {response_text[:500]}"
        logger.error(error_msg)
        
        # 记录失败的上传
        if persistence:
            upload_data.update({
                'success': False,
                'error': error_msg,
                'error_type': 'HTTPError'
            })
            persistence.add_pending_operation('failed_upload', datetime.now(BEIJING_TZ), upload_data)
            
    except requests.exceptions.RequestException as req_err: 
        error_msg = f"API 请求错误: {req_err}"
        logger.error(error_msg)
        
        # 记录失败的上传
        if persistence:
            upload_data.update({
                'success': False,
                'error': error_msg,
                'error_type': 'RequestException'
            })
            persistence.add_pending_operation('failed_upload', datetime.now(BEIJING_TZ), upload_data)
            
    except Exception as e: 
        error_msg = f"上传数据到 API 时发生未知错误: {e}"
        logger.error(error_msg, exc_info=True)
        
        # 记录失败的上传
        if persistence:
            upload_data.update({
                'success': False,
                'error': error_msg,
                'error_type': 'UnknownError'
            })
            persistence.add_pending_operation('failed_upload', datetime.now(BEIJING_TZ), upload_data)
            
    return False

# --- 检查并执行刻钟上传 (总召后) ---
def check_and_perform_quarter_upload(persistence=None):
    global last_upload_quarter_minute, latest_point_data, TARGET_IOA_FOR_UPLOAD, API_UPLOAD_URL, logger
    
    logger.info(f"GI UPLOAD CHECK: Entered function. Last GI Upload Quarter: {last_upload_quarter_minute}, Target IOA: {TARGET_IOA_FOR_UPLOAD}, API URL configured: {API_UPLOAD_URL is not None}")

    if TARGET_IOA_FOR_UPLOAD is None or API_UPLOAD_URL is None:
        logger.warning("GI UPLOAD CHECK: Target IOA or API URL not configured. Skipping.")
        return

    current_beijing_time = now_beijing() # 获取当前北京时间
    current_minute_beijing = current_beijing_time.minute
    current_target_quarter_minute_beijing = (current_minute_beijing // 15) * 15

    logger.info(f"GI UPLOAD CHECK: Current Beijing Time: {current_beijing_time.strftime('%Y-%m-%d %H:%M:%S')}, Minute: {current_minute_beijing}, Calculated Target Quarter Minute (Beijing): {current_target_quarter_minute_beijing}")

    data_to_upload = latest_point_data.get(TARGET_IOA_FOR_UPLOAD)

    if not data_to_upload:
        logger.warning(f"GI UPLOAD CHECK: No data found in latest_point_data for IOA {TARGET_IOA_FOR_UPLOAD}. Cannot upload.")
        return

    logger.info(f"GI UPLOAD CHECK: Data for IOA {TARGET_IOA_FOR_UPLOAD}: Value={data_to_upload['value']}, QualityGood={data_to_upload['quality_good']}, StoredDataTS_UTC={data_to_upload['timestamp'].isoformat()}")

    if data_to_upload["quality_good"]:
        logger.info(f"GI UPLOAD CHECK: Quality is GOOD. Comparing Target Quarter Minute ({current_target_quarter_minute_beijing}) with Last GI Upload Quarter Minute ({last_upload_quarter_minute}).")
        
        if current_target_quarter_minute_beijing != last_upload_quarter_minute:
            logger.info(f"GI UPLOAD CHECK: Condition MET (New Quarter for GI upload). Proceeding with upload.")
            
            beijing_timestamp_for_api = current_beijing_time.replace(
                minute=current_target_quarter_minute_beijing,
                second=0,
                microsecond=0
            )
            beijing_time_string = beijing_timestamp_for_api.strftime("%Y-%m-%dT%H:%M:%S")
            
            logger.info(f"GI QUARTER UPLOAD DEBUG: 当前北京时间: {current_beijing_time}")
            logger.info(f"GI QUARTER UPLOAD DEBUG: 北京时间刻钟起始点: {beijing_timestamp_for_api}")
            logger.info(f"GI QUARTER UPLOAD DEBUG: 将发送的时间字符串(无时区): {beijing_time_string}")

            value_for_upload = data_to_upload["value"]
            
            logger.info(f"GI QUARTER UPLOAD: 发送北京时间字符串到API. IOA: {TARGET_IOA_FOR_UPLOAD}, Value: {value_for_upload!r}")
            logger.info(f"GI QUARTER UPLOAD: 时间字符串: {beijing_time_string} (北京时间刻钟起始点)")
            
            upload_success = upload_to_api(beijing_time_string, value_for_upload, API_UPLOAD_URL, persistence)
            
            if upload_success:
                last_upload_quarter_minute = current_target_quarter_minute_beijing
                logger.info(f"GI QUARTER UPLOAD: Successfully uploaded. Updated last_upload_quarter_minute to {last_upload_quarter_minute}.")
                
                # 在API上传成功后，将数据写入CSV文件
                write_to_csv(beijing_timestamp_for_api, value_for_upload, logger, persistence)
            else:
                logger.warning(f"GI QUARTER UPLOAD: Upload failed. last_upload_quarter_minute ({last_upload_quarter_minute}) not updated.")
        else:
            logger.info(f"GI UPLOAD CHECK: Condition NOT MET. Target Quarter Minute ({current_target_quarter_minute_beijing}) IS THE SAME as Last GI Upload Quarter Minute ({last_upload_quarter_minute}). No GI upload triggered.")
    else:
        logger.warning(f"GI UPLOAD CHECK: Data for IOA {TARGET_IOA_FOR_UPLOAD} has non-GOOD quality. Skipping GI upload.")

# --- 新增：检查并执行预估刻钟近似值上传 ---
def check_and_perform_pre_quarter_approximation_upload(persistence=None):
    global last_pre_quarter_approximation_minute_processed, latest_point_data, TARGET_IOA_FOR_UPLOAD, API_UPLOAD_URL, logger

    if TARGET_IOA_FOR_UPLOAD is None or API_UPLOAD_URL is None:
        # logger.debug("ApproxUpload: Config missing for pre-quarter upload.") # Keep logs lean for frequent checks
        return

    current_beijing_time = now_beijing()
    current_minute = current_beijing_time.minute
    target_minutes_for_approximation = [14, 29, 44, 59]

    if current_minute in target_minutes_for_approximation:
        if current_minute == last_pre_quarter_approximation_minute_processed:
            # logger.debug(f"ApproxUpload: Already processed approximation for minute {current_minute}.")
            return 

        logger.info(f"APPROX UPLOAD: Detected target minute {current_minute} for approximation upload.")

        data_to_upload = latest_point_data.get(TARGET_IOA_FOR_UPLOAD)
        if not data_to_upload:
            logger.warning(f"APPROX UPLOAD: No data for IOA {TARGET_IOA_FOR_UPLOAD} for approximation at minute {current_minute}.")
            # Mark as processed for this minute to avoid re-spamming logs if data remains unavailable during this minute
            last_pre_quarter_approximation_minute_processed = current_minute 
            return

        if data_to_upload["quality_good"]:
            target_api_timestamp_beijing = None
            if current_minute == 14:
                target_api_timestamp_beijing = current_beijing_time.replace(minute=15, second=0, microsecond=0)
            elif current_minute == 29:
                target_api_timestamp_beijing = current_beijing_time.replace(minute=30, second=0, microsecond=0)
            elif current_minute == 44:
                target_api_timestamp_beijing = current_beijing_time.replace(minute=45, second=0, microsecond=0)
            elif current_minute == 59: # Handles hour rollover correctly
                target_api_timestamp_beijing = (current_beijing_time + timedelta(minutes=1)).replace(second=0, microsecond=0)


            if target_api_timestamp_beijing:
                api_timestamp_str = target_api_timestamp_beijing.strftime("%Y-%m-%dT%H:%M:%S") # Beijing time string
                value_for_upload = data_to_upload["value"]
                
                logger.info(f"APPROX UPLOAD: Attempting upload for IOA {TARGET_IOA_FOR_UPLOAD}, Value: {value_for_upload!r}, Calculated API Timestamp (Beijing): {api_timestamp_str}")
                
                upload_success = upload_to_api(api_timestamp_str, value_for_upload, API_UPLOAD_URL, persistence)
                if upload_success:
                    last_pre_quarter_approximation_minute_processed = current_minute
                    logger.info(f"APPROX UPLOAD: Successfully uploaded approximation for minute {current_minute}. Set last_processed_approx_minute to {current_minute}.")
                else:
                    logger.warning(f"APPROX UPLOAD: Upload failed for approximation at minute {current_minute}. Will retry if conditions meet again (i.e. if this minute passes and re-enters).")
            else: # Should not happen if logic is correct
                logger.error(f"APPROX UPLOAD: Could not determine target API timestamp for current minute {current_minute}")
        else:
            logger.warning(f"APPROX UPLOAD: Data for IOA {TARGET_IOA_FOR_UPLOAD} has non-GOOD quality. Skipping approximation upload for minute {current_minute}.")
            # Mark as processed for this minute to avoid re-spamming logs if quality remains bad during this minute
            last_pre_quarter_approximation_minute_processed = current_minute
    else:
        # If current minute is not a target minute, reset the flag
        if last_pre_quarter_approximation_minute_processed != -1:
             # logger.debug(f"ApproxUpload: Current minute {current_minute} is not an approximation target. Resetting last_pre_quarter_approximation_minute_processed from {last_pre_quarter_approximation_minute_processed}.")
             last_pre_quarter_approximation_minute_processed = -1

# --- Point on_receive Callback ---
def point_on_receive_handler(point: c104.Point, previous_info: c104.Information, message: c104.IncomingMessage) -> c104.ResponseState:
    global latest_point_data, TARGET_IOA_FOR_UPLOAD, logger # TARGET_IOA_FOR_UPLOAD 用于过滤
    station_ca = point.station.common_address
    ioa = point.io_address
    value = point.value
    quality_obj = point.quality
    server_timestamp = point.recorded_at
    client_received_timestamp = now_utc()  # 使用UTC时间记录接收时间

    # 转换时间戳为北京时间用于显示
    server_timestamp_beijing = to_beijing_time(server_timestamp)
    client_received_timestamp_beijing = to_beijing_time(client_received_timestamp)

    quality_description = "N/A"
    if quality_obj:
        if quality_obj.is_good(): quality_description = "GOOD"
        else:
            q_details = []
            if quality_obj.is_any(c104.Quality.INVALID): q_details.append("INVALID")
            if quality_obj.is_any(c104.Quality.BLOCKED): q_details.append("BLOCKED")
            if quality_obj.is_any(c104.Quality.NON_TOPICAL): q_details.append("NON_TOPICAL")
            if quality_obj.is_any(c104.Quality.OVERFLOW): q_details.append("OVERFLOW")
            if quality_obj.is_any(c104.Quality.SUBSTITUTED): q_details.append("SUBSTITUTED")
            if q_details: quality_description = ", ".join(q_details)
            else: quality_description = str(quality_obj)
    
    # prev_value_str logic (可以简化或移除如果不总是需要)
    # ...

    logger.info(f"POINT CB: Update for Point - Station CA: {station_ca}, IOA: {ioa}, Type: {point.type.name}")
    logger.info(f"POINT CB:   New Value: {value!r}, Quality: {quality_description}, ServerTS(Beijing): {server_timestamp_beijing.isoformat() if server_timestamp_beijing else 'None'}, ClientRcvTS(Beijing): {client_received_timestamp_beijing.isoformat()}")

    if TARGET_IOA_FOR_UPLOAD is not None and ioa == TARGET_IOA_FOR_UPLOAD:
        is_quality_good = quality_obj.is_good() if quality_obj else False
        timestamp_to_store = server_timestamp if server_timestamp else client_received_timestamp
        latest_point_data[ioa] = {
            "value": value, "timestamp": timestamp_to_store, "quality_good": is_quality_good
        }
        logger.info(f"Stored latest data for upload target IOA {ioa}: Value={value!r}, StoredTS(Beijing)={to_beijing_time(timestamp_to_store).isoformat()}")
        # 注意：上传决策现在移到了总召唤之后
    
    return c104.ResponseState.SUCCESS

# --- 异步执行总召唤的函数 ---
def perform_interrogation_async(connection: c104.Connection, station_ca: int, is_initial: bool = False):
    global logger # 确保 logger 在此函数中可用
    log_prefix = "INITIAL ASYNC TASK" if is_initial else "PERIODIC ASYNC TASK"
    try:
        # ... (创建和检查事件的逻辑不变) ...
        if station_ca not in station_initial_interrogation_done:
            station_initial_interrogation_done[station_ca] = threading.Event()
        if is_initial and station_initial_interrogation_done[station_ca].is_set():
            logger.info(f"{log_prefix}: Initial interrogation for CA {station_ca} already marked/being processed. Skipping.")
            return

        logger.info(f"{log_prefix}: Performing General Interrogation for station CA: {station_ca} on connection {connection.ip}:{connection.port}")
        success = connection.interrogation(common_address=station_ca, qualifier=c104.Qoi.STATION)
        
        if success:
            logger.info(f"{log_prefix}: General Interrogation command sent successfully for station CA: {station_ca}")
            if is_initial:
                station_initial_interrogation_done[station_ca].set()
                logger.info(f"{log_prefix}: Event set for CA {station_ca} after successful initial interrogation.")
            
            # --- 总召唤成功后，检查是否需要进行刻钟上传 ---
            logger.info(f"{log_prefix}: GI successful for CA {station_ca}. Checking for quarter upload.")
            check_and_perform_quarter_upload(global_persistence) # <--- 在这里调用
            # --- 结束检查 ---
        else:
            logger.warning(f"{log_prefix}: General Interrogation command failed for station CA: {station_ca}")
    # ... (异常处理逻辑不变) ...
    except RuntimeError as re:
        if "already running" in str(re): logger.warning(f"{log_prefix}: Failed to send GI for CA {station_ca}, command already running.")
        else: logger.error(f"{log_prefix}: Runtime error sending GI for CA {station_ca}: {re}", exc_info=True)
    except Exception as e: logger.error(f"{log_prefix}: Error sending GI for CA {station_ca}: {e}", exc_info=True)


# --- Client Callbacks (保持不变, 确保它们使用 logger) ---
def client_on_new_point_handler(client: c104.Client, station: c104.Station, io_address: int, point_type: c104.Type) -> None:
    # ... (使用 logger) ...
    logger.info(f"CLIENT CB: New unknown point reported by Station CA {station.common_address} ...")
    try:
        new_point = station.add_point(io_address=io_address, type=point_type)
        if new_point:
            logger.info(f"CLIENT CB: Successfully added new point IOA {io_address} ...")
            try:
                new_point.on_receive(point_on_receive_handler)
                logger.info(f"CLIENT CB: Assigned on_receive handler for new point IOA {io_address}")
            except Exception as e: logger.error(f"CLIENT CB: Error assigning on_receive for point IOA {io_address}: {e}", exc_info=True)
        # ...
    except Exception as e: logger.error(f"CLIENT CB: Error in client_on_new_point_handler for IOA {io_address}: {e}", exc_info=True)


def client_on_station_initialized_handler(client: c104.Client, station: c104.Station, cause: c104.Coi) -> None:
    # ... (使用 logger) ...
    station_ca = int(station.common_address) # 确保是整数
    logger.info(f"CLIENT CB: Station CA {station_ca} INITIALIZED ... Cause: {cause.name} ...")
    if station_ca not in station_initial_interrogation_done:
        station_initial_interrogation_done[station_ca] = threading.Event()
    if not station_initial_interrogation_done[station_ca].is_set():
        if station.connection.is_connected:
            logger.info(f"CLIENT CB: Scheduling initial GI for station CA: {station_ca} from on_station_initialized.")
            threading.Thread(target=perform_interrogation_async, args=(station.connection, station_ca, True),
                             name=f"InitialInterrogationThread-CB-CA{station_ca}", daemon=True).start()
    # ...


def client_on_new_station_handler(client: c104.Client, connection: c104.Connection, common_address: int) -> None:
    # ... (使用 logger) ...
    common_address = int(common_address) # 确保是整数
    logger.info(f"CLIENT CB: New unknown station CA {common_address} reported ...")
    try:
        new_station = connection.add_station(common_address=common_address)
        if new_station:
            logger.info(f"CLIENT CB: Successfully added new station CA {common_address} ...")
            if common_address not in station_initial_interrogation_done:
                station_initial_interrogation_done[common_address] = threading.Event()
            if PRE_DEFINE_POINTS:
                for ioa, point_type in PRE_DEFINE_POINTS.items():
                    point = new_station.get_point(io_address=ioa)
                    if not point: point = new_station.add_point(io_address=ioa, type=point_type)
                    if point:
                        try: point.on_receive(point_on_receive_handler)
                        except Exception as e: logger.error(f"CLIENT CB: Error assigning on_receive for pre-defined point IOA {ioa} on new station {common_address}: {e}")
        # ...
    except Exception as e: logger.error(f"CLIENT CB: Error adding new station CA {common_address}: {e}", exc_info=True)


# --- Connection Callback (保持不变, 确保使用 logger) ---
def connection_on_state_change_handler(connection: c104.Connection, state: c104.ConnectionState) -> None:
    # ... (使用 logger) ...
    conn_id = f"{connection.ip}:{connection.port}"
    logger.info(f"CONNECTION CB: Connection to {conn_id} new state is {state.name}")
    if state == c104.ConnectionState.OPEN_MUTED:
        # ...
        if not connection_unmuted_flags.get(conn_id, False):
            try:
                connection.unmute()
                connection_unmuted_flags[conn_id] = True
                logger.info(f"CONNECTION CB: Called unmute() on connection {conn_id}.")
            except Exception as e: logger.error(f"CONNECTION CB: Error calling unmute() on {conn_id}: {e}", exc_info=True)
        # ...
    elif state == c104.ConnectionState.OPEN:
        # ...
        unmuted_successfully = connection_unmuted_flags.get(conn_id, False)
        if unmuted_successfully and not connection.is_muted:
            logger.info(f"CONNECTION CB: Connection {conn_id} is OPEN and unmuted. Scheduling initial GI for its stations.")
            for station_obj in connection.stations:
                station_ca = int(station_obj.common_address)
                if station_ca not in station_initial_interrogation_done:
                    station_initial_interrogation_done[station_ca] = threading.Event()
                if not station_initial_interrogation_done[station_ca].is_set():
                    logger.info(f"CONNECTION CB: Scheduling initial GI for station CA: {station_ca} as OPEN & unmuted.")
                    threading.Thread(target=perform_interrogation_async,args=(connection, station_ca, True),
                                     name=f"InitialInterrogationThread-Open-CA{station_ca}",daemon=True).start()
        # ...
    elif state == c104.ConnectionState.CLOSED:
        # ...
        connection_unmuted_flags.pop(conn_id, None)
        for station in connection.stations: # station is a c104.Station object
            station_ca_key = int(station.common_address)
            if station_ca_key in station_initial_interrogation_done and station_initial_interrogation_done[station_ca_key].is_set():
                station_initial_interrogation_done[station_ca_key].clear()
                logger.info(f"CONNECTION CB: Cleared initial interrogation flag for Station CA {station_ca_key} due to connection {conn_id} closure.")
        # ...


# --- Periodic Interrogation Task (保持不变, 确保使用 logger) ---
def periodic_interrogation_task(client: c104.Client):
    interrogation_interval_sec_int = int(INTERROGATION_INTERVAL_SECONDS)
    while not stop_event.is_set():
        if not client.is_running or not client.has_active_connections:
            logger.warning("PERIODIC GI TASK: Client not running or no active connections. Skipping interrogation cycle.")
            stop_event.wait(interrogation_interval_sec_int) # Wait before retrying connection check
            continue
        
        active_connection_found = False
        for connection_obj in client.connections:
            if connection_obj.is_connected and connection_obj.has_stations:
                active_connection_found = True
                logger.debug(f"PERIODIC GI TASK: Checking connection {connection_obj.ip}:{connection_obj.port} for stations to interrogate.")
                for station in connection_obj.stations:
                    station_ca = int(station.common_address)
                    # Check if initial interrogation for this station on this connection is done
                    if station_initial_interrogation_done.get(station_ca) and station_initial_interrogation_done[station_ca].is_set():
                        # Perform periodic interrogation only if initial is done
                        logger.info(f"PERIODIC GI TASK: Performing periodic GI for station CA: {station_ca} on connection {connection_obj.ip}:{connection_obj.port}")
                        try:
                            success = connection_obj.interrogation(common_address=station_ca, qualifier=c104.Qoi.STATION)
                            if success: 
                                logger.info(f"PERIODIC GI TASK: Periodic GI command sent successfully for CA: {station_ca}.")
                                # --- 周期总召成功后，也检查是否需要进行刻钟上传 ---
                                logger.info(f"PERIODIC GI TASK: GI successful for CA {station_ca}. Checking for quarter upload (post-GI).")
                                check_and_perform_quarter_upload(global_persistence) 
                            else: 
                                logger.warning(f"PERIODIC GI TASK: Periodic GI command failed for CA: {station_ca}.")
                        except RuntimeError as re_gi:
                            if "already running" in str(re_gi):
                                logger.warning(f"PERIODIC GI TASK: Failed to send periodic GI for CA {station_ca}, command already running.")
                            else:
                                logger.error(f"PERIODIC GI TASK: Runtime error sending periodic GI for CA {station_ca}: {re_gi}", exc_info=True)
                        except Exception as e_gi:
                            logger.error(f"PERIODIC GI TASK: Error sending periodic GI for CA {station_ca}: {e_gi}", exc_info=True)
                    else:
                        logger.debug(f"PERIODIC GI TASK: Initial interrogation for station CA {station_ca} on connection {connection_obj.ip}:{connection_obj.port} not yet marked complete. Skipping periodic GI.")
            else:
                logger.debug(f"PERIODIC GI TASK: Connection {connection_obj.ip}:{connection_obj.port} not connected or no stations. Skipping.")
        
        if not active_connection_found:
            logger.warning("PERIODIC GI TASK: No active connections with stations found for interrogation.")

        stop_event.wait(interrogation_interval_sec_int)
    logger.info("Periodic GI interrogation task stopped.")


# --- 新增：预估值定时上传任务 ---
def approximation_upload_scheduler_task():
    global logger, stop_event
    logger.info("Approximation upload scheduler task started. Will check every ~20 seconds.")
    while not stop_event.is_set():
        try:
            if client.is_running and client.has_active_connections: # Only run if client is active
                 check_and_perform_pre_quarter_approximation_upload(global_persistence)
            else:
                 logger.debug("ApproximationUploadTask: Client not running or no active connections. Skipping approximation check.")
        except Exception as e:
            logger.error(f"Error in approximation_upload_scheduler_task loop: {e}", exc_info=True)
        
        # Sleep for a short duration.
        # This ensures it checks multiple times within a minute if needed, but not too aggressively.
        stop_event.wait(20) # Check roughly 3 times a minute.
    logger.info("Approximation upload scheduler task stopped.")


# --- 导入数据持久化模块 ---
try:
    from data_persistence import DataPersistence, DataCache
    logger.info("Successfully imported data persistence module")
except ImportError as e:
    logger.error(f"Failed to import data persistence module: {e}")
    logger.error("Running without data persistence features")
    DataPersistence = None
    DataCache = None

# --- 客户端初始化函数 ---
def initialize_and_start_client(persistence=None):
    """初始化并启动客户端，返回(client, connection, periodic_thread, approximation_thread)"""
    global logger, client, connection_unmuted_flags, station_initial_interrogation_done
    global last_upload_quarter_minute, last_pre_quarter_approximation_minute_processed
    
    logger.info("Initializing and starting client...")
    
    # 重置状态变量
    station_initial_interrogation_done = {}
    connection_unmuted_flags = {}
    last_upload_quarter_minute = -1
    last_pre_quarter_approximation_minute_processed = -1
    
    # 如果有持久化模块，恢复状态
    if persistence:
        try:
            state = persistence.load_state()
            last_upload_quarter_minute = state.get('last_upload_quarter_minute', -1)
            last_pre_quarter_approximation_minute_processed = state.get('last_pre_quarter_approximation_minute_processed', -1)
            logger.info(f"RESTORE: Restored state - last_upload_quarter: {last_upload_quarter_minute}, last_pre_quarter: {last_pre_quarter_approximation_minute_processed}")
        except Exception as e:
            logger.error(f"Failed to restore state: {e}", exc_info=True)
    
    originator_addr_int = int(ORIGINATOR_ADDRESS) 
    common_addr_int = int(COMMON_ADDRESS)
    server_port_int = int(SCADA_SERVER_PORT)

    client = c104.Client()
    if originator_addr_int != 0: 
        client.originator_address = originator_addr_int

    client.on_new_point(client_on_new_point_handler)
    client.on_station_initialized(client_on_station_initialized_handler)
    client.on_new_station(client_on_new_station_handler)
    logger.info("Client event handlers assigned.")

    connection = client.add_connection(ip=SCADA_SERVER_IP, port=server_port_int, init=c104.Init.MUTED)
    if not connection:
        logger.error(f"Failed to add connection to {SCADA_SERVER_IP}:{server_port_int}")
        return None, None, None, None

    conn_id = f"{connection.ip}:{connection.port}"
    connection_unmuted_flags[conn_id] = False
    logger.info(f"Added connection to {conn_id} with init=MUTED")
    
    try:
        connection.on_state_change(connection_on_state_change_handler)
        logger.info(f"Assigned on_state_change handler for connection {conn_id}")
    except Exception as e: 
        logger.error(f"Failed to assign on_state_change handler: {e}", exc_info=True)

    station_obj = connection.get_station(common_address=common_addr_int)
    if not station_obj:
        station_obj = connection.add_station(common_address=common_addr_int)
        if station_obj: 
            logger.info(f"Manually added/ensured station CA: {common_addr_int}")
        else: 
            logger.warning(f"Failed to manually add/ensure station CA {common_addr_int}")
    else: 
        logger.info(f"Station CA {common_addr_int} already exists")

    if station_obj:
        if common_addr_int not in station_initial_interrogation_done:
             station_initial_interrogation_done[common_addr_int] = threading.Event()
             logger.info(f"INIT: Created interrogation event for primary Station CA {common_addr_int}")
        if PRE_DEFINE_POINTS:
            for ioa, point_type in PRE_DEFINE_POINTS.items(): 
                point = station_obj.get_point(io_address=ioa)
                if not point: 
                    point = station_obj.add_point(io_address=ioa, type=point_type)
                if point:
                    logger.info(f"INIT: Ensuring point IOA {ioa} (Type: {point_type.name}) for station CA {common_addr_int}")
                    try:
                        point.on_receive(point_on_receive_handler)
                        logger.info(f"INIT: Assigned on_receive handler for point IOA {ioa} on CA {common_addr_int}")
                    except Exception as e: 
                        logger.error(f"INIT: Error assigning on_receive for point IOA {ioa}: {e}", exc_info=True)
                else: 
                    logger.warning(f"INIT: Point IOA {ioa} could not be added/found on CA {common_addr_int}")

    # 启动客户端
    try:
        client.start()
        logger.info("Client started successfully")
        
        # 启动周期性总召任务
        periodic_task_thread = threading.Thread(
            target=periodic_interrogation_task, 
            args=(client,), 
            name="PeriodicInterrogationTask", 
            daemon=True
        )
        periodic_task_thread.start()
        logger.info(f"Periodic interrogation task started. Interval: {INTERROGATION_INTERVAL_SECONDS} seconds.")
        
        # 启动预估值上传任务
        approximation_uploader_thread = None
        if TARGET_IOA_FOR_UPLOAD is not None and API_UPLOAD_URL is not None:
            approximation_uploader_thread = threading.Thread(
                target=approximation_upload_scheduler_task, 
                name="ApproximationUploadTask", 
                daemon=True
            )
            approximation_uploader_thread.start()
            logger.info("Approximation value upload scheduler task started.")
        else:
            logger.info("Approximation value upload task not started (TARGET_IOA_FOR_UPLOAD or API_UPLOAD_URL not configured).")
        
        return client, connection, periodic_task_thread, approximation_uploader_thread
        
    except Exception as e:
        logger.error(f"Failed to start client: {e}", exc_info=True)
        return None, None, None, None

# --- Main Function (监管者模式) ---
def main():
    """监管者主循环，提供自动重启和数据连续性保障"""
    global logger, client, stop_event, global_persistence
    logger.info("Starting SCADA Client Supervisor...")
    
    # 初始化数据持久化
    if DataPersistence:
        try:
            global_persistence = DataPersistence()
            logger.info("Data persistence module initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize data persistence: {e}", exc_info=True)
            global_persistence = None
    
    client_restart_count = 0
    
    while not stop_event.is_set():
        client_restart_count += 1
        logger.info(f"SUPERVISOR: Starting client instance #{client_restart_count}")
        
        # 重置状态变量
        global connection_unmuted_flags, station_initial_interrogation_done
        global last_upload_quarter_minute, last_pre_quarter_approximation_minute_processed
        
        connection_unmuted_flags = {}
        station_initial_interrogation_done = {}
        last_upload_quarter_minute = -1
        last_pre_quarter_approximation_minute_processed = -1
        
        # 处理积压数据（如果有持久化模块）
        if global_persistence:
            try:
                logger.info("SUPERVISOR: Checking for pending operations...")
                restore_pending_operations(global_persistence)
            except Exception as e:
                logger.error(f"SUPERVISOR: Error restoring pending operations: {e}", exc_info=True)
        
        # 初始化并启动客户端
        client, connection, periodic_thread, approximation_thread = initialize_and_start_client(global_persistence)
        
        if not client or not connection:
            logger.error("SUPERVISOR: Failed to initialize client. Retrying in 60 seconds...")
            stop_event.wait(60)
            continue
        
        logger.info("SUPERVISOR: Client initialized successfully. Starting health monitoring...")
        
        # 健康检查循环
        last_health_check = time.time()
        health_check_count = 0
        
        while client.is_running and not stop_event.is_set():
            current_time = time.time()
            
            # 每30秒进行一次健康检查
            if current_time - last_health_check >= 30:
                health_check_count += 1
                last_health_check = current_time
                
                logger.debug(f"SUPERVISOR: Health check #{health_check_count}")
                
                # 检查连接状态
                if not client.has_active_connections:
                    logger.warning("SUPERVISOR: No active connections detected. Waiting 30 seconds for confirmation...")
                    
                    # 等待30秒确认
                    stop_event.wait(30)
                    
                    if not stop_event.is_set() and not client.has_active_connections:
                        logger.error("SUPERVISOR: Confirmed no active connections. Triggering client restart...")
                        break  # 跳出健康检查循环，重启客户端
                
                # 保存当前状态（如果有持久化模块）
                if global_persistence:
                    try:
                        current_state = {
                            'client_running': client.is_running,
                            'program_last_running_time': datetime.now(BEIJING_TZ).isoformat(),
                            'last_upload_quarter_minute': last_upload_quarter_minute,
                            'last_pre_quarter_approximation_minute_processed': last_pre_quarter_approximation_minute_processed,
                            'health_check_count': health_check_count,
                            'client_restart_count': client_restart_count
                        }
                        global_persistence.save_state(current_state)
                    except Exception as e:
                        logger.error(f"SUPERVISOR: Error saving state: {e}", exc_info=True)
            
            # 短暂休眠，避免过度消耗CPU
            stop_event.wait(1)
        
        # 清理当前客户端实例
        logger.info("SUPERVISOR: Stopping current client instance...")
        cleanup_client_instance(client, periodic_thread, approximation_thread)
        
        if stop_event.is_set():
            logger.info("SUPERVISOR: Stop event detected, exiting supervisor loop")
            break
        
        # 等待一段时间再重新开始，避免快速的重启循环
        logger.info("SUPERVISOR: Waiting 15 seconds before restarting client...")
        stop_event.wait(15)
    
    logger.info("SUPERVISOR: Supervisor loop ended")

def restore_pending_operations(persistence):
    """恢复待处理的操作"""
    try:
        state = persistence.load_state()
        
        # 检查程序最后运行时间
        last_time = state.get('program_last_running_time')
        if last_time:
            # 计算遗漏的时间窗口
            missing_windows = persistence.get_missing_time_windows(last_time)
            
            if missing_windows:
                logger.info(f"RESTORE: Found {len(missing_windows)} missing time windows")
                
                # 处理遗漏的操作（示例实现）
                for window_time, operation_type in missing_windows[:5]:  # 最多处理5个遗漏窗口
                    logger.info(f"RESTORE: Would restore {operation_type} for {window_time}")
                    # 这里可以添加具体的数据恢复逻辑
                    # 例如：从缓存中获取数据并重新尝试上传
        
        # 处理待处理的上传操作
        pending_uploads = state.get('pending_database_uploads', [])
        pending_csv = state.get('pending_csv_writes', [])
        
        if pending_uploads:
            logger.info(f"RESTORE: Found {len(pending_uploads)} pending database uploads")
            # 这里可以添加重新上传的逻辑
        
        if pending_csv:
            logger.info(f"RESTORE: Found {len(pending_csv)} pending CSV writes")
            # 这里可以添加重新写入CSV的逻辑
        
    except Exception as e:
        logger.error(f"Error restoring pending operations: {e}", exc_info=True)

def cleanup_client_instance(client, periodic_thread, approximation_thread):
    """清理客户端实例"""
    try:
        logger.info("CLEANUP: Initiating client cleanup...")
        stop_event.set()  # 通知所有任务停止
        
        # 等待线程结束
        if periodic_thread and periodic_thread.is_alive():
            logger.info("CLEANUP: Waiting for periodic task to stop...")
            periodic_thread.join(timeout=10)
            if periodic_thread.is_alive():
                logger.warning("CLEANUP: Periodic task did not stop in time")
        
        if approximation_thread and approximation_thread.is_alive():
            logger.info("CLEANUP: Waiting for approximation task to stop...")
            approximation_thread.join(timeout=10)
            if approximation_thread.is_alive():
                logger.warning("CLEANUP: Approximation task did not stop in time")
        
        # 停止客户端
        if client and client.is_running:
            logger.info("CLEANUP: Stopping client...")
            client.stop()
            logger.info("CLEANUP: Client stopped")
        
        # 重置stop_event为下次使用
        stop_event.clear()
        logger.info("CLEANUP: Client cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during client cleanup: {e}", exc_info=True)

if __name__ == "__main__":
    main()
# Add client as a global variable so approximation_upload_scheduler_task can access it.
client = None