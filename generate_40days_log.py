#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
40天日志生成脚本
生成模拟风电功率预测系统的后端日志文件
"""

import random
import datetime
import os
from typing import List, Tuple

class LogGenerator:
    def __init__(self):
        # 日志级别
        self.log_levels = ["INFO", "WARNING", "ERROR", "DEBUG"]
        
        # 模块名称
        self.modules = [
            "logging_config",
            "operational_data_upload", 
            "forecast_service",
            "data_processor",
            "model_trainer",
            "auth_service",
            "database_manager",
            "weather_data_fetcher",
            "power_calculator",
            "validation_service",
            "file_handler",
            "scheduler",
            "api_router",
            "turbine_monitor"
        ]
        
        # 数据表名称
        self.table_names = [
            "available_capacity_data",
            "available_power_data", 
            "installed_capacity_data",
            "theoretical_power_data",
            "turbine_power_data",
            "weather_data",
            "forecast_results",
            "model_parameters"
        ]
        
        # 启动消息模板
        self.startup_messages = [
            "Wind Forecast Backend Startup with TimedRotatingFileHandler for app.log",
            "系统初始化完成，开始监听端口 8000",
            "数据库连接池初始化成功",
            "模型加载完成，准备接受预测请求",
            "定时任务调度器启动成功"
        ]
        
        # 数据处理消息模板
        self.data_processing_messages = [
            "正在处理第 {chunk} 块数据，表: {table}...",
            "第 {chunk} 块: 在 {total} 个有效时间戳中找到 {existing} 个现有记录",
            "第 {chunk} 块: 批量插入了 {inserted} 条新记录",
            "完成处理表 {table} 的所有块。总插入: {total_inserted}, 总更新: {total_updated}, 总错误: {total_errors}",
            "表 {table} 最终提交成功",
            "数据验证完成，发现 {anomalies} 个异常值",
            "正在执行数据清洗操作...",
            "特征工程处理完成，生成 {features} 个特征"
        ]
        
        # 预测相关消息
        self.forecast_messages = [
            "开始执行风速预测，使用模型版本 v{version}",
            "气象数据获取成功，覆盖未来 {hours} 小时",
            "功率预测计算完成，预测精度: {accuracy}%",
            "预测结果已保存到数据库，预测ID: {forecast_id}",
            "模型性能评估完成，RMSE: {rmse}, MAE: {mae}",
            "正在更新预测模型参数...",
            "模型训练完成，新模型准确率提升 {improvement}%"
        ]
        
        # 系统健康状态消息（用于显示高可用性）
        self.health_messages = [
            "系统健康检查通过，所有服务运行正常",
            "数据库连接池状态良好，连接数: {connections}/50",
            "内存使用率: {memory}%，系统运行稳定",
            "CPU使用率: {cpu}%，负载正常",
            "磁盘使用率: {disk}%，存储空间充足",
            "网络连接正常，延迟: {latency}ms",
            "所有风机数据接收正常，在线率: {online_rate}%",
            "模型服务响应正常，平均响应时间: {response_time}ms",
            "定时任务执行成功，下次执行时间: {next_run}",
            "数据备份完成，备份文件大小: {backup_size}GB",
            "系统监控告警正常，无异常事件",
            "API服务健康，过去1小时成功率: {success_rate}%",
            "缓存系统运行良好，命中率: {cache_hit}%",
            "负载均衡器状态正常，活跃连接: {active_connections}",
            "SSL证书有效，到期时间: {cert_days}天后"
        ]
        
        # 警告消息模板（轻微问题，不影响系统可用性）
        self.warning_messages = [
            "数据字段 '{field}' 类型转换提醒，已使用默认值处理",
            "数据库连接延迟稍高: {latency}ms，在正常范围内",
            "磁盘使用量提醒，剩余: {space}GB，建议清理历史数据",
            "风机 {turbine_id} 数据延迟，已切换备用数据源",
            "气象服务API响应稍慢，耗时 {time}s，已缓存结果",
            "模型预测精度监控提醒，当前精度: {accuracy}%",
            "检测到风机 {turbine_id} 功率波动，已记录分析",
            "缓存过期提醒，正在自动刷新缓存",
            "日志文件大小提醒，当前: {size}MB，已启动轮转"
        ]
        
        # 错误消息模板（偶发问题，系统具备恢复能力）
        self.error_messages = [
            "CSV数据处理异常，已重试成功: {table}",
            "数据库连接短暂中断，已自动重连成功",
            "临时模型文件锁定，已释放并重新加载",
            "气象数据服务临时不可用，已切换备用源",
            "临时文件清理完成，系统恢复正常",
            "内存使用峰值告警，已触发垃圾回收，内存已释放",
            "网络抖动检测，连接已恢复，数据同步正常"
        ]
        
        # 错误堆栈示例
        self.error_stacks = [
            """Traceback (most recent call last):
  File "D:\\my-vue-project\\wind-power-forecast\\backend\\routes\\operational_data_upload.py", line 122, in upload_operational_csv
    chunk_iterator = pd.read_csv(file.stream, chunksize=CHUNK_SIZE, iterator=True)
  File "D:\\my-vue-project\\wind-power-forecast\\backend\\wind-power-env\\lib\\site-packages\\pandas\\io\\parsers\\readers.py", line 1026, in read_csv
    return _read(filepath_or_buffer, kwds)
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xce in position 203: invalid continuation byte""",
            
            """Traceback (most recent call last):
  File "D:\\my-vue-project\\wind-power-forecast\\backend\\services\\database_manager.py", line 45, in connect
    conn = psycopg2.connect(DATABASE_URL)
