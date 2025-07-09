#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import datetime
import argparse
import os
import sys
import logging
from pathlib import Path

# --- E文本格式配置 ---
# 这些值将作为默认值，但可以通过函数参数覆盖
DEFAULT_STATION_TYPE = "YCSJ"  
DEFAULT_REGION = "YN"        # 示例: YN 代表云南 (假设竹园西在此省)
DEFAULT_STATION_NAME = "ZhuYXDC" # 与你的目标点位名称匹配

# E文本系统声明行细节
DEFAULT_SYSTEM = "OMS"
DEFAULT_VERSION = "1.0"
DEFAULT_CODE = "UTF-8"
DEFAULT_DATA_VERSION = "1.0"

# 报表类型 / 类名 (从CSV文件名推断)
SHORT_TERM_CLASS_NAME = "CDQYC" # 示例: 气象预测_短期 (Weather Forecast Short Term)
MID_TERM_CLASS_NAME = "DQYC"   # 示例: 气象预测_中期 (Weather Forecast Mid Term)
WEATHER_DATA_CLASS_NAME = "QXYC" # 气象数据集_数据聚合 (Weather Data Aggregated)

# E文本常量
TAB_SEPARATOR = "\t"
NEWLINE = "\n"
ETEXT_FILE_EXTENSION = ".dat"

# --- 日志设置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)] # 输出到控制台
)
# --- 配置结束 ---

def generate_e_text_filename(station_type, region, station_name, report_type, data_timestamp=None):
    """
    根据约定生成E文本文件名
    
    Args:
        station_type: 电站类型代码
        region: 地区代码
        station_name: 电站名称
        report_type: 报表类型
        data_timestamp: 数据时间戳，如果为None则使用当前时间
    """
    if data_timestamp is None:
        now = datetime.datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S") # 文件生成时间戳
    else:
        # 使用数据时间戳
        timestamp_str = data_timestamp.strftime("%Y%m%d_%H%M%S")
    
    entity_part = f"{region}.{station_name}" # 实体部分
    filename = f"{station_type}_{entity_part}_{report_type}_{timestamp_str}{ETEXT_FILE_EXTENSION}"
    return filename

