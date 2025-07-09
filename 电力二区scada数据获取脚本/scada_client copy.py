#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import sys
import logging
import configparser
import os
import requests 
from datetime import datetime, timedelta, timezone

# 尝试导入日志配置模块，如果失败，则提供基础的日志功能
try:
    from logging_config import configure_scada_logging 
except ImportError:
    print("WARNING: logging_config.py not found. Using basic logging configuration.", file=sys.stderr)
    def configure_scada_logging(logger_name, log_file_path, log_level, script_dir, backup_count, console_output):
        # 提供一个基础的备用日志配置
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        if script_dir and not os.path.isabs(log_file_path):
            log_file_path = os.path.join(script_dir, log_file_path)
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        handlers_list = []
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # 文件处理器
        try:
            from logging.handlers import TimedRotatingFileHandler
            file_handler = TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=backup_count, encoding='utf-8')
            file_handler.setFormatter(formatter)
            handlers_list.append(file_handler)
        except Exception as e_fh:
            print(f"Error setting up TimedRotatingFileHandler: {e_fh}. Using basic FileHandler.", file=sys.stderr)
            try:
                basic_file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
                basic_file_handler.setFormatter(formatter)
                handlers_list.append(basic_file_handler)
            except Exception as e_bfh:
                 print(f"Error setting up basic FileHandler: {e_bfh}.", file=sys.stderr)


        # 控制台处理器
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            handlers_list.append(console_handler)
            
        logging.basicConfig(level=numeric_level, handlers=handlers_list)
        logger_instance = logging.getLogger(logger_name)
        logger_instance.info("Basic logging configured as fallback.")
        return logger_instance

import ctypes
import struct
try:
    from pyiec104.iec104api import * 
except ImportError as e:
    print(f"FATAL ERROR: Could not import from pyiec104.iec104api: {e}. "
          "Ensure pyiec104 is installed correctly and iec104api.py is accessible.", file=sys.stderr)
    sys.exit(1)


# --- 全局变量 ---
g_client_handle = None
g_connection_successful = False
g_received_wp_true_value = None
g_last_scada_timestamp = None
g_next_target_checkpoint = None
g_value_before_checkpoint = None
g_wp_true_ti_enum_value = None
iec104_lib = None # 全局变量存储加载的库对象

# --- 配置加载 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, 'config.ini')
config = configparser.ConfigParser()

# 早期日志记录器
early_stage_logger = logging.getLogger("EarlyStageConfig")
try:
    if not early_stage_logger.hasHandlers():
        early_console_handler = logging.StreamHandler(sys.stderr)
        early_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        early_console_handler.setFormatter(early_formatter)
        early_stage_logger.addHandler(early_console_handler)
        early_stage_logger.setLevel(logging.INFO)
except Exception: pass

if not os.path.exists(config_path):
    err_msg = f"FATAL ERROR: Configuration file '{config_path}' not found."
    print(err_msg, file=sys.stderr); early_stage_logger.critical(err_msg); sys.exit(1)
try:
    files_read = config.read(config_path, encoding='utf-8')
    if not files_read: raise configparser.Error(f"File found but could not be read/is empty: '{config_path}'.")
    if not config.sections(): raise configparser.Error(f"File is empty or not valid INI: '{config_path}'.")
except Exception as e:
    err_msg = f"FATAL ERROR loading/parsing '{config_path}': {e}"
    print(err_msg, file=sys.stderr); early_stage_logger.critical(err_msg, exc_info=True); sys.exit(1)

# --- 日志设置 ---
try:
    log_file_path_str = config.get('Logging', 'LOG_FILE', fallback='scada_client.log')
    log_level_str = config.get('Logging', 'LOG_LEVEL', fallback='INFO')
    backup_count = config.getint('Logging', 'BACKUP_COUNT', fallback=30)
    console_log_enabled = config.getboolean('Logging', 'CONSOLE_OUTPUT', fallback=True)
    logger = configure_scada_logging(
        logger_name="SCADAClient_C_API", log_file_path=log_file_path_str, log_level=log_level_str,
        script_dir=script_dir, backup_count=backup_count, console_output=console_log_enabled
    )
except Exception as e:
    err_msg = f"FATAL ERROR: Failed to configure logging: {e}"
    print(err_msg, file=sys.stderr); early_stage_logger.critical(err_msg, exc_info=True); sys.exit(1)

