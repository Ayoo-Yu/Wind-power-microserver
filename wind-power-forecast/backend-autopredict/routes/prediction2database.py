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
        # 从文件名中提取时间信息并计算pre_order
        filename = file.filename
        time_str = filename[-8:-4]  # 获取文件名中的时间部分(hhmm)
        hour = int(time_str[:2])
        minute = int(time_str[2:])
        pre_order = (hour * 60 + minute) // 15 + 1  # 计算pre_order

        # 使用pandas读取CSV
        df = pd.read_csv(file)
        records = []
        
        # 为每行数据添加pre_num（从1开始的序号）
        for index, row in df.iterrows():
            try:
                timestamp = pd.to_datetime(row['Timestamp'])
                records.append({
                    "timestamp": timestamp,
                    "wp_pred": float(row['Predicted Power']),
                    "pre_order": pre_order,  # 使用计算得到的pre_order
                    "pre_num": index + 1     # 使用行索引+1作为pre_num
                })
            except (ValueError, TypeError) as e:
                current_app.logger.error(f"数据格式错误: {row} - {str(e)}")
        
        # 批量插入
        with db_session() as db:
            # 检查重复时间戳
            existing_timestamps = {r['timestamp'] for r in records}
            duplicates = db.query(SupershortlPower.timestamp).filter(
                SupershortlPower.timestamp.in_(existing_timestamps)
            ).all()
            duplicate_set = {dt[0] for dt in duplicates}
            
            # 修改：将重复记录更新而不是跳过
            for record in records:
                if record['timestamp'] in duplicate_set:
                    # 更新已存在的记录
                    db.query(SupershortlPower).filter(
                        SupershortlPower.timestamp == record['timestamp']
                    ).update({
                        "wp_pred": record['wp_pred'],
                        "pre_order": record['pre_order'],
                        "pre_num": record['pre_num']
                    })
                else:
                    # 插入新记录
                    db.add(SupershortlPower(**record))
            
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