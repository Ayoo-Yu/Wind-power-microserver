#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# --- 代码更新说明 ---
# 2025-04-12: 修复"multiple values for key 'edition'"错误
# - 添加多种策略尝试打开不同版本的GRIB文件
# - 为混合版本GRIB文件提供备用读取方式
# - 添加初始化时清理旧索引文件的功能
# - 增加GRIB文件诊断功能以帮助故障排除
#
# 2025-04-13: 保留空间位置数据并修复NaN问题
# - 不再对空间数据进行平均，保留所有点位数据
# - 使用经纬度作为CSV的索引列之一
# - 增强变量检测和日志记录，帮助排查NaN问题
# - 改进缺失数据处理，移除全为NaN的变量
#
# 2025-04-14: 为A1S文件添加特定处理策略
# - 添加针对A1S格式GRIB文件的专用读取策略
# - 分别处理surface和tropopause层级，然后合并结果
# - 使用grib_ls命令辅助诊断文件内容
# - 添加更多文件格式检测和错误恢复策略
#
# 2025-04-15: 添加特定点位数据筛选和透视功能 (本次更新)
# - 新增配置项 `TARGET_POINTS`, `TARGET_FILE_SUFFIX`, `TARGET_POINTS_TOLERANCE` 用于定义目标点位和文件名。
# - 新增辅助函数 `create_filtered_point_csv` 用于执行筛选和透视操作。
# - 在 `process_batch` 函数处理完主CSV后调用 `create_filtered_point_csv` 生成特定点位的CSV文件。
# - 优化了主CSV读取逻辑，增加了对多级索引的健壮性检查。
# ---------------------

import logging
import os
import re
import time
import signal
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# 尝试导入必要的库
try:
    import numpy as np # 用于 NaN 比较和数值操作
    import pandas as pd
    import xarray as xr
    # import cfgrib # cfgrib 被 xarray 的 engine='cfgrib' 隐式使用
    import eccodes # 用于 GRIB 文件诊断和直接读取
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemMovedEvent
    # 导入E文本转换模块
    import ecdata2etxt
except ImportError as e:
    print(f"错误：缺少必要的库: {e}。请确保已安装 numpy, pandas, xarray, python-eccodes (或 ecmwflibs), watchdog。")
    sys.exit(1)

# --- 配置项 ---
WATCH_DIR = Path("/ECMWF/data_milexi") # 监控的目录 (请根据实际情况修改)
OUTPUT_DIR = Path("/ECMWF/processed_csv") # CSV输出目录 (请根据实际情况修改)
ARCHIVE_DIR = Path("/ECMWF/data_milexi_processed") # 处理后GRIB文件归档目录 (请根据实际情况修改)
LOG_FILE = Path("/var/log/ecmwf_processor.log") # 日志文件路径 (请根据实际情况修改)

# GRIB 文件名模式: A1[S|D]MMDDHH00...
# 提取 预报起始时间 (MMDDHH00) 作为批次标识符
FILENAME_PATTERN = re.compile(r"^A1[SD](\d{8})(?!.*\.idx$)")

# --- 新增配置: 特定点位筛选 ---
# 重要: 请将下面的坐标替换为 竹园西 或其他目标站点的实际经纬度
TARGET_POINTS = {
    # 键是地点的英文或拼音标识符（将用于列名），值是包含 (纬度, 经度) 元组的列表
    "zhu_yuan_xi": [(23.8, 103.2), (23.9, 103.2), (24.0, 103.2), (24.1, 103.2), (24.2, 103.2),
                    (23.8, 103.3), (23.9, 103.3), (24.0, 103.3), (24.1, 103.3), (24.2, 103.3),
                    (23.8, 103.4), (23.9, 103.4), (24.0, 103.4), (24.1, 103.4), (24.2, 103.4)], # 示例：竹园西坐标 (纬度, 经度)
}
# 为第一个目标点配置（TARGET_POINTS的第一个键）生成的文件名添加后缀
TARGET_FILE_SUFFIX = "_zhu_yuan_xi"
# 坐标匹配容差（单位：度）。格点数据的坐标可能与目标点不完全一致。
TARGET_POINTS_TOLERANCE = 0.05 # 例如，0.05度约等于5公里，根据格点分辨率调整
# 是否移除包含NaN值的列（设置为True将生成更干净但可能信息更少的CSV）
REMOVE_NAN_COLUMNS = True
# 是否对时间进行插值处理
INTERPOLATE_TIME = True
# 时间插值间隔（分钟）
INTERPOLATION_INTERVAL_MINUTES = 15
# 插值方法 (可选: 'linear', 'time', 'index', 'values', 'nearest', 'zero', 
#          'slinear', 'quadratic', 'cubic', 'barycentric', 'polynomial')
INTERPOLATION_METHOD = 'linear'
# 插值后的CSV文件后缀
INTERPOLATED_FILE_SUFFIX = "_15min"
# 是否将UTC时间转换为北京时间
CONVERT_TO_BEIJING_TIME = True
# 北京时区信息 (UTC+8)
BEIJING_TIMEZONE = 'Asia/Shanghai'
# --- 特定点位筛选配置结束 ---

# --- 新增配置：专用预测文件 ---
# 是否生成专用预测文件
GENERATE_FORECAST_FILES = True
# 短中期预测使用的特征列表（用于18时刻批次）
MID_TERM_FEATURES = ['2t', '2d', '10u', '10v', '100u', '100v', '200u', '200v', 'dsrp','gh','hcc','msl', 'skt','ssrc','sp','ssrd','tisr', 'tcc','tcwv']
# 超短期预测使用的特征列表（用于12时刻批次）
SHORT_TERM_FEATURES = ['2t', '2d', '10u', '10v', '100u', '100v', '200u', '200v', 'dsrp','gh','hcc','msl', 'skt','ssrc','sp','ssrd','tisr', 'tcc','tcwv']
# 用于识别18时刻批次的模式
MIDTERM_BATCH_PATTERN = re.compile(r'^\d{4}18')  # 例如 0518
# 用于识别12时刻批次的模式
SHORTTERM_BATCH_PATTERN = re.compile(r'^\d{4}12')  # 例如 0512
# 专用预测文件数据开始行（跳过前20行）
FORECAST_DATA_START_ROW_MID = 88
FORECAST_DATA_START_ROW_SHORT = 28
# 后缀名
MID_TERM_SUFFIX = "_mid_term"
SHORT_TERM_SUFFIX = "_short_term"
# --- 专用预测文件配置结束 ---

# 定义基础期望特征 (此列表仅供参考，实际处理时会提取所有可用变量)
BASE_EXPECTED_FEATURES = [
    '2t', '2d', 'skt', 'mx2t', 'mn2t', 'mx2t3', 'mn2t3', 'mx2t6', 'mn2t6', 'deg0l', 'degm10l',
    '10u', '10v', 'u10n', 'v10n', 'i10fg', '10fg', '10fg3', '10fg6', '100u', '100v', '200u', '200v',
    'msl', 'sp', 'gh',
    'tcwv', 'tcc', 'hcc', 'hcct', 'ilspf',
    'ssr', 'ssrd', 'ssrc','sshf', 'slhf', 'dsrp', 'tisr', 'iews', 'inss', 'ishf', 'sund', 'pev',
    'blh', 'bld', 'capes', 'mld',
    'trpp', '200si',
]

# 变量名映射表 (处理可能的 GRIB shortName 变体)
VARIABLE_NAME_MAPPING = {
    # 温度
    't2m': '2t', 'temp2m': '2t', 'd2m': '2d', 'td2m': '2d', 'tmax': 'mx2t', 'tmin': 'mn2t',
    'mx2t24': 'mx2t', 'mn2t24': 'mn2t','tmax3': 'mx2t3', 'tmin3': 'mn2t3', 'tmax6': 'mx2t6',
    'tmin6': 'mn2t6', 'deg0': 'deg0l', 'degm10': 'degm10l',
    # 风
    'u10': '10u', 'v10': '10v', 'u10m': '10u', 'v10m': '10v', 'u100': '100u', 'v100': '100v',
    'u200': '200u', 'v200': '200v', 'fg10': '10fg', 'fg310': '10fg3', 'fg610': '10fg6',
    'fg6': '10fg6', 'fg_6h': '10fg6', '10fg6h': '10fg6', 'gust6': '10fg6', 'gust6h': '10fg6',
    'gust': '10fg', 'i10fg_max': 'i10fg', 'un10': 'u10n', 'vn10': 'v10n', 'p123': '10fg6', # 参数ID 123 通常是6小时最大阵风
    # 压力和高度
    'p': 'sp', 'psl': 'msl', 'slp': 'msl', 'z': 'gh', 'geopot': 'gh',
    # 湿度和云
    'r': 'tcwv', 'cc': 'tcc', 'hc': 'hcc', 'hct': 'hcct', 'ilspf_acc': 'ilspf',
    # 辐射
    'ssrd': 'ssrd', 'ssr': 'ssr', 'ssrc': 'ssrc', 'sshf_acc': 'sshf', 'slhf_acc': 'slhf',
    'dsrp_acc': 'dsrp', 'tisr_acc': 'tisr', 'iews_acc': 'iews', 'inss_acc': 'inss',
    'ishf_acc': 'ishf', 'sund_acc': 'sund', 'pev_acc': 'pev',
    # 边界层
    'blh': 'blh', 'bld_acc': 'bld', 'capes': 'capes', 'cape': 'capes', 'mld': 'mld',
    # 高空
    'si200': '200si', 'trpp': 'trpp', 'tropopause_pressure': 'trpp',
}


# 判断批次完成的超时时间（秒）
BATCH_COMPLETION_TIMEOUT = 1 * 10  # 15 分钟 (根据实际文件到达间隔调整)

# 检查周期（秒）
CHECK_INTERVAL = 10 # 1 分钟 (根据实际需求调整)
# --- 配置项结束 ---

# --- 日志设置 ---
# 清除旧的handler，避免重复添加
root_logger = logging.getLogger()
if root_logger.hasHandlers():
    root_logger.handlers.clear()

logging.basicConfig(
    level=logging.INFO, # 可以调整为 logging.DEBUG 获取更详细信息
    format='%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s', # 添加了函数/行号
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'), # 确保文件handler使用utf-8
        logging.StreamHandler(sys.stdout) # 同时输出到控制台
    ]
)
logging.info("日志系统初始化完成。")
# --- 日志设置结束 ---

# --- 全局状态变量 ---
batches_in_progress = defaultdict(lambda: {'files': set(), 'last_seen': 0.0})
batches_to_process = []
logging.info("全局状态变量初始化完成。")
# --- 全局状态变量结束 ---

# --- 辅助函数 ---
def cleanup_index_files():
    """清理监控目录下所有旧的cfgrib索引文件(.idx)"""
    logging.info(f"开始清理监控目录 {WATCH_DIR} 下的旧索引文件...")
    idx_count = 0
    try:
        for idx_file in WATCH_DIR.glob("*.idx"):
            try:
                idx_file.unlink()
                idx_count += 1
                logging.debug(f"已删除旧索引文件: {idx_file}")
            except OSError as e:
                logging.warning(f"删除索引文件失败: {idx_file}, 错误: {e}")
        logging.info(f"成功清理了 {idx_count} 个旧索引文件。")
    except Exception as e:
        logging.error(f"清理索引文件时发生意外错误: {e}", exc_info=True)

