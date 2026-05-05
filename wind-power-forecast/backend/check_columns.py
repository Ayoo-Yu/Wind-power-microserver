"""Quick check: train_pre_short table columns vs CSV columns."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import psycopg2
from config import KINGBASE_CONFIG

conn = psycopg2.connect(
    host=KINGBASE_CONFIG["host"],
    port=int(KINGBASE_CONFIG["port"]),
    user=KINGBASE_CONFIG["user"],
    password=KINGBASE_CONFIG["password"],
    database=KINGBASE_CONFIG["database"],
)
cur = conn.cursor()

# 1. Get DB columns
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'train_pre_short'
    ORDER BY ordinal_position
""")
db_cols = [r[0] for r in cur.fetchall()]
print(f"DB columns count: {len(db_cols)}")
print(f"First 10: {db_cols[:10]}")
print(f"Sample feature cols: {[c for c in db_cols if c.startswith('100u')][:5]}")

# 2. Get CSV columns from a sample file
import csv
csv_path = r"D:\weather_data\csv_short\bainijing\2026-05_short.csv"
with open(csv_path, 'r') as f:
    reader = csv.reader(f)
    csv_headers = next(reader)
print(f"\nCSV columns count: {len(csv_headers)}")
print(f"CSV first 5: {csv_headers[:5]}")
print(f"CSV 100u cols: {[c for c in csv_headers if c.startswith('100u')][:5]}")

# 3. Compare
csv_feature_cols = [c for c in csv_headers if c != 'Timestamp']
missing_in_db = []
for col in csv_feature_cols:
    # DB column names have dots, CSV has dots
    if col not in db_cols:
        missing_in_db.append(col)

print(f"\nCSV feature columns: {len(csv_feature_cols)}")
print(f"Missing in DB: {len(missing_in_db)}")
if missing_in_db:
    print(f"First 5 missing: {missing_in_db[:5]}")

# 4. Check if DB has any 'col_' prefixed columns (SQLAlchemy model style)
col_prefixed = [c for c in db_cols if c.startswith('col_')]
print(f"\nDB 'col_' prefixed columns: {len(col_prefixed)}")
if col_prefixed:
    print(f"Sample: {col_prefixed[:5]}")

conn.close()