# --- 共享库加载函数 ---
def load_shared_library():
    global iec104_lib, logger # 确保 logger 在此函数中可用
    lib_name_win = 'iec104x64d.dll'  # <--- 已根据你提供的信息修改
    lib_name_linux = 'libx86_x64-iec104.so' # !!! 示例：你需要为Linux环境替换为实际的.so文件名 !!!
    
    lib_to_load_path = None
    platform_system = sys.platform # 缓存 sys.platform 的结果

    if platform_system.startswith('win'):
        lib_path_local = os.path.join(script_dir, lib_name_win)
        if os.path.exists(lib_path_local):
            lib_to_load_path = lib_path_local
        else: 
            lib_to_load_path = lib_name_win # 尝试从系统 PATH 加载
            logger.warning(f"Shared library '{lib_name_win}' not found in script directory. Attempting to load from system PATH.")
    elif platform_system.startswith('linux'):
        lib_path_local = os.path.join(script_dir, lib_name_linux)
        if os.path.exists(lib_path_local):
            lib_to_load_path = lib_path_local
        else: 
            lib_to_load_path = lib_name_linux # 尝试从 LD_LIBRARY_PATH 或标准库路径加载
            logger.warning(f"Shared library '{lib_name_linux}' not found in script directory. Attempting to load from LD_LIBRARY_PATH/system paths.")
    else:
        logger.critical(f"Unsupported platform: {platform_system}. Cannot load shared library. Exiting.")
        sys.exit(1)
            
    try:
        logger.info(f"Attempting to load shared library: {lib_to_load_path} for platform {platform_system}")
        if platform_system.startswith('win'):
            iec104_lib = ctypes.WinDLL(lib_to_load_path)
        else:
            iec104_lib = ctypes.CDLL(lib_to_load_path)
        logger.info(f"Successfully loaded shared library: {lib_to_load_path}")
    except OSError as e:
        logger.critical(f"CRITICAL: Failed to load shared library '{lib_to_load_path}': {e}. "
                        "Ensure it's in the script directory or system PATH (Windows) or LD_LIBRARY_PATH / standard lib paths (Linux), "
                        "and all its dependencies (like VC++ Redistributables for Windows or other .so files for Linux) are installed/accessible. Exiting.")
        sys.exit(1)
    except Exception as e: 
        logger.critical(f"CRITICAL: Unexpected error loading shared library '{lib_to_load_path}': {e}", exc_info=True)
        sys.exit(1)

# --- 在脚本的主要部分开始前加载库 ---
load_shared_library()


# --- 全局配置变量 ---
try:
    scada_ip = config['IEC104_Connection']['SCADA_SERVER_IP']
    scada_port = config.getint('IEC104_Connection', 'SCADA_SERVER_PORT')
    casdu_addr = config.getint('IEC104_Connection', 'CASDU_ADDRESS')
    timeout_t0 = config.getint('IEC104_Connection', 'TIMEOUT_T0'); timeout_t1 = config.getint('IEC104_Connection', 'TIMEOUT_T1')
    timeout_t2 = config.getint('IEC104_Connection', 'TIMEOUT_T2'); timeout_t3 = config.getint('IEC104_Connection', 'TIMEOUT_T3')
    param_k = config.getint('IEC104_Connection', 'PARAM_K'); param_w = config.getint('IEC104_Connection', 'PARAM_W')
    data_wait_timeout = config.getint('IEC104_Connection', 'DATA_WAIT_TIMEOUT')
    g_wp_true_ioa = config.getint('WP_TRUE_Config', 'IOA')
    wp_true_ti_str = config['WP_TRUE_Config']['TI_STR']
    api_url = config['API']['UPLOAD_URL']
    inner_loop_interval_seconds = config.getint('TaskConfig', 'INNER_LOOP_FETCH_INTERVAL_SECONDS')

    if 'eIEC870TypeID' not in globals() or eIEC870TypeID is None:
        logger.critical("CRITICAL: eIEC870TypeID not available from pyiec104.iec104api. Exiting.")
        sys.exit(1)
    try:
        ti_enum_member = getattr(eIEC870TypeID, wp_true_ti_str)
        if isinstance(ti_enum_member, int): g_wp_true_ti_enum_value = ti_enum_member
        elif hasattr(ti_enum_member, 'value') and isinstance(ti_enum_member.value, int): g_wp_true_ti_enum_value = ti_enum_member.value
        else: logger.critical(f"Could not get int value for TypeID '{wp_true_ti_str}'. Got: {ti_enum_member}. Exiting."); sys.exit(1)
        logger.info(f"TypeID '{wp_true_ti_str}' resolved to int value: {g_wp_true_ti_enum_value}")
    except AttributeError: logger.critical(f"TI_STR '{wp_true_ti_str}' not in eIEC870TypeID. Exiting."); sys.exit(1)
except Exception as e: logger.critical(f"CRITICAL Config error: {e}. Exiting.", exc_info=True); sys.exit(1)