def get_grib_diagnostics(grib_file: Path) -> tuple[str, dict]:
    """获取GRIB文件的诊断信息，用于调试"""
    logging.debug(f"开始诊断 GRIB 文件: {grib_file}")
    summary = f"GRIB文件 {grib_file.name}: 诊断信息获取失败。"
    details = {"error": "诊断未执行或失败"}
    try:
        # eccodes 已在顶部导入
        result = {"grib_file": str(grib_file), "messages_summary": [], "message_count": 0, "all_shortNames": set(), "all_levels": set()}
        edition_count = defaultdict(int)
        message_count = 0
        
        with open(grib_file, 'rb') as f:
            while True:
                msg_id = None # 初始化 msg_id
                try:
                    msg_id = eccodes.codes_grib_new_from_file(f)
                    if msg_id is None:
                        break # 文件结束
                    
                    message_count += 1
                    try:
                        edition = eccodes.codes_get(msg_id, 'edition')
                    except:
                        edition = 0
                    edition_count[edition] += 1
                    
                    # 尝试获取关键信息
                    try:
                        shortName = eccodes.codes_get(msg_id, 'shortName')
                    except:
                        shortName = 'N/A'
                    try:
                        levelType = eccodes.codes_get(msg_id, 'typeOfLevel')
                    except:
                        levelType = 'N/A'
                    try:
                        level = eccodes.codes_get(msg_id, 'level')
                    except:
                        level = 'N/A'

                    result["all_shortNames"].add(shortName)
                    result["all_levels"].add((levelType, level))

                    # 仅记录前几条消息的摘要
                    if len(result["messages_summary"]) < 5:
                        msg_summary = f"Msg {message_count}: Edition={edition}, shortName={shortName}, typeOfLevel={levelType}, level={level}"
                        result["messages_summary"].append(msg_summary)

                except Exception as e_msg:
                    logging.warning(f"处理 GRIB 文件 {grib_file.name} 中的消息 {message_count+1} 时出错: {e_msg}")
                    # 如果是读取错误，可能无法继续，尝试跳出循环
                    if "end of file" in str(e_msg).lower():
                         break
                    # 其他错误可能允许继续读取下一条消息
                finally:
                    if msg_id is not None:
                        eccodes.codes_release(msg_id) # 确保释放句柄
        
        result["message_count"] = message_count
        result["edition_count"] = dict(edition_count) # 转为普通字典
        result["all_shortNames"] = sorted(list(result["all_shortNames"])) # 排序方便查看
        result["all_levels"] = sorted(list(result["all_levels"]))

        summary = f"GRIB文件 {grib_file.name}: 总消息数={message_count}, "
        summary += f"版本分布={result['edition_count']}, "
        summary += f"发现的shortName({len(result['all_shortNames'])}个): {result['all_shortNames'][:10]}..., " # 显示前10个
        summary += f"发现的层级({len(result['all_levels'])}种): {result['all_levels'][:5]}..." # 显示前5种

        # 检查 10fg6 别名
        possible_10fg6_names = {'10fg6', 'fg6', 'fg610', 'fg_6h', '10fg6h', 'gust6', 'gust6h', 'p123'}
        found_aliases = possible_10fg6_names.intersection(result['all_shortNames'])
        if found_aliases:
            logging.info(f"诊断发现: 文件 {grib_file.name} 中包含可能的10fg6别名: {list(found_aliases)}")
        else:
             logging.info(f"诊断发现: 文件 {grib_file.name} 中未找到常见的10fg6别名。")

        details = result # 更新 details
        logging.debug(f"GRIB 文件诊断完成: {grib_file.name}")

    except Exception as e_ecc:
        summary = f"获取 GRIB 诊断信息失败: {e_ecc}"
        details = {"error": str(e_ecc)}
        logging.error(summary, exc_info=False) # 只记录错误信息，不记录堆栈
    except FileNotFoundError:
        summary = f"获取 GRIB 诊断信息失败: 文件 {grib_file} 未找到。"
        details = {"error": "File not found"}
        logging.error(summary)
    except Exception as e:
        summary = f"获取 GRIB 诊断信息时发生未知错误: {e}"
        details = {"error": str(e)}
        logging.error(summary, exc_info=True) # 记录未知错误的堆栈

    return summary, details


