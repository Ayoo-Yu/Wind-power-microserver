from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from db_session import db_session
from db_models.weather_fetch import WeatherConnection, WeatherTask, WeatherLog
from datetime import datetime, timedelta
import subprocess
import paramiko
import os
import logging
from services.task_executor import execute_weather_task
from services.scheduler_service import get_scheduler
from services import ssh_service

weather_fetch_bp = Blueprint('weather_fetch', __name__)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@weather_fetch_bp.route('/connections', methods=['GET'])
@jwt_required()
def get_connections():
    """获取SSH连接列表"""
    try:
        with db_session() as db:
            connections = db.query(WeatherConnection).filter(
                WeatherConnection.deleted_at == None
            ).all()
            
            return jsonify([{
                'id': conn.id,
                'name': conn.name,
                'host': conn.host,
                'port': conn.port,
                'username': conn.username,
                'auth_type': conn.auth_type,
                'status': conn.status,
                'created_at': conn.created_at.isoformat() if conn.created_at else None,
                'last_test_at': conn.last_test_at.isoformat() if conn.last_test_at else None
            } for conn in connections])
    except Exception as e:
        logger.error(f"获取连接列表失败: {e}")
        return jsonify({'message': '获取连接列表失败'}), 500

@weather_fetch_bp.route('/connections', methods=['POST'])
@jwt_required()
def create_connection():
    """创建SSH连接"""
    try:
        data = request.get_json()
        current_user_id = get_jwt_identity()
        
        # 验证必填字段
        required_fields = ['name', 'host', 'port', 'username', 'auth_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'message': f'缺少必填字段: {field}'}), 400
        
        # 根据认证方式验证相应字段
        if data['auth_type'] == 'password' and not data.get('password'):
            return jsonify({'message': '密码认证需要提供密码'}), 400
        elif data['auth_type'] == 'key' and not data.get('private_key_path'):
            return jsonify({'message': '密钥认证需要提供私钥路径'}), 400
        
        with db_session() as db:
            # 检查连接名称是否重复
            existing = db.query(WeatherConnection).filter(
                WeatherConnection.name == data['name'],
                WeatherConnection.deleted_at == None
            ).first()
            
            if existing:
                return jsonify({'message': '连接名称已存在'}), 400
            
            # 创建新连接
            connection = WeatherConnection(
                name=data['name'],
                host=data['host'],
                port=data['port'],
                username=data['username'],
                auth_type=data['auth_type'],
                password=data.get('password', ''),
                private_key_path=data.get('private_key_path', ''),
                key_passphrase=data.get('key_passphrase', ''),
                created_by=current_user_id
            )
            
            db.add(connection)
            db.commit()
            
            return jsonify({
                'message': '连接创建成功',
                'id': connection.id
            }), 201
            
    except Exception as e:
        logger.error(f"创建连接失败: {e}")
        return jsonify({'message': '创建连接失败'}), 500

@weather_fetch_bp.route('/connections/<int:connection_id>', methods=['PUT'])
@jwt_required()
def update_connection(connection_id):
    """更新SSH连接"""
    try:
        data = request.get_json()
        
        with db_session() as db:
            connection = db.query(WeatherConnection).filter(
                WeatherConnection.id == connection_id,
                WeatherConnection.deleted_at == None
            ).first()
            
            if not connection:
                return jsonify({'message': '连接不存在'}), 404
            
            # 更新字段
            update_fields = ['name', 'host', 'port', 'username', 'auth_type', 
                           'password', 'private_key_path', 'key_passphrase']
            
            for field in update_fields:
                if field in data:
                    setattr(connection, field, data[field])
            
            connection.updated_at = datetime.utcnow()
            db.commit()
            
            return jsonify({'message': '连接更新成功'})
            
    except Exception as e:
        logger.error(f"更新连接失败: {e}")
        return jsonify({'message': '更新连接失败'}), 500

@weather_fetch_bp.route('/connections/<int:connection_id>', methods=['DELETE'])
@jwt_required()
def delete_connection(connection_id):
    """删除SSH连接（软删除）"""
    try:
        with db_session() as db:
            connection = db.query(WeatherConnection).filter(
                WeatherConnection.id == connection_id,
                WeatherConnection.deleted_at == None
            ).first()
            
            if not connection:
                return jsonify({'message': '连接不存在'}), 404
            
            # 软删除
            connection.deleted_at = datetime.utcnow()
            db.commit()
            
            return jsonify({'message': '连接删除成功'})
            
    except Exception as e:
        logger.error(f"删除连接失败: {e}")
        return jsonify({'message': '删除连接失败'}), 500

@weather_fetch_bp.route('/connections/<int:connection_id>/test', methods=['POST'])
@jwt_required()
def test_connection(connection_id):
    """测试SSH连接"""
    try:
        with db_session() as db:
            connection = db.query(WeatherConnection).filter(
                WeatherConnection.id == connection_id,
                WeatherConnection.deleted_at == None
            ).first()
            
            if not connection:
                return jsonify({'message': '连接不存在'}), 404
            
            # 测试SSH连接
            success = False
            error_message = ""
            
            try:
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                if connection.auth_type == 'password':
                    ssh_client.connect(
                        hostname=connection.host,
                        port=connection.port,
                        username=connection.username,
                        password=connection.password,
                        timeout=10
                    )
                else:  # key authentication
                    ssh_client.connect(
                        hostname=connection.host,
                        port=connection.port,
                        username=connection.username,
                        key_filename=connection.private_key_path,
                        passphrase=connection.key_passphrase if connection.key_passphrase else None,
                        timeout=10
                    )
                
                # 执行简单命令测试
                stdin, stdout, stderr = ssh_client.exec_command('echo "test"')
                result = stdout.read().decode().strip()
                
                if result == "test":
                    success = True
                    connection.status = 'connected'
                else:
                    error_message = "命令执行测试失败"
                    connection.status = 'disconnected'
                
                ssh_client.close()
                
            except Exception as ssh_error:
                error_message = str(ssh_error)
                connection.status = 'disconnected'
            
            # 更新测试时间
            connection.last_test_at = datetime.utcnow()
            db.commit()
            
            return jsonify({
                'success': success,
                'message': '连接成功' if success else f'连接失败: {error_message}'
            })
            
    except Exception as e:
        logger.error(f"测试连接失败: {e}")
        return jsonify({'message': '测试连接失败'}), 500

@weather_fetch_bp.route('/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
    """获取拉取任务列表"""
    try:
        with db_session() as db:
            tasks = db.query(WeatherTask).join(WeatherConnection).filter(
                WeatherTask.deleted_at == None,
                WeatherConnection.deleted_at == None
            ).all()
            
            return jsonify([{
                'id': task.id,
                'name': task.name,
                'connection_id': task.connection_id,
                'connection_name': task.connection.name,
                'remote_path': task.remote_path,
                'path_pattern': task.path_pattern,
                'custom_path_pattern': task.custom_path_pattern,
                'time_strategy': task.time_strategy,
                'specific_time': task.specific_time.isoformat() if task.specific_time else None,
                'time_range_start': task.time_range_start.isoformat() if task.time_range_start else None,
                'time_range_end': task.time_range_end.isoformat() if task.time_range_end else None,
                'file_pattern': task.file_pattern,
                'schedule': task.schedule,
                'save_path': task.save_path,
                'processing_options': task.processing_options,
                'deduplication_options': task.deduplication_options,
                'timeout': task.timeout,
                'retry_count': task.retry_count,
                'enabled': task.enabled,
                'status': task.status,
                'last_run': task.last_run.isoformat() if task.last_run else None,
                'next_run': task.next_run.isoformat() if task.next_run else None,
                'description': task.description,
                'created_at': task.created_at.isoformat() if task.created_at else None
            } for task in tasks])
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return jsonify({'message': '获取任务列表失败'}), 500

@weather_fetch_bp.route('/tasks', methods=['POST'])
@jwt_required()
def create_task():
    """创建拉取任务"""
    try:
        data = request.get_json()
        current_user_id = get_jwt_identity()
        
        # 验证必填字段
        required_fields = ['name', 'connection_id', 'remote_path', 'file_pattern', 'save_path', 'path_pattern', 'time_strategy']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'message': f'缺少必填字段: {field}'}), 400
        
        with db_session() as db:
            # 验证连接存在
            connection = db.query(WeatherConnection).filter(
                WeatherConnection.id == data['connection_id'],
                WeatherConnection.deleted_at == None
            ).first()
            
            if not connection:
                return jsonify({'message': '指定的SSH连接不存在'}), 400
            
            # 检查任务名称是否重复
            existing = db.query(WeatherTask).filter(
                WeatherTask.name == data['name'],
                WeatherTask.deleted_at == None
            ).first()
            
            if existing:
                return jsonify({'message': '任务名称已存在'}), 400
            
            # 处理调度表达式
            schedule = data.get('schedule', '0 */6 * * *')
            if schedule == 'custom':
                schedule = data.get('custom_schedule', '0 */6 * * *')
            
            # 处理时间范围
            time_range_start = None
            time_range_end = None
            specific_time = None
            
            if data['time_strategy'] == 'specific' and data.get('specific_time'):
                specific_time = datetime.fromisoformat(data['specific_time'].replace('Z', '+00:00'))
            elif data['time_strategy'] == 'range' and data.get('time_range'):
                time_range = data['time_range']
                if isinstance(time_range, list) and len(time_range) == 2:
                    time_range_start = datetime.fromisoformat(time_range[0].replace('Z', '+00:00'))
                    time_range_end = datetime.fromisoformat(time_range[1].replace('Z', '+00:00'))
            
            # 创建新任务
            task = WeatherTask(
                name=data['name'],
                connection_id=data['connection_id'],
                remote_path=data['remote_path'],
                path_pattern=data['path_pattern'],
                custom_path_pattern=data.get('custom_path_pattern', ''),
                time_strategy=data['time_strategy'],
                specific_time=specific_time,
                time_range_start=time_range_start,
                time_range_end=time_range_end,
                file_pattern=data['file_pattern'],
                schedule=schedule,
                save_path=data['save_path'],
                processing_options=data.get('processing_options', []),
                deduplication_options=data.get('deduplication_options', ['skip_existing']),
                timeout=data.get('timeout', 300),
                retry_count=data.get('retry_count', 3),
                description=data.get('description', ''),
                created_by=current_user_id
            )
            
            db.add(task)
            db.commit()
            
            # 将任务添加到调度器
            try:
                scheduler = get_scheduler()
                if scheduler and task.enabled:
                    scheduler.add_task_to_scheduler(task)
            except Exception as e:
                logger.error(f"添加任务到调度器失败: {e}")
            
            return jsonify({
                'message': '任务创建成功',
                'id': task.id
            }), 201
            
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        return jsonify({'message': '创建任务失败'}), 500

