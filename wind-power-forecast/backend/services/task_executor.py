import os
import logging
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from db_models.weather_fetch import WeatherTask, WeatherConnection, WeatherLog, WeatherData
from services.ssh_service import ssh_service
from services.weather_data_service import weather_data_service
from services.weather_connection_security import build_connection_config

logger = logging.getLogger(__name__)

def execute_weather_task(task: WeatherTask, connection: WeatherConnection, session: Session) -> Dict[str, Any]:
    """执行气象数据拉取任务"""
    try:
        # 更新任务状态
        task.status = 'running'
        task.last_run = datetime.now()
        session.commit()
        
        # 记录开始日志
        log_entry = WeatherLog(
            task_id=task.id,
            farm_code=task.farm_code,
            log_level='info',
            message='任务开始执行',
            created_at=datetime.now()
        )
        session.add(log_entry)
        session.commit()
        
        # 构建连接配置
        connection_config = build_connection_config(connection)
        
        # 1. 列出远程文件（使用动态路径）
        files = ssh_service.list_files_dynamic_path(
            connection_config,
            task.remote_path,
            task.path_pattern,
            task.time_strategy,
            task.specific_time,
            task.time_range_start,
            task.time_range_end,
            task.file_pattern
        )
        
        if not files:
            log_entry = WeatherLog(
                task_id=task.id,
                farm_code=task.farm_code,
                log_level='warning',
                message='未找到匹配的文件',
                created_at=datetime.now()
            )
            session.add(log_entry)
            session.commit()
            
            task.status = 'idle'
            session.commit()
            
            return {
                'success': True,
                'message': '未找到匹配的文件',
                'files_processed': 0
            }
        
        # 2. 处理和保存文件
        processed_files = 0
        total_size = 0
        
        # 解析保存路径，支持日期变量替换
        save_path = task.save_path.replace('{date}', datetime.now().strftime('%Y-%m-%d'))
        
        # 确保保存目录存在
        import os
        os.makedirs(save_path, exist_ok=True)
        
        for file_info in files:
            try:
                # 构建最终保存路径
                final_file_path = os.path.join(save_path, file_info['name'])
                
                # 🔄 去重检查：根据用户设置决定是否跳过文件
                dedup_options = task.deduplication_options or ['skip_existing']
                
                if 'skip_existing' in dedup_options and not ('force_reprocess' in dedup_options):
                    if _should_skip_file(session, task.id, file_info, final_file_path, dedup_options):
                        log_entry = WeatherLog(
                            task_id=task.id,
                            farm_code=task.farm_code,
                            log_level='info',
                            message=f'跳过已存在文件: {file_info["name"]}',
                            details=f'文件已存在于: {final_file_path}',
                            created_at=datetime.now()
                        )
                        session.add(log_entry)
                        continue
                
                # 检查文件是否已存在，避免重复下载
                file_already_exists = os.path.exists(final_file_path)
                
                if not file_already_exists:
                    # 下载文件到目标位置
                    download_result = ssh_service.download_file(
                        connection_config,
                        file_info['full_path'],
                        final_file_path
                    )
                    
                    if not download_result['success']:
                        log_entry = WeatherLog(
                            task_id=task.id,
                            farm_code=task.farm_code,
                            log_level='error',
                            message=f'文件下载失败: {file_info["name"]}',
                            details=download_result.get('error'),
                            created_at=datetime.now()
                        )
                        session.add(log_entry)
                        continue
                    
                    log_entry = WeatherLog(
                        task_id=task.id,
                        farm_code=task.farm_code,
                        log_level='info',
                        message=f'文件下载成功: {file_info["name"]}',
                        details=f'大小: {file_info.get("size", 0)} 字节',
                        created_at=datetime.now()
                    )
                    session.add(log_entry)
                else:
                    log_entry = WeatherLog(
                        task_id=task.id,
                        farm_code=task.farm_code,
                        log_level='info',
                        message=f'使用已存在文件: {file_info["name"]}',
                        details=f'路径: {final_file_path}',
                        created_at=datetime.now()
                    )
                    session.add(log_entry)
                
                # 应用数据处理选项（如果需要）
                process_result = weather_data_service.process_weather_file_local(
                    final_file_path,
                    task.processing_options
                )
                
                if process_result['success']:
                    processed_files += 1
                    total_size += file_info.get('size', 0)
                    
                    # 记录处理结果
                    data_record = WeatherData(
                        task_id=task.id,
                        farm_code=task.farm_code,
                        file_name=file_info['name'],
                        file_path=final_file_path,
                        file_size=file_info.get('size', 0),
                        records_count=0,  # 本地文件保存不需要记录数
                        status='success',
                        started_at=datetime.now(),
                        completed_at=datetime.now()
                    )
                    session.add(data_record)
                    
                    log_entry = WeatherLog(
                        task_id=task.id,
                        farm_code=task.farm_code,
                        log_level='success',
                        message=f'文件保存成功: {file_info["name"]}',
                        details=f'保存路径: {final_file_path}',
                        created_at=datetime.now()
                    )
                    session.add(log_entry)
                else:
                    log_entry = WeatherLog(
                        task_id=task.id,
                        farm_code=task.farm_code,
                        log_level='error',
                        message=f'文件处理失败: {file_info["name"]}',
                        details=process_result.get('error'),
                        created_at=datetime.now()
                    )
                    session.add(log_entry)
                    
                    # 如果处理失败，删除已下载的文件
                    if os.path.exists(final_file_path):
                        os.remove(final_file_path)
                
            except Exception as e:
                log_entry = WeatherLog(
                    task_id=task.id,
                    farm_code=task.farm_code,
                    log_level='error',
                    message=f'处理文件时发生错误: {file_info["name"]}',
                    details=str(e),
                    created_at=datetime.now()
                )
                session.add(log_entry)
                continue
        
        # 更新任务状态
        task.status = 'idle'
        session.commit()
        
        # 记录完成日志
        log_entry = WeatherLog(
            task_id=task.id,
            farm_code=task.farm_code,
            log_level='info',
            message='任务执行完成',
            details=f'保存文件数: {processed_files}, 总文件大小: {total_size} 字节, 保存路径: {save_path}',
            created_at=datetime.now()
        )
        session.add(log_entry)
        session.commit()
        
        return {
            'success': True,
            'files_processed': processed_files,
            'total_size': total_size,
            'save_path': save_path
        }
        
    except Exception as e:
        # 更新任务状态为错误
        task.status = 'error'
        session.commit()
        
        # 记录错误日志
        log_entry = WeatherLog(
            task_id=task.id,
            farm_code=task.farm_code,
            log_level='error',
            message='任务执行失败',
            details=str(e),
            created_at=datetime.now()
        )
        session.add(log_entry)
        session.commit()
        
        return {
            'success': False,
            'error': str(e)
        }