# --- 新增辅助函数: 筛选并透视特定点位数据 ---
def create_filtered_point_csv(source_csv_path: Path, target_points_config: dict, suffix: str, tolerance: float, batch_id: str = None):
    """
    从源CSV文件中筛选特定点位的数据，并生成新的CSV文件
    
    Args:
        source_csv_path: 源CSV文件路径
        target_points_config: 目标点位配置 (字典，键:点位名称，值:(纬度,经度)元组列表)
        suffix: 输出文件后缀
        tolerance: 坐标匹配容差（度）
        batch_id: 批次ID，用于创建批次特定的文件夹，如果为None则取文件名中的批次ID
    """
    logging.info(f"[点位筛选] 开始为 {source_csv_path} 执行点位筛选和透视...")
    
    # 如果未提供batch_id，尝试从文件名中提取
    year_part = None
    
    if batch_id is None:
        # 尝试从文件名中提取批次ID和年份
        # 首先检查文件名是否包含年份 (形如 ECMWF_Forecast_YYYY_MMDDHHMM.csv)
        stem_parts = source_csv_path.stem.split('_')
        if len(stem_parts) >= 3 and stem_parts[2].isdigit() and len(stem_parts[2]) == 4:
            # 文件名包含年份
            year_part = stem_parts[2]
            # 尝试提取批次ID
            if len(stem_parts) >= 4:
                batch_id = stem_parts[3]
                logging.info(f"[点位筛选] 从文件名中提取的年份和批次ID: {year_part}_{batch_id}")
        else:
            # 尝试旧格式提取批次ID
            match = FILENAME_PATTERN.search(source_csv_path.stem)
            if match:
                batch_id = match.group(1)
                # 确定年份
                year_part = str(determine_year_from_batch_id(batch_id))
                logging.info(f"[点位筛选] 从文件名中提取的批次ID: {batch_id}，确定年份: {year_part}")
            else:
                # 如果无法从文件名中提取，使用时间戳作为批次ID
                batch_id = datetime.now().strftime("%m%d%H%M")
                year_part = str(datetime.now().year)
                logging.warning(f"[点位筛选] 无法从 {source_csv_path.stem} 提取批次ID，使用当前时间作为批次ID: {year_part}_{batch_id}")
    else:
        # 如果提供了batch_id，检查是否包含年份
        if '_' in batch_id:
            parts = batch_id.split('_', 1)
            if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 4:
                year_part = parts[0]
                batch_id_only = parts[1]
                logging.info(f"[点位筛选] 从提供的batch_id中提取年份和批次: {year_part}_{batch_id_only}")
            else:
                # 不符合预期格式，使用原始batch_id
                year_part = str(determine_year_from_batch_id(batch_id))
        else:
            # 没有年份部分，确定年份
            year_part = str(determine_year_from_batch_id(batch_id))
    
    # 确保batch_id包含年份
    if year_part and '_' not in batch_id:
        full_batch_id = f"{year_part}_{batch_id}"
    else:
        full_batch_id = batch_id
    
    # 创建批次特定的输出目录
    batch_output_dir = OUTPUT_DIR / full_batch_id
    batch_output_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"[点位筛选] 为批次 {full_batch_id} 创建/确认输出目录: {batch_output_dir}")
    
    # 构建目标文件路径（放在批次特定的文件夹下）
    target_csv_path = batch_output_dir / f"{source_csv_path.stem}{suffix}.csv"
    
    # 检查目标文件是否已存在
    if target_csv_path.exists():
        logging.warning(f"[点位筛选] 目标文件 {target_csv_path} 已存在，跳过筛选操作。")
        return
    
    try:
        # --- 读取源CSV文件 ---
        df = None
        try:
            # 尝试读取为标准CSV
            df = pd.read_csv(source_csv_path)
            # 如果成功，检查必要的列是否存在
            required_cols = ['valid_time', 'latitude', 'longitude']
            
            # 找到实际列名，以便处理列名可能的大小写不同
            actual_cols = {col.lower(): col for col in df.columns}
            col_mapping = {}
            for req_col in required_cols:
                req_col_lower = req_col.lower()
                if req_col_lower in actual_cols:
                    col_mapping[req_col] = actual_cols[req_col_lower]
                else:
                    col_mapping = None
                    break
            
            if col_mapping is not None:
                # 重命名列以使用标准名称
                if any(col_mapping[col] != col for col in required_cols):
                    df = df.rename(columns={col_mapping[col]: col for col in required_cols})
                logging.debug(f"[点位筛选] 成功使用标准CSV格式加载 {source_csv_path}。")
            elif all(col in df.columns for col in required_cols):
                logging.debug(f"[点位筛选] 成功使用标准CSV格式加载 {source_csv_path}，列名已标准化。")
            else:
                # 尝试检查是否是特殊格式
                if all(col in df.columns for col in ['valid_time']):
                    # 可能是没有地理信息的特殊格式
                    df_plain = df.copy()
                    logging.warning(f"[点位筛选] 文件 {source_csv_path} 可能是特殊格式（无地理信息）。尝试替代处理。")
                    
                    # 尝试处理普通格式（无地理信息）
                    if 'valid_time' in df_plain.columns:
                        df_plain['valid_time'] = pd.to_datetime(df_plain['valid_time'])
                        
                        # 时区转换（如果启用）
                        if CONVERT_TO_BEIJING_TIME:
                            # 将valid_time列视为UTC时间
                            df_plain['valid_time'] = df_plain['valid_time'].dt.tz_localize('UTC')
                            # 转换为北京时间
                            df_plain['valid_time'] = df_plain['valid_time'].dt.tz_convert(BEIJING_TIMEZONE)
                            # 去除时区信息
                            df_plain['valid_time'] = df_plain['valid_time'].dt.tz_localize(None)
                            logging.info(f"[点位筛选] 已将时间从UTC转换为北京时间")
                        
                        # 此类文件通常不需要地理筛选，直接保存
                        logging.info(f"[点位筛选] 特殊格式文件，跳过地理筛选，直接保存到 {target_csv_path}")
                        df_plain.to_csv(target_csv_path, index=False)
                        logging.info(f"[点位筛选] 成功保存特殊格式文件: {target_csv_path}")
                        
                        # 检查是否需要进行时间插值
                        if INTERPOLATE_TIME and not df_plain.empty:
                            try:
                                # 设置时间索引
                                df_time_indexed = df_plain.set_index('valid_time')
                                
                                # 执行时间插值
                                interpolated_df = interpolate_time_series(
                                    df_time_indexed, 
                                    interval_minutes=INTERPOLATION_INTERVAL_MINUTES,
                                    method=INTERPOLATION_METHOD
                                )
                                
                                if interpolated_df is not None and not interpolated_df.empty:
                                    # 构建插值后的文件名，放在批次特定的文件夹下
                                    interpolated_path = batch_output_dir / f"INTER_{source_csv_path.stem}{suffix}{INTERPOLATED_FILE_SUFFIX}.csv"
                                    
                                    # 保存插值后的数据
                                    logging.info(f"[点位筛选] 保存插值后的数据到 {interpolated_path} (形状: {interpolated_df.shape})")
                                    interpolated_df.to_csv(interpolated_path, index=False)
                                    logging.info(f"[点位筛选] 成功创建插值后的点位文件: {interpolated_path}")
                                    
                                    # 生成专用预测文件
                                    generate_forecast_file(interpolated_df, interpolated_path, batch_id)
                                    
                                    # 生成特征平均值文件
                                    generate_average_feature_file(interpolated_path)
                                    
                                    # 删除筛选后的点位文件(B)，保留插值文件(C)和预测文件(D)
                                    try:
                                        if target_csv_path.exists():
                                            target_csv_path.unlink()
                                            logging.info(f"[点位筛选] 已删除筛选后的点位文件: {target_csv_path}")
                                    except Exception as e_del:
                                        logging.error(f"[点位筛选] 删除筛选后的点位文件时出错: {e_del}")
                                else:
                                    logging.warning("[点位筛选] 插值结果为空，跳过保存插值文件")
                            except Exception as e_interp:
                                logging.error(f"[点位筛选] 执行特殊格式时间插值时出错: {e_interp}", exc_info=True)
                        
                        return
                
                # 尝试读取为MultiIndex格式
                logging.warning(f"[点位筛选] 文件 {source_csv_path} 不是标准CSV格式，尝试读取为MultiIndex格式...")
                df = None
        
        except Exception as e_read_std:
            # 读取标准CSV失败，尝试其他格式
            logging.warning(f"[点位筛选] 读取标准CSV格式失败: {e_read_std}，尝试MultiIndex格式...")
            df = None

        # 如果标准读取失败，尝试读取为MultiIndex格式
        if df is None:
            try:
                # 尝试读取为三级索引（valid_time, latitude, longitude）
                df = pd.read_csv(source_csv_path, index_col=[0, 1, 2])
                
                # 确保索引列是正确的数值和日期时间类型
                df.index = pd.MultiIndex.from_arrays([
                    pd.to_datetime(df.index.levels[0]),
                    pd.to_numeric(df.index.levels[1]),
                    pd.to_numeric(df.index.levels[2])
                ])
                
                # 时区转换（如果启用）
                if CONVERT_TO_BEIJING_TIME:
                    # 首先确保时间是UTC时区的
                    utc_times = df.index.get_level_values('valid_time').tz_localize('UTC')
                    # 然后转换到北京时间
                    beijing_times = utc_times.tz_convert(BEIJING_TIMEZONE)
                    # 去除时区信息，只保留本地时间值
                    beijing_times = beijing_times.tz_localize(None)
                    # 更新索引
                    df.index = df.index.set_levels([beijing_times, 
                                                 df.index.levels[1], 
                                                 df.index.levels[2]], 
                                                level=[0, 1, 2])
                    logging.info(f"[点位筛选] 已将时间从UTC转换为北京时间")
                
                logging.debug(f"[点位筛选] 成功使用 MultiIndex 加载 {source_csv_path}。")
            except Exception as e_read_multi:
                logging.error(f"[点位筛选] 读取 {source_csv_path} 为 MultiIndex 格式失败: {e_read_multi}")
                raise ValueError(f"无法读取文件为标准CSV或MultiIndex格式: {e_read_multi}")

        # --- 进行点位筛选 ---
        if df is None:
            logging.error(f"[点位筛选] 无法加载文件 {source_csv_path}")
            return

        # 检查是否是MultiIndex格式
        is_multi_index = isinstance(df.index, pd.MultiIndex) and len(df.index.names) == 3
        
        if is_multi_index:
            # 使用MultiIndex格式筛选
            logging.info(f"[点位筛选] 使用MultiIndex格式进行点位筛选...")
            
            # 筛选匹配的点位
            filtered_indices = []
            for point_name, point_coords in target_points_config.items():
                for lat, lon in point_coords:
                    for idx_lat, idx_lon in zip(df.index.levels[1], df.index.levels[2]):
                        if (abs(idx_lat - lat) <= tolerance and 
                            abs(idx_lon - lon) <= tolerance):
                            times = df.index.levels[0]
                            for time in times:
                                try:
                                    if (time, idx_lat, idx_lon) in df.index:
                                        filtered_indices.append((time, idx_lat, idx_lon))
                                except Exception:
                                    # 某些复合索引可能不存在，忽略错误
                                    pass
            
            # 如果没有匹配的点位，记录警告并返回
            if not filtered_indices:
                logging.warning(f"[点位筛选] 未找到匹配的点位，无法创建筛选后的CSV文件")
                return
            
            # 使用筛选后的索引获取子集
            filtered_df = df.loc[filtered_indices]
            
        else:
            # 使用标准CSV格式筛选（使用更高效的向量化操作）
            logging.info(f"[点位筛选] 使用标准CSV格式进行点位筛选...")
            
            # 构建筛选条件
            filtered_df = pd.DataFrame()  # 创建一个空的DataFrame来存储所有匹配的点
            
            for point_name, point_coords in target_points_config.items():
                logging.debug(f"[点位筛选] 处理点位 {point_name} 的 {len(point_coords)} 个坐标...")
                
                for lat, lon in point_coords:
                    # 使用向量化操作找到接近目标坐标的所有行
                    lat_mask = np.abs(df['latitude'] - lat) <= tolerance
                    lon_mask = np.abs(df['longitude'] - lon) <= tolerance
                    
                    # 合并条件
                    combined_mask = lat_mask & lon_mask
                    
                    if combined_mask.any():
                        # 找到了匹配点，添加到筛选结果中
                        matched_rows = df[combined_mask].copy()
                        # 增加点位名称列，便于后续区分
                        matched_rows['point_name'] = point_name
                        matched_rows['target_lat'] = lat
                        matched_rows['target_lon'] = lon
                        
                        # 追加到总的筛选结果中
                        filtered_df = pd.concat([filtered_df, matched_rows])
                        
                        logging.debug(f"[点位筛选] 找到 {combined_mask.sum()} 行匹配点位 ({lat}, {lon})")
                    else:
                        logging.warning(f"[点位筛选] 未找到匹配点位 ({lat}, {lon}) 的数据")
            
            if filtered_df.empty:
                logging.warning(f"[点位筛选] 未找到任何匹配的点位，无法创建筛选后的CSV文件")
                return
        
        # --- 数据透视 ---
        try:
            logging.info(f"[点位筛选] 找到 {len(filtered_df)} 行匹配的点位数据，开始执行数据透视...")
            
            # 根据格式执行不同的透视操作
            if is_multi_index:
                # 如果是MultiIndex格式
                # 重新组织为 valid_time 为索引，列名为 "varname_lat_lon" 格式的透视表
                pivoted_df = pd.DataFrame(index=sorted(set(idx[0] for idx in filtered_df.index)))
                
                # 找出所有变量名
                all_variables = filtered_df.columns
                
                # 为每个变量和位置组合创建一列
                for lat, lon in set((idx[1], idx[2]) for idx in filtered_df.index):
                    for var in all_variables:
                        # 提取当前变量和位置的所有时间点数据
                        var_data = {}
                        for time, idx_lat, idx_lon in filtered_df.index:
                            if idx_lat == lat and idx_lon == lon:
                                try:
                                    var_data[time] = filtered_df.loc[(time, lat, lon), var]
                                except:
                                    # 可能某些组合不存在
                                    pass
                        
                        # 添加一列，格式为 "var_lat_lon"
                        if var_data:  # 只有当有数据时才添加列
                            col_name = f"{var}_{lat}_{lon}"
                            pivoted_df[col_name] = pd.Series(var_data)
                
            else:
                # 如果是标准CSV格式
                # 使用pandas的pivot_table函数
                pivoted_df = pd.pivot_table(
                    filtered_df,
                    index='valid_time',
                    columns=['point_name', 'target_lat', 'target_lon'],
                    values=[col for col in filtered_df.columns if col not in ['valid_time', 'latitude', 'longitude', 'point_name', 'target_lat', 'target_lon']]
                )
                
                # 展平MultiIndex列名
                pivoted_df.columns = [f"{col[0]}_{col[2]}_{col[3]}" for col in pivoted_df.columns]
            
            # 根据配置，移除包含NaN的列
            if REMOVE_NAN_COLUMNS:
                # 查找包含NaN的列
                cols_with_nan = pivoted_df.columns[pivoted_df.isna().any()].tolist()
                if cols_with_nan:
                    # 记录下将要移除的列
                    removed_cols = len(cols_with_nan)
                    remaining_cols = len(pivoted_df.columns) - removed_cols
                    
                    if removed_cols == len(pivoted_df.columns):
                        logging.warning("[点位筛选] 所有列都包含NaN值，这可能是个问题")
                        # 通常我们仍会继续处理，但保留警告
                    
                    # 从DataFrame中移除这些列
                    pivoted_df = pivoted_df.drop(columns=cols_with_nan)
                    logging.info(f"[点位筛选] 已移除 {removed_cols} 个包含NaN的列，剩余 {remaining_cols} 列")
                    if removed_cols > 0 and remaining_cols == 0:
                        logging.warning("[点位筛选] 所有列都包含NaN值，无法生成有效的CSV文件")
                        return
                else:
                    logging.info("[点位筛选] 未发现包含NaN的列，保留所有列")

            # 保存透视后的数据
            logging.info(f"[点位筛选] 保存筛选并透视后的数据到 {target_csv_path} (形状: {pivoted_df.shape})")
            pivoted_df.to_csv(target_csv_path, index=True, na_rep='NaN') # index=True 保存 valid_time 索引
            logging.info(f"[点位筛选] 成功创建筛选后的点位文件: {target_csv_path}")
            
            # 根据配置决定是否进行时间插值
            if INTERPOLATE_TIME and not pivoted_df.empty:
                try:
                    logging.info(f"[点位筛选] 开始进行时间插值处理 (间隔: {INTERPOLATION_INTERVAL_MINUTES}分钟, 方法: {INTERPOLATION_METHOD})")
                    
                    # 执行时间插值
                    interpolated_df = interpolate_time_series(
                        pivoted_df, 
                        interval_minutes=INTERPOLATION_INTERVAL_MINUTES,
                        method=INTERPOLATION_METHOD
                    )
                    
                    if interpolated_df is not None and not interpolated_df.empty:
                        # 构建插值后的文件名，放在批次特定的文件夹下
                        interpolated_path = batch_output_dir / f"INTER_{source_csv_path.stem}{suffix}{INTERPOLATED_FILE_SUFFIX}.csv"
                        
                        # 保存插值后的数据
                        logging.info(f"[点位筛选] 保存插值后的数据到 {interpolated_path} (形状: {interpolated_df.shape})")
                        interpolated_df.to_csv(interpolated_path, index=False)
                        logging.info(f"[点位筛选] 成功创建插值后的点位文件: {interpolated_path}")
                        
                        # 生成专用预测文件
                        generate_forecast_file(interpolated_df, interpolated_path, batch_id)
                        
                        # 生成特征平均值文件
                        generate_average_feature_file(interpolated_path)
                        
                        # 删除筛选后的点位文件(B)，保留插值文件(C)和预测文件(D)
                        try:
                            if target_csv_path.exists():
                                target_csv_path.unlink()
                                logging.info(f"[点位筛选] 已删除筛选后的点位文件: {target_csv_path}")
                        except Exception as e_del:
                            logging.error(f"[点位筛选] 删除筛选后的点位文件时出错: {e_del}")
                    else:
                        logging.warning("[点位筛选] 插值结果为空，跳过保存插值文件")
                        
                except Exception as e_interp:
                    logging.error(f"[点位筛选] 执行时间插值时出错: {e_interp}", exc_info=True)

        except Exception as e_pivot:
             logging.error(f"[点位筛选] 对文件 {source_csv_path} 进行数据透视失败: {e_pivot}", exc_info=True)
             # 记录导致透视失败的DataFrame信息（如果不大）
             if filtered_df.memory_usage(deep=True).sum() < 10 * 1024 * 1024: # 小于10MB
                 logging.debug(f"透视失败前的 filtered_df (前5行):\n{filtered_df.head()}")
                 logging.debug(f"列类型: {filtered_df.dtypes}")
                 logging.debug(f"非数值列: {[col for col in filtered_df.columns if not pd.api.types.is_numeric_dtype(filtered_df[col].dtype)]}")
             return

    except MemoryError:
        logging.error(f"[点位筛选] 处理文件 {source_csv_path} 时发生内存错误。文件可能过大无法在内存中完成筛选。")
    except Exception as e:
        logging.error(f"[点位筛选] 在为 {source_csv_path} 执行筛选/透视时发生意外错误: {e}", exc_info=True)

