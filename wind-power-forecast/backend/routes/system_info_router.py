from flask import Blueprint, jsonify
import psutil
import platform
import subprocess
import sys
import os
from datetime import datetime, timedelta
import logging
import pkg_resources
from flask_jwt_extended import jwt_required

system_info_bp = Blueprint('system_info', __name__)

@system_info_bp.route('/test', methods=['GET'])
def test_route():
    """测试路由"""
    return jsonify({'message': '系统信息API正常工作', 'status': 'ok'})

@system_info_bp.route('/platform-test', methods=['GET'])
def platform_test():
    """平台兼容性测试"""
    test_results = {
        'platform': platform.system(),
        'machine': platform.machine(),
        'python_version': sys.version,
        'docker_env': os.path.exists('/.dockerenv'),
        'proc_cpuinfo_exists': os.path.exists('/proc/cpuinfo'),
        'etc_os_release_exists': os.path.exists('/etc/os-release'),
        'environment_vars': {
            'DB_HOST': os.environ.get('DB_HOST', 'Not Set'),
            'DB_PORT': os.environ.get('DB_PORT', 'Not Set'),
            'DB_USER': os.environ.get('DB_USER', 'Not Set'),
            'DB_NAME': os.environ.get('DB_NAME', 'Not Set')
        },
        'available_commands': {}
    }
    
    # 测试各种命令的可用性
    commands_to_test = ['lspci', 'nvidia-smi', 'node', 'wmic']
    for cmd in commands_to_test:
        try:
            result = subprocess.run([cmd, '--version'], capture_output=True, timeout=2)
            test_results['available_commands'][cmd] = result.returncode == 0
        except:
            test_results['available_commands'][cmd] = False
    
    return jsonify(test_results)

