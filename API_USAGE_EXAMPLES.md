# API接口使用示例

## 认证相关API

### 用户登录
```bash
# Request
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'

# Response
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "username": "admin",
    "role": "administrator",
    "permissions": ["read", "write", "admin"]
  }
}
```

### 刷新Token
```bash
# Request
curl -X POST http://localhost:5000/auth/refresh \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Response
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

## 数据管理API

### 上传训练数据
```python
import requests
import json

# Python示例
url = "http://localhost:5000/upload_train_csv"
headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}

files = {
    'file': open('train_data.csv', 'rb')
}

data = {
    'description': '2024年训练数据',
    'tags': 'winter,complete'
}

response = requests.post(url, headers=headers, files=files, data=data)
result = response.json()

if result['success']:
    print(f"文件上传成功: {result['data']['filename']}")
    print(f"文件ID: {result['data']['file_id']}")
else:
    print(f"上传失败: {result['error']}")
```

### 批量上传多个文件
```javascript
// JavaScript/Node.js示例
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

async function uploadFiles() {
    const form = new FormData();

    // 添加多个文件
    form.append('files', fs.createReadStream('weather_data.csv'));
    form.append('files', fs.createReadStream('power_data.csv'));
    form.append('files', fs.createReadStream('turbine_data.csv'));

    // 添加其他参数
    form.append('data_type', 'training');
    form.append('description', '批量训练数据');

    try {
        const response = await axios.post('http://localhost:5000/upload_batch', form, {
            headers: {
                ...form.getHeaders(),
                'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
            }
        });

        console.log('批量上传成功:', response.data);
    } catch (error) {
        console.error('上传失败:', error.response.data);
    }
}
```

### 获取数据列表
```bash
# 获取所有训练数据
curl -X GET "http://localhost:5000/api/data/list?type=train&page=1&limit=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# 带过滤条件
curl -X GET "http://localhost:5000/api/data/list?type=predict&status=completed&start_date=2024-01-01&end_date=2024-01-31" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## 模型训练API

### 创建训练任务
```python
import requests
import time

def train_model():
    # 1. 创建训练任务
    url = "http://localhost:5000/modeltrain"
    headers = {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "Content-Type": "application/json"
    }

    training_config = {
        "name": "XGBoost模型_2024年1月",
        "data_id": "12345",
        "model_type": "xgboost",
        "features": ["wind_speed", "wind_direction", "temperature", "pressure"],
        "target": "power_output",
        "parameters": {
            "n_estimators": 1000,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8
        },
        "validation_split": 0.2,
        "test_split": 0.1
    }

    response = requests.post(url, headers=headers, json=training_config)
    result = response.json()

    if result['success']:
        task_id = result['data']['task_id']
        print(f"训练任务已创建: {task_id}")

        # 2. 监控训练进度
        monitor_training(task_id)
    else:
        print(f"任务创建失败: {result['error']}")

def monitor_training(task_id):
    """监控训练进度"""
    status_url = f"http://localhost:5000/modeltrain/status/{task_id}"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}

    while True:
        response = requests.get(status_url, headers=headers)
        status = response.json()['data']

        print(f"训练进度: {status['progress']}% - {status['status']}")

        if status['status'] == 'completed':
            print("训练完成!")
            print(f"模型ID: {status['model_id']}")
            print(f"训练精度: {status['metrics']}")
            break
        elif status['status'] == 'failed':
            print(f"训练失败: {status.get('error', '未知错误')}")
            break

        time.sleep(30)  # 每30秒检查一次

# 执行训练
train_model()
```

### 获取训练结果和模型
```bash
# 下载训练好的模型
curl -X GET "http://localhost:5000/modeltrain/download-model?model_id=1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -o model.pkl

# 下载标准化器
curl -X GET "http://localhost:5000/modeltrain/download-scaler?model_id=1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -o scaler.pkl
```

## 功率预测API

### 创建预测任务
```javascript
// JavaScript示例 - 创建预测任务
async function createPrediction() {
    const predictionData = {
        model_id: 1,
        name: "2024年1月16日功率预测",
        start_time: "2024-01-16T00:00:00Z",
        end_time: "2024-01-17T00:00:00Z",
        data_source: "weather_forecast",
        parameters: {
            prediction_interval: "1h",
            confidence_level: 0.95,
            include_confidence_interval: true
        }
    };

    try {
        const response = await fetch('http://localhost:5000/predict', {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(predictionData)
        });

        const result = await response.json();

        if (result.success) {
            console.log('预测任务创建成功:', result.data);
            return result.data.prediction_id;
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        console.error('预测任务创建失败:', error);
    }
}
```

