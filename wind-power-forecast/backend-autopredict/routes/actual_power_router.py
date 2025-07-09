from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from database_config import get_db
from models import ActualPower
from sqlalchemy.orm import Session
import pandas as pd  # 添加pandas导入
from db_session import db_session  # 导入上下文管理器

actual_power_bp = Blueprint('actual_power', __name__, url_prefix='/actual_power')

@actual_power_bp.route('/', methods=['POST'])
def create_actual_power():
    data = request.get_json()
    if not data or 'Timestamp' not in data or 'wp_true' not in data:
        return jsonify({"error": "缺少必要参数"}), 400
    
    try:
        with db_session() as db:
            # 检查时间戳是否已存在
            existing = db.query(ActualPower).filter(
                ActualPower.timestamp == datetime.fromisoformat(data['Timestamp'])
            ).first()
            
            if existing:
                return jsonify({
                    "error": f"时间戳 {data['Timestamp']} 已存在"
                }), 400
                
            db_record = ActualPower(
                timestamp=datetime.fromisoformat(data['Timestamp']),
                wp_true=data['wp_true']
            )
            
            db.add(db_record)
            db.commit()
            return jsonify({
                "id": db_record.id,
                "timestamp": db_record.timestamp.isoformat(),
                "wp_true": db_record.wp_true
            }), 201
            
    except ValueError as e:
        return jsonify({"error": "时间戳格式错误，请使用ISO 8601格式"}), 400
    except Exception as e:
        return jsonify({"error": f"数据存储失败: {str(e)}"}), 500

@actual_power_bp.route('/batch', methods=['POST'])
def batch_create_actual_power():
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
        
        records = []
        for _, row in df.iterrows():
            try:
                # 使用pandas处理时间戳
                timestamp = pd.to_datetime(row['Timestamp'])
                records.append({
                    "timestamp": timestamp,
                    "wp_true": float(row['wp_true'])
                })
            except (ValueError, TypeError) as e:
                current_app.logger.error(f"数据格式错误: {row} - {str(e)}")
        
        # 批量插入
        with db_session() as db:
            # 检查重复时间戳
            existing_timestamps = {r['timestamp'] for r in records}
            duplicates = db.query(ActualPower.timestamp).filter(
                ActualPower.timestamp.in_(existing_timestamps)
            ).all()
            duplicate_set = {dt[0] for dt in duplicates}
            
            # 过滤有效记录
            valid_records = [
                r for r in records 
                if r['timestamp'] not in duplicate_set
            ]
            
            # 批量插入
            if valid_records:
                db.bulk_insert_mappings(ActualPower, valid_records)
                db.commit()
            
            return jsonify({
                "total": len(records),
                "inserted": len(valid_records),
                "duplicates": len(duplicate_set),
                "errors": len(records) - len(valid_records) - len(duplicate_set)
            }), 201
            
    except Exception as e:
        current_app.logger.error(f"文件处理失败: {str(e)}")
        return jsonify({"error": f"文件处理失败: {str(e)}"}), 500 