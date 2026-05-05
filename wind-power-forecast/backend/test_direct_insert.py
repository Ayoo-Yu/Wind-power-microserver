"""Test direct CSV insert into train_pre_short_bnj (bypassing HTTP)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import psycopg2
from config import KINGBASE_CONFIG
import pandas as pd
import io

TABLE = "train_pre_short_bnj"
CSV_PATH = r"D:\weather_data\csv_short\bainijing\2026-05_short.csv"

conn = psycopg2.connect(
    host=KINGBASE_CONFIG["host"],
    port=int(KINGBASE_CONFIG["port"]),
    user=KINGBASE_CONFIG["user"],
    password=KINGBASE_CONFIG["password"],
    database=KINGBASE_CONFIG["database"],
)
conn.autocommit = True
cur = conn.cursor()

# Read first 5 rows
df = pd.read_csv(CSV_PATH, encoding='utf-8-sig', nrows=5)
ts_col = next(c for c in df.columns if c.strip().lower() == 'timestamp')
if ts_col != 'Timestamp':
    df = df.rename(columns={ts_col: 'Timestamp'})
feature_cols = [c for c in df.columns if c != 'Timestamp']

print(f"CSV columns: {len(feature_cols) + 1} (Timestamp + {len(feature_cols)} features)")
print(f"First Timestamp: {df['Timestamp'].iloc[0]}")

# Check DB table columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position", (TABLE,))
db_cols = set(r[0] for r in cur.fetchall())
print(f"DB table columns: {len(db_cols)}")

# Find matching columns
matching = [c for c in feature_cols if c in db_cols]
missing = [c for c in feature_cols if c not in db_cols]
print(f"Matching: {len(matching)}, Missing: {len(missing)}")

if missing:
    print(f"Sample missing: {missing[:5]}")

# Insert first row using matching columns only
cols_to_insert = ['Timestamp'] + matching
cols_str = ', '.join(f'"{c}"' for c in cols_to_insert)
placeholders = ', '.join(['%s'] * len(cols_to_insert))

row = df.iloc[0]
vals = [row['Timestamp']] + [None if pd.isna(row[c]) else float(row[c]) for c in matching]

sql = f'INSERT INTO "{TABLE}" ({cols_str}) VALUES ({placeholders})'
try:
    cur.execute(sql, vals)
    print(f"\nINSERT SUCCESS! Inserted 1 row into {TABLE}")

    # Verify
    cur.execute(f'SELECT COUNT(*) FROM "{TABLE}"')
    count = cur.fetchone()[0]
    print(f"Total rows in {TABLE}: {count}")

    # Clean up test row
    cur.execute(f'DELETE FROM "{TABLE}" WHERE "Timestamp" = %s', (row['Timestamp'],))
    print("Test row cleaned up.")
except Exception as e:
    print(f"\nINSERT FAILED: {e}")

cur.close()
conn.close()
