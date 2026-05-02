#!/bin/bash
set -e

# 绉婚櫎PM2妫€鏌ワ紝鍥犱负backend瀹瑰櫒涓嶉渶瑕丳M2
# python check_pm2.py

# 鍒涘缓utils鐩綍锛堝鏋滀笉瀛樺湪锛?
mkdir -p /app/backend/utils

# 纭繚瀛愮洰褰曚腑鐨刜_init__.py鏂囦欢瀛樺湪
touch /app/backend/utils/__init__.py

# 鍒涘缓鐢ㄤ簬妫€鏌ユ暟鎹簱杩炴帴鐨勪复鏃禤ython鑴氭湰
cat > check_db.py << EOL
import psycopg2
import os
import sys
import time

# 浠庣幆澧冨彉閲忚幏鍙栨暟鎹簱杩炴帴淇℃伅
host = os.environ.get('DB_HOST', 'kingbase')
port = os.environ.get('DB_PORT', '54321')
user = os.environ.get('DB_USER', 'system')
password = os.environ.get('DB_PASSWORD', '12345678ab')
dbname = os.environ.get('DB_NAME', 'windpower')

try:
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        connect_timeout=3
    )
    conn.close()
    print("鏁版嵁搴撹繛鎺ユ垚鍔?)
    sys.exit(0)
except Exception as e:
    print(f"鏁版嵁搴撹繛鎺ュけ璐? {e}")
    sys.exit(1)
EOL

# 绛夊緟PostgreSQL鍜孧inIO鏈嶅姟鍙敤
echo "绛夊緟鏁版嵁搴撴湇鍔″氨缁?.."
for i in {1..30}; do
  if python check_db.py; then
    echo "鏁版嵁搴撴湇鍔″凡灏辩华"
    break
  fi
  echo "绛夊緟鏁版嵁搴撴湇鍔″惎鍔?.. $i/30"
  sleep 2
done

# 鍒濆鍖栨暟鎹簱鍜岀敤鎴?
echo "鍒濆鍖栨暟鎹簱鍜岀敤鎴?.."
python -m init_users

# 淇绠＄悊鍛樻潈闄?
echo "妫€鏌ュ苟淇绠＄悊鍛樻潈闄?.."
python -m fix_admin_permissions

# 淇鎵€鏈夎鑹叉潈闄?
echo "妫€鏌ュ苟淇鎵€鏈夎鑹叉潈闄?.."
python -m fix_user_permissions

# 浣跨敤鏍囪鏂囦欢鍒ゆ柇鏄惁涓洪娆￠儴缃?
# 纭繚宸ヤ綔鐩綍瀛樺湪
mkdir -p /app/backend/data

# 浣跨敤鐩稿浜庡簲鐢ㄧ殑绋冲畾璺緞
INIT_FLAG_FILE="/app/backend/data/admin_initialized.flag"
if [ ! -f "$INIT_FLAG_FILE" ]; then
    echo "棣栨閮ㄧ讲锛氶噸缃鐞嗗憳瀵嗙爜涓洪粯璁ゅ€?admin123)..."
    python -m reset_admin
    # 鍒涘缓鏍囪鏂囦欢锛岃〃绀哄凡瀹屾垚鍒濆鍖?
    touch "$INIT_FLAG_FILE"
    echo "宸插畬鎴愮鐞嗗憳瀵嗙爜鍒濆鍖?
else
    echo "妫€娴嬪埌宸插垵濮嬪寲鏍囪锛岃烦杩囩鐞嗗憳瀵嗙爜閲嶇疆"
fi

# 鍒涘缓monkey patch棰勫姞杞芥枃浠?
cat > /app/wsgi_app.py << EOL
# 棣栧厛纭繚gevent monkey patching宸插簲鐢?
import gevent.monkey
gevent.monkey.patch_all()

# 浠巃pp.py瀵煎叆Flask搴旂敤瀹炰緥
from app import app as application

# 杩欎釜鏂囦欢浼氳Gunicorn鐩存帴瀵煎叆
print("鉁?WSGI搴旂敤宸叉垚鍔熼鍔犺浇锛実event monkey patching宸插簲鐢?)

# 瀵煎嚭app鍙橀噺鐢ㄤ簬Gunicorn
app = application
EOL

# 璁＄畻worker鏁伴噺锛?2 * CPU鏍稿績鏁? + 1
CORES=$(grep -c ^processor /proc/cpuinfo)
# 涓轰簡娴嬭瘯锛屾垜浠皢worker鏁伴噺璁剧疆涓?锛岄伩鍏嶇郴缁熻祫婧愯繃搴︽秷鑰?
WORKERS=3
echo "绯荤粺妫€娴嬪埌 $CORES 涓狢PU鏍稿績锛屽皢鍚姩 $WORKERS 涓狦unicorn宸ヤ綔杩涚▼"

# 鍚姩搴旂敤
echo "浣跨敤Gunicorn鍚姩搴旂敤..."
exec gunicorn \
  --workers $WORKERS \
  --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
  --worker-connections 2000 \
  --timeout 600 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 200 \
  --log-level info \
  --bind 0.0.0.0:5000 \
  --preload \
  wsgi_app:app 