# --- Python 回调函数 (将被C库调用) ---
@IEC104UpdateCallback 
def py_cbUpdate(u16ObjectId, psDAID, psData, psUpdateParams, ptErrVal):
    global g_received_wp_true_value, g_last_scada_timestamp, logger
    try:
        logger.debug(f"=== py_cbUpdate CALLED ===")
        if not (psDAID and psDAID.contents and psData and psData.contents): 
            logger.warning("Callback py_cbUpdate received NULL pointer(s)."); return 0
        ioa = psDAID.contents.u32IOA; type_id_val = psDAID.contents.eTypeID
        logger.info(f"C_Callback py_cbUpdate: ClientID={u16ObjectId}, TypeID_Val={type_id_val}, IOA={ioa}")
        
        # 记录所有接收到的数据，不仅仅是目标IOA
        quality_int = psData.contents.tQuality
        data_type = psData.contents.eDataType
        data_size = psData.contents.eDataSize
        logger.info(f"Received data: IOA={ioa}, TypeID={type_id_val}, Quality={quality_int}, DataType={data_type}, DataSize={data_size}")
        
        if ioa == g_wp_true_ioa and type_id_val == g_wp_true_ti_enum_value:
            # 检查数据有效性 - IV表示无效
            try:
                iv_flag = eIEC870QualityFlags.IV.value if hasattr(eIEC870QualityFlags.IV, 'value') else 1
            except (NameError, AttributeError):
                iv_flag = 1  # IV标志位通常是1
            is_valid = (quality_int & iv_flag) == 0
            
            if is_valid:
                # 检查数据类型 - M_ME_NC_1通常使用短浮点数或缩放值
                try:
                    float32_type = eDataTypes.FLOAT32_DATA.value if hasattr(eDataTypes.FLOAT32_DATA, 'value') else 4
                    scaled_type = eDataTypes.SCALED_DATA.value if hasattr(eDataTypes.SCALED_DATA, 'value') else 13
                except (NameError, AttributeError):
                    float32_type = 4  # 假设FLOAT32_DATA为4
                    scaled_type = 13  # 假设SCALED_DATA为13
                    
                if psData.contents.eDataType == float32_type:
                    # 4字节浮点数
                    data_bytes = bytearray(ctypes.string_at(psData.contents.pvData, 4))
                    value = struct.unpack('f', data_bytes)[0]
                    ts_s = psData.contents.sTimeStamp
                    timestamp = datetime(ts_s.u16Year, ts_s.u8Month, ts_s.u8Day, ts_s.u8Hour, ts_s.u8Minute, ts_s.u8Seconds, ts_s.u16MilliSeconds * 1000)
                    logger.info(f"Callback: Valid wp_true (IOA {ioa}) data: Value={value:.3f}, SCADA_Timestamp={timestamp.isoformat()}, Quality={quality_int}")
                    g_received_wp_true_value = value; g_last_scada_timestamp = timestamp
                elif psData.contents.eDataType == scaled_type or data_size == 4:
                    # M_ME_NC_1类型的缩放数据，通常是4字节
                    try:
                        if data_size == 4:
                            data_bytes = bytearray(ctypes.string_at(psData.contents.pvData, 4))
                            # 尝试作为浮点数解析
                            value = struct.unpack('f', data_bytes)[0]
                        elif data_size == 2:
                            data_bytes = bytearray(ctypes.string_at(psData.contents.pvData, 2))
                            # 尝试作为有符号短整数解析，然后转换为浮点数
                            scaled_value = struct.unpack('h', data_bytes)[0]
                            value = float(scaled_value)  # 可能需要应用缩放因子
                        else:
                            logger.warning(f"Unexpected data size for M_ME_NC_1: {data_size}")
                            return 0
                            
                        ts_s = psData.contents.sTimeStamp
                        timestamp = datetime(ts_s.u16Year, ts_s.u8Month, ts_s.u8Day, ts_s.u8Hour, ts_s.u8Minute, ts_s.u8Seconds, ts_s.u16MilliSeconds * 1000)
                        logger.info(f"Callback: Valid wp_true (IOA {ioa}) M_ME_NC_1 data: Value={value:.3f}, SCADA_Timestamp={timestamp.isoformat()}, Quality={quality_int}")
                        g_received_wp_true_value = value; g_last_scada_timestamp = timestamp
                    except Exception as e:
                        logger.error(f"Failed to extract M_ME_NC_1 value: {e}")
                else: 
                    logger.warning(f"Callback: IOA {ioa} received but data type is {psData.contents.eDataType}, expected FLOAT32_DATA({float32_type}) or SCALED_DATA({scaled_type}).")
                    # 尝试根据实际数据类型解析
                    if psData.contents.pvData:
                        if data_size == 4:
                            try:
                                data_bytes = bytearray(ctypes.string_at(psData.contents.pvData, 4))
                                value = struct.unpack('f', data_bytes)[0]
                                logger.info(f"Extracted 4-byte float anyway: {value}")
                                g_received_wp_true_value = value
                                g_last_scada_timestamp = datetime.now()
                            except Exception as e:
                                logger.error(f"Failed to extract 4-byte value: {e}")
            else: logger.warning(f"Callback: Invalid quality for wp_true (IOA {ioa}): QualityBits={quality_int}")
        else:
            logger.debug(f"Callback: Received data for different IOA/TypeID (IOA={ioa}, TypeID={type_id_val}), target is IOA={g_wp_true_ioa}, TypeID={g_wp_true_ti_enum_value}")
    except Exception as e: logger.error(f"Exception in py_cbUpdate callback: {e}", exc_info=True)
    return 0

