import csv
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from database_config import engine
from utils.db_partition_utils import quote_identifier as _q
from db_models.ecmwf_grid_model import ecmwf_grid_table_name

logger = logging.getLogger(__name__)

RETENTION_DAYS = int(os.environ.get("DATA_RETENTION_DAYS", "730"))
ARCHIVE_DIR = os.environ.get(
    "DATA_RETENTION_ARCHIVE_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "archives", "retention")),
)


@dataclass(frozen=True)
class RetentionTable:
    table_name: str
    time_column: str
    retention_days: Optional[int] = None


RETENTION_TABLES = [
    RetentionTable("actual_power", "timestamp"),
    RetentionTable("supershortl_power", "timestamp"),
    RetentionTable("shortl_power", "timestamp"),
    RetentionTable("mid_power", "timestamp"),
    RetentionTable(
        "scada_ingest_records",
        "received_at",
        int(os.environ.get("SCADA_INGEST_RETENTION_DAYS", "30")),
    ),
    RetentionTable(
        "source_observations",
        "event_time",
        int(os.environ.get("SOURCE_OBSERVATION_RETENTION_DAYS", "180")),
    ),
    RetentionTable(
        "ingestion_batches",
        "received_at",
        int(os.environ.get("INGESTION_BATCH_RETENTION_DAYS", "730")),
    ),
    RetentionTable(
        "prediction_input_snapshots",
        "captured_at",
        int(os.environ.get("PREDICTION_LINEAGE_RETENTION_DAYS", "730")),
    ),
    RetentionTable(
        "forecast_output_points",
        "created_at",
        int(os.environ.get("PREDICTION_LINEAGE_RETENTION_DAYS", "730")),
    ),
    RetentionTable("daily_metrics", "date"),
]


def _psycopg2_table_exists(cursor, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL", (table_name,))
    return bool(cursor.fetchone()[0])


def _archive_path(table_name: str, cutoff: datetime, archive_dir: str) -> str:
    folder = os.path.join(archive_dir, table_name)
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(folder, f"{table_name}_before_{cutoff:%Y%m%d}_{stamp}.csv")


def _archive_and_delete_table(cursor, config: RetentionTable, cutoff: datetime, archive_dir: str) -> dict:
    if not _psycopg2_table_exists(cursor, config.table_name):
        return {
            "table": config.table_name,
            "archived_rows": 0,
            "deleted_rows": 0,
            "archive_file": None,
            "skipped": "table_missing",
        }

    cursor.execute(
        f"SELECT COUNT(*) FROM {_q(config.table_name)} WHERE {_q(config.time_column)} < %s",
        (cutoff,),
    )
    row_count = int(cursor.fetchone()[0] or 0)
    if row_count == 0:
        return {
            "table": config.table_name,
            "archived_rows": 0,
            "deleted_rows": 0,
            "archive_file": None,
            "skipped": "no_expired_rows",
        }

    archive_file = _archive_path(config.table_name, cutoff, archive_dir)
    copy_sql = cursor.mogrify(
        (
            f"COPY (SELECT * FROM {_q(config.table_name)} "
            f"WHERE {_q(config.time_column)} < %s "
            f"ORDER BY {_q(config.time_column)}) TO STDOUT WITH CSV HEADER"
        ),
        (cutoff,),
    ).decode("utf-8")

    with open(archive_file, "w", encoding="utf-8", newline="") as handle:
        cursor.copy_expert(copy_sql, handle)

    with open(archive_file, "r", encoding="utf-8", newline="") as handle:
        archived_rows = max(0, sum(1 for _ in csv.reader(handle)) - 1)

    if archived_rows != row_count:
        raise RuntimeError(
            f"archive row count mismatch for {config.table_name}: expected {row_count}, got {archived_rows}"
        )

    cursor.execute(
        f"DELETE FROM {_q(config.table_name)} WHERE {_q(config.time_column)} < %s",
        (cutoff,),
    )
    deleted_rows = int(cursor.rowcount or 0)
    if deleted_rows != archived_rows:
        raise RuntimeError(
            f"delete row count mismatch for {config.table_name}: archived {archived_rows}, deleted {deleted_rows}"
        )

    return {
        "table": config.table_name,
        "archived_rows": archived_rows,
        "deleted_rows": deleted_rows,
        "archive_file": archive_file,
        "skipped": None,
    }


def run_retention_archive(
    retention_days: int = RETENTION_DAYS,
    archive_dir: str = ARCHIVE_DIR,
    now: Optional[datetime] = None,
) -> dict:
    effective_now = now or datetime.now()
    cutoff = effective_now - timedelta(days=retention_days)
    os.makedirs(archive_dir, exist_ok=True)

    connection = engine.raw_connection()
    try:
        cursor = connection.cursor()
        try:
            results: List[dict] = []
            for config in RETENTION_TABLES:
                table_days = config.retention_days or retention_days
                table_cutoff = effective_now - timedelta(days=table_days)
                result = _archive_and_delete_table(
                    cursor, config, table_cutoff, archive_dir
                )
                result["retention_days"] = table_days
                result["cutoff"] = table_cutoff.isoformat(timespec="seconds")
                results.append(result)

            # Per-farm ECMWF grid tables
            cursor.execute("SELECT farm_code FROM wind_farms WHERE is_active = true")
            farm_codes = [row[0] for row in cursor.fetchall()]
            for fc in farm_codes:
                table = ecmwf_grid_table_name(fc)
                ecmwf_config = RetentionTable(table, "forecast_source")
                results.append(_archive_and_delete_table(cursor, ecmwf_config, cutoff, archive_dir))

            connection.commit()
            return {
                "cutoff": cutoff.isoformat(timespec="seconds"),
                "retention_days": retention_days,
                "archive_dir": archive_dir,
                "tables": results,
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()