def convert_csv_to_etext(csv_filepath, output_dir=None, 
                        station_type=DEFAULT_STATION_TYPE, 
                        region=DEFAULT_REGION, 
                        station_name=DEFAULT_STATION_NAME,
                        system=DEFAULT_SYSTEM,
                        version=DEFAULT_VERSION,
                        code=DEFAULT_CODE,
                        data_version=DEFAULT_DATA_VERSION,
                        report_type=None,
                        data_type="forecast"):
    """
    将CSV文件转换为E文本格式。

    Args:
        csv_filepath (Path|str): 输入CSV文件的路径。
        output_dir (Path|str, optional): 保存输出E文本文件的目录。如果为None，则使用输入文件所在目录。
        station_type (str): 电站类型代码 (例如 'QX', 'YCSJ')。
        region (str): 地区代码 (例如 'YN')。
        station_name (str): 电站名称 (例如 'ZhuYuanXi')。
        system (str): E文本系统声明。
        version (str): E文本版本。
        code (str): E文本编码。
        data_version (str): 数据版本。
        report_type (str, optional): 报表类型/类名。如果为None，则从文件名推断。
        data_type (str): 数据类型，"forecast"表示预测数据D，"weather"表示气象数据E。

    Returns:
        bool: 转换成功返回 True，否则返回 False。
    """
    # 转换输入参数为Path对象
    csv_filepath = Path(csv_filepath) if not isinstance(csv_filepath, Path) else csv_filepath
    if output_dir is None:
        output_dir = csv_filepath.parent
    else:
        output_dir = Path(output_dir) if not isinstance(output_dir, Path) else output_dir
    
    logging.info(f"开始转换文件: {csv_filepath}")

    if not csv_filepath.is_file():
        logging.error(f"输入 CSV 文件未找到: {csv_filepath}")
        return False

    # --- 从文件名确定报表类型 (类名) ---
    if report_type is None:
        filename_stem = csv_filepath.stem # 获取不带扩展名的文件名
        if data_type == "forecast":
            if "_short_term" in filename_stem:
                report_type = SHORT_TERM_CLASS_NAME
                logging.info(f"检测到报表类型: 短期 ({report_type})")
            elif "_mid_term" in filename_stem:
                report_type = MID_TERM_CLASS_NAME
                logging.info(f"检测到报表类型: 中期 ({report_type})")
            else:
                logging.error(f"无法从文件名推断报表类型 (短期/中期): {csv_filepath.name}")
                logging.error("文件名必须包含 '_short_term' 或 '_mid_term'.")
                return False
        elif data_type == "weather":
            report_type = WEATHER_DATA_CLASS_NAME
            logging.info(f"使用气象数据报表类型: {report_type}")
        else:
            logging.error(f"不支持的数据类型: {data_type}")
            return False
    else:
        logging.info(f"使用指定的报表类型: {report_type}")

    # --- 构建 E文本 实体名称 ---
    entity_name = f"{region}.{station_name}" # 例如 "YN.ZhuYuanXi"

    # --- 读取 CSV 数据 ---
    try:
        df = pd.read_csv(csv_filepath)
        logging.info(f"成功读取 CSV: {csv_filepath.name} (数据形状: {df.shape})")
        if df.empty:
            logging.warning(f"CSV 文件为空: {csv_filepath.name}。跳过 E文本 生成。")
            return False # 表示因空文件跳过
    except pd.errors.EmptyDataError:
        logging.warning(f"CSV 文件为空: {csv_filepath.name}。跳过 E文本 生成。")
        return False # 表示因空文件跳过
    except Exception as e:
        logging.error(f"读取 CSV 文件 {csv_filepath.name} 时出错: {e}", exc_info=True)
        return False

    # --- 从 CSV 提取预报起始日期/时间 ---
    # 假设 CSV 文件中的 'Timestamp' 列的第一行即为预报起始时间
    # 假设 CSV 中的时间戳已经是所需时区（例如北京时间），只需格式化
    if 'Timestamp' not in df.columns:
        logging.error(f"必需的 'Timestamp' 列在 {csv_filepath.name} 中未找到。")
        return False

    try:
        # 将时间戳字符串转换为 datetime 对象
        first_timestamp_str = str(df['Timestamp'].iloc[0])
        try:
            first_timestamp = pd.to_datetime(first_timestamp_str)
        except ValueError:
            # 如果有其他可能的格式，可以在这里添加解析尝试
            logging.error(f"无法解析第一个时间戳: '{first_timestamp_str}'。请确保它是可识别的日期/时间格式。")
            return False

        # 格式化为 E文本 头部所需的格式 (YYYY-MM-DD 和 HH-MM-SS)
        data_date_str = first_timestamp.strftime('%Y-%m-%d')
        data_time_str = first_timestamp.strftime('%H-%M-%S') # 根据 ZTXX 示例使用连字符
        logging.info(f"提取用于 E文本 头部的数据日期/时间: {data_date_str} {data_time_str}")

    except IndexError:
        logging.warning(f"CSV 文件 {csv_filepath.name} 似乎没有数据行可供提取时间戳。")
        return False # 没有数据时间无法继续
    except Exception as e:
        logging.error(f"处理来自 {csv_filepath.name} 的时间戳时出错: {e}", exc_info=True)
        return False

    # --- 生成输出文件名 ---
    output_filename = generate_e_text_filename(station_type, region, station_name, report_type, first_timestamp)
    output_filepath = output_dir / output_filename # 构造完整输出路径
    logging.info(f"E文本 输出路径: {output_filepath}")

    # --- 构建 E文本 内容 ---
    e_text_content = []

    # 1. 系统声明行
    system_line = f"<!System={system} Version={version} Code={code} Data={data_version}!>"
    e_text_content.append(system_line)

    # 2. 可选注释行
    data_type_desc = "预测" if data_type == "forecast" else "气象"
    e_text_content.append(f"// {report_type} {data_type_desc}数据 (实体: {entity_name})")

    # 3. 数据块开始标签
    start_tag = f"<{report_type}::{entity_name} Date='{data_date_str}' Time='{data_time_str}'>"
    e_text_content.append(start_tag)

    # 4. 列名行 (@)
    # 直接使用 CSV 的表头
    headers = df.columns.tolist()
    header_line = "@" + TAB_SEPARATOR + TAB_SEPARATOR.join(headers)
    e_text_content.append(header_line)

    # 5. 数据行 (#)
    logging.info(f"开始处理 {len(df)} 行数据...")
    for index, row in df.iterrows():
        # 将行内所有值转换为字符串，并显式处理 NaN
        # 使用 'NaN' 字符串，与生成器中的 na_rep='NaN' 保持一致
        str_row = [str(value) if pd.notna(value) else 'NaN' for value in row]
        data_line = "#" + TAB_SEPARATOR + TAB_SEPARATOR.join(str_row)
        e_text_content.append(data_line)

    # 6. 数据块结束标签
    end_tag = f"</{report_type}::{entity_name}>"
    e_text_content.append(end_tag)

    # --- 写入 E文本 文件 ---
    try:
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_filepath, mode='w', encoding=code) as outfile:
            # 写入内容，并确保文件末尾有换行符
            outfile.write(NEWLINE.join(e_text_content) + NEWLINE)
        logging.info(f"成功生成 E文本 文件: {output_filepath}")
        return True
    except IOError as e:
        logging.error(f"写入 E文本 文件 {output_filepath} 时发生 IO 错误: {e}", exc_info=True)
        return False
    except Exception as e:
        logging.error(f"文件写入期间发生意外错误: {e}", exc_info=True)
        return False

