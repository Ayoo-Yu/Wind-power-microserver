import pandas as pd
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import io
from datetime import datetime
import logging

from sqlalchemy import text
from db_session import db_session
from db_models.operational_data import (
    WindSpeedData,
    TurbinePowerData,
    WeatherData,
    InstalledCapacityData,
    AvailableCapacityData,
    TheoreticalPowerData,
    AvailablePowerData
)
from db_models.power import ActualPower
from services.import_job_service import import_job_store
from utils.authorization import permission_required

operational_data_upload_bp = Blueprint('operational_data_upload', __name__)

# 映射表名到模型类
OPERATIONAL_TABLE_MODEL_MAP = {
    'wind_speed_data': WindSpeedData,
    'turbine_power_data': TurbinePowerData,
    'weather_data': WeatherData,
    'installed_capacity_data': InstalledCapacityData,
    'available_capacity_data': AvailableCapacityData,
    'theoretical_power_data': TheoreticalPowerData,
    'available_power_data': AvailablePowerData,
    'actual_power': ActualPower
}

# 定义处理大文件的块大小
CHUNK_SIZE = 1000

def map_csv_to_operational_model(row_dict, model_class):
    """将CSV行字典映射到SQLAlchemy模型属性"""
    mapped_data = {}
    current_app.logger.debug(f"映射CSV行，可用列: {list(row_dict.keys())}")
    
    # 处理时间戳字段
    timestamp_val = None
    for key, value in row_dict.items():
        if key.lower() == 'timestamp':
            try:
                # 处理多种时间格式
                if isinstance(value, str):
                    # 处理 2025/7/7 17:30 格式
                    if '/' in value and len(value.split()) == 2:
                        value = value.replace('/', '-')
                        if len(value.split(':')) == 2:  # 只有小时分钟，添加秒
                            value += ':00'
                timestamp_val = pd.to_datetime(value)
                mapped_data['timestamp'] = timestamp_val
                break
            except Exception as e:
                current_app.logger.warning(f"无法解析时间戳 '{value}': {e}")
                mapped_data['timestamp'] = None
                return mapped_data
    
    if mapped_data.get('timestamp') is None:
        return mapped_data
    
    # 映射其他字段（直接映射，字段名匹配模型属性）
    for csv_col_name, value in row_dict.items():
        if csv_col_name.lower() != 'timestamp':
            # 检查模型是否有此属性
            if hasattr(model_class, csv_col_name):
                try:
                    # 根据字段类型进行转换
                    if value in [None, '', 'NULL', 'null']:
                        mapped_data[csv_col_name] = None
                    elif csv_col_name in ['id']:  # 跳过ID字段，让数据库自动生成
                        continue
                    elif csv_col_name in ['created_at']:  # 跳过created_at，让模型自动处理
                        continue
                    elif csv_col_name in ['turbine_id', 'farm_code']:
                        # 字符串ID字段
                        mapped_data[csv_col_name] = str(value) if value not in [None, ''] else None
                    elif any(csv_col_name.endswith(suffix) for suffix in ['_count', 'turbine_count', 'maintenance_turbines', 'fault_turbines']):
                        # 整数字段
                        mapped_data[csv_col_name] = int(float(value)) if value not in [None, ''] else None
                    elif any(csv_col_name.endswith(suffix) for suffix in ['_power', '_speed', '_capacity', '_rate', '_factor', '_constraint', 'temperature', 'humidity', 'pressure', 'wind_speed', 'wind_direction', 'visibility', 'precipitation', 'air_density']):
                        # 浮点数字段
                        mapped_data[csv_col_name] = float(value) if value not in [None, ''] else None
                    elif csv_col_name in ['commissioning_date']:
                        # 日期字段
                        mapped_data[csv_col_name] = pd.to_datetime(value) if value not in [None, ''] else None
                    else:
                        # 字符串字段
                        mapped_data[csv_col_name] = str(value) if value not in [None, ''] else None
                        
                except (ValueError, TypeError) as e:
                    current_app.logger.warning(f"无法转换字段 '{csv_col_name}' 的值 '{value}': {e}")
                    mapped_data[csv_col_name] = None
    
    return mapped_data


