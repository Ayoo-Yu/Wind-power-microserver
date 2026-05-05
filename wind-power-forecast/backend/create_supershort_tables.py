"""Create train_pre_supershort_{farm} tables for all 5 farms."""
import sys, os, csv
sys.path.insert(0, os.path.dirname(__file__))

import psycopg2
from config import KINGBASE_CONFIG

FARM_DIRS = {
    "bainijing": "bnj",
    "cangfang": "cf",
    "shidongshan": "sds",
    "doupoliangzi": "dplz",
    "zhuyuanxi": "zyx",
}
BASE_DIR = r"D:\weather_data\csv_short"

conn = psycopg2.connect(
    host=KINGBASE_CONFIG["host"], port=int(KINGBASE_CONFIG["port"]),
    user=KINGBASE_CONFIG["user"], password=KINGBASE_CONFIG["password"],
    database=KINGBASE_CONFIG["database"],
)
conn.autocommit = True
cur = conn.cursor()

for farm_dir_name, farm_code in FARM_DIRS.items():
    farm_dir = os.path.join(BASE_DIR, farm_dir_name)
    files = sorted(f for f in os.listdir(farm_dir) if f.endswith('.csv'))
    with open(os.path.join(farm_dir, files[-1]), 'r', encoding='utf-8-sig') as f:
        features = [h for h in next(csv.reader(f)) if h.strip().lower() != 'timestamp']

    table_name = f"train_pre_supershort_{farm_code}"
    cur.execute("SELECT to_regclass(%s)", (table_name,))
    if cur.fetchone()[0]:
        print(f"  {table_name}: already exists")
        continue

    cols = ',\n  '.join([f'"{c.replace(chr(34), chr(34)+chr(34))}" DOUBLE PRECISION' for c in features])
    sql = f'CREATE TABLE "{table_name}" (\n  "record_id" BIGSERIAL PRIMARY KEY,\n  "Timestamp" TIMESTAMP NOT NULL,\n  {cols}\n)'
    cur.execute(sql)
    cur.execute(f'CREATE INDEX "ix_{table_name}_timestamp" ON "{table_name}" ("Timestamp")')
    print(f"  Created {table_name} ({len(features)} features)")

cur.close()
conn.close()
print("Done")
