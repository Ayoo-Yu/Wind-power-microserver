#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zone2 本地 E-text 处理包装脚本（模拟模式）

不通过 SFTP 拉取，而是扫描本地共享卷中 Zone3 下载的 E-text 文件，
转换为 CSV 并生成预测输入文件。复用原始脚本的转换函数。
"""

import os
import sys
import re
import logging
import pandas as pd
from pathlib import Path

# 添加脚本目录到 path 以导入原始模块
sys.path.insert(0, '/opt/scripts/ecmwf_fetcher')
sys.path.insert(0, '/opt/scripts')  # 用于导入 db_config 和摄取服务

from etext2csv import convert_etext_to_csv
from fetch_data_from_c import (
    add_wind_speed_features_wide,
    add_wind_speed_features_simple,
    process_dq_csv,
    load_downloaded_state,
    save_downloaded_state,
)

# DB 摄取开关
DB_INGEST_ENABLED = os.environ.get('DB_INGEST_ENABLED', 'true').lower() == 'true'

# 多场站支持：FARM_CODES 优先，否则退回单 FARM_CODE
_raw_farm_codes = os.environ.get('FARM_CODES', '').strip()
FARM_CODES = [s.strip() for s in _raw_farm_codes.split(',') if s.strip()] if _raw_farm_codes else [os.environ.get('FARM_CODE', 'DEFAULT_FARM')]

# --- 配置 ---
LOCAL_DOWNLOAD_DIR = "/data/from_server_c"
CSV_OUTPUT_DIR = "/data/from_server_c/csv"
DAILY_PRE_CSV_DIR = "/data/daily_pre_csv"
SHORT_PRED_DIR = os.path.join(DAILY_PRE_CSV_DIR, "short")
MIDDLE_PRED_DIR = os.path.join(DAILY_PRE_CSV_DIR, "middle")
STATE_FILE = "/opt/scripts/ecmwf_fetcher/downloaded_state.txt"
TEMPLATE_FILE_PATH = os.path.join(DAILY_PRE_CSV_DIR, "example", "template_predict_input.csv")

PREDICTION_FILE_PATTERN = re.compile(r"^YCSJ_.*_C?DQYC_.*\.dat$")
WEATHER_FILE_PATTERN = re.compile(r"^YCSJ_.*_QXYC_.*\.dat$")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/ecmwf_fetcher.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("zone2-processor")


def _ingest_csv_to_db(csv_path: str, data_type: str, source_file: str):
    """将处理后的 CSV 文件摄取到数据库（为每个场站各写一份）"""
    if not DB_INGEST_ENABLED:
        return

    try:
        from db_config import get_session
        from ecmwf_ingest_service import ingest_dataframe

        df = pd.read_csv(csv_path)
        if df.empty:
            logger.warning(f"CSV is empty, skip DB ingest: {csv_path}")
            return

        for farm_code in FARM_CODES:
            db = get_session()
            try:
                count = ingest_dataframe(db, df, farm_code, data_type, source_file)
                logger.info(f"DB ingest OK: {count} rows for {farm_code} from {os.path.basename(csv_path)}")
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
    except Exception as e:
        logger.error(f"DB ingest failed for {csv_path}: {e}")
        # DB 摄取失败不影响文件处理流程


def scan_and_process():
    """扫描本地 E-text 目录，处理新文件"""
    logger.info("======== Starting local E-text scan ========")

    # 确保输出目录存在
    for d in [CSV_OUTPUT_DIR, SHORT_PRED_DIR, MIDDLE_PRED_DIR]:
        os.makedirs(d, exist_ok=True)

    downloaded_state = load_downloaded_state()
    newly_processed = set()

    download_dir = Path(LOCAL_DOWNLOAD_DIR)
    if not download_dir.exists():
        logger.warning(f"Download directory {LOCAL_DOWNLOAD_DIR} does not exist yet.")
        return

    # 扫描所有子目录（YYYY_MM格式或YYYY_MMDDHHMM格式）
    for subdir in sorted(download_dir.iterdir()):
        if not subdir.is_dir():
            continue
        if subdir.name in ('temp', 'csv'):
            continue

        logger.info(f"Scanning directory: {subdir}")

        for dat_file in sorted(subdir.glob("*.dat")):
            file_name = dat_file.name
            file_path = str(dat_file)

            is_prediction = PREDICTION_FILE_PATTERN.match(file_name)
            is_weather = WEATHER_FILE_PATTERN.match(file_name)

            if not (is_prediction or is_weather):
                continue

            if file_path in downloaded_state:
                logger.debug(f"Already processed: {file_path}")
                continue

            # 判断文件类型
            if "_CDQYC_" in file_name:
                target_subdir = "CDQ"
                file_type = "ultra-short-term"
            elif "_DQYC_" in file_name:
                target_subdir = "DQ"
                file_type = "short-term"
            elif "_QXYC_" in file_name:
                target_subdir = "QXYC"
                file_type = "weather"
            else:
                logger.warning(f"Cannot classify file: {file_name}")
                continue

            logger.info(f"Found new [{file_type}] E-text: {file_name}")

            target_csv_dir = os.path.join(CSV_OUTPUT_DIR, target_subdir)
            os.makedirs(target_csv_dir, exist_ok=True)

            # 转换 E-text → CSV
            try:
                csv_output_path = convert_etext_to_csv(
                    etext_filepath=file_path,
                    output_dir=target_csv_dir
                )
            except Exception as e:
                logger.error(f"Conversion failed for {file_path}: {e}")
                continue

            if not csv_output_path:
                logger.error(f"Conversion returned None for {file_path}")
                continue

            csv_str = str(csv_output_path)
            logger.info(f"Converted to CSV: {csv_str}")

            # 添加风速特征
            try:
                if target_subdir == "QXYC":
                    add_wind_speed_features_simple(csv_str)
                elif target_subdir in ["DQ", "CDQ"]:
                    add_wind_speed_features_wide(csv_str)
                logger.info(f"Wind speed features added: {file_name}")
            except Exception as e:
                logger.error(f"Wind speed feature failed for {csv_str}: {e}")

            # DQ文件：生成预测输入
            if target_subdir == "DQ":
                try:
                    process_dq_csv(csv_str, file_name)
                    logger.info(f"Prediction inputs generated from DQ: {file_name}")
                except Exception as e:
                    logger.error(f"DQ processing failed for {csv_str}: {e}")

            # 摄取到数据库
            _ingest_csv_to_db(csv_str, target_subdir, file_name)

            newly_processed.add(file_path)
            logger.info(f"Successfully processed: {file_name}")

    # 更新状态文件
    if newly_processed:
        updated_state = downloaded_state.union(newly_processed)
        save_downloaded_state(updated_state)
        logger.info(f"Processed {len(newly_processed)} new files.")
    else:
        logger.info("No new files to process.")

    logger.info("======== Local scan complete ========")


if __name__ == "__main__":
    scan_and_process()
