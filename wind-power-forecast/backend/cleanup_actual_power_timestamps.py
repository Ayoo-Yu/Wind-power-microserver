"""
Clean up actual_power table:
1. Delete rows whose timestamp is NOT on a 15-minute boundary (00/15/30/45 min).
2. Report cleanup results.

Run: cd wind-power-forecast/backend && python cleanup_actual_power_timestamps.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from database_config import engine

# KingBase: EXTRACT returns double precision, no % operator.
# Use MOD(CAST(... AS INTEGER), 15) instead.

_SQL_NOT_ON_BOUNDARY = """
CAST(EXTRACT(MINUTE FROM timestamp) AS INTEGER) NOT IN (0, 15, 30, 45)
"""

SQL_COUNT_OFF_GRID = f"""
SELECT COUNT(*) AS cnt
FROM actual_power
WHERE {_SQL_NOT_ON_BOUNDARY}
   OR EXTRACT(SECOND FROM timestamp) != 0
"""

SQL_SAMPLE_OFF_GRID = f"""
SELECT id, farm_code, timestamp
FROM actual_power
WHERE {_SQL_NOT_ON_BOUNDARY}
   OR EXTRACT(SECOND FROM timestamp) != 0
ORDER BY timestamp DESC
LIMIT 20
"""

SQL_DELETE_OFF_GRID = f"""
DELETE FROM actual_power
WHERE {_SQL_NOT_ON_BOUNDARY}
   OR EXTRACT(SECOND FROM timestamp) != 0
"""

SQL_VERIFY = f"""
SELECT
  CASE
    WHEN {_SQL_NOT_ON_BOUNDARY}
         OR EXTRACT(SECOND FROM timestamp) != 0
    THEN 'off_grid'
    ELSE 'clean'
  END AS status,
  COUNT(*) AS cnt
FROM actual_power
GROUP BY status
ORDER BY status
"""

SQL_TOTAL = "SELECT COUNT(*) AS cnt FROM actual_power"

SQL_TIME_RANGE = """
SELECT MIN(timestamp) AS earliest, MAX(timestamp) AS latest
FROM actual_power
"""

SQL_SAMPLE_CLEAN = """
SELECT farm_code, timestamp
FROM actual_power
ORDER BY timestamp DESC
LIMIT 10
"""


def main():
    print("=== actual_power timestamp cleanup ===\n")

    with engine.begin() as conn:
        total = conn.execute(text(SQL_TOTAL)).scalar()
        print(f"Total rows: {total}")

        time_range = conn.execute(text(SQL_TIME_RANGE)).one()
        print(f"Time range: {time_range[0]} ~ {time_range[1]}")

        off_grid = conn.execute(text(SQL_COUNT_OFF_GRID)).scalar()
        print(f"Off-grid rows: {off_grid}")
        print(f"Clean rows:    {total - off_grid}")

        if off_grid == 0:
            print("\nAll data is already clean. Nothing to do.")
            return

        print(f"\nSample off-grid rows:")
        rows = conn.execute(text(SQL_SAMPLE_OFF_GRID)).fetchall()
        for r in rows:
            print(f"  id={r[0]}  farm={r[1]}  ts={r[2]}")

        print(f"\nDeleting {off_grid} off-grid rows...")
        result = conn.execute(text(SQL_DELETE_OFF_GRID))
        deleted = result.rowcount
        print(f"Deleted: {deleted} rows")

        remaining = conn.execute(text(SQL_TOTAL)).scalar()
        print(f"Remaining rows: {remaining}")

        verify = conn.execute(text(SQL_VERIFY)).fetchall()
        print("\nVerification:")
        for row in verify:
            print(f"  {row[0]}: {row[1]}")

        if len(verify) == 1 and verify[0][0] == 'clean':
            print("\nAll timestamps are now on 15-minute boundaries.")

            print("\nLatest 10 rows after cleanup:")
            samples = conn.execute(text(SQL_SAMPLE_CLEAN)).fetchall()
            for s in samples:
                print(f"  farm={s[0]}  ts={s[1]}")
            print("\nDone!")
        else:
            print("\nWARNING: some off-grid rows remain!")
            sys.exit(1)


if __name__ == '__main__':
    main()
