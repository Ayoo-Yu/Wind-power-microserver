"""Quick check: which farms have training data available."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_session import db_session
from sqlalchemy import text

with db_session() as s:
    farms = ['dplz', 'sds', 'zyx', 'cf', 'bnj']
    print("=== NWP training tables ===")
    for fc in farms:
        for suffix, label in [('short', 'short'), ('middle', 'mid')]:
            tbl = f'train_pre_{suffix}_{fc}'
            try:
                cnt = s.execute(text(f'SELECT COUNT(*) FROM {tbl}')).scalar()
                row = s.execute(text(f'SELECT MIN(timestamp), MAX(timestamp) FROM {tbl}')).fetchone()
                mn = row[0].strftime('%Y-%m-%d') if row[0] else '-'
                mx = row[1].strftime('%Y-%m-%d') if row[1] else '-'
                print(f'  {fc}/{label}: {cnt:>6} rows  {mn} ~ {mx}')
            except Exception as e:
                print(f'  {fc}/{label}: ERROR - {e}')

    print("\n=== Actual power ===")
    for fc in farms:
        try:
            cnt = s.execute(
                text('SELECT COUNT(*) FROM actual_power WHERE farm_code = :fc'),
                {'fc': fc}
            ).scalar()
            row = s.execute(
                text('SELECT MIN(timestamp), MAX(timestamp) FROM actual_power WHERE farm_code = :fc'),
                {'fc': fc}
            ).fetchone()
            mn = row[0].strftime('%Y-%m-%d') if row[0] else '-'
            mx = row[1].strftime('%Y-%m-%d') if row[1] else '-'
            print(f'  {fc}: {cnt:>6} rows  {mn} ~ {mx}')
        except Exception as e:
            print(f'  {fc}: ERROR - {e}')