# --- 新增辅助函数: 时间插值处理 ---
def interpolate_time_series(df, interval_minutes=15, method='linear'):
    """
    对时间序列数据进行插值，生成固定时间间隔的数据集
    
    Args:
        df: 带有时间索引的DataFrame
        interval_minutes: 插值后的时间间隔（分钟）
        method: 插值方法，默认为线性插值
        
    Returns:
        插值后的DataFrame
    """
    if df.empty:
        logging.warning("[时间插值] 输入DataFrame为空，无法进行插值")
        return df
        
    try:
        # 确保索引是时间类型
        if not isinstance(df.index, pd.DatetimeIndex):
            logging.warning("[时间插值] 输入DataFrame索引不是时间类型，尝试转换")
            df.index = pd.to_datetime(df.index)
            
        # 获取开始和结束时间
        start_time = df.index.min()
        end_time = df.index.max()
        
        # 检查时间跨度
        time_span = end_time - start_time
        total_minutes = time_span.total_seconds() / 60
        
        if total_minutes < interval_minutes:
            logging.warning(f"[时间插值] 时间跨度 ({total_minutes:.2f}分钟) 小于插值间隔 ({interval_minutes}分钟)，插值可能无意义")
            return df
            
        # 创建均匀的时间序列
        # 向前取整到整点，便于时间对齐
        # 根据不同的分钟间隔取整
        freq_str = f'{interval_minutes}min'
        start_rounded = start_time.floor(freq_str)
        end_rounded = end_time.ceil(freq_str)
        
        # 创建新的时间序列
        new_index = pd.date_range(
            start=start_rounded,
            end=end_rounded,
            freq=freq_str
        )
        
        # 如果启用了北京时间转换，则在日志中记录使用的是北京时间
        if CONVERT_TO_BEIJING_TIME:
            logging.info(f"[时间插值] 使用北京时间进行插值 (范围: {start_rounded} - {end_rounded})")
        else:
            logging.info(f"[时间插值] 使用UTC时间进行插值 (范围: {start_rounded} - {end_rounded})")
        
        if len(new_index) <= 1:
            logging.warning("[时间插值] 生成的新时间索引过短，无法进行插值")
            return df
            
        # 记录原始数据点数和新索引点数
        original_points = len(df)
        new_points = len(new_index)
        logging.info(f"[时间插值] 原始数据点数: {original_points}, 插值后点数: {new_points}, 插值方法: {method}")
        
        # 执行插值
        interpolated_df = df.reindex(df.index.union(new_index))
        interpolated_df = interpolated_df.interpolate(method=method)
        
        # 只保留新的时间索引
        interpolated_df = interpolated_df.reindex(new_index)
        
        # 重置索引，确保时间列名为"Timestamp"
        interpolated_df = interpolated_df.reset_index()
        interpolated_df.rename(columns={'index': 'Timestamp'}, inplace=True)
        
        # 返回插值后的数据
        return interpolated_df
        
    except Exception as e:
        logging.error(f"[时间插值] 执行插值时出错: {e}", exc_info=True)
        # 发生错误时返回原始数据
        return df

# --- 新增辅助函数: 根据批次ID生成专用预测文件 ---
def generate_forecast_file(interpolated_df, interpolated_path, batch_id):
    """
    根据批次ID生成相应的专用预测文件
    
    Args:
        interpolated_df: 插值后的DataFrame
        interpolated_path: 插值文件路径
        batch_id: 批次ID，用于判断是12时刻还是18时刻
    """
    if not GENERATE_FORECAST_FILES or interpolated_df is None or interpolated_df.empty:
        return
    
    try:
        # 从batch_id中提取年份和原始批次部分
        # batch_id格式应为 "YYYY_MMDDHHMM"
        year_part = None
        original_batch_id = batch_id
        
        # 检查batch_id是否包含年份信息
        if '_' in batch_id:
            parts = batch_id.split('_', 1)
            if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 4:
                year_part = parts[0]
                original_batch_id = parts[1]  # 提取不包含年份的原始批次ID
        
        # 如果没有年份信息，确定年份
        if year_part is None:
            year_part = str(determine_year_from_batch_id(batch_id))
        
        # 获取文件所在目录
        file_dir = interpolated_path.parent
        
        # 检查是否是18时刻批次
        if MIDTERM_BATCH_PATTERN.match(original_batch_id):
            logging.info(f"[专用预测] 检测到18时刻批次 {batch_id}，生成短中期专用预测文件")
            
            # --- 修正后的筛选逻辑 ---
            features_to_keep = []
            # 总是保留 Timestamp 列
            if 'Timestamp' in interpolated_df.columns:
                features_to_keep.append('Timestamp')

            # 遍历所有列
            for col in interpolated_df.columns:
                if col == 'Timestamp': # 已经添加过，跳过
                    continue
                
                col_lower = col.lower() # 转换为小写一次
                
                # 检查列名是否以任何一个目标特征名 + 下划线 开头
                # 这确保了精确匹配特征名本身，而不是作为子串匹配
                is_target_feature = False
                for feature in MID_TERM_FEATURES:
                    if col_lower.startswith(feature + '_'):
                        is_target_feature = True
                        break # 找到匹配的特征，无需再检查其他特征
                
                if is_target_feature:
                    features_to_keep.append(col)
            
            # 确保列表唯一，虽然上面的逻辑应该能保证，以防万一
            features_to_keep = list(dict.fromkeys(features_to_keep))

            logging.debug(f"[专用预测] 筛选出的特征列 ({len(features_to_keep)}): {features_to_keep[:20]}...") # 打印部分筛选结果用于调试
            # --- 修正后的筛选逻辑结束 ---
            
            # 从第88行开始选择数据
            forecast_df = interpolated_df.iloc[FORECAST_DATA_START_ROW_MID:].copy()
            
            # 检查筛选出的列是否真的都在forecast_df中 (以防万一)
            actual_cols_to_keep = [col for col in features_to_keep if col in forecast_df.columns]
            if len(actual_cols_to_keep) < len(features_to_keep):
                missing_cols = set(features_to_keep) - set(actual_cols_to_keep)
                logging.warning(f"[专用预测] 筛选出的部分列在iloc切片后不存在: {missing_cols}")
            
            forecast_df = forecast_df[actual_cols_to_keep]
            
            # 生成输出文件路径 - 包含年份和前缀
            forecast_path = file_dir / f"Pre_use_{interpolated_path.stem}{MID_TERM_SUFFIX}.csv"
            
            # 保存预测文件
            logging.info(f"[专用预测] 保存短中期预测文件到 {forecast_path} (特征数: {len(actual_cols_to_keep)}, 行数: {len(forecast_df)})")
            forecast_df.to_csv(forecast_path, index=False)
            
            # 调用E文本转换函数
            try:
                logging.info(f"[专用预测] 开始为中期预测文件 {forecast_path} 生成E文本")
                success = ecdata2etxt.convert_csv_to_etext(
                    csv_filepath=forecast_path,
                    data_type="forecast",
                    report_type=ecdata2etxt.MID_TERM_CLASS_NAME
                )
                if success:
                    logging.info(f"[专用预测] 成功为中期预测文件 {forecast_path} 生成E文本")
                else:
                    logging.warning(f"[专用预测] 为中期预测文件 {forecast_path} 生成E文本失败")
            except Exception as e_etxt:
                logging.error(f"[专用预测] 调用E文本转换时出错: {e_etxt}", exc_info=True)
            
        # 检查是否是12时刻批次
        elif SHORTTERM_BATCH_PATTERN.match(original_batch_id):
            logging.info(f"[专用预测] 检测到12时刻批次 {batch_id}，生成超短期专用预测文件")
            
            # --- 修正后的筛选逻辑 ---
            features_to_keep = []
            # 总是保留 Timestamp 列
            if 'Timestamp' in interpolated_df.columns:
                features_to_keep.append('Timestamp')

            # 遍历所有列
            for col in interpolated_df.columns:
                if col == 'Timestamp': # 已经添加过，跳过
                    continue
                
                col_lower = col.lower() # 转换为小写一次
                
                # 检查列名是否以任何一个目标特征名 + 下划线 开头
                # 这确保了精确匹配特征名本身，而不是作为子串匹配
                is_target_feature = False
                for feature in SHORT_TERM_FEATURES:
                    if col_lower.startswith(feature + '_'):
                        is_target_feature = True
                        break # 找到匹配的特征，无需再检查其他特征
                
                if is_target_feature:
                    features_to_keep.append(col)
            
            # 确保列表唯一，虽然上面的逻辑应该能保证，以防万一
            features_to_keep = list(dict.fromkeys(features_to_keep))

            logging.debug(f"[专用预测] 筛选出的特征列 ({len(features_to_keep)}): {features_to_keep[:20]}...") # 打印部分筛选结果用于调试
            # --- 修正后的筛选逻辑结束 ---
            
            # 从第28行开始选择数据
            forecast_df = interpolated_df.iloc[FORECAST_DATA_START_ROW_SHORT:].copy()
            
            # 检查筛选出的列是否真的都在forecast_df中 (以防万一)
            actual_cols_to_keep = [col for col in features_to_keep if col in forecast_df.columns]
            if len(actual_cols_to_keep) < len(features_to_keep):
                missing_cols = set(features_to_keep) - set(actual_cols_to_keep)
                logging.warning(f"[专用预测] 筛选出的部分列在iloc切片后不存在: {missing_cols}")
            
            forecast_df = forecast_df[actual_cols_to_keep]
            
            # 生成输出文件路径 - 包含年份和前缀
            forecast_path = file_dir / f"Pre_use_{interpolated_path.stem}{SHORT_TERM_SUFFIX}.csv"
            
            # 保存预测文件
            logging.info(f"[专用预测] 保存超短期预测文件到 {forecast_path} (特征数: {len(actual_cols_to_keep)}, 行数: {len(forecast_df)})")
            forecast_df.to_csv(forecast_path, index=False)
            
            # 调用E文本转换函数
            try:
                logging.info(f"[专用预测] 开始为短期预测文件 {forecast_path} 生成E文本")
                success = ecdata2etxt.convert_csv_to_etext(
                    csv_filepath=forecast_path,
                    data_type="forecast",
                    report_type=ecdata2etxt.SHORT_TERM_CLASS_NAME
                )
                if success:
                    logging.info(f"[专用预测] 成功为短期预测文件 {forecast_path} 生成E文本")
                else:
                    logging.warning(f"[专用预测] 为短期预测文件 {forecast_path} 生成E文本失败")
            except Exception as e_etxt:
                logging.error(f"[专用预测] 调用E文本转换时出错: {e_etxt}", exc_info=True)
            
        else:
            logging.info(f"[专用预测] 批次 {batch_id} 不符合专用预测文件生成条件，跳过")
    
    except Exception as e:
        logging.error(f"[专用预测] 生成专用预测文件时出错: {e}", exc_info=True)
# --- 辅助函数结束 ---


