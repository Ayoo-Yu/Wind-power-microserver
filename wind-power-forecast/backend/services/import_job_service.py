import csv
import json
import os
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from io import StringIO
from typing import Dict, Optional

import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text

from database_config import engine
from db_session import db_session
from db_models.ecmwf_grid_model import (
    ecmwf_grid_table_name,
    ensure_ecmwf_grid_table,
    ensure_ecmwf_grid_month_partitions,
    META_COLUMNS,
    WIND_DERIVE_RULES,
)
from db_models.report_config import WindFarm
from utils.db_partition_utils import parse_timestamp


ACTUAL_POWER_CHUNK_SIZE = int(os.environ.get("ACTUAL_POWER_IMPORT_CHUNK_SIZE", "50000"))
ECMWF_GRID_CHUNK_SIZE = int(os.environ.get("ECMWF_GRID_IMPORT_CHUNK_SIZE", "50000"))
MAX_IMPORT_WORKERS = int(os.environ.get("DATA_IMPORT_WORKERS", "2"))
IMPORT_JOB_STATE_DIR = os.environ.get(
    "IMPORT_JOB_STATE_DIR",
    os.path.join(tempfile.gettempdir(), "wind_power_import_jobs"),
)


@dataclass
class ImportJob:
    job_id: str
    kind: str
    status: str = "queued"
    file_name: str = ""
    farm_code: str = ""
    strategy: str = "fill_only"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    total_rows: Optional[int] = None
    processed_rows: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    ingested_count: int = 0
    error_count: int = 0
    message: str = ""
    errors: list = field(default_factory=list)

    @property
    def progress(self) -> int:
        if self.status == "done":
            return 100
        if not self.total_rows:
            return 0
        return min(99, int((self.processed_rows / self.total_rows) * 100))

    def to_dict(self):
        data = asdict(self)
        data["progress"] = self.progress
        return data


class ImportJobStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._jobs: Dict[str, ImportJob] = {}
        self._executor = ThreadPoolExecutor(max_workers=MAX_IMPORT_WORKERS)
        os.makedirs(IMPORT_JOB_STATE_DIR, exist_ok=True)
        self._recover_orphaned_jobs()

    def create_actual_power_job(self, file_storage, farm_code: str, strategy: str) -> ImportJob:
        farm_code = str(farm_code or "").strip()
        if not farm_code:
            raise ValueError("farm_code is required")

        job_id = uuid.uuid4().hex
        suffix = os.path.splitext(file_storage.filename or "")[1] or ".csv"
        fd, temp_path = tempfile.mkstemp(prefix=f"actual_power_{job_id}_", suffix=suffix)
        os.close(fd)
        file_storage.save(temp_path)

        job = ImportJob(
            job_id=job_id,
            kind="actual_power",
            file_name=file_storage.filename or "",
            farm_code=farm_code,
            strategy=strategy,
            message="waiting for worker",
        )
        with self._lock:
            self._jobs[job_id] = job
            self._write_job_file(job)

        self._executor.submit(self._run_actual_power_job, job_id, temp_path)
        return job

    def create_ecmwf_grid_job(self, file_storage, farm_code: str) -> ImportJob:
        job_id = uuid.uuid4().hex
        suffix = os.path.splitext(file_storage.filename or "")[1] or ".csv"
        fd, temp_path = tempfile.mkstemp(prefix=f"ecmwf_grid_{job_id}_", suffix=suffix)
        os.close(fd)
        file_storage.save(temp_path)

        job = ImportJob(
            job_id=job_id,
            kind="ecmwf_grid",
            file_name=file_storage.filename or "",
            farm_code=farm_code,
            message="waiting for worker",
        )
        with self._lock:
            self._jobs[job_id] = job
            self._write_job_file(job)

        self._executor.submit(self._run_ecmwf_grid_job, job_id, temp_path)
        return job

    def get_job(self, job_id: str) -> Optional[ImportJob]:
        file_job = self._read_job_file(job_id)
        if file_job:
            with self._lock:
                self._jobs[job_id] = file_job
            return file_job

        with self._lock:
            return self._jobs.get(job_id)

    def _update(self, job_id: str, **kwargs):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                job = self._read_job_file(job_id)
                if not job:
                    return
                self._jobs[job_id] = job
            for key, value in kwargs.items():
                setattr(job, key, value)
            self._write_job_file(job)

    def _append_error(self, job_id: str, message: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                job = self._read_job_file(job_id)
                if not job:
                    return
                self._jobs[job_id] = job
            job.error_count += 1
            if len(job.errors) < 50:
                job.errors.append(message)
            self._write_job_file(job)

    def _job_file_path(self, job_id: str) -> str:
        return os.path.join(IMPORT_JOB_STATE_DIR, f"{job_id}.json")

    def _write_job_file(self, job: ImportJob):
        path = self._job_file_path(job.job_id)
        tmp_path = f"{path}.{os.getpid()}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(job.to_dict(), handle, ensure_ascii=False)
        os.replace(tmp_path, path)

    def _read_job_file(self, job_id: str) -> Optional[ImportJob]:
        path = self._job_file_path(job_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            data.pop("progress", None)
            return ImportJob(**data)
        except Exception:
            return None

    def _recover_orphaned_jobs(self):
        """Mark orphaned jobs (queued/running) as failed after a process restart."""
        if not os.path.isdir(IMPORT_JOB_STATE_DIR):
            return
        for filename in os.listdir(IMPORT_JOB_STATE_DIR):
            if not filename.endswith(".json"):
                continue
            job_id = filename[:-5]
            job = self._read_job_file(job_id)
            if job and job.status in ("queued", "running"):
                job.status = "failed"
                job.message = "server restarted during import"
                job.finished_at = datetime.now().isoformat(timespec="seconds")
                with self._lock:
                    self._jobs[job_id] = job
                self._write_job_file(job)

    def _run_actual_power_job(self, job_id: str, temp_path: str):
        job = self.get_job(job_id)
        if not job:
            return

        self._update(
            job_id,
            status="running",
            started_at=datetime.now().isoformat(timespec="seconds"),
            message="validating input",
        )

        try:
            _validate_farm_code(job.farm_code)
            _validate_actual_power_csv(temp_path)
            total_rows = _count_csv_data_rows(temp_path)
            self._update(job_id, total_rows=total_rows, message="importing rows")

            totals = import_actual_power_csv(
                temp_path=temp_path,
                farm_code=job.farm_code,
                strategy=job.strategy,
                progress_callback=lambda processed, inserted, updated, skipped, errors: self._update(
                    job_id,
                    processed_rows=processed,
                    inserted_count=inserted,
                    updated_count=updated,
                    skipped_count=skipped,
                    error_count=errors,
                    message="importing rows",
                ),
                error_callback=lambda message: self._append_error(job_id, message),
            )

            self._update(
                job_id,
                status="done",
                processed_rows=totals["processed_rows"],
                inserted_count=totals["inserted_count"],
                updated_count=totals["updated_count"],
                skipped_count=totals["skipped_count"],
                error_count=totals["error_count"],
                finished_at=datetime.now().isoformat(timespec="seconds"),
                message="completed",
            )
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                finished_at=datetime.now().isoformat(timespec="seconds"),
                message=str(exc),
            )
            self._append_error(job_id, str(exc))
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    def _run_ecmwf_grid_job(self, job_id: str, temp_path: str):
        job = self.get_job(job_id)
        if not job:
            return

        self._update(
            job_id,
            status="running",
            started_at=datetime.now().isoformat(timespec="seconds"),
            message="validating input",
        )

        try:
            _validate_farm_code(job.farm_code)
            total_rows = _count_csv_data_rows(temp_path)
            self._update(job_id, total_rows=total_rows, message="importing rows")

            totals = import_ecmwf_grid_csv(
                temp_path=temp_path,
                farm_code=job.farm_code,
                progress_callback=lambda processed, ingested, errors: self._update(
                    job_id,
                    processed_rows=processed,
                    ingested_count=ingested,
                    error_count=errors,
                    message="importing rows",
                ),
                error_callback=lambda message: self._append_error(job_id, message),
            )

            self._update(
                job_id,
                status="done",
                processed_rows=totals["processed_rows"],
                ingested_count=totals["ingested_count"],
                error_count=totals["error_count"],
                finished_at=datetime.now().isoformat(timespec="seconds"),
                message="completed",
            )
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                finished_at=datetime.now().isoformat(timespec="seconds"),
                message=str(exc),
            )
            self._append_error(job_id, str(exc))
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _validate_farm_code(farm_code: str):
    with db_session() as session:
        farm = session.query(WindFarm).filter(WindFarm.farm_code == farm_code).first()
        if not farm:
            raise ValueError(f"farm_code '{farm_code}' does not exist")