### 批量预测
```python
import asyncio
import aiohttp
import pandas as pd

async def batch_predict(models, time_ranges):
    """批量创建预测任务"""
    tasks = []

    async with aiohttp.ClientSession() as session:
        for model_id, time_range in zip(models, time_ranges):
            task = create_single_prediction(session, model_id, time_range)
            tasks.append(task)

        # 并发执行所有预测任务
        results = await asyncio.gather(*tasks)
        return results

async def create_single_prediction(session, model_id, time_range):
    """创建单个预测任务"""
    url = "http://localhost:5000/predict"
    headers = {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "Content-Type": "application/json"
    }

    prediction_data = {
        "model_id": model_id,
        "name": f"批量预测_{model_id}_{time_range['start']}",
        "start_time": time_range['start'],
        "end_time": time_range['end'],
        "data_source": "weather_forecast"
    }

    async with session.post(url, headers=headers, json=prediction_data) as response:
        result = await response.json()
        return result

# 使用示例
models = [1, 2, 3]  # 多个模型ID
time_ranges = [
    {"start": "2024-01-16T00:00:00Z", "end": "2024-01-16T12:00:00Z"},
    {"start": "2024-01-16T12:00:00Z", "end": "2024-01-17T00:00:00Z"},
    {"start": "2024-01-17T00:00:00Z", "end": "2024-01-17T12:00:00Z"}
]

# 运行批量预测
results = asyncio.run(batch_predict(models, time_ranges))
print(f"批量预测完成，共创建 {len(results)} 个预测任务")
```

### 获取预测结果
```python
import requests
import pandas as pd
import matplotlib.pyplot as plt

def get_prediction_results(prediction_id):
    """获取预测结果并可视化"""
    url = f"http://localhost:5000/predict/result/{prediction_id}"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}

    response = requests.get(url, headers=headers)
    result = response.json()

    if result['success']:
        data = result['data']

        # 转换为DataFrame
        df = pd.DataFrame(data['results'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # 显示统计信息
        print("预测统计信息:")
        print(f"MAE: {data['statistics']['mae']:.2f} kW")
        print(f"RMSE: {data['statistics']['rmse']:.2f} kW")
        print(f"MAPE: {data['statistics']['mape']:.2f}%")
        print(f"R²: {data['statistics']['r2']:.3f}")

        # 可视化
        plt.figure(figsize=(12, 6))
        plt.plot(df['timestamp'], df['predicted_power'],
                label='预测功率', color='blue', linewidth=2)

        # 如果有实际值，也绘制出来
        if 'actual_power' in df.columns:
            plt.plot(df['timestamp'], df['actual_power'],
                    label='实际功率', color='red', linewidth=2, alpha=0.7)

        # 绘制置信区间
        if 'confidence_lower' in df.columns:
            plt.fill_between(df['timestamp'],
                           df['confidence_lower'],
                           df['confidence_upper'],
                           alpha=0.3, color='blue', label='置信区间')

        plt.xlabel('时间')
        plt.ylabel('功率 (kW)')
        plt.title('风功率预测结果')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()

        return df
    else:
        print(f"获取预测结果失败: {result['error']}")
        return None

# 使用示例
df_predictions = get_prediction_results("pred_12345")
```

## 运营数据API

### 上传运营数据
```python
import requests
import pandas as pd
from datetime import datetime

def upload_operational_data(file_path, table_name):
    """上传运营数据"""
    url = "http://localhost:5000/operational/upload"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}

    # 支持的运营数据表
    supported_tables = [
        'wind_speed_data',           # 单机风速数据
        'turbine_power_data',        # 单机功率数据
        'weather_data',              # 气象信息数据
        'installed_capacity_data',   # 装机容量数据
        'available_capacity_data',   # 可用容量数据
        'theoretical_power_data',    # 理论功率数据
        'available_power_data'       # 可用功率数据
    ]

    if table_name not in supported_tables:
        print(f"不支持的表名: {table_name}")
        return

    files = {'file': open(file_path, 'rb')}
    data = {
        'table_name': table_name,
        'description': f'{table_name}_{datetime.now().strftime("%Y%m%d")}'
    }

    response = requests.post(url, headers=headers, files=files, data=data)
    result = response.json()

    if result['success']:
        print(f"运营数据上传成功: {result['data']['records_uploaded']} 条记录")
    else:
        print(f"上传失败: {result['error']}")

# 批量上传不同类型的运营数据
operational_files = {
    'wind_speed_data': 'wind_speed_2024.csv',
    'turbine_power_data': 'turbine_power_2024.csv',
    'weather_data': 'weather_station_2024.csv'
}

for table_name, file_path in operational_files.items():
    upload_operational_data(file_path, table_name)
```

### 查询运营数据
```bash
# 获取风速数据
curl -X GET "http://localhost:5000/operational/data/wind_speed_data?start_date=2024-01-01&end_date=2024-01-31&limit=100" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# 获取特定风机的功率数据
curl -X GET "http://localhost:5000/operational/data/turbine_power_data?turbine_id=T001&date=2024-01-15" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## 系统管理API

### 获取系统状态
```python
import requests
import json
from datetime import datetime

