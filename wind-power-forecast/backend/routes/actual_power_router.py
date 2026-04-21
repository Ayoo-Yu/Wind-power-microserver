from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from database_config import get_db
from models import ActualPower
from sqlalchemy.orm import Session
import pandas as pd  # 添加pandas导入
from db_session import db_session  # 导入上下文管理器

actual_power_bp = Blueprint('actual_power', __name__, url_prefix='/actual_power')

# 定义分块大小
CHUNK_SIZE = 10000  # 每次处理2000行数据

@actual_power_bp.route('/', methods=['POST'])
def create_actual_power():
    data = request.get_json()
    
    # 检查 'Timestamp' 是否存在。 'wp_true' 可以不存在或为 null。
    if not data or 'Timestamp' not in data:
        return jsonify({"error": "缺少必要参数: Timestamp"}), 400

    wp_true_input = data.get('wp_true') # 使用 .get() 获取，如果键不存在则为 None
    farm_code = str(data.get('farm_code', '') or '').strip() or 'DEFAULT_FARM'

    processed_wp_true = None # 默认值，如果 wp_true_input 是 None 或无效，则存为 NULL

    if wp_true_input is not None: # 如果 'wp_true' 键存在且值不是 JSON null
        if isinstance(wp_true_input, str):
            if wp_true_input.lower() == 'nan':
                # 字符串 "NaN" 也处理为 None (数据库 NULL)
                processed_wp_true = None
            else:
                try:
                    processed_wp_true = float(wp_true_input)
                except ValueError:
                    return jsonify({"error": f"wp_true 值 '{wp_true_input}' 无法转换为有效的数字或识别为NaN"}), 400
        elif isinstance(wp_true_input, (int, float)):
            # 优化：只转换一次float
            val_float = float(wp_true_input)
            if pd.isna(val_float):
                processed_wp_true = None # 将 float('nan') 也统一处理为数据库 NULL
            else:
                processed_wp_true = val_float
        else:
            # 如果类型不是 None, str, int, float
            return jsonify({"error": "wp_true 必须是数字、null、或字符串 'NaN'"}), 400
    
    # 到这里，processed_wp_true 要么是一个有效的浮点数，要么是 None (将被存为数据库 NULL)

    try:
        timestamp_dt = datetime.fromisoformat(data['Timestamp'])
    except ValueError:
        current_app.logger.error(f"时间戳格式错误: {data.get('Timestamp')}")
        return jsonify({"error": "时间戳格式错误，请使用ISO 8601格式"}), 400

    try:
        with db_session() as db:
            # 检查时间戳是否已存在
            existing = db.query(ActualPower).filter(
                ActualPower.timestamp == timestamp_dt,
                ActualPower.farm_code == farm_code
            ).first()
            
            if existing:
                # 更新现有记录
                existing.wp_true = processed_wp_true
                db.commit()
                
                return jsonify({
                    "id": existing.id,
                    "timestamp": existing.timestamp.isoformat(),
                    "farm_code": existing.farm_code,
                    "wp_true": existing.wp_true,
                    "action": "updated"
                }), 200
            else:
                # 创建新记录
                db_record = ActualPower(
                    timestamp=timestamp_dt,
                    farm_code=farm_code,
                    wp_true=processed_wp_true
                )
                
                db.add(db_record)
                db.commit()
                
                # 返回时，如果 wp_true 是 None (数据库中是 NULL), JSON 中会是 null
                return jsonify({
                    "id": db_record.id,
                    "timestamp": db_record.timestamp.isoformat(),
                    "farm_code": db_record.farm_code,
                    "wp_true": db_record.wp_true,
                    "action": "created"
                }), 201
            
    except Exception as e:
        current_app.logger.error(f"数据存储失败: {e}")
        # 如果 db_session 实现了自动回滚，则不需要手动 rollback
        # 否则可能需要 db.rollback()
        return jsonify({"error": "数据存储失败，请稍后重试"}), 500

