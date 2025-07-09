#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import time
import csv
import pandas as pd
import glob
import logging
from datetime import datetime, timedelta
import shutil
import numpy as np
import eccodes  # 使用eccodes库处理气象数据
import gc  # 用于手动垃圾回收
import sys  # 用于异常处理
import traceback  # 用于打印详细的异常信息

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ec_data_processing.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("EC数据处理")

# 配置参数
DATA_DIR = "/ECMWF/data_milexi"  # 数据目录
PROCESSED_DIR = "/ECMWF/processed"  # 已处理数据存放目录
OUTPUT_DIR = "/ECMWF/output"  # 输出CSV文件目录
BATCH_TIMEOUT = 10  # 批次超时时间(秒)，如果这段时间内没有新文件，则认为一个批次结束
MAX_FILES_PER_BATCH = 50  # 每批处理的最大文件数，超过则分批处理
MAX_MEMORY_PERCENT = 80  # 内存使用百分比上限，超过此值将触发垃圾回收

# 确保目录存在
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 监控内存使用的函数
def check_memory_usage():
    """检查当前内存使用情况并在必要时执行垃圾回收"""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_percent = process.memory_percent()
        if memory_percent > MAX_MEMORY_PERCENT:
            logger.warning(f"内存使用率过高: {memory_percent:.2f}%，执行垃圾回收")
            gc.collect()
            return True
    except ImportError:
        # 如果没有psutil，使用简单的垃圾回收策略
        gc.collect()
    except Exception as e:
        logger.warning(f"检查内存使用时出错: {str(e)}")
    return False

def parse_filename(filename):
    """解析文件名，提取时间和其他信息"""
    # 示例: A1S03311800040113001 -> 产品类型=A1S, 生成日期=0331, 生成时间=1800, 预报日期=0401, 预报时间=1300, 其他标识=1
    pattern = r'([A-Z0-9]+)(\d{4})(\d{4})(\d{4})(\d{4})(\d+)'
    match = re.match(pattern, filename)
    
    if not match:
        logger.warning(f"文件名格式不匹配: {filename}")
        return None
    
    try:
        product_type = match.group(1)
        gen_date = match.group(2)
        gen_time = match.group(3)
        forecast_date = match.group(4)
        forecast_time = match.group(5)
        identifier = match.group(6)
        
        # 基于文件名的结构解析日期时间
        # 例如: A1S03311800040113001
        # 生成日期: 0331 (月份=03, 日=31)
        # 生成时间: 1800 (小时=18, 分钟=00)
        # 预报日期: 0401 (月份=04, 日=01)
        # 预报时间: 1300 (小时=13, 分钟=00)
        
        # 处理生成日期时间
        gen_month = int(gen_date[:2])
        gen_day = int(gen_date[2:])
        gen_hour = int(gen_time[:2])
        gen_minute = int(gen_time[2:])
        
        # 处理预报日期时间
        # 检查预报日期格式 - 特殊处理类似 0406 这样可能表示 4月6日 的情况
        if len(forecast_date) == 4 and forecast_date.isdigit():
            # 假设格式为MMDD
            forecast_month = int(forecast_date[:2])
            forecast_day = int(forecast_date[2:])
            
            # 验证月份和日的合法性
            if 1 <= forecast_month <= 12 and 1 <= forecast_day <= 31:
                # 有效的MMDD格式
                pass
            else:
                # 尝试其他格式，例如可能是YYMM格式
                forecast_year_val = int(forecast_date[:2])
                forecast_month = int(forecast_date[2:])
                # 使用20+YY作为年份
                if 1 <= forecast_month <= 12:
                    gen_year_val = datetime.now().year // 100  # 获取当前世纪
                    forecast_year_val = gen_year_val * 100 + forecast_year_val
                    # 设置forecast_day为1
                    forecast_day = 1
        else:
            # 默认处理，假设为MMDD格式
            forecast_month = 1  # 默认1月
            forecast_day = 1    # 默认1日
            logger.warning(f"无法解析预报日期: {forecast_date}，使用默认值")
        
        # 处理预报时间
        if len(forecast_time) == 4 and forecast_time.isdigit():
            forecast_hour = int(forecast_time[:2])
            forecast_minute = int(forecast_time[2:])
        elif len(forecast_time) == 6 and forecast_time.isdigit():
            # 特殊处理6位数的情况，例如HHMMSS
            forecast_hour = int(forecast_time[:2])
            forecast_minute = int(forecast_time[2:4])
            # 忽略秒数
        else:
            forecast_hour = 0
            forecast_minute = 0
            logger.warning(f"无法解析预报时间: {forecast_time}，使用默认值")
        
        # 获取当前年份，假设文件是当前年份生成的
        current_year = datetime.now().year
        
        # 构建datetime对象
        gen_datetime = datetime(current_year, gen_month, gen_day, gen_hour, gen_minute)
        forecast_datetime = datetime(current_year, forecast_month, forecast_day, forecast_hour, forecast_minute)
        
        # 如果预报时间早于生成时间，可能是跨年预报
        if forecast_datetime < gen_datetime:
            # 预报时间推后一年
            forecast_datetime = datetime(current_year + 1, forecast_month, forecast_day, forecast_hour, forecast_minute)
        
        # 处理特殊情况：如果预报日期格式可能是YYMMDD
        if forecast_time.startswith('00') and len(forecast_date) == 6:
            try:
                # 尝试解析为YYMMDD格式
                forecast_year_val = int(forecast_date[:2]) + 2000  # 假设是21世纪
                forecast_month = int(forecast_date[2:4])
                forecast_day = int(forecast_date[4:6])
                
                # 重建预报时间对象
                if 1 <= forecast_month <= 12 and 1 <= forecast_day <= 31:
                    forecast_datetime = datetime(forecast_year_val, forecast_month, forecast_day, forecast_hour, forecast_minute)
            except ValueError:
                # 如果解析失败，保持原始处理结果
                pass
        
        return {
            "filename": filename,
            "product_type": product_type,
            "generation_datetime": gen_datetime,
            "forecast_datetime": forecast_datetime,
            "identifier": identifier
        }
        
    except (ValueError, IndexError) as e:
        # 记录错误并使用当前时间作为替代
        logger.error(f"解析文件名失败: {filename}, 错误: {str(e)}")
        current_time = datetime.now()
        
        # 尝试至少保留产品类型信息
        product_type = match.group(1) if match else "unknown"
        
        return {
            "filename": filename,
            "product_type": product_type,
            "generation_datetime": current_time,
            "forecast_datetime": current_time + timedelta(hours=24),
            "identifier": "000"
        }

