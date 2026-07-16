import paramiko
import os
import re
import logging
from typing import List, Dict, Any
from datetime import datetime
import stat

logger = logging.getLogger(__name__)

class SSHService:
    """SSH连接服务类"""
    
    def __init__(self):
        self.connections = {}
        
    def create_connection(self, connection_config: Dict[str, Any]) -> str:
        """创建SSH连接"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接参数
            connect_params = {
                'hostname': connection_config['host'],
                'port': connection_config.get('port', 22),
                'username': connection_config['username'],
                'timeout': 30
            }
            
            # 根据认证方式添加认证信息
            if connection_config['auth_type'] == 'password':
                connect_params['password'] = connection_config['password']
            elif connection_config['auth_type'] == 'key':
                # 处理私钥认证
                key_path = connection_config['private_key_path']
                passphrase = connection_config.get('key_passphrase')
                
                # 尝试加载私钥
                try:
                    if key_path.endswith('.rsa') or 'rsa' in key_path.lower():
                        pkey = paramiko.RSAKey.from_private_key_file(key_path, password=passphrase)
                    elif key_path.endswith('.dsa') or 'dsa' in key_path.lower():
                        pkey = paramiko.DSSKey.from_private_key_file(key_path, password=passphrase)
                    elif key_path.endswith('.ecdsa') or 'ecdsa' in key_path.lower():
                        pkey = paramiko.ECDSAKey.from_private_key_file(key_path, password=passphrase)
                    elif key_path.endswith('.ed25519') or 'ed25519' in key_path.lower():
                        pkey = paramiko.Ed25519Key.from_private_key_file(key_path, password=passphrase)
                    else:
                        # 自动检测密钥类型
                        pkey = paramiko.RSAKey.from_private_key_file(key_path, password=passphrase)
                    
                    connect_params['pkey'] = pkey
                except Exception as e:
                    logger.error(f"加载私钥失败: {e}")
                    raise Exception(f"私钥加载失败: {str(e)}")
            
            # 建立连接
            client.connect(**connect_params)
            
            # 存储连接
            connection_id = f"{connection_config['host']}_{connection_config['username']}"
            self.connections[connection_id] = client
            
            logger.info(f"SSH连接创建成功: {connection_id}")
            return connection_id
            
        except Exception as e:
            logger.error(f"SSH连接失败: {e}")
            raise Exception(f"SSH连接失败: {str(e)}")
    
    def test_connection(self, connection_config: Dict[str, Any]) -> Dict[str, Any]:
        """测试SSH连接"""
        try:
            connection_id = self.create_connection(connection_config)
            client = self.connections[connection_id]
            
            # 执行简单命令测试连接
            stdin, stdout, stderr = client.exec_command('echo "test"')
            output = stdout.read().decode().strip()
            
            if output == "test":
                self.close_connection(connection_id)
                return {"success": True, "message": "连接测试成功"}
            else:
                return {"success": False, "message": "连接测试失败"}
                
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return {"success": False, "message": f"连接测试失败: {str(e)}"}
    
    def close_connection(self, connection_id: str):
        """关闭SSH连接"""
        if connection_id in self.connections:
            try:
                self.connections[connection_id].close()
                del self.connections[connection_id]
                logger.info(f"SSH连接已关闭: {connection_id}")
            except Exception as e:
                logger.error(f"关闭SSH连接失败: {e}")
    
    def list_files(self, connection_config: Dict[str, Any], remote_path: str, 
                   file_pattern: str = None) -> List[Dict[str, Any]]:
        """列出远程目录文件"""
        connection_id = None
        try:
            connection_id = self.create_connection(connection_config)
            client = self.connections[connection_id]
            
            # 创建SFTP客户端
            sftp = client.open_sftp()
            
            # 列出目录文件
            files = []
            try:
                file_list = sftp.listdir_attr(remote_path)
                
                for file_attr in file_list:
                    # 只处理文件，不处理目录
                    if stat.S_ISREG(file_attr.st_mode):
                        filename = file_attr.filename
                        
                        # 如果指定了文件模式，进行匹配
                        if file_pattern:
                            # 先转义所有正则特殊字符，再替换通配符
                            pattern = re.escape(file_pattern)
                            pattern = pattern.replace(r'\*', '.*').replace(r'\?', '.')
                            pattern = f'^{pattern}$'  # 确保完整匹配
                            if not re.match(pattern, filename):
                                continue
                        
                        # 确保使用正斜杠作为路径分隔符（SSH/SFTP要求）
                        full_path = f"{remote_path.rstrip('/')}/{filename}"
                        
                        files.append({
                            'name': filename,
                            'size': file_attr.st_size,
                            'modified_time': datetime.fromtimestamp(file_attr.st_mtime),
                            'full_path': full_path
                        })
                
                # 按修改时间排序，最新的在前
                files.sort(key=lambda x: x['modified_time'], reverse=True)
                
            except FileNotFoundError:
                logger.warning(f"远程目录不存在: {remote_path}")
                return []
            
            finally:
                sftp.close()
            
            return files
            
        except Exception as e:
            logger.error(f"列出文件失败: {e}")
            raise Exception(f"列出文件失败: {str(e)}")
        finally:
            if connection_id:
                self.close_connection(connection_id)
    
    def download_file(self, connection_config: Dict[str, Any], 
                     remote_file_path: str, local_file_path: str) -> Dict[str, Any]:
        """下载文件"""
        connection_id = None
        try:
            logger.info(f"开始下载文件: 远程路径={remote_file_path}, 本地路径={local_file_path}")
            
            connection_id = self.create_connection(connection_config)
            client = self.connections[connection_id]
            
            # 创建SFTP客户端
            sftp = client.open_sftp()
            
            # 检查远程文件是否存在
            try:
                file_stat = sftp.stat(remote_file_path)
                logger.info(f"远程文件确认存在: {remote_file_path}, 大小: {file_stat.st_size} 字节")
            except FileNotFoundError:
                logger.error(f"远程文件不存在: {remote_file_path}")
                return {
                    "success": False,
                    "error": f"远程文件不存在: {remote_file_path}"
                }
            
            # 确保本地目录存在
            local_dir = os.path.dirname(local_file_path)
            if not os.path.exists(local_dir):
                logger.info(f"创建本地目录: {local_dir}")
                os.makedirs(local_dir)
            
            # 下载文件
            logger.info(f"正在下载文件: {remote_file_path} -> {local_file_path}")
            sftp.get(remote_file_path, local_file_path)
            
            # 获取文件信息
            file_stat = os.stat(local_file_path)
            
            sftp.close()
            
            return {
                "success": True,
                "local_path": local_file_path,
                "file_size": file_stat.st_size,
                "download_time": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"文件下载失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if connection_id:
                self.close_connection(connection_id)
    
    def execute_command(self, connection_config: Dict[str, Any], 
                       command: str) -> Dict[str, Any]:
        """执行远程命令"""
        connection_id = None
        try:
            connection_id = self.create_connection(connection_config)
            client = self.connections[connection_id]
            
            # 执行命令
            stdin, stdout, stderr = client.exec_command(command)
            
            # 读取输出
            output = stdout.read().decode()
            error = stderr.read().decode()
            exit_status = stdout.channel.recv_exit_status()
            
            return {
                "success": exit_status == 0,
                "output": output,
                "error": error,
                "exit_status": exit_status
            }
            
        except Exception as e:
            logger.error(f"命令执行失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if connection_id:
                self.close_connection(connection_id)

    def list_files_dynamic_path(self, connection_config: Dict[str, Any], 
                               base_path: str, path_pattern: str, 
                               time_strategy: str, specific_time: datetime = None,
                               time_range_start: datetime = None, time_range_end: datetime = None,
                               file_pattern: str = None) -> List[Dict[str, Any]]:
        """根据时间策略动态搜索文件"""
        connection_id = None
        try:
            connection_id = self.create_connection(connection_config)
            client = self.connections[connection_id]
            sftp = client.open_sftp()
            
            # 平铺目录直接在基础路径中查找文件。
            if path_pattern == 'flat':
                time_paths = [base_path]
            # 对于 latest 策略，先查找实际存在的时间目录
            elif time_strategy == 'latest':
                logger.info("使用最新数据策略，扫描服务器上实际存在的时间目录")
                time_paths = []
                
                try:
                    # 列出基础目录下的所有文件夹
                    dir_list = sftp.listdir_attr(base_path)
                    logger.info(f"扫描基础路径 {base_path}，找到 {len(dir_list)} 个条目")
                    
                    time_dirs = []
                    pattern_regex = self._convert_pattern_to_regex(path_pattern)
                    
                    for dir_attr in dir_list:
                        # 只处理目录
                        if stat.S_ISDIR(dir_attr.st_mode):
                            dirname = dir_attr.filename
                            
                            # 检查是否匹配时间模式
                            if re.match(pattern_regex, dirname):
                                parsed_time = self._parse_time_from_dirname(dirname, path_pattern)
                                if parsed_time:
                                    # 确保使用正斜杠作为路径分隔符（SSH/SFTP要求）
                                    dir_path = f"{base_path.rstrip('/')}/{dirname}"
                                    
                                    time_dirs.append({
                                        'name': dirname,
                                        'path': dir_path,
                                        'parsed_time': parsed_time
                                    })
                    
                    # 按时间排序，最新的在前
                    time_dirs.sort(key=lambda x: x['parsed_time'], reverse=True)
                    
                    # 对于latest策略，只取最新的1个目录
                    time_paths = [dir_info['path'] for dir_info in time_dirs[:1]]
                    logger.info(f"找到 {len(time_dirs)} 个时间目录，使用最新的 {len(time_paths)} 个: {[os.path.basename(p) for p in time_paths]}")
                    
                except FileNotFoundError:
                    logger.warning(f"基础路径不存在: {base_path}")
                    time_paths = []
                except Exception as e:
                    logger.error(f"扫描时间目录失败: {e}")
                    # 如果扫描失败，回退到原来的时间生成方法
                    time_paths = self._generate_time_paths(
                        base_path, path_pattern, time_strategy, 
                        specific_time, time_range_start, time_range_end
                    )
            else:
                # 其他策略使用原来的路径生成方法
                time_paths = self._generate_time_paths(
                    base_path, path_pattern, time_strategy, 
                    specific_time, time_range_start, time_range_end
                )
            
            all_files = []
            
            # 遍历每个时间路径
            for time_path in time_paths:
                try:
                    logger.info(f"搜索路径: {time_path}")
                    
                    # 检查目录是否存在
                    try:
                        sftp.stat(time_path)
                        logger.info(f"路径存在: {time_path}")
                    except FileNotFoundError:
                        logger.warning(f"路径不存在: {time_path}")
                        continue
                    
                    # 列出目录文件
                    file_list = sftp.listdir_attr(time_path)
                    logger.info(f"路径 {time_path} 中找到 {len(file_list)} 个文件/目录")
                    
                    file_count = 0
                    matched_count = 0
                    for file_attr in file_list:
                        # 只处理文件
                        if stat.S_ISREG(file_attr.st_mode):
                            filename = file_attr.filename
                            file_count += 1
                            logger.debug(f"检查文件: {filename}")
                            
                            # 文件模式匹配
                            if file_pattern:
                                # 先转义所有正则特殊字符，再替换通配符
                                pattern = self._convert_file_pattern_to_regex(file_pattern)
                                logger.debug(f"文件匹配: {filename} vs 模式: {pattern}")
                                if not re.match(pattern, filename):
                                    logger.debug(f"文件 {filename} 不匹配模式 {file_pattern}")
                                    continue
                                else:
                                    logger.info(f"文件 {filename} 匹配成功!")
                                    matched_count += 1
                            
                            # 确保使用正斜杠作为路径分隔符（SSH/SFTP要求）
                            full_path = f"{time_path.rstrip('/')}/{filename}"
                            
                            all_files.append({
                                'name': filename,
                                'size': file_attr.st_size,
                                'modified_time': datetime.fromtimestamp(file_attr.st_mtime),
                                'full_path': full_path,
                                'time_folder': os.path.basename(time_path)
                            })
                    
                    logger.info(f"路径 {time_path} 处理完成: 共 {file_count} 个文件，匹配 {matched_count} 个")
                            
                except Exception as e:
                    logger.warning(f"处理路径 {time_path} 时出错: {e}")
                    continue
            
            # 按修改时间排序，最新的在前
            all_files.sort(key=lambda x: x['modified_time'], reverse=True)
            
            logger.info(f"文件搜索完成: 总共找到 {len(all_files)} 个匹配文件")
            if all_files:
                logger.info(f"匹配的文件列表: {[f['name'] for f in all_files]}")
            
            sftp.close()
            return all_files
            
        except Exception as e:
            logger.error(f"动态路径文件搜索失败: {e}")
            raise Exception(f"动态路径文件搜索失败: {str(e)}")
        finally:
            if connection_id:
                self.close_connection(connection_id)
    
    def find_available_time_directories(self, connection_config: Dict[str, Any],
                                      base_path: str, path_pattern: str,
                                      time_strategy: str = 'latest',
                                      specific_time: str = None,
                                      time_range_start: str = None,
                                      time_range_end: str = None,
                                      limit: int = 10) -> List[Dict[str, Any]]:
        """查找可用的时间目录"""
        connection_id = None
        try:
            connection_id = self.create_connection(connection_config)
            client = self.connections[connection_id]
            sftp = client.open_sftp()
            
            # 列出基础目录下的所有文件夹
            try:
                dir_list = sftp.listdir_attr(base_path)
                logger.info(f"找到 {len(dir_list)} 个条目在路径: {base_path}")
            except FileNotFoundError:
                logger.warning(f"基础路径不存在: {base_path}")
                return []
            
            time_dirs = []
            pattern_regex = self._convert_pattern_to_regex(path_pattern)
            logger.info(f"使用正则表达式: {pattern_regex}")
            
            matched_count = 0
            total_dirs = 0
            
            for dir_attr in dir_list:
                # 只处理目录
                if stat.S_ISDIR(dir_attr.st_mode):
                    total_dirs += 1
                    dirname = dir_attr.filename
                    
                    # 检查是否匹配时间模式
                    if re.match(pattern_regex, dirname):
                        matched_count += 1
                        parsed_time = self._parse_time_from_dirname(dirname, path_pattern)
                        if parsed_time:  # 只添加能成功解析时间的目录
                            # 确保使用正斜杠作为路径分隔符（SSH/SFTP要求）
                            dir_path = f"{base_path.rstrip('/')}/{dirname}"
                            
                            time_dirs.append({
                                'name': dirname,
                                'path': dir_path,
                                'modified_time': datetime.fromtimestamp(dir_attr.st_mtime),
                                'parsed_time': parsed_time
                            })
                        else:
                            logger.warning(f"目录 {dirname} 匹配格式但时间解析失败")
                    else:
                        logger.debug(f"目录 {dirname} 不匹配格式 {pattern_regex}")
            
            logger.info(f"总目录数: {total_dirs}, 格式匹配: {matched_count}, 时间解析成功: {len(time_dirs)}")
            
            # 按时间排序，最新的在前
            time_dirs.sort(key=lambda x: x['parsed_time'] or datetime.min, reverse=True)
            
            # 根据时间策略筛选目录
            filtered_dirs = self._filter_directories_by_time_strategy(
                time_dirs, time_strategy, specific_time, time_range_start, time_range_end
            )
            
            logger.info(f"时间策略筛选后: {len(filtered_dirs)} 个目录")
            
            sftp.close()
            return filtered_dirs[:limit]
            
        except Exception as e:
            logger.error(f"查找时间目录失败: {e}")
            return []
        finally:
            if connection_id:
                self.close_connection(connection_id)
    
    def _generate_time_paths(self, base_path: str, path_pattern: str, 
                           time_strategy: str, specific_time: datetime = None,
                           time_range_start: datetime = None, time_range_end: datetime = None) -> List[str]:
        """生成时间路径列表"""
        from datetime import timedelta
        
        paths = []
        
        if time_strategy == 'latest':
            # 最新数据：生成过去24小时的可能路径
            now = datetime.now()
            for hours_back in range(0, 25, 6):  # 每6小时一个时间点
                time_point = now - timedelta(hours=hours_back)
                path = self._format_time_path(base_path, path_pattern, time_point)
                paths.append(path)
                
        elif time_strategy == 'specific' and specific_time:
            # 指定时间
            path = self._format_time_path(base_path, path_pattern, specific_time)
            paths.append(path)
            
        elif time_strategy == 'range' and time_range_start and time_range_end:
            # 时间范围：每6小时生成一个时间点
            current_time = time_range_start
            while current_time <= time_range_end:
                path = self._format_time_path(base_path, path_pattern, current_time)
                paths.append(path)
                current_time += timedelta(hours=6)
        
        return paths
    
    def _format_time_path(self, base_path: str, pattern: str, time_obj: datetime) -> str:
        """根据时间模式格式化路径"""
        # 时间格式映射
        formats = {
            'YYYY': time_obj.strftime('%Y'),
            'MM': time_obj.strftime('%m'),
            'DD': time_obj.strftime('%d'),
            'HH': time_obj.strftime('%H'),
            'NN': time_obj.strftime('%M'),
            'SS': time_obj.strftime('%S')
        }
        
        # 常见模式处理
        if pattern == 'YYYY_MMDDHHNN':
            folder_name = f"{formats['YYYY']}_{formats['MM']}{formats['DD']}{formats['HH']}{formats['NN']}"
        elif pattern == 'YYYY-MM-DD/HH':
            folder_name = f"{formats['YYYY']}-{formats['MM']}-{formats['DD']}/{formats['HH']}"
        elif pattern == 'YYYYMMDDHH':
            folder_name = f"{formats['YYYY']}{formats['MM']}{formats['DD']}{formats['HH']}"
        elif pattern == 'YYYY/MM/DD/HH':
            folder_name = f"{formats['YYYY']}/{formats['MM']}/{formats['DD']}/{formats['HH']}"
        else:
            # 自定义模式：替换所有变量
            folder_name = pattern
            for var, value in formats.items():
                folder_name = folder_name.replace(var, value)
        
        # 确保使用正斜杠作为路径分隔符（SSH/SFTP要求）
        return f"{base_path.rstrip('/')}/{folder_name}"
    
    def _convert_pattern_to_regex(self, pattern: str) -> str:
        """将时间模式转换为正则表达式"""
        # 转义特殊字符
        regex_pattern = re.escape(pattern)
        
        # 替换时间变量为正则表达式
        replacements = {
            'YYYY': r'\d{4}',
            'MM': r'\d{2}',
            'DD': r'\d{2}',
            'HH': r'\d{2}',
            'NN': r'\d{2}',
            'SS': r'\d{2}'
        }
        
        for var, regex in replacements.items():
            regex_pattern = regex_pattern.replace(re.escape(var), regex)
        
        return f'^{regex_pattern}$'

    def _convert_file_pattern_to_regex(self, pattern: str) -> str:
        """将文件名模板和通配符转换为完整匹配正则。"""

        regex_pattern = re.escape(pattern)
        replacements = {
            '${YYYYMMDDHHNN}': r'\d{12}',
            '${YYYYMMDDHH}': r'\d{10}',
            '${YYYYMMDD}': r'\d{8}',
            '${YYYY}': r'\d{4}',
            '${MM}': r'\d{2}',
            '${DD}': r'\d{2}',
            '${HH}': r'\d{2}',
            '${NN}': r'\d{2}',
        }
        for token, replacement in replacements.items():
            regex_pattern = regex_pattern.replace(re.escape(token), replacement)
        regex_pattern = regex_pattern.replace(r'\*', '.*').replace(r'\?', '.')
        return f'^{regex_pattern}$'
    
    def _parse_time_from_dirname(self, dirname: str, pattern: str) -> datetime:
        """从目录名解析时间"""
        try:
            if pattern == 'YYYY_MMDDHHNN':
                # 2025_07011800 格式，支持不同长度
                parts = dirname.split('_')
                if len(parts) >= 2:
                    year = int(parts[0])
                    date_time_str = parts[1]
                    
                    if len(date_time_str) >= 8:  # 至少要有MMDDHH
                        month = int(date_time_str[0:2])
                        day = int(date_time_str[2:4])
                        hour = int(date_time_str[4:6])
                        minute = int(date_time_str[6:8]) if len(date_time_str) >= 8 else 0
                        return datetime(year, month, day, hour, minute)
                
                # 备用解析方式：直接按位置解析
                if len(dirname) >= 11:  # 2025_070118 最小长度
                    year = int(dirname[:4])
                    month = int(dirname[5:7])
                    day = int(dirname[7:9])
                    hour = int(dirname[9:11])
                    minute = int(dirname[11:13]) if len(dirname) >= 13 else 0
                    return datetime(year, month, day, hour, minute)
                
            elif pattern == 'YYYYMMDDHH':
                # 2025070118 格式
                if len(dirname) >= 10:
                    year = int(dirname[:4])
                    month = int(dirname[4:6])
                    day = int(dirname[6:8])
                    hour = int(dirname[8:10]) if len(dirname) >= 10 else 0
                    return datetime(year, month, day, hour)
                
            # 其他格式的解析可以在这里添加
            
        except (ValueError, IndexError) as e:
            logger.warning(f"解析时间失败: {dirname}, pattern: {pattern}, error: {e}")
            
        return None

    def _filter_directories_by_time_strategy(self, time_dirs: List[Dict[str, Any]],
                                           time_strategy: str, specific_time: str = None,
                                           time_range_start: str = None, time_range_end: str = None) -> List[Dict[str, Any]]:
        """根据时间策略筛选目录"""
        try:
            if time_strategy == 'latest':
                # 最新数据：返回所有目录（已按时间排序）
                return time_dirs
                
            elif time_strategy == 'specific' and specific_time:
                # 指定时间：筛选匹配指定时间的目录
                try:
                    target_time = datetime.fromisoformat(specific_time.replace('Z', '+00:00'))
                    target_date = target_time.date()
                    target_hour = target_time.hour
                    
                    filtered = []
                    for dir_info in time_dirs:
                        if dir_info['parsed_time']:
                            dir_date = dir_info['parsed_time'].date()
                            dir_hour = dir_info['parsed_time'].hour
                            
                            # 匹配日期和小时
                            if dir_date == target_date and abs(dir_hour - target_hour) <= 3:  # 允许3小时误差
                                filtered.append(dir_info)
                    
                    logger.info(f"指定时间 {specific_time} 筛选: {len(filtered)} 个目录")
                    return filtered
                    
                except Exception as e:
                    logger.warning(f"解析指定时间失败: {specific_time}, error: {e}")
                    return time_dirs
                    
            elif time_strategy == 'range' and time_range_start and time_range_end:
                # 时间范围：筛选在时间范围内的目录
                try:
                    start_time = datetime.fromisoformat(time_range_start.replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(time_range_end.replace('Z', '+00:00'))
                    
                    filtered = []
                    for dir_info in time_dirs:
                        if dir_info['parsed_time']:
                            dir_time = dir_info['parsed_time']
                            if start_time <= dir_time <= end_time:
                                filtered.append(dir_info)
                    
                    logger.info(f"时间范围 {time_range_start} 到 {time_range_end} 筛选: {len(filtered)} 个目录")
                    return filtered
                    
                except Exception as e:
                    logger.warning(f"解析时间范围失败: {time_range_start} - {time_range_end}, error: {e}")
                    return time_dirs
            
            # 默认返回所有目录
            return time_dirs
            
        except Exception as e:
            logger.error(f"时间策略筛选失败: {e}")
            return time_dirs

# 全局SSH服务实例
ssh_service = SSHService()
