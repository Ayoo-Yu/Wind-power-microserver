#!/usr/bin/env python3
"""
Docker容器健康检查脚本
检查SCADA客户端的运行状态
"""
import json
import sys
import os
from datetime import datetime, timedelta, timezone

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))

def check_health():
    """检查客户端健康状态"""
    try:
        # 检查状态文件是否存在
        status_file = "/app/state/status.json"
        if not os.path.exists(status_file):
            print("Health check failed: Status file not found", file=sys.stderr)
            return False
        
        # 读取状态
        with open(status_file, 'r', encoding='utf-8') as f:
            status = json.load(f)
        
        # 检查客户端是否运行
        client_running = status.get('client_running', False)
        if not client_running:
            print("Health check failed: Client not running", file=sys.stderr)
            return False
        
        # 检查最后更新时间（5分钟内有更新认为健康）
        last_time_str = status.get('program_last_running_time')
        if last_time_str:
            try:
                # 解析时间戳
                if last_time_str.endswith('Z'):
                    last_time_str = last_time_str[:-1] + '+00:00'
                elif '+' not in last_time_str and last_time_str.count(':') >= 2:
                    # 如果没有时区信息，假设是北京时间
                    last_dt = datetime.fromisoformat(last_time_str)
                    last_dt = last_dt.replace(tzinfo=BEIJING_TZ)
                else:
                    last_dt = datetime.fromisoformat(last_time_str)
                
                current_time = datetime.now(BEIJING_TZ)
                time_diff = current_time - last_dt
                
                if time_diff > timedelta(minutes=5):
                    print(f"Health check failed: Last update too old ({time_diff})", file=sys.stderr)
                    return False
                    
            except Exception as e:
                print(f"Health check failed: Error parsing timestamp: {e}", file=sys.stderr)
                return False
        
        # 检查缓存大小是否合理
        cache_size = status.get('cache_size', 0)
        if cache_size > 5000:  # 缓存过大可能有内存泄漏
            print(f"Health check warning: Cache size is large ({cache_size})", file=sys.stderr)
            # 不返回False，只是警告
        
        # 健康检查成功
        print("Health check passed", file=sys.stdout)
        return True
        
    except FileNotFoundError:
        print("Health check failed: Status file not found", file=sys.stderr)
        return False
    except json.JSONDecodeError as e:
        print(f"Health check failed: Invalid JSON in status file: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Health check failed: Unexpected error: {e}", file=sys.stderr)
        return False

def check_disk_space():
    """检查磁盘空间"""
    try:
        import shutil
        
        # 检查日志目录空间
        logs_usage = shutil.disk_usage("/app/logs")
        state_usage = shutil.disk_usage("/app/state")
        
        # 计算可用空间百分比
        logs_free_percent = (logs_usage.free / logs_usage.total) * 100
        state_free_percent = (state_usage.free / state_usage.total) * 100
        
        if logs_free_percent < 10:  # 少于10%空间
            print(f"Health check warning: Low disk space in logs ({logs_free_percent:.1f}% free)", file=sys.stderr)
        
        if state_free_percent < 10:
            print(f"Health check warning: Low disk space in state ({state_free_percent:.1f}% free)", file=sys.stderr)
            
    except Exception as e:
        print(f"Disk space check failed: {e}", file=sys.stderr)

def main():
    """主函数"""
    try:
        # 执行基本健康检查
        health_ok = check_health()
        
        # 执行磁盘空间检查（不影响健康状态）
        check_disk_space()
        
        # 返回健康状态
        sys.exit(0 if health_ok else 1)
        
    except KeyboardInterrupt:
        print("Health check interrupted", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Health check script error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main() 