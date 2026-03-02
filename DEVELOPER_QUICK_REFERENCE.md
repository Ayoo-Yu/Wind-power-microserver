# 寮€鍙戣€呭揩閫熷弬鑰冩寚鍗?

## 寮€鍙戠幆澧冩惌寤?

### 1. 鍓嶇疆瑕佹眰
- Python 3.8+
- Node.js 14+
- Docker & Docker Compose
- Git

### 2. 蹇€熷惎鍔ㄥ懡浠?
```bash
# 鍏嬮殕椤圭洰
git clone [椤圭洰鍦板潃]
cd wind-power-forecast

# 鍚姩寮€鍙戠幆澧?
docker-compose up -d

# 鎴栬€呭崟鐙惎鍔ㄥ悗绔?
cd wind-power-forecast/backend
pip install -r requirements.txt
python app.py

# 鍚姩鍓嶇寮€鍙戞湇鍔″櫒
cd wind-power-forecast/frontend
npm install
npm run serve
```

### 3. 鍏抽敭鏈嶅姟绔彛
- 鍓嶇寮€鍙戞湇鍔″櫒: http://localhost:8080
- 鍚庣API鏈嶅姟: http://localhost:5000
- PostgreSQL鏁版嵁搴? localhost:5432
- Redis缂撳瓨: localhost:6379
- MinIO瀵硅薄瀛樺偍: http://localhost:9900
- Grafana鐩戞帶: http://localhost:3000
- Prometheus: http://localhost:9090

### 4. 甯哥敤寮€鍙戝懡浠?
```bash
# 鏌ョ湅鏈嶅姟鐘舵€?
docker-compose ps

# 鏌ョ湅鏃ュ織
docker-compose logs -f [service-name]

# 閲嶅惎鏈嶅姟
docker-compose restart [service-name]

# 杩涘叆瀹瑰櫒璋冭瘯
docker-compose exec [service-name] bash

# 鏁版嵁搴撹繛鎺?
docker-compose exec postgres psql -U postgres -d windpower

# 杩愯娴嬭瘯
cd backend && python -m pytest
cd frontend && npm run test
```

### 5. API娴嬭瘯
```bash
# 鍋ュ悍妫€鏌?
curl http://localhost:5000/health

# 鐢ㄦ埛鐧诲綍
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 涓婁紶璁粌鏁版嵁
curl -X POST http://localhost:5000/upload_train_csv \
  -H "Authorization: Bearer [token]" \
  -F "file=@train_data.csv"

# 鍒涘缓棰勬祴浠诲姟
curl -X POST http://localhost:5000/predict \
  -H "Authorization: Bearer [token]" \
  -H "Content-Type: application/json" \
  -d '{"model_id":1,"start_time":"2024-01-16T00:00:00Z"}'
```

### 6. 浠ｇ爜缁撴瀯
```
wind-power-forecast/
鈹溾攢鈹€ backend/                    # Python鍚庣
鈹?  鈹溾攢鈹€ app.py                 # 涓诲簲鐢ㄦ枃浠?
鈹?  鈹溾攢鈹€ config.py              # 閰嶇疆鏂囦欢
鈹?  鈹溾攢鈹€ routes/                # API璺敱
鈹?  鈹溾攢鈹€ services/              # 涓氬姟閫昏緫
鈹?  鈹溾攢鈹€ models/                # 鏁版嵁妯″瀷
鈹?  鈹斺攢鈹€ utils/                 # 宸ュ叿鍑芥暟
鈹溾攢鈹€ frontend/                   # Vue.js鍓嶇
鈹?  鈹溾攢鈹€ src/
鈹?  鈹?  鈹溾攢鈹€ components/        # Vue缁勪欢
鈹?  鈹?  鈹溾攢鈹€ views/             # 椤甸潰瑙嗗浘
鈹?  鈹?  鈹溾攢鈹€ services/          # API鏈嶅姟
鈹?  鈹?  鈹溾攢鈹€ store/             # 鐘舵€佺鐞?
鈹?  鈹?  鈹斺攢鈹€ utils/             # 宸ュ叿鍑芥暟
鈹?  鈹斺攢鈹€ public/                # 闈欐€佽祫婧?
鈹?  鈹溾攢鈹€ docker-compose.yml     # 鏈嶅姟缂栨帓
鈹?  鈹溾攢鈹€ services/              # 鍚勪釜寰湇鍔?
鈹?  鈹斺攢鈹€ configs/               # 閰嶇疆鏂囦欢
鈹斺攢鈹€ monitoring/                 # 鐩戞帶绯荤粺
    鈹溾攢鈹€ prometheus/            # 鎸囨爣鏀堕泦
    鈹溾攢鈹€ grafana/               # 鍙鍖?
    鈹斺攢鈹€ alertmanager/          # 鍛婅绠＄悊
```