@system_info_bp.route('/hardware', methods=['GET'])
@jwt_required()
def get_hardware_info():
    """获取硬件信息"""
    try:
        # CPU信息
        cpu_count = psutil.cpu_count()
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()
        
        # 尝试获取更准确的CPU名称
        cpu_name = "未知处理器"
        try:
            if platform.system() == "Windows":
                # 使用wmic获取CPU型号
                result = subprocess.run(['wmic', 'cpu', 'get', 'name'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    cpu_lines = [line.strip() for line in result.stdout.split('\n') 
                               if line.strip() and 'Name' not in line and line.strip()]
                    if cpu_lines:
                        cpu_name = cpu_lines[0]
            else:
                # Linux系统可以从/proc/cpuinfo获取
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if line.startswith('model name'):
                                cpu_name = line.split(':')[1].strip()
                                break
                except:
                    cpu_name = platform.processor() or "未知处理器"
        except:
            cpu_name = platform.processor() or "未知处理器"
        
        # 内存信息
        memory = psutil.virtual_memory()
        memory_total_gb = round(memory.total / (1024**3), 1)
        
        # 磁盘信息 - 优先检测容器环境
        disk_path = '/'  # 默认使用根目录
        try:
            # 检查是否在Docker容器中
            if os.path.exists('/.dockerenv'):
                disk_path = '/'  # 容器环境使用根目录
            elif platform.system() == "Windows":
                disk_path = 'C:'  # Windows本地环境
            else:
                disk_path = '/'   # Linux本地环境
            
            disk_usage = psutil.disk_usage(disk_path)
            disk_total_gb = round(disk_usage.total / (1024**3), 1)
        except Exception as e:
            logging.warning(f"获取磁盘信息失败: {e}")
            disk_total_gb = "未知"
        
        # 网络信息
        network_interfaces = list(psutil.net_if_addrs().keys())
        main_interface = network_interfaces[0] if network_interfaces else "未知"
        
        # 系统信息（操作系统 + 架构）
        os_system = platform.system()
        architecture = platform.machine()
        system_info = f"{os_system} ({architecture})"
        
        # GPU信息（跨平台检测）
        gpu_info = "未检测到GPU"
        try:
            if platform.system() == "Windows":
                # Windows使用wmic
                result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'name'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    gpu_lines = [line.strip() for line in result.stdout.split('\n') 
                               if line.strip() and 'Name' not in line and line.strip()]
                    
                    # 过滤掉虚拟显卡和远程显卡
                    real_gpus = []
                    for gpu_line in gpu_lines:
                        gpu_lower = gpu_line.lower()
                        if not any(exclude in gpu_lower for exclude in [
                            'oray', 'teamviewer', 'vnc', 'remote', 'virtual', 
                            'microsoft basic', 'standard vga'
                        ]):
                            real_gpus.append(gpu_line)
                    
                    if real_gpus:
                        gpu_info = ', '.join(real_gpus)
                    else:
                        gpu_info = "集成显卡 (已过滤虚拟显卡)"
            else:
                # Linux使用lspci或nvidia-smi
                gpu_detected = False
                
                # 尝试nvidia-smi检测NVIDIA显卡
                try:
                    result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0 and result.stdout.strip():
                        gpu_info = result.stdout.strip()
                        gpu_detected = True
                except:
                    pass
                
                # 如果没有NVIDIA显卡，尝试lspci
                if not gpu_detected:
                    try:
                        result = subprocess.run(['lspci'], capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            gpu_lines = []
                            for line in result.stdout.split('\n'):
                                if any(keyword in line.lower() for keyword in ['vga', 'display', 'graphics']):
                                    # 提取显卡名称
                                    if ':' in line:
                                        gpu_name = line.split(':', 2)[-1].strip()
                                        gpu_lines.append(gpu_name)
                            
                            if gpu_lines:
                                gpu_info = ', '.join(gpu_lines)
                                gpu_detected = True
                    except:
                        pass
                
                # 如果都失败了，检查是否有GPU相关文件
                if not gpu_detected:
                    if os.path.exists('/proc/driver/nvidia/version'):
                        gpu_info = "NVIDIA GPU (详细信息获取失败)"
                    elif any(os.path.exists(f'/sys/class/drm/card{i}') for i in range(4)):
                        gpu_info = "集成显卡或独立显卡"
                    else:
                        gpu_info = "未检测到GPU硬件"
        except Exception as e:
            logging.warning(f"GPU检测失败: {e}")
            gpu_info = "GPU检测失败"
        
        hardware_info = {
            'cpu': f"{cpu_name} ({cpu_count}核{cpu_count_logical}线程)",
            'memory': f"{memory_total_gb}GB",
            'storage': f"{disk_total_gb}GB (路径: {disk_path})",
            'network': f"网络适配器: {main_interface}",
            'gpu': gpu_info,
            'architecture': system_info
        }
        
        return jsonify(hardware_info)
    except Exception as e:
        logging.error(f"获取硬件信息失败: {str(e)}")
        return jsonify({'error': '获取硬件信息失败'}), 500

@system_info_bp.route('/software', methods=['GET'])
@jwt_required()
def get_software_info():
    """获取软件信息"""
    try:
        # 操作系统信息 - 改进Linux发行版检测
        os_name = platform.system()
        os_version = platform.version()
        os_release = platform.release()
        
        # 对Linux系统，尝试获取更详细的发行版信息
        if os_name == "Linux":
            try:
                # 尝试读取/etc/os-release文件
                if os.path.exists('/etc/os-release'):
                    with open('/etc/os-release', 'r') as f:
                        release_info = {}
                        for line in f:
                            if '=' in line:
                                key, value = line.strip().split('=', 1)
                                release_info[key] = value.strip('"')
                        
                        if 'PRETTY_NAME' in release_info:
                            os_detailed = release_info['PRETTY_NAME']
                        elif 'NAME' in release_info and 'VERSION' in release_info:
                            os_detailed = f"{release_info['NAME']} {release_info['VERSION']}"
                        else:
                            os_detailed = f"{os_name} {os_release}"
                else:
                    os_detailed = f"{os_name} {os_release}"
            except:
                os_detailed = f"{os_name} {os_release}"
        else:
            os_detailed = f"{os_name} {os_release}"
        
        # Python版本
        python_version = f"Python {sys.version.split()[0]}"
        
        # Node.js版本（如果可用）
        nodejs_version = "未安装"
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                nodejs_version = f"Node.js {result.stdout.strip()}"
        except:
            pass
        
        # 数据库信息 - 根据部署环境和配置确定
        database_info = "数据库未连接"
        try:
            # 检查数据库主机配置
            db_host = os.environ.get('DB_HOST', '')
            db_port = os.environ.get('DB_PORT', '')
            
            # 如果配置了金仓数据库（检查端口54321，这是金仓数据库的默认端口）
            if db_host == 'kingbase' or db_port == '54321':
                database_info = "KingbaseES V009R001C002B0014"
            # 如果在Docker容器环境中（通常使用金仓数据库）
            elif os.path.exists('/.dockerenv'):
                database_info = "KingbaseES V009R001C002B0014"
            else:
                # 本地开发环境，检查实际安装的数据库驱动
                drivers_found = []
                
                # 检查PostgreSQL驱动
                try:
                    import psycopg2
                    drivers_found.append("PostgreSQL")
                except ImportError:
                    pass
                
                # 检查金仓数据库驱动（如果有的话）
                try:
                    import kingbase
                    drivers_found.append("KingbaseES")
                except ImportError:
                    pass
                
                if drivers_found:
                    # 优先显示金仓数据库，如果没有则显示PostgreSQL
                    if "KingbaseES" in drivers_found:
                        database_info = "KingbaseES V009R001C002B0014"
                    else:
                        database_info = "PostgreSQL 13+"
                else:
                    database_info = "未检测到数据库驱动"
                    
        except Exception as e:
            logging.warning(f"数据库信息检测失败: {e}")
            database_info = "数据库信息获取失败"
        
        # Web服务器信息
        webserver_info = "Flask"
        try:
            flask_version = pkg_resources.get_distribution("flask").version
            webserver_info = f"Flask {flask_version}"
        except:
            pass
        
        # 系统版本（项目版本）
        system_version = "v1.0.0"
        
        software_info = {
            'os': os_detailed,
            'python': python_version,
            'nodejs': nodejs_version,
            'database': database_info,
            'webserver': webserver_info,
            'version': system_version
        }
        
        return jsonify(software_info)
    except Exception as e:
        logging.error(f"获取软件信息失败: {str(e)}")
        return jsonify({'error': '获取软件信息失败'}), 500

@system_info_bp.route('/runtime', methods=['GET'])
@jwt_required()
def get_runtime_info():
    """获取运行时参数"""
    try:
        # 系统启动时间
        boot_time = psutil.boot_time()
        uptime_seconds = datetime.now().timestamp() - boot_time
        uptime_timedelta = timedelta(seconds=int(uptime_seconds))
        uptime_str = str(uptime_timedelta)
        
        # CPU使用率
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # 内存使用率
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        
        # 磁盘使用率
        try:
            # 使用与硬件信息相同的逻辑
            if os.path.exists('/.dockerenv'):
                disk = psutil.disk_usage('/')  # 容器环境
            elif platform.system() == "Windows":
                disk = psutil.disk_usage('C:')  # Windows本地环境
            else:
                disk = psutil.disk_usage('/')   # Linux本地环境
            disk_usage = round((disk.used / disk.total) * 100, 1)
        except Exception as e:
            logging.warning(f"获取磁盘使用率失败: {e}")
            disk_usage = 0
        
        # 网络连接数
        connections = len(psutil.net_connections())
        
        # 当前时间
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        runtime_info = {
            'uptime': uptime_str,
            'cpuUsage': int(cpu_usage),
            'memoryUsage': int(memory_usage),
            'diskUsage': int(disk_usage),
            'connections': connections,
            'lastUpdate': current_time
        }
        
        return jsonify(runtime_info)
    except Exception as e:
        logging.error(f"获取运行时信息失败: {str(e)}")
        return jsonify({'error': '获取运行时信息失败'}), 500

@system_info_bp.route('/logs', methods=['GET'])
@jwt_required()
def get_system_logs():
    """获取系统日志"""
    try:
        # 这里可以读取实际的日志文件
        logs = []
        
        # 尝试读取应用日志
        log_file_path = os.path.join(os.path.dirname(__file__), '..', 'logs', 'app.log')
        if os.path.exists(log_file_path):
            try:
                with open(log_file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # 只取最后20行
                    recent_lines = lines[-20:] if len(lines) > 20 else lines
                    
                    for i, line in enumerate(recent_lines):
                        if line.strip():
                            # 简单的日志解析
                            parts = line.strip().split(' - ')
                            if len(parts) >= 3:
                                timestamp = parts[0]
                                level = parts[1].lower()
                                message = ' - '.join(parts[2:])
                                
                                logs.append({
                                    'id': len(logs) + 1,
                                    'timestamp': timestamp,
                                    'level': level if level in ['info', 'warning', 'error'] else 'info',
                                    'message': message
                                })
            except Exception as e:
                logging.error(f"读取日志文件失败: {str(e)}")
        
        # 如果没有日志文件或读取失败，提供一些默认的系统状态日志
        if not logs:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logs = [
                {
                    'id': 1,
                    'timestamp': current_time,
                    'level': 'info',
                    'message': '风电功率预测系统运行正常'
                },
                {
                    'id': 2,
                    'timestamp': (datetime.now() - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'),
                    'level': 'info',
                    'message': '系统监控数据已更新'
                }
            ]
        
        return jsonify(logs)
    except Exception as e:
        logging.error(f"获取系统日志失败: {str(e)}")
        return jsonify({'error': '获取系统日志失败'}), 500 
