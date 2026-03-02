# API鎺ュ彛浣跨敤绀轰緥

## 璁よ瘉鐩稿叧API

### 鐢ㄦ埛鐧诲綍
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

### 鍒锋柊Token
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

## 鏁版嵁绠＄悊API

### 涓婁紶璁粌鏁版嵁
```python
import requests
import json

# Python绀轰緥
url = "http://localhost:5000/upload_train_csv"
headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}

files = {
    'file': open('train_data.csv', 'rb')
}

data = {
    'description': '2024骞磋缁冩暟鎹?,
    'tags': 'winter,complete'
}

response = requests.post(url, headers=headers, files=files, data=data)
result = response.json()

if result['success']:
    print(f"鏂囦欢涓婁紶鎴愬姛: {result['data']['filename']}")
    print(f"鏂囦欢ID: {result['data']['file_id']}")
else:
    print(f"涓婁紶澶辫触: {result['error']}")
```

### 鎵归噺涓婁紶澶氫釜鏂囦欢
```javascript
// JavaScript/Node.js绀轰緥
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

async function uploadFiles() {
    const form = new FormData();

    // 娣诲姞澶氫釜鏂囦欢
    form.append('files', fs.createReadStream('weather_data.csv'));
    form.append('files', fs.createReadStream('power_data.csv'));
    form.append('files', fs.createReadStream('turbine_data.csv'));

    // 娣诲姞鍏朵粬鍙傛暟
    form.append('data_type', 'training');
    form.append('description', '鎵归噺璁粌鏁版嵁');

    try {
        const response = await axios.post('http://localhost:5000/upload_batch', form, {
            headers: {
                ...form.getHeaders(),
                'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
            }
        });

        console.log('鎵归噺涓婁紶鎴愬姛:', response.data);
    } catch (error) {
        console.error('涓婁紶澶辫触:', error.response.data);
    }
}
```

### 鑾峰彇鏁版嵁鍒楄〃
```bash
# 鑾峰彇鎵€鏈夎缁冩暟鎹?
curl -X GET "http://localhost:5000/api/data/list?type=train&page=1&limit=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# 甯﹁繃婊ゆ潯浠?
curl -X GET "http://localhost:5000/api/data/list?type=predict&status=completed&start_date=2024-01-01&end_date=2024-01-31" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## 妯″瀷璁粌API

### 鍒涘缓璁粌浠诲姟
```python
import requests
import time

def train_model():
    # 1. 鍒涘缓璁粌浠诲姟
    url = "http://localhost:5000/modeltrain"
    headers = {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "Content-Type": "application/json"
    }

    training_config = {
        "name": "XGBoost妯″瀷_2024骞?鏈?,
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
        print(f"璁粌浠诲姟宸插垱寤? {task_id}")

        # 2. 鐩戞帶璁粌杩涘害
        monitor_training(task_id)
    else:
        print(f"浠诲姟鍒涘缓澶辫触: {result['error']}")

def monitor_training(task_id):
    """鐩戞帶璁粌杩涘害"""
    status_url = f"http://localhost:5000/modeltrain/status/{task_id}"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}

    while True:
        response = requests.get(status_url, headers=headers)
        status = response.json()['data']

        print(f"璁粌杩涘害: {status['progress']}% - {status['status']}")

        if status['status'] == 'completed':
            print("璁粌瀹屾垚!")
            print(f"妯″瀷ID: {status['model_id']}")
            print(f"璁粌绮惧害: {status['metrics']}")
            break
        elif status['status'] == 'failed':
            print(f"璁粌澶辫触: {status.get('error', '鏈煡閿欒')}")
            break

        time.sleep(30)  # 姣?0绉掓鏌ヤ竴娆?

# 鎵ц璁粌
train_model()
```

### 鑾峰彇璁粌缁撴灉鍜屾ā鍨?
```bash
# 涓嬭浇璁粌濂界殑妯″瀷
curl -X GET "http://localhost:5000/modeltrain/download-model?model_id=1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -o model.pkl

# 涓嬭浇鏍囧噯鍖栧櫒
curl -X GET "http://localhost:5000/modeltrain/download-scaler?model_id=1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -o scaler.pkl
```

## 鍔熺巼棰勬祴API

### 鍒涘缓棰勬祴浠诲姟
```javascript
// JavaScript绀轰緥 - 鍒涘缓棰勬祴浠诲姟
async function createPrediction() {
    const predictionData = {
        model_id: 1,
        name: "2024骞?鏈?6鏃ュ姛鐜囬娴?,
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
            console.log('棰勬祴浠诲姟鍒涘缓鎴愬姛:', result.data);
            return result.data.prediction_id;
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        console.error('棰勬祴浠诲姟鍒涘缓澶辫触:', error);
    }
}
```

### 鎵归噺棰勬祴
```python
import asyncio
import aiohttp
import pandas as pd

