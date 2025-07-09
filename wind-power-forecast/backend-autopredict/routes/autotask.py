from flask import Blueprint, request, jsonify
from models import AutoPredictionTask
from database_config import get_db
from datetime import datetime
from db_session import db_session  # 导入上下文管理器

autotask_bp = Blueprint('autotask', __name__)

@autotask_bp.route('/tasks', methods=['POST'])
def create_auto_task():
    data = request.json
    
    try:
        with db_session() as db:
            task = AutoPredictionTask(
                task_type=data['task_type'],
                schedule_time=data['schedule_time'],
                output_dir=data['output_dir'],
                is_active=True
            )
            db.add(task)
            db.commit()
            return jsonify({'task_id': task.id})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@autotask_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def update_auto_task(task_id):
    data = request.json
    
    try:
        with db_session() as db:
            task = db.query(AutoPredictionTask).get(task_id)
            if not task:
                return jsonify({'error': 'Task not found'}), 404
                
            if 'schedule_time' in data:
                task.schedule_time = data['schedule_time']
            if 'is_active' in data:
                task.is_active = data['is_active']
            if 'output_dir' in data:
                task.output_dir = data['output_dir']
                
            db.commit()
            return jsonify({'message': 'Task updated'})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500 