# --- 主程序入口 ---
if __name__ == "__main__":
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description="将特定的 ECMWF 预测 CSV 文件转换为 E文本 格式。")
    parser.add_argument("csv_file", help="输入的预测 CSV 文件路径 (_short_term.csv 或 _mid_term.csv)")
    parser.add_argument("-o", "--output-dir",
                        help="保存输出 E文本 (.dat) 文件的目录。"
                             " (默认: 与输入 CSV 文件在同一目录)")
    parser.add_argument("--station-type", default=DEFAULT_STATION_TYPE,
                        help=f"E文本 电站类型代码 (默认: {DEFAULT_STATION_TYPE})")
    parser.add_argument("--region", default=DEFAULT_REGION,
                        help=f"E文本 地区代码 (默认: {DEFAULT_REGION})")
    parser.add_argument("--station-name", default=DEFAULT_STATION_NAME,
                        help=f"E文本 电站名称 (默认: {DEFAULT_STATION_NAME})")
    parser.add_argument("--data-type", default="forecast", choices=["forecast", "weather"],
                        help="数据类型: forecast=预测数据, weather=气象数据 (默认: forecast)")

    args = parser.parse_args()

    input_csv_path = Path(args.csv_file) # 将输入路径转为 Path 对象

    # 确定输出目录
    if args.output_dir:
        output_directory = Path(args.output_dir)
    else:
        # 默认为输入 CSV 文件所在的目录
        output_directory = input_csv_path.parent
        logging.info(f"未指定输出目录，将使用输入 CSV 所在目录: {output_directory}")

    # 执行转换
    success = convert_csv_to_etext(
        csv_filepath=input_csv_path,
        output_dir=output_directory,
        station_type=args.station_type,
        region=args.region,
        station_name=args.station_name,
        data_type=args.data_type
    )

    # 根据转换结果退出
    if success:
        logging.info("转换过程成功完成。")
        sys.exit(0) # 成功退出
    else:
        logging.error("转换过程失败。")
        sys.exit(1) # 失败退出