def read_ec_file_with_eccodes(file_path):
    """使用eccodes读取EC数据文件并解析内容"""
    try:
        data = []
        # 确定文件类型（GRIB或BUFR）
        _, file_extension = os.path.splitext(file_path)
        is_bufr = file_extension.lower() in ['.bufr', '.bin']
        
        # 文件大小检查
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
        if file_size > 100:  # 如果文件大于100MB，记录警告
            logger.warning(f"文件{file_path}大小为{file_size:.2f}MB，处理可能需要较长时间")
        
        # 打开文件
        with open(file_path, 'rb') as f:
            # 对BUFR和GRIB文件采用不同的处理方式
            if is_bufr:
                msg_count = 0
                while True:
                    msg = eccodes.codes_bufr_new_from_file(f)
                    if msg is None:
                        break
                    
                    try:
                        msg_count += 1
                        # 每处理100个消息检查一次内存
                        if msg_count % 100 == 0:
                            check_memory_usage()
                            
                        eccodes.codes_set(msg, 'unpack', 1)  # 解包BUFR消息
                        
                        # 获取站点ID或位置信息
                        station_id = None
                        try:
                            station_id = eccodes.codes_get_string(msg, 'stationNumber')
                        except:
                            try:
                                station_id = eccodes.codes_get_string(msg, 'stationOrSiteName')
                            except:
                                try:
                                    # 如果没有站点ID，尝试使用坐标
                                    lat = eccodes.codes_get_double(msg, 'latitude')
                                    lon = eccodes.codes_get_double(msg, 'longitude')
                                    station_id = f"{lat:.3f}_{lon:.3f}"
                                except:
                                    station_id = "unknown"
                        
                        # 获取所有可用的气象要素
                        keys = []
                        values = []
                        
                        # 获取常见的气象要素
                        # 这里列出一些常见的BUFR气象要素代码，可能需要根据实际数据进行调整
                        common_keys = [
                            'airTemperature', 'dewpointTemperature', 'relativeHumidity',
                            'windSpeed', 'windDirection', 'precipitation', 'pressure',
                            'visibility', 'cloudCover', 'snowDepth'
                        ]
                        
                        for key in common_keys:
                            try:
                                value = eccodes.codes_get(msg, key)
                                keys.append(key)
                                values.append(value)
                            except:
                                pass
                        
                        # 如果找不到任何预定义的键，尝试获取所有可用键，但限制数量
                        if not keys:
                            iterator = eccodes.codes_keys_iterator_new(msg)
                            key_count = 0
                            while eccodes.codes_keys_iterator_next(iterator) and key_count < 50:  # 限制最多50个键
                                key = eccodes.codes_keys_iterator_get_name(iterator)
                                try:
                                    value = eccodes.codes_get(msg, key)
                                    if isinstance(value, (int, float, str)) and not isinstance(value, bool):
                                        keys.append(key)
                                        values.append(value)
                                        key_count += 1
                                except:
                                    pass
                            eccodes.codes_keys_iterator_delete(iterator)
                        
                        row_data = {
                            "station_id": station_id,
                            "keys": keys,
                            "values": values
                        }
                        data.append(row_data)
                        
                        # 如果数据量太大，提前返回一部分
                        if len(data) >= 10000:
                            logger.warning(f"文件{file_path}数据量过大，仅处理前10000条记录")
                            break
                    except Exception as e:
                        logger.warning(f"处理BUFR消息时出错: {str(e)}")
                    finally:
                        eccodes.codes_release(msg)
            else:
                # 处理GRIB文件
                msg_count = 0
                while True:
                    msg = eccodes.codes_grib_new_from_file(f)
                    if msg is None:
                        break
                    
                    try:
                        msg_count += 1
                        # 每处理100个消息检查一次内存
                        if msg_count % 100 == 0:
                            check_memory_usage()
                            
                        # 获取一些元数据
                        parameter = eccodes.codes_get_string(msg, 'shortName')
                        level_type = eccodes.codes_get_string(msg, 'levelType')
                        level = eccodes.codes_get_double(msg, 'level')
                        
                        # 获取网格信息 - 使用安全获取方法
                        ni = 0
                        nj = 0
                        try:
                            ni = eccodes.codes_get_long(msg, 'Ni')
                            nj = eccodes.codes_get_long(msg, 'Nj')
                        except:
                            pass
                        
                        # 获取经纬度 - 使用更安全的方法
                        try:
                            lats = np.array(eccodes.codes_get_double_array(msg, 'latitudes'))
                            lons = np.array(eccodes.codes_get_double_array(msg, 'longitudes'))
                            
                            # 获取数据值
                            values = np.array(eccodes.codes_get_double_array(msg, 'values'))
                            
                            # 如果数据量太大，采样处理
                            max_points = 10000
                            if len(values) > max_points:
                                logger.warning(f"GRIB消息包含{len(values)}个格点，将进行采样")
                                step = len(values) // max_points + 1
                                lats = lats[::step]
                                lons = lons[::step]
                                values = values[::step]
                            
                            # 对于每个格点，创建一条记录
                            for i in range(len(values)):
                                if i < len(lats) and i < len(lons):
                                    station_id = f"{lats[i]:.3f}_{lons[i]:.3f}"
                                    row_data = {
                                        "station_id": station_id,
                                        "latitude": lats[i],
                                        "longitude": lons[i],
                                        "parameter": parameter,
                                        "level_type": level_type,
                                        "level": level,
                                        "value": values[i]
                                    }
                                    data.append(row_data)
                                    
                                    # 如果数据太多，提前退出
                                    if len(data) >= 10000:
                                        logger.warning(f"文件{file_path}数据量过大，仅处理部分记录")
                                        break
                        except Exception as e:
                            logger.warning(f"处理GRIB经纬度数据时出错: {str(e)}")
                    except Exception as e:
                        logger.warning(f"处理GRIB消息时出错: {str(e)}")
                    finally:
                        eccodes.codes_release(msg)
        
        logger.info(f"成功从文件{file_path}中读取{len(data)}条记录")
        return data
    except Exception as e:
        logger.error(f"读取文件{file_path}失败: {str(e)}")
        return []