async def batch_predict(models, time_ranges):
    """鎵归噺鍒涘缓棰勬祴浠诲姟"""
    tasks = []

    async with aiohttp.ClientSession() as session:
        for model_id, time_range in zip(models, time_ranges):
            task = create_single_prediction(session, model_id, time_range)
            tasks.append(task)

        # 骞跺彂鎵ц鎵€鏈夐娴嬩换鍔?
        results = await asyncio.gather(*tasks)
        return results

async def create_single_prediction(session, model_id, time_range):
    """鍒涘缓鍗曚釜棰勬祴浠诲姟"""
    url = "http://localhost:5000/predict"
    headers = {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "Content-Type": "application/json"
    }

    prediction_data = {
        "model_id": model_id,
        "name": f"鎵归噺棰勬祴_{model_id}_{time_range['start']}",
        "start_time": time_range['start'],
        "end_time": time_range['end'],
        "data_source": "weather_forecast"
    }

    async with session.post(url, headers=headers, json=prediction_data) as response:
        result = await response.json()
        return result

# 浣跨敤绀轰緥
models = [1, 2, 3]  # 澶氫釜妯″瀷ID
time_ranges = [
    {"start": "2024-01-16T00:00:00Z", "end": "2024-01-16T12:00:00Z"},
    {"start": "2024-01-16T12:00:00Z", "end": "2024-01-17T00:00:00Z"},
    {"start": "2024-01-17T00:00:00Z", "end": "2024-01-17T12:00:00Z"}
]