### 7. 寮€鍙戣皟璇曟妧宸?

#### 鍚庣璋冭瘯
```python
# 浣跨敤pdb璋冭瘯
import pdb; pdb.set_trace()

# 鏃ュ織璋冭瘯
import logging
logger = logging.getLogger(__name__)
logger.info(f"Debug info: {variable}")

# 鎬ц兘鍒嗘瀽
import cProfile
profiler = cProfile.Profile()
profiler.enable()
# ... 浠ｇ爜 ...
profiler.disable()
profiler.print_stats()
```

#### 鍓嶇璋冭瘯
```javascript
// Vue缁勪欢璋冭瘯
console.log('Component data:', this.data)
console.table(this.predictions)

// API璋冪敤璋冭瘯
const response = await api.getPredictions()
console.log('API Response:', response)
debugger; // 鏂偣璋冭瘯

// 鎬ц兘鐩戞帶
console.time('prediction')
// ... 浠ｇ爜 ...
console.timeEnd('prediction')
```

### 8. 鏁版嵁搴撴搷浣?
```sql
-- 甯哥敤鏌ヨ
-- 鏌ョ湅鏈€杩戠殑棰勬祴缁撴灉
SELECT * FROM power_predictions
ORDER BY prediction_time DESC
LIMIT 10;

-- 缁熻棰勬祴绮惧害
SELECT
    AVG(ABS(predicted_power - actual_power)) as mae,
    SQRT(AVG(POWER(predicted_power - actual_power, 2))) as rmse
FROM prediction_results
WHERE DATE(created_at) = CURRENT_DATE;

-- 鏌ョ湅璁粌浠诲姟鐘舵€?
SELECT * FROM training_tasks
ORDER BY created_at DESC
LIMIT 5;
```

### 9. 鐜閰嶇疆
```bash
# 鍚庣鐜鍙橀噺 (.env)
FLASK_ENV=development
FLASK_DEBUG=True
DB_HOST=localhost
DB_PORT=5432
DB_NAME=windpower
JWT_SECRET_KEY=your-secret-key

# 鍓嶇鐜鍙橀噺 (.env.development)
VUE_APP_API_BASE_URL=http://localhost:5000
VUE_APP_WS_URL=ws://localhost:5000
VUE_APP_TITLE=椋庡姛鐜囬娴嬬郴缁?寮€鍙戠幆澧?
```

### 10. 甯歌闂蹇€熻В鍐?

#### 绔彛琚崰鐢?
```bash
# 鏌ユ壘鍗犵敤杩涚▼
lsof -i :5000
# 鎴?
netstat -tlnp | grep 5000

# 缁堟杩涚▼
kill -9 [PID]
```

#### 渚濊禆瀹夎澶辫触
```bash
# 娓呯悊缂撳瓨
pip cache purge
npm cache clean --force

# 閲嶆柊瀹夎
pip install -r requirements.txt --no-cache-dir
npm install --registry https://registry.npmmirror.com
```

#### 鏁版嵁搴撹繛鎺ュけ璐?
```bash
# 妫€鏌ostgreSQL鐘舵€?
docker-compose exec postgres pg_isready

# 閲嶇疆鏁版嵁搴?
docker-compose down
docker volume rm windpower_postgres_data
docker-compose up -d
```

---
**寮€鍙戠幆澧冨揩閫熸鏌ユ竻鍗?*:
- [ ] Docker鏈嶅姟姝ｅ父杩愯
- [ ] 绔彛鏈鍗犵敤 (5000, 8080, 5432, 6379)
- [ ] 鐜鍙橀噺閰嶇疆姝ｇ‘
- [ ] 渚濊禆鍖呭畨瑁呭畬鎴?
- [ ] 鏁版嵁搴撳垵濮嬪寲鎴愬姛
- [ ] API鏈嶅姟鍝嶅簲姝ｅ父
- [ ] 鍓嶇椤甸潰鍔犺浇姝ｅ父

> Deprecation Notice (M1): Manual model training and manual predict endpoints are decommissioned from active product flow.
> Prefer /api/v1/autopredict/* and farm-scoped data APIs.

