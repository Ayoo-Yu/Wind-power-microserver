# 椋庣數鍔熺巼棰勬祴绯荤粺 鈥?鐢熶骇鐜閮ㄧ讲瀹夎鎸囧崡

## 1. 浜や粯鐗╂竻鍗?
| 鏂囦欢 | 璇存槑 |
|------|------|
| `01_database.tar` | 閲戜粨鏁版嵁搴?Docker 闀滃儚 (绾?710MB) |
| `02_prediction_system.tar` | 棰勬祴绯荤粺鍏ㄩ儴闀滃儚 (绾?2.7GB) |
| `deploy/` 鐩綍 | 閮ㄧ讲閰嶇疆鏂囦欢锛坈ompose銆佽剼鏈€佺幆澧冨彉閲忔ā鏉匡級 |

`deploy/` 鐩綍缁撴瀯锛?
```
deploy/
鈹溾攢鈹€ docker-compose.db.yaml      # 鏁版嵁搴撶紪鎺?鈹溾攢鈹€ docker-compose.prod.yaml    # 棰勬祴绯荤粺缂栨帓
鈹溾攢鈹€ deploy.sh                   # 閮ㄧ讲绠＄悊鑴氭湰
鈹溾攢鈹€ .env.example                # 鐜鍙橀噺妯℃澘
鈹斺攢鈹€ INSTALL_GUIDE.md            # 鏈枃浠?```

## 2. 鏈嶅姟鍣ㄨ姹?
| 椤圭洰 | 瑕佹眰 |
|------|------|
| 鎿嶄綔绯荤粺 | CentOS 7+ / 鍗庝负閾舵渤楹掗簾 V10 (x86_64) |
| Docker | >= 20.10锛堝惈 Docker Compose V2锛?|
| 纾佺洏 | 鑷冲皯 20GB 鍙敤绌洪棿 |
| 鍐呭瓨 | 鑷冲皯 8GB |
| 绔彛 | 8080锛堝墠绔級銆?000锛堝悗绔?API锛夈€?4321锛堟暟鎹簱锛夈€?050锛坧gAdmin锛夊紑鏀?|

## 3. 瀹夎姝ラ

### 3.1 涓婁紶鏂囦欢

灏嗕互涓嬫枃浠?鐩綍涓婁紶鍒版湇鍔″櫒鐨勫悓涓€閮ㄧ讲鐩綍锛堝 `/opt/wind-power/`锛夛細

```
/opt/wind-power/
鈹溾攢鈹€ 01_database.tar
鈹溾攢鈹€ 02_prediction_system.tar
鈹斺攢鈹€ deploy/
```

### 3.2 鍔犺浇闀滃儚

```bash
cd /opt/wind-power

# 鍔犺浇鏁版嵁搴撻暅鍍?docker load -i 01_database.tar

# 鍔犺浇棰勬祴绯荤粺闀滃儚锛堝寘鍚?frontend銆乥ackend銆乧elery銆乺edis銆乸gadmin锛?docker load -i 02_prediction_system.tar

# 楠岃瘉闀滃儚鏄惁鍔犺浇鎴愬姛
docker images | grep -E "kingbase|wind-power|redis|pgadmin"
```

棰勬湡杈撳嚭搴斿寘鍚互涓嬮暅鍍忥細

```
kingbase_v009r001c002b0014_single_x86   v1         ...   1.52GB
wind-power-frontend                      v250715_1.0  ...   110MB
wind-power-backend                       v250714_1.0  ...   4.44GB
wind-power-staging-celery-worker                 latest     ...   4.47GB
redis                                    7-alpine   ...   60.7MB
dpage/pgadmin4                          latest     ...   1.14GB
```

### 3.3 閰嶇疆鐜鍙橀噺

```bash
cd /opt/wind-power/deploy

# 浠庢ā鏉垮垱寤?.env 鏂囦欢
cp .env.example .env

# 缂栬緫 .env锛屼慨鏀逛互涓嬮」锛堝繀鏀癸級锛?vi .env
```

`.env` 鍐呭锛?
```bash
# 鏁版嵁搴撳瘑鐮侊紙kingbase 鍜?backend 鍏辩敤锛屽繀椤讳慨鏀癸級
DB_PASSWORD=浣犵殑鏁版嵁搴撳瘑鐮?
# Flask JWT 瀵嗛挜锛堝繀椤讳慨鏀癸紝寤鸿闅忔満鐢熸垚锛?SECRET_KEY=浣犵殑瀵嗛挜瀛楃涓?
# Flower 鐩戞帶闈㈡澘锛堝彲閫夛級
FLOWER_USER=admin
FLOWER_PASSWORD=浣犵殑鐩戞帶闈㈡澘瀵嗙爜
```

