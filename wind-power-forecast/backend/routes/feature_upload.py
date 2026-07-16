"""Feature CSV upload route — DELETE overlapping range + bulk INSERT."""

import re

import pandas as pd
from flask import Blueprint, request, jsonify, current_app
import io
import psycopg2
import psycopg2.extras

from config import KINGBASE_CONFIG
from utils.authorization import permission_required

feature_upload_bp = Blueprint('feature_upload', __name__)

CHUNK_SIZE = 2000

_TABLE_RE = re.compile(r'^train_pre_(?:supershort|short|middle)(?:_[a-z]+)?$')


def _is_valid_table_name(name):
    """Allow per-farm tables like train_pre_short_bnj and legacy full tables."""
    return bool(_TABLE_RE.match(name))


@feature_upload_bp.route('/api/upload_feature_csv', methods=['POST'])
@permission_required('upload_files')
def upload_feature_csv():
    """Upload CSV to a per-farm feature table.

    Strategy: read all rows first, find timestamp range,
    DELETE that range in one shot, then bulk INSERT everything.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    table_name = request.form.get('table_name', '').strip()
    farm_code = request.form.get('farm_code', '').strip()

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not table_name or not _is_valid_table_name(table_name):
        return jsonify({"error": f"Invalid table_name '{table_name}'. Must be train_pre_short_{{farm}} or train_pre_middle_{{farm}}"}), 400

    if not farm_code:
        return jsonify({"error": "Missing required 'farm_code'."}), 400

    if not file.filename.lower().endswith('.csv'):
        return jsonify({"error": "Only CSV allowed."}), 400

    total_inserted = 0
    total_deleted = 0
    total_errors = 0
    all_errors = []
    conn = None

    try:
        conn = psycopg2.connect(
            host=KINGBASE_CONFIG["host"],
            port=int(KINGBASE_CONFIG["port"]),
            user=KINGBASE_CONFIG["user"],
            password=KINGBASE_CONFIG["password"],
            database=KINGBASE_CONFIG["database"],
        )
        cur = conn.cursor()

        # --- Pass 1: read CSV, parse timestamps, collect clean rows ---
        all_rows = []
        feature_cols = None
        chunk_idx = 0

        chunk_iterator = pd.read_csv(
            io.TextIOWrapper(file.stream, encoding='utf-8-sig'),
            chunksize=CHUNK_SIZE,
            iterator=True,
        )

        for chunk_df in chunk_iterator:
            chunk_idx += 1

            if feature_cols is None:
                ts_col = next((c for c in chunk_df.columns if c.strip().lower() == 'timestamp'), None)
                if ts_col is None:
                    return jsonify({"error": "CSV must contain a 'Timestamp' column."}), 400
                if ts_col != 'Timestamp':
                    chunk_df = chunk_df.rename(columns={ts_col: 'Timestamp'})
                feature_cols = [c for c in chunk_df.columns if c != 'Timestamp']

            timestamps = pd.to_datetime(chunk_df['Timestamp'], errors='coerce')
            valid_mask = timestamps.notna()
            if not valid_mask.all():
                bad_count = int((~valid_mask).sum())
                total_errors += bad_count
                all_errors.append(f"Chunk {chunk_idx}: {bad_count} rows with invalid Timestamp skipped")

            for idx in chunk_df[valid_mask].index:
                row = chunk_df.loc[idx]
                ts = timestamps[idx]
                values = []
                for col in feature_cols:
                    val = row.get(col)
                    if pd.isna(val) or val == '':
                        values.append(None)
                    else:
                        try:
                            values.append(float(val))
                        except (ValueError, TypeError):
                            values.append(None)
                all_rows.append(tuple([ts] + values))

        if not all_rows:
            return jsonify({"message": "No valid rows in CSV.", "inserted_count": 0, "deleted_count": 0})

        # --- Delete overlapping range ---
        ts_values = [r[0] for r in all_rows]
        ts_min = min(ts_values)
        ts_max = max(ts_values)
        delete_sql = f'DELETE FROM "{table_name}" WHERE "Timestamp" >= %s AND "Timestamp" <= %s'
        cur.execute(delete_sql, [ts_min, ts_max])
        total_deleted = cur.rowcount
        current_app.logger.info(
            f"Deleted {total_deleted} existing rows from {table_name} "
            f"in range [{ts_min}, {ts_max}]"
        )

        # --- Pass 2: bulk INSERT all rows ---
        cols_str = '"Timestamp", ' + ', '.join(f'"{c}"' for c in feature_cols)
        placeholders_row = ', '.join(['%s'] * (1 + len(feature_cols)))
        insert_sql = f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders_row})'

        for i in range(0, len(all_rows), CHUNK_SIZE):
            batch = all_rows[i:i + CHUNK_SIZE]
            try:
                psycopg2.extras.execute_batch(cur, insert_sql, batch)
                total_inserted += len(batch)
            except Exception as e:
                total_errors += len(batch)
                all_errors.append(f"Insert batch failed at row {i}: {str(e)[:200]}")
                conn.rollback()
                return jsonify({
                    "error": "Insert failed, transaction rolled back.",
                    "deleted_count": 0,
                    "inserted_count": 0,
                    "error_count": total_errors,
                    "errors": all_errors[:50],
                }), 500

        conn.commit()
        current_app.logger.info(
            f"Commit OK: {table_name} del={total_deleted} ins={total_inserted}"
        )

    except pd.errors.EmptyDataError:
        return jsonify({"error": "CSV file is empty."}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        current_app.logger.error(f"Upload failed for {table_name}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

    status_code = 200 if total_errors == 0 else 207
    result = {
        "message": f"Processed {table_name}",
        "deleted_count": total_deleted,
        "inserted_count": total_inserted,
        "updated_count": total_deleted,  # backward compat: old "updated" now means "overwritten"
    }
    if total_errors > 0:
        result["error_count"] = total_errors
        result["errors"] = all_errors[:50]

    return jsonify(result), status_code