def check_system_health():
    """检查系统健康状态"""
    url = "http://localhost:5000/system/status"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}

    response = requests.get(url, headers=headers)
    result = response.json()

    if result['success']:
        status = result['data']

        print("=== 系统健康状态 ===")
        print(f"整体状态: {status['status']}")
        print(f"运行时间: {status['system_info']['uptime']}")
        print()

        print("=== 服务状态 ===")
        for service, state in status['services'].items():
            status_icon = "✅" if state == "connected" else "❌"
            print(f"{status_icon} {service}: {state}")
        print()

        print("=== 系统资源 ===")
        sys_info = status['system_info']
        print(f"CPU使用率: {sys_info['cpu_usage']}%")
        print(f"内存使用率: {sys_info['memory_usage']}%")
        print(f"磁盘使用率: {sys_info['disk_usage']}%")

        # 资源告警
        if sys_info['cpu_usage'] > 80:
            print("⚠️ 警告: CPU使用率过高")
        if sys_info['memory_usage'] > 85:
            print("⚠️ 警告: 内存使用率过高")
        if sys_info['disk_usage'] > 90:
            print("⚠️ 警告: 磁盘使用率过高")

    else:
        print(f"系统状态检查失败: {result['error']}")

# 定时检查系统状态
def monitor_system(interval=300):
    """定期监控系统状态"""
    while True:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 系统检查")
        check_system_health()
        time.sleep(interval)

# 运行监控
check_system_health()
```

### 获取系统统计信息
```bash
# 获取今日预测统计
curl -X GET "http://localhost:5000/system/stats?type=predictions&date=$(date +%Y-%m-%d)" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# 获取本月模型训练统计
curl -X GET "http://localhost:5000/system/stats?type=training&month=$(date +%Y-%m)" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## 高级功能示例

### WebSocket实时数据
```javascript
// JavaScript WebSocket客户端
const socket = io('http://localhost:5000', {
    auth: {
        token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    }
});

// 监听训练进度
socket.on('training_progress', (data) => {
    console.log('训练进度:', data.progress + '%');
    console.log('状态:', data.status);

    if (data.status === 'completed') {
        console.log('训练完成！模型ID:', data.model_id);
    }
});

// 监听预测结果
socket.on('prediction_result', (data) => {
    console.log('新的预测结果:', data);

    // 更新实时图表
    updateRealtimeChart(data);
});

// 监听系统告警
socket.on('system_alert', (alert) => {
    console.log('系统告警:', alert.message);

    if (alert.severity === 'critical') {
        // 显示紧急告警通知
        showCriticalAlert(alert);
    }
});

// 加入房间（按任务ID）
socket.emit('join_room', 'task_12345');
socket.emit('join_room', 'pred_67890');
```

### 批量数据处理
```python
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import requests

def process_large_dataset(file_path, chunk_size=1000):
    """分块处理大型数据集"""

    # 读取CSV文件
    chunks = pd.read_csv(file_path, chunksize=chunk_size)

    # 并行处理每个数据块
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []

        for chunk_id, chunk in enumerate(chunks):
            # 数据预处理
            processed_chunk = preprocess_data(chunk)

            # 提交处理任务
            future = executor.submit(upload_chunk, processed_chunk, chunk_id)
            futures.append(future)

        # 等待所有任务完成
        results = [future.result() for future in futures]

    return results

def preprocess_data(df):
    """数据预处理"""
    # 处理缺失值
    df = df.fillna(method='forward')

    # 数据验证
    df = df[(df['wind_speed'] >= 0) & (df['wind_speed'] <= 50)]
    df = df[(df['power_output'] >= 0) & (df['power_output'] <= 5000)]

    # 添加派生特征
    df['wind_speed_squared'] = df['wind_speed'] ** 2
    df['wind_direction_sin'] = np.sin(np.radians(df['wind_direction']))
    df['wind_direction_cos'] = np.cos(np.radians(df['wind_direction']))

    return df

def upload_chunk(chunk, chunk_id):
    """上传数据块"""
    # 将DataFrame转换为CSV
    csv_data = chunk.to_csv(index=False)

    files = {
        'file': (f'chunk_{chunk_id}.csv', csv_data, 'text/csv')
    }

    data = {
        'chunk_id': chunk_id,
        'total_chunks': 'unknown',  # 将在最后更新
        'description': f'数据块_{chunk_id}'
    }

    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}

    response = requests.post(
        'http://localhost:5000/upload_chunk',
        headers=headers,
        files=files,
        data=data
    )

    return response.json()
```

