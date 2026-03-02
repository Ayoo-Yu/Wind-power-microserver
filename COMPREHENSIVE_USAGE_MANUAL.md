# 椋庡姛鐜囬娴嬬郴缁?- 瀹屾暣浣跨敤鎵嬪唽

## 馃搵 鐩綍

1. [绯荤粺姒傝堪](#绯荤粺姒傝堪)
2. [蹇€熷紑濮媇(#蹇€熷紑濮?
3. [涓嶅悓鐢ㄦ埛瑙掕壊鎸囧崡](#涓嶅悓鐢ㄦ埛瑙掕壊鎸囧崡)
4. [鏍稿績鍔熻兘浣跨敤](#鏍稿績鍔熻兘浣跨敤)
5. [API鎺ュ彛浣跨敤](#api鎺ュ彛浣跨敤)
6. [閰嶇疆鍜岄儴缃瞉(#閰嶇疆鍜岄儴缃?
7. [鐩戞帶鍜岀淮鎶(#鐩戞帶鍜岀淮鎶?
8. [鏁呴殰鎺掗櫎](#鏁呴殰鎺掗櫎)
9. [鏈€浣冲疄璺礭(#鏈€浣冲疄璺?
10. [甯歌闂](#甯歌闂)

## 绯荤粺姒傝堪

### 馃彈锔?绯荤粺鏋舵瀯

椋庡姛鐜囬娴嬬郴缁熸彁渚涗袱绉嶉儴缃叉ā寮忥細

#### 妯″紡1锛氬崟浣撴灦鏋勶紙閫傚悎涓皬瑙勬ā锛?
- **鍓嶇**: Vue.js 3 + Element Plus
- **鍚庣**: Python Flask + scikit-learn
- **鏁版嵁搴?*: KingBase閲戜粨鏁版嵁搴?
- **鏂囦欢瀛樺偍**: MinIO瀵硅薄瀛樺偍

#### 妯″紡2锛氬井鏈嶅姟鏋舵瀯锛堥€傚悎澶ц妯★級
- **API缃戝叧**: Kong Gateway
- **6涓井鏈嶅姟**: 姘旇薄銆丼CADA銆佸姛鐜囬娴嬨€佹姤鍛娿€侀鍦恒€佺鎴?
- **娑堟伅闃熷垪**: Kafka + Zookeeper
- **鏁版嵁搴?*: PostgreSQL + Redis + InfluxDB
- **鏈哄櫒瀛︿範**: MLflow妯″瀷绠＄悊

### 馃幆 鏍稿績鍔熻兘

1. **澶氭椂闂村昂搴﹀姛鐜囬娴?*锛?灏忔椂-72灏忔椂锛?
2. **澶氱鏈哄櫒瀛︿範妯″瀷**锛圠STM銆乆GBoost銆侀殢鏈烘．鏋楋級
3. **鑷姩鍖栨姤鍛婄敓鎴?*锛圥DF銆丠TML銆丒xcel锛?
4. **瀹炴椂鐩戞帶鍛婅**锛圥rometheus + Grafana锛?
5. **澶氱鎴锋敮鎸?*锛堜紒涓氱骇鏉冮檺绠＄悊锛?
6. **鏁版嵁璐ㄩ噺绠＄悊**锛堝畬鏁存€ф鏌ャ€佸紓甯告娴嬶級

## 蹇€熷紑濮?

### 馃殌 涓€閿惎鍔?

#### Windows鐢ㄦ埛
```bash
# 鍙屽嚮杩愯鎴栧懡浠よ鎵ц
quick-start.bat
```

#### Linux/Mac鐢ㄦ埛
```bash
# 娣诲姞鎵ц鏉冮檺骞惰繍琛?
chmod +x quick-start.sh
./quick-start.sh
```

鍚姩宸ュ叿鎻愪緵浠ヤ笅閫夐」锛?
- **1锔忊儯 寮€鍙戠幆澧?* - 蹇€熶綋楠屾墍鏈夊姛鑳?
- **2锔忊儯 寰湇鍔℃灦鏋?* - 浼佷笟绾у畬鏁撮儴缃?
- **3锔忊儯 浠呭熀纭€璁炬柦** - 鏁版嵁搴撳拰涓棿浠?
- **4锔忊儯 绯荤粺鐘舵€佹鏌?* - 鍋ュ悍鐘舵€佹鏌?
- **5锔忊儯 鍋滄鎵€鏈夋湇鍔?* - 浼橀泤鍏抽棴绯荤粺
- **6锔忊儯 鏌ョ湅鏃ュ織** - 鏁呴殰鎺掓煡宸ュ叿

### 馃摝 鎵嬪姩鍚姩姝ラ

#### 寮€鍙戠幆澧冨惎鍔?
```bash
# 1. 鍚姩鍩虹璁炬柦
cd wind-power-forecast
docker-compose -f database/docker-compose.yaml up -d

# 2. 鍚姩鍚庣鏈嶅姟
cd backend
pip install -r requirements.txt
python app.py

# 3. 鍚姩鍓嶇鏈嶅姟锛堟柊缁堢锛?
cd frontend
npm install
npm run dev
```

#### 寰湇鍔℃灦鏋勫惎鍔?
```bash
# 鍚姩鎵€鏈夊井鏈嶅姟
docker-compose up -d

# 绛夊緟1-2鍒嗛挓鏈嶅姟鍚姩瀹屾垚
```

### 馃攳 璁块棶绯荤粺

绯荤粺鍚姩鍚庯紝鍙€氳繃浠ヤ笅鍦板潃璁块棶锛?

| 鏈嶅姟 | URL | 鐢ㄦ埛鍚?瀵嗙爜 |
|------|-----|-------------|
| 鍓嶇搴旂敤 | http://localhost:8080 | - |
| 鍚庣API | http://localhost:5000 | - |
| API缃戝叧 | http://localhost:8000 | - |
| Grafana鐩戞帶 | http://localhost:3000 | admin/password |
| Kafka UI | http://localhost:8090 | - |
| MinIO鎺у埗鍙?| http://localhost:9001 | minioadmin/minioadmin |
| PgAdmin | http://localhost:5050 | admin@admin.com/admin |

## 涓嶅悓鐢ㄦ埛瑙掕壊鎸囧崡

### 馃懆鈥嶐煉?寮€鍙戣€呬娇鐢ㄦ寚鍗?

#### 鐜瑕佹眰
- **Node.js**: 18+ (鍓嶇寮€鍙?
- **Python**: 3.9+ (鍚庣寮€鍙?
- **Docker**: 20.10+ (瀹瑰櫒鍖?
- **Git**: 鐗堟湰鎺у埗

#### 寮€鍙戠幆澧冩惌寤?
```bash
# 1. 鍏嬮殕椤圭洰
git clone https://github.com/your-org/wind-power-forecasting.git

# 2. 鍚姩鍩虹璁炬柦
cd wind-power-forecast
docker-compose -f database/docker-compose.yaml up -d

# 3. 鍚庣寮€鍙戠幆澧?
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py

# 4. 鍓嶇寮€鍙戠幆澧?
cd frontend
npm install
npm run dev
```

#### 浠ｇ爜璋冭瘯鎶€宸?
```bash
# 鍚庣璋冭瘯锛圴S Code锛?
# 瀹夎Python鎵╁睍锛岃缃柇鐐癸紝鎸塅5璋冭瘯

# 鍓嶇璋冭瘯锛堟祻瑙堝櫒锛?
# Chrome DevTools -> Vue.js devtools 鎵╁睍

# API娴嬭瘯锛圥ostman/curl锛?
curl -X GET "http://localhost:5000/api/weather/current"

# 鏁版嵁搴撴煡璇?
docker exec -it kingbase psql -U system -d wind_power
```

#### 寮€鍙戞渶浣冲疄璺?
1. **浠ｇ爜瑙勮寖**: 閬靛惊PEP8锛圥ython锛夊拰ESLint锛圝avaScript锛?
2. **鐗堟湰鎺у埗**: 浣跨敤Git鍒嗘敮绠＄悊锛屽畾鏈熸彁浜や唬鐮?
3. **娴嬭瘯椹卞姩**: 缂栧啓鍗曞厓娴嬭瘯锛岀‘淇濅唬鐮佽川閲?
4. **鏂囨。鏇存柊**: 鍚屾鏇存柊鐩稿叧鏂囨。鍜屾敞閲?

### 馃敡 杩愮淮浜哄憳浣跨敤鎸囧崡

#### 鏃ュ父宸℃娓呭崟
```bash
# 1. 绯荤粺鍋ュ悍妫€鏌?
./scripts/health-check.sh

# 2. 鏈嶅姟鐘舵€佹鏌?
docker ps
docker-compose ps

# 3. 璧勬簮浣跨敤鐩戞帶
docker stats
kubectl top nodes  # Kubernetes鐜

# 4. 鏃ュ織妫€鏌?
docker logs --tail 100 service-name
```

#### 鐩戞帶闈㈡澘浣跨敤
1. **Grafana鐩戞帶** (http://localhost:3000)
   - 鏌ョ湅绯荤粺鎬ц兘鎸囨爣
   - 鐩戞帶棰勬祴绮惧害瓒嬪娍
   - 璁剧疆鑷畾涔夊憡璀﹁鍒?

2. **Kibana鏃ュ織** (http://localhost:5601)
   - 鎼滅储鍜屽垎鏋愮郴缁熸棩蹇?
   - 鍒涘缓鏃ュ織鍙鍖栧浘琛?
   - 璁剧疆鏃ュ織鍛婅

#### 澶囦唤鍜屾仮澶?
```bash
# 鏁版嵁搴撳浠?
./scripts/backup-database.sh

# 閰嶇疆鏂囦欢澶囦唤
./scripts/backup-configs.sh

# 绯荤粺鎭㈠
./scripts/restore-system.sh backup-2024-01-15
```

### 馃懆鈥嶐煉?鏈€缁堢敤鎴蜂娇鐢ㄦ寚鍗?

#### 棣栨浣跨敤姝ラ
1. **璁块棶绯荤粺**: 鎵撳紑娴忚鍣ㄨ闂?http://localhost:8080
2. **涓婁紶鏁版嵁**: 鐐瑰嚮"鏁版嵁绠＄悊"涓婁紶姘旇薄鍜岃繍钀ユ暟鎹?
3. **閫夋嫨妯″瀷**: 鍦?妯″瀷璁粌"椤甸潰閫夋嫨鍚堥€傜殑绠楁硶
4. **寮€濮嬮娴?*: 璁剧疆鍙傛暟鍚庡紑濮嬪姛鐜囬娴?
5. **鏌ョ湅鎶ュ憡**: 鍦?鎶ュ憡涓績"鏌ョ湅鐢熸垚鐨勫垎鏋愭姤鍛?

#### 甯哥敤鎿嶄綔
- **鏁版嵁涓婁紶**: 鏀寔CSV銆丒xcel銆丣SON鏍煎紡
- **妯″瀷閫夋嫨**: LSTM閫傚悎闀挎湡棰勬祴锛孹GBoost閫傚悎鐭湡棰勬祴
- **鍙傛暟璋冩暣**: 鏍规嵁瀹為檯鏁版嵁鐗圭偣璋冩暣妯″瀷鍙傛暟
- **缁撴灉瀵煎嚭**: 棰勬祴缁撴灉鍙鍑轰负PDF銆丒xcel绛夋牸寮?

## 鏍稿績鍔熻兘浣跨敤

### 馃搳 鍔熺巼棰勬祴鍔熻兘

#### 瀹炴椂棰勬祴
```bash
# API鏂瑰紡璋冪敤
curl -X POST "http://localhost:5000/api/predictions/realtime" \
  -H "Content-Type: application/json" \
  -d '{
    "farm_id": "farm_001",
    "horizon_hours": 24,
    "weather_data": {
      "temperature": 15.2,
      "wind_speed": 8.5,
      "wind_direction": 225,
      "pressure": 1013.2
    }
  }'
```

#### 鎵归噺棰勬祴
```python
# Python绀轰緥
import requests

url = "http://localhost:5000/api/predictions/batch"
data = {
    "farm_id": "farm_001",
    "start_time": "2024-01-15T00:00:00Z",
    "end_time": "2024-01-22T00:00:00Z",
    "model_type": "lstm"
}

response = requests.post(url, json=data)
predictions = response.json()
```

#### 棰勬祴绮惧害璇勪及
```bash
# 鏌ョ湅棰勬祴绮惧害缁熻
curl -X GET "http://localhost:5000/api/predictions/accuracy?farm_id=farm_001&days=7"
```

### 馃搱 鏁版嵁绠＄悊鍔熻兘

#### 鏁版嵁涓婁紶锛圵eb鐣岄潰锛?
1. 鐐瑰嚮宸︿晶鑿滃崟"鏁版嵁绠＄悊"
2. 閫夋嫨鏁版嵁绫诲瀷锛堟皵璞℃暟鎹?杩愯惀鏁版嵁锛?
3. 鐐瑰嚮"涓婁紶鏂囦欢"鎸夐挳
4. 閫夋嫨CSV/Excel鏂囦欢
5. 棰勮鏁版嵁骞剁‘璁や笂浼?

#### 鏁版嵁涓婁紶锛圓PI鏂瑰紡锛?
```bash
# 姘旇薄鏁版嵁涓婁紶
curl -X POST "http://localhost:5000/api/data/weather" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@weather_data.csv" \
  -F "station_id=station_001"
```

#### 鏁版嵁璐ㄩ噺妫€鏌?
```bash
# 妫€鏌ユ暟鎹畬鏁存€?
curl -X GET "http://localhost:5000/api/data/quality?farm_id=farm_001&date=2024-01-15"
```

### 馃搵 鎶ュ憡鐢熸垚鍔熻兘

#### 鑷姩鍖栨姤鍛?
```bash
# 鐢熸垚杩愯惀鎶ュ憡
curl -X POST "http://localhost:5000/api/reports/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "operational",
    "farm_id": "farm_001",
    "start_date": "2024-01-01",
    "end_date": "2024-01-15",
    "format": "pdf"
  }'
```

#### 瀹氭椂鎶ュ憡閰嶇疆
```bash
# 璁剧疆姣忔棩鑷姩鎶ュ憡
curl -X POST "http://localhost:5000/api/reports/schedule" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily Operational Report",
    "type": "operational",
    "cron": "0 8 * * *",
    "recipients": ["manager@windpower.com"]
  }'
```

### 馃敂 鐩戞帶鍜屽憡璀﹀姛鑳?

#### 鏌ョ湅绯荤粺鐘舵€?
```bash
# 绯荤粺鍋ュ悍妫€鏌?
curl -X GET "http://localhost:5000/health"

# 璇︾粏绯荤粺鐘舵€?
curl -X GET "http://localhost:5000/api/system/status"
```

#### 璁剧疆鍛婅瑙勫垯
```bash
# 鍒涘缓鍛婅瑙勫垯
curl -X POST "http://localhost:5000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Prediction Error",
    "metric": "prediction_accuracy",
    "threshold": 80,
    "operator": "<",
    "duration": "5m",
    "severity": "warning"
  }'
```

## API鎺ュ彛浣跨敤

### 馃敆 鍩虹淇℃伅

**Base URL**: `http://localhost:5000/api`

**璁よ瘉鏂瑰紡**: JWT Token锛堥儴鍒嗘帴鍙ｉ渶瑕侊級
```bash
# 鑾峰彇Token
curl -X POST "http://localhost:5000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "password"
  }'
```

### 馃摗 涓昏API绔偣

#### 姘旇薄鏁版嵁API
```
GET /api/weather/current          # 褰撳墠姘旇薄鏁版嵁
GET /api/weather/historical       # 鍘嗗彶姘旇薄鏁版嵁
POST /api/weather/data            # 涓婁紶姘旇薄鏁版嵁
GET /api/weather/forecast         # 姘旇薄棰勬姤鏁版嵁
```

#### 鍔熺巼棰勬祴API
```
POST /api/predictions/realtime    # 瀹炴椂棰勬祴
POST /api/predictions/batch       # 鎵归噺棰勬祴
GET /api/predictions/results      # 棰勬祴缁撴灉鏌ヨ
GET /api/predictions/accuracy     # 棰勬祴绮惧害缁熻
```

#### 鎶ュ憡API
```
POST /api/reports/generate        # 鐢熸垚鎶ュ憡
GET /api/reports/list             # 鎶ュ憡鍒楄〃
GET /api/reports/{id}/download    # 涓嬭浇鎶ュ憡
POST /api/reports/schedule        # 瀹氭椂鎶ュ憡
```

#### 绯荤粺绠＄悊API
```
GET /api/system/status            # 绯荤粺鐘舵€?
GET /api/system/metrics           # 绯荤粺鎸囨爣
GET /api/system/logs              # 绯荤粺鏃ュ織
GET /health                       # 鍋ュ悍妫€鏌?
GET /ready                        # 灏辩华妫€鏌?
```

### 馃捇 浠ｇ爜绀轰緥

#### Python绀轰緥
```python
import requests
import json

class WindPowerAPI:
    def __init__(self, base_url="http://localhost:5000/api"):
        self.base_url = base_url
        self.token = None

    def login(self, username, password):
        response = requests.post(f"{self.base_url}/auth/login", json={
            "username": username,
            "password": password
        })
        self.token = response.json()["token"]
        return self.token

    def get_weather_data(self, station_id, date):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = requests.get(
            f"{self.base_url}/weather/historical",
            headers=headers,
            params={"station_id": station_id, "date": date}
        )
        return response.json()

    def create_prediction(self, farm_id, horizon_hours, weather_data):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        data = {
            "farm_id": farm_id,
            "horizon_hours": horizon_hours,
            "weather_data": weather_data
        }
        response = requests.post(
            f"{self.base_url}/predictions/realtime",
            headers=headers,
            json=data
        )
        return response.json()

# 浣跨敤绀轰緥
api = WindPowerAPI()

# 鑾峰彇姘旇薄鏁版嵁
weather_data = api.get_weather_data("station_001", "2024-01-15")
print(f"姘旇薄鏁版嵁: {weather_data}")

# 鍒涘缓鍔熺巼棰勬祴
prediction = api.create_prediction("farm_001", 24, {
    "temperature": 15.2,
    "wind_speed": 8.5,
    "wind_direction": 225,
    "pressure": 1013.2
})
print(f"棰勬祴缁撴灉: {prediction}")
```

#### JavaScript绀轰緥
```javascript
class WindPowerAPI {
    constructor(baseUrl = 'http://localhost:5000/api') {
        this.baseUrl = baseUrl;
        this.token = null;
    }

    async login(username, password) {
        const response = await fetch(`${this.baseUrl}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();
        this.token = data.token;
        return this.token;
    }

    async getWeatherData(stationId, date) {
        const headers = this.token ? { 'Authorization': `Bearer ${this.token}` } : {};
        const response = await fetch(`${this.baseUrl}/weather/historical?station_id=${stationId}&date=${date}`, {
            headers
        });
        return await response.json();
    }

    async createPrediction(farmId, horizonHours, weatherData) {
        const headers = this.token ? { 'Authorization': `Bearer ${this.token}` } : {};
        headers['Content-Type'] = 'application/json';

        const response = await fetch(`${this.baseUrl}/predictions/realtime`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
                farm_id: farmId,
                horizon_hours: horizonHours,
                weather_data: weatherData
            })
        });
        return await response.json();
    }
}

// 浣跨敤绀轰緥
const api = new WindPowerAPI();

// 鑾峰彇姘旇薄鏁版嵁骞跺垱寤洪娴?
async function runPrediction() {
    try {
        const weatherData = await api.getWeatherData('station_001', '2024-01-15');
        console.log('姘旇薄鏁版嵁:', weatherData);

        const prediction = await api.createPrediction('farm_001', 24, {
            temperature: 15.2,
            wind_speed: 8.5,
            wind_direction: 225,
            pressure: 1013.2
        });
        console.log('棰勬祴缁撴灉:', prediction);
    } catch (error) {
        console.error('閿欒:', error);
    }
}

runPrediction();
```

## 閰嶇疆鍜岄儴缃?

### 鈿欙笍 鐜閰嶇疆

#### 鐜鍙橀噺閰嶇疆
```bash
# 鍩虹閰嶇疆
export NODE_ENV=development
export API_BASE_URL=http://localhost:5000
export JWT_SECRET=your-secret-key

# 鏁版嵁搴撻厤缃?
export DB_HOST=localhost
export DB_PORT=54321
export DB_NAME=wind_power
export DB_USER=system
export DB_PASSWORD=yzz0216yh

# Redis閰嶇疆
export REDIS_HOST=localhost
export REDIS_PORT=6379

# 閭欢閰嶇疆
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=your-email@gmail.com
export SMTP_PASS=your-password
```

#### 閰嶇疆鏂囦欢璇存槑
```
wind-power-forecast/
鈹溾攢鈹€ .env                    # 鐜鍙橀噺閰嶇疆
鈹溾攢鈹€ backend/
鈹?  鈹溾攢鈹€ config.py          # 鍚庣閰嶇疆
鈹?  鈹斺攢鈹€ requirements.txt   # Python渚濊禆
鈹溾攢鈹€ frontend/
鈹?  鈹溾攢鈹€ .env               # 鍓嶇鐜閰嶇疆
鈹?  鈹斺攢鈹€ package.json       # Node.js渚濊禆
鈹斺攢鈹€ database/
    鈹斺攢鈹€ docker-compose.yaml # 鏁版嵁搴撻厤缃?
```

### 馃惓 Docker閮ㄧ讲

#### 寮€鍙戠幆澧冮儴缃?
```bash
# 鍚姩鍩虹璁炬柦
docker-compose -f database/docker-compose.yaml up -d

# 鏋勫缓搴旂敤闀滃儚
docker build -t wind-power-app ./backend
docker build -t wind-power-frontend ./frontend

# 鍚姩搴旂敤鏈嶅姟
docker run -d -p 5000:5000 --name wind-power-backend wind-power-app
docker run -d -p 8080:8080 --name wind-power-frontend wind-power-frontend
```

#### 鐢熶骇鐜閮ㄧ讲
```bash
# 浣跨敤鐢熶骇閰嶇疆
docker-compose -f docker-compose.prod.yml up -d

# 鎴栦娇鐢↘ubernetes
kubectl apply -f k8s/
```

### 鈽革笍 Kubernetes閮ㄧ讲

#### 鍩虹閮ㄧ讲
```bash
# 鍒涘缓鍛藉悕绌洪棿
kubectl create namespace wind-power

# 閮ㄧ讲鍩虹璁炬柦
kubectl apply -f k8s/infrastructure/

# 閮ㄧ讲寰湇鍔?
kubectl apply -f k8s/services/

# 閮ㄧ讲鐩戞帶
kubectl apply -f k8s/monitoring/
```

#### Helm閮ㄧ讲锛堟帹鑽愶級
```bash
# 娣诲姞Helm浠撳簱
helm repo add wind-power https://charts.windpower.com

# 瀹夎鍩虹鏈嶅姟
helm install wind-power-infrastructure wind-power/infrastructure

# 瀹夎搴旂敤鏈嶅姟
helm install wind-power-services wind-power/services

# 瀹夎鐩戞帶
helm install wind-power-monitoring wind-power/monitoring
```

## 鐩戞帶鍜岀淮鎶?

### 馃搳 鐩戞帶闈㈡澘浣跨敤

#### Grafana鐩戞帶
1. 璁块棶 http://localhost:3000
2. 浣跨敤 admin/password 鐧诲綍
3. 鏌ョ湅棰勯厤缃殑浠〃鏉匡細
   - **绯荤粺姒傝**: CPU銆佸唴瀛樸€佺鐩樹娇鐢ㄧ巼
   - **搴旂敤鎬ц兘**: 鍝嶅簲鏃堕棿銆侀敊璇巼銆佸悶鍚愰噺
   - **涓氬姟鎸囨爣**: 棰勬祴绮惧害銆佹暟鎹川閲忋€佺敤鎴锋椿璺冨害

#### 鑷畾涔夌洃鎺?
```json
// 鍒涘缓鑷畾涔変华琛ㄦ澘
{
  "dashboard": {
    "title": "椋庡姛鐜囬娴嬬洃鎺?,
    "panels": [
      {
        "title": "棰勬祴绮惧害瓒嬪娍",
        "type": "graph",
        "targets": [
          {
            "expr": "prediction_accuracy_percentage",
            "legendFormat": "棰勬祴绮惧害"
          }
        ]
      },
      {
        "title": "API鍝嶅簲鏃堕棿",
        "type": "graph",
        "targets": [
          {
            "expr": "http_request_duration_seconds",
            "legendFormat": "鍝嶅簲鏃堕棿"
          }
        ]
      }
    ]
  }
}
```

### 馃毃 鍛婅绠＄悊

#### 璁剧疆鍛婅瑙勫垯
```bash
# CPU浣跨敤鐜囧憡璀?
curl -X POST "http://localhost:9090/api/v1/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "high_cpu_usage",
    "expr": "cpu_usage_percent > 85",
    "for": "5m",
    "labels": {
      "severity": "warning"
    },
    "annotations": {
      "summary": "CPU浣跨敤鐜囪繃楂?,
      "description": "CPU浣跨敤鐜囪秴杩?5%锛屾寔缁?鍒嗛挓"
    }
  }'
```

#### 鍛婅閫氱煡閰嶇疆
```bash
# 閭欢閫氱煡
curl -X POST "http://localhost:9093/api/v1/alerts" \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "email-notifications",
    "email_configs": [
      {
        "to": "admin@windpower.com",
        "from": "alerts@windpower.com",
        "smarthost": "smtp.gmail.com:587",
        "auth_username": "alerts@windpower.com",
        "auth_password": "password"
      }
    ]
  }'
```

### 馃敡 鏃ュ父缁存姢

#### 鑷姩缁存姢鑴氭湰
```bash
#!/bin/bash
# daily-maintenance.sh

echo "$(date): 寮€濮嬫棩甯哥淮鎶?

# 1. 娓呯悊杩囨湡鏃ュ織
echo "娓呯悊杩囨湡鏃ュ織..."
find /var/log/wind-power -name "*.log" -mtime +7 -delete

# 2. 鏁版嵁澶囦唤
echo "鎵ц鏁版嵁澶囦唤..."
./scripts/backup-database.sh

# 3. 鍋ュ悍妫€鏌?
echo "绯荤粺鍋ュ悍妫€鏌?.."
./scripts/health-check.sh

# 4. 鎬ц兘鎶ュ憡
echo "鐢熸垚鎬ц兘鎶ュ憡..."
./scripts/generate-performance-report.sh

echo "$(date): 鏃ュ父缁存姢瀹屾垚"
```

#### 鎵嬪姩缁存姢妫€鏌?
```bash
# 鏁版嵁搴撶淮鎶?
docker exec -it postgres psql -U postgres -d wind_power -c "
  -- 妫€鏌ユ暟鎹簱澶у皬
  SELECT pg_size_pretty(pg_database_size('wind_power'));

  -- 妫€鏌ヨ〃缁熻淇℃伅
  SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del
  FROM pg_stat_user_tables
  ORDER BY n_tup_ins DESC;

  -- 鏇存柊缁熻淇℃伅
  ANALYZE;
"

# Redis缁存姢
docker exec -it redis redis-cli info

# 纾佺洏绌洪棿妫€鏌?
df -h
```

## 鏁呴殰鎺掗櫎

### 馃攳 甯歌闂璇婃柇

#### 鏈嶅姟鍚姩澶辫触
```bash
# 妫€鏌ocker鐘舵€?
docker system info
docker ps -a

# 鏌ョ湅瀹瑰櫒鏃ュ織
docker logs container-name

# 妫€鏌ョ鍙ｅ啿绐?
netstat -tulpn | grep :8080
lsof -i :8080
```

#### 鏁版嵁搴撹繛鎺ラ棶棰?
```bash
# 娴嬭瘯鏁版嵁搴撹繛鎺?
docker exec -it postgres psql -U postgres -d wind_power -c "SELECT 1;"

# 妫€鏌ユ暟鎹簱閰嶇疆
docker exec -it backend env | grep DB

# 閲嶇疆鏁版嵁搴?
docker-compose -f database/docker-compose.yaml down
docker-compose -f database/docker-compose.yaml up -d
```

#### 棰勬祴绮惧害寮傚父
```bash
# 妫€鏌ユ暟鎹川閲?
curl -X GET "http://localhost:5000/api/data/quality"

# 妫€鏌ユā鍨嬬姸鎬?
curl -X GET "http://localhost:5000/api/models/status"

# 閲嶆柊璁粌妯″瀷
curl -X POST "http://localhost:5000/api/models/retrain"
```

### 馃毃 绱ф€ユ晠闅滃鐞?

#### 绯荤粺瀹屽叏涓嶅彲鐢?
1. **绔嬪嵆妫€鏌ュ熀纭€璁炬柦**
   ```bash
   docker-compose ps
   docker system df
   ```

2. **閲嶅惎鏍稿績鏈嶅姟**
   ```bash
   docker-compose restart
   ```

3. **妫€鏌ヨ祫婧愪娇鐢?*
   ```bash
   docker stats
   free -h
   df -h
   ```

4. **鏌ョ湅璇︾粏鏃ュ織**
   ```bash
   docker-compose logs --tail 100
   ```

#### 鏁版嵁涓㈠け鎭㈠
1. **妫€鏌ュ浠界姸鎬?*
   ```bash
   ls -la /backups/
   ```

2. **浠庡浠芥仮澶?*
   ```bash
   ./scripts/restore-database.sh backup-latest.sql
   ```

3. **楠岃瘉鏁版嵁瀹屾暣鎬?*
   ```bash
   ./scripts/verify-data-integrity.sh
   ```

### 馃摓 鎶€鏈敮鎸?

#### 鑾峰彇甯姪
1. **鏌ョ湅鏃ュ織鏂囦欢**
   - 搴旂敤鏃ュ織: `/var/log/wind-power/`
   - Docker鏃ュ織: `docker logs service-name`
   - 绯荤粺鏃ュ織: `journalctl -u docker`

2. **鍦ㄧ嚎鏂囨。**
   - 椤圭洰鏂囨。: `PROJECT_DOCUMENTATION.md`
   - 杩愮淮鎵嬪唽: `OPERATIONS_MANUAL.md`
   - API鏂囨。: `http://localhost:5000/api-docs`

3. **绀惧尯鏀寔**
   - GitHub Issues: 鎶ュ憡bug鍜屽姛鑳借姹?
   - 鎶€鏈敮鎸? support@windpower.com
   - 绱ф€ヨ仈绯? +86-xxx-xxxx-xxxx

## 鏈€浣冲疄璺?

### 馃彈锔?鏋舵瀯璁捐鏈€浣冲疄璺?

#### 寰湇鍔″垝鍒嗗師鍒?
1. **鍗曚竴鑱岃矗**: 姣忎釜鏈嶅姟鍙礋璐ｄ竴涓笟鍔￠鍩?
2. **鐙珛閮ㄧ讲**: 鏈嶅姟鍙互鐙珛鏋勫缓銆佹祴璇曞拰閮ㄧ讲
3. **鏁版嵁闅旂**: 姣忎釜鏈嶅姟鎷ユ湁鑷繁鐨勬暟鎹簱
4. **寮傛閫氫俊**: 浣跨敤娑堟伅闃熷垪杩涜鏈嶅姟闂撮€氫俊

#### 鏁版嵁绠＄悊绛栫暐
1. **鏁版嵁鍒嗗眰**
   - 鍘熷鏁版嵁灞? 淇濇寔鏁版嵁鍘熷鐘舵€?
   - 娓呮礂鏁版嵁灞? 缁忚繃璐ㄩ噺妫€鏌ョ殑鏁版嵁
   - 姹囨€绘暟鎹眰: 鑱氬悎鍜岀粺璁℃暟鎹?
   - 搴旂敤鏁版嵁灞? 涓氬姟閫昏緫澶勭悊鍚庣殑鏁版嵁

2. **鏁版嵁鐢熷懡鍛ㄦ湡绠＄悊**
   - 鐑暟鎹? 鏈€杩?澶╋紝蹇€熻闂?
   - 娓╂暟鎹? 7澶?3涓湀锛屾爣鍑嗚闂?
   - 鍐锋暟鎹? 3涓湀浠ヤ笂锛屽綊妗ｅ瓨鍌?

### 馃敡 寮€鍙戞渶浣冲疄璺?

#### 浠ｇ爜璐ㄩ噺
1. **浠ｇ爜瀹℃煡**
   - 寮哄埗浠ｇ爜瀹℃煡娴佺▼
   - 浣跨敤Pull Request宸ヤ綔娴?
   - 鑷姩鍖栦唬鐮佽川閲忔鏌?

2. **娴嬭瘯绛栫暐**
   - 鍗曞厓娴嬭瘯瑕嗙洊鐜?> 80%
   - 闆嗘垚娴嬭瘯瑕嗙洊鏍稿績鍔熻兘
   - 绔埌绔祴璇曡鐩栫敤鎴峰満鏅?

3. **鏂囨。缁存姢**
   - 浠ｇ爜娉ㄩ噴瑕嗙洊鐜?> 30%
   - API鏂囨。鑷姩鐢熸垚
   - 鏋舵瀯鏂囨。鍙婃椂鏇存柊

#### 鎬ц兘浼樺寲
1. **鍓嶇浼樺寲**
   ```javascript
   // 缁勪欢鎳掑姞杞?
   const LazyComponent = () => import('./components/HeavyComponent.vue');

   // 鏁版嵁缂撳瓨
   const cache = new Map();
   const getCachedData = (key, fetchFn) => {
     if (cache.has(key)) return cache.get(key);
     const data = fetchFn();
     cache.set(key, data);
     return data;
   };

   // 铏氭嫙婊氬姩
   import { VirtualScroller } from 'vue-virtual-scroller';
   ```

2. **鍚庣浼樺寲**
   ```python
   # 鏁版嵁搴撴煡璇紭鍖?
   def get_optimized_data():
       return db.session.query(WeatherData)\
           .filter(WeatherData.created_at >= start_date)\
           .filter(WeatherData.station_id == station_id)\
           .order_by(WeatherData.created_at.desc())\
           .limit(100)\
           .all()

   # 缂撳瓨绛栫暐
   from functools import lru_cache

   @lru_cache(maxsize=1000)
   def get_prediction_model(model_type):
       return load_model(f"models/{model_type}.pkl")
   ```

### 馃敀 瀹夊叏鏈€浣冲疄璺?

#### 搴旂敤瀹夊叏
1. **杈撳叆楠岃瘉**
   ```python
   from marshmallow import Schema, fields, validate

   class WeatherDataSchema(Schema):
       temperature = fields.Float(required=True, validate=validate.Range(min=-50, max=60))
       wind_speed = fields.Float(required=True, validate=validate.Range(min=0, max=100))
       wind_direction = fields.Integer(required=True, validate=validate.Range(min=0, max=360))
   ```

2. **SQL娉ㄥ叆闃叉姢**
   ```python
   # 浣跨敤ORM鍙傛暟鍖栨煡璇?
   result = db.session.query(WeatherData).filter(
       WeatherData.station_id == station_id,
       WeatherData.date >= start_date
   ).all()

   # 閬垮厤瀛楃涓叉嫾鎺?
   # 鉂?閿欒鏂瑰紡
   query = f"SELECT * FROM weather WHERE station_id = '{station_id}'"

   # 鉁?姝ｇ‘鏂瑰紡
   query = "SELECT * FROM weather WHERE station_id = %s"
   result = db.session.execute(query, (station_id,))
   ```

3. **XSS闃叉姢**
   ```javascript
   // 杈撳叆杞箟
   function escapeHtml(text) {
     const map = {
       '&': '&amp;',
       '<': '&lt;',
       '>': '&gt;',
       '"': '&quot;',
       "'": '&#039;'
     };
     return text.replace(/[&<>"']/g, m => map[m]);
   }

   // Vue.js鑷姩杞箟
   {{ userInput }}  <!-- 鑷姩杞箟 -->
   <div v-html="userInput"></div>  <!-- 闇€瑕佹墜鍔ㄨ浆涔?-->
   ```

#### 绯荤粺瀹夊叏
1. **缃戠粶瀹夊叏**
   - 浣跨敤HTTPS鍔犲瘑閫氫俊
   - 閰嶇疆闃茬伀澧欒鍒?
   - 瀹炴柦缃戠粶鍒嗘
   - 瀹氭湡瀹夊叏鎵弿

2. **鏁版嵁瀹夊叏**
   - 鏁忔劅鏁版嵁鍔犲瘑瀛樺偍
   - 鏁版嵁浼犺緭鍔犲瘑
   - 瀹氭湡澶囦唤鍜屾祴璇曟仮澶?
   - 瀹炴柦鏁版嵁鑴辨晱

3. **璁块棶鎺у埗**
   - 鍩轰簬瑙掕壊鐨勬潈闄愮鐞?
   - 鏈€灏忔潈闄愬師鍒?
   - 瀹氭湡鏉冮檺瀹℃煡
   - 澶氬洜绱犺璇?

### 馃搳 杩愮淮鏈€浣冲疄璺?

#### 鐩戞帶绛栫暐
1. **澶氬眰鐩戞帶**
   - 鍩虹璁炬柦鐩戞帶锛圕PU銆佸唴瀛樸€佺鐩樸€佺綉缁滐級
   - 搴旂敤鎬ц兘鐩戞帶锛堝搷搴旀椂闂淬€侀敊璇巼銆佸悶鍚愰噺锛?
   - 涓氬姟鎸囨爣鐩戞帶锛堥娴嬬簿搴︺€佹暟鎹川閲忋€佺敤鎴锋椿璺冨害锛?

2. **鍛婅浼樺寲**
   - 鍑忓皯璇姤鍜屾紡鎶?
   - 璁剧疆鍛婅鍗囩骇鏈哄埗
   - 瀹氭湡瀹℃煡鍜岃皟鏁村憡璀﹁鍒?
   - 瀹炴柦鍛婅闈欓粯绛栫暐

#### 瀹归噺瑙勫垝
1. **璧勬簮璇勪及**
   ```bash
   # 瀹归噺璇勪及鑴氭湰
   #!/bin/bash

   # 鏀堕泦褰撳墠璧勬簮浣跨敤鎯呭喌
   CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
   MEM_USAGE=$(free | grep Mem | awk '{print ($3/$2) * 100.0}')
   DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | cut -d'%' -f1)

   # 棰勬祴澧為暱瓒嬪娍
   GROWTH_RATE=0.15  # 15%鏈堝闀跨巼
   MONTHS_AHEAD=6

   PREDICTED_CPU=$(echo "$CPU_USAGE * (1 + $GROWTH_RATE)^$MONTHS_AHEAD" | bc)
   PREDICTED_MEM=$(echo "$MEM_USAGE * (1 + $GROWTH_RATE)^$MONTHS_AHEAD" | bc)

   echo "褰撳墠CPU浣跨敤鐜? ${CPU_USAGE}%"
   echo "棰勬祴6涓湀鍚嶤PU浣跨敤鐜? ${PREDICTED_CPU}%"
   echo "褰撳墠鍐呭瓨浣跨敤鐜? ${MEM_USAGE}%"
   echo "棰勬祴6涓湀鍚庡唴瀛樹娇鐢ㄧ巼: ${PREDICTED_MEM}%"
   ```

2. **寮规€т几缂?*
   ```yaml
   # Kubernetes HPA閰嶇疆
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   metadata:
     name: wind-power-hpa
   spec:
     scaleTargetRef:
       apiVersion: apps/v1
       kind: Deployment
       name: wind-power-app
     minReplicas: 2
     maxReplicas: 10
     metrics:
     - type: Resource
       resource:
         name: cpu
         target:
           type: Utilization
           averageUtilization: 70
     - type: Resource
       resource:
         name: memory
         target:
           type: Utilization
           averageUtilization: 80
   ```

## 甯歌闂

### 鉂?瀹夎鍜屽惎鍔ㄩ棶棰?

#### Q: Docker瀹瑰櫒鍚姩澶辫触鎬庝箞鍔烇紵
**A**:
1. 妫€鏌ocker鏈嶅姟鐘舵€侊細`docker system info`
2. 鏌ョ湅瀹瑰櫒鏃ュ織锛歚docker logs container-name`
3. 妫€鏌ョ鍙ｅ啿绐侊細`netstat -tulpn | grep port-number`
4. 閲嶆柊鏋勫缓闀滃儚锛歚docker-compose build --no-cache`

#### Q: 鏁版嵁搴撹繛鎺ュけ璐ユ€庝箞鍔烇紵
**A**:
1. 妫€鏌ユ暟鎹簱瀹瑰櫒鐘舵€侊細`docker ps | grep postgres`
2. 娴嬭瘯杩炴帴锛歚docker exec -it postgres psql -U postgres`
3. 妫€鏌ヨ繛鎺ュ瓧绗︿覆閰嶇疆
4. 閲嶅惎鏁版嵁搴撴湇鍔★細`docker-compose restart postgres`

#### Q: 鍓嶇鏃犳硶璁块棶鍚庣API鎬庝箞鍔烇紵
**A**:
1. 妫€鏌ュ悗绔湇鍔＄姸鎬侊細`curl http://localhost:5000/health`
2. 妫€鏌ORS閰嶇疆
3. 楠岃瘉API绔偣姝ｇ‘鎬?
4. 鏌ョ湅娴忚鍣ㄦ帶鍒跺彴閿欒淇℃伅

### 鉂?鍔熻兘浣跨敤闂

#### Q: 棰勬祴绮惧害涓嶉珮鎬庝箞鍔烇紵
**A**:
1. 妫€鏌ヨ緭鍏ユ暟鎹川閲?
2. 灏濊瘯涓嶅悓鐨勬満鍣ㄥ涔犳ā鍨?
3. 璋冩暣妯″瀷鍙傛暟
4. 澧炲姞璁粌鏁版嵁閲?
5. 妫€鏌ョ壒寰佸伐绋嬫槸鍚﹀悎鐞?

#### Q: 鎶ュ憡鐢熸垚澶辫触鎬庝箞鍔烇紵
**A**:
1. 妫€鏌ユ暟鎹簮鏄惁鍙敤
2. 楠岃瘉鎶ュ憡妯℃澘閰嶇疆
3. 鏌ョ湅鎶ュ憡鏈嶅姟鏃ュ織
4. 妫€鏌ョ鐩樼┖闂存槸鍚﹀厖瓒?
5. 楠岃瘉閭欢鏈嶅姟閰嶇疆

#### Q: 绯荤粺鍝嶅簲缂撴參鎬庝箞鍔烇紵
**A**:
1. 妫€鏌ョ郴缁熻祫婧愪娇鐢ㄦ儏鍐?
2. 浼樺寲鏁版嵁搴撴煡璇?
3. 鍚敤缂撳瓨鏈哄埗
4. 妫€鏌ョ綉缁滃欢杩?
5. 鑰冭檻澧炲姞鏈嶅姟鍣ㄨ祫婧?

### 鉂?鐩戞帶鍜岀淮鎶ら棶棰?

#### Q: Grafana鏃犳硶鏄剧ず鏁版嵁鎬庝箞鍔烇紵
**A**:
1. 妫€鏌ユ暟鎹簮閰嶇疆
2. 楠岃瘉Prometheus鏄惁姝ｅ父杩愯
3. 妫€鏌ユ寚鏍囧悕绉版槸鍚︽纭?
4. 鏌ョ湅Grafana鏃ュ織
5. 娴嬭瘯鏁版嵁婧愯繛鎺?

#### Q: 鍛婅閫氱煡鏃犳硶鍙戦€佹€庝箞鍔烇紵
**A**:
1. 妫€鏌ラ偖浠舵湇鍔￠厤缃?
2. 楠岃瘉缃戠粶杩炴帴
3. 妫€鏌ュ憡璀﹁鍒欓厤缃?
4. 娴嬭瘯閫氱煡娓犻亾
5. 鏌ョ湅AlertManager鏃ュ織

---

## 馃摓 鎶€鏈敮鎸?

### 鑾峰彇甯姪閫斿緞
1. **鏂囨。鏌ヨ**: 鏌ョ湅鐩稿叧鎿嶄綔鎵嬪唽鍜屾枃妗?
2. **鏃ュ織鍒嗘瀽**: 妫€鏌ュ簲鐢ㄦ棩蹇楀拰绯荤粺鏃ュ織
3. **绀惧尯鏀寔**: 璁块棶鎶€鏈ぞ鍖哄拰璁哄潧
4. **瀹樻柟鏀寔**: 鑱旂郴鎶€鏈敮鎸佸洟闃?

### 鑱旂郴淇℃伅
- **鎶€鏈敮鎸侀偖绠?*: support@windpower.com
- **绱ф€ヨ仈绯荤數璇?*: +86-xxx-xxxx-xxxx
- **鍦ㄧ嚎鏂囨。**: https://docs.windpower.com
- **闂鍙嶉**: https://github.com/your-org/wind-power-forecasting/issues

### 鍙嶉寤鸿
鎴戜滑鎸佺画鏀硅繘浜у搧锛屾杩庢偍鎻愪緵瀹濊吹鐨勬剰瑙佸拰寤鸿锛?
- 鍔熻兘鏀硅繘寤鸿
- 浣跨敤浣撻獙鍙嶉
- 鏂囨。璐ㄩ噺璇勪环
- 鏂板姛鑳介渶姹?

---

**鏂囨。鐗堟湰**: 1.0.0
**鏇存柊鏃ユ湡**: 2024骞?
**缁存姢鍥㈤槦**: 椋庡姛鐜囬娴嬬郴缁熷紑鍙戝洟闃?

*鏈墜鍐屼細瀹氭湡鏇存柊锛岃鍙婃椂鍏虫敞鏈€鏂扮増鏈€?