# 杩愯鎵归噺棰勬祴
results = asyncio.run(batch_predict(models, time_ranges))
print(f"鎵归噺棰勬祴瀹屾垚锛屽叡鍒涘缓 {len(results)} 涓娴嬩换鍔?)
```

### 鑾峰彇棰勬祴缁撴灉
```python
import requests
import pandas as pd
import matplotlib.pyplot as plt

def get_prediction_results(prediction_id):
    """鑾峰彇棰勬祴缁撴灉骞跺彲瑙嗗寲"""
    url = f"http://localhost:5000/predict/result/{prediction_id}"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}

    response = requests.get(url, headers=headers)
    result = response.json()

    if result['success']:
        data = result['data']

        # 杞崲涓篋ataFrame
        df = pd.DataFrame(data['results'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # 鏄剧ず缁熻淇℃伅
        print("棰勬祴缁熻淇℃伅:")
        print(f"MAE: {data['statistics']['mae']:.2f} kW")
        print(f"RMSE: {data['statistics']['rmse']:.2f} kW")
        print(f"MAPE: {data['statistics']['mape']:.2f}%")
        print(f"R虏: {data['statistics']['r2']:.3f}")

        # 鍙鍖?
        plt.figure(figsize=(12, 6))
        plt.plot(df['timestamp'], df['predicted_power'],
                label='棰勬祴鍔熺巼', color='blue', linewidth=2)

        # 濡傛灉鏈夊疄闄呭€硷紝涔熺粯鍒跺嚭鏉?
        if 'actual_power' in df.columns:
            plt.plot(df['timestamp'], df['actual_power'],
                    label='瀹為檯鍔熺巼', color='red', linewidth=2, alpha=0.7)

        # 缁樺埗缃俊鍖洪棿
        if 'confidence_lower' in df.columns:
            plt.fill_between(df['timestamp'],
                           df['confidence_lower'],
                           df['confidence_upper'],
                           alpha=0.3, color='blue', label='缃俊鍖洪棿')

        plt.xlabel('鏃堕棿')
        plt.ylabel('鍔熺巼 (kW)')
        plt.title('椋庡姛鐜囬娴嬬粨鏋?)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()

        return df
    else:
        print(f"鑾峰彇棰勬祴缁撴灉澶辫触: {result['error']}")
        return None

# 浣跨敤绀轰緥
df_predictions = get_prediction_results("pred_12345")
```

## 杩愯惀鏁版嵁API

### 涓婁紶杩愯惀鏁版嵁
```python
import requests
import pandas as pd
from datetime import datetime

def upload_operational_data(file_path, table_name):
    """涓婁紶杩愯惀鏁版嵁"""
    url = "http://localhost:5000/operational/upload"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}

    # 鏀寔鐨勮繍钀ユ暟鎹〃
    supported_tables = [
        'wind_speed_data',           # 鍗曟満椋庨€熸暟鎹?
        'turbine_power_data',        # 鍗曟満鍔熺巼鏁版嵁
        'weather_data',              # 姘旇薄淇℃伅鏁版嵁
        'installed_capacity_data',   # 瑁呮満瀹归噺鏁版嵁
        'available_capacity_data',   # 鍙敤瀹归噺鏁版嵁
        'theoretical_power_data',    # 鐞嗚鍔熺巼鏁版嵁
        'available_power_data'       # 鍙敤鍔熺巼鏁版嵁
    ]

    if table_name not in supported_tables:
        print(f"涓嶆敮鎸佺殑琛ㄥ悕: {table_name}")
        return

    files = {'file': open(file_path, 'rb')}
    data = {
        'table_name': table_name,
        'description': f'{table_name}_{datetime.now().strftime("%Y%m%d")}'
    }

    response = requests.post(url, headers=headers, files=files, data=data)
    result = response.json()

    if result['success']:
        print(f"杩愯惀鏁版嵁涓婁紶鎴愬姛: {result['data']['records_uploaded']} 鏉¤褰?)
    else:
        print(f"涓婁紶澶辫触: {result['error']}")

# 鎵归噺涓婁紶涓嶅悓绫诲瀷鐨勮繍钀ユ暟鎹?
operational_files = {
    'wind_speed_data': 'wind_speed_2024.csv',
    'turbine_power_data': 'turbine_power_2024.csv',
    'weather_data': 'weather_station_2024.csv'
}

for table_name, file_path in operational_files.items():
    upload_operational_data(file_path, table_name)
```

### 鏌ヨ杩愯惀鏁版嵁
```bash
# 鑾峰彇椋庨€熸暟鎹?
curl -X GET "http://localhost:5000/operational/data/wind_speed_data?start_date=2024-01-01&end_date=2024-01-31&limit=100" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# 鑾峰彇鐗瑰畾椋庢満鐨勫姛鐜囨暟鎹?
curl -X GET "http://localhost:5000/operational/data/turbine_power_data?turbine_id=T001&date=2024-01-15" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## 绯荤粺绠＄悊API

### 鑾峰彇绯荤粺鐘舵€?
```python
import requests
import json
from datetime import datetime

def check_system_health():
    """妫€鏌ョ郴缁熷仴搴风姸鎬?""
    url = "http://localhost:5000/system/status"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}

    response = requests.get(url, headers=headers)
    result = response.json()

    if result['success']:
        status = result['data']

        print("=== 绯荤粺鍋ュ悍鐘舵€?===")
        print(f"鏁翠綋鐘舵€? {status['status']}")
        print(f"杩愯鏃堕棿: {status['system_info']['uptime']}")
        print()

        print("=== 鏈嶅姟鐘舵€?===")
        for service, state in status['services'].items():
            status_icon = "鉁? if state == "connected" else "鉂?
            print(f"{status_icon} {service}: {state}")
        print()

        print("=== 绯荤粺璧勬簮 ===")
        sys_info = status['system_info']
        print(f"CPU浣跨敤鐜? {sys_info['cpu_usage']}%")
        print(f"鍐呭瓨浣跨敤鐜? {sys_info['memory_usage']}%")
        print(f"纾佺洏浣跨敤鐜? {sys_info['disk_usage']}%")

        # 璧勬簮鍛婅
        if sys_info['cpu_usage'] > 80:
            print("鈿狅笍 璀﹀憡: CPU浣跨敤鐜囪繃楂?)
        if sys_info['memory_usage'] > 85:
            print("鈿狅笍 璀﹀憡: 鍐呭瓨浣跨敤鐜囪繃楂?)
        if sys_info['disk_usage'] > 90:
            print("鈿狅笍 璀﹀憡: 纾佺洏浣跨敤鐜囪繃楂?)

    else:
        print(f"绯荤粺鐘舵€佹鏌ュけ璐? {result['error']}")

# 瀹氭椂妫€鏌ョ郴缁熺姸鎬?
def monitor_system(interval=300):
    """瀹氭湡鐩戞帶绯荤粺鐘舵€?""
    while True:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 绯荤粺妫€鏌?)
        check_system_health()
        time.sleep(interval)

# 杩愯鐩戞帶
check_system_health()
```

### 鑾峰彇绯荤粺缁熻淇℃伅
```bash
# 鑾峰彇浠婃棩棰勬祴缁熻
curl -X GET "http://localhost:5000/system/stats?type=predictions&date=$(date +%Y-%m-%d)" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# 鑾峰彇鏈湀妯″瀷璁粌缁熻
curl -X GET "http://localhost:5000/system/stats?type=training&month=$(date +%Y-%m)" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## 楂樼骇鍔熻兘绀轰緥

### WebSocket瀹炴椂鏁版嵁
```javascript
// JavaScript WebSocket瀹㈡埛绔?
const socket = io('http://localhost:5000', {
    auth: {
        token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    }
});

// 鐩戝惉璁粌杩涘害
socket.on('training_progress', (data) => {
    console.log('璁粌杩涘害:', data.progress + '%');
    console.log('鐘舵€?', data.status);

    if (data.status === 'completed') {
        console.log('璁粌瀹屾垚锛佹ā鍨婭D:', data.model_id);
    }
});

// 鐩戝惉棰勬祴缁撴灉
socket.on('prediction_result', (data) => {
    console.log('鏂扮殑棰勬祴缁撴灉:', data);

    // 鏇存柊瀹炴椂鍥捐〃
    updateRealtimeChart(data);
});

// 鐩戝惉绯荤粺鍛婅
socket.on('system_alert', (alert) => {
    console.log('绯荤粺鍛婅:', alert.message);

    if (alert.severity === 'critical') {
        // 鏄剧ず绱ф€ュ憡璀﹂€氱煡
        showCriticalAlert(alert);
    }
});

// 鍔犲叆鎴块棿锛堟寜浠诲姟ID锛?
socket.emit('join_room', 'task_12345');
socket.emit('join_room', 'pred_67890');
```

### 鎵归噺鏁版嵁澶勭悊
```python
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import requests

def process_large_dataset(file_path, chunk_size=1000):
    """鍒嗗潡澶勭悊澶у瀷鏁版嵁闆?""

    # 璇诲彇CSV鏂囦欢
    chunks = pd.read_csv(file_path, chunksize=chunk_size)

    # 骞惰澶勭悊姣忎釜鏁版嵁鍧?
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []

        for chunk_id, chunk in enumerate(chunks):
            # 鏁版嵁棰勫鐞?
            processed_chunk = preprocess_data(chunk)

            # 鎻愪氦澶勭悊浠诲姟
            future = executor.submit(upload_chunk, processed_chunk, chunk_id)
            futures.append(future)

        # 绛夊緟鎵€鏈変换鍔″畬鎴?
        results = [future.result() for future in futures]

    return results

def preprocess_data(df):
    """鏁版嵁棰勫鐞?""
    # 澶勭悊缂哄け鍊?
    df = df.fillna(method='forward')

    # 鏁版嵁楠岃瘉
    df = df[(df['wind_speed'] >= 0) & (df['wind_speed'] <= 50)]
    df = df[(df['power_output'] >= 0) & (df['power_output'] <= 5000)]

    # 娣诲姞娲剧敓鐗瑰緛
    df['wind_speed_squared'] = df['wind_speed'] ** 2
    df['wind_direction_sin'] = np.sin(np.radians(df['wind_direction']))
    df['wind_direction_cos'] = np.cos(np.radians(df['wind_direction']))

    return df

def upload_chunk(chunk, chunk_id):
    """涓婁紶鏁版嵁鍧?""
    # 灏咲ataFrame杞崲涓篊SV
    csv_data = chunk.to_csv(index=False)

    files = {
        'file': (f'chunk_{chunk_id}.csv', csv_data, 'text/csv')
    }

    data = {
        'chunk_id': chunk_id,
        'total_chunks': 'unknown',  # 灏嗗湪鏈€鍚庢洿鏂?
        'description': f'鏁版嵁鍧梍{chunk_id}'
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

### 鑷姩鍖栭娴嬫祦绋?
```python
import schedule
import time
from datetime import datetime, timedelta
import requests

def automated_prediction():
    """鑷姩鍖栭娴嬩换鍔?""

    # 1. 鑾峰彇鏈€鏂版皵璞℃暟鎹?
    weather_data = fetch_latest_weather_data()

    # 2. 鏁版嵁棰勫鐞?
    processed_data = preprocess_weather_data(weather_data)

    # 3. 閫夋嫨鏈€浼樻ā鍨?
    best_model = select_best_model()

    # 4. 鍒涘缓棰勬祴浠诲姟
    prediction_id = create_prediction_task(best_model, processed_data)

    # 5. 绛夊緟棰勬祴瀹屾垚
    results = wait_for_prediction_completion(prediction_id)

    # 6. 鐢熸垚鎶ュ憡
    report_id = generate_automated_report(results)

    # 7. 鍙戦€侀€氱煡
    send_prediction_notification(results, report_id)

    print(f"[{datetime.now()}] 鑷姩鍖栭娴嬪畬鎴? {prediction_id}")

def fetch_latest_weather_data():
    """鑾峰彇鏈€鏂版皵璞℃暟鎹?""
    # 浠庢皵璞℃湇鍔PI鑾峰彇鏁版嵁
    response = requests.get('http://api.weather.com/forecast', params={
        'location': 'wind_farm_001',
        'hours': 72
    })
    return response.json()

def select_best_model():
    """閫夋嫨鏈€浼樻ā鍨?""
    # 鑾峰彇鎵€鏈夊彲鐢ㄦā鍨?
    response = requests.get(
        'http://localhost:5000/model/list?status=completed',
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    )

    models = response.json()['data']['items']

    # 閫夋嫨绮惧害鏈€楂樼殑妯″瀷
    best_model = max(models, key=lambda x: x['accuracy'])
    return best_model['id']

def create_prediction_task(model_id, weather_data):
    """鍒涘缓棰勬祴浠诲姟"""
    prediction_config = {
        "model_id": model_id,
        "name": f"鑷姩棰勬祴_{datetime.now().strftime('%Y%m%d_%H%M')}",
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

# 璁剧疆瀹氭椂浠诲姟
schedule.every().day.at("06:00").do(automated_prediction)  # 姣忓ぉ鏃╀笂6鐐?
schedule.every().day.at("18:00").do(automated_prediction)  # 姣忓ぉ鏅氫笂6鐐?

# 杩愯璋冨害鍣?
while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## 閿欒澶勭悊绀轰緥

### API閿欒澶勭悊
```python
import requests
from requests.exceptions import RequestException
import time

def safe_api_call(method, url, **kwargs):
    """瀹夊叏鐨凙PI璋冪敤锛屽寘鍚噸璇曟満鍒?""

    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            response = requests.request(method, url, **kwargs)

            # 澶勭悊HTTP閿欒
            if response.status_code >= 400:
                error_data = response.json()

                if response.status_code == 401:
                    print("璁よ瘉澶辫触锛岄渶瑕侀噸鏂扮櫥褰?)
                    # 閲嶆柊鑾峰彇token
                    new_token = refresh_token()
                    kwargs['headers']['Authorization'] = f'Bearer {new_token}'
                    continue

                elif response.status_code == 429:
                    print("璇锋眰杩囦簬棰戠箒锛岀瓑寰呴噸璇?)
                    time.sleep(retry_delay * (attempt + 1))
                    continue

                else:
                    print(f"API閿欒 ({response.status_code}): {error_data.get('error', '鏈煡閿欒')}")
                    return None

            return response.json()

        except RequestException as e:
            print(f"缃戠粶璇锋眰澶辫触 (灏濊瘯 {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                print("鎵€鏈夐噸璇曞皾璇曢兘澶辫触浜?)
                return None

    return None

def refresh_token():
    """鍒锋柊璁块棶浠ょ墝"""
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
        raise Exception("鏃犳硶鍒锋柊token")
```

### 鏁版嵁楠岃瘉绀轰緥
```python
def validate_prediction_data(data):
    """楠岃瘉棰勬祴杈撳叆鏁版嵁"""

    required_fields = ['wind_speed', 'wind_direction', 'temperature']

    # 妫€鏌ュ繀闇€瀛楁
    for field in required_fields:
        if field not in data:
            raise ValueError(f"缂哄皯蹇呴渶瀛楁: {field}")

    # 楠岃瘉鏁版嵁鑼冨洿
    if not (0 <= data['wind_speed'] <= 50):
        raise ValueError("椋庨€熷繀椤诲湪0-50 m/s涔嬮棿")

    if not (0 <= data['wind_direction'] <= 360):
        raise ValueError("椋庡悜蹇呴』鍦?-360搴︿箣闂?)

    if not (-40 <= data['temperature'] <= 60):
        raise ValueError("娓╁害蹇呴』鍦?40鍒?0鎽勬皬搴︿箣闂?)

    # 妫€鏌ユ暟鎹被鍨?
    for field in required_fields:
        if not isinstance(data[field], (int, float)):
            raise ValueError(f"瀛楁 {field} 蹇呴』鏄暟鍊肩被鍨?)

    return True

# 浣跨敤绀轰緥
try:
    prediction_data = {
        "wind_speed": 15.5,
        "wind_direction": 180,
        "temperature": 25.0
    }

    validate_prediction_data(prediction_data)
    print("鏁版嵁楠岃瘉閫氳繃")

except ValueError as e:
    print(f"鏁版嵁楠岃瘉澶辫触: {e}")
```

---

## 鎬ц兘浼樺寲绀轰緥

### 骞跺彂璇锋眰澶勭悊
```python
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor

async def concurrent_predictions(session, prediction_requests):
    """骞跺彂澶勭悊澶氫釜棰勬祴璇锋眰"""

    async def single_prediction(request_data):
        url = "http://localhost:5000/predict"
        headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "Content-Type": "application/json"
        }

        async with session.post(url, headers=headers, json=request_data) as response:
            return await response.json()

    # 鍒涘缓骞跺彂浠诲姟
    tasks = [single_prediction(req) for req in prediction_requests]

    # 骞跺彂鎵ц
    results = await asyncio.gather(*tasks)
    return results

async def optimized_batch_processing():
    """浼樺寲鐨勬壒閲忓鐞?""

    # 棰勬祴璇锋眰鍒楄〃
    prediction_requests = [
        {
            "model_id": 1,
            "name": f"棰勬祴浠诲姟_{i}",
            "start_time": f"2024-01-16T{i:02d}:00:00Z",
            "end_time": f"2024-01-16T{i+1:02d}:00:00Z",
            "data_source": "weather_forecast"
        }
        for i in range(24)  # 24灏忔椂鐨勯娴?
    ]

    # 浣跨敤杩炴帴姹?
    connector = aiohttp.TCPConnector(
        limit=100,  # 鎬昏繛鎺ユ暟闄愬埗
        limit_per_host=30,  # 姣忎釜涓绘満鐨勮繛鎺ユ暟闄愬埗
        ttl_dns_cache=300,  # DNS缂撳瓨鏃堕棿
        use_dns_cache=True,
    )

    timeout = aiohttp.ClientTimeout(
        total=30,  # 鎬昏秴鏃舵椂闂?
        connect=10,  # 杩炴帴瓒呮椂鏃堕棿
        sock_read=10  # 璇诲彇瓒呮椂鏃堕棿
    )

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout
    ) as session:
        start_time = time.time()

        # 鍒嗘壒澶勭悊锛岄伩鍏嶄竴娆℃€ц姹傝繃澶?
        batch_size = 5
        all_results = []

        for i in range(0, len(prediction_requests), batch_size):
            batch = prediction_requests[i:i + batch_size]
            batch_results = await concurrent_predictions(session, batch)
            all_results.extend(batch_results)

            # 鎵规闂寸◢浣滅瓑寰咃紝閬垮厤绯荤粺杩囪浇
            if i + batch_size < len(prediction_requests):
                await asyncio.sleep(0.5)

        end_time = time.time()

        print(f"澶勭悊瀹屾垚: {len(all_results)} 涓娴嬭姹?)
        print(f"鎬昏€楁椂: {end_time - start_time:.2f} 绉?)
        print(f"骞冲潎鍝嶅簲鏃堕棿: {(end_time - start_time) / len(all_results):.2f} 绉?璇锋眰")

        return all_results

# 杩愯浼樺寲鍚庣殑鎵归噺澶勭悊
if __name__ == "__main__":
    results = asyncio.run(optimized_batch_processing())
```

### 缂撳瓨绛栫暐瀹炵幇
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
        """鐢熸垚缂撳瓨閿?""
        key_data = {
            'function': func_name,
            'args': args,
            'kwargs': kwargs
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return f"api_cache:{hashlib.md5(key_string.encode()).hexdigest()}"

    def cache_result(self, ttl=None):
        """缂撳瓨瑁呴グ鍣?""
        if ttl is None:
            ttl = self.default_ttl

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = self.generate_cache_key(func.__name__, *args, **kwargs)

                # 灏濊瘯浠庣紦瀛樿幏鍙?
                cached_result = self.redis_client.get(cache_key)
                if cached_result:
                    print(f"浠庣紦瀛樿幏鍙栫粨鏋? {func.__name__}")
                    return json.loads(cached_result)

                # 鎵ц鍑芥暟骞剁紦瀛樼粨鏋?
                result = func(*args, **kwargs)
                if result:
                    self.redis_client.setex(
                        cache_key,
                        ttl,
                        json.dumps(result)
                    )
                    print(f"缂撳瓨缁撴灉: {func.__name__}")

                return result

            return wrapper
        return decorator

# 浣跨敤缂撳瓨瑁呴グ鍣?
api_cache = APICache()

@api_cache.cache_result(ttl=600)  # 缂撳瓨10鍒嗛挓
def get_weather_forecast(station_id, start_date, end_date):
    """鑾峰彇澶╂皵棰勬姤鏁版嵁锛堝甫缂撳瓨锛?""
    url = f"http://localhost:5000/weather/forecast"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    params = {
        "station_id": station_id,
        "start_date": start_date,
        "end_date": end_date
    }

    response = requests.get(url, headers=headers, params=params)
    return response.json()

@api_cache.cache_result(ttl=1800)  # 缂撳瓨30鍒嗛挓
def get_model_list(status="completed"):
    """鑾峰彇妯″瀷鍒楄〃锛堝甫缂撳瓨锛?""
    url = f"http://localhost:5000/model/list"
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    params = {"status": status}

    response = requests.get(url, headers=headers, params=params)
    return response.json()
```

### 鏁版嵁搴撴煡璇紭鍖?
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
        """浼樺寲鐨勫ぉ姘旀暟鎹煡璇?""

        # 浣跨敤鍙傛暟鍖栨煡璇㈤槻姝QL娉ㄥ叆
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

        # 浣跨敤pandas鐩存帴璇诲彇鏁版嵁
        df = pd.read_sql_query(
            query,
            self.engine,
            params={
                'station_ids': station_ids,
                'start_date': start_date,
                'end_date': end_date
            }
        )

        # 璁剧疆绱㈠紩浼樺寲鍚庣画澶勭悊
        df['measurement_time'] = pd.to_datetime(df['measurement_time'])
        df.set_index('measurement_time', inplace=True)

        return df

    def get_aggregated_data(self, station_id, date, aggregation_level='hour'):
        """鑾峰彇鑱氬悎鏁版嵁"""

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
        """鍒嗛〉鑾峰彇澶ф暟鎹泦"""

        query = text(f"""
            SELECT *
            FROM {table}
            WHERE id > :start_id
            ORDER BY id ASC
            LIMIT :batch_size
        """)

        offset = start_id

        while True:
            # 鑾峰彇涓€鎵规暟鎹?
            batch_df = pd.read_sql_query(
                query,
                self.engine,
                params={'start_id': offset, 'batch_size': batch_size}
            )

            if batch_df.empty:
                break

            yield batch_df

            # 鏇存柊鍋忕Щ閲?
            offset = batch_df['id'].max()

            # 鍙€夛細娣诲姞寤惰繜閬垮厤鏁版嵁搴撹繃杞?
            # time.sleep(0.1)

# 浣跨敤绀轰緥
query_engine = OptimizedDataQueries("postgresql://user:password@localhost:5432/wind_power")

# 浼樺寲鐨勫ぉ姘旀暟鎹煡璇?
weather_data = query_engine.get_weather_data_optimized(
    station_ids=['ST001', 'ST002', 'ST003'],
    start_date='2024-01-01',
    end_date='2024-01-31'
)

# 鑱氬悎鏁版嵁鏌ヨ
hourly_data = query_engine.get_aggregated_data(
    station_id='ST001',
    date='2024-01-15',
    aggregation_level='hour'
)

# 鍒嗛〉澶勭悊澶ф暟鎹泦
for batch_df in query_engine.get_data_with_pagination('weather_data', batch_size=5000):
    # 澶勭悊姣忎釜鎵规鐨勬暟鎹?
    process_batch(batch_df)
    print(f"澶勭悊浜?{len(batch_df)} 鏉¤褰?)
```

---

## 澶氳瑷€绀轰緥

### Java绀轰緥
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

    // 鏁版嵁妯″瀷绫?
    public static class PredictionRequest {
        public int modelId;
        public String name;
        public String startTime;
        public String endTime;
        public String dataSource;
        public Map<String, Object> parameters;

        // 鏋勯€犲嚱鏁板拰getter/setter鐪佺暐
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

### Go绀轰緥
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
        Name:       "Go瀹㈡埛绔娴嬩换鍔?,
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

### C#绀轰緥
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

        // 娴嬭瘯杩炴帴
        var isConnected = await client.TestConnectionAsync();
        Console.WriteLine($"Connection test: {(isConnected ? "Success" : "Failed")}");

        if (isConnected)
        {
            var request = new PredictionRequest
            {
                ModelId = 1,
                Name = "C#瀹㈡埛绔娴嬩换鍔?,
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

## 璋冭瘯鍜岀洃鎺хず渚?

### 璇锋眰鏃ュ織璁板綍
```python
import logging
import time
import json
from datetime import datetime

class APIRequestLogger:
    def __init__(self, log_file='api_requests.log'):
        self.logger = logging.getLogger('api_requests')
        self.logger.setLevel(logging.INFO)

        # 鏂囦欢澶勭悊鍣?
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        # 鎺у埗鍙板鐞嗗櫒
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        # 鏍煎紡鍖栧櫒
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log_request(self, method, url, headers=None, data=None, response=None, duration=None):
        """璁板綍API璇锋眰鍜屽搷搴?""

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
        """娓呯悊鏁忔劅淇℃伅"""
        sanitized = headers.copy()
        sensitive_keys = ['authorization', 'x-api-key', 'cookie']

        for key in sensitive_keys:
            if key.lower() in sanitized:
                sanitized[key] = '***REDACTED***'

        return sanitized

    def _truncate_response(self, response, max_length=1000):
        """鎴柇鍝嶅簲鏁版嵁"""
        try:
            content = response.text
            if len(content) > max_length:
                return content[:max_length] + '... [TRUNCATED]'
            return content
        except:
            return '[Unable to read response content]'

# 浣跨敤绀轰緥
request_logger = APIRequestLogger()

def logged_api_request(method, url, **kwargs):
    """甯︽棩蹇楄褰曠殑API璇锋眰"""
    start_time = time.time()

    try:
        response = requests.request(method, url, **kwargs)
        duration = (time.time() - start_time) * 1000  # 杞崲涓烘绉?

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

### 鎬ц兘鐩戞帶
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
        """寮€濮嬫€ц兘鐩戞帶"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        print("鎬ц兘鐩戞帶宸插惎鍔?)

    def stop_monitoring(self):
        """鍋滄鎬ц兘鐩戞帶"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        print("鎬ц兘鐩戞帶宸插仠姝?)

    def _monitor_loop(self, interval):
        """鐩戞帶寰幆"""
        while self.monitoring:
            # CPU浣跨敤鐜?
            cpu_percent = psutil.cpu_percent(interval=None)
            self.cpu_history.append(cpu_percent)

            # 鍐呭瓨浣跨敤鐜?
            memory = psutil.virtual_memory()
            self.memory_history.append(memory.percent)

            # 缃戠粶IO
            network = psutil.net_io_counters()
            self.network_history.append({
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'timestamp': time.time()
            })

            time.sleep(interval)

    def get_stats(self):
        """鑾峰彇鎬ц兘缁熻"""
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
        """妫€鏌ヨ祫婧愪娇鐢ㄦ儏鍐?""
        stats = self.get_stats()
        if not stats:
            return {'alerts': [], 'status': 'unknown'}

        alerts = []

        # CPU鍛婅
        if stats['cpu']['current'] > cpu_threshold:
            alerts.append({
                'type': 'cpu_high',
                'message': f"CPU浣跨敤鐜囪繃楂? {stats['cpu']['current']:.1f}%",
                'severity': 'warning' if stats['cpu']['current'] < 90 else 'critical'
            })

        # 鍐呭瓨鍛婅
        if stats['memory']['current'] > memory_threshold:
            alerts.append({
                'type': 'memory_high',
                'message': f"鍐呭瓨浣跨敤鐜囪繃楂? {stats['memory']['current']:.1f}%",
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

# 浣跨敤绀轰緥
perf_monitor = PerformanceMonitor()

# 寮€濮嬬洃鎺?
perf_monitor.start_monitoring(interval=2)

# 妯℃嫙涓€浜涘伐浣?
time.sleep(10)

# 妫€鏌ヨ祫婧愪娇鐢ㄦ儏鍐?
resource_check = perf_monitor.check_resource_usage()
print(f"璧勬簮鐘舵€? {resource_check['status']}")
for alert in resource_check['alerts']:
    print(f"鍛婅: {alert['message']}")

# 鑾峰彇璇︾粏缁熻淇℃伅
stats = perf_monitor.get_stats()
if stats:
    print(f"CPU骞冲潎浣跨敤鐜? {stats['cpu']['average']:.1f}%")
    print(f"鍐呭瓨骞冲潎浣跨敤鐜? {stats['memory']['average']:.1f}%")

# 鍋滄鐩戞帶
perf_monitor.stop_monitoring()
```

---

杩欎簺API浣跨敤绀轰緥娑电洊浜嗛鍔熺巼棰勬祴绯荤粺鐨勪富瑕佸姛鑳斤紝鍖呮嫭璁よ瘉銆佹暟鎹鐞嗐€佹ā鍨嬭缁冦€佸姛鐜囬娴嬨€佽繍钀ユ暟鎹鐞嗗拰绯荤粺绠＄悊绛夊悇涓柟闈€傚悓鏃惰繕鎻愪緵浜嗘€ц兘浼樺寲銆侀敊璇鐞嗐€佸璇█鏀寔鍜岃皟璇曠洃鎺х殑楂樼骇绀轰緥銆傛偍鍙互鏍规嵁瀹為檯闇€姹傞€夋嫨鍚堥€傜殑绀轰緥杩涜淇敼鍜屼娇鐢ㄣ€傝寰楁浛鎹㈢ず渚嬩腑鐨則oken鍜孶RL涓烘偍鐨勫疄闄呭€笺€傚鏋滄偍闇€瑕佹洿澶氱壒瀹氬姛鑳界殑绀轰緥锛岃闅忔椂璇㈤棶銆?}
> Deprecation Notice (M1): Manual model training and manual predict endpoints are decommissioned from active product flow.
> Prefer /api/v1/autopredict/* and farm-scoped data APIs.