### 自动化预测流程
```python
import schedule
import time
from datetime import datetime, timedelta
import requests

def automated_prediction():
    """自动化预测任务"""

    # 1. 获取最新气象数据
    weather_data = fetch_latest_weather_data()

    # 2. 数据预处理
    processed_data = preprocess_weather_data(weather_data)

    # 3. 选择最优模型
    best_model = select_best_model()

    # 4. 创建预测任务
    prediction_id = create_prediction_task(best_model, processed_data)

    # 5. 等待预测完成
    results = wait_for_prediction_completion(prediction_id)

    # 6. 生成报告
    report_id = generate_automated_report(results)

    # 7. 发送通知
    send_prediction_notification(results, report_id)

    print(f"[{datetime.now()}] 自动化预测完成: {prediction_id}")

def fetch_latest_weather_data():
    """获取最新气象数据"""
    # 从气象服务API获取数据
    response = requests.get('http://api.weather.com/forecast', params={
        'location': 'wind_farm_001',
        'hours': 72
    })
    return response.json()

def select_best_model():
    """选择最优模型"""
    # 获取所有可用模型
    response = requests.get(
        'http://localhost:5000/model/list?status=completed',
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    )

    models = response.json()['data']['items']

    # 选择精度最高的模型
    best_model = max(models, key=lambda x: x['accuracy'])
    return best_model['id']

def create_prediction_task(model_id, weather_data):
    """创建预测任务"""
    prediction_config = {
        "model_id": model_id,
        "name": f"自动预测_{datetime.now().strftime('%Y%m%d_%H%M')}",
        "start_time": datetime.utcnow().isoformat(),
        "end_time": (datetime.utcnow() + timedelta(hours=72)).isoformat(),
        "data_source": "weather_forecast",
        "auto_notify": True
    }

    response = requests.post(
        'http://localhost:5000/predict',
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."},
        json=prediction_config
    )

    return response.json()['data']['prediction_id']

# 设置定时任务
schedule.every().day.at("06:00").do(automated_prediction)  # 每天早上6点
schedule.every().day.at("18:00").do(automated_prediction)  # 每天晚上6点

# 运行调度器
while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## 错误处理示例

### API错误处理
```python
import requests
from requests.exceptions import RequestException
import time

def safe_api_call(method, url, **kwargs):
    """安全的API调用，包含重试机制"""

    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            response = requests.request(method, url, **kwargs)

            # 处理HTTP错误
            if response.status_code >= 400:
                error_data = response.json()

                if response.status_code == 401:
                    print("认证失败，需要重新登录")
                    # 重新获取token
                    new_token = refresh_token()
                    kwargs['headers']['Authorization'] = f'Bearer {new_token}'
                    continue

                elif response.status_code == 429:
                    print("请求过于频繁，等待重试")
                    time.sleep(retry_delay * (attempt + 1))
                    continue

                else:
                    print(f"API错误 ({response.status_code}): {error_data.get('error', '未知错误')}")
                    return None

            return response.json()

        except RequestException as e:
            print(f"网络请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                print("所有重试尝试都失败了")
                return None

    return None

def refresh_token():
    """刷新访问令牌"""
    login_data = {
        "username": "admin",
        "password": "admin123"
    }

    response = requests.post(
        'http://localhost:5000/auth/login',
        json=login_data
    )

    if response.status_code == 200:
        return response.json()['token']
    else:
        raise Exception("无法刷新token")
```

### 数据验证示例
```python
def validate_prediction_data(data):
    """验证预测输入数据"""

    required_fields = ['wind_speed', 'wind_direction', 'temperature']

    # 检查必需字段
    for field in required_fields:
        if field not in data:
            raise ValueError(f"缺少必需字段: {field}")

    # 验证数据范围
    if not (0 <= data['wind_speed'] <= 50):
        raise ValueError("风速必须在0-50 m/s之间")

    if not (0 <= data['wind_direction'] <= 360):
        raise ValueError("风向必须在0-360度之间")

    if not (-40 <= data['temperature'] <= 60):
        raise ValueError("温度必须在-40到60摄氏度之间")

    # 检查数据类型
    for field in required_fields:
        if not isinstance(data[field], (int, float)):
            raise ValueError(f"字段 {field} 必须是数值类型")

    return True

# 使用示例
try:
    prediction_data = {
        "wind_speed": 15.5,
        "wind_direction": 180,
        "temperature": 25.0
    }

    validate_prediction_data(prediction_data)
    print("数据验证通过")

except ValueError as e:
    print(f"数据验证失败: {e}")
```

---

## 性能优化示例

### 并发请求处理
```python
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor

async def concurrent_predictions(session, prediction_requests):
    """并发处理多个预测请求"""

    async def single_prediction(request_data):
        url = "http://localhost:5000/predict"
        headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "Content-Type": "application/json"
        }

        async with session.post(url, headers=headers, json=request_data) as response:
            return await response.json()

    # 创建并发任务
    tasks = [single_prediction(req) for req in prediction_requests]

    # 并发执行
    results = await asyncio.gather(*tasks)
    return results

