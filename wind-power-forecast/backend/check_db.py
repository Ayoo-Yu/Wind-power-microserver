import psycopg2
import os
import sys
import time

# 从环境变量获取数据库连接信息
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
    print("数据库连接成功")
    sys.exit(0)
except Exception as e:
    print(f"数据库连接失败: {e}")
    sys.exit(1)
