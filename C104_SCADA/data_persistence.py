"""
数据持久化和状态管理模块
用于监管者模式下的数据连续性保障
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from collections import OrderedDict
from typing import Dict, List, Tuple, Optional, Any
import logging

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))

class DataCache:
    """数据缓存类，提供内存限制和LRU清理机制"""
    
    def __init__(self, max_size: int = 1000, max_hours: int = 24):
        self.cache = OrderedDict()  # {timestamp_str: data}
        self.max_size = max_size
        self.max_hours = max_hours
        self.logger = logging.getLogger("DataCache")
    
    def add_data(self, timestamp: datetime, data: Dict[str, Any]) -> bool:
        """添加数据并检查限制"""
        try:
            # 确保时间戳有时区信息
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=BEIJING_TZ)
            
            timestamp_str = timestamp.isoformat()
            
            # 添加数据
            self.cache[timestamp_str] = {
                'timestamp': timestamp,
                'data': data,
                'added_time': datetime.now(BEIJING_TZ)
            }
            
            # 移动到末尾（LRU）
            self.cache.move_to_end(timestamp_str)
            
            # 检查大小限制
            if len(self.cache) > self.max_size:
                # 删除最旧的条目
                oldest_key = next(iter(self.cache))
                removed_item = self.cache.pop(oldest_key)
                self.logger.debug(f"Cache size limit reached. Removed oldest item: {oldest_key}")
            
            # 清理过期数据
            self._cleanup_old_data()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding data to cache: {e}", exc_info=True)
            return False
    
    def get_data_for_timerange(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """获取指定时间范围的数据"""
        try:
            # 确保时间戳有时区信息
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=BEIJING_TZ)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=BEIJING_TZ)
            
            result = []
            for timestamp_str, cache_item in self.cache.items():
                item_time = cache_item['timestamp']
                if start_time <= item_time <= end_time:
                    result.append({
                        'timestamp': item_time,
                        'data': cache_item['data']
                    })
            
            return sorted(result, key=lambda x: x['timestamp'])
            
        except Exception as e:
            self.logger.error(f"Error getting data for time range: {e}", exc_info=True)
            return []
    
    def _cleanup_old_data(self):
        """清理超时数据"""
        try:
            cutoff_time = datetime.now(BEIJING_TZ) - timedelta(hours=self.max_hours)
            keys_to_remove = []
            
            for timestamp_str, cache_item in self.cache.items():
                if cache_item['added_time'] < cutoff_time:
                    keys_to_remove.append(timestamp_str)
            
            for key in keys_to_remove:
                self.cache.pop(key)
                self.logger.debug(f"Removed expired cache item: {key}")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}", exc_info=True)
    
    def get_size(self) -> int:
        """获取缓存大小"""
        return len(self.cache)
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.logger.info("Cache cleared")


class DataPersistence:
    """数据持久化和状态管理类"""
    
    def __init__(self, state_dir: str = "state", data_dir: str = "data"):
        self.state_dir = state_dir
        self.data_dir = data_dir
        self.status_file = os.path.join(state_dir, "status.json")
        self.cache_file = os.path.join(state_dir, "data_cache.json")
        self.backup_dir = os.path.join(state_dir, "backup")
        
        self.cache = DataCache()
        self.logger = logging.getLogger("DataPersistence")
        
        # 确保目录存在
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        for directory in [self.state_dir, self.data_dir, self.backup_dir]:
            os.makedirs(directory, exist_ok=True)
    
    def save_state(self, state_data: Dict[str, Any]) -> bool:
        """保存状态到文件"""
        try:
            # 添加元数据
            state_data.update({
                'last_updated': datetime.now(BEIJING_TZ).isoformat(),
                'cache_size': self.cache.get_size(),
                'version': '1.0'
            })
            
            # 原子写入
            temp_file = self.status_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
            
            # 原子替换
            if os.path.exists(self.status_file):
                backup_file = os.path.join(self.backup_dir, f"status_{int(time.time())}.json")
                os.rename(self.status_file, backup_file)
            
            os.rename(temp_file, self.status_file)
            
            self.logger.debug(f"State saved successfully: {len(state_data)} items")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving state: {e}", exc_info=True)
            return False
    
    def load_state(self) -> Dict[str, Any]:
        """从文件加载状态"""
        try:
            if not os.path.exists(self.status_file):
                self.logger.info("No existing state file found, starting with default state")
                return self._get_default_state()
            
            with open(self.status_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            self.logger.info(f"State loaded successfully from {self.status_file}")
            return state_data
            
        except Exception as e:
            self.logger.error(f"Error loading state: {e}, using default state", exc_info=True)
            return self._get_default_state()
    
    def _get_default_state(self) -> Dict[str, Any]:
        """获取默认状态"""
        return {
            'client_running': False,
            'last_database_upload_time': None,
            'last_csv_write_time': None,
            'program_last_running_time': None,
            'pending_database_uploads': [],
            'pending_csv_writes': [],
            'cache_size': 0,
            'health_check_count': 0,
            'last_upload_quarter_minute': -1,
            'last_pre_quarter_approximation_minute_processed': -1
        }
    
    def save_cache_data(self) -> bool:
        """保存缓存数据到文件"""
        try:
            cache_data = {
                'cache_items': [],
                'saved_time': datetime.now(BEIJING_TZ).isoformat(),
                'total_items': self.cache.get_size()
            }
            
            # 只保存最近的数据，避免文件过大
            recent_items = list(self.cache.cache.items())[-100:]  # 最多保存100条
            
            for timestamp_str, cache_item in recent_items:
                cache_data['cache_items'].append({
                    'timestamp': timestamp_str,
                    'data': cache_item['data'],
                    'added_time': cache_item['added_time'].isoformat()
                })
            
            temp_file = self.cache_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            os.rename(temp_file, self.cache_file)
            
            self.logger.debug(f"Cache data saved: {len(cache_data['cache_items'])} items")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving cache data: {e}", exc_info=True)
            return False
    
    def load_cache_data(self) -> bool:
        """从文件加载缓存数据"""
        try:
            if not os.path.exists(self.cache_file):
                self.logger.info("No existing cache file found")
                return True
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 恢复缓存数据
            for item in cache_data.get('cache_items', []):
                timestamp = datetime.fromisoformat(item['timestamp'])
                self.cache.add_data(timestamp, item['data'])
            
            self.logger.info(f"Cache data loaded: {len(cache_data.get('cache_items', []))} items")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading cache data: {e}", exc_info=True)
            return False
    
    def get_missing_time_windows(self, last_time: Optional[str] = None) -> List[Tuple[datetime, str]]:
        """计算遗漏的15分钟时间窗口"""
        try:
            missing_windows = []
            current_time = datetime.now(BEIJING_TZ)
            
            # 如果没有上次时间，返回空列表
            if not last_time:
                return missing_windows
            
            last_dt = datetime.fromisoformat(last_time)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=BEIJING_TZ)
            
            # 计算15分钟窗口
            current_quarter = self._get_quarter_time(current_time)
            last_quarter = self._get_quarter_time(last_dt)
            
            # 生成遗漏的时间窗口
            window_time = last_quarter + timedelta(minutes=15)
            while window_time <= current_quarter:
                window_type = "database_upload" if window_time.minute % 15 == 0 else "csv_write"
                missing_windows.append((window_time, window_type))
                window_time += timedelta(minutes=15)
            
            if missing_windows:
                self.logger.info(f"Found {len(missing_windows)} missing time windows")
            
            return missing_windows
            
        except Exception as e:
            self.logger.error(f"Error calculating missing time windows: {e}", exc_info=True)
            return []
    
    def _get_quarter_time(self, dt: datetime) -> datetime:
        """获取15分钟整点时间"""
        quarter_minute = (dt.minute // 15) * 15
        return dt.replace(minute=quarter_minute, second=0, microsecond=0)
    
    def add_pending_operation(self, operation_type: str, timestamp: datetime, data: Dict[str, Any]) -> bool:
        """添加待处理操作"""
        try:
            self.cache.add_data(timestamp, {
                'operation_type': operation_type,
                'data': data,
                'created_time': datetime.now(BEIJING_TZ).isoformat()
            })
            
            self.logger.debug(f"Added pending operation: {operation_type} at {timestamp}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding pending operation: {e}", exc_info=True)
            return False
    
    def get_pending_operations(self, operation_type: str = None) -> List[Dict[str, Any]]:
        """获取待处理操作"""
        try:
            result = []
            for timestamp_str, cache_item in self.cache.cache.items():
                if not operation_type or cache_item['data'].get('operation_type') == operation_type:
                    result.append({
                        'timestamp': cache_item['timestamp'],
                        'data': cache_item['data']
                    })
            
            return sorted(result, key=lambda x: x['timestamp'])
            
        except Exception as e:
            self.logger.error(f"Error getting pending operations: {e}", exc_info=True)
            return []
    
    def cleanup_old_backups(self, max_backups: int = 50):
        """清理旧的备份文件"""
        try:
            backup_files = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("status_") and filename.endswith(".json"):
                    filepath = os.path.join(self.backup_dir, filename)
                    backup_files.append((filepath, os.path.getmtime(filepath)))
            
            # 按修改时间排序
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            # 删除超过限制的文件
            for filepath, _ in backup_files[max_backups:]:
                os.remove(filepath)
                self.logger.debug(f"Removed old backup: {filepath}")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old backups: {e}", exc_info=True) 