async def optimized_batch_processing():
    """优化的批量处理"""

    # 预测请求列表
    prediction_requests = [
        {
            "model_id": 1,
            "name": f"预测任务_{i}",
            "start_time": f"2024-01-16T{i:02d}:00:00Z",
            "end_time": f"2024-01-16T{i+1:02d}:00:00Z",
            "data_source": "weather_forecast"
        }
        for i in range(24)  # 24小时的预测
    ]

    # 使用连接池
    connector = aiohttp.TCPConnector(
        limit=100,  # 总连接数限制
        limit_per_host=30,  # 每个主机的连接数限制
        ttl_dns_cache=300,  # DNS缓存时间
        use_dns_cache=True,
    )

    timeout = aiohttp.ClientTimeout(
        total=30,  # 总超时时间
        connect=10,  # 连接超时时间
        sock_read=10  # 读取超时时间
    )

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout
    ) as session:
        start_time = time.time()

        # 分批处理，避免一次性请求过多
        batch_size = 5
        all_results = []

        for i in range(0, len(prediction_requests), batch_size):
            batch = prediction_requests[i:i + batch_size]
            batch_results = await concurrent_predictions(session, batch)
            all_results.extend(batch_results)

            # 批次间稍作等待，避免系统过载
            if i + batch_size < len(prediction_requests):
                await asyncio.sleep(0.5)

        end_time = time.time()

        print(f"处理完成: {len(all_results)} 个预测请求")
        print(f"总耗时: {end_time - start_time:.2f} 秒")
        print(f"平均响应时间: {(end_time - start_time) / len(all_results):.2f} 秒/请求")

        return all_results

# 运行优化后的批量处理
if __name__ == "__main__":
    results = asyncio.run(optimized_batch_processing())
```

### 缓存策略实现
```python
import redis
import json
import hashlib
from functools import wraps
import time