# --- 新增辅助函数: 计算特征平均值并生成E文件 ---
def generate_average_feature_file(interpolated_path):
    """
    基于插值后的CSV文件(C)，生成包含所有特征平均值的数据文件(E)
    
    Args:
        interpolated_path: 插值后的CSV文件路径
    """
    try:
        logging.info(f"[特征平均值] 开始处理文件 {interpolated_path} 生成平均值文件...")
        
        # 读取插值后的CSV文件
        df = pd.read_csv(interpolated_path)
        
        if df.empty:
            logging.warning(f"[特征平均值] 文件 {interpolated_path} 为空，无法生成平均值文件")
            return
        
        # 保留时间戳列
        timestamp_col = None
        if 'Timestamp' in df.columns:
            timestamp_col = df['Timestamp']
        
        # 按特征类型分组并计算平均值
        grouped_features = {}
        
        # 遍历所有列，排除时间戳列
        for col in df.columns:
            if col == 'Timestamp':
                continue
            
            # 提取特征名称，通常格式为 "特征名_纬度_经度"
            parts = col.split('_')
            if len(parts) >= 2:
                feature_name = parts[0]
                
                # 初始化特征组
                if feature_name not in grouped_features:
                    grouped_features[feature_name] = []
                
                # 添加当前列到特征组
                grouped_features[feature_name].append(col)
        
        # 创建平均值DataFrame
        avg_df = pd.DataFrame()
        
        # 添加时间戳列
        if timestamp_col is not None:
            avg_df['Timestamp'] = timestamp_col
        
        # 计算每个特征组的平均值
        for feature_name, columns in grouped_features.items():
            if columns:  # 确保有列可以计算平均值
                # 计算所有点位的平均值
                avg_df[feature_name] = df[columns].mean(axis=1)
                logging.debug(f"[特征平均值] 为特征 {feature_name} 计算了 {len(columns)} 个点位的平均值")
        
        # 构建平均值文件路径
        file_dir = interpolated_path.parent
        avg_path = file_dir / f"ECDATA_{interpolated_path.stem}.csv"
        
        # 保存平均值文件
        avg_df.to_csv(avg_path, index=False)
        logging.info(f"[特征平均值] 成功创建平均值文件: {avg_path} (特征数: {len(grouped_features)})")
        
        # 调用E文本转换函数处理气象数据
        try:
            logging.info(f"[特征平均值] 开始为气象数据文件 {avg_path} 生成E文本")
            success = ecdata2etxt.convert_csv_to_etext(
                csv_filepath=avg_path,
                data_type="weather",
                report_type=ecdata2etxt.WEATHER_DATA_CLASS_NAME
            )
            if success:
                logging.info(f"[特征平均值] 成功为气象数据文件 {avg_path} 生成E文本")
            else:
                logging.warning(f"[特征平均值] 为气象数据文件 {avg_path} 生成E文本失败")
        except Exception as e_etxt:
            logging.error(f"[特征平均值] 调用E文本转换时出错: {e_etxt}", exc_info=True)
        
    except Exception as e:
        logging.error(f"[特征平均值] 生成平均值文件时出错: {e}", exc_info=True)
# --- 辅助函数结束 ---

# --- 修改辅助函数: 从批次ID和当前时间确定年份 ---
def determine_year_from_batch_id(batch_id: str, grib_files: set = None) -> int:
    """
    根据批次ID、GRIB文件集合和当前时间确定正确的年份
    
    Args:
        batch_id: 批次ID，格式如 "MMDDHHMM"
        grib_files: 可选，GRIB文件路径集合，尝试从中提取年份
    
    Returns:
        int: 确定的年份
    """
    # 首先尝试从GRIB文件提取年份（最可靠的方法）
    if grib_files and len(grib_files) > 0:
        try:
            # 尝试打开第一个GRIB文件，获取年份
            import xarray as xr
            import os
            
            # 按照字母顺序排序文件名，获取第一个
            sorted_files = sorted(list(grib_files))
            first_file = sorted_files[0]
            
            if os.path.exists(first_file):
                logging.debug(f"从GRIB文件 {first_file} 提取年份信息")
                
                try:
                    # 尝试策略1：使用xarray直接打开
                    ds = xr.open_dataset(first_file, engine='cfgrib')
                    
                    # 尝试从valid_time或time中提取年份
                    if 'valid_time' in ds.coords:
                        year = pd.to_datetime(ds.coords['valid_time'].values[0]).year
                        logging.info(f"从GRIB文件 'valid_time' 坐标成功提取年份: {year}")
                        ds.close()
                        return year
                    elif 'time' in ds.coords:
                        year = pd.to_datetime(ds.coords['time'].values[0]).year
                        logging.info(f"从GRIB文件 'time' 坐标成功提取年份: {year}")
                        ds.close()
                        return year
                    ds.close()
                except Exception as e1:
                    logging.debug(f"使用xarray直接打开GRIB提取年份失败: {e1}")
                    
                    try:
                        # 尝试策略2：使用pygrib
                        import pygrib
                        grbs = pygrib.open(str(first_file))
                        first_message = grbs.message(1)
                        year = first_message.year
                        logging.info(f"从GRIB文件 pygrib 成功提取年份: {year}")
                        grbs.close()
                        return year
                    except Exception as e2:
                        logging.debug(f"使用pygrib提取年份失败: {e2}")
        except Exception as e:
            logging.warning(f"从GRIB文件提取年份失败: {e}")
    
    # 如果无法从文件提取，使用基于当前时间的推断逻辑
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # 从批次ID中提取月份
    if len(batch_id) >= 2:
        try:
            batch_month = int(batch_id[:2])
            
            # 处理跨年情况
            # 1. 如果批次月份是11-12月，但当前月份是1-3月，说明批次是去年的
            if batch_month >= 11 and current_month <= 3:
                logging.info(f"基于月份推断: 批次月份 {batch_month}，当前月份 {current_month}，判断为去年 {current_year-1}")
                return current_year - 1
            # 2. 如果批次月份是1-2月，但当前月份是11-12月，说明批次可能是明年的
            elif batch_month <= 2 and current_month >= 11:
                logging.info(f"基于月份推断: 批次月份 {batch_month}，当前月份 {current_month}，判断为明年 {current_year+1}")
                return current_year + 1
            # 3. 如果批次月份与当前月份相差超过6个月，需要仔细判断
            elif abs(batch_month - current_month) > 6:
                if batch_month > current_month:
                    # 如果批次月份大于当前月份且差距大于6个月，可能是去年的数据
                    logging.info(f"基于月份推断(相差>6个月): 批次月份 {batch_month}，当前月份 {current_month}，判断为去年 {current_year-1}")
                    return current_year - 1
                else:
                    # 如果批次月份小于当前月份且差距大于6个月，可能是明年的数据
                    logging.info(f"基于月份推断(相差>6个月): 批次月份 {batch_month}，当前月份 {current_month}，判断为明年 {current_year+1}")
                    return current_year + 1
        except ValueError:
            pass  # 如果无法解析月份，就使用当前年份
    
    logging.info(f"使用当前年份 {current_year} 作为批次 {batch_id} 的年份")
    return current_year

