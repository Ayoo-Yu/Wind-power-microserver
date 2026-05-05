"""Test round_to_quarter_hour window logic."""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone, timedelta
from services.scada_worker import round_to_quarter_hour, BEIJING_TZ

BEIJING = BEIJING_TZ
PASS = 0
FAIL = 0


def mk(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 5, 4, hour, minute, second, tzinfo=BEIJING)


def check(label: str, now: datetime, expected_str: str | None):
    global PASS, FAIL
    result = round_to_quarter_hour(now)
    if expected_str is None:
        ok = result is None
    else:
        ok = result is not None and result.strftime('%H:%M') == expected_str

    status = "OK" if ok else "FAIL"
    if not ok:
        FAIL += 1
        detail = f"got={result}"
    else:
        PASS += 1
        detail = f"→ {result.strftime('%H:%M') if result else 'None'}"

    print(f"  [{status}] {label}: now={now.strftime('%H:%M:%S')} {detail}")
    return ok


print("=== Acceptance window tests (WINDOW=2 min before boundary) ===\n")

# -- 18:30 boundary --
print("--- 18:30 boundary ---")
check("18:28:00 (2min before)",  mk(18, 28, 0),  "18:30")
check("18:28:30 (still 2min)",   mk(18, 28, 30), "18:30")
check("18:29:00 (1min before)",  mk(18, 29, 0),  "18:30")
check("18:29:59 (almost there)", mk(18, 29, 59), "18:30")
check("18:30:00 (exact)",        mk(18, 30, 0),  "18:30")
check("18:30:59 (still exact min)", mk(18, 30, 59), "18:30")

# -- Outside window --
print("\n--- Outside window ---")
check("18:27:59 (3min before)",  mk(18, 27, 59), None)
check("18:25:00 (5min before)",  mk(18, 25, 0),  None)
check("18:31:00 (1min after)",   mk(18, 31, 0),  None)
check("18:35:00 (exact but no remainder)", mk(18, 35, 0), None)  # 35%15=5, not 0
check("18:37:00",                mk(18, 37, 0),  None)

# Wait, 18:35 % 15 = 5, not 0. Let me reconsider...
# Actually 35 // 15 = 2, 35 % 15 = 5. So 18:35 is NOT on a boundary.
# The boundaries are 0, 15, 30, 45.

print("\n--- 18:45 boundary ---")
check("18:43:00 (2min before)",  mk(18, 43, 0),  "18:45")
check("18:44:00 (1min before)",  mk(18, 44, 0),  "18:45")
check("18:45:00 (exact)",        mk(18, 45, 0),  "18:45")
check("18:46:00 (1min after)",   mk(18, 46, 0),  None)

print("\n--- 18:00 boundary ---")
check("17:58:00 (2min before)",  mk(17, 58, 0),  "18:00")
check("17:59:00 (1min before)",  mk(17, 59, 0),  "18:00")
check("18:00:00 (exact)",        mk(18, 0, 0),   "18:00")
check("18:01:00 (1min after)",   mk(18, 1, 0),   None)

print("\n--- 00:00 midnight boundary ---")
check("23:58:00 (2min before)",  mk(23, 58, 0),  "00:00")
check("23:59:00 (1min before)",  mk(23, 59, 0),  "00:00")
check("00:00:00 (exact)",        mk(0, 0, 0),    "00:00")
check("00:01:00 (1min after)",   mk(0, 1, 0),    None)

print("\n--- 18:15 boundary ---")
check("18:13:00 (2min before)",  mk(18, 13, 0),  "18:15")
check("18:14:00 (1min before)",  mk(18, 14, 0),  "18:15")
check("18:15:00 (exact)",        mk(18, 15, 0),  "18:15")
check("18:16:00 (1min after)",   mk(18, 16, 0),  None)

print(f"\n{'='*50}")
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL:
    print("TESTS FAILED!")
    sys.exit(1)
else:
    print("All tests passed!")