class APICache:
    def __init__(self, redis_host='localhost', redis_port=6379, default_ttl=300):
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        self.default_ttl = default_ttl

    def generate_cache_key(self, func_name, *args, **kwargs):
        """生成缓存键"""
        key_data = {
            'function': func_name,
            'args': args,
            'kwargs': kwargs
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return f"api_cache:{hashlib.md5(key_string.encode()).hexdigest()}"

    def cache_result(self, ttl=None):
        """缓存装饰器"""
        if ttl is None:
            ttl = self.default_ttl

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = self.generate_cache_key(func.__name__, *args, **kwargs)

                # 尝试从缓存获取
                cached_result = self.redis_client.get(cache_key)
                if cached_result:
                    print(f"从缓存获取结果: {func.__name__}")
                    return json.loads(cached_result)

                # 执行函数并缓存结果
                result = func(*args, **kwargs)
                if result:
                    self.redis_client.setex(
                        cache_key,
                        ttl,
                        json.dumps(result)
                    )
                    print(f"缓存结果: {func.__name__}")

                return result

            return wrapper
        return decorator

# 使用缓存装饰器
api_cache = APICache()

@api_cache.cache_result(ttl=600)  # 缓存10分钟
def get_weather_forecast(station_id, start_date, end_date):
    """获取天气预报数据（带缓存）"""
    url = f"http://localhost:5000/weather/forecast"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    params = {
        "station_id": station_id,
        "start_date": start_date,
        "end_date": end_date
    }

    response = requests.get(url, headers=headers, params=params)
    return response.json()

@api_cache.cache_result(ttl=1800)  # 缓存30分钟
def get_model_list(status="completed"):
    """获取模型列表（带缓存）"""
    url = f"http://localhost:5000/model/list"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    params = {"status": status}

    response = requests.get(url, headers=headers, params=params)
    return response.json()
```

### 数据库查询优化
```python
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

class OptimizedDataQueries:
    def __init__(self, connection_string):
        self.engine = create_engine(
            connection_string,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=3600
        )

    def get_weather_data_optimized(self, station_ids, start_date, end_date):
        """优化的天气数据查询"""

        # 使用参数化查询防止SQL注入
        query = text("""
            SELECT
                station_id,
                measurement_time,
                wind_speed,
                wind_direction,
                temperature,
                pressure,
                humidity
            FROM weather_data
            WHERE station_id = ANY(:station_ids)
                AND measurement_time BETWEEN :start_date AND :end_date
                AND wind_speed IS NOT NULL
                AND wind_direction IS NOT NULL
                AND temperature IS NOT NULL
            ORDER BY station_id, measurement_time
        """)

        # 使用pandas直接读取数据
        df = pd.read_sql_query(
            query,
            self.engine,
            params={
                'station_ids': station_ids,
                'start_date': start_date,
                'end_date': end_date
            }
        )

        # 设置索引优化后续处理
        df['measurement_time'] = pd.to_datetime(df['measurement_time'])
        df.set_index('measurement_time', inplace=True)

        return df

    def get_aggregated_data(self, station_id, date, aggregation_level='hour'):
        """获取聚合数据"""

        aggregation_map = {
            'hour': 'DATE_TRUNC(\'hour\', measurement_time)',
            'day': 'DATE_TRUNC(\'day\', measurement_time)',
            'week': 'DATE_TRUNC(\'week\', measurement_time)',
            'month': 'DATE_TRUNC(\'month\', measurement_time)'
        }

        time_trunc = aggregation_map.get(aggregation_level, aggregation_map['hour'])

        query = text(f"""
            SELECT
                {time_trunc} as time_period,
                AVG(wind_speed) as avg_wind_speed,
                AVG(wind_direction) as avg_wind_direction,
                AVG(temperature) as avg_temperature,
                AVG(pressure) as avg_pressure,
                MIN(wind_speed) as min_wind_speed,
                MAX(wind_speed) as max_wind_speed,
                COUNT(*) as record_count
            FROM weather_data
            WHERE station_id = :station_id
                AND DATE(measurement_time) = :date
            GROUP BY {time_trunc}
            ORDER BY time_period
        """)

        df = pd.read_sql_query(
            query,
            self.engine,
            params={'station_id': station_id, 'date': date}
        )

        return df

    def get_data_with_pagination(self, table, start_id=0, batch_size=1000):
        """分页获取大数据集"""

        query = text(f"""
            SELECT *
            FROM {table}
            WHERE id > :start_id
            ORDER BY id ASC
            LIMIT :batch_size
        """)

        offset = start_id

        while True:
            # 获取一批数据
            batch_df = pd.read_sql_query(
                query,
                self.engine,
                params={'start_id': offset, 'batch_size': batch_size}
            )

            if batch_df.empty:
                break

            yield batch_df

            # 更新偏移量
            offset = batch_df['id'].max()

            # 可选：添加延迟避免数据库过载
            # time.sleep(0.1)

# 使用示例
query_engine = OptimizedDataQueries("postgresql://user:password@localhost:5432/wind_power")

# 优化的天气数据查询
weather_data = query_engine.get_weather_data_optimized(
    station_ids=['ST001', 'ST002', 'ST003'],
    start_date='2024-01-01',
    end_date='2024-01-31'
)

# 聚合数据查询
hourly_data = query_engine.get_aggregated_data(
    station_id='ST001',
    date='2024-01-15',
    aggregation_level='hour'
)

# 分页处理大数据集
for batch_df in query_engine.get_data_with_pagination('weather_data', batch_size=5000):
    # 处理每个批次的数据
    process_batch(batch_df)
    print(f"处理了 {len(batch_df)} 条记录")
```

---

## 多语言示例

### Java示例
```java
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.URI;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.concurrent.CompletableFuture;
import java.time.Duration;

public class WindPowerAPI {
    private final HttpClient client;
    private final ObjectMapper objectMapper;
    private final String baseUrl;
    private final String token;

    public WindPowerAPI(String baseUrl, String token) {
        this.baseUrl = baseUrl;
        this.token = token;
        this.objectMapper = new ObjectMapper();
        this.client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();
    }

    public CompletableFuture<PredictionResult> createPrediction(PredictionRequest request) {
        try {
            String jsonBody = objectMapper.writeValueAsString(request);

            HttpRequest httpRequest = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/predict"))
                    .header("Content-Type", "application/json")
                    .header("Authorization", "Bearer " + token)
                    .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
                    .timeout(Duration.ofSeconds(30))
                    .build();

            return client.sendAsync(httpRequest, HttpResponse.BodyHandlers.ofString())
                    .thenApply(response -> {
                        if (response.statusCode() == 200) {
                            try {
                                return objectMapper.readValue(response.body(), PredictionResult.class);
                            } catch (Exception e) {
                                throw new RuntimeException("Failed to parse response", e);
                            }
                        } else {
                            throw new RuntimeException("API call failed with status: " + response.statusCode());
                        }
                    });
        } catch (Exception e) {
            CompletableFuture<PredictionResult> future = new CompletableFuture<>();
            future.completeExceptionally(e);
            return future;
        }
    }

    // 数据模型类
    public static class PredictionRequest {
        public int modelId;
        public String name;
        public String startTime;
        public String endTime;
        public String dataSource;
        public Map<String, Object> parameters;

        // 构造函数和getter/setter省略
    }

    public static class PredictionResult {
        public boolean success;
        public PredictionData data;

        public static class PredictionData {
            public String predictionId;
            public String status;
            public String message;
        }
    }
}
```

### Go示例
```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

type WindPowerClient struct {
    baseURL    string
    token      string
    httpClient *http.Client
}

func NewWindPowerClient(baseURL, token string) *WindPowerClient {
    return &WindPowerClient{
        baseURL: baseURL,
        token:   token,
        httpClient: &http.Client{
            Timeout: 30 * time.Second,
        },
    }
}

type PredictionRequest struct {
    ModelID    int                    `json:"model_id"`
    Name       string                 `json:"name"`
    StartTime  string                 `json:"start_time"`
    EndTime    string                 `json:"end_time"`
    DataSource string                 `json:"data_source"`
    Parameters map[string]interface{} `json:"parameters"`
}

type PredictionResponse struct {
    Success bool   `json:"success"`
    Error   string `json:"error,omitempty"`
    Data    struct {
        PredictionID string `json:"prediction_id"`
        Status       string `json:"status"`
        Message      string `json:"message"`
    } `json:"data"`
}

func (c *WindPowerClient) CreatePrediction(req PredictionRequest) (*PredictionResponse, error) {
    jsonData, err := json.Marshal(req)
    if err != nil {
        return nil, fmt.Errorf("failed to marshal request: %v", err)
    }

    request, err := http.NewRequest(
        "POST",
        c.baseURL+"/predict",
        bytes.NewBuffer(jsonData),
    )
    if err != nil {
        return nil, fmt.Errorf("failed to create request: %v", err)
    }

    request.Header.Set("Content-Type", "application/json")
    request.Header.Set("Authorization", "Bearer "+c.token)

    response, err := c.httpClient.Do(request)
    if err != nil {
        return nil, fmt.Errorf("failed to execute request: %v", err)
    }
    defer response.Body.Close()

    var result PredictionResponse
    if err := json.NewDecoder(response.Body).Decode(&result); err != nil {
        return nil, fmt.Errorf("failed to decode response: %v", err)
    }

    if !result.Success {
        return nil, fmt.Errorf("API error: %s", result.Error)
    }

    return &result, nil
}

func main() {
    client := NewWindPowerClient("http://localhost:5000", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")

    request := PredictionRequest{
        ModelID:    1,
        Name:       "Go客户端预测任务",
        StartTime:  "2024-01-16T00:00:00Z",
        EndTime:    "2024-01-17T00:00:00Z",
        DataSource: "weather_forecast",
        Parameters: map[string]interface{}{
            "prediction_interval": "1h",
            "confidence_level":    0.95,
        },
    }

    result, err := client.CreatePrediction(request)
    if err != nil {
        fmt.Printf("Error creating prediction: %v\n", err)
        return
    }

    fmt.Printf("Prediction created successfully: %s\n", result.Data.PredictionID)
}
```

### C#示例
```csharp
using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Collections.Generic;

public class WindPowerApiClient
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;
    private readonly string _token;
    private readonly JsonSerializerOptions _jsonOptions;

    public WindPowerApiClient(string baseUrl, string token)
    {
        _baseUrl = baseUrl.TrimEnd('/');
        _token = token;
        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            WriteIndented = true
        };

        _httpClient = new HttpClient
        {
            Timeout = TimeSpan.FromSeconds(30)
        };

        _httpClient.DefaultRequestHeaders.Add("Authorization", $"Bearer {token}");
    }

    public class PredictionRequest
    {
        public int ModelId { get; set; }
        public string Name { get; set; }
        public string StartTime { get; set; }
        public string EndTime { get; set; }
        public string DataSource { get; set; }
        public Dictionary<string, object> Parameters { get; set; }
    }

    public class PredictionResponse
    {
        public bool Success { get; set; }
        public string Error { get; set; }
        public PredictionData Data { get; set; }
    }

    public class PredictionData
    {
        public string PredictionId { get; set; }
        public string Status { get; set; }
        public string Message { get; set; }
    }

    public async Task<PredictionResponse> CreatePredictionAsync(PredictionRequest request)
    {
        try
        {
            var json = JsonSerializer.Serialize(request, _jsonOptions);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync($"{_baseUrl}/predict", content);

            if (response.IsSuccessStatusCode)
            {
                var responseContent = await response.Content.ReadAsStringAsync();
                return JsonSerializer.Deserialize<PredictionResponse>(responseContent, _jsonOptions);
            }
            else
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                throw new Exception($"API call failed with status {response.StatusCode}: {errorContent}");
            }
        }
        catch (TaskCanceledException)
        {
            throw new Exception("Request timed out");
        }
        catch (Exception ex)
        {
            throw new Exception($"Failed to create prediction: {ex.Message}");
        }
    }

    public async Task<bool> TestConnectionAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync($"{_baseUrl}/health");
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }
}

