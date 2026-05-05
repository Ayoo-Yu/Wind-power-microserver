"""One-time script to TRUNCATE all ecmwf_grid_* tables (preserving structure)."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from config import KINGBASE_CONFIG
import psycopg2


def main():
    farm_codes = ["cf", "bnj", "sds", "dplz", "zyx"]

    conn = psycopg2.connect(
        host=KINGBASE_CONFIG["host"],
        port=int(KINGBASE_CONFIG["port"]),
        user=KINGBASE_CONFIG["user"],
        password=KINGBASE_CONFIG["password"],
        database=KINGBASE_CONFIG["database"],
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Find all ecmwf_grid tables (including partitions)
    cur.execute(
        "SELECT tablename FROM pg_tables WHERE tablename LIKE 'ecmwf_grid_%' ORDER BY tablename"
    )
    all_tables = [r[0] for r in cur.fetchall()]
    print(f"Found {len(all_tables)} ecmwf_grid tables/partitions: {all_tables}")

    # TRUNCATE each main table with CASCADE (handles partitions automatically)
    truncated = []
    for code in farm_codes:
        table = f"ecmwf_grid_{code}"
        if table in all_tables:
            cur.execute(f'TRUNCATE TABLE "{table}" CASCADE')
            truncated.append(table)
            print(f"  TRUNCATED: {table}")
        else:
            print(f"  SKIPPED (not found): {table}")

    cur.close()
    conn.close()
    print(f"\nDone. Truncated {len(truncated)} tables: {truncated}")


if __name__ == "__main__":
    main()