@operational_data_upload_bp.route('/api/upload_operational_csv', methods=['POST'])
@permission_required('upload_files')
def upload_operational_csv():
    """
    处理运营数据CSV文件上传，支持分块处理和批量upsert操作（支持多场站）
    """
    if 'file' not in request.files:
        return jsonify({"error": "请提供文件"}), 400

    file = request.files['file']
    table_name = request.form.get('table_name')
    farm_code = request.form.get('farm_code', '')  # 新增场站参数
    strategy = request.form.get('strategy', 'overwrite')  # fill_only 或 overwrite

    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400

    if not table_name or table_name not in OPERATIONAL_TABLE_MODEL_MAP:
        return jsonify({
            "error": f"无效或缺失的 'table_name'。必须是以下之一: {list(OPERATIONAL_TABLE_MODEL_MAP.keys())}"
        }), 400

    if strategy not in ('fill_only', 'overwrite'):
        return jsonify({"error": "strategy 参数必须是 'fill_only' 或 'overwrite'"}), 400

    if not file.filename.lower().endswith('.csv'):
        return jsonify({"error": "无效的文件类型。仅支持CSV文件。"}), 400

    TargetModel = OPERATIONAL_TABLE_MODEL_MAP[table_name]

    # 验证场站代码
    from db_models.report_config import WindFarm
    try:
        with db_session() as session:
            farm = session.query(WindFarm).filter(WindFarm.farm_code == farm_code).first()
            if not farm:
                return jsonify({"error": f"指定的场站代码 '{farm_code}' 不存在"}), 400
    except Exception as e:
        logger.warning(f"验证场站代码失败: {e}，使用默认场站")
        farm_code = ''

    total_inserted_count = 0
    total_updated_count = 0
    total_skipped_count = 0
    total_error_count = 0
    all_errors = []
    processed_chunks = 0

    try:
        # 使用pandas分块读取CSV
        chunk_iterator = pd.read_csv(file.stream, chunksize=CHUNK_SIZE, iterator=True)
        first_chunk = True

        with db_session() as session:
            for chunk_df in chunk_iterator:
                processed_chunks += 1
                current_app.logger.info(f"正在处理第 {processed_chunks} 块数据，表: {table_name}...")

                # 对第一块进行基本验证
                if first_chunk:
                    if not any(col.lower() == 'timestamp' for col in chunk_df.columns):
                        return jsonify({"error": "CSV文件必须包含 'timestamp' 列"}), 400
                    first_chunk = False

                to_insert = []
                update_candidates = {}
                chunk_timestamps_valid = []

                # 处理当前块：映射行并识别有效时间戳
                for index, row in chunk_df.iterrows():
                    original_row_dict = row.to_dict()
                    global_row_index = (processed_chunks - 1) * CHUNK_SIZE + index + 1

                    try:
                        model_data = map_csv_to_operational_model(original_row_dict, TargetModel)

                        # 添加场站信息
                        model_data['farm_code'] = farm_code

                        # 验证时间戳
                        target_timestamp = model_data.get('timestamp')
                        if target_timestamp is None or pd.isna(target_timestamp):
                            raise ValueError(f"无法解析时间戳或时间戳缺失")

                        # 过滤出有效的模型属性
                        valid_model_keys = {k for k in model_data if hasattr(TargetModel, k)}
                        filtered_model_data = {k: model_data[k] for k in valid_model_keys}

                        chunk_timestamps_valid.append(target_timestamp)
                        update_candidates[target_timestamp] = filtered_model_data

                    except Exception as e:
                        total_error_count += 1
                        err_msg = f"第 {global_row_index} 行: 映射/验证行时出错 - {str(e)}"
                        all_errors.append(err_msg)
                        current_app.logger.error(f"处理第 {global_row_index} 行时出错，表 {table_name}: {e}")

                # 检查数据库中是否存在相同时间戳的记录（考虑场站）
                existing_records_dict = {}
                if chunk_timestamps_valid:
                    try:
                        existing_records = session.query(TargetModel).filter(
                            TargetModel.timestamp.in_(chunk_timestamps_valid),
                            TargetModel.farm_code == farm_code  # 添加场站过滤条件
                        ).all()
                        existing_records_dict = {record.timestamp: record for record in existing_records}
                        current_app.logger.info(f"第 {processed_chunks} 块: 在场站 {farm_code} 的 {len(chunk_timestamps_valid)} 个有效时间戳中找到 {len(existing_records_dict)} 个现有记录")
                    except Exception as db_query_error:
                        current_app.logger.error(f"第 {processed_chunks} 块: 数据库查询失败: {db_query_error}", exc_info=True)

                # 准备批量插入列表并更新现有记录
                for timestamp, mapped_data in update_candidates.items():
                    existing_record = existing_records_dict.get(timestamp)

                    if existing_record:
                        if strategy == 'fill_only':
                            total_skipped_count += 1
                        else:
                            try:
                                for key, value in mapped_data.items():
                                    if key != 'timestamp':
                                        setattr(existing_record, key, value)
                                total_updated_count += 1
                            except Exception as update_attr_err:
                                total_error_count += 1
                                err_msg = f"更新时间戳为 {timestamp} 的现有记录属性时出错: {update_attr_err}"
                                all_errors.append(err_msg)
                                current_app.logger.error(err_msg)
                    else:
                        # 准备插入新记录
                        to_insert.append(mapped_data)

                # 执行批量插入
                if to_insert:
                    try:
                        session.bulk_insert_mappings(TargetModel, to_insert)
                        total_inserted_count += len(to_insert)
                        current_app.logger.info(f"第 {processed_chunks} 块: 批量插入了 {len(to_insert)} 条新记录")
                    except Exception as bulk_insert_err:
                        total_error_count += len(to_insert)
                        err_msg = f"第 {processed_chunks} 块: 批量插入失败: {str(bulk_insert_err)}"
                        all_errors.append(err_msg)
                        current_app.logger.error(err_msg, exc_info=True)
                        session.rollback()

            # 最终提交所有更改
            current_app.logger.info(f"完成处理表 {table_name} 的所有块（场站: {farm_code}）。总插入: {total_inserted_count}, 总更新: {total_updated_count}, 总错误: {total_error_count}")
            try:
                session.commit()
                current_app.logger.info(f"表 {table_name} 最终提交成功")

                if total_error_count == 0:
                    return jsonify({
                        "message": f"成功处理表 {table_name} 的CSV数据",
                        "farm_code": farm_code,
                        "strategy": strategy,
                        "inserted_count": total_inserted_count,
                        "updated_count": total_updated_count,
                        "skipped_count": total_skipped_count
                    }), 200
                else:
                    return jsonify({
                        "warning": f"处理表 {table_name} 的CSV数据时遇到 {total_error_count} 个错误",
                        "farm_code": farm_code,
                        "strategy": strategy,
                        "inserted_count": total_inserted_count,
                        "updated_count": total_updated_count,
                        "skipped_count": total_skipped_count,
                        "error_count": total_error_count,
                        "errors": all_errors[:50]
                    }), 207  # Multi-Status

            except Exception as commit_error:
                current_app.logger.error(f"表 {table_name} 最终提交失败: {commit_error}", exc_info=True)
                session.rollback()
                return jsonify({
                    "error": f"处理完成后提交更改失败: {commit_error}",
                    "processed_inserted_count": total_inserted_count,
                    "processed_updated_count": total_updated_count,
                    "skipped_count": total_skipped_count,
                    "error_count": total_error_count,
                    "errors": all_errors[:50]
                }), 500

    except pd.errors.EmptyDataError:
        return jsonify({"error": "CSV文件为空"}), 400
    except Exception as e:
        current_app.logger.error(f"处理表 {table_name} 的CSV上传失败: {e}", exc_info=True)
        try:
            if 'session' in locals() and session.is_active:
                session.rollback()
        except Exception as rb_err:
            current_app.logger.error(f"回滚尝试失败: {rb_err}")
            
        return jsonify({"error": f"处理过程中发生意外错误: {str(e)}"}), 500