class Program
{
    static async Task Main(string[] args)
    {
        var client = new WindPowerApiClient(
            "http://localhost:5000",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        );

        // 测试连接
        var isConnected = await client.TestConnectionAsync();
        Console.WriteLine($"Connection test: {(isConnected ? "Success" : "Failed")}");

        if (isConnected)
        {
            var request = new PredictionRequest
            {
                ModelId = 1,
                Name = "C#客户端预测任务",
                StartTime = "2024-01-16T00:00:00Z",
                EndTime = "2024-01-17T00:00:00Z",
                DataSource = "weather_forecast",
                Parameters = new Dictionary<string, object>
                {
                    ["prediction_interval"] = "1h",
                    ["confidence_level"] = 0.95
                }
            };

            try
            {
                var result = await client.CreatePredictionAsync(request);

                if (result.Success)
                {
                    Console.WriteLine($"Prediction created successfully: {result.Data.PredictionId}");
                }
                else
                {
                    Console.WriteLine($"Error creating prediction: {result.Error}");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Exception: {ex.Message}");
            }
        }
    }
}
```

---

## 调试和监控示例

### 请求日志记录
```python
import logging
import time
import json
from datetime import datetime

class APIRequestLogger:
    def __init__(self, log_file='api_requests.log'):
        self.logger = logging.getLogger('api_requests')
        self.logger.setLevel(logging.INFO)