def detect_batch_completion():
    """检测一个批次的数据是否已完成接收"""
    files = glob.glob(os.path.join(DATA_DIR, "*"))
    if not files:
        return False
    
    # 检查最近一段时间内是否有新文件
    newest_file_time = max(os.path.getmtime(f) for f in files)
    time_since_last_file = time.time() - newest_file_time
    
    return time_since_last_file > BATCH_TIMEOUT

def process_batch():
    """处理一个批次的数据文件"""
    try:
        files = glob.glob(os.path.join(DATA_DIR, "*"))
        if not files:
            logger.info("没有找到需要处理的文件")
            return
        
        logger.info(f"开始处理新批次，共{len(files)}个文件")
        
        # 按生成时间分组文件
        batches = {}
        for file_path in files:
            filename = os.path.basename(file_path)
            file_info = parse_filename(filename)
            
            if not file_info:
                logger.warning(f"无法解析文件名: {filename}")
                continue
            
            # 用生成时间作为批次的键
            batch_key = file_info["generation_datetime"].strftime("%Y%m%d%H%M")
            if batch_key not in batches:
                batches[batch_key] = []
            
            batches[batch_key].append({
                "file_path": file_path,
                "file_info": file_info
            })
        
        # 处理每个批次
        for batch_key, batch_files in batches.items():
            # 如果批次太大，分批处理
            if len(batch_files) > MAX_FILES_PER_BATCH:
                logger.info(f"批次 {batch_key} 包含 {len(batch_files)} 个文件，将分批处理")
                for i in range(0, len(batch_files), MAX_FILES_PER_BATCH):
                    sub_batch = batch_files[i:i+MAX_FILES_PER_BATCH]
                    sub_batch_key = f"{batch_key}_{i//MAX_FILES_PER_BATCH+1}"
                    logger.info(f"处理子批次 {sub_batch_key}, 包含 {len(sub_batch)} 个文件")
                    process_single_batch(sub_batch_key, sub_batch)
                    # 执行垃圾回收
                    gc.collect()
            else:
                process_single_batch(batch_key, batch_files)
    except Exception as e:
        logger.error(f"处理批次时出错: {str(e)}")
        logger.error(traceback.format_exc())  # 打印详细的异常堆栈