# --- GRIB 处理函数 ---
def process_batch(batch_id: str, grib_files: set):
    """处理一个完整批次的GRIB文件并生成包含所有点位的CSV，然后尝试生成特定点位的CSV"""
    logging.info(f"======== 开始处理批次: {batch_id}, 文件数: {len(grib_files)} ========")
    
    # 确定年份（更可靠的方式：同时利用GRIB文件和推断逻辑）
    year = determine_year_from_batch_id(batch_id, grib_files)
    
    # 创建批次特定的输出目录
    full_batch_id = f"{year}_{batch_id}"
    batch_output_dir = OUTPUT_DIR / full_batch_id
    batch_output_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"批次 {batch_id}: 创建/确认输出目录: {batch_output_dir}")
    
    # 在文件名中包含年份和前缀
    output_filename = batch_output_dir / f"ALL_ECMWF_Forecast_{year}_{batch_id}.csv"
    batch_archive_dir = ARCHIVE_DIR / f"{year}_{batch_id}"
    target_filtered_filename = batch_output_dir / f"ECMWF_Forecast_{year}_{batch_id}{TARGET_FILE_SUFFIX}.csv"

    # --- 检查输出文件是否已存在 ---
    main_csv_exists = output_filename.exists()
    filtered_csv_exists = target_filtered_filename.exists()

    if main_csv_exists and filtered_csv_exists:
        logging.warning(f"批次 {batch_id}: 主CSV和筛选CSV均已存在，跳过处理和归档。")
        # 注意：这里不归档，假设之前的运行已完成归档
        # 如果需要无论如何都归档，需要移除此 return 并调整后续逻辑
        return
    elif main_csv_exists and not filtered_csv_exists:
        logging.info(f"批次 {batch_id}: 主CSV已存在，但筛选CSV不存在，将尝试生成筛选CSV。")
        # 尝试基于已存在的主文件生成筛选文件
        create_filtered_point_csv(
            source_csv_path=output_filename,
            target_points_config=TARGET_POINTS,
            suffix=TARGET_FILE_SUFFIX,
            tolerance=TARGET_POINTS_TOLERANCE,
            batch_id=full_batch_id  # 传递包含年份的批次ID
        )
        # 生成筛选文件后，归档 GRIB 文件 (如果它们还在WATCH_DIR)
        logging.info(f"尝试归档批次 {batch_id} 的 GRIB 文件 (因为主CSV已存在)...")
        try:
            batch_archive_dir.mkdir(parents=True, exist_ok=True)
            for grib_file in grib_files:
                 if grib_file.exists() and grib_file.parent == WATCH_DIR: # 确保文件还在监控目录
                    try:
                        target_archive_path = batch_archive_dir / grib_file.name
                        if target_archive_path.exists():
                            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                            target_archive_path = batch_archive_dir / f"{grib_file.stem}_{timestamp}{grib_file.suffix}"
                        grib_file.rename(target_archive_path)
                    except OSError as e: logging.error(f"归档文件失败 {grib_file} -> {target_archive_path}: {e}")
                 elif not grib_file.exists():
                      logging.warning(f"尝试归档时文件已不存在: {grib_file}")
                 elif grib_file.parent != WATCH_DIR:
                      logging.warning(f"尝试归档时文件不在监控目录中: {grib_file}")

        except Exception as e: logging.error(f"归档批次 {batch_id} 文件时出错: {e}", exc_info=True)
        logging.info(f"======== 批次 {batch_id} (仅筛选/归档) 处理结束 ========")
        return # 完成任务，返回
    # 如果主CSV不存在，则继续正常处理流程

    # --- 正常处理流程开始 ---
    all_data = []
    processed_files_in_batch = set()
    found_variable_levels = defaultdict(set) # 使用 set 避免重复记录层级

    # --- GRIB 文件读取和初步处理循环 ---
    logging.info(f"批次 {batch_id}: 开始读取 GRIB 文件...")
    for grib_file in sorted(list(grib_files)):
        if not grib_file.exists():
             logging.warning(f"批次 {batch_id}: 处理时文件已不存在: {grib_file}, 跳过。")
             continue
        if grib_file in processed_files_in_batch: # 避免重复处理（理论上不应发生）
             logging.warning(f"批次 {batch_id}: 文件 {grib_file.name} 已处理过，跳过。")
             continue

        logging.info(f"批次 {batch_id}: 正在处理文件: {grib_file.name}")
        # 获取诊断信息
        diag_summary, _ = get_grib_diagnostics(grib_file)
        logging.info(f"批次 {batch_id}: 文件 {grib_file.name} 诊断摘要: {diag_summary}")

        try:
            # --- 使用多种策略尝试打开GRIB文件 ---
            ds = None
            exceptions = []
            read_successful = False

            # 策略组合尝试 (简化，优先使用分层读取，失败则尝试不分层)
            # 1. 尝试分层读取合并 (surface, heightAboveGround, etc.)
            try:
                logging.debug(f"批次 {batch_id}: 尝试策略 1 (分层读取) 文件 {grib_file.name}")
                level_types_to_check = ['surface', 'heightAboveGround', 'isobaricInhPa', 'hybrid', 'tropopause']
                merged_ds = None
                level_datasets = []

                # 清理可能的旧索引文件
                for level_type in level_types_to_check:
                    idx_path = WATCH_DIR / f"{grib_file.name}.{level_type}.idx"
                    if idx_path.exists(): idx_path.unlink()

                for level_type in level_types_to_check:
                    try:
                        level_ds = xr.open_dataset(
                            grib_file,
                            engine="cfgrib",
                            backend_kwargs={
                                'filter_by_keys': {'typeOfLevel': level_type},
                                'indexpath': '', # 让 cfgrib 自动管理
                                'errors': 'ignore' # 忽略无法解码的消息
                            },
                            # cache=False # 禁用缓存可能有助于解决某些问题，但会降低性能
                        )
                        if level_ds and len(level_ds.data_vars) > 0:
                            logging.debug(f"批次 {batch_id}: 成功读取 {level_type} 层级，变量: {list(level_ds.data_vars)}")
                            level_datasets.append(level_ds)
                            # 记录变量层级
                            for var in level_ds.data_vars: found_variable_levels[var].add(level_type)

                    except Exception as e_level:
                        # 记录读取特定层级失败，但不认为是致命错误
                        logging.debug(f"批次 {batch_id}: 读取 {level_type} 层级失败: {e_level}")
                        if "filter_by_keys" in str(e_level): # 特定错误可能指示文件不适合分层
                             logging.warning(f"批次 {batch_id}: 文件 {grib_file.name} 可能不适合按 '{level_type}' 分层读取。")


                if level_datasets:
                    # 合并找到的数据集 (优先保留第一个找到的同名变量)
                    ds = xr.merge(level_datasets, compat='override', join='outer')
                    logging.info(f"批次 {batch_id}: 策略 1 (分层读取) 成功，合并后变量数: {len(ds.data_vars)}")
                    read_successful = True
                else:
                     exceptions.append("策略 1 (分层读取): 未能从任何指定层级读取到数据。")

            except Exception as e1:
                exceptions.append(f"策略 1 (分层读取) 失败: {e1}")
                if ds: ds.close(); ds = None # 确保关闭

            # 2. 如果策略1失败，尝试不加过滤直接读取
            if not read_successful:
                try:
                    logging.debug(f"批次 {batch_id}: 尝试策略 2 (无过滤) 文件 {grib_file.name}")
                    # 清理通用索引文件
                    idx_path_generic = WATCH_DIR / f"{grib_file.name}.idx"
                    if idx_path_generic.exists(): idx_path_generic.unlink()

                    ds = xr.open_dataset(
                        grib_file,
                        engine="cfgrib",
                        backend_kwargs={
                            'indexpath': '', # 自动管理
                            'errors': 'raise' # 'raise'有助于暴露问题，但'ignore'容错性更高
                        }
                        # cache=False
                    )
                    if ds and len(ds.data_vars) > 0:
                        logging.info(f"批次 {batch_id}: 策略 2 (无过滤) 成功，变量数: {len(ds.data_vars)}")
                        read_successful = True
                        # 记录层级信息
                        for var_name, data_array in ds.data_vars.items():
                             if 'typeOfLevel' in data_array.coords:
                                 levels = np.unique(data_array['typeOfLevel'].values).tolist()
                                 for lvl in levels: found_variable_levels[var_name].add(lvl)
                             elif 'typeOfLevel' in data_array.attrs.get('GRIB_keys', {}): # 有时在属性里
                                  found_variable_levels[var_name].add(data_array.attrs['GRIB_keys']['typeOfLevel'])
                             else: # 默认认为是 surface
                                 found_variable_levels[var_name].add('surface') # 假设

                    else:
                         exceptions.append("策略 2 (无过滤): 读取成功但未找到数据变量。")

                except Exception as e2:
                    exceptions.append(f"策略 2 (无过滤) 失败: {e2}")
                    if ds: ds.close(); ds = None

            # --- 读取策略结束 ---

            if not read_successful or ds is None:
                logging.error(f"批次 {batch_id}: 无法打开或解析 GRIB 文件 {grib_file.name}。尝试的策略均失败。错误: {'; '.join(exceptions)}")
                continue # 跳过此文件

            # --- 坐标和变量名处理 ---
            logging.debug(f"批次 {batch_id}: 文件 {grib_file.name} 读取成功，开始处理坐标和变量...")
            # 重命名时间坐标
            if 'time' in ds.coords and 'valid_time' not in ds.coords:
                ds = ds.rename({'time': 'valid_time'})
            if 'step' in ds.coords and 'valid_time' not in ds.coords: # 有些文件可能只有 step
                 if 'time' in ds.coords: # 如果 time 是参考时间
                     base_time = pd.to_datetime(ds['time'].values[0])
                     # 检查 step 是否是 timedelta 类型
                     if pd.api.types.is_timedelta64_dtype(ds['step'].dtype):
                          ds['valid_time'] = ('step', base_time + ds['step'].values)
                          ds = ds.swap_dims({'step': 'valid_time'}).drop_vars(['step', 'time'], errors='ignore')
                          logging.info(f"批次 {batch_id}: 从 'time' 和 'step' 计算得到 'valid_time'。")
                     else:
                          logging.warning(f"批次 {batch_id}: 'step' 坐标不是 timedelta 类型，无法计算 'valid_time'。")
                 else:
                     logging.warning(f"批次 {batch_id}: 缺少 'time' 基准时间，无法从 'step' 计算 'valid_time'。")


            # 检查必要坐标
            required_coords = ['valid_time', 'latitude', 'longitude']
            missing_coords = [coord for coord in required_coords if coord not in ds.coords]
            if missing_coords:
                logging.error(f"批次 {batch_id}: 文件 {grib_file.name} 缺少必要坐标: {missing_coords}，无法处理。跳过。")
                ds.close()
                continue

            # 应用变量名映射
            rename_dict = {}
            current_vars = list(ds.data_vars)
            for var_name in current_vars:
                standard_name = VARIABLE_NAME_MAPPING.get(var_name)
                if standard_name and standard_name != var_name and standard_name not in ds.data_vars:
                    rename_dict[var_name] = standard_name
            if rename_dict:
                logging.info(f"批次 {batch_id}: 文件 {grib_file.name} 应用变量重命名: {rename_dict}")
                ds = ds.rename(rename_dict)

            # --- 提取数据到 DataFrame ---
            vars_to_extract = list(ds.data_vars)
            if not vars_to_extract:
                logging.warning(f"批次 {batch_id}: 文件 {grib_file.name} 处理后没有数据变量，跳过。")
                ds.close()
                continue

            logging.debug(f"批次 {batch_id}: 从 {grib_file.name} 提取变量: {vars_to_extract}")
            try:
                df = ds.to_dataframe().reset_index() # 直接转并重置索引
                logging.debug(f"批次 {batch_id}: 文件 {grib_file.name} 成功转换为 DataFrame，形状: {df.shape}")
            except Exception as e_todf:
                logging.error(f"批次 {batch_id}: 文件 {grib_file.name} 转换为 DataFrame 失败: {e_todf}", exc_info=True)
                ds.close()
                continue

            ds.close() # 及时关闭 Dataset

            # 检查转换后的 DataFrame 是否包含必要列
            if not all(col in df.columns for col in required_coords):
                 missing_after_convert = [col for col in required_coords if col not in df.columns]
                 logging.error(f"批次 {batch_id}: 文件 {grib_file.name} 转换为 DataFrame 后缺少列: {missing_after_convert}，跳过。")
                 continue

            # 清理：移除所有值都为 NaN 的列（这些通常是读取错误或空变量）
            cols_before_dropna = set(df.columns)
            df.dropna(axis=1, how='all', inplace=True)
            cols_after_dropna = set(df.columns)
            removed_cols = cols_before_dropna - cols_after_dropna
            if removed_cols:
                 logging.info(f"批次 {batch_id}: 文件 {grib_file.name} 移除了全 NaN 列: {list(removed_cols)}")


            # --- DataFrame 处理结束 ---
            if df.empty:
                 logging.warning(f"批次 {batch_id}: 文件 {grib_file.name} 处理后 DataFrame 为空。")
                 continue

            all_data.append(df)
            processed_files_in_batch.add(grib_file)
            logging.info(f"批次 {batch_id}: 文件 {grib_file.name} 处理成功并添加到数据列表。")

        except FileNotFoundError:
             # 这个异常理论上在循环开始时已处理，但再次捕获以防万一
             logging.warning(f"批次 {batch_id}: 处理文件 {grib_file} 时未找到 (FileNotFoundError)。")
        except MemoryError:
             logging.error(f"批次 {batch_id}: 处理文件 {grib_file} 时发生内存错误！尝试跳过此文件。")
             # 可以考虑在这里清理内存
             import gc; gc.collect()
        except Exception as e_ecc:
             logging.error(f"批次 {batch_id}: 处理文件 {grib_file} 时发生 eccodes 错误: {e_ecc}。跳过此文件。")
        except Exception as e:
            logging.error(f"批次 {batch_id}: 处理文件 {grib_file} 时发生未知意外错误: {e}", exc_info=True)
            # 尝试关闭可能未关闭的 xarray dataset
            try:
                if 'ds' in locals() and ds is not None: ds.close()
            except: pass
    # --- GRIB 文件读取和初步处理循环结束 ---

    if not all_data:
        logging.warning(f"批次 {batch_id}: 没有成功处理任何文件或提取任何数据。")
        # 归档未成功处理的文件
        logging.info(f"尝试归档批次 {batch_id} 的原始 GRIB 文件 (因无数据)...")
        # ... (此处省略归档逻辑，与下面失败时的归档类似) ...
        logging.info(f"======== 批次 {batch_id} (无数据) 处理结束 ========")
        return # 无数据则结束

    # --- 合并数据并保存主 CSV ---
    try:
        logging.info(f"批次 {batch_id}: 开始合并 {len(all_data)} 个 DataFrame 片段...")
        start_merge_time = time.time()
        # 使用 concat 进行堆叠
        combined_df = pd.concat(all_data, ignore_index=True)
        del all_data # 释放内存
        logging.info(f"批次 {batch_id}: 合并完成，耗时 {time.time() - start_merge_time:.2f} 秒。合并后形状: {combined_df.shape}")

        # --- 数据清理和索引设置 ---
        logging.debug(f"批次 {batch_id}: 开始数据类型转换和索引设置...")
        try:
            # 确保索引列是正确的数值和日期时间类型
            combined_df['valid_time'] = pd.to_datetime(combined_df['valid_time'])
            
            # 时区转换（如果启用）
            if CONVERT_TO_BEIJING_TIME:
                logging.info(f"批次 {batch_id}: 将时间从UTC转换为北京时间 (UTC+8)")
                try:
                    # 检查一下原始时间样本，记录到日志
                    sample_times = combined_df['valid_time'].head(5).tolist()
                    #logging.debug(f"时区转换前的UTC时间样本: {sample_times}")
                    
                    # 确保valid_time列不带时区信息（裸时间）
                    if hasattr(combined_df['valid_time'].dtype, 'tz') and combined_df['valid_time'].dtype.tz is not None:
                        combined_df['valid_time'] = combined_df['valid_time'].dt.tz_localize(None)
                        
                    # 正确方式：直接加8小时
                    combined_df['valid_time'] = combined_df['valid_time'] + pd.Timedelta(hours=8)
                    
                    # 记录转换后的样本
                    converted_sample = combined_df['valid_time'].head(5).tolist()
                    logging.debug(f"转换后的北京时间样本: {converted_sample}")
                    logging.info(f"完成时区转换：UTC -> 北京时间")
                except Exception as e:
                    logging.error(f"时区转换失败: {e}", exc_info=True)
                    # 如果转换失败，保持原样
                
                combined_df['latitude'] = pd.to_numeric(combined_df['latitude'])
            
            combined_df['longitude'] = pd.to_numeric(combined_df['longitude'])

            # 移除不需要的元数据列
            metadata_cols = ['time', 'number', 'surface', 'step']
            for col in metadata_cols:
                if col in combined_df.columns:
                    logging.info(f"批次 {batch_id}: 移除元数据列: {col}")
                    combined_df = combined_df.drop(columns=[col])

            # 设置 MultiIndex
            index_cols = ['valid_time', 'latitude', 'longitude']
            combined_df = combined_df.set_index(index_cols)

            # 按索引排序
            logging.debug(f"批次 {batch_id}: 开始排序索引...")
            start_sort_time = time.time()
            combined_df = combined_df.sort_index()
            logging.info(f"批次 {batch_id}: 索引排序完成，耗时 {time.time() - start_sort_time:.2f} 秒。")

            logging.info(f"批次 {batch_id}: 最终合并数据形状: {combined_df.shape}, 索引: {combined_df.index.names}")
            logging.debug(f"批次 {batch_id}: 包含列: {combined_df.columns.tolist()}")

        except Exception as e_idx:
             logging.error(f"批次 {batch_id}: 设置索引或排序时出错: {e_idx}", exc_info=True)
             # 即使索引失败，也尝试保存（可能没有索引）
             pass # 继续尝试保存

        # 检查关键变量 (例如 10fg6)
        if '10fg6' in combined_df.columns:
            non_nan_count = combined_df['10fg6'].notna().sum()
            logging.info(f"批次 {batch_id}: 变量 '10fg6' 存在，非 NaN 值数量: {non_nan_count}/{len(combined_df)}")
        else:
            logging.warning(f"批次 {batch_id}: 变量 '10fg6' 在最终数据中未找到!")

        # --- 保存主 CSV 文件 ---
        logging.info(f"批次 {batch_id}: 开始保存主 CSV 文件到 {output_filename}...")
        start_save_time = time.time()
        combined_df.to_csv(output_filename, index=True, na_rep='NaN') # index=True 保存 MultiIndex
        logging.info(f"批次 {batch_id}: 主 CSV 文件保存成功，耗时 {time.time() - start_save_time:.2f} 秒。")

        # --- 执行时间插值处理 (移动到这里，确保combined_df仍然有效) ---
        # interpolated_df = None
        # if INTERPOLATE_TIME and 'valid_time' in combined_df.index.names:
        #     try:
        #         logging.info(f"批次 {batch_id}: 开始时间插值处理 (间隔: {INTERPOLATION_INTERVAL_MINUTES}分钟, 方法: {INTERPOLATION_METHOD})...")
        #         interpolated_df = interpolate_time_series(
        #             combined_df,
        #             interval_minutes=INTERPOLATION_INTERVAL_MINUTES,
        #             method=INTERPOLATION_METHOD
        #         )
                
        #         if interpolated_df is not None and not interpolated_df.empty:
        #             # 构建插值文件路径 - 包含年份
        #             interpolated_path = OUTPUT_DIR / f"{year}_{output_filename.stem}{INTERPOLATED_FILE_SUFFIX}.csv"
                    
        #             logging.info(f"批次 {batch_id}: 保存插值后的数据到 {interpolated_path} (形状: {interpolated_df.shape})")
        #             # 保存插值后的数据到CSV
        #             interpolated_df.to_csv(interpolated_path, index=True)
                    
        #             # 如果启用，生成专用预测文件
        #             if GENERATE_FORECAST_FILES:
        #                 generate_forecast_file(interpolated_df, interpolated_path, f"{year}_{batch_id}")
        #         else:
        #             logging.warning(f"批次 {batch_id}: 时间插值后数据为空，跳过保存插值文件。")
        #     except Exception as e:
        #         logging.error(f"批次 {batch_id}: 执行时间插值失败: {e}", exc_info=True)

        # --- 调用点位筛选函数 ---
        if output_filename.exists() and isinstance(combined_df.index, pd.MultiIndex) and list(combined_df.index.names) == ['valid_time', 'latitude', 'longitude']:
             logging.info(f"批次 {batch_id}: 主 CSV 已生成，开始为特定点位生成筛选文件...")
             create_filtered_point_csv(
                 source_csv_path=output_filename,
                 target_points_config=TARGET_POINTS,
                 suffix=TARGET_FILE_SUFFIX,
                 tolerance=TARGET_POINTS_TOLERANCE,
                 batch_id=full_batch_id  # 传递包含年份的批次ID
             )
        elif not output_filename.exists():
             logging.error(f"批次 {batch_id}: 主 CSV 文件未能成功保存，无法进行点位筛选。")
        else:
             logging.warning(f"批次 {batch_id}: 主 CSV 索引结构不符合预期 (需要 ['valid_time', 'latitude', 'longitude']，实际为: {combined_df.index.names})，跳过点位筛选。")

    except MemoryError:
         logging.error(f"批次 {batch_id}: 合并或保存 CSV 时发生内存错误！")
         # 归档文件，因为无法完成处理
         processed_files_in_batch = set() # 标记为未处理，以便归档所有文件
    except Exception as e:
        logging.error(f"批次 {batch_id}: 合并或保存 CSV 时发生严重错误: {e}", exc_info=True)
        # 归档文件，因为无法完成处理
        processed_files_in_batch = set() # 标记为未处理，以便归档所有文件
    finally:
         # 确保释放内存
         del combined_df
         import gc; gc.collect()


    # --- 归档 GRIB 文件 ---
    logging.info(f"批次 {batch_id}: 开始归档 GRIB 文件到 {batch_archive_dir}...")
    archived_count = 0
    failed_archive_count = 0
    try:
        batch_archive_dir.mkdir(parents=True, exist_ok=True)
        # 归档所有属于这个批次的文件
        for grib_file in grib_files:
             if grib_file.exists() and grib_file.parent == WATCH_DIR: # 确保文件存在且在监控目录
                try:
                    target_archive_path = batch_archive_dir / grib_file.name
                    if target_archive_path.exists():
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                        target_archive_path = batch_archive_dir / f"{grib_file.stem}_{timestamp}{grib_file.suffix}"
                        logging.warning(f"批次 {batch_id}: 目标归档文件已存在，重命名为: {target_archive_path.name}")
                    grib_file.rename(target_archive_path)
                    archived_count += 1
                except OSError as e:
                    logging.error(f"批次 {batch_id}: 归档文件失败 {grib_file} -> {target_archive_path}: {e}")
                    failed_archive_count += 1
             elif not grib_file.exists():
                  logging.warning(f"批次 {batch_id}: 尝试归档时文件已不存在: {grib_file}")
                  failed_archive_count += 1 # 算作失败
             elif grib_file.parent != WATCH_DIR:
                  logging.warning(f"批次 {batch_id}: 文件 {grib_file} 不在监控目录中，无法归档。")
                  failed_archive_count += 1 # 算作失败
        logging.info(f"批次 {batch_id}: 归档完成。成功: {archived_count}, 失败/跳过: {failed_archive_count}")
    except Exception as e:
        logging.error(f"批次 {batch_id}: 归档过程中发生错误: {e}", exc_info=True)
    # --- 归档结束 ---


    # 记录批次处理结束时的变量层级信息
    final_var_levels_str = ", ".join([f"{var}: {list(levels)}" for var, levels in found_variable_levels.items()])
    logging.info(f"批次 {batch_id}: 最终处理发现的变量及层级: {final_var_levels_str}")

    logging.info(f"======== 批次 {batch_id} 处理结束 ========")
