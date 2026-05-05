#!/usr/bin/env python3
"""E text file processing pipeline.

Parses wide-format E text (.dat) files containing weather prediction data
for all 5 wind farms, splits by farm and forecast type (supershort/short/middle),
uploads to database tables, and archives processed files.

Usage:
    python etext_pipeline.py                          # process all incoming files
    python etext_pipeline.py --file path/to/file.dat  # process single file
    python etext_pipeline.py --dry-run                 # parse only, skip DB upload
    python etext_pipeline.py --farm bnj --type short   # filter by farm/type
"""

import argparse
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

import psycopg2
import psycopg2.extras

# Add backend/ to sys.path for config import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from config import KINGBASE_CONFIG

# --- Constants ---
FARM_CODES = ["bnj", "cf", "sds", "dplz", "zyx"]

FORECAST_TYPES = {
    "supershort": {"prefix": "train_pre_supershort", "start_line": 24},
    "short": {"prefix": "train_pre_short", "start_line": 24},
    "middle": {"prefix": "train_pre_middle", "start_line": 72},
}

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.environ.get("ETEXT_DATA_DIR", os.path.join(PROJECT_ROOT, "data", "etext"))
INCOMING_DIR = os.environ.get("ETEXT_INCOMING_DIR", os.path.join(DATA_DIR, "incoming"))
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
CSV_DIR = os.path.join(DATA_DIR, "csv")
STATE_FILE = os.path.join(DATA_DIR, ".etext_pipeline_state.json")

UPLOAD_BATCH_SIZE = 500


# --- Logging ---
def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=level, format=fmt, handlers=[logging.StreamHandler(sys.stdout)])
    _ensure_file_handler()


