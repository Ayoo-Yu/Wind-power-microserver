#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import argparse
import os
import sys
import logging
from pathlib import Path
import re

# --- 配置项 ---
# E文本文件中的常量定义
SYSTEM_PREFIX = "<!System="
COMMENT_PREFIX = "//"
START_TAG_PREFIX = "<"
END_TAG_PREFIX = "</"
HEADER_PREFIX = "@"
DATA_PREFIX = "#"
TAB_SEPARATOR = "\t"
NAN_STRING = "NaN" # E文本中表示NaN的字符串
DEFAULT_ENCODING = "UTF-8" # E文本文件的默认编码
OUTPUT_CSV_EXTENSION = ".csv"

# 日志设置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)] # 输出到控制台
)
# --- 配置结束 ---

def parse_metadata_from_tag(tag_line):
    """尝试从开始或结束标签中解析元数据 (可选)"""
    metadata = {}
    # 简单的正则匹配 <ReportType::Entity Date='YYYY-MM-DD' Time='HH-MM-SS'>
    match = re.match(r"<([^:]+)::([^ ]+) Date='([^']+)' Time='([^']+)'", tag_line)
    if match:
        metadata['report_type'] = match.group(1)
        metadata['entity'] = match.group(2)
        metadata['date'] = match.group(3)
        metadata['time'] = match.group(4)
        # 尝试组合日期和时间
        try:
            # 注意时间格式是 HH-MM-SS，需要替换为 HH:MM:SS
            time_corrected = metadata['time'].replace('-', ':')
            metadata['datetime'] = pd.to_datetime(f"{metadata['date']} {time_corrected}")
        except Exception:
            metadata['datetime'] = None # 解析失败则为 None
    return metadata


