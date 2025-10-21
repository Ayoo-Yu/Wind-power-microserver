"""
风电功率预测系统 - Prometheus指标收集器
用于收集和暴露系统性能指标
"""

import time
import threading
from collections import defaultdict
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from prometheus_client.core import CounterMetricFamily, HistogramMetricFamily, GaugeMetricFamily

class WindPowerMetrics:
    """风电功率预测系统指标收集器"""

    def __init__(self):
        self.registry = CollectorRegistry()

        # 请求计数器
        self.request_counter = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )

        # 请求耗时
        self.request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration',
            ['method', 'endpoint'],
            registry=self.registry
        )

        # 数据库操作计数器
        self.db_operations = Counter(
            'database_operations_total',
            'Total database operations',
            ['operation', 'table'],
            registry=self.registry
        )

        # 数据库连接数
        self.db_connections = Gauge(
            'database_connections_active',
            'Active database connections',
            registry=self.registry
        )

        # 预测任务计数器
        self.prediction_tasks = Counter(
            'prediction_tasks_total',
            'Total prediction tasks',
            ['task_type', 'farm_code', 'status'],
            registry=self.registry
        )

        # 数据上传计数器
        self.data_uploads = Counter(
            'data_uploads_total',
            'Total data uploads',
            ['data_type', 'farm_code', 'status'],
            registry=self.registry
        )

        # 系统资源使用率
        self.system_resources = Gauge(
            'system_resources_usage',
            'System resource usage',
            ['resource_type'],
            registry=self.registry
        )

        # 活跃用户数
        self.active_users = Gauge(
            'active_users_total',
            'Total active users',
            registry=self.registry
        )

        # 风场状态
        self.farm_status = Gauge(
            'wind_farm_status',
            'Wind farm status',
            ['farm_code', 'status_type'],
            registry=self.registry
        )

        # 预测准确性
        self.prediction_accuracy = Gauge(
            'prediction_accuracy',
            'Prediction accuracy metrics',
            ['farm_code', 'prediction_type', 'metric_type'],
            registry=self.registry
        )

        # 内部统计
        self._stats = defaultdict(int)
        self._lock = threading.Lock()

    def record_request(self, method, endpoint, status, duration):
        """记录HTTP请求"""
        self.request_counter.labels(method=method, endpoint=endpoint, status=status).inc()
        self.request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    def record_db_operation(self, operation, table):
        """记录数据库操作"""
        self.db_operations.labels(operation=operation, table=table).inc()

    def set_db_connections(self, count):
        """设置数据库连接数"""
        self.db_connections.set(count)

    def record_prediction_task(self, task_type, farm_code, status):
        """记录预测任务"""
        self.prediction_tasks.labels(task_type=task_type, farm_code=farm_code, status=status).inc()

    def record_data_upload(self, data_type, farm_code, status):
        """记录数据上传"""
        self.data_uploads.labels(data_type=data_type, farm_code=farm_code, status=status).inc()

    def set_system_resource(self, resource_type, value):
        """设置系统资源使用率"""
        self.system_resources.labels(resource_type=resource_type).set(value)

    def set_active_users(self, count):
        """设置活跃用户数"""
        self.active_users.set(count)

    def set_farm_status(self, farm_code, status_type, value):
        """设置风场状态"""
        self.farm_status.labels(farm_code=farm_code, status_type=status_type).set(value)

    def set_prediction_accuracy(self, farm_code, prediction_type, metric_type, value):
        """设置预测准确性"""
        self.prediction_accuracy.labels(
            farm_code=farm_code,
            prediction_type=prediction_type,
            metric_type=metric_type
        ).set(value)

    def get_metrics(self):
        """获取所有指标的Prometheus格式数据"""
        return generate_latest(self.registry)

    def increment_stat(self, key):
        """增加内部统计计数"""
        with self._lock:
            self._stats[key] += 1

    def get_stats(self):
        """获取内部统计数据"""
        with self._lock:
            return dict(self._stats)

# 全局指标收集器实例
metrics_collector = WindPowerMetrics()

# 请求计时装饰器
def timed_request(func):
    """请求计时装饰器"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            status = '200'
        except Exception as e:
            status = '500'
            raise e
        finally:
            duration = time.time() - start_time
            # 这里需要从请求上下文中获取method和endpoint
            # 在实际使用时需要在Flask请求上下文中调用
            metrics_collector.record_request('UNKNOWN', 'UNKNOWN', status, duration)
        return result
    return wrapper

# 数据库操作装饰器
def db_operation(operation, table):
    """数据库操作装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            metrics_collector.record_db_operation(operation, table)
            return func(*args, **kwargs)
        return wrapper
    return decorator

def init_metrics():
    """初始化指标收集器"""
    return metrics_collector

def get_metrics():
    """获取指标数据"""
    return metrics_collector.get_metrics()