def process_single_batch(batch_key, batch_files):
    """处理单个批次的文件"""
    try:
        logger.info(f"处理批次 {batch_key}, 共{len(batch_files)}个文件")
        
        # 收集所有数据
        all_data = []
        all_stations = set()  # 所有站点
        all_parameters = set()  # 所有参数
        all_times = set()  # 所有预报时间
        
        for file_item in batch_files:
            try:
                file_path = file_item["file_path"]
                file_info = file_item["file_info"]
                
                # 使用eccodes读取文件
                logger.info(f"开始处理文件: {file_path}")
                file_data = read_ec_file_with_eccodes(file_path)
                logger.info(f"文件 {file_path} 处理完成，获取 {len(file_data)} 条记录")
                
                # 处理文件中的每条记录
                for record in file_data:
                    # 根据记录类型处理
                    if isinstance(record, dict):
                        # 对于GRIB数据
                        if "parameter" in record:
                            station_id = record["station_id"]
                            parameter = record["parameter"]
                            forecast_time = file_info["forecast_datetime"]
                            
                            all_stations.add(station_id)
                            all_parameters.add(parameter)
                            all_times.add(forecast_time)
                            
                            all_data.append({
                                "station_id": station_id,
                                "generation_time": file_info["generation_datetime"],
                                "forecast_time": forecast_time,
                                "parameter": parameter,
                                "value": record["value"],
                                "level_type": record.get("level_type", ""),
                                "level": record.get("level", ""),
                                "latitude": record.get("latitude", ""),
                                "longitude": record.get("longitude", ""),
                                "product_type": file_info["product_type"],
                                "identifier": file_info["identifier"]
                            })
                        # 对于BUFR数据
                        elif "keys" in record and "values" in record:
                            station_id = record["station_id"]
                            keys = record["keys"]
                            values = record["values"]
                            forecast_time = file_info["forecast_datetime"]
                            
                            all_stations.add(station_id)
                            all_times.add(forecast_time)
                            
                            for i, key in enumerate(keys):
                                if i < len(values):
                                    all_parameters.add(key)
                                    all_data.append({
                                        "station_id": station_id,
                                        "generation_time": file_info["generation_datetime"],
                                        "forecast_time": forecast_time,
                                        "parameter": key,
                                        "value": values[i],
                                        "product_type": file_info["product_type"],
                                        "identifier": file_info["identifier"]
                                    })
                # 检查内存使用
                check_memory_usage()
            except Exception as e:
                logger.error(f"处理文件 {file_item['file_path']} 时出错: {str(e)}")
                logger.error(traceback.format_exc())
        
        # 转换为DataFrame并保存为CSV
        if all_data:
            logger.info(f"批次 {batch_key} 共收集 {len(all_data)} 条数据记录")
            
            # 分块处理数据，避免内存溢出
            chunk_size = 100000  # 每个CSV文件最多10万行
            num_chunks = (len(all_data) + chunk_size - 1) // chunk_size
            
            if num_chunks > 1:
                logger.info(f"数据量较大，将分为 {num_chunks} 个文件保存")
                
                for i in range(num_chunks):
                    start_idx = i * chunk_size
                    end_idx = min((i + 1) * chunk_size, len(all_data))
                    chunk_data = all_data[start_idx:end_idx]
                    
                    df = pd.DataFrame(chunk_data)
                    
                    # 输出文件名格式: EC_数据_YYYYMMDD_HHMM_部分X.csv
                    if num_chunks > 1:
                        output_filename = f"EC_数据_{batch_key}_部分{i+1}.csv"
                    else:
                        output_filename = f"EC_数据_{batch_key}.csv"
                    
                    output_path = os.path.join(OUTPUT_DIR, output_filename)
                    
                    df.to_csv(output_path, index=False, encoding='utf-8')
                    logger.info(f"已生成CSV文件: {output_path}, 包含 {len(df)} 行数据")
                    
                    # 清理内存
                    del df
                    gc.collect()
            else:
                # 数据量较小，直接保存
                df = pd.DataFrame(all_data)
                
                # 输出文件名格式: EC_数据_YYYYMMDD_HHMM.csv
                output_filename = f"EC_数据_{batch_key}.csv"
                output_path = os.path.join(OUTPUT_DIR, output_filename)
                
                df.to_csv(output_path, index=False, encoding='utf-8')
                logger.info(f"已生成CSV文件: {output_path}, 包含 {len(all_stations)} 个站点, {len(all_parameters)} 个参数, {len(all_times)} 个预报时间")
            
            # 尝试创建透视表
            try:
                if len(all_data) <= 50000:  # 只对较小的数据集创建透视表
                    # 提取最新的预报时间数据来创建透视表
                    latest_time = max(all_times)
                    latest_data = [d for d in all_data if d["forecast_time"] == latest_time]
                    if latest_data:
                        pivot_df = pd.DataFrame(latest_data)
                        pivot_table = pivot_df.pivot_table(
                            index="station_id", 
                            columns="parameter", 
                            values="value", 
                            aggfunc='first'
                        )
                        
                        # 保存透视表
                        pivot_filename = f"EC_透视表_{batch_key}.csv"
                        pivot_path = os.path.join(OUTPUT_DIR, pivot_filename)
                        pivot_table.to_csv(pivot_path, encoding='utf-8')
                        logger.info(f"已生成透视表: {pivot_path}")
                else:
                    logger.info(f"数据量过大 ({len(all_data)} 条)，跳过生成透视表")
            except Exception as e:
                logger.warning(f"生成透视表时出错: {str(e)}")
                logger.warning(traceback.format_exc())
        
        # 移动处理过的文件到已处理目录
        for file_item in batch_files:
            try:
                file_path = file_item["file_path"]
                filename = os.path.basename(file_path)
                dest_path = os.path.join(PROCESSED_DIR, filename)
                shutil.move(file_path, dest_path)
            except Exception as e:
                logger.error(f"移动文件 {file_path} 时出错: {str(e)}")
        
        logger.info(f"批次 {batch_key} 处理完成，已移动 {len(batch_files)} 个文件到已处理目录")
        
        # 强制垃圾回收
        del all_data
        gc.collect()
    except Exception as e:
        logger.error(f"处理批次 {batch_key} 时出错: {str(e)}")
        logger.error(traceback.format_exc())

def main():
    """主函数: 持续监控并处理EC数据文件"""
    logger.info("EC数据处理服务启动")
    
    try:
        while True:
            try:
                if detect_batch_completion():
                    process_batch()
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"处理过程中出错: {str(e)}")
                logger.error(traceback.format_exc())
                time.sleep(300)  # 出错后等待5分钟再继续
    except KeyboardInterrupt:
        logger.info("服务被手动停止")
    except Exception as e:
        logger.error(f"服务发生严重错误: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