def _ensure_file_handler():
    """Attach a TimedRotatingFileHandler (daily rotation, keep 30 days)."""
    root = logging.getLogger()
    log_path = os.path.join(DATA_DIR, "etext_pipeline.log")
    for h in root.handlers:
        if isinstance(h, logging.handlers.TimedRotatingFileHandler) and getattr(h, 'baseFilename', '') == os.path.abspath(log_path):
            return
    os.makedirs(DATA_DIR, exist_ok=True)
    fh = logging.handlers.TimedRotatingFileHandler(
        log_path, when="midnight", interval=1, backupCount=30, encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root.addHandler(fh)


log = logging.getLogger(__name__)


# --- State Tracking ---
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_files": {}}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


def is_processed(state, filepath):
    name = os.path.basename(filepath)
    try:
        size = os.path.getsize(filepath)
        mtime = os.path.getmtime(filepath)
    except OSError:
        return False
    entry = state["processed_files"].get(name)
    return entry and entry.get("size") == size and entry.get("mtime") == mtime


def mark_processed(state, filepath):
    name = os.path.basename(filepath)
    state["processed_files"][name] = {
        "size": os.path.getsize(filepath),
        "mtime": os.path.getmtime(filepath),
        "processed_at": datetime.now().isoformat(),
    }


# --- E Text Parsing ---
def parse_etext_file(filepath):
    """Parse E text file, return (headers, data_rows).

    headers: list of column name strings
    data_rows: list of lists of string values
    """
    headers = None
    data_rows = []
    metadata = {}

    with open(filepath, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.rstrip("\n\r")
            if not line:
                continue

            # Line 3: metadata tag
            if line_no == 3 and line.startswith("<"):
                match = re.search(r"Date='([^']+)'", line)
                if match:
                    metadata["date"] = match.group(1)

            # Header line
            if line.startswith("@\t"):
                headers = line[2:].split("\t")
                # Remove empty first element if present
                if headers and headers[0] == "":
                    headers.pop(0)
                log.info(f"Parsed header: {len(headers)} columns")
                continue

            # Data line
            if line.startswith("#\t"):
                values = line[2:].split("\t")
                if values and values[0] == "":
                    values.pop(0)
                if headers and len(values) != len(headers):
                    log.warning(f"Row mismatch: {len(values)} values vs {len(headers)} headers, skipping")
                    continue
                data_rows.append(values)

    if headers is None:
        raise ValueError(f"No header line found in {filepath}")
    if not data_rows:
        raise ValueError(f"No data rows found in {filepath}")

    log.info(f"Parsed {len(data_rows)} data rows from {filepath}")
    return headers, data_rows, metadata


# --- Row Selection ---
def select_data_rows(headers, data_rows, start_line):
    """Select data rows starting from file line `start_line` (1-based).

    Data rows start at file line 5, so data index = start_line - 5.
    """
    idx = start_line - 5
    if idx < 0:
        idx = 0
    selected = data_rows[idx:]
    log.info(f"Selected {len(selected)} rows starting from file line {start_line}")
    return headers, selected


# --- Column Filtering ---
def get_table_columns(conn, table_name):
    """Get column names from a DB table (excluding record_id)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s ORDER BY ordinal_position",
        (table_name,),
    )
    cols = [row[0] for row in cur.fetchall() if row[0] != "record_id"]
    cur.close()
    return cols


def filter_columns_for_farm(headers, data_rows, farm_columns):
    """Filter E text data to only include columns matching the farm's DB table.

    Returns (filtered_headers, filtered_data_rows).
    """
    farm_col_set = set(farm_columns)
    # Always keep Timestamp
    indices = []
    filtered_headers = []
    for i, h in enumerate(headers):
        if h == "Timestamp" or h in farm_col_set:
            indices.append(i)
            filtered_headers.append(h)

    if not indices:
        log.warning("No matching columns found for farm")
        return [], []

    filtered_rows = []
    for row in data_rows:
        filtered_rows.append([row[i] for i in indices])

    log.info(f"Filtered to {len(filtered_headers)} columns ({len(indices) - 1} features + Timestamp)")
    return filtered_headers, filtered_rows


# --- CSV Output ---
def write_csv(headers, data_rows, output_path):
    """Write headers and data rows to a CSV file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(",".join(headers) + "\n")
        for row in data_rows:
            f.write(",".join(row) + "\n")
    log.info(f"Wrote CSV: {output_path} ({len(data_rows)} rows)")
    return output_path


def get_csv_path(forecast_type, farm_code, source_date):
    """Build CSV output path: csv/{type}/{farm}/{YYYY-MM}/etext_{date}_{type}_{farm}.csv"""
    if source_date:
        month = source_date[:7]  # YYYY-MM
        date_str = source_date.replace("-", "")
    else:
        now = datetime.now()
        month = now.strftime("%Y-%m")
        date_str = now.strftime("%Y%m%d")

    filename = f"etext_{date_str}_{forecast_type}_{farm_code}.csv"
    return os.path.join(CSV_DIR, forecast_type, farm_code, month, filename)


# --- DB Upload ---
def upload_to_db(conn, headers, data_rows, table_name):
    """Upsert data rows into the specified DB table."""
    if not data_rows:
        log.info(f"No data to upload for {table_name}")
        return {"inserted": 0, "updated": 0, "errors": 0}

    ts_idx = headers.index("Timestamp")
    feature_cols = [h for h in headers if h != "Timestamp"]
    feat_indices = [i for i, h in enumerate(headers) if h != "Timestamp"]

    total_inserted = 0
    total_updated = 0
    total_errors = 0

    cur = conn.cursor()
    try:
        # Process in batches
        for batch_start in range(0, len(data_rows), UPLOAD_BATCH_SIZE):
            batch = data_rows[batch_start:batch_start + UPLOAD_BATCH_SIZE]

            # Parse timestamps
            ts_list = [row[ts_idx] for row in batch]

            # Check existing
            placeholders = ", ".join(["%s"] * len(ts_list))
            cur.execute(
                f'SELECT "Timestamp" FROM "{table_name}" WHERE "Timestamp" IN ({placeholders})',
                ts_list,
            )
            existing_ts = set(str(row[0]) for row in cur.fetchall())

            to_insert = []
            to_update = []

            for row in batch:
                ts = row[ts_idx]
                values = []
                for fi in feat_indices:
                    v = row[fi]
                    try:
                        values.append(float(v) if v and v != "NaN" else None)
                    except (ValueError, TypeError):
                        values.append(None)

                if ts in existing_ts:
                    to_update.append((ts, values))
                else:
                    to_insert.append((ts, values))

            # Bulk insert
            if to_insert:
                cols_str = '"Timestamp", ' + ", ".join(f'"{c}"' for c in feature_cols)
                ph_row = ", ".join(["%s"] * (1 + len(feature_cols)))
                insert_sql = f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({ph_row})'
                rows = [(ts, *vals) for ts, vals in to_insert]
                try:
                    psycopg2.extras.execute_batch(cur, insert_sql, rows)
                    total_inserted += len(to_insert)
                except Exception as e:
                    total_errors += len(to_insert)
                    log.error(f"Batch insert failed for {table_name}: {e}")
                    conn.rollback()
                    break

            # Update existing
            for ts, values in to_update:
                set_parts = []
                set_vals = []
                for i, col in enumerate(feature_cols):
                    if values[i] is not None:
                        set_parts.append(f'"{col}" = %s')
                        set_vals.append(values[i])
                if set_parts:
                    update_sql = f'UPDATE "{table_name}" SET {", ".join(set_parts)} WHERE "Timestamp" = %s'
                    try:
                        cur.execute(update_sql, set_vals + [ts])
                        total_updated += 1
                    except Exception as e:
                        total_errors += 1
                        log.error(f"Update failed for {ts} in {table_name}: {e}")

        conn.commit()
        log.info(f"Upload {table_name}: ins={total_inserted} upd={total_updated} err={total_errors}")
    except Exception as e:
        conn.rollback()
        log.error(f"Upload failed for {table_name}: {e}", exc_info=True)
        total_errors += 1
    finally:
        cur.close()

    return {"inserted": total_inserted, "updated": total_updated, "errors": total_errors}


# --- File Archiving ---
def archive_file(filepath, source_date=None):
    """Move processed E text file to processed/{YYYY-MM}/."""
    if source_date:
        month = source_date[:7]
    else:
        month = datetime.now().strftime("%Y-%m")

    dest_dir = os.path.join(PROCESSED_DIR, month)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(filepath))

    if os.path.exists(dest):
        base, ext = os.path.splitext(dest)
        i = 1
        while os.path.exists(f"{base}_{i}{ext}"):
            i += 1
        dest = f"{base}_{i}{ext}"

    shutil.move(filepath, dest)
    log.info(f"Archived {filepath} -> {dest}")
    return dest


# --- Main Processing ---
def process_file(filepath, conn=None, dry_run=False, farm_filter=None, type_filter=None):
    """Process a single E text file."""
    filepath = os.path.abspath(filepath)
    log.info(f"Processing: {filepath}")

    # Parse
    headers, data_rows, metadata = parse_etext_file(filepath)
    source_date = metadata.get("date")
    log.info(f"Source date: {source_date}, total data rows: {len(data_rows)}")

    results = []
    farms = [f for f in FARM_CODES if (not farm_filter or f == farm_filter)]
    types = [t for t in FORECAST_TYPES if (not type_filter or t == type_filter)]

    # Always connect to DB for column discovery (even in dry-run)
    own_conn = False
    if conn is None:
        conn = psycopg2.connect(
            host=KINGBASE_CONFIG["host"],
            port=int(KINGBASE_CONFIG["port"]),
            user=KINGBASE_CONFIG["user"],
            password=KINGBASE_CONFIG["password"],
            database=KINGBASE_CONFIG["database"],
        )
        own_conn = True

    try:
        # Pre-load farm column sets from DB
        farm_columns = {}
        for farm in farms:
                # Use short table as reference for column names (all types share same columns per farm)
                ref_table = f"train_pre_short_{farm}"
                cols = get_table_columns(conn, ref_table)
                farm_columns[farm] = cols
                log.info(f"Farm {farm}: {len(cols)} columns from {ref_table}")

        for ftype in types:
            config = FORECAST_TYPES[ftype]
            sel_headers, sel_rows = select_data_rows(headers, data_rows, config["start_line"])

            if not sel_rows:
                log.warning(f"No rows for {ftype}, skipping")
                continue

            for farm in farms:
                table_name = f"{config['prefix']}_{farm}"
                log.info(f"--- {table_name} ({len(sel_rows)} rows) ---")

                if dry_run:
                    # Use known coordinate sets for dry-run column estimation
                    cols = farm_columns.get(farm, [])
                    if cols:
                        fh, fr = filter_columns_for_farm(sel_headers, sel_rows, cols)
                        log.info(f"[DRY RUN] Would upload {len(fr)} rows x {len(fh)} cols to {table_name}")
                        # Still write CSV in dry-run
                        csv_path = get_csv_path(ftype, farm, source_date)
                        write_csv(fh, fr, csv_path)
                        results.append({"table": table_name, "rows": len(fr), "cols": len(fh), "dry_run": True})
                    else:
                        log.warning(f"[DRY RUN] No column info for {farm}, skipping CSV")
                    continue

                # Filter columns for this farm
                cols = farm_columns.get(farm, [])
                if not cols:
                    log.warning(f"No columns found for {farm}, skipping")
                    continue

                fh, fr = filter_columns_for_farm(sel_headers, sel_rows, cols)
                if not fh:
                    log.warning(f"No matching columns for {farm} in {ftype}")
                    continue

                # Write CSV
                csv_path = get_csv_path(ftype, farm, source_date)
                write_csv(fh, fr, csv_path)

                # Upload to DB
                upload_result = upload_to_db(conn, fh, fr, table_name)
                results.append({
                    "table": table_name,
                    "csv": csv_path,
                    **upload_result,
                })

    finally:
        if own_conn:
            conn.close()

    # Update state before archiving (file must still exist)
    state = load_state()
    mark_processed(state, filepath)
    save_state(state)

    # Archive
    archive_file(filepath, source_date)

    return results


def run_pipeline(incoming_dir=None, dry_run=False, farm_filter=None, type_filter=None, force=False):
    """Scan incoming directory and process all unprocessed E text files.

    Args:
        force: If True, re-process files even if already tracked as processed.
    """
    incoming = incoming_dir or INCOMING_DIR
    _ensure_file_handler()
    if not os.path.isdir(incoming):
        log.warning(f"Incoming directory does not exist: {incoming}")
        return []

    state = load_state()
    dat_files = sorted(
        f for f in os.listdir(incoming) if f.lower().endswith(".dat")
    )

    if not dat_files:
        log.info("No .dat files found in incoming directory")
        return []

    log.info(f"Found {len(dat_files)} .dat files in {incoming}")

    all_results = []
    for fname in dat_files:
        fpath = os.path.join(incoming, fname)
        if not force and is_processed(state, fpath):
            log.info(f"Skipping already processed: {fname}")
            continue
        try:
            results = process_file(fpath, dry_run=dry_run, farm_filter=farm_filter, type_filter=type_filter)
            all_results.extend(results)
        except Exception as e:
            log.error(f"Failed to process {fname}: {e}", exc_info=True)

    return all_results


def main():
    parser = argparse.ArgumentParser(description="E text file processing pipeline")
    parser.add_argument("--incoming", default=INCOMING_DIR, help="Incoming directory")
    parser.add_argument("--file", default=None, help="Process single file")
    parser.add_argument("--dry-run", action="store_true", help="Parse and split only, skip DB upload")
    parser.add_argument("--farm", default=None, choices=FARM_CODES, help="Process single farm")
    parser.add_argument("--type", default=None, choices=list(FORECAST_TYPES.keys()), help="Process single type")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-process already processed files")
    args = parser.parse_args()

    setup_logging(args.verbose)
    log.info(f"Pipeline started (dry_run={args.dry_run})")

    if args.file:
        results = process_file(args.file, dry_run=args.dry_run, farm_filter=args.farm, type_filter=args.type)
    else:
        results = run_pipeline(args.incoming, dry_run=args.dry_run, farm_filter=args.farm, type_filter=args.type, force=args.force)

    log.info(f"Pipeline finished. {len(results)} table operations.")
    for r in results:
        log.info(f"  {r.get('table', '?')}: ins={r.get('inserted', 0)} upd={r.get('updated', 0)} err={r.get('errors', 0)}")

    return 0 if all(r.get("errors", 0) == 0 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