def convert_etext_to_csv(etext_filepath, output_dir=None, output_filename=None):
    """
    将 E 文本文件转换为 CSV 文件。

    Args:
        etext_filepath (Path|str): 输入的 E 文本文件路径。
        output_dir (Path|str, optional): 保存输出 CSV 文件的目录。如果为 None，则使用输入文件所在目录。
        output_filename (str, optional): 输出 CSV 文件的名称 (不含路径)。如果为 None，则根据输入文件名生成。

    Returns:
        Path | None: 转换成功则返回输出 CSV 文件的路径，否则返回 None。
    """
    etext_filepath = Path(etext_filepath) if not isinstance(etext_filepath, Path) else etext_filepath
    if output_dir is None:
        output_dir = etext_filepath.parent
    else:
        output_dir = Path(output_dir) if not isinstance(output_dir, Path) else output_dir

    logging.info(f"开始转换 E 文本文件: {etext_filepath}")

    if not etext_filepath.is_file():
        logging.error(f"输入 E 文本文件未找到: {etext_filepath}")
        return None

    headers = None
    data_rows = []
    in_data_block = False
    line_num = 0
    metadata = {} # 存储从标签提取的元数据

    try:
        # 使用在生成时指定的编码打开文件
        with open(etext_filepath, 'r', encoding=DEFAULT_ENCODING) as infile:
            for line in infile:
                line_num += 1
                line = line.strip() # 去除首尾空白

                if not line: # 跳过空行
                    continue

                if line.startswith(SYSTEM_PREFIX):
                    logging.debug(f"L{line_num}: 忽略系统行: {line}")
                    continue
                if line.startswith(COMMENT_PREFIX):
                    logging.debug(f"L{line_num}: 忽略注释行: {line}")
                    continue

                if line.startswith(END_TAG_PREFIX):
                    if in_data_block:
                        logging.info(f"L{line_num}: 检测到数据块结束标签: {line}")
                        in_data_block = False
                        # 通常一个文件只有一个数据块，可以考虑在此处停止读取
                        # break
                    else:
                        logging.warning(f"L{line_num}: 在数据块外检测到结束标签: {line}")
                    continue

                if line.startswith(START_TAG_PREFIX) and not line.startswith(END_TAG_PREFIX) and not line.startswith(SYSTEM_PREFIX):
                    if not in_data_block:
                        logging.info(f"L{line_num}: 检测到数据块开始标签: {line}")
                        in_data_block = True
                        metadata = parse_metadata_from_tag(line)
                        if metadata:
                            logging.info(f"  - 解析到元数据: {metadata}")
                    else:
                        logging.warning(f"L{line_num}: 在数据块内检测到意外的开始标签: {line}")
                    continue

                # ---- 以下处理应在数据块内 ----
                if not in_data_block:
                    logging.debug(f"L{line_num}: 忽略数据块外的内容: {line}")
                    continue

                # 处理表头行
                if line.startswith(HEADER_PREFIX):
                    if headers is None:
                        # 移除 '@' 并按 Tab 分割
                        headers = line[len(HEADER_PREFIX):].split(TAB_SEPARATOR)
                        # 移除可能因首个TAB产生的空字符串
                        if headers and headers[0] == '':
                            headers.pop(0)
                        logging.info(f"L{line_num}: 解析到表头 ({len(headers)} 列): {headers}")
                    else:
                        logging.warning(f"L{line_num}: 在数据块内检测到重复的表头行: {line}")
                    continue

                # 处理数据行
                if line.startswith(DATA_PREFIX):
                    if headers is not None:
                        # 移除 '#' 并按 Tab 分割
                        values = line[len(DATA_PREFIX):].split(TAB_SEPARATOR)
                        # 移除可能因首个TAB产生的空字符串
                        if values and values[0] == '':
                            values.pop(0)

                        # 检查列数是否匹配
                        if len(values) == len(headers):
                            # 将 'NaN' 字符串转换回 np.nan
                            processed_values = [np.nan if v == NAN_STRING else v for v in values]
                            data_rows.append(processed_values)
                        else:
                            logging.warning(f"L{line_num}: 数据行列数 ({len(values)}) 与表头列数 ({len(headers)}) 不匹配。跳过此行。数据: {values}")
                    else:
                        logging.warning(f"L{line_num}: 在找到表头之前检测到数据行: {line}")
                    continue

                # 如果行不符合任何已知格式
                logging.warning(f"L{line_num}: 无法识别的行格式: {line}")

    except FileNotFoundError:
        logging.error(f"文件未找到: {etext_filepath}")
        return None
    except IOError as e:
        logging.error(f"读取 E 文本文件 {etext_filepath} 时发生 IO 错误: {e}", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"解析 E 文本文件 {etext_filepath} 时发生意外错误: {e}", exc_info=True)
        return None

    # --- 检查解析结果 ---
    if headers is None:
        logging.error(f"未能从文件 {etext_filepath} 中解析到表头行 (@)。")
        return None
    if not data_rows:
        logging.warning(f"未能从文件 {etext_filepath} 中解析到有效数据行 (#)。将生成空 CSV 文件。")
        # return None # 或者选择生成一个空的CSV

    # --- 创建 DataFrame ---
    try:
        logging.info(f"解析完成，共 {len(data_rows)} 行数据。正在创建 DataFrame...")
        df = pd.DataFrame(data_rows, columns=headers)

        # --- 类型转换 (重要) ---
        logging.info("尝试进行数据类型转换...")
        for col in df.columns:
            # 尝试转换为数值类型
            try:
                # 使用 pd.to_numeric，无法转换的保持原样 (或变为 NaN)
                df[col] = pd.to_numeric(df[col], errors='ignore')
                logging.debug(f"列 '{col}' 尝试转换为数值类型。")
            except Exception as e:
                logging.warning(f"转换列 '{col}' 为数值类型时出错: {e}")

            # 尝试转换 Timestamp 列为日期时间类型
            if 'timestamp' in col.lower(): # 假设时间戳列名包含 'timestamp'
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce') # 无法转换的变为 NaT
                    logging.info(f"列 '{col}' 已尝试转换为日期时间类型。")
                except Exception as e:
                    logging.warning(f"转换列 '{col}' 为日期时间类型时出错: {e}")

        logging.info(f"DataFrame 创建成功，形状: {df.shape}")
        # logging.debug(f"DataFrame dtypes:\n{df.dtypes}") # 打印类型信息
        # logging.debug(f"DataFrame head:\n{df.head()}") # 打印前几行

    except Exception as e:
        logging.error(f"创建 DataFrame 或进行类型转换时出错: {e}", exc_info=True)
        return None

    # --- 保存为 CSV ---
    try:
        # 确定输出文件名
        if output_filename is None:
            # 基于输入文件名生成，替换扩展名
            output_filename = etext_filepath.stem + OUTPUT_CSV_EXTENSION
        output_csv_path = output_dir / output_filename

        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存 CSV，不包含索引，NaN表示为空字符串 (标准CSV做法) 或 'NaN'
        df.to_csv(output_csv_path, index=False, na_rep=NAN_STRING) # 使用 na_rep='NaN' 保持一致性
        logging.info(f"成功将数据保存到 CSV 文件: {output_csv_path}")
        return output_csv_path # 返回输出文件的路径

    except IOError as e:
        logging.error(f"写入 CSV 文件 {output_csv_path} 时发生 IO 错误: {e}", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"保存 CSV 文件时发生意外错误: {e}", exc_info=True)
        return None

# --- 主程序入口 ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将 E 文本 (.dat) 文件转换为 CSV (.csv) 文件。")
    parser.add_argument("etext_file", help="输入的 E 文本文件路径。")
    parser.add_argument("-o", "--output-dir",
                        help="保存输出 CSV 文件的目录。"
                             " (默认: 与输入 E 文本文件在同一目录)")
    parser.add_argument("-n", "--output-name",
                        help="输出 CSV 文件的名称 (不含路径)。"
                             " (默认: 基于输入文件名生成)")

    args = parser.parse_args()

    output_file_path = convert_etext_to_csv(
        etext_filepath=args.etext_file,
        output_dir=args.output_dir,
        output_filename=args.output_name
    )

    if output_file_path:
        logging.info(f"转换成功完成。输出文件: {output_file_path}")
        sys.exit(0) # 成功退出
    else:
        logging.error("转换过程失败。")
        sys.exit(1) # 失败退出