# 获取支持的表名列表的端点
@operational_data_upload_bp.route('/api/upload_actual_power_async', methods=['POST'])
@permission_required('upload_files')
def upload_actual_power_async():
    """Create an async import job for large actual_power CSV files."""
    if 'file' not in request.files:
        return jsonify({"error": "file is required"}), 400

    file = request.files['file']
    farm_code = str(request.form.get('farm_code', '') or '').strip()
    strategy = request.form.get('strategy', 'fill_only')

    if file.filename == '':
        return jsonify({"error": "file is required"}), 400

    if strategy not in ('fill_only', 'overwrite'):
        return jsonify({"error": "strategy must be fill_only or overwrite"}), 400

    if not file.filename.lower().endswith('.csv'):
        return jsonify({"error": "only CSV files are supported"}), 400

    if not farm_code:
        return jsonify({"error": "farm_code is required"}), 400

    try:
        job = import_job_store.create_actual_power_job(file, farm_code, strategy)
        return jsonify(job.to_dict()), 202
    except Exception as e:
        current_app.logger.error(f"failed to create actual_power import job: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@operational_data_upload_bp.route('/api/import_jobs/<job_id>', methods=['GET'])
@permission_required('upload_files')
def get_import_job(job_id):
    """Return async import job progress."""
    job = import_job_store.get_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    response = jsonify(job.to_dict())
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response, 200


@operational_data_upload_bp.route('/api/operational_tables', methods=['GET'])
@permission_required('upload_files')
def get_operational_tables():
    """返回支持的运营数据表名列表及其描述"""
    tables_info = {
        'wind_speed_data': '单机风速数据',
        'turbine_power_data': '单机功率数据',
        'weather_data': '气象信息数据',
        'installed_capacity_data': '装机容量数据',
        'available_capacity_data': '可用容量数据',
        'theoretical_power_data': '理论功率数据',
        'available_power_data': '可用功率数据',
        'actual_power': '实际功率数据'
    }
    
    return jsonify({
        "supported_tables": list(OPERATIONAL_TABLE_MODEL_MAP.keys()),
        "table_descriptions": tables_info
    }), 200


# 获取特定表的字段信息
@operational_data_upload_bp.route('/api/operational_table_schema/<table_name>', methods=['GET'])  
@permission_required('upload_files')
def get_table_schema(table_name):
    """返回指定表的字段信息，用于CSV格式参考"""
    if table_name not in OPERATIONAL_TABLE_MODEL_MAP:
        return jsonify({
            "error": f"不支持的表名。支持的表: {list(OPERATIONAL_TABLE_MODEL_MAP.keys())}"
        }), 400
    
    model_class = OPERATIONAL_TABLE_MODEL_MAP[table_name]
    
    # 获取模型的列信息
    columns_info = {}
    for column in model_class.__table__.columns:
        col_info = {
            "type": str(column.type),
            "nullable": column.nullable,
            "primary_key": column.primary_key
        }
        if hasattr(column, 'comment') and column.comment:
            col_info["comment"] = column.comment
        columns_info[column.name] = col_info
    
    return jsonify({
        "table_name": table_name,
        "columns": columns_info
    }), 200 