def _count_csv_data_rows(path: str) -> int:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.reader(handle)
        next(reader, None)  # skip header
        return sum(1 for _ in reader)


def _read_csv_columns(path: str):
    return [
        str(column).strip().lower()
        for column in pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns
    ]


def _validate_actual_power_csv(path: str):
    columns = set(_read_csv_columns(path))
    missing = {"timestamp", "wp_true"} - columns
    if missing:
        raise ValueError(
            "actual_power CSV missing columns: "
            f"{', '.join(sorted(missing))}. "
            "Please upload ECMWF grid files from the weather data tab."
        )


def _ensure_actual_power_indexes(connection):
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_actual_power_farm_timestamp_import "
            "ON actual_power (farm_code, timestamp)"
        )
    )


def _prepare_actual_power_chunk(chunk_df: pd.DataFrame, farm_code: str):
    lower_to_original = {str(col).strip().lower(): col for col in chunk_df.columns}
    if "timestamp" not in lower_to_original:
        raise ValueError("CSV must contain timestamp column")
    if "wp_true" not in lower_to_original:
        raise ValueError("CSV must contain wp_true column")

    prepared = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                chunk_df[lower_to_original["timestamp"]],
                errors="coerce",
            ),
            "farm_code": farm_code,
            "wp_true": pd.to_numeric(
                chunk_df[lower_to_original["wp_true"]],
                errors="coerce",
            ),
        }
    )
    invalid_count = int(prepared["timestamp"].isna().sum())
    prepared = prepared.dropna(subset=["timestamp"])
    prepared = prepared.drop_duplicates(subset=["farm_code", "timestamp"], keep="last")
    return prepared, invalid_count


def _copy_dataframe_to_staging(connection, prepared: pd.DataFrame):
    if prepared.empty:
        return

    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for row in prepared.itertuples(index=False):
        writer.writerow(
            [
                row.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                row.farm_code,
                "" if pd.isna(row.wp_true) else row.wp_true,
            ]
        )
    buffer.seek(0)

    cursor = connection.connection.cursor()
    try:
        if hasattr(cursor, "copy_expert"):
            cursor.copy_expert(
                "COPY actual_power_import_staging (timestamp, farm_code, wp_true) FROM STDIN WITH CSV",
                buffer,
            )
        else:
            buffer.seek(0)
            rows = [
                tuple(None if value == "" else value for value in row)
                for row in csv.reader(buffer)
            ]
            execute_values(
                cursor,
                "INSERT INTO actual_power_import_staging (timestamp, farm_code, wp_true) VALUES %s",
                rows,
                page_size=10000,
            )
    finally:
        cursor.close()