def process_wp_true_value(wp_true_input, row_index=None):
    """处理wp_true值的通用函数"""
    if wp_true_input is None or pd.isna(wp_true_input):
        return None
    
    if isinstance(wp_true_input, str):
        if wp_true_input.lower() == 'nan':
            return None
        try:
            return float(wp_true_input)
        except ValueError:
            raise ValueError(f"wp_true值 '{wp_true_input}' 无法转换为有效的数字")
    elif isinstance(wp_true_input, (int, float)):
        val_float = float(wp_true_input)
        if pd.isna(val_float):
            return None
        return val_float
    else:
        raise ValueError(f"wp_true类型无效: {type(wp_true_input)}")

@actual_power_bp.route('/batch', methods=['POST'])
def batch_create_actual_power():
    if 'file' not in request.files:
        return jsonify({"error": "未上传文件"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "空文件名"}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "仅支持CSV文件"}), 400

    batch_farm_code = str(request.form.get('farm_code', '') or '').strip() or 'DEFAULT_FARM'

    total_inserted_count = 0
    total_updated_count = 0
    total_error_count = 0
    total_processed_rows = 0
    total_skipped_intra_batch_duplicates = 0
    all_errors = []
    processed_chunks = 0

    try:
        # 使用分块迭代器处理大文件
        chunk_iterator = pd.read_csv(file.stream, chunksize=CHUNK_SIZE, iterator=True)
        first_chunk = True

        with db_session() as session:
            for chunk_df in chunk_iterator:
                processed_chunks += 1
                current_app.logger.info(f"处理第 {processed_chunks} 个数据块，包含 {len(chunk_df)} 行数据...")

                # 首次验证必要列是否存在
                if first_chunk:
                    if 'Timestamp' not in chunk_df.columns:
                        return jsonify({"error": "CSV文件缺少必要的'Timestamp'列"}), 400
                    
                    if 'wp_true' not in chunk_df.columns:
                        current_app.logger.warning("CSV文件缺少'wp_true'列，所有值将被设置为NULL")
                    
                    first_chunk = False

                # 处理当前数据块
                chunk_records = []
                chunk_errors = 0
                
                for index, row in chunk_df.iterrows():
                    global_row_index = (processed_chunks - 1) * CHUNK_SIZE + index + 1
                    try:
                        # 处理时间戳
                        try:
                            timestamp = pd.to_datetime(row['Timestamp'])
                        except Exception as e:
                            chunk_errors += 1
                            error_msg = f"行 {global_row_index}: 时间戳格式错误 '{row.get('Timestamp', 'N/A')}' - {str(e)}"
                            all_errors.append(error_msg)
                            current_app.logger.error(error_msg)
                            continue
                        
                        # 处理wp_true值
                        wp_true_input = row.get('wp_true') if 'wp_true' in chunk_df.columns else None
                        try:
                            processed_wp_true = process_wp_true_value(wp_true_input, global_row_index)
                        except ValueError as e:
                            chunk_errors += 1
                            error_msg = f"行 {global_row_index}: {str(e)}"
                            all_errors.append(error_msg)
                            current_app.logger.error(error_msg)
                            continue
                        
                        row_farm_code = str(row.get('farm_code', '') or '').strip() if 'farm_code' in chunk_df.columns else ''
                        chunk_records.append({
                            "timestamp": timestamp,
                            "farm_code": row_farm_code or batch_farm_code,
                            "wp_true": processed_wp_true
                        })
                        
                    except Exception as e:
                        chunk_errors += 1
                        error_msg = f"行 {global_row_index}: 数据处理错误 - {str(e)}"
                        all_errors.append(error_msg)
                        current_app.logger.error(error_msg)

                total_error_count += chunk_errors
                total_processed_rows += len(chunk_df)

                if not chunk_records:
                    current_app.logger.warning(f"数据块 {processed_chunks} 中没有有效记录，跳过...")
                    continue

                # 处理数据块内部的重复时间戳（按 timestamp+farm_code 组合去重）
                seen_timestamps_in_chunk = {}
                chunk_skipped_duplicates = 0

                for record in chunk_records:
                    key = (record['timestamp'], record['farm_code'])
                    if key in seen_timestamps_in_chunk:
                        chunk_skipped_duplicates += 1
                        current_app.logger.warning(f"数据块内重复记录，使用最新值: {record['timestamp'].isoformat()} farm={record['farm_code']}")
                    seen_timestamps_in_chunk[key] = record
                
                total_skipped_intra_batch_duplicates += chunk_skipped_duplicates
                unique_chunk_records = list(seen_timestamps_in_chunk.values())

                # 查询数据库中已存在的记录
                chunk_timestamps = [r['timestamp'] for r in unique_chunk_records]
                chunk_farm_codes = list(set(r['farm_code'] for r in unique_chunk_records))
                existing_records = session.query(ActualPower).filter(
                    ActualPower.timestamp.in_(chunk_timestamps),
                    ActualPower.farm_code.in_(chunk_farm_codes)
                ).all()

                existing_timestamp_map = {(record.timestamp, record.farm_code): record for record in existing_records}

                # 分离需要插入和更新的记录
                records_to_insert = []
                records_to_update = []
                
                for record in unique_chunk_records:
                    key = (record['timestamp'], record['farm_code'])
                    if key in existing_timestamp_map:
                        # 更新现有记录
                        existing_record = existing_timestamp_map[key]
                        existing_record.wp_true = record['wp_true']
                        records_to_update.append(existing_record)
                    else:
                        # 准备插入新记录
                        records_to_insert.append(record)

                # 执行批量操作
                try:
                    if records_to_insert:
                        session.bulk_insert_mappings(ActualPower, records_to_insert)
                        total_inserted_count += len(records_to_insert)
                        current_app.logger.info(f"数据块 {processed_chunks}: 批量插入 {len(records_to_insert)} 条新记录")
                    
                    if records_to_update:
                        total_updated_count += len(records_to_update)
                        current_app.logger.info(f"数据块 {processed_chunks}: 更新 {len(records_to_update)} 条现有记录")
                    
                    # 提交当前数据块的更改
                    session.commit()
                    current_app.logger.info(f"数据块 {processed_chunks} 处理完成并提交")
                    
                except Exception as e:
                    session.rollback()
                    chunk_error_msg = f"数据块 {processed_chunks} 数据库操作失败: {str(e)}"
                    all_errors.append(chunk_error_msg)
                    current_app.logger.error(chunk_error_msg)
                    total_error_count += len(unique_chunk_records)

            # 处理完成，返回结果
            current_app.logger.info(f"文件处理完成。总计: 插入 {total_inserted_count}, 更新 {total_updated_count}, 错误 {total_error_count}")
            
            if total_error_count == 0:
                return jsonify({
                    "message": "文件处理成功",
                    "total_csv_rows": total_processed_rows,
                    "processed_chunks": processed_chunks,
                    "inserted": total_inserted_count,
                    "updated": total_updated_count,
                    "skipped_intra_batch_duplicates": total_skipped_intra_batch_duplicates
                }), 200
            else:
                return jsonify({
                    "warning": f"文件处理完成，但有 {total_error_count} 个错误",
                    "total_csv_rows": total_processed_rows,
                    "processed_chunks": processed_chunks,
                    "inserted": total_inserted_count,
                    "updated": total_updated_count,
                    "skipped_intra_batch_duplicates": total_skipped_intra_batch_duplicates,
                    "error_count": total_error_count,
                    "errors": all_errors[:50]  # 限制返回的错误数量
                }), 207  # Multi-Status

    except pd.errors.EmptyDataError:
        return jsonify({"error": "CSV文件为空"}), 400
    except Exception as e:
        current_app.logger.error(f"文件处理失败: {str(e)}", exc_info=True)
        return jsonify({"error": "文件处理失败，请检查数据格式后重试"}), 500 