# 风功率预测系统 - 故障排除指南

## 目录
1. [系统启动问题](#系统启动问题)
2. [数据库连接问题](#数据库连接问题)
3. [API服务问题](#api服务问题)
4. [预测精度问题](#预测精度问题)
5. [性能问题](#性能问题)
6. [数据问题](#数据问题)
7. [安全问题](#安全问题)
8. [监控告警问题](#监控告警问题)
9. [日志分析指南](#日志分析指南)
10. [紧急处理流程](#紧急处理流程)

---

## 系统启动问题

### 🔴 服务无法启动

#### 症状表现
- Docker容器状态为 `Exited`
- 服务端口无法访问
- 启动日志显示错误信息

#### 排查步骤

1. **检查容器状态**
```bash
# 查看所有容器状态
docker-compose ps

# 查看失败容器的日志
docker-compose logs [service-name]

# 查看最近的日志
docker-compose logs --tail=50 [service-name]
```

2. **检查系统资源**
```bash
# 检查内存使用
free -h

# 检查磁盘空间
df -h

# 检查CPU负载
top -n 1
```

3. **检查端口冲突**
```bash
# 查看端口占用情况
netstat -tlnp | grep -E "5000|5432|6379|8080"

# 或者使用ss命令
ss -tlnp | grep -E "5000|5432|6379|8080"
```

#### 常见解决方案

**端口被占用**
```bash
# 找出占用进程
lsof -i :5000

# 终止进程（谨慎操作）
kill -9 [PID]

# 修改端口配置
# 编辑 docker-compose.yml 文件，修改端口映射
```

**内存不足**
```bash
# 清理Docker缓存
docker system prune -a

# 增加Docker内存限制
# 编辑 /etc/docker/daemon.json
{
  "default-ulimits": {
    "memlock": {"Name": "memlock", "Hard": -1, "Soft": -1}
  }
}

# 重启Docker服务
systemctl restart docker
```

**依赖服务未就绪**
```bash
# 检查依赖服务状态
docker-compose ps postgres redis

# 等待依赖服务完全启动
sleep 30

# 重新启动应用服务
docker-compose restart api frontend
```

### 🔴 数据库初始化失败

#### 症状表现
- PostgreSQL容器反复重启
- 数据库连接超时
- 表结构创建失败

#### 排查步骤

1. **检查数据库日志**
```bash
docker-compose logs postgres

# 查看具体错误信息
docker-compose logs postgres | grep -i "error\|fatal"
```

2. **检查数据库配置**
```bash
# 进入数据库容器
docker-compose exec postgres bash

# 检查数据库是否创建
psql -U postgres -l

# 检查表是否存在
psql -U postgres -d windpower -c "\dt"
```

3. **验证数据库连接**
```bash
# 从API容器测试连接
docker-compose exec api python -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='postgres',
        port=5432,
        user='postgres',
        password='password',
        dbname='windpower'
    )
    print('数据库连接成功')
    conn.close()
except Exception as e:
    print(f'连接失败: {e}')
"
```

#### 解决方案

**数据库权限问题**
```sql
-- 在PostgreSQL中执行
CREATE USER windpower WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE windpower TO windpower;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO windpower;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO windpower;
```

**数据库初始化脚本失败**
```bash
# 手动运行初始化脚本
docker-compose exec api python init_database.py

# 或者运行migration
docker-compose exec api python manage.py db upgrade
```

---

## 数据库连接问题

### 🔴 连接超时

#### 症状表现
- API返回 "Connection timed out"
- 数据库查询超时
- 连接池耗尽

#### 排查步骤

1. **检查网络连接**
```bash
# 测试容器间网络
docker-compose exec api ping postgres

# 检查网络配置
docker network ls
docker network inspect windpower_default
```

2. **检查连接参数**
```bash
# 验证环境变量
docker-compose exec api env | grep DB_

# 测试连接字符串
docker-compose exec api python -c "
import os
print('DB_HOST:', os.environ.get('DB_HOST'))
print('DB_PORT:', os.environ.get('DB_PORT'))
print('DB_NAME:', os.environ.get('DB_NAME'))
"
```

3. **监控数据库连接**
```sql
-- 查看当前连接
SELECT count(*) as connections,
       state,
       application_name
FROM pg_stat_activity
WHERE datname = 'windpower'
GROUP BY state, application_name;

-- 查看连接限制
SELECT name, setting FROM pg_settings WHERE name LIKE 'max_connections%';
```

#### 解决方案

**增加连接超时时间**
```python
# 在数据库连接配置中
DATABASE_CONFIG = {
    'host': 'postgres',
    'port': 5432,
    'user': 'postgres',
    'password': 'password',
    'dbname': 'windpower',
    'connect_timeout': 30,  # 增加超时时间
    'application_name': 'windpower_api'
}
```

**优化连接池配置**
```python
# SQLAlchemy连接池配置
SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 20,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'max_overflow': 30,
    'pool_timeout': 30
}
```

**增加数据库最大连接数**
```bash
# 在PostgreSQL配置中
echo "max_connections = 200" >> /var/lib/postgresql/data/postgresql.conf
echo "shared_buffers = 256MB" >> /var/lib/postgresql/data/postgresql.conf

# 重启数据库
docker-compose restart postgres
```

### 🔴 数据库性能慢

#### 症状表现
- 查询响应时间超过5秒
- CPU使用率持续高位
- 磁盘I/O负载高

#### 排查步骤

1. **分析慢查询**
```sql
-- 启用慢查询日志
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();

-- 查看慢查询
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;
```

2. **检查索引使用情况**
```sql
-- 查看表索引
\d weather_data

-- 分析查询计划
EXPLAIN ANALYZE SELECT * FROM weather_data
WHERE timestamp > '2024-01-01'
AND wind_speed > 10;
```

3. **监控系统资源**
```bash
# 数据库容器资源使用
docker stats postgres

# 查看数据库进程
docker-compose exec postgres ps aux | head -20
```

#### 解决方案

**创建优化索引**
```sql
-- 为常用查询创建索引
CREATE INDEX CONCURRENTLY idx_weather_data_timestamp
ON weather_data(timestamp);

CREATE INDEX CONCURRENTLY idx_weather_data_speed_direction
ON weather_data(wind_speed, wind_direction);

CREATE INDEX CONCURRENTLY idx_power_predictions_time_model
ON power_predictions(prediction_time, model_id);

-- 创建复合索引
CREATE INDEX CONCURRENTLY idx_weather_composite
ON weather_data(timestamp, wind_speed, wind_direction)
WHERE wind_speed IS NOT NULL;
```

**表分区优化**
```sql
-- 按时间分区
CREATE TABLE weather_data_2024 PARTITION OF weather_data
FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE weather_data_2023 PARTITION OF weather_data
FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');

-- 自动创建分区函数
CREATE OR REPLACE FUNCTION create_monthly_partition() RETURNS trigger AS $$
BEGIN
    EXECUTE format('CREATE TABLE IF NOT EXISTS weather_data_%s '
                   'PARTITION OF weather_data '
                   'FOR VALUES FROM (%L) TO (%L)',
                   to_char(NEW.timestamp, 'YYYY_MM'),
                   date_trunc('month', NEW.timestamp),
                   date_trunc('month', NEW.timestamp) + interval '1 month');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

**配置优化**
```bash
# PostgreSQL性能调优
echo "shared_buffers = 512MB" >> /var/lib/postgresql/data/postgresql.conf
echo "effective_cache_size = 2GB" >> /var/lib/postgresql/data/postgresql.conf
echo "work_mem = 32MB" >> /var/lib/postgresql/data/postgresql.conf
echo "maintenance_work_mem = 256MB" >> /var/lib/postgresql/data/postgresql.conf
echo "wal_buffers = 16MB" >> /var/lib/postgresql/data/postgresql.conf
echo "checkpoint_completion_target = 0.9" >> /var/lib/postgresql/data/postgresql.conf
```

---

## API服务问题

### 🔴 API响应超时

#### 症状表现
- 请求响应时间超过30秒
- 返回504 Gateway Timeout
- 大量请求堆积

#### 排查步骤

1. **检查API日志**
```bash
# 查看API服务日志
docker-compose logs api | grep -i "timeout\|error\|slow"

# 查看请求响应时间
docker-compose logs api | grep -E "POST|GET" | tail -20
```

2. **监控请求统计**
```bash
# 使用Prometheus查询
# API请求延迟
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 请求错误率
rate(http_requests_total{status=~"5.."}[5m])
```

3. **检查后端依赖**
```bash
# 数据库响应时间
docker-compose exec api python -c "
import time
from database import db
start = time.time()
result = db.session.execute('SELECT 1').fetchall()
print(f'DB query time: {time.time() - start:.3f}s')
"
```

#### 解决方案

**优化API配置**
```python
# Gunicorn配置优化
# docker-compose.yml
command: gunicorn --workers 8 --worker-class gevent --worker-connections 1000 \\
                  --timeout 120 --keep-alive 5 --max-requests 1000 \\
                  --max-requests-jitter 100 --graceful-timeout 30 \\
                  --bind 0.0.0.0:5000 app:app
```

**增加超时时间**
```python
# Flask应用配置
class Config:
    # 数据库连接超时
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'connect_timeout': 60,
            'application_name': 'windpower_api'
        },
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }

    # 请求超时
    REQUEST_TIMEOUT = 120
```

**启用查询缓存**
```python
# Redis缓存配置
import redis
from functools import wraps

redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

def cache_result(expiration=300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"

            # 尝试从缓存获取
            cached_result = redis_client.get(cache_key)
            if cached_result:
                return json.loads(cached_result)

            # 执行函数
            result = func(*args, **kwargs)

            # 缓存结果
            redis_client.setex(cache_key, expiration, json.dumps(result))
            return result
        return wrapper
    return decorator

# 使用示例
@cache_result(expiration=600)
def get_model_predictions(model_id, start_date, end_date):
    # 复杂的预测计算
    return predictions
```

### 🔴 内存泄漏

#### 症状表现
- 内存使用率持续上升
- 服务响应变慢
- 最终服务崩溃

#### 排查步骤

1. **监控内存使用**
```bash
# 实时监控内存
docker stats api --no-stream

# 查看内存使用趋势
ps aux | grep python | grep -v grep
```

2. **分析内存使用**
```python
# 内存分析脚本
import gc
import tracemalloc
import linecache

def display_top(snapshot, key_type='lineno', limit=10):
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "*tracemalloc*"),
    ))
    top_stats = snapshot.statistics(key_type)

    print("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        print("#%s: %s:%s: %.1f KiB" % (index, frame.filename, frame.lineno, stat.size / 1024))
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            print("    %s" % line)

# 开始跟踪内存分配
tracemalloc.start()

# 在需要分析的地方添加
snapshot = tracemalloc.take_snapshot()
display_top(snapshot)
```

3. **检查对象引用**
```python
# 检查循环引用
import gc

def find_cyclic_references():
    # 收集垃圾
    gc.collect()

    # 找到循环引用
    for obj in gc.garbage:
        print(f"发现循环引用对象: {type(obj)}")
        print(f"对象大小: {obj.__sizeof__()}")

# 启用循环引用调试
gc.set_debug(gc.DEBUG_LEAK)
```

#### 解决方案

**及时释放资源**
```python
# 确保文件和连接正确关闭
with open('large_file.csv', 'r') as f:
    data = f.read()

# 使用上下文管理器
class DatabaseConnection:
    def __enter__(self):
        self.conn = psycopg2.connect(**db_config)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

# 使用示例
with DatabaseConnection() as conn:
    # 数据库操作
    pass
```

**优化数据结构**
```python
# 使用生成器代替列表
def read_large_csv(file_path):
    """使用生成器读取大文件"""
    with open(file_path, 'r') as f:
        for line in f:
            yield process_line(line)

# 使用__slots__减少内存占用
class PredictionResult:
    __slots__ = ['timestamp', 'predicted_power', 'confidence_interval']

    def __init__(self, timestamp, predicted_power, confidence_interval):
        self.timestamp = timestamp
        self.predicted_power = predicted_power
        self.confidence_interval = confidence_interval
```

**定期垃圾回收**
```python
import gc

# 定期垃圾回收
def periodic_gc():
    """定期执行垃圾回收"""
    gc.collect()
    print(f"垃圾回收完成，回收了 {gc.garbage} 个对象")

# 在长时间运行的任务中添加
def long_running_task():
    for i in range(1000):
        # 处理任务
        process_data()

        # 每100次执行一次垃圾回收
        if i % 100 == 0:
            periodic_gc()
```

---

## 预测精度问题

### 🔴 预测结果偏差大

#### 症状表现
- MAPE > 15%
- 预测趋势与实际相反
- 异常值预测不准确

#### 排查步骤

1. **检查输入数据质量**
```python
# 数据质量检查脚本
def check_data_quality(df):
    """检查数据质量"""
    quality_report = {}

    # 缺失值检查
    missing_data = df.isnull().sum()
    quality_report['missing_percentage'] = (missing_data / len(df) * 100).round(2)

    # 异常值检查
    for column in df.select_dtypes(include=[np.number]).columns:
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        outliers = df[(df[column] < lower_bound) | (df[column] > upper_bound)]
        quality_report[f'{column}_outliers'] = len(outliers)

    # 数据一致性检查
    if 'wind_speed' in df.columns and 'power_output' in df.columns:
        # 检查风速-功率关系
        correlation = df['wind_speed'].corr(df['power_output'])
        quality_report['wind_power_correlation'] = correlation

    return quality_report
```

2. **分析模型性能**
```python
# 模型性能分析
def analyze_model_performance(model, X_test, y_test):
    """分析模型性能"""
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    import matplotlib.pyplot as plt

    # 预测
    y_pred = model.predict(X_test)

    # 计算指标
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    # 残差分析
    residuals = y_test - y_pred

    # 可视化
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # 实际值vs预测值
    axes[0, 0].scatter(y_test, y_pred, alpha=0.5)
    axes[0, 0].plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
    axes[0, 0].set_xlabel('实际值')
    axes[0, 0].set_ylabel('预测值')
    axes[0, 0].set_title('实际值 vs 预测值')

    # 残差图
    axes[0, 1].scatter(y_pred, residuals, alpha=0.5)
    axes[0, 1].axhline(y=0, color='r', linestyle='--')
    axes[0, 1].set_xlabel('预测值')
    axes[0, 1].set_ylabel('残差')
    axes[0, 1].set_title('残差图')

    # 残差分布
    axes[1, 0].hist(residuals, bins=30, alpha=0.7)
    axes[1, 0].set_xlabel('残差')
    axes[1, 0].set_ylabel('频次')
    axes[1, 0].set_title('残差分布')

    # 时间序列残差
    if hasattr(X_test, 'index'):
        axes[1, 1].plot(X_test.index, residuals, alpha=0.5)
        axes[1, 1].axhline(y=0, color='r', linestyle='--')
        axes[1, 1].set_xlabel('时间')
        axes[1, 1].set_ylabel('残差')
        axes[1, 1].set_title('残差时间序列')

    plt.tight_layout()
    plt.show()

    return {
        'mae': mae,
        'rmse': rmse,
        'r2': r2,
        'residuals_stats': {
            'mean': residuals.mean(),
            'std': residuals.std(),
            'min': residuals.min(),
            'max': residuals.max()
        }
    }
```

3. **特征重要性分析**
```python
# 特征重要性分析
def analyze_feature_importance(model, feature_names):
    """分析特征重要性"""
    import matplotlib.pyplot as plt
    import seaborn as sns

    # 获取特征重要性
    if hasattr(model, 'feature_importances_'):
        importance = model.feature_importances_
    elif hasattr(model, 'coef_'):
        importance = np.abs(model.coef_)
    else:
        print("模型不支持特征重要性分析")
        return

    # 创建重要性数据框
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': importance
    }).sort_values('importance', ascending=False)

    # 可视化
    plt.figure(figsize=(10, 6))
    sns.barplot(data=importance_df, x='importance', y='feature')
    plt.title('特征重要性')
    plt.xlabel('重要性')
    plt.ylabel('特征')
    plt.tight_layout()
    plt.show()

    return importance_df
```

#### 解决方案

**数据预处理优化**
```python
# 高级数据预处理
def advanced_data_preprocessing(df):
    """高级数据预处理"""

    # 1. 异常值处理
    def remove_outliers_iqr(df, columns, factor=1.5):
        """使用IQR方法移除异常值"""
        for col in columns:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - factor * IQR
            upper_bound = Q3 + factor * IQR

            # 标记异常值而不是删除
            df[f'{col}_outlier'] = (df[col] < lower_bound) | (df[col] > upper_bound)
            df[col] = df[col].clip(lower_bound, upper_bound)

        return df

    # 2. 特征工程
    def create_advanced_features(df):
        """创建高级特征"""
        # 时间特征
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['month'] = df['timestamp'].dt.month
        df['season'] = df['month'].map({12:1, 1:1, 2:1, 3:2, 4:2, 5:2, 6:3, 7:3, 8:3, 9:4, 10:4, 11:4})

        # 风速特征
        df['wind_speed_rolling_mean_3h'] = df['wind_speed'].rolling(window=3, center=True).mean()
        df['wind_speed_rolling_std_3h'] = df['wind_speed'].rolling(window=3, center=True).std()
        df['wind_speed_lag_1h'] = df['wind_speed'].shift(1)
        df['wind_speed_lag_2h'] = df['wind_speed'].shift(2)

        # 风向特征
        df['wind_direction_sin'] = np.sin(np.radians(df['wind_direction']))
        df['wind_direction_cos'] = np.cos(np.radians(df['wind_direction']))
        df['wind_direction_change'] = df['wind_direction'].diff()

        # 组合特征
        df['wind_power_density'] = 0.5 * 1.225 * df['wind_speed']**3  # 风功率密度
        df['temperature_wind_interaction'] = df['temperature'] * df['wind_speed']

        return df

    # 3. 数据平滑
    def smooth_data(df, columns, window=3):
        """数据平滑处理"""
        for col in columns:
            df[f'{col}_smoothed'] = df[col].rolling(window=window, center=True).mean()
        return df

    # 应用预处理
    numeric_columns = df.select_dtypes(include=[np.number]).columns
    df = remove_outliers_iqr(df, numeric_columns)
    df = create_advanced_features(df)
    df = smooth_data(df, ['wind_speed', 'power_output'])

    # 4. 处理缺失值
    df = df.fillna(method='forward').fillna(method='backward')

    return df
```

**模型集成**
```python
# 模型集成
from sklearn.ensemble import VotingRegressor, BaggingRegressor
from sklearn.model_selection import cross_val_score

def create_ensemble_model(models_dict):
    """创建集成模型"""

    # 1. 投票集成
    voting_regressor = VotingRegressor(
        estimators=[
            ('xgb', models_dict['xgboost']),
            ('lgb', models_dict['lightgbm']),
            ('rf', models_dict['random_forest'])
        ]
    )

    # 2. Bagging集成
    bagging_regressor = BaggingRegressor(
        base_estimator=models_dict['xgboost'],
        n_estimators=10,
        random_state=42
    )

    # 3. 堆叠集成（高级）
    stacking_regressor = create_stacking_ensemble(models_dict)

    return {
        'voting': voting_regressor,
        'bagging': bagging_regressor,
        'stacking': stacking_regressor
    }

def create_stacking_ensemble(models_dict):
    """创建堆叠集成模型"""
    from sklearn.linear_model import LinearRegression

    # 第一层：基础模型
    base_models = [
        ('xgb', models_dict['xgboost']),
        ('lgb', models_dict['lightgbm']),
        ('rf', models_dict['random_forest']),
        ('svr', models_dict['svr'])
    ]

    # 第二层：元模型
    meta_model = LinearRegression()

    # 创建堆叠模型
    stacking_model = StackingRegressor(
        estimators=base_models,
        final_estimator=meta_model,
        cv=5
    )

    return stacking_model
```

**超参数优化**
```python
# 超参数优化
from sklearn.model_selection import RandomizedSearchCV, BayesSearchCV
from scipy.stats import randint, uniform

def optimize_hyperparameters(model, param_distributions, X, y):
    """超参数优化"""

    # 1. 随机搜索
    random_search = RandomizedSearchCV(
        estimator=model,
        param_distributions=param_distributions,
        n_iter=100,
        cv=5,
        scoring='neg_mean_absolute_error',
        n_jobs=-1,
        random_state=42
    )

    # 2. 贝叶斯优化（更高级）
    bayes_search = BayesSearchCV(
        estimator=model,
        search_spaces=param_distributions,
        n_iter=50,
        cv=5,
        scoring='neg_mean_absolute_error',
        n_jobs=-1,
        random_state=42
    )

    # 执行搜索
    print("开始超参数优化...")
    random_search.fit(X, y)

    print(f"最优参数: {random_search.best_params_}")
    print(f"最优分数: {random_search.best_score_}")

    return random_search.best_estimator_

# XGBoost参数空间
xgb_param_space = {
    'n_estimators': randint(100, 2000),
    'max_depth': randint(3, 12),
    'learning_rate': uniform(0.01, 0.3),
    'subsample': uniform(0.6, 0.4),
    'colsample_bytree': uniform(0.6, 0.4),
    'min_child_weight': randint(1, 10),
    'gamma': uniform(0, 0.5),
    'reg_alpha': uniform(0, 1),
    'reg_lambda': uniform(0, 2)
}
```

---

## 性能问题

### 🔴 CPU使用率高

#### 症状表现
- CPU使用率持续 > 80%
- 响应时间变慢
- 系统负载高

#### 排查步骤

1. **识别高CPU进程**
```bash
# 查看容器CPU使用
docker stats --no-stream

# 容器内进程分析
docker-compose exec api top -b -n1

# 查看具体线程
docker-compose exec api ps -ef | grep python
```

2. **分析Python性能**
```python
# CPU性能分析
import cProfile
import pstats

# 性能分析
def profile_function(func, *args, **kwargs):
    profiler = cProfile.Profile()
    profiler.enable()

    result = func(*args, **kwargs)

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # 显示前20个最耗时的函数

    return result

# 或者使用line_profiler
@profile
def predict_power(model, data):
    return model.predict(data)
```

3. **数据库查询优化**
```sql
-- 查看正在执行的查询
SELECT pid, usename, application_name, state, query_start, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY query_start;

-- 查看查询计划
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM power_predictions
WHERE model_id = 1
AND prediction_time > '2024-01-01';
```

#### 解决方案

**算法优化**
```python
# 使用更高效的算法
import numpy as np
from numba import jit

@jit(nopython=True)  # Numba加速
def calculate_power_curve(wind_speeds, coefficients):
    """优化的功率曲线计算"""
    results = np.zeros_like(wind_speeds)

    for i in range(len(wind_speeds)):
        ws = wind_speeds[i]

        # 分段功率曲线计算
        if ws < 3:
            results[i] = 0
        elif ws < 12:
            results[i] = coefficients[0] * ws**3 + coefficients[1] * ws**2 + coefficients[2] * ws
        elif ws < 25:
            results[i] = coefficients[3]  # 额定功率
        else:
            results[i] = 0  # 切出风速

    return results

# 使用向量化操作
def vectorized_prediction(model, X):
    """向量化预测"""
    # 避免循环，使用NumPy向量化操作
    if isinstance(X, pd.DataFrame):
        X = X.values

    # 批量预测
    predictions = model.predict(X)

    # 向量化后处理
    predictions = np.where(predictions < 0, 0, predictions)
    predictions = np.where(predictions > 5000, 5000, predictions)

    return predictions
```

**并发处理**
```python
# 使用多进程处理CPU密集型任务
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed

def parallel_model_training(models_config, X, y):
    """并行模型训练"""

    def train_single_model(config):
        model_type = config['type']
        params = config['params']

        # 根据类型创建模型
        if model_type == 'xgboost':
            model = XGBRegressor(**params)
        elif model_type == 'lightgbm':
            model = LGBMRegressor(**params)
        elif model_type == 'random_forest':
            model = RandomForestRegressor(**params)

        # 训练模型
        model.fit(X, y)

        return {
            'type': model_type,
            'model': model,
            'config': config
        }

    # 使用进程池并行训练
    with ProcessPoolExecutor(max_workers=mp.cpu_count()) as executor:
        futures = [executor.submit(train_single_model, config) for config in models_config]

        trained_models = []
        for future in as_completed(futures):
            try:
                result = future.result()
                trained_models.append(result)
                print(f"模型 {result['type']} 训练完成")
            except Exception as e:
                print(f"模型训练失败: {e}")

    return trained_models
```

**缓存策略**
```python
# 多级缓存策略
import hashlib
import pickle
import redis

class MultiLevelCache:
    def __init__(self):
        self.redis_client = redis.Redis(host='redis', port=6379, db=0)
        self.local_cache = {}  # 本地内存缓存
        self.local_cache_size = 1000  # 限制本地缓存大小

    def _generate_key(self, func_name, args, kwargs):
        """生成缓存键"""
        key_data = f"{func_name}:{str(args)}:{str(kwargs)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key):
        """获取缓存值"""
        # 先检查本地缓存
        if key in self.local_cache:
            return self.local_cache[key]

        # 再检查Redis缓存
        try:
            value = self.redis_client.get(key)
            if value:
                result = pickle.loads(value)
                # 同时存入本地缓存
                self._add_to_local_cache(key, result)
                return result
        except:
            pass

        return None

    def set(self, key, value, expiration=3600):
        """设置缓存值"""
        # 存入本地缓存
        self._add_to_local_cache(key, value)

        # 存入Redis缓存
        try:
            serialized_value = pickle.dumps(value)
            self.redis_client.setex(key, expiration, serialized_value)
        except:
            pass

    def _add_to_local_cache(self, key, value):
        """添加到本地缓存（LRU策略）"""
        if len(self.local_cache) >= self.local_cache_size:
            # 移除最旧的条目
            oldest_key = next(iter(self.local_cache))
            del self.local_cache[oldest_key]

        self.local_cache[key] = value

# 使用示例
cache = MultiLevelCache()

def cached_prediction(model, data):
    cache_key = cache._generate_key("prediction", (model.id,), (str(data.hash()),))

    # 尝试从缓存获取
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # 执行预测
    result = model.predict(data)

    # 缓存结果
    cache.set(cache_key, result, expiration=600)

    return result
```

### 🔴 内存使用过高

#### 症状表现
- 内存使用率持续 > 85%
- 系统开始使用交换分区
- OOM Killer杀死进程

#### 排查步骤

1. **内存使用分析**
```bash
# 查看内存使用详情
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

# 查看容器内存限制
docker inspect api | grep -A 10 Memory

# 查看系统内存信息
cat /proc/meminfo
```

2. **Python内存分析**
```python
# 内存使用监控
import psutil
import os

def log_memory_usage():
    """记录内存使用情况"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()

    print(f"内存使用: {memory_info.rss / 1024 / 1024:.1f} MB")
    print(f"虚拟内存: {memory_info.vms / 1024 / 1024:.1f} MB")

    return memory_info.rss

# 内存泄漏检测
def detect_memory_leak():
    """简单的内存泄漏检测"""
    initial_memory = log_memory_usage()

    # 执行可能泄漏的操作
    for i in range(1000):
        # 你的代码
        pass

    final_memory = log_memory_usage()

    if final_memory > initial_memory * 1.5:  # 内存增长超过50%
        print("警告: 可能存在内存泄漏")
        return True

    return False
```

3. **对象引用分析**
```python
# 使用objgraph分析对象引用
import objgraph

def analyze_memory_objects():
    """分析内存中的对象"""

    # 显示最常见的对象类型
    print("最常见的对象类型:")
    objgraph.show_growth(limit=10)

    # 查找特定对象的引用链
    objgraph.show_backrefs([objgraph.by_type('list')[0]], filename='backrefs.png')

    # 查找循环引用
    objgraph.show_cycles(filename='cycles.png')

# 内存泄漏定位
def find_memory_leaks():
    """定位内存泄漏"""

    # 获取初始对象计数
    initial_objects = {}
    for obj_type in ['list', 'dict', 'function', 'MyClass']:
        initial_objects[obj_type] = len(objgraph.by_type(obj_type))

    # 执行可疑代码
    # ... 你的代码 ...

    # 检查对象增长
    for obj_type, initial_count in initial_objects.items():
        current_count = len(objgraph.by_type(obj_type))
        if current_count > initial_count * 1.2:  # 增长超过20%
            print(f"{obj_type}对象数量异常增长: {initial_count} -> {current_count}")
```

#### 解决方案

**优化数据结构**
```python
# 使用更高效的数据结构
import numpy as np
import pandas as pd

class OptimizedDataStorage:
    """优化的数据存储"""

    def __init__(self, capacity):
        self.capacity = capacity
        self.timestamps = np.zeros(capacity, dtype='datetime64[ns]')
        self.wind_speeds = np.zeros(capacity, dtype='float32')
        self.power_outputs = np.zeros(capacity, dtype='float32')
        self.size = 0

    def add_data(self, timestamp, wind_speed, power_output):
        if self.size < self.capacity:
            self.timestamps[self.size] = timestamp
            self.wind_speeds[self.size] = wind_speed
            self.power_outputs[self.size] = power_output
            self.size += 1

    def to_dataframe(self):
        return pd.DataFrame({
            'timestamp': self.timestamps[:self.size],
            'wind_speed': self.wind_speeds[:self.size],
            'power_output': self.power_outputs[:self.size]
        })

# 使用内存映射文件处理大数据
import mmap

def process_large_file_mmap(filename):
    """使用内存映射处理大文件"""
    with open(filename, 'r+b') as f:
        # 创建内存映射
        mm = mmap.mmap(f.fileno(), 0)

        # 逐行处理，避免全部加载到内存
        for line in iter(mm.readline, b''):
            process_line(line.decode('utf-8'))

        mm.close()
```

**流式处理**
```python
# 流式数据处理
def stream_process_data(source, processor, batch_size=1000):
    """流式处理数据"""
    batch = []

    for item in source:
        batch.append(item)

        if len(batch) >= batch_size:
            # 处理批次
            processed_batch = processor(batch)
            yield processed_batch

            # 清空批次
            batch = []

    # 处理剩余数据
    if batch:
        processed_batch = processor(batch)
        yield processed_batch

# 使用示例
def data_generator():
    """数据生成器"""
    for i in range(1000000):  # 100万条数据
        yield {
            'timestamp': datetime.now() + timedelta(hours=i),
            'wind_speed': np.random.normal(10, 3),
            'power_output': np.random.normal(2000, 500)
        }

def process_batch(batch):
    """批次处理函数"""
    df = pd.DataFrame(batch)
    # 数据处理逻辑
    return df.groupby(df['timestamp'].dt.hour).agg({
        'wind_speed': 'mean',
        'power_output': 'mean'
    })

# 流式处理
for result in stream_process_data(data_generator(), process_batch):
    # 处理结果
    print(f"处理了 {len(result)} 条聚合数据")
```

**定期内存清理**
```python
# 定期内存清理
def periodic_memory_cleanup():
    """定期内存清理"""
    import gc
    import ctypes

    # 强制垃圾回收
    gc.collect()

    # 清理本地缓存
    if hasattr(cache, 'clear'):
        cache.clear()

    # 释放未使用的内存
    try:
        # 尝试释放内存给操作系统
        malloc_trim = ctypes.CDLL(None).malloc_trim
        malloc_trim(0)
    except:
        pass

# 设置定时清理
import threading

def schedule_memory_cleanup(interval=300):  # 5分钟
    """定时内存清理"""
    def cleanup_task():
        while True:
            time.sleep(interval)
            periodic_memory_cleanup()
            print(f"[{datetime.now()}] 内存清理完成")

    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()
```

---

## 日志分析指南

### 日志收集和查看

#### Docker日志管理
```bash
# 查看实时日志
docker-compose logs -f api

# 查看特定时间段的日志
docker-compose logs --since="2024-01-15T10:00:00" --until="2024-01-15T12:00:00" api

# 查看特定级别的日志
docker-compose logs api | grep -E "ERROR|WARN|CRITICAL"

# 日志导出
docker-compose logs --no-color api > api_logs_$(date +%Y%m%d).log
```

#### 结构化日志分析
```python
# 日志分析脚本
import json
import re
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

def analyze_api_logs(log_file):
    """分析API日志"""

    log_pattern = re.compile(
        r'(?P\u003ctimestamp\u003e\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) '
        r'(?P\u003clevel\u003e\w+) '
        r'(?P\u003cmessage\u003e.*)'
    )

    error_pattern = re.compile(
        r'ERROR.*(?P\u003cerror_type\u003e\w+Error): (?P\u003cerror_msg\u003e[^\n]+)'
    )

    logs = []
    errors = []

    with open(log_file, 'r') as f:
        for line in f:
            # 解析基本日志
            match = log_pattern.match(line)
            if match:
                log_data = match.groupdict()
                log_data['timestamp'] = datetime.strptime(log_data['timestamp'], '%Y-%m-%d %H:%M:%S')
                logs.append(log_data)

                # 解析错误信息
                error_match = error_pattern.search(line)
                if error_match:
                    error_data = error_match.groupdict()
                    error_data['timestamp'] = log_data['timestamp']
                    errors.append(error_data)

    # 创建DataFrame
    logs_df = pd.DataFrame(logs)
    errors_df = pd.DataFrame(errors)

    # 统计分析
    print("=== 日志级别统计 ===")
    print(logs_df['level'].value_counts())

    print("\n=== 错误类型统计 ===")
    if not errors_df.empty:
        print(errors_df['error_type'].value_counts())

    print("\n=== 时间分布 ===")
    logs_df.set_index('timestamp')['level'].resample('H').count().plot()
    plt.title('每小时日志数量')
    plt.show()

    return logs_df, errors_df

# 使用示例
logs_df, errors_df = analyze_api_logs('api_logs_20240115.log')
```

#### 性能日志分析
```python
# 性能日志分析
def analyze_performance_logs(log_file):
    """分析性能日志"""

    # 性能日志模式
    perf_pattern = re.compile(
        r'(?P\u003ctimestamp\u003e\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) '
        r'.*'
        r'(?P\u003cendpoint\u003e/\w+) '
        r'.*'
        r'(?P\u003cresponse_time\u003e\d+\.\d+)s '
        r'(?P\u003cstatus_code\u003e\d{3})'
    )

    perf_data = []

    with open(log_file, 'r') as f:
        for line in f:
            match = perf_pattern.search(line)
            if match:
                data = match.groupdict()
                data['timestamp'] = datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S')
                data['response_time'] = float(data['response_time'])
                data['status_code'] = int(data['status_code'])
                perf_data.append(data)

    df = pd.DataFrame(perf_data)

    # 性能分析
    print("=== 响应时间统计 ===")
    print(df['response_time'].describe())

    print("\n=== 最慢的端点 ===")
    slow_endpoints = df.groupby('endpoint')['response_time'].agg(['mean', 'max', 'count'])
    print(slow_endpoints.sort_values('mean', ascending=False).head(10))

    print("\n=== 错误率统计 ===")
    error_rate = df.groupby('endpoint').apply(
        lambda x: (x['status_code'] >= 400).sum() / len(x) * 100
    )
    print(error_rate.sort_values(ascending=False).head(10))

    # 可视化
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    # 响应时间分布
    axes[0, 0].hist(df['response_time'], bins=50, alpha=0.7)
    axes[0, 0].set_xlabel('响应时间 (s)')
    axes[0, 0].set_ylabel('频次')
    axes[0, 0].set_title('响应时间分布')

    # 响应时间趋势
    df.set_index('timestamp')['response_time'].resample('H').mean().plot(ax=axes[0, 1])
    axes[0, 1].set_ylabel('平均响应时间 (s)')
    axes[0, 1].set_title('响应时间趋势')

    # 端点性能对比
    endpoint_perf = df.groupby('endpoint')['response_time'].mean().sort_values(ascending=False)
    endpoint_perf.head(10).plot(kind='barh', ax=axes[1, 0])
    axes[1, 0].set_xlabel('平均响应时间 (s)')
    axes[1, 0].set_title('端点性能对比')

    # 状态码分布
    df['status_code'].value_counts().plot(kind='bar', ax=axes[1, 1])
    axes[1, 1].set_xlabel('状态码')
    axes[1, 1].set_ylabel('数量')
    axes[1, 1].set_title('HTTP状态码分布')

    plt.tight_layout()
    plt.show()

    return df
```

### 错误模式分析
```python
# 错误模式分析
def analyze_error_patterns(log_file):
    """分析错误模式"""

    error_patterns = {
        'DatabaseError': re.compile(r'DatabaseError.*(?P\u003cdetail\u003e[^\n]+)'),
        'ConnectionError': re.compile(r'ConnectionError.*(?P\u003cdetail\u003e[^\n]+)'),
        'TimeoutError': re.compile(r'TimeoutError.*(?P\u003cdetail\u003e[^\n]+)'),
        'ValidationError': re.compile(r'ValidationError.*(?P\u003cdetail\u003e[^\n]+)'),
        'PredictionError': re.compile(r'PredictionError.*(?P\u003cdetail\u003e[^\n]+)'),
    }

    errors = {error_type: [] for error_type in error_patterns.keys()}

    with open(log_file, 'r') as f:
        for line in f:
            for error_type, pattern in error_patterns.items():
                match = pattern.search(line)
                if match:
                    errors[error_type].append(match.group('detail'))

    # 分析错误模式
    print("=== 错误模式分析 ===")
    for error_type, error_list in errors.items():
        if error_list:
            print(f"\n{error_type} ({len(error_list)} 次):")
            # 统计最常见的错误详情
            from collections import Counter
            error_counter = Counter(error_list)
            for error_detail, count in error_counter.most_common(5):
                print(f"  - {error_detail} ({count} 次)")

    # 生成错误报告
    error_report = generate_error_report(errors)
    return error_report

def generate_error_report(errors):
    """生成错误报告"""

    report = {
        'timestamp': datetime.now().isoformat(),
        'total_errors': sum(len(error_list) for error_list in errors.values()),
        'error_breakdown': {},
        'recommendations': []
    }

    for error_type, error_list in errors.items():
        if error_list:
            report['error_breakdown'][error_type] = {
                'count': len(error_list),
                'percentage': len(error_list) / sum(len(errs) for errs in errors.values()) * 100,
                'unique_errors': len(set(error_list))
            }

    # 生成建议
    if 'DatabaseError' in report['error_breakdown']:
        report['recommendations'].append("检查数据库连接和性能")

    if 'TimeoutError' in report['error_breakdown']:
        report['recommendations'].append("优化API响应时间和增加超时设置")

    if 'ConnectionError' in report['error_breakdown']:
        report['recommendations'].append("检查网络连接和服务状态")

    return report
```

---

## 紧急处理流程

### 🚨 系统完全不可用

#### 立即响应（5分钟内）
1. **确认故障范围**
   ```bash
   # 快速检查所有服务状态
   docker-compose ps

   # 检查基础服务
   ping $(hostname)
   systemctl status docker
   ```

2. **通知相关人员**
   - 立即通知技术负责人
   - 在运维群组发布故障通知
   - 记录故障开始时间

3. **启动紧急预案**
   ```bash
   # 执行紧急重启脚本
   ./emergency_restart.sh

   # 如果脚本不可用，手动重启
   docker-compose down
docker-compose up -d
   ```

#### 故障定位（15分钟内）
1. **检查系统资源**
   ```bash
   # 检查磁盘空间
   df -h

   # 检查内存使用
   free -h

   # 检查系统负载
   uptime
   ```

2. **查看关键日志**
   ```bash
   # 查看系统日志
   journalctl -xe --since="15 minutes ago"

   # 查看Docker日志
   journalctl -u docker.service --since="15 minutes ago"

   # 查看应用日志
   docker-compose logs --since="15 minutes ago" | tail -100
   ```

3. **网络连通性检查**
   ```bash
   # 检查网络连接
   ping 8.8.8.8
   curl -I http://localhost:5000/health

   # 检查DNS解析
   nslookup google.com
   ```

#### 恢复服务（30分钟内）
1. **基础服务恢复**
   ```bash
   # 如果Docker服务异常
   systemctl restart docker

   # 如果网络异常
   systemctl restart networking

   # 如果磁盘满
   find /var/log -name "*.log" -mtime +7 -delete
   docker system prune -f
   ```

2. **应用服务恢复**
   ```bash
   # 分步启动服务
   docker-compose up -d postgres redis
   sleep 30
   docker-compose up -d api
   sleep 10
   docker-compose up -d frontend

   # 验证服务状态
   curl -f http://localhost:5000/health
   ```

3. **数据完整性检查**
   ```bash
   # 检查数据库连接
   docker-compose exec postgres pg_isready

   # 检查关键表
   docker-compose exec postgres psql -U postgres -d windpower -c "
     SELECT COUNT(*) FROM weather_data WHERE created_at > NOW() - INTERVAL '1 hour';
     SELECT COUNT(*) FROM power_predictions WHERE created_at > NOW() - INTERVAL '1 hour';
   "
   ```

#### 故障报告（1小时内）
1. **编写故障报告**
   - 故障发生时间和持续时间
   - 故障现象和影响范围
   - 故障根因分析
   - 解决过程和恢复时间
   - 预防措施建议

2. **经验总结**
   - 更新应急预案
   - 完善监控告警
   - 制定预防措施

### 🔔 关键业务功能异常

#### 预测功能异常
1. **检查预测服务状态**
   ```bash
   # 检查预测服务日志
   docker-compose logs predict-service | grep -i error

   # 测试预测API
   curl -X POST http://localhost:5000/predict \
     -H "Authorization: Bearer test_token" \
     -d '{"model_id":1,"start_time":"2024-01-16T00:00:00Z"}'
   ```

2. **检查模型状态**
   ```bash
   # 检查可用模型
   curl http://localhost:5000/model/list

   # 检查模型文件
   docker-compose exec api ls -la /app/models/
   ```

3. **备用方案启动**
   ```bash
   # 切换到备用模型
   curl -X PUT http://localhost:5000/model/set-default/2

   # 使用简化预测算法
   curl -X POST http://localhost:5000/predict/simple \
     -d '{"data":"basic_weather_data"}'
   ```

#### 数据库异常
1. **数据库恢复**
   ```bash
   # 如果有主从复制，切换到从库
   # 从备份恢复
   docker-compose exec postgres pg_restore -U postgres -d windpower < backup.sql

   # 检查数据一致性
   docker-compose exec postgres psql -U postgres -d windpower -c "
     SELECT table_name,
            (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public') as table_count
     FROM information_schema.tables
     WHERE table_schema='public';
   "
   ```

2. **降级服务**
   ```bash
   # 启用只读模式
   export READONLY_MODE=true
   docker-compose restart api

   # 缓存模式
   export CACHE_ONLY_MODE=true
   docker-compose restart api
   ```

### 📞 联系信息和上报流程

#### 内部联系
- **技术负责人**: 138-0000-1234 (24小时)
- **运维团队**: 400-123-4567 (工作日9:00-18:00)
- **紧急邮箱**: urgent@company.com

#### 外部支持
- **云服务提供商**: 400-910-0000
- **数据库厂商**: 400-600-6800
- **网络运营商**: 10000

#### 上报流程
1. **5分钟内**: 通知直接上级和技术负责人
2. **15分钟内**: 通知运维团队和管理层
3. **30分钟内**: 向客户发送故障通知（如影响业务）
4. **1小时内**: 提交初步故障报告
5. **4小时内**: 提交详细故障分析和恢复报告

#### 故障级别定义
- **P0-紧急**: 系统完全不可用，影响所有用户
- **P1-高级**: 核心功能异常，影响大部分用户
- **P2-中级**: 非核心功能异常，影响部分用户
- **P3-低级**: 一般性问题，不影响主要功能

---

**记住**: 在处理紧急故障时，保持冷静，按流程操作，及时沟通，记录详细。如有疑问，立即联系技术支持团队！

**紧急联系卡片** (建议打印随身携带):
```
风功率预测系统紧急联系
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
技术负责人: 138-0000-1234
运维团队:   400-123-4567
紧急邮箱:   urgent@company.com
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
基础检查命令:
docker-compose ps              # 服务状态
docker-compose logs --tail=50  # 查看日志
curl http://localhost:5000/health # 健康检查
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
紧急重启:
docker-compose down && docker-compose up -d
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

*本故障排除指南定期更新，请确保使用最新版本。如有疑问或建议，请联系技术支持团队。*