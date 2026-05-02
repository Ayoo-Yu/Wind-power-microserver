import argparse
import json
import os
import sys


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.data_retention_service import ARCHIVE_DIR, RETENTION_DAYS, run_retention_archive


def main():
    parser = argparse.ArgumentParser(
        description="Archive rows older than the retention window to CSV, then delete them."
    )
    parser.add_argument("--days", type=int, default=RETENTION_DAYS)
    parser.add_argument("--archive-dir", default=ARCHIVE_DIR)
    args = parser.parse_args()

    result = run_retention_archive(
        retention_days=args.days,
        archive_dir=os.path.abspath(args.archive_dir),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