# --- GRIB 处理函数结束 ---


# --- Watchdog 事件处理器 ---
class NewFileHandler(FileSystemEventHandler):
    """监控文件系统事件，并将符合条件的文件添加到批处理队列"""
    def __init__(self):
        super().__init__()
        logging.info("文件监控处理器已初始化。")
        self._recently_processed = set() # 用于短暂忽略刚处理的文件事件
        self._ignore_timeout = 2 # 秒

    def _add_to_ignore(self, filepath):
        self._recently_processed.add(filepath)
        # 使用简单的延时清除（非精确，但足够）
        # import threading
        # threading.Timer(self._ignore_timeout, self._remove_from_ignore, args=[filepath]).start()
        # 注意：Timer 可能导致线程过多，简单地在 process 中检查时间可能更好

    def _remove_from_ignore(self, filepath):
         self._recently_processed.discard(filepath)

    def _is_ignored(self, filepath):
         # 简单的忽略逻辑，避免文件创建/移动过程中的重复事件
         # 在实践中， watchdog 的去重可能已经处理了大部分情况
         return filepath in self._recently_processed


    def process(self, event):
        """处理 watchdog 检测到的事件"""
        filepath_str = event.src_path if not isinstance(event, FileSystemMovedEvent) else event.dest_path
        filepath = Path(filepath_str)
        filename = filepath.name

        # 忽略目录事件和索引文件
        if event.is_directory or filename.endswith(".idx"):
            logging.debug(f"忽略事件: 目录或索引文件 {filepath}")
            return

        # 尝试忽略短时间内重复的事件 (可选优化)
        # if self._is_ignored(filepath):
        #     logging.debug(f"忽略短时间内重复处理的文件事件: {filepath}")
        #     return

        logging.debug(f"检测到事件: {event.event_type} - {filepath}")

        # 增加延迟，等待文件写入完成（对于大文件尤其重要）
        time.sleep(3) # 增加到 3 秒

        try:
            # 再次检查文件是否存在且非空
            if not filepath.exists():
                logging.warning(f"文件 {filepath} 在延迟后检查时已不存在，忽略。")
                return
            # st_size 可能在 NFS 等系统上不立即准确，但仍可作为基本检查
            if filepath.stat().st_size == 0:
                logging.warning(f"文件 {filepath} 在延迟后检查时大小为 0，忽略。")
                # 可以考虑稍后再次检查，或依赖超时机制
                return
        except FileNotFoundError:
             # 捕获 stat() 可能的 FileNotFoundError
             logging.warning(f"检查文件 {filepath} 状态时文件消失 (FileNotFoundError)，忽略。")
             return
        except OSError as e:
            # 捕获其他可能的 OS 错误 (例如权限问题)
            logging.error(f"检查文件 {filepath} 状态时发生 OS 错误: {e}，忽略此事件。")
            return
        except Exception as e:
            # 捕获未知错误
            logging.error(f"检查文件 {filepath} 状态时发生未知错误: {e}，忽略此事件。", exc_info=True)
            return


        # 匹配文件名模式
        match = FILENAME_PATTERN.match(filename)
        if match:
            batch_id = match.group(1)
            current_time = time.time()
            # 将文件添加到对应的批次
            batches_in_progress[batch_id]['files'].add(filepath)
            batches_in_progress[batch_id]['last_seen'] = current_time
            logging.info(f"文件 {filename} 添加到批次 {batch_id} (当前文件数: {len(batches_in_progress[batch_id]['files'])})")
            # self._add_to_ignore(filepath) # 添加到临时忽略列表
        else:
            logging.debug(f"忽略不匹配文件名模式的文件: {filename}")


    # 监控文件创建和移动（文件写入完成通常触发 moved 事件从临时位置）
    def on_created(self, event):
        self.process(event)

    def on_moved(self, event):
        # moved 事件有 src_path 和 dest_path
        self.process(event)
# --- Watchdog 事件处理器结束 ---


# --- 检查并触发处理 ---
def check_for_completed_batches():
    """检查是否有批次已超时（即文件已全部到达），将其移至待处理队列"""
    current_time = time.time()
    completed_batch_ids = [] # 记录在此次检查中完成的批次ID

    # 使用 list() 复制 keys，允许在迭代中安全地删除字典项
    for batch_id in list(batches_in_progress.keys()):
        batch_info = batches_in_progress[batch_id]
        time_since_last_file = current_time - batch_info['last_seen']

        # 判断是否超时
        if time_since_last_file > BATCH_COMPLETION_TIMEOUT:
            logging.info(f"批次 {batch_id} 超时 ({time_since_last_file:.1f}s > {BATCH_COMPLETION_TIMEOUT}s)，标记为待处理。文件数: {len(batch_info['files'])}")
            # 确保至少有一个文件
            if batch_info['files']:
                 # 添加到待处理队列
                 batches_to_process.append((batch_id, batch_info['files'].copy())) # 复制文件集合
                 completed_batch_ids.append(batch_id)
            else:
                 logging.warning(f"批次 {batch_id} 超时但文件列表为空，已将其移除。")

            # 从进行中字典移除已完成或空的批次
            del batches_in_progress[batch_id]

    # if completed_batch_ids:
    #     logging.info(f"本次检查完成的批次: {completed_batch_ids}")
# --- 检查并触发处理结束 ---


