from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone, date
import requests
import json
import logging
from db_session import db_session
from models import (
    WindFarm, ReportConfig, ReportLog, ActualPower, SupershortlPower, ShortlPower, MidPower, ReportQualityStatistics,
    WindSpeedData, TurbinePowerData, WeatherData, InstalledCapacityData, AvailableCapacityData, 
    TheoreticalPowerData, AvailablePowerData
)
from sqlalchemy import desc, and_, or_, func, distinct

# 添加定时调度器
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
from threading import Lock

# 创建调度器实例和锁
report_scheduler = BackgroundScheduler(daemon=True)
scheduler_lock = Lock()

report_management_bp = Blueprint('report_management', __name__)

@report_management_bp.route('/test', methods=['GET'])
def test_route():
    """测试路由"""
    return jsonify({'message': '上报管理路由工作正常', 'status': 'ok'})

@report_management_bp.route('/farms', methods=['GET'])
def get_wind_farms():
    """获取风电场站列表"""
    try:
        with db_session() as db:
            farms = db.query(WindFarm).filter(WindFarm.is_active == True).all()
            
            farms_data = []
            for farm in farms:
                farms_data.append({
                    'id': farm.id,
                    'farm_code': farm.farm_code,
                    'farm_name': farm.farm_name,
                    'capacity': farm.capacity,
                    'location': farm.location,
                    'is_active': farm.is_active,
                    'created_at': farm.created_at.isoformat() if farm.created_at else None
                })
            
            return jsonify(farms_data)
    except Exception as e:
        logging.error(f"获取风电场站列表失败: {str(e)}")
        return jsonify({'error': '获取风电场站列表失败'}), 500

@report_management_bp.route('/farms', methods=['POST'])
def create_wind_farm():
    """创建风电场站"""
    try:
        data = request.get_json()
        
        with db_session() as db:
            # 检查场站编码是否已存在
            existing = db.query(WindFarm).filter(WindFarm.farm_code == data['farm_code']).first()
            if existing:
                return jsonify({'error': '场站编码已存在'}), 400
            
            farm = WindFarm(
                farm_code=data['farm_code'],
                farm_name=data['farm_name'],
                capacity=data.get('capacity'),
                location=data.get('location'),
                is_active=data.get('is_active', True)
            )
            
            db.add(farm)
            db.commit()
            
            return jsonify({
                'message': '风电场站创建成功',
                'farm_id': farm.id
            })
    except Exception as e:
        logging.error(f"创建风电场站失败: {str(e)}")
        return jsonify({'error': '创建风电场站失败'}), 500

@report_management_bp.route('/farms/<int:farm_id>', methods=['PUT'])
def update_wind_farm(farm_id):
    """更新风电场站"""
    try:
        data = request.get_json()
        with db_session() as db:
            farm = db.query(WindFarm).filter(WindFarm.id == farm_id).first()
            if not farm:
                return jsonify({'error': '风电场站不存在'}), 404
            
            if 'farm_code' in data and data['farm_code'] != farm.farm_code:
                existing = db.query(WindFarm).filter(WindFarm.farm_code == data['farm_code'], WindFarm.id != farm_id).first()
                if existing:
                    return jsonify({'error': '场站编码已存在'}), 400

            for key, value in data.items():
                if hasattr(farm, key) and key not in ['id', 'created_at']:
                    setattr(farm, key, value)
            
            db.commit()
            return jsonify({'message': '风电场站更新成功'})
    except Exception as e:
        logging.error(f"更新风电场站失败: {str(e)}")
        return jsonify({'error': '更新风电场站失败'}), 500

@report_management_bp.route('/configs', methods=['GET'])
def get_report_configs():
    """获取上报配置列表"""
    try:
        farm_id = request.args.get('farm_id', type=int)
        
        with db_session() as db:
            query = db.query(ReportConfig, WindFarm.farm_name, WindFarm.farm_code)\
                     .join(WindFarm, ReportConfig.farm_id == WindFarm.id)
            
            if farm_id:
                query = query.filter(ReportConfig.farm_id == farm_id)
            
            configs = query.all()
            
            configs_data = []
            for config, farm_name, farm_code in configs:
                configs_data.append({
                    'id': config.id,
                    'farm_id': config.farm_id,
                    'farm_name': farm_name,
                    'farm_code': farm_code,
                    'report_type': config.report_type,
                    'target_ip': config.target_ip,
                    'target_port': config.target_port,
                    'report_interval': config.report_interval,
                    'report_time': config.report_time,
                    'is_enabled': config.is_enabled,
                    'last_report_time': config.last_report_time.isoformat() if config.last_report_time else None,
                    'report_format': config.report_format,
                    'timeout_seconds': config.timeout_seconds,
                    'retry_count': config.retry_count,
                    'created_at': config.created_at.isoformat() if config.created_at else None
                })
            
            return jsonify(configs_data)
    except Exception as e:
        logging.error(f"获取上报配置列表失败: {str(e)}")
        return jsonify({'error': '获取上报配置列表失败'}), 500

@report_management_bp.route('/configs', methods=['POST'])
def create_report_config():
    """创建上报配置"""
    try:
        data = request.get_json()
        
        with db_session() as db:
            config = ReportConfig(
                farm_id=data['farm_id'],
                report_type=data['report_type'],
                target_ip=data['target_ip'],
                target_port=data['target_port'],
                report_interval=data['report_interval'],
                report_time=data.get('report_time'),
                is_enabled=data.get('is_enabled', True),
                report_format=data.get('report_format', 'json'),
                timeout_seconds=data.get('timeout_seconds', 30),
                retry_count=data.get('retry_count', 3)
            )
            
            db.add(config)
            db.commit()
            
            return jsonify({
                'message': '上报配置创建成功',
                'config_id': config.id
            })
    except Exception as e:
        logging.error(f"创建上报配置失败: {str(e)}")
        return jsonify({'error': '创建上报配置失败'}), 500

@report_management_bp.route('/configs/<int:config_id>', methods=['PUT'])
def update_report_config(config_id):
    """更新上报配置"""
    try:
        data = request.get_json()
        
        with db_session() as db:
            config = db.query(ReportConfig).filter(ReportConfig.id == config_id).first()
            if not config:
                return jsonify({'error': '配置不存在'}), 404
            
            # 更新字段
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            config.updated_at = datetime.now()
            db.commit()
            
            return jsonify({'message': '上报配置更新成功'})
    except Exception as e:
        logging.error(f"更新上报配置失败: {str(e)}")
        return jsonify({'error': '更新上报配置失败'}), 500

@report_management_bp.route('/configs/<int:config_id>', methods=['DELETE'])
def delete_report_config(config_id):
    """删除上报配置"""
    try:
        with db_session() as db:
            config = db.query(ReportConfig).filter(ReportConfig.id == config_id).first()
            if not config:
                return jsonify({'error': '配置不存在'}), 404
            
            db.delete(config)
            db.commit()
            
            return jsonify({'message': '上报配置删除成功'})
    except Exception as e:
        logging.error(f"删除上报配置失败: {str(e)}")
        return jsonify({'error': '删除上报配置失败'}), 500