> **瀹夊叏鎻愮ず**锛歚SECRET_KEY` 寤鸿浣跨敤 `openssl rand -hex 32` 鐢熸垚闅忔満瀛楃涓层€?
### 3.4 鍒涘缓缃戠粶骞跺惎鍔?
**鏂瑰紡 A锛氫娇鐢ㄩ儴缃茶剼鏈紙鎺ㄨ崘锛?*

```bash
cd /opt/wind-power/deploy
chmod +x deploy.sh

# 棣栨瀹夎锛堝垱寤虹綉缁滃拰鐩綍锛?./deploy.sh install

# 鍚姩鍏ㄩ儴鏈嶅姟
./deploy.sh start
```

**鏂瑰紡 B锛氭墜鍔ㄦ搷浣?*

```bash
cd /opt/wind-power/deploy

# 鍒涘缓 Docker 缃戠粶
docker network create wind-power-staging-network

# 鍒涘缓鏁版嵁鐩綍
mkdir -p kingbase-data && chmod 777 kingbase-data
mkdir -p backend-data/{forecast_models,uploads,forecasts,logs,saved_models,saved_scalers,saved_metrics,data_etext,archives}
mkdir -p redis-data celery-beat-data pgadmin-data
chmod 777 pgadmin-data

# 鍚姩鏁版嵁搴?docker compose -f docker-compose.db.yaml up -d

# 绛夊緟鏁版嵁搴撳氨缁紙绾?10-30 绉掞級
echo "绛夊緟鏁版嵁搴撳惎鍔?.."
sleep 15

# 鍚姩棰勬祴绯荤粺
docker compose -f docker-compose.prod.yaml up -d
```

### 3.5 楠岃瘉鏈嶅姟

```bash
# 鏌ョ湅鎵€鏈夊鍣ㄧ姸鎬?cd /opt/wind-power/deploy
./deploy.sh status

# 鎴栨墜鍔ㄦ煡鐪?docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

棰勬湡鎵€鏈夊鍣ㄧ姸鎬佷负 `Up`锛?
| 瀹瑰櫒鍚?| 绔彛鏄犲皠 |
|--------|---------|
| wind-power-staging-kingbase | 54321:54321 |
| wind-power-staging-redis | 127.0.0.1:6379 |
| wind-power-backend | 5000:5000 |
| wind-power-staging-celery-worker | 鈥?|
| wind-power-staging-celery-beat | 鈥?|
| wind-power-frontend | 8080:80 |
| wind-power-staging-pgadmin | 5050:80 |

璁块棶楠岃瘉锛?
- 鍓嶇鐣岄潰锛歚http://<鏈嶅姟鍣↖P>:8080`
- 鍚庣 API锛歚http://<鏈嶅姟鍣↖P>:5000/health`锛堝簲杩斿洖 `{"status": "healthy"}`锛?- pgAdmin锛歚http://<鏈嶅姟鍣↖P>:5050`锛堣处鍙?admin@admin.com / admin锛?
## 4. 鏁版嵁鎸佷箙鍖?
鎵€鏈夋暟鎹€氳繃 bind mount 瀛樺偍鍦ㄥ涓绘満锛?*瀹瑰櫒鍒犻櫎閲嶅缓涓嶄涪鏁版嵁**锛?
```
deploy/
鈹溾攢鈹€ kingbase-data/          # 鏁版嵁搴撴暟鎹紙鏈€鍏抽敭锛?鈹溾攢鈹€ backend-data/
鈹?  鈹溾攢鈹€ forecast_models/    # 璁粌濂界殑 ML 妯″瀷
鈹?  鈹溾攢鈹€ uploads/            # 涓婁紶鐨?CSV 鏂囦欢
鈹?  鈹溾攢鈹€ forecasts/          # 棰勬祴缁撴灉涓嬭浇
鈹?  鈹溾攢鈹€ logs/               # 搴旂敤鏃ュ織
鈹?  鈹溾攢鈹€ saved_models/       # 妯″瀷瀛樺偍
鈹?  鈹溾攢鈹€ saved_scalers/      # 褰掍竴鍖栧櫒
鈹?  鈹溾攢鈹€ saved_metrics/      # 妯″瀷鎸囨爣
鈹?  鈹溾攢鈹€ data_etext/         # E鏂囨湰绠￠亾閰嶇疆
鈹?  鈹斺攢鈹€ archives/           # 鏁版嵁褰掓。
鈹溾攢鈹€ redis-data/             # Redis AOF 鎸佷箙鍖?鈹溾攢鈹€ celery-beat-data/       # 璋冨害鐘舵€?鈹溾攢鈹€ pgadmin-data/           # pgAdmin 閰嶇疆
鈹溾攢鈹€ datasets/               # 涓湡棰勬祴鏁版嵁闆?鈹溾攢鈹€ models/                 # 涓湡妯″瀷
鈹溾攢鈹€ predict_outputs/        # 涓湡棰勬祴缁撴灉
鈹斺攢鈹€ ...                     # 鍏朵粬棰勬祴绠￠亾鐩綍
```

