from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from database_config import get_db
from models import ShortlPower, MidPower, SupershortlPower
from sqlalchemy.orm import Session
import pandas as pd  # 添加pandas导入
from db_session import db_session  # 导入上下文管理器

prediction2database_bp = Blueprint('prediction2database', __name__, url_prefix='/prediction2database')

@prediction2database_bp.route('/batch_supershortl_power', methods=['POST'])
def batch_create_supershortl_power():
    if 'file' not in request.files:
        return jsonify({"error": "未上传文件"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "空文件名"}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "仅支持CSV文件"}), 400

    try:
        # 读取CSV (宽格式，一行数据包含所有预测值)
        df = pd.read_csv(file)
        
        # 检查是否为空
        if df.empty:
            return jsonify({"error": "文件没有数据行"}), 400
            
        # 检查必要列是否存在
        required_cols = ['Timestamp']
        # 检查是否有预测字段 (wp_pred2 到 wp_pred17)
        pred_cols = [f'wp_pred{i}' for i in range(2, 18)]
        for col in required_cols:
            if col not in df.columns:
                return jsonify({"error": f"缺少必要列: {col}"}), 400
        
        # 检查是否存在至少一个预测列
        if not any(col in df.columns for col in pred_cols):
            return jsonify({"error": "未找到任何预测列 (wp_pred2 到 wp_pred17)"}), 400
        
        # 处理每一行数据 (通常应该只有一行)
        records = []
        for index, row in df.iterrows():
            record = {}
            try:
                # 处理时间戳
                record["timestamp"] = pd.to_datetime(row['Timestamp'])
                
                # 处理预测值列
                for pred_col in pred_cols:
                    if pred_col in row and not pd.isna(row[pred_col]):
                        record[pred_col] = float(row[pred_col])
                    else:
                        # 如果预测值不存在或为 NaN，设置为 0 或其他默认值
                        record[pred_col] = 0.0
                
                records.append(record)
            except (ValueError, TypeError) as e:
                current_app.logger.error(f"数据格式错误: {row} - {str(e)}")
        
        # 批量插入/更新
        with db_session() as db:
            # 记录更新和插入的计数
            updated_count = 0
            inserted_count = 0
            
            for record in records:
                # 检查是否已存在相同时间戳的记录
                existing = db.query(SupershortlPower).filter(
                    SupershortlPower.timestamp == record['timestamp']
                ).first()
                
                if existing:
                    # 更新已存在的记录
                    for key, value in record.items():
                        if key != 'timestamp':  # 不更新时间戳
                            setattr(existing, key, value)
                    updated_count += 1
                else:
                    # 插入新记录
                    db.add(SupershortlPower(**record))
                    inserted_count += 1
            
            db.commit()
            
            return jsonify({
                "total": len(records),
                "updated": updated_count,
                "inserted": inserted_count,
                "errors": 0
            }), 201
            
    except Exception as e:
        current_app.logger.error(f"文件处理失败: {str(e)}")
        return jsonify({"error": f"文件处理失败: {str(e)}"}), 500 
    
@prediction2database_bp.route('/batch_shortl_power', methods=['POST'])
def batch_create_shortl_power():
    if 'file' not in request.files:
        return jsonify({"error": "未上传文件"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "空文件名"}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "仅支持CSV文件"}), 400

    try:
        # 使用pandas读取CSV
        df = pd.read_csv(file)
        
        # 获取当前日期（不包含时间）
        current_date = pd.Timestamp.now().date()
        
        records = []
        for index, row in df.iterrows():
            try:
                # 使用pandas处理时间戳
                timestamp = pd.to_datetime(row['Timestamp'])
                records.append({
                    "timestamp": timestamp,
                    "wp_pred": float(row['Predicted Power']),
                    "pre_at": current_date,  # 使用当前日期
                    "pre_num": index + 1     # 使用行索引+1作为序号
                })
            except (ValueError, TypeError) as e:
                current_app.logger.error(f"数据格式错误: {row} - {str(e)}")
        
        # 批量插入
        with db_session() as db:
            # 检查重复时间戳
            existing_timestamps = {r['timestamp'] for r in records}
            duplicates = db.query(ShortlPower.timestamp).filter(
                ShortlPower.timestamp.in_(existing_timestamps)
            ).all()
            duplicate_set = {dt[0] for dt in duplicates}
            
            # 修改：将重复记录更新而不是跳过
            for record in records:
                if record['timestamp'] in duplicate_set:
                    # 更新已存在的记录
                    db.query(ShortlPower).filter(
                        ShortlPower.timestamp == record['timestamp']
                    ).update({
                        "wp_pred": record['wp_pred'],
                        "pre_at": record['pre_at'],
                        "pre_num": record['pre_num']
                    })
                else:
                    # 插入新记录
                    db.add(ShortlPower(**record))
            
            db.commit()
            
            return jsonify({
                "total": len(records),
                "updated": len(duplicate_set),
                "inserted": len(records) - len(duplicate_set),
                "errors": 0
            }), 201
            
    except Exception as e:
        current_app.logger.error(f"文件处理失败: {str(e)}")
        return jsonify({"error": f"文件处理失败: {str(e)}"}), 500 
    
@prediction2database_bp.route('/batch_mid_power', methods=['POST'])
def batch_create_mid_power():
    if 'file' not in request.files:
        return jsonify({"error": "未上传文件"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "空文件名"}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "仅支持CSV文件"}), 400

    try:
        # 使用pandas读取CSV
        df = pd.read_csv(file)
        
        # 修改：只获取年月日的日期
        current_date = pd.Timestamp.now().date()
        
        records = []
        for index, row in df.iterrows():
            try:
                # 使用pandas处理时间戳
                timestamp = pd.to_datetime(row['Timestamp'])
                records.append({
                    "timestamp": timestamp,
                    "wp_pred": float(row['Predicted Power']),
                    "pre_at": current_date,  # 使用修改后的current_date
                    "pre_num": index + 1     # 使用行索引+1作为序号
                })
            except (ValueError, TypeError) as e:
                current_app.logger.error(f"数据格式错误: {row} - {str(e)}")
        
        # 批量插入
        with db_session() as db:
            # 检查重复时间戳
            existing_timestamps = {r['timestamp'] for r in records}
            duplicates = db.query(MidPower.timestamp).filter(
                MidPower.timestamp.in_(existing_timestamps)
            ).all()
            duplicate_set = {dt[0] for dt in duplicates}
            
            # 修改：将重复记录更新而不是跳过
            for record in records:
                if record['timestamp'] in duplicate_set:
                    # 更新已存在的记录
                    db.query(MidPower).filter(
                        MidPower.timestamp == record['timestamp']
                    ).update({
                        "wp_pred": record['wp_pred'],
                        "pre_at": record['pre_at'],
                        "pre_num": record['pre_num']
                    })
                else:
                    # 插入新记录
                    db.add(MidPower(**record))
            
            db.commit()
            
            return jsonify({
                "total": len(records),
                "updated": len(duplicate_set),
                "inserted": len(records) - len(duplicate_set),
                "errors": 0
            }), 201
            
    except Exception as e:
        current_app.logger.error(f"文件处理失败: {str(e)}")
        return jsonify({"error": f"文件处理失败: {str(e)}"}), 500 