# --- 扫描现有文件 (脚本启动时) ---
def scan_existing_files():
    """扫描监控目录中已存在的文件，将其按批次ID分组"""
    logging.info(f"启动时扫描现有文件于 {WATCH_DIR}...")
    current_time = time.time()
    found_files_count = 0
    initial_batches = defaultdict(lambda: {'files': set(), 'last_seen': 0.0})

    try:
        for filepath in WATCH_DIR.glob("A1[SD]*"):
            # 确保是文件且非索引文件
            if filepath.is_file() and not filepath.name.endswith(".idx"):
                filename = filepath.name
                match = FILENAME_PATTERN.match(filename)
                if match:
                    batch_id = match.group(1)
                    try:
                        # 检查文件大小是否大于0
                        if filepath.stat().st_size > 0:
                            initial_batches[batch_id]['files'].add(filepath)
                            # 使用文件的最后修改时间作为参考，避免立即超时
                            file_mtime = filepath.stat().st_mtime
                            initial_batches[batch_id]['last_seen'] = max(initial_batches[batch_id]['last_seen'], file_mtime)
                            found_files_count += 1
                        else:
                            logging.warning(f"启动扫描：跳过空文件 {filepath}")
                    except FileNotFoundError:
                         logging.warning(f"启动扫描：文件 {filepath} 在检查时消失。")
                    except Exception as e:
                        logging.error(f"启动扫描：检查文件 {filepath} 时出错: {e}")

        logging.info(f"扫描完成，发现 {found_files_count} 个有效 GRIB 文件，归入 {len(initial_batches)} 个初始批次。")

        # 将扫描到的批次合并到全局状态
        # 如果批次已存在于 batches_in_progress (例如由快速启动的监控添加)，则合并文件列表
        for batch_id, batch_info in initial_batches.items():
            if batch_id in batches_in_progress:
                batches_in_progress[batch_id]['files'].update(batch_info['files'])
                # 更新 last_seen 为两者中较晚的时间
                batches_in_progress[batch_id]['last_seen'] = max(batches_in_progress[batch_id]['last_seen'], batch_info['last_seen'])
            else:
                batches_in_progress[batch_id] = batch_info

        logging.info(f"扫描后，当前进行中的批次: {list(batches_in_progress.keys())}")

        # 立即检查一次，看是否有扫描到的批次因为文件最后修改时间较早而已经超时
        logging.info("启动时检查扫描到的批次是否已完成...")
        check_for_completed_batches()

    except Exception as e:
        logging.error(f"启动扫描过程中发生错误: {e}", exc_info=True)
# --- 扫描现有文件结束 ---


# --- 主程序 ---
def main():
    """主程序入口，初始化，启动监控，处理循环"""
    logging.info("======== 启动 ECMWF 数据处理器脚本 ========")

    # --- 初始化检查和设置 ---
    try:
        # 检查并创建目录
        for dir_path in [OUTPUT_DIR, ARCHIVE_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
            logging.info(f"目录确认/创建成功: {dir_path}")
        # 检查监控目录是否存在
        if not WATCH_DIR.is_dir():
             logging.critical(f"错误：监控目录 {WATCH_DIR} 不存在或不是一个目录！脚本无法启动。")
             sys.exit(1)
        logging.info(f"监控目录: {WATCH_DIR}")
        logging.info(f"输出目录: {OUTPUT_DIR}")
        logging.info(f"归档目录: {ARCHIVE_DIR}")
        logging.info(f"日志文件: {LOG_FILE}")
        logging.info(f"目标点位配置: {TARGET_POINTS}")
    except OSError as e:
        logging.critical(f"创建目录失败: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
         logging.critical(f"初始化目录检查时发生未知错误: {e}", exc_info=True)
         sys.exit(1)

    # 清理旧索引文件
    cleanup_index_files()

    # 扫描已存在的文件
    scan_existing_files()

    # --- 设置 Watchdog 监控 ---
    event_handler = NewFileHandler()
    observer = Observer()
    try:
        observer.schedule(event_handler, str(WATCH_DIR), recursive=False) # 不监控子目录
        observer.start()
        logging.info(f"已成功启动对目录 {WATCH_DIR} 的监控。")
    except Exception as e:
        logging.critical(f"启动 Watchdog 监控失败: {e}", exc_info=True)
        sys.exit(1)


    # --- 设置信号处理 ---
    shutdown_flag = False
    def signal_handler(sig, frame):
        nonlocal shutdown_flag
        # 避免重复处理信号
        if shutdown_flag: return
        logging.info(f"接收到信号 {signal.Signals(sig).name} ({sig}), 开始优雅停止...")
        shutdown_flag = True
        # 尝试停止监控线程，但不在这里 join，在主循环外 join
        if observer.is_alive():
             observer.stop()

    # 捕获中断信号 (Ctrl+C) 和终止信号
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logging.info("信号处理器已设置 (SIGINT, SIGTERM)。")

    # --- 主处理循环 ---
    logging.info("进入主处理循环...")
    try:
        while not shutdown_flag:
            # 1. 检查是否有批次已完成（超时）
            check_for_completed_batches()

            # 2. 处理待处理队列中的批次 (一次处理一个)
            if batches_to_process:
                # 按批次ID（时间顺序）排序处理
                batches_to_process.sort(key=lambda item: item[0])
                batch_id, files_to_process = batches_to_process.pop(0) # 取出最早的批次
                logging.info(f"从队列中取出批次 {batch_id} 进行处理...")
                try:
                    process_batch(batch_id, files_to_process)
                    logging.info(f"批次 {batch_id} 处理流程执行完毕。")
                except Exception as e:
                    # 捕获 process_batch 中的顶层错误，记录并继续，防止主循环崩溃
                    logging.error(f"处理批次 {batch_id} 时发生无法捕获的顶层错误: {e}", exc_info=True)
                    # 可以在这里添加更复杂的错误处理，例如将失败批次的文件移到错误目录

            # 3. 控制循环频率，避免CPU空转
            # 如果队列为空，按正常间隔等待；如果队列非空，等待时间短一些以便快速处理下一个
            wait_time = 1 if batches_to_process else CHECK_INTERVAL
            # 使用带有超时的 join 或 sleep，以便能响应 shutdown_flag
            # time.sleep(wait_time) # 简单 sleep

            # 使用更精细的等待，以便更快响应中断信号
            wait_end_time = time.monotonic() + wait_time
            while time.monotonic() < wait_end_time and not shutdown_flag:
                 # 检查监控线程是否还在运行
                 if not observer.is_alive() and not shutdown_flag: # 如果 observer 意外停止且不是我们主动停止的
                     logging.error("错误：Watchdog observer 线程意外停止！脚本将退出。")
                     shutdown_flag = True; break # 触发退出
                 time.sleep(0.5) # 短暂睡眠

    except KeyboardInterrupt:
        # 虽然有信号处理，但以防万一直接捕获 Ctrl+C
        logging.info("检测到 KeyboardInterrupt，开始停止...")
        if not shutdown_flag: # 如果信号处理器未触发
             shutdown_flag = True
             if observer.is_alive(): observer.stop()
    except Exception as e_main_loop:
         logging.critical(f"主处理循环发生严重错误，脚本将退出: {e_main_loop}", exc_info=True)
         if not shutdown_flag: # 尝试优雅停止
              shutdown_flag = True
              if observer.is_alive(): observer.stop()
    finally:
        # --- 清理和退出 ---
        logging.info("开始执行退出清理...")

        # 停止 Watchdog observer 并等待其线程结束
        if observer.is_alive():
            logging.info("正在停止 Watchdog observer 线程...")
            observer.stop() # 再次确保调用 stop
            observer.join(timeout=10) # 等待最多10秒
            if observer.is_alive():
                logging.warning("Watchdog observer 线程未能在 10 秒内停止。")
            else:
                 logging.info("Watchdog observer 线程已停止。")
        else:
             logging.info("Watchdog observer 线程已经停止。")


        # 处理残留的进行中批次
        if batches_in_progress:
             logging.warning(f"脚本停止时，仍有 {len(batches_in_progress)} 个批次在进行中（未超时），这些批次将在下次启动时通过扫描重新处理。")
             # for batch_id, batch_info in batches_in_progress.items():
             #     logging.info(f"  - 批次 {batch_id}: {len(batch_info['files'])} 文件")

        # 处理未完成的待处理队列
        if batches_to_process:
             logging.warning(f"脚本停止时，仍有 {len(batches_to_process)} 个批次在待处理队列中，这些批次将在下次启动时通过扫描重新处理。")
             # for batch_id, files in batches_to_process:
             #     logging.info(f"  - 批次 {batch_id}: {len(files)} 文件")

        logging.info("======== ECMWF 数据处理器脚本已退出 ========")
# --- 主程序结束 ---


# --- 脚本入口点 ---
if __name__ == "__main__":
    # --- 依赖库检查 ---
    print("开始检查依赖库...")
    lib_missing = False
    libs_checked = {
        "numpy": None, "pandas": None, "xarray": None,
        "eccodes": None, "watchdog": None
    }
    try: import numpy; libs_checked["numpy"] = numpy.__version__
    except ImportError: lib_missing = True; print("错误: 缺少 numpy 库。")
    try: import pandas; libs_checked["pandas"] = pandas.__version__
    except ImportError: lib_missing = True; print("错误: 缺少 pandas 库。")
    try: import xarray; libs_checked["xarray"] = xarray.__version__
    except ImportError: lib_missing = True; print("错误: 缺少 xarray 库。")
    try:
        import eccodes
        libs_checked["eccodes"] = eccodes.codes_get_api_version()
    except ImportError:
        # 尝试检查是否安装了 ecmwflibs (它可能包含 eccodes)
        try:
            import ecmwflibs
            print("警告: 未直接找到 eccodes，但找到 ecmwflibs。假定 eccodes 可用。")
            # 无法直接获取版本号，标记为 'via_ecmwflibs'
            libs_checked["eccodes"] = 'via_ecmwflibs'
        except ImportError:
             lib_missing = True
             print("错误: 缺少 eccodes (或 ecmwflibs) 库。请安装 python-eccodes 或 ecmwflibs。")
    except Exception as e:
        lib_missing = True; print(f"错误: 初始化 eccodes 时出错: {e}")
    try: 
        import watchdog
        # watchdog没有__version__属性，因此需要使用其他方式检查
        libs_checked["watchdog"] = "已安装"
    except ImportError: lib_missing = True; print("错误: 缺少 watchdog 库。")

    # 检查 cfgrib (xarray 需要)
    try:
        import cfgrib
        # 尝试用 cfgrib 打开一个（不存在的）文件来触发引擎注册检查
        try: xr.open_dataset("dummy.grib", engine="cfgrib", errors='ignore')
        except ImportError: pass # 忽略文件不存在错误
        except ValueError as e_cfg: # 捕获引擎未注册等错误
             if "is not a valid engine" in str(e_cfg):
                 print("错误: cfgrib 引擎未成功注册到 xarray。请确保 cfgrib 安装正确。")
                 lib_missing = True
             else:
                 print(f"检查 cfgrib 引擎时发生错误: {e_cfg}") # 其他 ValueError
        except Exception: pass # 忽略其他可能的错误
        print(f"找到 cfgrib 库 (版本通常不直接报告，但存在)")
    except ImportError:
        lib_missing = True; print("错误: 缺少 cfgrib 库 (xarray 处理 GRIB 需要)。")

    print("依赖库检查完成。")
    print("库版本信息:")
    for lib, version in libs_checked.items():
        status = version if version else "未找到"
        print(f"  - {lib}: {status}")

    if lib_missing:
        print("\n错误：存在缺失的关键依赖库，脚本无法运行。请根据上面的错误信息安装所需库。")
        print("建议安装命令 (根据您的包管理器调整):")
        print("pip install numpy pandas xarray eccodes-python watchdog cfgrib")
        print("或者 conda install numpy pandas xarray python-eccodes watchdog cfgrib -c conda-forge")
        sys.exit(1)
    else:
         print("\n所有主要依赖库似乎都已安装。")
         # 开始执行主程序
         main()
# --- 脚本入口点结束 ---