> **閲嶈**锛氬浠芥椂鍙渶澶囦唤鏁翠釜 `deploy/` 鐩綍鍗冲彲淇濈暀鍏ㄩ儴鏁版嵁銆?
## 5. 鏁版嵁搴撹鍙瘉缁湡锛堟瘡 2 涓湀锛?
閲戜粨鏁版嵁搴撹鍙瘉鍒版湡闇€瑕佸嵏杞介噸瑁呭鍣ㄣ€傜敱浜庝娇鐢?bind mount锛?*鏁版嵁涓嶄細涓㈠け**锛?
```bash
cd /opt/wind-power/deploy

# 1. 鍋滄鏁版嵁搴撳鍣?docker compose -f docker-compose.db.yaml down

# 2. 鍒犻櫎鏃ч暅鍍忥紙淇濈暀 kingbase-data/ 鐩綍涓嶅姩锛?docker rmi kingbase_v009r001c002b0014_single_x86:staging-20260510

# 3. 鍔犺浇鏂拌鍙瘉闀滃儚
docker load -i 鏂扮殑01_database.tar

# 4. 閲嶆柊鍚姩鏁版嵁搴?docker compose -f docker-compose.db.yaml up -d

# 5. 楠岃瘉鏁版嵁搴撳氨缁?docker exec wind-power-staging-kingbase ls /home/kingbase/userdata/data
```

> **娉ㄦ剰**锛氭暣涓繃绋嬩腑 **涓嶈鍒犻櫎 `kingbase-data/` 鐩綍**锛屽惁鍒欐暟鎹細涓㈠け銆?
鏁版嵁搴撻噸鍚悗锛岄娴嬬郴缁熶細鑷姩閲嶈繛锛堝凡瀹炵幇鏂嚎閲嶈繛鏈哄埗锛夈€?
## 6. 鏃ュ父杩愮淮

### 甯哥敤鍛戒护

```bash
cd /opt/wind-power/deploy

./deploy.sh start     # 鍚姩鍏ㄩ儴鏈嶅姟
./deploy.sh stop      # 鍋滄鍏ㄩ儴鏈嶅姟
./deploy.sh restart   # 閲嶅惎鍏ㄩ儴鏈嶅姟
./deploy.sh status    # 鏌ョ湅鏈嶅姟鐘舵€?./deploy.sh logs      # 鏌ョ湅鍏ㄩ儴鏃ュ織
./deploy.sh logs backend  # 鍙湅鍚庣鏃ュ織
./deploy.sh db-only   # 浠呭惎鍔ㄦ暟鎹簱
```

### 鍗曠嫭閲嶅惎鏌愪釜鏈嶅姟

```bash
# 閲嶅惎鍚庣
docker compose -f docker-compose.prod.yaml restart backend

# 閲嶅惎 Celery Worker
docker compose -f docker-compose.prod.yaml restart celery-worker
```

### 鏁版嵁澶囦唤

```bash
# 澶囦唤鏁翠釜閮ㄧ讲鐩綍锛堝惈鏁版嵁锛?tar czf wind-power-backup-$(date +%Y%m%d).tar.gz \
    --exclude='*.log' \
    --exclude='logs/*' \
    /opt/wind-power/deploy/
```

### 绯荤粺鏇存柊

褰撴湁鏂扮増鏈暅鍍忔椂锛?
```bash
# 1. 鍋滄棰勬祴绯荤粺锛堟暟鎹簱涓嶅仠锛?docker compose -f docker-compose.prod.yaml down

# 2. 鍔犺浇鏂伴暅鍍?docker load -i 鏂扮殑02_prediction_system.tar

# 3. 閲嶆柊鍚姩
docker compose -f docker-compose.prod.yaml up -d
```

## 7. 鏁呴殰鎺掓煡

### 瀹瑰櫒鍚姩澶辫触

```bash
# 鏌ョ湅瀹瑰櫒鏃ュ織
docker logs wind-power-backend --tail 50
docker logs wind-power-staging-kingbase --tail 50
```

### 鏁版嵁搴撹繛鎺ュけ璐?
```bash
# 妫€鏌ユ暟鎹簱鏄惁灏辩华
docker exec wind-power-staging-kingbase ls /home/kingbase/userdata/data

# 娴嬭瘯杩炴帴
docker exec wind-power-backend python -c "
from sqlalchemy import create_engine, text
e = create_engine('postgresql://system:浣犵殑瀵嗙爜@kingbase:54321/windpower')
with e.connect() as c:
    print(c.execute(text('SELECT 1')).scalar())
"
```

### 纾佺洏绌洪棿涓嶈冻

```bash
# 鏌ョ湅纾佺洏鍗犵敤
du -sh /opt/wind-power/deploy/*/

# 娓呯悊 Docker 鏃犵敤璧勬簮
docker system prune -f
```