psycopg2.OperationalError: could not connect to server: Connection refused""",
            
            """Traceback (most recent call last):
  File "D:\\my-vue-project\\wind-power-forecast\\backend\\services\\model_service.py", line 78, in load_model
    model = joblib.load(model_path)
  File "joblib\\numpy_pickle.py", line 587, in load
    obj = _unpickle(fobj, filename, mmap_mode)
FileNotFoundError: [Errno 2] No such file or directory: 'models/wind_forecast_v2.joblib'"""
        ]

    def generate_timestamp(self, base_date: datetime.datetime) -> str:
        """生成时间戳"""
        # 在一天内随机分布时间
        random_seconds = random.randint(0, 86400-1)  # 一天的秒数
        timestamp = base_date + datetime.timedelta(seconds=random_seconds)
        
        # 格式化为日志格式
        return timestamp.strftime("[%Y-%m-%d %H:%M:%S,") + f"{random.randint(100, 999)}]"

    def generate_info_log(self, timestamp: str) -> str:
        """生成INFO级别日志"""
        module = random.choice(self.modules)
        
        if module == "logging_config":
            message = random.choice(self.startup_messages)
        elif module == "operational_data_upload":
            template = random.choice(self.data_processing_messages)
            message = template.format(
                chunk=random.randint(1, 10),
                table=random.choice(self.table_names),
                total=random.randint(100, 1000),
                existing=random.randint(0, 50),
                inserted=random.randint(50, 500),
                total_inserted=random.randint(500, 5000),
                total_updated=random.randint(0, 100),
                total_errors=random.randint(0, 5),
                anomalies=random.randint(0, 20),
                features=random.randint(10, 100)
            )
        elif module == "forecast_service":
            template = random.choice(self.forecast_messages)
            message = template.format(
                version=f"{random.randint(1, 5)}.{random.randint(0, 9)}",
                hours=random.choice([24, 48, 72]),
                accuracy=round(random.uniform(85, 98), 2),
                forecast_id=f"FCST_{random.randint(100000, 999999)}",
                rmse=round(random.uniform(0.1, 2.5), 3),
                mae=round(random.uniform(0.05, 1.8), 3),
                improvement=round(random.uniform(0.5, 5.0), 1)
            )
        elif random.random() < 0.4:  # 40%概率显示系统健康状态
            template = random.choice(self.health_messages)
            message = template.format(
                connections=random.randint(20, 40),
                memory=random.randint(45, 75),
                cpu=random.randint(15, 60),
                disk=random.randint(25, 65),
                latency=random.randint(10, 50),
                online_rate=round(random.uniform(98.5, 99.9), 1),
                response_time=random.randint(50, 150),
                next_run=f"{random.randint(1, 23):02d}:{random.randint(0, 59):02d}",
                backup_size=round(random.uniform(1.2, 5.8), 1),
                success_rate=round(random.uniform(99.2, 99.9), 1),
                cache_hit=random.randint(85, 98),
                active_connections=random.randint(100, 500),
                cert_days=random.randint(30, 180)
            )
        else:
            messages = [
                f"服务 {module} 运行正常",
                f"定时任务执行成功: {module}",
                f"数据同步完成: {module}",
                f"监控检查通过: {module}",
                f"缓存更新完成: {module}",
                f"数据质量检查通过: {module}",
                f"系统性能监控正常: {module}",
                f"安全扫描完成，无威胁: {module}"
            ]
            message = random.choice(messages)
        
        return f"{timestamp} INFO in {module}: {message}"

    def generate_warning_log(self, timestamp: str) -> str:
        """生成WARNING级别日志"""
        module = random.choice(self.modules)
        template = random.choice(self.warning_messages)
        
        message = template.format(
            field=random.choice(["turbine_id", "power_value", "wind_speed", "temperature"]),
            latency=random.randint(200, 500),  # 降低延迟范围
            space=round(random.uniform(8.0, 15.0), 1),  # 增加剩余空间
            turbine_id=f"WT{random.randint(1, 50)}",
            time=round(random.uniform(1.5, 3.0), 1),  # 降低响应时间
            accuracy=round(random.uniform(92, 96), 1),
            size=random.randint(50, 200),
            power=round(random.uniform(0.1, 3.5), 2)
        )
        
        return f"{timestamp} WARNING in {module}: {message}"

    def generate_error_log(self, timestamp: str) -> str:
        """生成ERROR级别日志（显示系统恢复能力）"""
        module = random.choice(self.modules)
        template = random.choice(self.error_messages)
        
        message = template.format(
            table=random.choice(self.table_names)
        )
        
        # 减少堆栈跟踪的概率，因为这些是已恢复的问题
        if random.random() < 0.1:  # 只有10%概率显示技术细节
            return f"{timestamp} ERROR in {module}: {message} (已自动恢复)"
        else:
            return f"{timestamp} ERROR in {module}: {message}"

    def generate_debug_log(self, timestamp: str) -> str:
        """生成DEBUG级别日志"""
        module = random.choice(self.modules)
        debug_messages = [
            f"执行SQL查询: SELECT * FROM {random.choice(self.table_names)} WHERE timestamp > '2025-01-01'",
            f"缓存命中率: {random.randint(75, 95)}%",
            f"内存使用情况: {random.randint(40, 80)}%",
            f"HTTP请求处理时间: {random.randint(50, 200)}ms",
            f"模型推理时间: {random.randint(10, 100)}ms",
            f"数据库连接池状态: {random.randint(5, 20)}/20",
        ]
        
        message = random.choice(debug_messages)
        return f"{timestamp} DEBUG in {module}: {message}"

    def generate_daily_logs(self, date: datetime.datetime) -> List[str]:
        """生成一天的日志"""
        logs = []
        
        # 每天生成80-300条日志（增加日志量显示活跃度）
        num_logs = random.randint(80, 300)
        
        for _ in range(num_logs):
            timestamp = self.generate_timestamp(date)
            
            # 调整日志级别分布以体现高可用性：INFO 88%, WARNING 10%, ERROR 1.5%, DEBUG 0.5%
            rand = random.random()
            if rand < 0.88:
                log_entry = self.generate_info_log(timestamp)
            elif rand < 0.98:
                log_entry = self.generate_warning_log(timestamp)
            elif rand < 0.995:
                log_entry = self.generate_error_log(timestamp)
            else:
                log_entry = self.generate_debug_log(timestamp)
            
            logs.append(log_entry)
        
        # 按时间戳排序
        logs.sort(key=lambda x: x[:23])  # 根据时间戳部分排序
        return logs

    def generate_40days_log(self, output_file: str = "app_40days.log"):
        """生成40天的日志文件"""
        print(f"开始生成40天日志文件: {output_file}")
        
        # 计算开始日期（40天前）
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=40)
        
        total_logs = 0
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for day in range(40):
                current_date = start_date + datetime.timedelta(days=day)
                print(f"生成 {current_date.strftime('%Y-%m-%d')} 的日志...")
                
                daily_logs = self.generate_daily_logs(current_date)
                total_logs += len(daily_logs)
                
                for log_entry in daily_logs:
                    f.write(log_entry + '\n')
        
        print(f"日志生成完成！")
        print(f"文件: {output_file}")
        print(f"总计: {total_logs} 条日志")
        print(f"时间范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")

def main():
    """主函数"""
    generator = LogGenerator()
    
    # 生成40天日志
    output_file = "wind_forecast_40days.log"
    generator.generate_40days_log(output_file)
    
    # 显示文件大小
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        print(f"文件大小: {file_size / 1024 / 1024:.2f} MB")

if __name__ == "__main__":
    main() 