def _should_skip_file(session: Session, task_id: int, file_info: Dict[str, Any], local_file_path: str, dedup_options: List[str]) -> bool:
    """
    检查是否应该跳过文件下载（去重检查）
    
    Args:
        session: 数据库会话
        task_id: 任务ID
        file_info: 远程文件信息 {'name', 'size', 'modified_time', 'full_path', 'time_folder'}
        local_file_path: 本地文件路径
        dedup_options: 去重选项列表
    
    Returns:
        bool: True表示应该跳过，False表示需要下载
    """
    import os
    
    # 1. 检查本地文件是否存在
    if not os.path.exists(local_file_path):
        return False  # 文件不存在，需要下载
    
    # 2. 检查本地文件大小是否匹配（如果启用了check_size选项）
    if 'check_size' in dedup_options:
        try:
            local_file_size = os.path.getsize(local_file_path)
            remote_file_size = file_info.get('size', 0)
            
            if remote_file_size > 0 and local_file_size != remote_file_size:
                logger.info(f"文件大小不匹配，重新下载: {file_info['name']} (本地:{local_file_size}, 远程:{remote_file_size})")
                return False  # 文件大小不匹配，需要重新下载
                
        except OSError:
            return False  # 无法读取本地文件，需要重新下载
    
    # 3. 检查数据库中是否已有成功的处理记录
    existing_record = session.query(WeatherData).filter(
        WeatherData.task_id == task_id,
        WeatherData.file_name == file_info['name'],
        WeatherData.status == 'success'
    ).first()
    
    if existing_record:
        # 检查记录中的文件路径是否与当前路径一致
        if existing_record.file_path == local_file_path:
            logger.info(f"文件已成功处理过，跳过: {file_info['name']}")
            return True  # 文件已成功处理，跳过
        else:
            # 路径不一致，可能是保存路径配置发生了变化
            logger.info(f"文件路径变更，重新下载: {file_info['name']}")
            return False
    
    # 4. 检查修改时间（如果启用了check_mtime选项）
    if 'check_mtime' in dedup_options:
        try:
            local_mtime = datetime.fromtimestamp(os.path.getmtime(local_file_path))
            remote_mtime = file_info.get('modified_time')
            
            if remote_mtime and local_mtime:
                # 如果远程文件更新，需要重新下载
                if remote_mtime > local_mtime:
                    logger.info(f"远程文件已更新，重新下载: {file_info['name']}")
                    return False
                    
        except (OSError, TypeError):
            # 时间比较失败，继续其他检查
            pass
    
    # 5. 如果文件存在且大小匹配，但没有数据库记录，说明可能是之前下载但处理失败的文件
    # 这种情况下允许重新处理，但不重新下载
    logger.info(f"文件存在但无成功记录，重新处理: {file_info['name']}")
    return False