@weather_fetch_bp.route('/tasks/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    """更新拉取任务"""
    try:
        data = request.get_json()
        
        with db_session() as db:
            task = db.query(WeatherTask).filter(
                WeatherTask.id == task_id,
                WeatherTask.deleted_at == None
            ).first()
            
            if not task:
                return jsonify({'message': '任务不存在'}), 404
            
            # 处理时间相关字段
            if 'time_strategy' in data:
                task.time_strategy = data['time_strategy']
                
                if data['time_strategy'] == 'specific' and data.get('specific_time'):
                    task.specific_time = datetime.fromisoformat(data['specific_time'].replace('Z', '+00:00'))
                    task.time_range_start = None
                    task.time_range_end = None
                elif data['time_strategy'] == 'range' and data.get('time_range'):
                    time_range = data['time_range']
                    if isinstance(time_range, list) and len(time_range) == 2:
                        task.time_range_start = datetime.fromisoformat(time_range[0].replace('Z', '+00:00'))
                        task.time_range_end = datetime.fromisoformat(time_range[1].replace('Z', '+00:00'))
                    task.specific_time = None
                else:  # latest
                    task.specific_time = None
                    task.time_range_start = None
                    task.time_range_end = None
            
            # 更新其他字段
            update_fields = ['name', 'connection_id', 'remote_path', 'path_pattern', 'custom_path_pattern',
                           'file_pattern', 'schedule', 'save_path', 'processing_options', 'deduplication_options',
                           'timeout', 'retry_count', 'description']
            
            for field in update_fields:
                if field in data:
                    if field == 'schedule' and data[field] == 'custom':
                        setattr(task, field, data.get('custom_schedule', '0 */6 * * *'))
                    else:
                        setattr(task, field, data[field])
            
            task.updated_at = datetime.utcnow()
            db.commit()
            
            # 更新调度器中的任务
            try:
                scheduler = get_scheduler()
                if scheduler:
                    scheduler.update_task_in_scheduler(task)
            except Exception as e:
                logger.error(f"更新调度器中的任务失败: {e}")
            
            return jsonify({'message': '任务更新成功'})
            
    except Exception as e:
        logger.error(f"更新任务失败: {e}")
        return jsonify({'message': '更新任务失败'}), 500

@weather_fetch_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    """删除拉取任务（软删除）"""
    try:
        with db_session() as db:
            task = db.query(WeatherTask).filter(
                WeatherTask.id == task_id,
                WeatherTask.deleted_at == None
            ).first()
            
            if not task:
                return jsonify({'message': '任务不存在'}), 404
            
            # 软删除
            task.deleted_at = datetime.utcnow()
            db.commit()
            
            # 从调度器中移除任务
            try:
                scheduler = get_scheduler()
                if scheduler:
                    scheduler.remove_task_from_scheduler(task.id)
            except Exception as e:
                logger.error(f"从调度器移除任务失败: {e}")
            
            return jsonify({'message': '任务删除成功'})
            
    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        return jsonify({'message': '删除任务失败'}), 500

@weather_fetch_bp.route('/tasks/<int:task_id>/toggle', methods=['POST'])
@jwt_required()
def toggle_task(task_id):
    """启用/停用任务"""
    try:
        with db_session() as db:
            task = db.query(WeatherTask).filter(
                WeatherTask.id == task_id,
                WeatherTask.deleted_at == None
            ).first()
            
            if not task:
                return jsonify({'message': '任务不存在'}), 404
            
            task.enabled = not task.enabled
            task.updated_at = datetime.utcnow()
            db.commit()
            
            # 更新调度器中的任务状态
            try:
                scheduler = get_scheduler()
                if scheduler:
                    scheduler.update_task_in_scheduler(task)
            except Exception as e:
                logger.error(f"更新调度器中的任务状态失败: {e}")
            
            return jsonify({
                'message': f'任务已{"启用" if task.enabled else "停用"}',
                'enabled': task.enabled
            })
            
    except Exception as e:
        logger.error(f"切换任务状态失败: {e}")
        return jsonify({'message': '切换任务状态失败'}), 500

@weather_fetch_bp.route('/tasks/<int:task_id>/run', methods=['POST'])
@jwt_required()
def run_task(task_id):
    """立即执行任务"""
    try:
        with db_session() as db:
            task = db.query(WeatherTask).filter(
                WeatherTask.id == task_id,
                WeatherTask.deleted_at == None
            ).first()
            
            if not task:
                return jsonify({'message': '任务不存在'}), 404
            
            # 获取连接信息
            connection = db.query(WeatherConnection).filter(
                WeatherConnection.id == task.connection_id,
                WeatherConnection.deleted_at == None
            ).first()
            
            if not connection:
                return jsonify({'message': '连接不存在'}), 404
            
            # 实际执行任务
            result = execute_weather_task(task, connection, db)
            
            if result['success']:
                return jsonify({
                    'message': '任务执行完成',
                    'files_processed': result.get('files_processed', 0),
                    'save_path': result.get('save_path', ''),
                    'total_size': result.get('total_size', 0)
                })
            else:
                return jsonify({
                    'message': '任务执行失败',
                    'error': result.get('error', '未知错误')
                }), 500
            
    except Exception as e:
        logger.error(f"执行任务失败: {e}")
        return jsonify({'message': f'执行任务失败: {str(e)}'}), 500

@weather_fetch_bp.route('/logs', methods=['GET'])
@jwt_required()
def get_logs():
    """获取执行日志"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        level = request.args.get('level', '')
        
        with db_session() as db:
            query = db.query(WeatherLog).join(WeatherTask).filter(
                WeatherTask.deleted_at == None
            )
            
            if level and level != 'all':
                query = query.filter(WeatherLog.log_level == level)
            
            logs = query.order_by(WeatherLog.created_at.desc()).limit(per_page).offset((page - 1) * per_page).all()
            
            return jsonify([{
                'id': log.id,
                'task_id': log.task_id,
                'task_name': log.task.name if log.task else '未知任务',
                'level': log.log_level,
                'message': log.message,
                'details': log.details,
                'created_at': log.created_at.isoformat() if log.created_at else None
            } for log in logs])
            
    except Exception as e:
        logger.error(f"获取日志失败: {e}")
        return jsonify({'message': '获取日志失败'}), 500

@weather_fetch_bp.route('/tasks/<int:task_id>/logs', methods=['GET'])
@jwt_required()
def get_task_logs(task_id):
    """获取特定任务的执行日志"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)
        level = request.args.get('level', '')
        
        with db_session() as db:
            # 验证任务存在
            task = db.query(WeatherTask).filter(
                WeatherTask.id == task_id,
                WeatherTask.deleted_at == None
            ).first()
            
            if not task:
                return jsonify({'message': '任务不存在'}), 404
            
            query = db.query(WeatherLog).filter(WeatherLog.task_id == task_id)
            
            if level and level != 'all':
                query = query.filter(WeatherLog.log_level == level)
            
            logs = query.order_by(WeatherLog.created_at.desc()).limit(per_page).offset((page - 1) * per_page).all()
            
            return jsonify({
                'task_name': task.name,
                'task_id': task_id,
                'logs': [{
                    'id': log.id,
                    'level': log.log_level,
                    'message': log.message,
                    'details': log.details,
                    'created_at': log.created_at.isoformat() if log.created_at else None
                } for log in logs]
            })
            
    except Exception as e:
        logger.error(f"获取任务日志失败: {e}")
        return jsonify({'message': '获取任务日志失败'}), 500

@weather_fetch_bp.route('/scheduler/status', methods=['GET'])
@jwt_required()
def get_scheduler_status():
    """获取调度器状态"""
    try:
        scheduler = get_scheduler()
        if not scheduler:
            return jsonify({
                'message': '调度器未初始化',
                'is_running': False,
                'jobs': [],
                'total_jobs': 0
            }), 503
        
        return jsonify(scheduler.get_scheduled_jobs())
    except Exception as e:
        logger.error(f"获取调度器状态失败: {e}")
        return jsonify({'message': '获取调度器状态失败'}), 500

@weather_fetch_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    """获取统计信息"""
    try:
        with db_session() as db:
            today = datetime.utcnow().date()
            
            # 今日处理文件数（从日志中统计）
            files_processed_today = db.query(WeatherLog).filter(
                WeatherLog.log_level == 'success',
                WeatherLog.message.like('%文件处理完成%'),
                WeatherLog.created_at >= today
            ).count()
            
            # 今日插入记录数（需要从详细日志中解析，这里简化处理）
            records_inserted_today = files_processed_today * 100  # 假设每个文件平均100条记录
            
            # 成功率计算（最近24小时）
            yesterday = datetime.utcnow() - timedelta(hours=24)
            total_runs = db.query(WeatherLog).filter(
                WeatherLog.created_at >= yesterday,
                WeatherLog.message.like('%任务执行%')
            ).count()
            
            success_runs = db.query(WeatherLog).filter(
                WeatherLog.created_at >= yesterday,
                WeatherLog.log_level == 'success',
                WeatherLog.message.like('%任务执行成功%')
            ).count()
            
            success_rate = f"{(success_runs / total_runs * 100):.1f}%" if total_runs > 0 else "0%"
            
            # 活跃任务数
            active_tasks = db.query(WeatherTask).filter(
                WeatherTask.enabled == True,
                WeatherTask.deleted_at == None
            ).count()
            
            # 获取调度器状态
            scheduler_status = "未知"
            try:
                scheduler = get_scheduler()
                if scheduler:
                    scheduler_status = "运行中" if scheduler.is_running else "已停止"
                else:
                    scheduler_status = "未初始化"
            except:
                scheduler_status = "错误"
            
            return jsonify({
                'files_processed_today': files_processed_today,
                'records_inserted_today': records_inserted_today,
                'success_rate': success_rate,
                'active_tasks': active_tasks,
                'scheduler_status': scheduler_status
            })
            
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return jsonify({'message': '获取统计信息失败'}), 500

@weather_fetch_bp.route('/check-directories', methods=['POST'])
@jwt_required()
def check_directories():
    """检查可用的时间目录"""
    try:
        data = request.get_json()
        connection_id = data.get('connection_id')
        base_path = data.get('base_path')
        path_pattern = data.get('path_pattern', 'YYYY_MMDDHHNN')
        time_strategy = data.get('time_strategy', 'latest')
        specific_time = data.get('specific_time')
        time_range_start = data.get('time_range_start')
        time_range_end = data.get('time_range_end')
        
        if not connection_id or not base_path:
            return jsonify({'message': '缺少必要参数'}), 400
        
        with db_session() as db:
            # 获取连接信息
            connection = db.query(WeatherConnection).filter(
                WeatherConnection.id == connection_id,
                WeatherConnection.deleted_at == None
            ).first()
            
            if not connection:
                return jsonify({'message': '连接不存在'}), 404
            
            # 构建连接配置
            connection_config = {
                'host': connection.host,
                'port': connection.port,
                'username': connection.username,
                'auth_type': connection.auth_type,
                'password': connection.password,
                'private_key_path': connection.private_key_path,
                'key_passphrase': connection.key_passphrase
            }
            
            # 查找可用目录
            limit = data.get('limit', 50)  # 默认50个，最大100个
            if limit > 100:
                limit = 100
            
            directories = ssh_service.find_available_time_directories(
                connection_config,
                base_path,
                path_pattern,
                time_strategy=time_strategy,
                specific_time=specific_time,
                time_range_start=time_range_start,
                time_range_end=time_range_end,
                limit=limit
            )
            
            return jsonify({
                'directories': directories,
                'total_found': len(directories)
            })
            
    except Exception as e:
        logger.error(f"检查可用目录失败: {e}")
        return jsonify({'message': f'检查目录失败: {str(e)}'}), 500

@weather_fetch_bp.route('/scheduler/restart', methods=['POST'])
@jwt_required()
def restart_scheduler():
    """重启调度器"""
    try:
        from services.scheduler_service import weather_scheduler, init_scheduler
        import os
        
        # 停止当前调度器
        if weather_scheduler and weather_scheduler.is_running:
            weather_scheduler.stop()
            logger.info("旧调度器已停止")
        
        # 重新初始化调度器
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '54321')
        db_user = os.environ.get('DB_USER', 'system')
        db_password = os.environ.get('DB_PASSWORD', '12345678ab')
        db_name = os.environ.get('DB_NAME', 'windpower')
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        init_scheduler(database_url)
        logger.info("调度器重启成功")
        
        # 获取重启后的状态
        scheduler = get_scheduler()
        status = scheduler.get_scheduled_jobs() if scheduler else {
            'is_running': False,
            'jobs': [],
            'total_jobs': 0
        }
        
        return jsonify({
            'message': '调度器重启成功',
            'status': status
        })
        
    except Exception as e:
        logger.error(f"重启调度器失败: {e}")
        return jsonify({'message': f'重启调度器失败: {str(e)}'}), 500 