@report_management_bp.route('/logs', methods=['GET'])
def get_report_logs():
    """获取上报日志"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        farm_code = request.args.get('farm_code')
        report_type = request.args.get('report_type')
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with db_session() as db:
            query = db.query(ReportLog)
            
            # 应用过滤条件
            if farm_code:
                query = query.filter(ReportLog.farm_code == farm_code)
            if report_type:
                query = query.filter(ReportLog.report_type == report_type)
            if status:
                query = query.filter(ReportLog.status == status)
            if start_date:
                start_datetime = datetime.fromisoformat(start_date)
                query = query.filter(ReportLog.report_time >= start_datetime)
            if end_date:
                end_datetime = datetime.fromisoformat(end_date)
                query = query.filter(ReportLog.report_time <= end_datetime)
            
            # 按时间倒序排列
            query = query.order_by(desc(ReportLog.report_time))
            
            # 分页
            total = query.count()
            logs = query.offset((page - 1) * per_page).limit(per_page).all()
            
            logs_data = []
            for log in logs:
                logs_data.append({
                    'id': log.id,
                    'config_id': log.config_id,
                    'farm_code': log.farm_code,
                    'report_type': log.report_type,
                    'report_time': log.report_time.isoformat() if log.report_time else None,
                    'data_count': log.data_count,
                    'status': log.status,
                    'response_code': log.response_code,
                    'response_message': log.response_message,
                    'error_message': log.error_message,
                    'execution_time': log.execution_time
                })
            
            return jsonify({
                'logs': logs_data,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            })
    except Exception as e:
        logging.error(f"获取上报日志失败: {str(e)}")
        return jsonify({'error': '获取上报日志失败'}), 500

@report_management_bp.route('/preview-report', methods=['POST'])
def preview_report():
    """预览上报数据"""
    try:
        data = request.get_json()
        config_id = data.get('config_id')
        
        if not config_id:
            return jsonify({'error': '缺少配置ID'}), 400
        
        with db_session() as db:
            config = db.query(ReportConfig).filter(ReportConfig.id == config_id).first()
            if not config:
                return jsonify({'error': '配置不存在'}), 404
            
            # 获取风电场信息
            farm = db.query(WindFarm).filter(WindFarm.id == config.farm_id).first()
            if not farm:
                return jsonify({'error': '风电场不存在'}), 404
            
            # 获取预览数据 - 使用北京时间
            beijing_tz = timezone(timedelta(hours=8))
            current_time = datetime.now(beijing_tz)
            
            if config.report_type == 'actual':
                data_list = get_actual_power_data(db, current_time)
            elif config.report_type == 'forecast_short':
                data_list = get_forecast_short_data(db, current_time)
            elif config.report_type == 'forecast_long':
                data_list = get_forecast_long_data(db, current_time)
            elif config.report_type == 'wind_speed':
                data_list = get_wind_speed_data(db, current_time, farm.farm_code)
            elif config.report_type == 'turbine_power':
                data_list = get_turbine_power_data(db, current_time, farm.farm_code)
            elif config.report_type == 'weather':
                data_list = get_weather_data(db, current_time, farm.farm_code)
            elif config.report_type == 'installed_capacity':
                data_list = get_installed_capacity_data(db, current_time, farm.farm_code)
            elif config.report_type == 'available_capacity':
                data_list = get_available_capacity_data(db, current_time, farm.farm_code)
            elif config.report_type == 'theoretical_power':
                data_list = get_theoretical_power_data(db, current_time, farm.farm_code)
            elif config.report_type == 'available_power':
                data_list = get_available_power_data(db, current_time, farm.farm_code)
            else:
                return jsonify({'error': f'未知的上报类型: {config.report_type}'}), 400
            
            # 构造预览数据结构
            preview_data = {
                'config_info': {
                    'id': config.id,
                    'farm_name': farm.farm_name,
                    'farm_code': farm.farm_code,
                    'report_type': config.report_type,
                    'target_url': f"http://{config.target_ip}:{config.target_port}{getattr(config, 'target_path', '/receive-data') or '/receive-data'}"
                },
                'payload': {
                    'report_type': config.report_type,
                    'timestamp': current_time.isoformat(),
                    'farm_code': farm.farm_code,
                    'data': data_list
                },
                'data_summary': {
                    'total_records': len(data_list) if data_list else 0,
                    'has_data': any(item.get('data_source') == 'database' for item in data_list) if data_list else False,
                    'empty_records': sum(1 for item in data_list if item.get('data_source') == 'empty') if data_list else 0
                },
                'data_structure': get_data_structure_info(config.report_type)
            }
            
            return jsonify(preview_data)
    
    except Exception as e:
        logging.error(f"预览上报数据失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@report_management_bp.route('/manual-report', methods=['POST'])
def manual_report():
    """手动执行上报（支持自定义数据）"""
    try:
        data = request.get_json()
        config_id = data.get('config_id')
        custom_data = data.get('data')  # 用户修改后的数据
        
        if not config_id:
            return jsonify({'error': '缺少配置ID'}), 400
        
        with db_session() as db:
            config = db.query(ReportConfig).filter(ReportConfig.id == config_id).first()
            if not config:
                return jsonify({'error': '配置不存在'}), 404
            
            farm = db.query(WindFarm).filter(WindFarm.id == config.farm_id).first()
            if not farm:
                return jsonify({'error': '风电场不存在'}), 404
            
            # 如果提供了自定义数据，使用自定义数据；否则使用系统数据
            if custom_data:
                data_to_send = custom_data
            else:
                # 使用系统默认数据 - 使用北京时间
                beijing_tz = timezone(timedelta(hours=8))
                current_time = datetime.now(beijing_tz)
                
                if config.report_type == 'actual':
                    data_to_send = get_actual_power_data(db, current_time)
                elif config.report_type == 'forecast_short':
                    data_to_send = get_forecast_short_data(db, current_time)
                elif config.report_type == 'forecast_long':
                    data_to_send = get_forecast_long_data(db, current_time)
                elif config.report_type == 'wind_speed':
                    data_to_send = get_wind_speed_data(db, current_time, farm.farm_code)
                elif config.report_type == 'turbine_power':
                    data_to_send = get_turbine_power_data(db, current_time, farm.farm_code)
                elif config.report_type == 'weather':
                    data_to_send = get_weather_data(db, current_time, farm.farm_code)
                elif config.report_type == 'installed_capacity':
                    data_to_send = get_installed_capacity_data(db, current_time, farm.farm_code)
                elif config.report_type == 'available_capacity':
                    data_to_send = get_available_capacity_data(db, current_time, farm.farm_code)
                elif config.report_type == 'theoretical_power':
                    data_to_send = get_theoretical_power_data(db, current_time, farm.farm_code)
                elif config.report_type == 'available_power':
                    data_to_send = get_available_power_data(db, current_time, farm.farm_code)
                else:
                    return jsonify({'error': f'未知的上报类型: {config.report_type}'}), 400
            
            # 执行上报
            start_time = datetime.now()
            try:
                # 发送数据
                response = send_report_data(config, data_to_send, farm.farm_code)
                
                # 记录成功日志
                execution_time = (datetime.now() - start_time).total_seconds()
                log = ReportLog(
                    config_id=config.id,
                    farm_code=farm.farm_code,
                    report_type=config.report_type,
                    data_count=len(data_to_send) if data_to_send else 0,
                    data_completeness_rate=check_data_completeness(data_to_send, config.report_type),
                    status='success',
                    response_code=response.status_code,
                    response_message=response.text[:500] if response.text else None,
                    execution_time=execution_time
                )
                
                # 更新最后上报时间
                config.last_report_time = datetime.now()
                
                db.add(log)
                db.commit()
                
                # 手动上报也更新质量统计
                try:
                    # 检查数据完整性和及时性
                    data_completeness = check_data_completeness(data_to_send, config.report_type)
                    
                    # 获取数据时间戳用于及时性检查
                    data_timestamp = None
                    if data_to_send and len(data_to_send) > 0:
                        if 'timestamp' in data_to_send[0]:
                            try:
                                if isinstance(data_to_send[0]['timestamp'], str):
                                    if '+' in data_to_send[0]['timestamp']:
                                        timestamp_str = data_to_send[0]['timestamp'].split('+')[0]
                                    else:
                                        timestamp_str = data_to_send[0]['timestamp'].replace('T', ' ').replace('Z', '')
                                    data_timestamp = datetime.fromisoformat(timestamp_str)
                                else:
                                    data_timestamp = data_to_send[0]['timestamp']
                            except:
                                data_timestamp = None
                    
                    is_on_time = check_report_timeliness(start_time, data_timestamp)
                    
                    with db_session() as stats_db:
                        update_quality_statistics_async(stats_db, farm.farm_code, start_time, data_completeness, is_on_time, config.report_type)
                        stats_db.commit()
                except Exception as stats_error:
                    logging.warning(f"手动上报质量统计更新失败: {stats_error}")
                
                return jsonify({
                    'status': 'success',
                    'message': '手动上报执行完成',
                    'data_count': len(data_to_send) if data_to_send else 0,
                    'execution_time': execution_time,
                    'response_code': response.status_code,
                    'custom_data_used': bool(custom_data)
                })
                
            except Exception as e:
                # 记录失败日志
                execution_time = (datetime.now() - start_time).total_seconds()
                log = ReportLog(
                    config_id=config.id,
                    farm_code=farm.farm_code,
                    report_type=config.report_type,
                    data_count=0,
                    data_completeness_rate=0.0,
                    status='failed',
                    error_message=str(e)[:500],
                    execution_time=execution_time
                )
                
                db.add(log)
                db.commit()
                
                # 失败时也更新统计
                try:
                    with db_session() as stats_db:
                        update_quality_statistics_async(stats_db, farm.farm_code, start_time, 0.0, False, config.report_type)
                        stats_db.commit()
                except Exception as stats_error:
                    logging.warning(f"手动上报失败统计更新失败: {stats_error}")
                
                return jsonify({
                    'status': 'failed',
                    'error': str(e),
                    'execution_time': execution_time
                }), 500
    
    except Exception as e:
        logging.error(f"手动上报失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

def execute_report(db: Session, config: ReportConfig):
    """执行具体的上报逻辑"""
    start_time = datetime.now()
    farm = db.query(WindFarm).filter(WindFarm.id == config.farm_id).first()
    
    try:
        # 根据上报类型获取数据，传入当前上报时间
        if config.report_type == 'actual':
            data = get_actual_power_data(db, start_time)
        elif config.report_type == 'forecast_short':
            data = get_forecast_short_data(db, start_time)
        elif config.report_type == 'forecast_long':
            data = get_forecast_long_data(db, start_time)
        elif config.report_type == 'wind_speed':
            data = get_wind_speed_data(db, start_time, farm.farm_code)
        elif config.report_type == 'turbine_power':
            data = get_turbine_power_data(db, start_time, farm.farm_code)
        elif config.report_type == 'weather':
            data = get_weather_data(db, start_time, farm.farm_code)
        elif config.report_type == 'installed_capacity':
            data = get_installed_capacity_data(db, start_time, farm.farm_code)
        elif config.report_type == 'available_capacity':
            data = get_available_capacity_data(db, start_time, farm.farm_code)
        elif config.report_type == 'theoretical_power':
            data = get_theoretical_power_data(db, start_time, farm.farm_code)
        elif config.report_type == 'available_power':
            data = get_available_power_data(db, start_time, farm.farm_code)
        else:
            raise ValueError(f"未知的上报类型: {config.report_type}")
        
        # 检查数据完整性
        data_completeness = check_data_completeness(data, config.report_type)
        
        # 发送数据
        response = send_report_data(config, data, farm.farm_code)
        
        # 检查上报及时性（获取数据时间戳）
        data_timestamp = None
        if data and len(data) > 0:
            # 尝试从数据中提取时间戳
            if 'timestamp' in data[0]:
                try:
                    if isinstance(data[0]['timestamp'], str):
                        # 处理ISO格式的时间字符串
                        if '+' in data[0]['timestamp']:
                            timestamp_str = data[0]['timestamp'].split('+')[0]
                        else:
                            timestamp_str = data[0]['timestamp'].replace('T', ' ').replace('Z', '')
                        data_timestamp = datetime.fromisoformat(timestamp_str)
                    else:
                        data_timestamp = data[0]['timestamp']
                except:
                    data_timestamp = None
        
        is_on_time = check_report_timeliness(start_time, data_timestamp)
        
        # 记录成功日志
        execution_time = (datetime.now() - start_time).total_seconds()
        log = ReportLog(
            config_id=config.id,
            farm_code=farm.farm_code,
            report_type=config.report_type,
            data_count=len(data) if data else 0,
            data_completeness_rate=data_completeness,
            status='success',
            response_code=response.status_code,
            response_message=response.text[:500] if response.text else None,
            execution_time=execution_time
        )
        
        # 更新最后上报时间
        config.last_report_time = datetime.now()
        
        db.add(log)
        db.commit()
        
        # 在新的事务中更新质量统计（避免影响上报性能）
        try:
            with db_session() as stats_db:
                update_quality_statistics_async(stats_db, farm.farm_code, start_time, data_completeness, is_on_time, config.report_type)
                stats_db.commit()
        except Exception as stats_error:
            logging.warning(f"更新质量统计失败: {stats_error}")
        
        return {
            'status': 'success',
            'data_count': len(data) if data else 0,
            'execution_time': execution_time,
            'data_completeness': data_completeness,
            'is_on_time': is_on_time
        }
        
    except Exception as e:
        # 记录失败日志
        execution_time = (datetime.now() - start_time).total_seconds()
        log = ReportLog(
            config_id=config.id,
            farm_code=farm.farm_code,
            report_type=config.report_type,
            data_count=0,
            data_completeness_rate=0.0,
            status='failed',
            error_message=str(e)[:500],
            execution_time=execution_time
        )
        
        db.add(log)
        db.commit()
        
        # 失败时也要更新统计（在新事务中）
        try:
            with db_session() as stats_db:
                update_quality_statistics_async(stats_db, farm.farm_code, start_time, 0.0, False, config.report_type)
                stats_db.commit()
        except Exception as stats_error:
            logging.warning(f"更新质量统计失败: {stats_error}")
        
        return {
            'status': 'failed',
            'error': str(e),
            'execution_time': execution_time
        }

def get_actual_power_data(db: Session, report_time: datetime = None):
    """获取实际功率数据（对应时刻的数据）"""
    if report_time is None:
        report_time = datetime.now()
    
    # 移除时区信息进行本地时间查询
    if report_time.tzinfo is not None:
        report_time = report_time.replace(tzinfo=None)
    
    # 向前取整到15分钟边界（实际功率通常按15分钟间隔记录）
    # 例如：10:16:30 -> 10:15:00, 10:31:30 -> 10:30:00
    minutes = (report_time.minute // 15) * 15
    target_time = report_time.replace(minute=minutes, second=0, microsecond=0)
    
    # 扩大查找窗口到±30分钟，增加找到数据的可能性
    time_window_start = target_time - timedelta(minutes=30)
    time_window_end = target_time + timedelta(minutes=30)
    
    actual_data = db.query(ActualPower)\
                   .filter(and_(
                       ActualPower.timestamp >= time_window_start,
                       ActualPower.timestamp <= time_window_end
                   ))\
                   .order_by(ActualPower.timestamp.desc())\
                   .first()
    
    if actual_data:
        return [{
            'time': target_time.isoformat(),
            'value': actual_data.wp_true,  # 使用value字段以匹配前端数据结构
            'wp_true': actual_data.wp_true,  # 保留兼容性字段
            'actual_timestamp': actual_data.timestamp.isoformat(),  # 实际数据的时间戳
            'data_source': 'database'
        }]
    else:
        # 如果还是找不到，尝试查询任意时间的数据
        any_data = db.query(ActualPower)\
                    .order_by(ActualPower.timestamp.desc())\
                    .limit(3).all()
        
        if any_data:
            logging.warning(f"未找到 {target_time} 时刻的实际功率数据，但数据库中有其他时间的数据")
            logging.info(f"最新数据时间: {[d.timestamp for d in any_data]}")
        else:
            logging.warning(f"数据库中完全没有实际功率数据")
        return []

def get_forecast_short_data(db: Session, report_time: datetime = None):
    """获取超短期预测数据（对应时刻的数据）"""
    if report_time is None:
        report_time = datetime.now()
    
    # 移除时区信息进行本地时间查询
    if report_time.tzinfo is not None:
        report_time = report_time.replace(tzinfo=None)
    
    # 超短期预测通常是基于整点时刻的预测，向前取整到15分钟边界
    minutes = (report_time.minute // 15) * 15
    target_time = report_time.replace(minute=minutes, second=0, microsecond=0)
    
    # 扩大查找窗口到±30分钟，增加找到数据的可能性
    time_window_start = target_time - timedelta(minutes=30)
    time_window_end = target_time + timedelta(minutes=30)
    
    forecast_data = db.query(SupershortlPower)\
                     .filter(and_(
                         SupershortlPower.timestamp >= time_window_start,
                         SupershortlPower.timestamp <= time_window_end
                     ))\
                     .order_by(SupershortlPower.timestamp.desc())\
                     .first()
    
    if forecast_data:
        data = {
            'time': target_time.isoformat(),
            'actual_timestamp': forecast_data.timestamp.isoformat(),  # 实际数据的时间戳
            'data_source': 'database'
        }
        # 添加所有预测字段（修正为wp_pred2到wp_pred17，对应数据库字段）
        for i in range(2, 18):  # wp_pred2 to wp_pred17
            field_name = f'wp_pred{i}'
            data[field_name] = getattr(forecast_data, field_name, None)
        return [data]
    else:
        # 如果还是找不到，尝试查询任意时间的数据
        any_data = db.query(SupershortlPower)\
                    .order_by(SupershortlPower.timestamp.desc())\
                    .limit(3).all()
        
        if any_data:
            logging.warning(f"未找到 {target_time} 时刻的超短期预测数据，但数据库中有其他时间的数据")
            logging.info(f"最新数据时间: {[d.timestamp for d in any_data]}")
        else:
            logging.warning(f"数据库中完全没有超短期预测数据")
        return []

def get_forecast_long_data(db: Session, report_time: datetime = None):
    """获取未来10天预测数据（短期1天+中期9天）"""
    if report_time is None:
        report_time = datetime.now()
    
    # 移除时区信息进行本地时间查询
    if report_time.tzinfo is not None:
        base_time = report_time.replace(tzinfo=None)
    else:
        base_time = report_time
        
    tomorrow = base_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    ten_days_later = tomorrow + timedelta(days=10)
    
    data = []
    
    # 获取短期预测（明天一天）
    short_forecasts = db.query(ShortlPower)\
                       .filter(and_(
                           ShortlPower.timestamp >= tomorrow,
                           ShortlPower.timestamp < tomorrow + timedelta(days=1)
                       ))\
                       .order_by(ShortlPower.timestamp)\
                       .all()
    
    logging.info(f"找到 {len(short_forecasts)} 条短期预测数据")
    for forecast in short_forecasts:
        data.append({
            'time': forecast.timestamp.isoformat(),
            'value': forecast.wp_pred,
            'data_source': 'database'
        })
    
    # 获取中期预测（后9天）
    mid_start = tomorrow + timedelta(days=1)
    mid_forecasts = db.query(MidPower)\
                     .filter(and_(
                         MidPower.timestamp >= mid_start,
                         MidPower.timestamp < ten_days_later
                     ))\
                     .order_by(MidPower.timestamp)\
                     .all()
    
    logging.info(f"找到 {len(mid_forecasts)} 条中期预测数据")
    for forecast in mid_forecasts:
        data.append({
            'time': forecast.timestamp.isoformat(),
            'value': forecast.wp_pred,
            'data_source': 'database'
        })
    
    # 如果数据不足，记录调试信息
    if len(data) == 0:
        # 检查是否有任意时间的预测数据
        any_short = db.query(ShortlPower).order_by(ShortlPower.timestamp.desc()).limit(3).all()
        any_mid = db.query(MidPower).order_by(MidPower.timestamp.desc()).limit(3).all()
        
        if any_short:
            logging.warning(f"未找到指定时间范围的短期预测数据，但数据库中有其他时间的短期数据")
            logging.info(f"最新短期数据时间: {[d.timestamp for d in any_short]}")
        else:
            logging.warning(f"数据库中完全没有短期预测数据")
            
        if any_mid:
            logging.warning(f"未找到指定时间范围的中期预测数据，但数据库中有其他时间的中期数据")
            logging.info(f"最新中期数据时间: {[d.timestamp for d in any_mid]}")
        else:
            logging.warning(f"数据库中完全没有中期预测数据")
    
    # 生成完整的960个时间点，不足的用空值填充
    time_series_data = []
    existing_times = {item['time']: item for item in data}
    
    for i in range(960):
        timestamp = tomorrow + timedelta(minutes=i * 15)
        timestamp_str = timestamp.isoformat()
        
        if timestamp_str in existing_times:
            time_series_data.append(existing_times[timestamp_str])
        else:
            time_series_data.append({
                'time': timestamp_str,
                'value': None,
                'data_source': 'empty'
            })
    
    if len(data) < 960:
        logging.warning(f"预测数据不足960个点，当前有{len(data)}个点，已用空值填充")
    
    # 验证时间范围
    if time_series_data:
        first_time = time_series_data[0]['time']
        last_time = time_series_data[-1]['time']
        logging.info(f"长期预测时间范围: {first_time} 到 {last_time}")
    
    return time_series_data

def get_wind_speed_data(db: Session, report_time: datetime = None, farm_code: str = None):
    """获取单机风速数据"""
    if report_time is None:
        report_time = datetime.now()
    if farm_code is None:
        return []
    
    # 移除时区信息进行本地时间查询
    if report_time.tzinfo is not None:
        report_time = report_time.replace(tzinfo=None)
    
    # 向前取整到15分钟边界
    minutes = (report_time.minute // 15) * 15
    target_time = report_time.replace(minute=minutes, second=0, microsecond=0)
    
    # 扩大查找窗口到±30分钟，增加找到数据的可能性
    time_window_start = target_time - timedelta(minutes=30)
    time_window_end = target_time + timedelta(minutes=30)
    
    # 查询数据，按turbine_id分组，每组取最新的一条记录
    # 子查询：每个turbine_id的最新时间戳
    subquery = db.query(
        WindSpeedData.turbine_id,
        func.max(WindSpeedData.timestamp).label('max_timestamp')
    ).filter(and_(
        WindSpeedData.farm_code == farm_code,
        WindSpeedData.timestamp >= time_window_start,
        WindSpeedData.timestamp <= time_window_end
    )).group_by(WindSpeedData.turbine_id).subquery()
    
    # 主查询：根据turbine_id和最新时间戳获取完整记录
    wind_speed_data = db.query(WindSpeedData)\
                       .join(subquery, and_(
                           WindSpeedData.turbine_id == subquery.c.turbine_id,
                           WindSpeedData.timestamp == subquery.c.max_timestamp
                       ))\
                       .filter(WindSpeedData.farm_code == farm_code)\
                       .order_by(WindSpeedData.turbine_id)\
                       .all()
    
    if wind_speed_data:
        result = []
        for data in wind_speed_data:
            result.append({
                'time': target_time.isoformat(),
                'turbine_id': data.turbine_id,
                'wind_speed': data.wind_speed,
                'wind_direction': data.wind_direction,
                'nacelle_position': data.nacelle_position,
                'actual_timestamp': data.timestamp.isoformat(),
                'data_source': 'database'
            })
        return result
    else:
        # 如果找不到指定时刻的数据，查询该场站有哪些风机（用于生成模板）
        turbine_list = db.query(WindSpeedData.turbine_id)\
                        .filter(WindSpeedData.farm_code == farm_code)\
                        .distinct()\
                        .order_by(WindSpeedData.turbine_id)\
                        .all()
        
        if turbine_list:
            # 根据该场站的风机列表生成模板数据
            result = []
            for turbine_data in turbine_list:
                result.append({
                    'time': target_time.isoformat(),
                    'turbine_id': turbine_data.turbine_id,
                    'wind_speed': 0,
                    'wind_direction': 0,
                    'nacelle_position': 0,
                    'data_source': 'template'
                })
            logging.info(f"未找到 {target_time} 时刻场站 {farm_code} 的风速数据，但根据该场站历史数据生成了 {len(result)} 台风机的模板")
            return result
        else:
            # 如果该场站完全没有历史数据，提供一个默认模板
            logging.warning(f"场站 {farm_code} 完全没有风速数据，提供默认模板")
            return [{
                'time': target_time.isoformat(),
                'turbine_id': 'WT01',
                'wind_speed': 0,
                'wind_direction': 0,
                'nacelle_position': 0,
                'data_source': 'template'
            }]

def get_turbine_power_data(db: Session, report_time: datetime = None, farm_code: str = None):
    """获取单机功率数据"""
    if report_time is None:
        report_time = datetime.now()
    if farm_code is None:
        return []
    
    # 移除时区信息进行本地时间查询
    if report_time.tzinfo is not None:
        report_time = report_time.replace(tzinfo=None)
    
    # 向前取整到15分钟边界
    minutes = (report_time.minute // 15) * 15
    target_time = report_time.replace(minute=minutes, second=0, microsecond=0)
    
    # 扩大查找窗口到±30分钟
    time_window_start = target_time - timedelta(minutes=30)
    time_window_end = target_time + timedelta(minutes=30)
    
    # 查询数据，按turbine_id分组，每组取最新的一条记录
    # 子查询：每个turbine_id的最新时间戳
    subquery = db.query(
        TurbinePowerData.turbine_id,
        func.max(TurbinePowerData.timestamp).label('max_timestamp')
    ).filter(and_(
        TurbinePowerData.farm_code == farm_code,
        TurbinePowerData.timestamp >= time_window_start,
        TurbinePowerData.timestamp <= time_window_end
    )).group_by(TurbinePowerData.turbine_id).subquery()
    
    # 主查询：根据turbine_id和最新时间戳获取完整记录
    turbine_power_data = db.query(TurbinePowerData)\
                          .join(subquery, and_(
                              TurbinePowerData.turbine_id == subquery.c.turbine_id,
                              TurbinePowerData.timestamp == subquery.c.max_timestamp
                          ))\
                          .filter(TurbinePowerData.farm_code == farm_code)\
                          .order_by(TurbinePowerData.turbine_id)\
                          .all()
    
    if turbine_power_data:
        result = []
        for data in turbine_power_data:
            result.append({
                'time': target_time.isoformat(),
                'turbine_id': data.turbine_id,
                'active_power': data.active_power,
                'reactive_power': data.reactive_power,
                'power_factor': data.power_factor,
                'rotor_speed': data.rotor_speed,
                'generator_speed': data.generator_speed,
                'blade_angle': data.blade_angle,
                'turbine_status': data.turbine_status,
                'actual_timestamp': data.timestamp.isoformat(),
                'data_source': 'database'
            })
        return result
    else:
        # 如果找不到指定时刻的数据，查询该场站有哪些风机（用于生成模板）
        turbine_list = db.query(TurbinePowerData.turbine_id)\
                        .filter(TurbinePowerData.farm_code == farm_code)\
                        .distinct()\
                        .order_by(TurbinePowerData.turbine_id)\
                        .all()
        
        if turbine_list:
            # 根据该场站的风机列表生成模板数据
            result = []
            for turbine_data in turbine_list:
                result.append({
                    'time': target_time.isoformat(),
                    'turbine_id': turbine_data.turbine_id,
                    'active_power': 0,
                    'reactive_power': 0,
                    'power_factor': 0,
                    'rotor_speed': 0,
                    'generator_speed': 0,
                    'blade_angle': 0,
                    'turbine_status': '正常',
                    'data_source': 'template'
                })
            logging.info(f"未找到 {target_time} 时刻场站 {farm_code} 的单机功率数据，但根据该场站历史数据生成了 {len(result)} 台风机的模板")
            return result
        else:
            # 如果该场站完全没有历史数据，提供一个默认模板
            logging.warning(f"场站 {farm_code} 完全没有单机功率数据，提供默认模板")
            return [{
                'time': target_time.isoformat(),
                'turbine_id': 'WT01',
                'active_power': 0,
                'reactive_power': 0,
                'power_factor': 0,
                'rotor_speed': 0,
                'generator_speed': 0,
                'blade_angle': 0,
                'turbine_status': '正常',
                'data_source': 'template'
            }]

def get_weather_data(db: Session, report_time: datetime = None, farm_code: str = None):
    """获取气象信息数据"""
    if report_time is None:
        report_time = datetime.now()
    if farm_code is None:
        return []
    
    # 移除时区信息进行本地时间查询
    if report_time.tzinfo is not None:
        report_time = report_time.replace(tzinfo=None)
    
    # 向前取整到15分钟边界
    minutes = (report_time.minute // 15) * 15
    target_time = report_time.replace(minute=minutes, second=0, microsecond=0)
    
    # 扩大查找窗口到±30分钟
    time_window_start = target_time - timedelta(minutes=30)
    time_window_end = target_time + timedelta(minutes=30)
    
    weather_data = db.query(WeatherData)\
                    .filter(and_(
                        WeatherData.farm_code == farm_code,
                        WeatherData.timestamp >= time_window_start,
                        WeatherData.timestamp <= time_window_end
                    ))\
                    .order_by(WeatherData.timestamp.desc())\
                    .first()
    
    if weather_data:
        return [{
            'time': target_time.isoformat(),
            'temperature': weather_data.temperature,
            'humidity': weather_data.humidity,
            'pressure': weather_data.pressure,
            'wind_speed_avg': weather_data.wind_speed_avg,
            'wind_speed_max': weather_data.wind_speed_max,
            'wind_direction': weather_data.wind_direction,
            'visibility': weather_data.visibility,
            'precipitation': weather_data.precipitation,
            'weather_condition': weather_data.weather_condition,
            'actual_timestamp': weather_data.timestamp.isoformat(),
            'data_source': 'database'
        }]
    else:
        # 如果还是找不到，尝试查询该场站的任意时间数据
        any_data = db.query(WeatherData)\
                    .filter(WeatherData.farm_code == farm_code)\
                    .order_by(WeatherData.timestamp.desc())\
                    .limit(3).all()
        
        if any_data:
            logging.warning(f"未找到 {target_time} 时刻场站 {farm_code} 的气象数据，但该场站有其他时间的数据")
            logging.info(f"该场站最新数据时间: {[d.timestamp for d in any_data]}")
        else:
            logging.warning(f"场站 {farm_code} 完全没有气象数据")
        return []

def get_installed_capacity_data(db: Session, report_time: datetime = None, farm_code: str = None):
    """获取装机容量数据"""
    if report_time is None:
        report_time = datetime.now()
    if farm_code is None:
        return []
    
    # 装机容量数据通常是静态的，取最新的记录
    capacity_data = db.query(InstalledCapacityData)\
                     .filter(InstalledCapacityData.farm_code == farm_code)\
                     .order_by(InstalledCapacityData.timestamp.desc())\
                     .first()
    
    if capacity_data:
        return [{
            'time': report_time.isoformat(),
            'total_capacity': capacity_data.total_capacity,
            'turbine_count': capacity_data.turbine_count,
            'turbine_capacity': capacity_data.turbine_capacity,
            'commissioning_date': capacity_data.commissioning_date.isoformat() if capacity_data.commissioning_date else None,
            'remarks': capacity_data.remarks,
            'actual_timestamp': capacity_data.timestamp.isoformat(),
            'data_source': 'database'
        }]
    else:
        logging.warning(f"未找到场站 {farm_code} 的装机容量数据")
        return []

def get_available_capacity_data(db: Session, report_time: datetime = None, farm_code: str = None):
    """获取可用容量数据"""
    if report_time is None:
        report_time = datetime.now()
    if farm_code is None:
        return []
    
    # 移除时区信息进行本地时间查询
    if report_time.tzinfo is not None:
        report_time = report_time.replace(tzinfo=None)
    
    # 向前取整到15分钟边界
    minutes = (report_time.minute // 15) * 15
    target_time = report_time.replace(minute=minutes, second=0, microsecond=0)
    
    # 扩大查找窗口到±30分钟
    time_window_start = target_time - timedelta(minutes=30)
    time_window_end = target_time + timedelta(minutes=30)
    
    capacity_data = db.query(AvailableCapacityData)\
                     .filter(and_(
                         AvailableCapacityData.farm_code == farm_code,
                         AvailableCapacityData.timestamp >= time_window_start,
                         AvailableCapacityData.timestamp <= time_window_end
                     ))\
                     .order_by(AvailableCapacityData.timestamp.desc())\
                     .first()
    
    if capacity_data:
        return [{
            'time': target_time.isoformat(),
            'available_capacity': capacity_data.available_capacity,
            'maintenance_capacity': capacity_data.maintenance_capacity,
            'fault_capacity': capacity_data.fault_capacity,
            'limited_capacity': capacity_data.limited_capacity,
            'availability_rate': capacity_data.availability_rate,
            'maintenance_turbines': capacity_data.maintenance_turbines,
            'fault_turbines': capacity_data.fault_turbines,
            'actual_timestamp': capacity_data.timestamp.isoformat(),
            'data_source': 'database'
        }]
    else:
        # 如果还是找不到，尝试查询该场站的任意时间数据
        any_data = db.query(AvailableCapacityData)\
                    .filter(AvailableCapacityData.farm_code == farm_code)\
                    .order_by(AvailableCapacityData.timestamp.desc())\
                    .limit(3).all()
        
        if any_data:
            logging.warning(f"未找到 {target_time} 时刻场站 {farm_code} 的可用容量数据，但该场站有其他时间的数据")
            logging.info(f"该场站最新数据时间: {[d.timestamp for d in any_data]}")
        else:
            logging.warning(f"场站 {farm_code} 完全没有可用容量数据")
        return []

def get_theoretical_power_data(db: Session, report_time: datetime = None, farm_code: str = None):
    """获取理论功率数据"""
    if report_time is None:
        report_time = datetime.now()
    if farm_code is None:
        return []
    
    # 移除时区信息进行本地时间查询
    if report_time.tzinfo is not None:
        report_time = report_time.replace(tzinfo=None)
    
    # 向前取整到15分钟边界
    minutes = (report_time.minute // 15) * 15
    target_time = report_time.replace(minute=minutes, second=0, microsecond=0)
    
    # 扩大查找窗口到±30分钟
    time_window_start = target_time - timedelta(minutes=30)
    time_window_end = target_time + timedelta(minutes=30)
    
    theoretical_data = db.query(TheoreticalPowerData)\
                        .filter(and_(
                            TheoreticalPowerData.farm_code == farm_code,
                            TheoreticalPowerData.timestamp >= time_window_start,
                            TheoreticalPowerData.timestamp <= time_window_end
                        ))\
                        .order_by(TheoreticalPowerData.timestamp.desc())\
                        .first()
    
    if theoretical_data:
        return [{
            'time': target_time.isoformat(),
            'theoretical_power': theoretical_data.theoretical_power,
            'wind_speed_hub': theoretical_data.wind_speed_hub,
            'air_density': theoretical_data.air_density,
            'power_curve_factor': theoretical_data.power_curve_factor,
            'wake_loss_factor': theoretical_data.wake_loss_factor,
            'availability_factor': theoretical_data.availability_factor,
            'actual_timestamp': theoretical_data.timestamp.isoformat(),
            'data_source': 'database'
        }]
    else:
        # 如果还是找不到，尝试查询该场站的任意时间数据
        any_data = db.query(TheoreticalPowerData)\
                    .filter(TheoreticalPowerData.farm_code == farm_code)\
                    .order_by(TheoreticalPowerData.timestamp.desc())\
                    .limit(3).all()
        
        if any_data:
            logging.warning(f"未找到 {target_time} 时刻场站 {farm_code} 的理论功率数据，但该场站有其他时间的数据")
            logging.info(f"该场站最新数据时间: {[d.timestamp for d in any_data]}")
        else:
            logging.warning(f"场站 {farm_code} 完全没有理论功率数据")
        return []

def get_available_power_data(db: Session, report_time: datetime = None, farm_code: str = None):
    """获取可用功率数据"""
    if report_time is None:
        report_time = datetime.now()
    if farm_code is None:
        return []
    
    # 移除时区信息进行本地时间查询
    if report_time.tzinfo is not None:
        report_time = report_time.replace(tzinfo=None)
    
    # 向前取整到15分钟边界
    minutes = (report_time.minute // 15) * 15
    target_time = report_time.replace(minute=minutes, second=0, microsecond=0)
    
    # 扩大查找窗口到±30分钟
    time_window_start = target_time - timedelta(minutes=30)
    time_window_end = target_time + timedelta(minutes=30)
    
    available_data = db.query(AvailablePowerData)\
                      .filter(and_(
                          AvailablePowerData.farm_code == farm_code,
                          AvailablePowerData.timestamp >= time_window_start,
                          AvailablePowerData.timestamp <= time_window_end
                      ))\
                      .order_by(AvailablePowerData.timestamp.desc())\
                      .first()
    
    if available_data:
        return [{
            'time': target_time.isoformat(),
            'available_power': available_data.available_power,
            'grid_constraint': available_data.grid_constraint,
            'environmental_constraint': available_data.environmental_constraint,
            'maintenance_constraint': available_data.maintenance_constraint,
            'operational_constraint': available_data.operational_constraint,
            'grid_availability': available_data.grid_availability,
            'constraint_reason': available_data.constraint_reason,
            'actual_timestamp': available_data.timestamp.isoformat(),
            'data_source': 'database'
        }]
    else:
        # 如果还是找不到，尝试查询该场站的任意时间数据
        any_data = db.query(AvailablePowerData)\
                    .filter(AvailablePowerData.farm_code == farm_code)\
                    .order_by(AvailablePowerData.timestamp.desc())\
                    .limit(3).all()
        
        if any_data:
            logging.warning(f"未找到 {target_time} 时刻场站 {farm_code} 的可用功率数据，但该场站有其他时间的数据")
            logging.info(f"该场站最新数据时间: {[d.timestamp for d in any_data]}")
        else:
            logging.warning(f"场站 {farm_code} 完全没有可用功率数据")
        return []

def send_report_data(config: ReportConfig, data, farm_code: str):
    """发送上报数据"""
    # 使用配置中的target_path，如果没有则默认使用/receive-data
    target_path = getattr(config, 'target_path', '/receive-data') or '/receive-data'
    url = f"http://{config.target_ip}:{config.target_port}{target_path}"
    
    payload = {
        'report_type': config.report_type,
        'timestamp': datetime.now().isoformat(),
        'farm_code': farm_code,
        'data': data
    }
    
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=config.timeout_seconds
    )
    
    response.raise_for_status()
    return response

def check_and_execute_scheduled_reports():
    """
    检查所有启用的配置并执行需要上报的任务.
    由cron调度器在 :14:45, :29:45, :44:45, :59:45 触发.
    此函数通过为每个任务使用独立的、短暂的事务和数据库锁来确保健壮性.
    """
    now = datetime.now()
    logging.info(f"Cron job triggered at {now.strftime('%Y-%m-%d %H:%M:%S')}. Finding unique tasks.")

    unique_tasks = []
    try:
        # 步骤1: 在一个短暂的事务中，获取所有需要执行的任务并去重
        with db_session() as db:
            all_enabled_configs = db.query(
                ReportConfig.id,
                ReportConfig.farm_id,
                ReportConfig.report_type
            ).filter(ReportConfig.is_enabled == True).order_by(ReportConfig.created_at).all()

            processed_keys = set()
            for config_id, farm_id, report_type in all_enabled_configs:
                key = (farm_id, report_type)
                if key not in processed_keys:
                    processed_keys.add(key)
                    unique_tasks.append(config_id)
        logging.info(f"Found {len(unique_tasks)} unique tasks to process.")
    except Exception as e:
        logging.error(f"Error while fetching tasks for scheduler: {e}")
        return

    # 步骤2: 遍历去重后的任务列表，为每个任务开启独立的事务
    for config_id in unique_tasks:
        try:
            # 为每个任务使用独立的事务和会话
            with db_session() as db:
                # 步骤3: 使用行锁锁定配置，防止多进程并发执行同一任务
                config = db.query(ReportConfig).filter(ReportConfig.id == config_id).with_for_update().first()

                # 检查配置是否在查询后被禁用或删除
                if not config or not config.is_enabled:
                    logging.info(f"Skipping config_id {config_id}: no longer enabled or exists.")
                    continue

                # 步骤4: 防重放检查，这是在获得锁之后最关键的一步
                if config.last_report_time and (now - config.last_report_time).total_seconds() < 60:
                    logging.warning(f"Skipping config_id {config_id}: Already reported at {config.last_report_time} by another process.")
                    continue
                
                # 步骤5: 执行上报
                farm = db.query(WindFarm).filter(WindFarm.id == config.farm_id).first()
                if farm:
                    logging.info(f"Processing report for farm '{farm.farm_name}' (config_id: {config.id})")
                    execute_report(db, config)
                else:
                    logging.error(f"Could not find farm for config_id {config.id}")
            
            # 事务在此处成功提交，锁被释放
            
        except Exception as e:
            # 如果在处理单个任务时发生任何错误（包括获取锁超时），记录日志并继续下一个
            logging.error(f"Failed to execute report for config_id {config_id}. Error: {e}", exc_info=True)
            # 事务在此处自动回滚，锁被释放

def start_report_scheduler():
    """启动上报调度器"""
    try:
        # 避免重复启动
        if report_scheduler.running:
            logging.info("上报调度器已在运行，跳过启动")
            return
            
        # 使用CRON模式精确调度
        report_scheduler.add_job(
            check_and_execute_scheduled_reports,
            'cron',
            minute='14,29,44,59',
            second='45',
            id='report_scheduler_cron',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=30
        )
        
        report_scheduler.start()
        logging.info("上报调度器启动成功 - 使用CRON模式")
        logging.info("上报时间点: XX:14:45, XX:29:45, XX:44:45, XX:59:45")
        
        # 注册程序退出时的清理函数
        atexit.register(lambda: report_scheduler.shutdown())
        
    except Exception as e:
        logging.error(f"启动上报调度器失败: {str(e)}")

def stop_report_scheduler():
    """停止上报调度器"""
    try:
        if report_scheduler.running:
            report_scheduler.shutdown()
            logging.info("上报调度器已停止")
    except Exception as e:
        logging.error(f"停止上报调度器时出错: {str(e)}")

# 添加控制调度器的API接口
@report_management_bp.route('/scheduler/start', methods=['POST'])
def start_scheduler():
    """启动上报调度器"""
    try:
        if not report_scheduler.running:
            start_report_scheduler()
            return jsonify({'message': '上报调度器启动成功'})
        else:
            return jsonify({'message': '上报调度器已在运行中'})
    except Exception as e:
        logging.error(f"启动调度器失败: {str(e)}")
        return jsonify({'error': '启动调度器失败'}), 500

@report_management_bp.route('/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """停止上报调度器"""
    try:
        stop_report_scheduler()
        return jsonify({'message': '上报调度器已停止'})
    except Exception as e:
        logging.error(f"停止调度器失败: {str(e)}")
        return jsonify({'error': '停止调度器失败'}), 500

@report_management_bp.route('/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """获取调度器状态"""
    try:
        status = {
            'running': report_scheduler.running if report_scheduler else False,
            'next_report_times': get_next_report_times()
        }
        return jsonify(status)
    except Exception as e:
        logging.error(f"获取调度器状态失败: {str(e)}")
        return jsonify({'error': '获取调度器状态失败'}), 500

def get_next_report_times():
    """获取接下来的上报时间点"""
    now = datetime.now()
    
    # 15分钟整点提前15秒的时间点
    report_minutes = [14, 29, 44, 59]
    next_times = []
    
    for minute in report_minutes:
        if minute > now.minute or (minute == now.minute and now.second < 45):
            # 当前小时的时间
            next_time = now.replace(minute=minute, second=45, microsecond=0)
            next_times.append(next_time.strftime('%H:%M:%S'))
    
    # 如果当前小时没有找到合适的时间点，则取下一小时的时间点
    if not next_times:
        next_hour = now.hour + 1 if now.hour < 23 else 0
        # 添加下一小时的第一个时间点
        next_time = now.replace(hour=next_hour, minute=14, second=45, microsecond=0)
        next_times.append(next_time.strftime('%H:%M:%S'))
        # 如果需要第二个时间点
        if len(next_times) < 2:
            next_time = now.replace(hour=next_hour, minute=29, second=45, microsecond=0)
            next_times.append(next_time.strftime('%H:%M:%S'))
    elif len(next_times) == 1:
        # 如果当前小时只找到一个时间点，补充下一小时的第一个时间点
        next_hour = now.hour + 1 if now.hour < 23 else 0
        next_time = now.replace(hour=next_hour, minute=14, second=45, microsecond=0)
        next_times.append(next_time.strftime('%H:%M:%S'))
    
    return next_times[:1]  # 只返回最近的一个时间点

def get_data_structure_info(report_type):
    """获取不同上报类型的数据结构信息"""
    if report_type == 'actual':
        return {
            'columns': [
                {'key': 'time', 'label': '时间', 'type': 'datetime', 'editable': True},
                {'key': 'value', 'label': '实际功率(MW)', 'type': 'number', 'editable': True},
                {'key': 'data_source', 'label': '数据来源', 'type': 'text', 'editable': False}
            ],
            'supports_bulk_edit': True
        }
    elif report_type == 'forecast_short':
        columns = [
            {'key': 'time', 'label': '时间', 'type': 'datetime', 'editable': True},
            {'key': 'data_source', 'label': '数据来源', 'type': 'text', 'editable': False}
        ]
        # 添加16个预测值列（对应数据库字段wp_pred2-wp_pred17）
        for i in range(2, 18):
            pred_index = i - 1  # 显示为预测1-16，但对应wp_pred2-17
            columns.append({
                'key': f'wp_pred{i}', 
                'label': f'预测{pred_index}(MW)', 
                'type': 'number', 
                'editable': True
            })
        return {
            'columns': columns,
            'supports_bulk_edit': True
        }
    elif report_type == 'forecast_long':
        return {
            'columns': [
                {'key': 'time', 'label': '时间', 'type': 'datetime', 'editable': True},
                {'key': 'value', 'label': '预测功率(MW)', 'type': 'number', 'editable': True},
                {'key': 'data_source', 'label': '数据来源', 'type': 'text', 'editable': False}
            ],
            'supports_bulk_edit': True
        }
    elif report_type == 'wind_speed':
        return {
            'columns': [
                {'key': 'time', 'label': '时间', 'type': 'datetime', 'editable': True},
                {'key': 'turbine_id', 'label': '机组编号', 'type': 'text', 'editable': True},
                {'key': 'wind_speed', 'label': '风速(m/s)', 'type': 'number', 'editable': True},
                {'key': 'wind_direction', 'label': '风向(度)', 'type': 'number', 'editable': True},
                {'key': 'nacelle_position', 'label': '机舱位置(度)', 'type': 'number', 'editable': True},
                {'key': 'data_source', 'label': '数据来源', 'type': 'text', 'editable': False}
            ],
            'supports_bulk_edit': True
        }
    elif report_type == 'turbine_power':
        return {
            'columns': [
                {'key': 'time', 'label': '时间', 'type': 'datetime', 'editable': True},
                {'key': 'turbine_id', 'label': '机组编号', 'type': 'text', 'editable': True},
                {'key': 'active_power', 'label': '有功功率(kW)', 'type': 'number', 'editable': True},
                {'key': 'reactive_power', 'label': '无功功率(kVar)', 'type': 'number', 'editable': True},
                {'key': 'power_factor', 'label': '功率因数', 'type': 'number', 'editable': True},
                {'key': 'turbine_status', 'label': '机组状态', 'type': 'text', 'editable': True},
                {'key': 'data_source', 'label': '数据来源', 'type': 'text', 'editable': False}
            ],
            'supports_bulk_edit': True
        }
    elif report_type == 'weather':
        return {
            'columns': [
                {'key': 'time', 'label': '时间', 'type': 'datetime', 'editable': True},
                {'key': 'temperature', 'label': '温度(℃)', 'type': 'number', 'editable': True},
                {'key': 'humidity', 'label': '湿度(%)', 'type': 'number', 'editable': True},
                {'key': 'pressure', 'label': '气压(hPa)', 'type': 'number', 'editable': True},
                {'key': 'wind_speed_avg', 'label': '平均风速(m/s)', 'type': 'number', 'editable': True},
                {'key': 'weather_condition', 'label': '天气状况', 'type': 'text', 'editable': True},
                {'key': 'data_source', 'label': '数据来源', 'type': 'text', 'editable': False}
            ],
            'supports_bulk_edit': True
        }
    elif report_type == 'installed_capacity':
        return {
            'columns': [
                {'key': 'time', 'label': '时间', 'type': 'datetime', 'editable': True},
                {'key': 'total_capacity', 'label': '总装机容量(MW)', 'type': 'number', 'editable': True},
                {'key': 'turbine_count', 'label': '风机数量', 'type': 'number', 'editable': True},
                {'key': 'turbine_capacity', 'label': '单机容量(MW)', 'type': 'number', 'editable': True},
                {'key': 'data_source', 'label': '数据来源', 'type': 'text', 'editable': False}
            ],
            'supports_bulk_edit': True
        }
    elif report_type == 'available_capacity':
        return {
            'columns': [
                {'key': 'time', 'label': '时间', 'type': 'datetime', 'editable': True},
                {'key': 'available_capacity', 'label': '可用容量(MW)', 'type': 'number', 'editable': True},
                {'key': 'maintenance_capacity', 'label': '检修容量(MW)', 'type': 'number', 'editable': True},
                {'key': 'fault_capacity', 'label': '故障容量(MW)', 'type': 'number', 'editable': True},
                {'key': 'availability_rate', 'label': '可用率(%)', 'type': 'number', 'editable': True},
                {'key': 'data_source', 'label': '数据来源', 'type': 'text', 'editable': False}
            ],
            'supports_bulk_edit': True
        }
    elif report_type == 'theoretical_power':
        return {
            'columns': [
                {'key': 'time', 'label': '时间', 'type': 'datetime', 'editable': True},
                {'key': 'theoretical_power', 'label': '理论功率(MW)', 'type': 'number', 'editable': True},
                {'key': 'wind_speed_hub', 'label': '轮毂风速(m/s)', 'type': 'number', 'editable': True},
                {'key': 'air_density', 'label': '空气密度(kg/m³)', 'type': 'number', 'editable': True},
                {'key': 'data_source', 'label': '数据来源', 'type': 'text', 'editable': False}
            ],
            'supports_bulk_edit': True
        }
    elif report_type == 'available_power':
        return {
            'columns': [
                {'key': 'time', 'label': '时间', 'type': 'datetime', 'editable': True},
                {'key': 'available_power', 'label': '可用功率(MW)', 'type': 'number', 'editable': True},
                {'key': 'grid_constraint', 'label': '电网约束(MW)', 'type': 'number', 'editable': True},
                {'key': 'environmental_constraint', 'label': '环境约束(MW)', 'type': 'number', 'editable': True},
                {'key': 'grid_availability', 'label': '电网可用率(%)', 'type': 'number', 'editable': True},
                {'key': 'data_source', 'label': '数据来源', 'type': 'text', 'editable': False}
            ],
            'supports_bulk_edit': True
        }
    else:
        return {
            'columns': [],
            'supports_bulk_edit': False
        }

# ========== 数据质量统计相关接口 ==========

@report_management_bp.route('/statistics', methods=['GET'])
def get_report_statistics():
    """获取上报数据质量统计 - 按类型分别统计"""
    try:
        farm_code = request.args.get('farm_code')
        month_str = request.args.get('month')

        # 使用with语句获取数据库会话
        with db_session() as session:
            # 基础查询
            query = session.query(ReportQualityStatistics)

            # 按场站筛选
            if farm_code:
                query = query.filter(ReportQualityStatistics.farm_code == farm_code)

            # --- 今日统计 ---
            today = datetime.utcnow().date()
            today_stats_query = query.filter(ReportQualityStatistics.date == today)
            
            # 直接计算总的加权平均
            today_summary_res = today_stats_query.with_entities(
                func.sum(ReportQualityStatistics.completeness_rate * ReportQualityStatistics.total_reports) / func.sum(ReportQualityStatistics.total_reports),
                func.sum(ReportQualityStatistics.timeliness_rate * ReportQualityStatistics.total_reports) / func.sum(ReportQualityStatistics.total_reports)
            ).first()

            today_stats_summary = {
                "completeness_rate": today_summary_res[0] if today_summary_res and today_summary_res[0] is not None else 0,
                "timeliness_rate": today_summary_res[1] if today_summary_res and today_summary_res[1] is not None else 0,
            }

            # --- 月度统计 ---
            if month_str:
                year, month = map(int, month_str.split('-'))
                start_date = date(year, month, 1)
                end_date = (start_date + timedelta(days=31)).replace(day=1) - timedelta(days=1)
            else:
                today = datetime.utcnow().date()
                start_date = today.replace(day=1)
                end_date = (start_date + timedelta(days=31)).replace(day=1) - timedelta(days=1)
                
            monthly_query = query.filter(ReportQualityStatistics.date.between(start_date, end_date))

            # 按日期和场站分组计算每日统计
            daily_stats_query = monthly_query.group_by(
                ReportQualityStatistics.date, 
                ReportQualityStatistics.farm_code
            ).with_entities(
                ReportQualityStatistics.date,
                ReportQualityStatistics.farm_code,
                func.sum(ReportQualityStatistics.completeness_rate * ReportQualityStatistics.total_reports) / func.sum(ReportQualityStatistics.total_reports),
                func.sum(ReportQualityStatistics.timeliness_rate * ReportQualityStatistics.total_reports) / func.sum(ReportQualityStatistics.total_reports),
                func.group_concat(ReportQualityStatistics.notes.distinct()).label('notes')
            ).order_by(ReportQualityStatistics.date.desc())

            daily_stats = []
            # 获取所有相关配置以查询类型
            configs = session.query(ReportConfig).all()
            config_map = {c.id: c for c in configs}

            for row in daily_stats_query.all():
                date_val, farm_code_val, completeness, timeliness, notes = row
                
                # 获取当天的类型详情
                types_query = session.query(ReportLog).filter(
                    func.date(ReportLog.report_time) == date_val,
                    ReportLog.farm_code == farm_code_val
                ).group_by(ReportLog.report_type).with_entities(
                    ReportLog.report_type,
                    func.avg(ReportLog.data_completeness_rate) * 100
                ).all()

                types_data = {}
                for type_result in types_query:
                    report_type = type_result[0]
                    avg_completeness = type_result[1] if type_result[1] is not None else 0
                    
                    # 计算该类型的及时率 - 需要单独查询所有日志进行计算
                    type_logs = session.query(ReportLog).filter(
                        func.date(ReportLog.report_time) == date_val,
                        ReportLog.farm_code == farm_code_val,
                        ReportLog.report_type == report_type
                    ).all()
                    
                    # 使用现有的及时性计算函数
                    on_time_count = 0
                    total_count = len(type_logs)
                    
                    for log in type_logs:
                        if check_report_timeliness(log.report_time, log.report_time):
                            on_time_count += 1
                    
                    timeliness_rate = (on_time_count / total_count * 100) if total_count > 0 else 0
                    
                    types_data[report_type] = {
                        "completeness_rate": avg_completeness,
                        "timeliness_rate": timeliness_rate
                    }

                daily_stats.append({
                    "date": date_val,
                    "farm_code": farm_code_val,
                    "farm_name": get_farm_name(session, farm_code_val),
                    "overall_completeness_rate": completeness if completeness is not None else 0,
                    "overall_timeliness_rate": timeliness if timeliness is not None else 0,
                    "types": types_data,
                    "notes": notes
                })

            # 计算月度总结
            monthly_summary_res = monthly_query.with_entities(
                 func.sum(ReportQualityStatistics.completeness_rate * ReportQualityStatistics.total_reports) / func.sum(ReportQualityStatistics.total_reports),
                 func.sum(ReportQualityStatistics.timeliness_rate * ReportQualityStatistics.total_reports) / func.sum(ReportQualityStatistics.total_reports)
            ).first()

            monthly_summary = {
                "completeness_rate": monthly_summary_res[0] if monthly_summary_res and monthly_summary_res[0] is not None else 0,
                "timeliness_rate": monthly_summary_res[1] if monthly_summary_res and monthly_summary_res[1] is not None else 0
            }

            return jsonify({
                "today_stats": today_stats_summary,
                "monthly_summary": monthly_summary,
                "daily_stats": daily_stats
            })
            
    except Exception as e:
        logging.error(f"获取上报统计数据失败: {e}", exc_info=True)
        return jsonify({"error": "获取统计数据失败"}), 500

def get_farm_name(session, farm_code: str):
    """根据场站编码获取场站名称"""
    try:
        farm = session.query(WindFarm).filter(WindFarm.farm_code == farm_code).first()
        return farm.farm_name if farm else farm_code
    except Exception as e:
        logging.error(f"获取场站名称失败: {e}")
        return farm_code

def calculate_real_time_statistics_by_type(db: Session, farm_code: str = None, date: str = None):
    """实时计算当日统计数据 - 按类型分别计算"""
    try:
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # 查询当日上报日志
        start_time = datetime.strptime(date, '%Y-%m-%d')
        end_time = start_time + timedelta(days=1)
        
        query = db.query(ReportLog).filter(
            and_(
                ReportLog.report_time >= start_time,
                ReportLog.report_time < end_time
            )
        )
        
        if farm_code:
            query = query.filter(ReportLog.farm_code == farm_code)
        
        logs = query.all()
        
        if not logs:
            return {'completeness_rate': None, 'timeliness_rate': None, 'types': {}}
        
        # 按类型分组计算
        type_stats = {}
        total_completeness = 0
        total_timeliness = 0
        total_weight = 0
        
        # 按上报类型分组
        type_logs = {}
        for log in logs:
            report_type = log.report_type
            if report_type not in type_logs:
                type_logs[report_type] = []
            type_logs[report_type].append(log)
        
        # 计算每种类型的统计
        for report_type, type_log_list in type_logs.items():
            total_reports = len(type_log_list)
            
            # 使用日志中保存的完整率，如果没有则使用兼容模式
            total_completeness_rate = 0.0
            complete_reports_count = 0
            
            for log in type_log_list:
                if log.data_completeness_rate is not None:
                    # 新版本：使用保存的完整率
                    total_completeness_rate += log.data_completeness_rate
                    if log.data_completeness_rate > 0:
                        complete_reports_count += 1
                else:
                    # 兼容模式：使用旧的判断逻辑（历史数据）
                    if log.status == 'success' and log.data_count > 0:
                        total_completeness_rate += 1.0  # 假设为100%完整
                        complete_reports_count += 1
            
            # 计算平均完整率
            completeness_rate = (total_completeness_rate / total_reports * 100) if total_reports > 0 else 0
            
            # 计算及时率
            on_time_reports = calculate_on_time_reports(type_log_list)
            timeliness_rate = (on_time_reports / total_reports * 100) if total_reports > 0 else 0
            
            type_stats[report_type] = {
                'completeness_rate': round(completeness_rate, 2),
                'timeliness_rate': round(timeliness_rate, 2)
            }
            
            # 累计总体统计（加权平均）
            weight = total_reports
            total_completeness += completeness_rate * weight
            total_timeliness += timeliness_rate * weight
            total_weight += weight
        
        # 计算总体统计
        overall_completeness = round(total_completeness / total_weight, 2) if total_weight > 0 else 0
        overall_timeliness = round(total_timeliness / total_weight, 2) if total_weight > 0 else 0
        
        return {
            'completeness_rate': overall_completeness,
            'timeliness_rate': overall_timeliness,
            'types': type_stats
        }
        
    except Exception as e:
        logging.error(f"实时计算统计数据失败: {str(e)}")
        return {'completeness_rate': None, 'timeliness_rate': None, 'types': {}}

def calculate_on_time_reports(logs):
    """计算及时上报的数量 - 只有在截止时间前才算及时"""
    on_time_count = 0
    
    for log in logs:
        # 对于历史数据，无法获取准确的数据时间戳，使用兼容模式
        # 假设上报时间就是数据时间戳（这是历史数据的最佳估计）
        if check_report_timeliness(log.report_time, log.report_time):
            on_time_count += 1
    
    return on_time_count

def calculate_monthly_summary_by_type(db: Session, farm_code: str = None, month: str = None):
    """计算月度汇总统计 - 按类型分别计算"""
    try:
        if not month:
            month = datetime.now().strftime('%Y-%m')
        
        query = db.query(ReportQualityStatistics).filter(ReportQualityStatistics.date.like(f'{month}%'))
        
        if farm_code:
            query = query.filter(ReportQualityStatistics.farm_code == farm_code)
        
        records = query.all()
        
        if not records:
            return {
                'completeness_rate': 0.0,
                'timeliness_rate': 0.0,
                'total_reports': 0,
                'on_time_reports': 0,
                'types': {}
            }
        
        # 按类型分组计算
        type_stats = {}
        total_completeness = 0
        total_timeliness = 0
        total_weight = 0
        total_reports_all = 0
        total_on_time_all = 0
        
        # 按上报类型分组
        type_records = {}
        for record in records:
            report_type = record.report_type
            if report_type not in type_records:
                type_records[report_type] = []
            type_records[report_type].append(record)
        
        # 计算每种类型的月度统计
        for report_type, type_record_list in type_records.items():
            type_total_completeness = 0
            type_total_timeliness = 0
            type_total_weight = 0
            type_total_reports = 0
            type_total_on_time = 0
            
            for record in type_record_list:
                weight = record.total_reports
                type_total_completeness += record.completeness_rate * weight
                type_total_timeliness += record.timeliness_rate * weight
                type_total_weight += weight
                type_total_reports += record.total_reports
                type_total_on_time += record.on_time_reports
            
            if type_total_weight > 0:
                type_completeness = round(type_total_completeness / type_total_weight, 2)
                type_timeliness = round(type_total_timeliness / type_total_weight, 2)
            else:
                type_completeness = 0.0
                type_timeliness = 0.0
            
            type_stats[report_type] = {
                'completeness_rate': type_completeness,
                'timeliness_rate': type_timeliness,
                'total_reports': type_total_reports,
                'on_time_reports': type_total_on_time
            }
            
            # 累计总体统计
            total_completeness += type_total_completeness
            total_timeliness += type_total_timeliness
            total_weight += type_total_weight
            total_reports_all += type_total_reports
            total_on_time_all += type_total_on_time
        
        # 计算总体月度统计
        overall_completeness = round(total_completeness / total_weight, 2) if total_weight > 0 else 0.0
        overall_timeliness = round(total_timeliness / total_weight, 2) if total_weight > 0 else 0.0
        
        return {
            'completeness_rate': overall_completeness,
            'timeliness_rate': overall_timeliness,
            'total_reports': total_reports_all,
            'on_time_reports': total_on_time_all,
            'types': type_stats
        }
             
    except Exception as e:
        logging.error(f"计算月度汇总失败: {str(e)}")
        return {
            'completeness_rate': 0.0,
            'timeliness_rate': 0.0,
            'total_reports': 0,
            'on_time_reports': 0,
            'types': {}
        }

@report_management_bp.route('/statistics/calculate-daily', methods=['POST'])
def calculate_daily_statistics():
    """手动触发计算每日统计数据"""
    try:
        data = request.get_json()
        target_date = data.get('date', (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
        
        with db_session() as db:
            # 获取所有场站
            farms = db.query(WindFarm).filter(WindFarm.is_active == True).all()
            
            results = []
            for farm in farms:
                result = update_daily_statistics(db, farm.farm_code, target_date)
                results.append({
                    'farm_code': farm.farm_code,
                    'farm_name': farm.farm_name,
                    'date': target_date,
                    'result': result
                })
            
            return jsonify({
                'message': f'完成{target_date}的统计计算',
                'results': results
            })
            
    except Exception as e:
        logging.error(f"计算每日统计失败: {str(e)}")
        return jsonify({'error': '计算每日统计失败'}), 500

def update_daily_statistics(db: Session, farm_code: str, date: str):
    """更新指定场站和日期的统计数据 - 按类型分别统计"""
    try:
        # 查询当日上报日志
        start_time = datetime.strptime(date, '%Y-%m-%d')
        end_time = start_time + timedelta(days=1)
        
        logs = db.query(ReportLog).filter(
            and_(
                ReportLog.farm_code == farm_code,
                ReportLog.report_time >= start_time,
                ReportLog.report_time < end_time
            )
        ).all()
        
        # 按上报类型分组
        type_logs = {}
        for log in logs:
            report_type = log.report_type
            if report_type not in type_logs:
                type_logs[report_type] = []
            type_logs[report_type].append(log)
        
        results = {}
        
        # 为每种上报类型分别计算和更新统计
        for report_type, type_log_list in type_logs.items():
            total_reports = len(type_log_list)
            
            # 使用日志中保存的完整率，如果没有则使用兼容模式
            total_completeness_rate = 0.0
            complete_reports_count = 0
            
            for log in type_log_list:
                if log.data_completeness_rate is not None:
                    # 新版本：使用保存的完整率
                    total_completeness_rate += log.data_completeness_rate
                    if log.data_completeness_rate > 0:
                        complete_reports_count += 1
                else:
                    # 兼容模式：使用旧的判断逻辑（历史数据）
                    if log.status == 'success' and log.data_count > 0:
                        total_completeness_rate += 1.0  # 假设为100%完整
                        complete_reports_count += 1
            
            # 计算平均完整率
            completeness_rate = (total_completeness_rate / total_reports * 100) if total_reports > 0 else 0
            
            # 计算及时率
            on_time_reports = calculate_on_time_reports(type_log_list)
            timeliness_rate = (on_time_reports / total_reports * 100) if total_reports > 0 else 0
            
            # 生成备注
            notes = []
            successful_count = len([log for log in type_log_list if log.status == 'success'])
            if total_reports == 0:
                notes.append("无上报记录")
            elif successful_count < total_reports:
                failed_count = total_reports - successful_count
                notes.append(f"{failed_count}次上报失败")
            elif on_time_reports < total_reports:
                delay_count = total_reports - on_time_reports
                notes.append(f"{delay_count}次上报延迟")
            else:
                notes.append("所有上报均正常")
            
            # 检查是否已存在该类型的记录
            existing = db.query(ReportQualityStatistics).filter(
                and_(
                    ReportQualityStatistics.farm_code == farm_code,
                    ReportQualityStatistics.report_type == report_type,
                    ReportQualityStatistics.date == date
                )
            ).first()
            
            if existing:
                # 更新现有记录
                existing.completeness_rate = completeness_rate
                existing.timeliness_rate = timeliness_rate
                existing.total_reports = total_reports
                existing.on_time_reports = on_time_reports
                existing.notes = '; '.join(notes)
                existing.updated_at = datetime.now()
            else:
                # 创建新记录
                new_stat = ReportQualityStatistics(
                    farm_code=farm_code,
                    report_type=report_type,
                    date=date,
                    completeness_rate=completeness_rate,
                    timeliness_rate=timeliness_rate,
                    total_reports=total_reports,
                    on_time_reports=on_time_reports,
                    notes='; '.join(notes)
                )
                db.add(new_stat)
            
            results[report_type] = {
                'completeness_rate': round(completeness_rate, 2),
                'timeliness_rate': round(timeliness_rate, 2),
                'total_reports': total_reports
            }
        
        db.commit()
        
        return {
            'success': True,
            'types': results,
            'total_types': len(results)
        }
        
    except Exception as e:
        logging.error(f"更新{farm_code}在{date}的统计数据失败: {str(e)}")
        return {'success': False, 'error': str(e)}

# 在模块加载时自动启动调度器
try:
    start_report_scheduler()
except Exception as e:
    logging.error(f"自动启动上报调度器失败: {str(e)}")

@report_management_bp.route('/statistics/test-update', methods=['POST'])
def test_statistics_update():
    """测试统计更新功能"""
    try:
        data = request.get_json() or {}
        farm_code = data.get('farm_code', 'TEST001')
        
        with db_session() as db:
            # 模拟一次成功的上报
            current_time = datetime.now()
            update_quality_statistics_async(db, farm_code, current_time, 1.0, True, 'actual')
            db.commit()
            
            # 查询更新后的统计
            today_date = current_time.strftime('%Y-%m-%d')
            stats = db.query(ReportQualityStatistics).filter(
                and_(
                    ReportQualityStatistics.farm_code == farm_code,
                    ReportQualityStatistics.date == today_date
                )
            ).all()
            
            if stats:
                results = []
                for stat in stats:
                    results.append({
                        'farm_code': stat.farm_code,
                        'report_type': stat.report_type,
                        'date': stat.date,
                        'total_reports': stat.total_reports,
                        'on_time_reports': stat.on_time_reports,
                        'completeness_rate': stat.completeness_rate,
                        'timeliness_rate': stat.timeliness_rate,
                        'notes': stat.notes
                    })
                
                result = {
                    'success': True,
                    'statistics': results,
                    'total_types': len(results)
                }
            else:
                result = {'success': False, 'message': '未找到统计记录'}
            
            return jsonify(result)
            
    except Exception as e:
        logging.error(f"测试统计更新失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def check_data_completeness(data, report_type):
    """检查数据完整性 - 计算非空数据占总数据的比例"""
    if not data or len(data) == 0:
        return 0.0  # 返回完整性比例而不是布尔值
    
    try:
        total_values = 0
        valid_values = 0
        
        if report_type == 'actual':
            # 实际功率：计算所有功率值中非空的比例
            # 支持两种字段名：wp_true（数据库格式）和value（前端格式）
            for item in data:
                total_values += 1
                # 检查wp_true或value字段（优先wp_true，兼容value）
                power_value = item.get('wp_true')
                if power_value is None:
                    power_value = item.get('value')
                if power_value is not None:
                    valid_values += 1
                    
        elif report_type == 'forecast_short':
            # 超短期预测：计算所有预测值中非空的比例
            for item in data:
                # 检查wp_pred2到wp_pred17（数据库实际字段为wp_pred2-wp_pred17）
                for i in range(2, 18):
                    total_values += 1
                    if item.get(f'wp_pred{i}') is not None:
                        valid_values += 1
                        
        elif report_type == 'forecast_long':
            # 长期预测：计算所有预测值中非空的比例
            for item in data:
                total_values += 1
                if item.get('value') is not None:
                    valid_values += 1
                    
        elif report_type == 'wind_speed':
            # 单机风速：计算主要字段的完整性
            for item in data:
                total_values += 3  # 检查风速、风向、机舱位置
                if item.get('wind_speed') is not None:
                    valid_values += 1
                if item.get('wind_direction') is not None:
                    valid_values += 1
                if item.get('nacelle_position') is not None:
                    valid_values += 1
                    
        elif report_type == 'turbine_power':
            # 单机功率：计算主要字段的完整性
            for item in data:
                total_values += 3  # 检查有功功率、无功功率、功率因数
                if item.get('active_power') is not None:
                    valid_values += 1
                if item.get('reactive_power') is not None:
                    valid_values += 1
                if item.get('power_factor') is not None:
                    valid_values += 1
                    
        elif report_type == 'weather':
            # 气象信息：计算主要字段的完整性
            for item in data:
                total_values += 4  # 检查温度、湿度、气压、平均风速
                if item.get('temperature') is not None:
                    valid_values += 1
                if item.get('humidity') is not None:
                    valid_values += 1
                if item.get('pressure') is not None:
                    valid_values += 1
                if item.get('wind_speed_avg') is not None:
                    valid_values += 1
                    
        elif report_type == 'installed_capacity':
            # 装机容量：计算主要字段的完整性
            for item in data:
                total_values += 3  # 检查总容量、风机数量、单机容量
                if item.get('total_capacity') is not None:
                    valid_values += 1
                if item.get('turbine_count') is not None:
                    valid_values += 1
                if item.get('turbine_capacity') is not None:
                    valid_values += 1
                    
        elif report_type == 'available_capacity':
            # 可用容量：计算主要字段的完整性
            for item in data:
                total_values += 2  # 检查可用容量、可用率
                if item.get('available_capacity') is not None:
                    valid_values += 1
                if item.get('availability_rate') is not None:
                    valid_values += 1
                    
        elif report_type == 'theoretical_power':
            # 理论功率：计算主要字段的完整性
            for item in data:
                total_values += 3  # 检查理论功率、轮毂风速、空气密度
                if item.get('theoretical_power') is not None:
                    valid_values += 1
                if item.get('wind_speed_hub') is not None:
                    valid_values += 1
                if item.get('air_density') is not None:
                    valid_values += 1
                    
        elif report_type == 'available_power':
            # 可用功率：计算主要字段的完整性
            for item in data:
                total_values += 2  # 检查可用功率、电网可用率
                if item.get('available_power') is not None:
                    valid_values += 1
                if item.get('grid_availability') is not None:
                    valid_values += 1
        
        # 返回完整性比例（0-1之间）
        if total_values == 0:
            return 0.0
        
        completeness_ratio = valid_values / total_values
        return completeness_ratio
            
    except Exception as e:
        logging.error(f"检查数据完整性时出错: {e}")
        return 0.0

def check_report_timeliness(report_time, data_timestamp=None):
    """检查上报及时性 - 根据数据时间戳确定截止时间"""
    try:
        # 如果没有提供数据时间戳，使用上报时间作为数据时间戳（兼容性）
        if data_timestamp is None:
            data_timestamp = report_time
        
        # 根据数据时间戳确定应该的截止时间
        data_minute = data_timestamp.minute
        data_hour = data_timestamp.hour
        
        # 确定数据所属的15分钟时段，并计算对应的截止时间
        if data_minute < 15:
            # 0-14分的数据，截止时间是同小时的15分
            deadline = data_timestamp.replace(minute=15, second=0, microsecond=0)
        elif data_minute < 30:
            # 15-29分的数据，截止时间是同小时的30分
            deadline = data_timestamp.replace(minute=30, second=0, microsecond=0)
        elif data_minute < 45:
            # 30-44分的数据，截止时间是同小时的45分
            deadline = data_timestamp.replace(minute=45, second=0, microsecond=0)
        else:
            # 45-59分的数据，截止时间是下一小时的0分
            deadline = data_timestamp.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        # 检查上报时间是否在截止时间前
        is_on_time = report_time <= deadline
        
        # 记录详细信息用于调试
        if not is_on_time:
            logging.info(f"延迟上报: 数据时间={data_timestamp.strftime('%H:%M:%S')}, "
                        f"上报时间={report_time.strftime('%H:%M:%S')}, "
                        f"截止时间={deadline.strftime('%H:%M:%S')}")
        
        return is_on_time
        
    except Exception as e:
        logging.error(f"检查上报及时性时出错: {e}")
        return False

def update_quality_statistics_async(db: Session, farm_code: str, report_time: datetime, 
                                   data_completeness: float, is_on_time: bool, report_type: str):
    """异步更新质量统计（简化版，直接在当前事务中更新）"""
    try:
        date_str = report_time.strftime('%Y-%m-%d')
        
        # 查找当日指定类型的统计记录
        stat = db.query(ReportQualityStatistics).filter(
            and_(
                ReportQualityStatistics.farm_code == farm_code,
                ReportQualityStatistics.report_type == report_type,
                ReportQualityStatistics.date == date_str
            )
        ).first()
        
        if not stat:
            # 创建新的统计记录
            stat = ReportQualityStatistics(
                farm_code=farm_code,
                report_type=report_type,
                date=date_str,
                total_reports=0,
                on_time_reports=0,
                completeness_rate=0.0,
                timeliness_rate=0.0
            )
            db.add(stat)
        
        # 更新计数和累计完整率
        stat.total_reports += 1
        
        # 累计完整率计算：使用加权平均方式
        if stat.total_reports == 1:
            # 第一次上报
            stat.completeness_rate = data_completeness * 100
        else:
            # 更新加权平均完整率
            old_weight = stat.total_reports - 1
            stat.completeness_rate = ((stat.completeness_rate * old_weight) + (data_completeness * 100)) / stat.total_reports
        
        # 更新及时上报计数
        if is_on_time:
            stat.on_time_reports += 1
        
        # 计算及时率
        stat.timeliness_rate = (stat.on_time_reports / stat.total_reports * 100) if stat.total_reports > 0 else 0
        stat.updated_at = datetime.now()
        
        # 更新备注
        notes = []
        if stat.completeness_rate >= 99.0 and stat.total_reports == stat.on_time_reports:
            notes.append("所有上报均正常")
        else:
            if stat.completeness_rate < 99.0:
                notes.append(f"平均完整率{stat.completeness_rate:.1f}%")
            if stat.on_time_reports < stat.total_reports:
                delayed_count = stat.total_reports - stat.on_time_reports
                notes.append(f"{delayed_count}次上报延迟")
        
        stat.notes = '; '.join(notes) if notes else "所有上报均正常"
        
        # 标记为已修改，待调用方提交
        # 不在这里提交，由调用方控制事务
        
    except Exception as e:
        logging.error(f"更新质量统计失败: {e}")
        # 不抛出异常，避免影响主要的上报流程 