        # 文件处理器
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log_request(self, method, url, headers=None, data=None, response=None, duration=None):
        """记录API请求和响应"""

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'method': method,
            'url': url,
            'duration_ms': duration,
            'request': {
                'headers': self._sanitize_headers(headers or {}),
                'data': data
            },
            'response': {
                'status_code': response.status_code if response else None,
                'headers': dict(response.headers) if response else None,
                'data': self._truncate_response(response) if response else None
            }
        }

        self.logger.info(json.dumps(log_entry, indent=2))

    def _sanitize_headers(self, headers):
        """清理敏感信息"""
        sanitized = headers.copy()
        sensitive_keys = ['authorization', 'x-api-key', 'cookie']

        for key in sensitive_keys:
            if key.lower() in sanitized:
                sanitized[key] = '***REDACTED***'

        return sanitized

    def _truncate_response(self, response, max_length=1000):
        """截断响应数据"""
        try:
            content = response.text
            if len(content) > max_length:
                return content[:max_length] + '... [TRUNCATED]'
            return content
        except:
            return '[Unable to read response content]'

# 使用示例
request_logger = APIRequestLogger()

def logged_api_request(method, url, **kwargs):
    """带日志记录的API请求"""
    start_time = time.time()

    try:
        response = requests.request(method, url, **kwargs)
        duration = (time.time() - start_time) * 1000  # 转换为毫秒

        request_logger.log_request(
            method=method,
            url=url,
            headers=kwargs.get('headers'),
            data=kwargs.get('json') or kwargs.get('data'),
            response=response,
            duration=duration
        )

        return response

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        request_logger.logger.error(f"API request failed: {e}")
        raise
```

### 性能监控
```python
import psutil
import threading
import time
from collections import deque

class PerformanceMonitor:
    def __init__(self, max_history=100):
        self.max_history = max_history
        self.cpu_history = deque(maxlen=max_history)
        self.memory_history = deque(maxlen=max_history)
        self.network_history = deque(maxlen=max_history)
        self.monitoring = False
        self.monitor_thread = None

    def start_monitoring(self, interval=1):
        """开始性能监控"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        print("性能监控已启动")

    def stop_monitoring(self):
        """停止性能监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        print("性能监控已停止")

    def _monitor_loop(self, interval):
        """监控循环"""
        while self.monitoring:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=None)
            self.cpu_history.append(cpu_percent)

            # 内存使用率
            memory = psutil.virtual_memory()
            self.memory_history.append(memory.percent)

            # 网络IO
            network = psutil.net_io_counters()
            self.network_history.append({
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'timestamp': time.time()
            })

            time.sleep(interval)

    def get_stats(self):
        """获取性能统计"""
        if not self.cpu_history:
            return None

        return {
            'cpu': {
                'current': self.cpu_history[-1],
                'average': sum(self.cpu_history) / len(self.cpu_history),
                'max': max(self.cpu_history),
                'min': min(self.cpu_history)
            },
            'memory': {
                'current': self.memory_history[-1],
                'average': sum(self.memory_history) / len(self.memory_history),
                'max': max(self.memory_history),
                'min': min(self.memory_history)
            },
            'sample_count': len(self.cpu_history)
        }

    def check_resource_usage(self, cpu_threshold=80, memory_threshold=85):
        """检查资源使用情况"""
        stats = self.get_stats()
        if not stats:
            return {'alerts': [], 'status': 'unknown'}

        alerts = []

        # CPU告警
        if stats['cpu']['current'] > cpu_threshold:
            alerts.append({
                'type': 'cpu_high',
                'message': f"CPU使用率过高: {stats['cpu']['current']:.1f}%",
                'severity': 'warning' if stats['cpu']['current'] < 90 else 'critical'
            })

        # 内存告警
        if stats['memory']['current'] > memory_threshold:
            alerts.append({
                'type': 'memory_high',
                'message': f"内存使用率过高: {stats['memory']['current']:.1f}%",
                'severity': 'warning' if stats['memory']['current'] < 95 else 'critical'
            })

        status = 'healthy' if not alerts else 'warning'
        if any(alert['severity'] == 'critical' for alert in alerts):
            status = 'critical'

        return {
            'alerts': alerts,
            'status': status,
            'stats': stats
        }

# 使用示例
perf_monitor = PerformanceMonitor()

# 开始监控
perf_monitor.start_monitoring(interval=2)

# 模拟一些工作
time.sleep(10)

# 检查资源使用情况
resource_check = perf_monitor.check_resource_usage()
print(f"资源状态: {resource_check['status']}")
for alert in resource_check['alerts']:
    print(f"告警: {alert['message']}")

# 获取详细统计信息
stats = perf_monitor.get_stats()
if stats:
    print(f"CPU平均使用率: {stats['cpu']['average']:.1f}%")
    print(f"内存平均使用率: {stats['memory']['average']:.1f}%")

# 停止监控
perf_monitor.stop_monitoring()
```

---

这些API使用示例涵盖了风功率预测系统的主要功能，包括认证、数据管理、模型训练、功率预测、运营数据管理和系统管理等各个方面。同时还提供了性能优化、错误处理、多语言支持和调试监控的高级示例。您可以根据实际需求选择合适的示例进行修改和使用。记得替换示例中的token和URL为您的实际值。如果您需要更多特定功能的示例，请随时询问。"}