@IEC104ClientStatusCallback
def py_cbClientStatus(u16ObjectId, psConnID, peStat, ptErrVal):
    global g_connection_successful, logger
    try:
        status_val = peStat.contents.value; ip_bytes = psConnID.contents.ai8IPAddress
        ip_str = ip_bytes.split(b'\x00', 1)[0].decode('ascii', errors='ignore'); port = psConnID.contents.u16PortNumber
        
        # 获取CONNECTED状态值
        try:
            connected_status = eStatus.CONNECTED.value if hasattr(eStatus.CONNECTED, 'value') else 1
        except (NameError, AttributeError):
            connected_status = 1  # CONNECTED通常为1
            
        if status_val == connected_status:
            logger.info(f"C_Callback py_cbClientStatus: ClientID {u16ObjectId} CONNECTED to {ip_str}:{port}"); g_connection_successful = True
        else: 
            logger.warning(f"C_Callback py_cbClientStatus: ClientID {u16ObjectId} DISCONNECTED from {ip_str}:{port}. Status: {status_val}"); g_connection_successful = False
    except Exception as e: logger.error(f"Exception in py_cbClientStatus callback: {e}", exc_info=True)
    return 0

@IEC104DebugMessageCallback
def py_cbDebug(u16ObjectId, psDebugData, ptErrVal):
    global logger
    try:
        debug_options = psDebugData.contents.u32DebugOptions
        debug_msg_bytes = psDebugData.contents.au8ErrorMessage
        
        # 正确处理ctypes数组到字节串的转换
        try:
            # 将ctypes数组转换为bytes
            debug_msg_raw = bytes(debug_msg_bytes)
            debug_msg = debug_msg_raw.split(b'\x00', 1)[0].decode('ascii', errors='ignore')
        except Exception as e:
            debug_msg = f"[Unable to decode debug message: {e}]"
        
        # 检查各种debug选项
        try:
            error_flag = eDebugOptionsFlag.DEBUG_OPTION_ERROR.value if hasattr(eDebugOptionsFlag.DEBUG_OPTION_ERROR, 'value') else 1
            warning_flag = eDebugOptionsFlag.DEBUG_OPTION_WARNING.value if hasattr(eDebugOptionsFlag.DEBUG_OPTION_WARNING, 'value') else 2
            rx_flag = eDebugOptionsFlag.DEBUG_OPTION_RX.value if hasattr(eDebugOptionsFlag.DEBUG_OPTION_RX, 'value') else 4
            tx_flag = eDebugOptionsFlag.DEBUG_OPTION_TX.value if hasattr(eDebugOptionsFlag.DEBUG_OPTION_TX, 'value') else 8
        except (NameError, AttributeError):
            error_flag = 1
            warning_flag = 2
            rx_flag = 4
            tx_flag = 8
            
        if (debug_options & error_flag) == error_flag:
            logger.error(f"C_Debug ERROR from ClientID {u16ObjectId}: {debug_msg}")
        elif (debug_options & warning_flag) == warning_flag:
            logger.warning(f"C_Debug WARNING from ClientID {u16ObjectId}: {debug_msg}")
        elif (debug_options & rx_flag) == rx_flag:
            logger.debug(f"C_Debug RX from ClientID {u16ObjectId}: {debug_msg}")
        elif (debug_options & tx_flag) == tx_flag:
            logger.debug(f"C_Debug TX from ClientID {u16ObjectId}: {debug_msg}")
        else:
            logger.debug(f"C_Debug from ClientID {u16ObjectId} (options={debug_options}): {debug_msg}")
    except Exception as e: logger.error(f"Exception in py_cbDebug callback: {e}", exc_info=True)
    return 0

