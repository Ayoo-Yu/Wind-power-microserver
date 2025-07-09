from flask import Blueprint, request, jsonify
from datetime import datetime
from models import Dataset, Model, TrainingRecord, EvaluationMetrics
from database_config import get_db
import time
from services.storage_service import get_model_path, get_scaler_path, get_metrics_path
from config import MINIO_CONFIG
from db_session import db_session  # 导入上下文管理器

training_bp = Blueprint('training', __name__)

@training_bp.route('/train', methods=['POST'])
def start_training():
    data = request.json
    
    try:
        with db_session() as db:
            # 创建训练记录
            record = TrainingRecord(
                model_name=data['model_name'],
                status='running',
                dataset_path=data['dataset_path'],
                created_at=datetime.utcnow(),
                log_path=data.get('log_path')
            )
            db.add(record)
            db.commit()
            
            # 模拟训练过程（实际应替换为真实训练逻辑）
            start_time = time.time()
            # ... 训练代码 ...
            training_time = time.time() - start_time
            
            # 保存模型信息
            new_model = Model(
                model_name=data['model_name'],
                model_path=data['model_path'],
                scaler_path=data['scaler_path'],
                model_type=data['model_type'],
                dataset_id=data['dataset_id'],
                metrics_path=data['metrics_path'],
                parameters=data['parameters'],
                is_active=False
            )
            db.add(new_model)
            
            # 保存评估指标
            metrics = EvaluationMetrics(
                model_id=new_model.id,
                mae=data['metrics']['mae'],
                rmse=data['metrics']['rmse'],
                mape=data['metrics']['mape'],
                r2=data['metrics']['r2']
            )
            db.add(metrics)
            
            # 生成存储路径
            model_type = data['model_type']
            model_path = get_model_path(model_type, data['model_name'])
            scaler_path = get_scaler_path(model_type)
            metrics_path = get_metrics_path(new_model.id)
            
            # 更新模型信息
            new_model.model_path = model_path
            new_model.scaler_path = scaler_path
            new_model.metrics_path = metrics_path
            
            # 实际训练中需要将文件保存到MinIO
            minio_client.put_object(
                MINIO_CONFIG["buckets"]["models"],
                model_path,
                trained_model_file
            )
            # ... 类似保存scaler和metrics ...
            
            # 更新训练记录
            record.status = 'success'
            record.duration = training_time
            
            db.commit()
            return jsonify({
                'message': 'Training completed',
                'model_id': new_model.id,
                'metrics': data['metrics']
            })
            
    except Exception as e:
        if 'db' in locals() and 'record' in locals():
            with db_session() as db:
                record = db.merge(record)
                record.status = 'failed'
                db.commit()
        return jsonify({'error': str(e)}), 500

@training_bp.route('/models/active', methods=['POST'])
def set_active_model():
    data = request.json
    
    try:
        with db_session() as db:
            # 先取消所有激活状态
            db.query(Model).update({Model.is_active: False})
            
            # 设置新的激活模型
            model = db.query(Model).get(data['model_id'])
            if model:
                model.is_active = True
                db.commit()
                return jsonify({'message': f'Model {model.id} activated'})
            
            return jsonify({'error': 'Model not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500 