def _prepare_ecmwf_grid_chunk(chunk_df: pd.DataFrame):
    required = {"forecast_source", "forecast_time", "latitude", "longitude"}
    missing = required - set(chunk_df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {', '.join(sorted(missing))}")

    feature_cols = [column for column in chunk_df.columns if column not in META_COLUMNS]
    for column in feature_cols:
        chunk_df[column] = pd.to_numeric(chunk_df[column], errors="coerce")

    for u_key, v_key, ws_key in WIND_DERIVE_RULES:
        if u_key in chunk_df.columns and v_key in chunk_df.columns:
            chunk_df[ws_key] = (chunk_df[u_key] ** 2 + chunk_df[v_key] ** 2) ** 0.5
            chunk_df[ws_key] = chunk_df[ws_key].round(6)
            if ws_key not in feature_cols:
                feature_cols.append(ws_key)

    chunk_df["forecast_source"] = chunk_df["forecast_source"].apply(parse_timestamp)
    chunk_df["forecast_time"] = chunk_df["forecast_time"].apply(parse_timestamp)
    chunk_df["latitude"] = pd.to_numeric(chunk_df["latitude"], errors="coerce")
    chunk_df["longitude"] = pd.to_numeric(chunk_df["longitude"], errors="coerce")

    before = len(chunk_df)
    chunk_df = chunk_df.dropna(subset=["forecast_source", "forecast_time", "latitude", "longitude"])
    invalid_count = before - len(chunk_df)

    records = []
    data_columns = ["forecast_source", "forecast_time", "latitude", "longitude"] + feature_cols
    for row_dict in chunk_df[data_columns].to_dict(orient="records"):
        features = {
            column: float(row_dict[column])
            for column in feature_cols
            if column in row_dict and pd.notna(row_dict[column])
        }
        records.append(
            {
                "forecast_source": row_dict["forecast_source"],
                "forecast_time": row_dict["forecast_time"],
                "latitude": float(row_dict["latitude"]),
                "longitude": float(row_dict["longitude"]),
                "features": json.dumps(features, ensure_ascii=False),
            }
        )

    return records, invalid_count


def _copy_ecmwf_records_to_staging(connection, records):
    if not records:
        return

    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for record in records:
        writer.writerow(
            [
                record["forecast_source"].strftime("%Y-%m-%d %H:%M:%S"),
                record["forecast_time"].strftime("%Y-%m-%d %H:%M:%S"),
                record["latitude"],
                record["longitude"],
                record["features"],
            ]
        )
    buffer.seek(0)

    cursor = connection.connection.cursor()
    try:
        if hasattr(cursor, "copy_expert"):
            cursor.copy_expert(
                "COPY ecmwf_grid_import_staging "
                "(forecast_source, forecast_time, latitude, longitude, features) "
                "FROM STDIN WITH CSV",
                buffer,
            )
        else:
            buffer.seek(0)
            rows = list(csv.reader(buffer))
            execute_values(
                cursor,
                "INSERT INTO ecmwf_grid_import_staging "
                "(forecast_source, forecast_time, latitude, longitude, features) VALUES %s",
                rows,
                page_size=10000,
            )
    finally:
        cursor.close()


def import_ecmwf_grid_csv(temp_path: str, farm_code: str, progress_callback=None, error_callback=None):
    totals = {
        "processed_rows": 0,
        "ingested_count": 0,
        "error_count": 0,
    }

    table = ecmwf_grid_table_name(farm_code)

    chunk_iterator = pd.read_csv(
        temp_path,
        chunksize=ECMWF_GRID_CHUNK_SIZE,
        encoding="utf-8-sig",
        dtype={"forecast_source": str, "forecast_time": str},
        iterator=True,
    )

    for chunk_number, chunk_df in enumerate(chunk_iterator, start=1):
        raw_rows = len(chunk_df)
        totals["processed_rows"] += raw_rows

        try:
            records, invalid_count = _prepare_ecmwf_grid_chunk(chunk_df)
        except Exception as exc:
            totals["error_count"] += raw_rows
            if error_callback:
                error_callback(f"chunk {chunk_number}: {exc}")
            continue

        totals["error_count"] += invalid_count
        if invalid_count and error_callback:
            error_callback(f"chunk {chunk_number}: {invalid_count} rows have invalid coordinates or timestamps")

        if records:
            with engine.begin() as connection:
                ensure_ecmwf_grid_table(connection, farm_code)
                ensure_ecmwf_grid_month_partitions(
                    connection,
                    farm_code,
                    [record["forecast_source"] for record in records],
                )
                connection.execute(
                    text(
                        "CREATE TEMP TABLE ecmwf_grid_import_staging ("
                        "forecast_source TIMESTAMP NOT NULL, "
                        "forecast_time TIMESTAMP NOT NULL, "
                        "latitude DOUBLE PRECISION NOT NULL, "
                        "longitude DOUBLE PRECISION NOT NULL, "
                        "features TEXT NOT NULL"
                        ") ON COMMIT DROP"
                    )
                )
                _copy_ecmwf_records_to_staging(connection, records)
                result = connection.execute(
                    text(
                        f"INSERT INTO {table} "
                        f"(forecast_source, forecast_time, latitude, longitude, features) "
                        f"SELECT forecast_source, forecast_time, latitude, longitude, CAST(features AS jsonb) "
                        f"FROM ("
                        f"  SELECT DISTINCT ON (forecast_source, forecast_time, latitude, longitude) "
                        f"    forecast_source, forecast_time, latitude, longitude, features "
                        f"  FROM ecmwf_grid_import_staging "
                        f") deduped "
                        f"ON CONFLICT (forecast_source, forecast_time, latitude, longitude) "
                        f"DO UPDATE SET features = "
                        f"COALESCE({table}.features, '{{}}'::jsonb) || EXCLUDED.features"
                    )
                )
                totals["ingested_count"] += max(0, result.rowcount or 0)

        if progress_callback:
            progress_callback(
                totals["processed_rows"],
                totals["ingested_count"],
                totals["error_count"],
            )

    return totals


def import_actual_power_csv(temp_path: str, farm_code: str, strategy: str, progress_callback=None, error_callback=None):
    if strategy not in ("fill_only", "overwrite"):
        raise ValueError("strategy must be fill_only or overwrite")
    _validate_actual_power_csv(temp_path)

    totals = {
        "processed_rows": 0,
        "inserted_count": 0,
        "updated_count": 0,
        "skipped_count": 0,
        "error_count": 0,
    }

    chunk_iterator = pd.read_csv(temp_path, chunksize=ACTUAL_POWER_CHUNK_SIZE, iterator=True)

    with engine.begin() as connection:
        _ensure_actual_power_indexes(connection)

    for chunk_number, chunk_df in enumerate(chunk_iterator, start=1):
        raw_rows = len(chunk_df)
        totals["processed_rows"] += raw_rows

        try:
            prepared, invalid_count = _prepare_actual_power_chunk(chunk_df, farm_code)
        except Exception as exc:
            totals["error_count"] += raw_rows
            if error_callback:
                error_callback(f"chunk {chunk_number}: {exc}")
            continue

        totals["error_count"] += invalid_count
        if invalid_count and error_callback:
            error_callback(f"chunk {chunk_number}: {invalid_count} rows have invalid timestamp")

        valid_rows = len(prepared)
        updated = 0
        inserted = 0

        if valid_rows:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TEMP TABLE actual_power_import_staging ("
                        "timestamp TIMESTAMP NOT NULL, "
                        "farm_code VARCHAR(50) NOT NULL, "
                        "wp_true DOUBLE PRECISION"
                        ") ON COMMIT DROP"
                    )
                )
                _copy_dataframe_to_staging(connection, prepared)

                if strategy == "overwrite":
                    existing_result = connection.execute(
                        text(
                            "SELECT COUNT(*) FROM actual_power_import_staging AS staging "
                            "JOIN actual_power AS target "
                            "ON target.farm_code = staging.farm_code "
                            "AND target.timestamp = staging.timestamp"
                        )
                    )
                    existing_before_merge = int(existing_result.scalar() or 0)
                    merge_result = connection.execute(
                        text(
                            "INSERT INTO actual_power (timestamp, farm_code, wp_true, created_at) "
                            "SELECT staging.timestamp, staging.farm_code, staging.wp_true, NOW() "
                            "FROM actual_power_import_staging AS staging "
                            "ON CONFLICT (farm_code, timestamp) "
                            "DO UPDATE SET wp_true = EXCLUDED.wp_true"
                        )
                    )
                    affected = max(0, merge_result.rowcount or 0)
                    updated = min(affected, existing_before_merge)
                    inserted = max(0, affected - updated)
                    totals["updated_count"] += updated
                    totals["inserted_count"] += inserted
                else:
                    insert_result = connection.execute(
                        text(
                            "INSERT INTO actual_power (timestamp, farm_code, wp_true, created_at) "
                            "SELECT staging.timestamp, staging.farm_code, staging.wp_true, NOW() "
                            "FROM actual_power_import_staging AS staging "
                            "ON CONFLICT (farm_code, timestamp) DO NOTHING"
                        )
                    )
                    inserted = max(0, insert_result.rowcount or 0)
                    totals["inserted_count"] += inserted

        skipped = max(0, valid_rows - inserted - updated)
        totals["skipped_count"] += skipped

        if progress_callback:
            progress_callback(
                totals["processed_rows"],
                totals["inserted_count"],
                totals["updated_count"],
                totals["skipped_count"],
                totals["error_count"],
            )

    return totals


import_job_store = ImportJobStore()