# --- 初始化或更新下一个15分钟目标点 ---
def update_next_target_checkpoint():
    global g_next_target_checkpoint, g_value_before_checkpoint, logger
    now = datetime.now()
    current_quarter_start_minute = (now.minute // 15) * 15
    current_quarter_start_time = now.replace(minute=current_quarter_start_minute, second=0, microsecond=0)
    g_next_target_checkpoint = current_quarter_start_time + timedelta(minutes=15)
    g_value_before_checkpoint = None 
    logger.info(f"下一个15分钟目标监测点更新为: {g_next_target_checkpoint.isoformat()}")

# --- 连接SCADA函数 (C API风格) ---
def connect_scada():
    global g_connection_successful, g_client_handle, iec104_lib, logger
    if g_client_handle is not None and g_connection_successful: logger.debug("Already connected."); return True
    if g_client_handle is not None and not g_connection_successful: 
        logger.warning("Client handle exists but not connected. Attempting to restart..."); tErrVal_restart = ctypes.c_short()
        ret_restart = iec104_lib.IEC104Start(g_client_handle, ctypes.byref(tErrVal_restart))
        if ret_restart == 0: time.sleep(1); return g_connection_successful
        else: logger.error(f"Failed to restart. ErrVal: {tErrVal_restart.value}"); disconnect_scada(); return False
    
    logger.info("Creating and configuring IEC 104 client (C API style)...")
    sParams = sIEC104Parameters(); sParams.eAppFlag = eApplicationFlag.APP_CLIENT; sParams.u16ObjectId = 1
    sParams.ptUpdateCallback = py_cbUpdate; sParams.ptClientStatusCallback = py_cbClientStatus; sParams.ptDebugCallback = py_cbDebug
    # Nullify unused callbacks
    sParams.ptReadCallback = IEC104ReadCallback(0); sParams.ptWriteCallback = IEC104WriteCallback(0)
    sParams.ptSelectCallback = IEC104ControlSelectCallback(0); sParams.ptOperateCallback = IEC104ControlOperateCallback(0)
    sParams.ptCancelCallback = IEC104ControlCancelCallback(0); sParams.ptFreezeCallback = IEC104ControlFreezeCallback(0)
    sParams.ptPulseEndActTermCallback = IEC104ControlPulseEndActTermCallback(0)
    sParams.ptParameterActCallback = IEC104ParameterActCallback(0)
    sParams.ptServerStatusCallback = IEC104ServerStatusCallback(0)
    sParams.ptDirectoryCallback = IEC104DirectoryCallback(0)
    sParams.u32Options = 0

    i16ErrCode = ctypes.c_short(); tErrVal = ctypes.c_short()
    try: g_client_handle = iec104_lib.IEC104Create(ctypes.byref(sParams), ctypes.byref(i16ErrCode), ctypes.byref(tErrVal))
    except Exception as e: logger.critical(f"CRITICAL: IEC104Create error: {e}. Exiting.", exc_info=True); sys.exit(1)
    if i16ErrCode.value != 0 or not g_client_handle: logger.error(f"IEC104Create FAILED. Code: {i16ErrCode.value}"); g_client_handle = None; return False
    logger.info(f"IEC104Create successful. Handle: {g_client_handle}")
    
    # 改进配置参数设置
    sConf = sIEC104ConfigurationParameters()
    
    # 设置源IP地址 - 确保字符串正确填充和null终止
    source_ip = "0.0.0.0".encode('ascii')
    sConf.sClientSet.ai8SourceIPAddress = source_ip + b'\x00' * (16 - len(source_ip))  # 假设IP地址字段为16字节
    
    sConf.sClientSet.benabaleUTCtime = False
    sConf.sClientSet.sDebug.u32DebugOptions = (eDebugOptionsFlag.DEBUG_OPTION_RX | eDebugOptionsFlag.DEBUG_OPTION_TX | eDebugOptionsFlag.DEBUG_OPTION_ERROR)
    sConf.sClientSet.u16TotalNumberofConnection = 1
    
    # 重要：设置自动生成IEC104数据对象
    sConf.sClientSet.bAutoGenIEC104DataObjects = True
    sConf.sClientSet.u16UpdateBuffersize = 1000  # 设置更新缓冲区大小
    sConf.sClientSet.bClientAcceptTCPconnection = False  # 客户端主动连接
    
    # 创建连接参数数组
    arraypointer = (sClientConnectionParameters * 1)()
    sConf.sClientSet.psClientConParameters = ctypes.cast(arraypointer, ctypes.POINTER(sClientConnectionParameters))
    conn_params = arraypointer[0]
    
    # 改进目标IP地址设置
    dest_ip = scada_ip.encode('ascii')
    conn_params.ai8DestinationIPAddress = dest_ip + b'\x00' * (16 - len(dest_ip))  # 确保null终止和正确填充
    
    conn_params.u16PortNumber = scada_port
    
    # 验证和设置超时参数（确保在合理范围内）
    conn_params.i16k = max(1, min(32767, param_k))  # k参数通常在1-32767范围内
    conn_params.i16w = max(1, min(32767, param_w))  # w参数通常在1-32767范围内
    conn_params.u8t0 = max(1, min(255, timeout_t0))  # t0通常在1-255范围内
    conn_params.u8t1 = max(1, min(255, timeout_t1))  # t1通常在1-255范围内
    conn_params.u8t2 = max(1, min(255, timeout_t2))  # t2通常在1-255范围内
    conn_params.u16t3 = max(1, min(65535, timeout_t3))  # t3通常在1-65535范围内
    
    logger.info(f"Configuration parameters: k={conn_params.i16k}, w={conn_params.i16w}, "
                f"t0={conn_params.u8t0}, t1={conn_params.u8t1}, t2={conn_params.u8t2}, t3={conn_params.u16t3}")
    
    conn_params.eState = eConnectState.DATA_MODE
    conn_params.u8TotalNumberofStations = 1
    
    # 验证CASDU地址
    if casdu_addr < 1 or casdu_addr > 65535:
        logger.error(f"Invalid CASDU address: {casdu_addr}. Must be 1-65535.")
        disconnect_scada()
        return False
    
    # 初始化所有interrogation间隔为0（禁用自动interrogation）
    # 改为设置一个短间隔来触发自动GI
    conn_params.u32GeneralInterrogationInterval = 10  # 10秒后自动发送GI，给连接一些时间稳定
    conn_params.u32Group1InterrogationInterval = 0
    conn_params.u32Group2InterrogationInterval = 0
    conn_params.u32Group3InterrogationInterval = 0
    conn_params.u32Group4InterrogationInterval = 0
    conn_params.u32Group5InterrogationInterval = 0
    conn_params.u32Group6InterrogationInterval = 0
    conn_params.u32Group7InterrogationInterval = 0
    conn_params.u32Group8InterrogationInterval = 0
    conn_params.u32Group9InterrogationInterval = 0
    conn_params.u32Group10InterrogationInterval = 0
    conn_params.u32Group11InterrogationInterval = 0
    conn_params.u32Group12InterrogationInterval = 0
    conn_params.u32Group13InterrogationInterval = 0
    conn_params.u32Group14InterrogationInterval = 0
    conn_params.u32Group15InterrogationInterval = 0
    conn_params.u32Group16InterrogationInterval = 0
    conn_params.u32CounterInterrogationInterval = 0
    conn_params.u32Group1CounterInterrogationInterval = 0
    conn_params.u32Group2CounterInterrogationInterval = 0
    conn_params.u32Group3CounterInterrogationInterval = 0
    conn_params.u32Group4CounterInterrogationInterval = 0
    conn_params.u32ClockSyncInterval = 0
    conn_params.u32CommandTimeout = 10000
    conn_params.u32FileTransferTimeout = 10000
    conn_params.bCommandResponseActtermUsed = False
    conn_params.bEnablefileftransfer = False
    conn_params.bUpdateCallbackCheckTimestamp = False
    conn_params.eCOTsize = eCauseofTransmissionSize.COT_TWO_BYTE
    
    # 关键：设置对象数量为0（因为使用自动生成）
    conn_params.u16NoofObject = 0
    conn_params.psIEC104Objects = None
    
    # 设置通用地址
    conn_params.au16CommonAddress[0] = casdu_addr
    conn_params.u8OriginatorAddress = 0
    
    # 初始化文件传输目录路径为空
    conn_params.ai8FileTransferDirPath = b'\x00' * 260  # MAX_DIRECTORY_PATH 通常是260
    
    logger.info(f"Loading configuration: Server={scada_ip}:{scada_port}, CASDU={casdu_addr}")
    ret_load = iec104_lib.IEC104LoadConfiguration(g_client_handle, ctypes.byref(sConf), ctypes.byref(tErrVal))
    if ret_load != 0: 
        logger.error(f"IEC104LoadConfiguration FAILED. Ret: {ret_load}, ErrVal: {tErrVal.value}")
        logger.error(f"检查配置参数: IP={scada_ip}, Port={scada_port}, CASDU={casdu_addr}")
        disconnect_scada()
        return False
    logger.info("IEC104LoadConfiguration successful.")
    
    ret_start = iec104_lib.IEC104Start(g_client_handle, ctypes.byref(tErrVal))
    if ret_start != 0: 
        logger.error(f"IEC104Start FAILED. Ret: {ret_start}, ErrVal: {tErrVal.value}")
        disconnect_scada()
        return False
    logger.info("IEC104Start called. Waiting for connection status...")
    time.sleep(1) 
    if g_connection_successful: logger.info("SCADA Connection successful (callback)."); return True
    else: logger.error("SCADA Connection FAILED (callback not confirmed)."); disconnect_scada(); return False

# --- 断开SCADA函数 (C API风格) ---
def disconnect_scada():
    global g_connection_successful, g_client_handle, iec104_lib, logger
    if g_client_handle is not None:
        logger.info(f"Stopping and freeing IEC 104 client (Handle: {g_client_handle})..."); tErrVal = ctypes.c_short()
        if iec104_lib: # 确保库已加载
            iec104_lib.IEC104Stop(g_client_handle, ctypes.byref(tErrVal)); logger.debug(f"IEC104Stop called. ErrVal: {tErrVal.value}")
            iec104_lib.IEC104Free(g_client_handle, ctypes.byref(tErrVal)); logger.debug(f"IEC104Free called. ErrVal: {tErrVal.value}")
        g_client_handle = None
    else: logger.debug("Client handle is None, no disconnect/free needed.")
    g_connection_successful = False

# --- 获取 wp_true 数据函数 (C API风格) ---
def fetch_wp_true_from_scada_once():
    global g_received_wp_true_value, g_last_scada_timestamp, iec104_lib, logger, casdu_addr, g_wp_true_ioa, scada_ip, scada_port
    g_received_wp_true_value = None
    g_last_scada_timestamp = None
    if not g_connection_successful or g_client_handle is None:
        logger.error("Cannot fetch: Not connected.")
        return False

    logger.info(f"Waiting for data from IOA {g_wp_true_ioa} (automatic GI should trigger within 10 seconds)...")

    # 等待自动GI触发并通过回调函数接收数据
    wait_start_time = time.time()
    logger.debug(f"Waiting up to {data_wait_timeout}s for data via callback...")
    
    while (time.time() - wait_start_time) < data_wait_timeout:
        if g_received_wp_true_value is not None and g_last_scada_timestamp is not None:
            logger.info(f"Data received via callback for IOA {g_wp_true_ioa}: Value={g_received_wp_true_value}, Timestamp={g_last_scada_timestamp.isoformat()}")
            return True
        time.sleep(0.1)  # 短暂休眠，让其他线程（如库的接收线程）有机会运行

    logger.warning(f"No data received for IOA {g_wp_true_ioa} via callback within {data_wait_timeout}s.")
    
    # 回退方案：尝试直接读取
    logger.info("Attempting direct IEC104Read as fallback...")
    psDAID_read = sIEC104DataAttributeID()
    psDAID_read.u16CommonAddress = casdu_addr
    psDAID_read.eTypeID = g_wp_true_ti_enum_value
    psDAID_read.u32IOA = g_wp_true_ioa
    psDAID_read.u16PortNumber = scada_port
    
    # 设置IP地址
    ip_bytes_read = scada_ip.encode('ascii')
    psDAID_read.ai8IPAddress = ip_bytes_read + b'\x00' * (16 - len(ip_bytes_read))
    
    psReturnedValue_read = sIEC104DataAttributeData()
    ctypes.memset(ctypes.byref(psReturnedValue_read), 0, ctypes.sizeof(psReturnedValue_read))
    tErrVal_read = ctypes.c_short()

    try:
        ret_read_fallback = iec104_lib.IEC104Read(g_client_handle, ctypes.byref(psDAID_read), ctypes.byref(psReturnedValue_read), ctypes.byref(tErrVal_read))
    except Exception as e:
        logger.error(f"Exception calling fallback IEC104Read: {e}", exc_info=True)
        return False

    if ret_read_fallback == 0:
        logger.info(f"Fallback IEC104Read successful. Quality={psReturnedValue_read.tQuality}, DataType={psReturnedValue_read.eDataType}, pvData={psReturnedValue_read.pvData}")
        
        # 检查数据有效性
        try:
            iv_flag = eIEC870QualityFlags.IV.value if hasattr(eIEC870QualityFlags.IV, 'value') else 1
        except (NameError, AttributeError):
            iv_flag = 1  # IV标志位通常是1
            
        is_valid = (psReturnedValue_read.tQuality & iv_flag) == 0
        
        if is_valid and psReturnedValue_read.pvData:
            try:
                float32_type = eDataTypes.FLOAT32_DATA.value if hasattr(eDataTypes.FLOAT32_DATA, 'value') else 4
            except (NameError, AttributeError):
                float32_type = 4  # 假设FLOAT32_DATA为4
                
            if psReturnedValue_read.eDataType == float32_type:
                try:
                    data_bytes = bytearray(ctypes.string_at(psReturnedValue_read.pvData, 4))
                    value = struct.unpack('f', data_bytes)[0]
                    ts_s = psReturnedValue_read.sTimeStamp
                    timestamp = datetime(ts_s.u16Year, ts_s.u8Month, ts_s.u8Day, ts_s.u8Hour, ts_s.u8Minute, ts_s.u8Seconds, ts_s.u16MilliSeconds * 1000)
                    
                    g_received_wp_true_value = value
                    g_last_scada_timestamp = timestamp
                    logger.info(f"Data obtained via fallback IEC104Read: Value={value:.3f}, Timestamp={timestamp.isoformat()}")
                    return True
                except Exception as e:
                    logger.error(f"Error extracting float value from fallback read: {e}")
            else:
                # 尝试按照实际数据大小提取数据
                logger.warning(f"Fallback read: data type is {psReturnedValue_read.eDataType}, expected {float32_type}. Trying to extract anyway...")
                if psReturnedValue_read.eDataSize == 4:  # 4字节，可能是float
                    try:
                        data_bytes = bytearray(ctypes.string_at(psReturnedValue_read.pvData, 4))
                        value = struct.unpack('f', data_bytes)[0]
                        g_received_wp_true_value = value
                        logger.info(f"Extracted 4-byte float value from fallback: {value}")
                        return True
                    except Exception as e:
                        logger.error(f"Failed to extract 4-byte float from fallback: {e}")
                elif psReturnedValue_read.eDataSize == 2:  # 2字节，可能是scaled value
                    try:
                        data_bytes = bytearray(ctypes.string_at(psReturnedValue_read.pvData, 2))
                        value = struct.unpack('h', data_bytes)[0]  # signed short
                        g_received_wp_true_value = float(value)
                        logger.info(f"Extracted 2-byte short value from fallback: {value}")
                        return True
                    except Exception as e:
                        logger.error(f"Failed to extract 2-byte short from fallback: {e}")
        else:
            if not is_valid:
                logger.warning(f"Fallback read: data is invalid. Quality={psReturnedValue_read.tQuality}")
            if not psReturnedValue_read.pvData:
                logger.warning("Fallback read: pvData is NULL")
    else:
        logger.warning(f"Fallback IEC104Read also failed. Ret: {ret_read_fallback}, ErrVal: {tErrVal_read.value}")

    return False

# --- 上传到数据库API函数 ---
def upload_to_api(target_timestamp_to_log, value_to_log):
    global logger, api_url # 确保这些全局变量可用
    payload = {"Timestamp": target_timestamp_to_log.isoformat(), "wp_true": value_to_log}
    logger.info(f"准备上传数据到 API {api_url}: {payload}")
    try:
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status() 
        logger.info(f"数据成功上传到 API: {response.json()}")
        return True
    except requests.exceptions.HTTPError as http_err: logger.error(f"API HTTP错误: {http_err} - 响应: {response.text if response and hasattr(response, 'text') else 'N/A'}")
    except requests.exceptions.RequestException as req_err: logger.error(f"API 请求错误: {req_err}")
    except Exception as e: logger.error(f"上传数据到 API 时发生未知错误: {e}", exc_info=True)
    return False

# --- 主程序入口 ---
if __name__ == "__main__":
    logger.info(f"IEC 104 Client (C API style) starting. Fetch interval: {inner_loop_interval_seconds}s.")
    update_next_target_checkpoint() 
    try:
        while True:
            main_loop_start_time = time.time()
            now = datetime.now()
            if now >= g_next_target_checkpoint:
                checkpoint_to_report = g_next_target_checkpoint 
                value_for_report = g_value_before_checkpoint    
                logger.info(f"Real time ({now.isoformat()}) reached/passed target checkpoint ({checkpoint_to_report.isoformat()}).")
                logger.info(f"Uploading for checkpoint {checkpoint_to_report.isoformat()} with cached value: {value_for_report}.")
                upload_to_api(checkpoint_to_report, value_for_report)
                update_next_target_checkpoint() 
            
            logger.info(f"---- Starting SCADA data fetch (next checkpoint: {g_next_target_checkpoint.isoformat()}) ----")
            if connect_scada(): 
                if fetch_wp_true_from_scada_once(): 
                    if g_received_wp_true_value is not None: 
                        g_value_before_checkpoint = g_received_wp_true_value 
                        logger.info(f"SCADA data fetch successful: {g_value_before_checkpoint}. Cached for next checkpoint.")
                disconnect_scada()
            else: logger.error("SCADA connection failed for this fetch cycle.")
            
            loop_execution_time = time.time() - main_loop_start_time
            sleep_time = inner_loop_interval_seconds - loop_execution_time
            if sleep_time < 0: sleep_time = 1 ; logger.warning(f"Loop execution time ({loop_execution_time:.2f}s) > interval ({inner_loop_interval_seconds}s).")
            logger.info(f"End of cycle. Sleeping for {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
    except KeyboardInterrupt: logger.info("Script interrupted by user.")
    except Exception as e: logger.error(f"CRITICAL UNHANDLED ERROR in main loop: {e}", exc_info=True)
    finally:
        logger.info("Performing final cleanup...")
        disconnect_scada()
        logger.info("IEC 104 Client script finished.")
        sys.exit(0)