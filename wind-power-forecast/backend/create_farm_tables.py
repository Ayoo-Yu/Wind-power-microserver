"""Analyze CSV columns for each farm and create per-farm tables."""
import sys, os, csv
sys.path.insert(0, os.path.dirname(__file__))

import psycopg2
from config import KINGBASE_CONFIG

# Farm config: directory name -> farm_code
FARM_DIRS = {
    "bainijing": "bnj",
    "cangfang": "cf",
    "shidongshan": "sds",
    "doupoliangzi": "dplz",
    "zhuyuanxi": "zyx",
}

BASE_DIR = r"D:\weather_data\csv_short"

def get_farm_columns(farm_dir):
    """Get sorted list of feature columns from the latest CSV in farm dir."""
    files = sorted([f for f in os.listdir(farm_dir) if f.endswith('.csv')])
    if not files:
        return []
    filepath = os.path.join(farm_dir, files[-1])  # latest file
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader)
    # Remove Timestamp, keep only feature columns
    features = [h for h in headers if h.lower().strip() != 'timestamp']
    return features

def create_farm_table_sql(table_name, feature_cols):
    """Generate CREATE TABLE SQL for a per-farm table."""
    lines = []
    lines.append(f'CREATE TABLE IF NOT EXISTS "{table_name}" (')
    lines.append('  "record_id" BIGSERIAL PRIMARY KEY,')
    lines.append('  "Timestamp" TIMESTAMP NOT NULL')
    for col in feature_cols:
        safe_col = col.replace('"', '""')
        lines.append(f'  ,"{safe_col}" DOUBLE PRECISION')
    lines.append(')')
    return '\n'.join(lines)

conn = psycopg2.connect(
    host=KINGBASE_CONFIG["host"],
    port=int(KINGBASE_CONFIG["port"]),
    user=KINGBASE_CONFIG["user"],
    password=KINGBASE_CONFIG["password"],
    database=KINGBASE_CONFIG["database"],
)
conn.autocommit = True
cur = conn.cursor()

for farm_dir_name, farm_code in FARM_DIRS.items():
    farm_dir = os.path.join(BASE_DIR, farm_dir_name)
    if not os.path.isdir(farm_dir):
        print(f"SKIP {farm_dir_name}: directory not found")
        continue

    features = get_farm_columns(farm_dir)
    print(f"\n{'='*60}")
    print(f"Farm: {farm_dir_name} ({farm_code})")
    print(f"Feature columns: {len(features)}")
    print(f"Sample: {features[:3]} ... {features[-3:]}")

    for prefix in ["train_pre_short", "train_pre_middle"]:
        table_name = f"{prefix}_{farm_code}"

        # Check if table already exists
        cur.execute("SELECT to_regclass(%s)", (table_name,))
        if cur.fetchone()[0]:
            print(f"  {table_name}: already exists, skipping")
            continue

        sql = create_farm_table_sql(table_name, features)
        print(f"  Creating {table_name} ({len(features)} feature columns)...")
        cur.execute(sql)

        # Create indexes
        cur.execute(f'CREATE INDEX IF NOT EXISTS "ix_{table_name}_timestamp" ON "{table_name}" ("Timestamp")')
        print(f"  {table_name}: created with index")

cur.close()
conn.close()
print("\nDone!")
