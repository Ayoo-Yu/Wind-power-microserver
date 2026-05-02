import argparse
import json
import os
import sys


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.partition_maintenance_service import PARTITION_MONTHS_AHEAD, ensure_future_partitions


def main():
    parser = argparse.ArgumentParser(
        description="Create future monthly partitions and drain default partitions."
    )
    parser.add_argument("--months-ahead", type=int, default=PARTITION_MONTHS_AHEAD)
    args = parser.parse_args()

    result = ensure_future_partitions(months_ahead=args.months_ahead)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
