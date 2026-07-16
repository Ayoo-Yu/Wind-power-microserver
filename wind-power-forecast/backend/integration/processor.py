"""将可靠接入箱中的 NWP 数据包处理为可供预测查询的业务数据。"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy.exc import DBAPIError, OperationalError

from db_models.data_lineage import IngestionBatch
from db_session import db_session
from services.import_job_service import import_ecmwf_grid_csv

from .contracts import ContractValidationError, IntegrationManifest, load_manifest
from .ingress import ingest_directory_once
from .spool import DurableSpool, PackageConflictError


LOGGER = logging.getLogger(__name__)
BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


@dataclass(frozen=True)
class ProcessingResult:
    status: str
    message_id: str | None = None
    accepted_count: int = 0
    rejected_count: int = 0
    error: str | None = None


def _local_naive_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("数据包时间必须包含时区偏移")
    return parsed.astimezone(BEIJING_TZ).replace(tzinfo=None)


class BusinessPackageProcessor:
    """从接入箱原子抢占数据包，并完成幂等业务入库。"""

    def __init__(
        self,
        spool_dir: str | Path,
        *,
        session_context: Callable = db_session,
        nwp_importer: Callable = import_ecmwf_grid_csv,
        retry_base_seconds: float = 5.0,
        retry_max_seconds: float = 300.0,
        nwp_enabled: bool | None = None,
    ) -> None:
        self.spool = DurableSpool(spool_dir)
        self.session_context = session_context
        self.nwp_importer = nwp_importer
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds
        self.nwp_enabled = (
            nwp_enabled
            if nwp_enabled is not None
            else os.environ.get("NWP_INGESTION_ENABLED", "false").lower() == "true"
        )

    def _start_batch(self, manifest: IntegrationManifest) -> tuple[int, bool]:
        now = datetime.now()
        with self.session_context() as session:
            batch = session.query(IngestionBatch).filter(
                IngestionBatch.message_id == manifest.message_id
            ).first()
            if batch is not None and batch.status == "completed":
                return batch.id, True
            if batch is None:
                batch = IngestionBatch(
                    message_id=manifest.message_id,
                    source_type=manifest.data_type,
                    source_id=manifest.source,
                    farm_code=manifest.farm_code,
                    schema_version=manifest.schema_version,
                    event_time=_local_naive_timestamp(manifest.event_time),
                    received_at=now,
                    status="processing",
                    quality_status="unknown",
                    record_count=manifest.record_count,
                    accepted_count=0,
                    rejected_count=0,
                    payload_sha256=manifest.payload_sha256,
                    payload_filename=manifest.payload_filename,
                    metadata_json={
                        "quality": manifest.quality,
                        "metadata": manifest.metadata,
                        "sequence": manifest.sequence,
                    },
                )
                session.add(batch)
            batch.started_at = now
            batch.status = "processing"
            batch.error_message = None
            session.flush()
            return batch.id, False

    def _finish_batch(
        self,
        batch_id: int,
        *,
        accepted_count: int,
        rejected_count: int,
        quality_status: str,
    ) -> None:
        with self.session_context() as session:
            batch = session.query(IngestionBatch).filter(
                IngestionBatch.id == batch_id
            ).one()
            batch.status = "completed"
            batch.quality_status = quality_status
            batch.accepted_count = accepted_count
            batch.rejected_count = rejected_count
            batch.completed_at = datetime.now()
            batch.error_message = None

    def _mark_batch_error(self, batch_id: int | None, error: str, status: str) -> None:
        if batch_id is None:
            return
        with self.session_context() as session:
            batch = session.query(IngestionBatch).filter(
                IngestionBatch.id == batch_id
            ).first()
            if batch is not None:
                batch.status = status
                batch.quality_status = "bad"
                batch.error_message = error
                if status == "quarantined":
                    batch.completed_at = datetime.now()

    def _process_nwp(self, manifest: IntegrationManifest, payload_path: Path) -> dict:
        if payload_path.suffix.lower() != ".csv":
            raise ValueError("当前 NWP 业务适配器只接受 UTF-8 CSV 文件")
        totals = self.nwp_importer(str(payload_path), manifest.farm_code)
        processed = int(totals.get("processed_rows", 0))
        accepted = int(totals.get("ingested_count", 0))
        rejected = int(totals.get("error_count", 0))
        if processed <= 0 or accepted <= 0:
            raise ValueError("NWP 数据包没有产生可用业务记录")
        if manifest.record_count is not None and processed != manifest.record_count:
            rejected += abs(int(manifest.record_count) - processed)
        return {
            "processed_count": processed,
            "accepted_count": accepted,
            "rejected_count": rejected,
        }

    def run_once(self) -> ProcessingResult:
        claimed = self.spool.claim()
        if claimed is None:
            return ProcessingResult(status="idle")

        message_id = claimed.message_id
        batch_id: int | None = None
        try:
            manifest = load_manifest(claimed.path / "manifest.json")
            payload_path = claimed.path / manifest.payload_filename
            manifest.validate_payload(payload_path.read_bytes())
            batch_id, duplicate = self._start_batch(manifest)
            if duplicate:
                self.spool.complete(message_id)
                return ProcessingResult(status="duplicate", message_id=message_id)
            if manifest.data_type != "nwp":
                raise ValueError(f"业务处理器尚未配置 {manifest.data_type} 适配器")
            if not self.nwp_enabled:
                raise RuntimeError("NWP 业务接入当前未启用，数据包保留等待配置启用")

            totals = self._process_nwp(manifest, payload_path)
            quality_status = "good" if totals["rejected_count"] == 0 else "degraded"
            self._finish_batch(
                batch_id,
                accepted_count=totals["accepted_count"],
                rejected_count=totals["rejected_count"],
                quality_status=quality_status,
            )
            self.spool.complete(message_id)
            return ProcessingResult(
                status="processed",
                message_id=message_id,
                accepted_count=totals["accepted_count"],
                rejected_count=totals["rejected_count"],
            )
        except (OperationalError, DBAPIError, RuntimeError, OSError) as exc:
            error = str(exc)
            self._mark_batch_error(batch_id, error, "retry")
            self.spool.retry(
                message_id,
                error,
                base_delay_seconds=self.retry_base_seconds,
                max_delay_seconds=self.retry_max_seconds,
            )
            return ProcessingResult(status="retry", message_id=message_id, error=error)
        except (ValueError, ContractValidationError, PackageConflictError) as exc:
            error = str(exc)
            self._mark_batch_error(batch_id, error, "quarantined")
            self.spool.fail(message_id, error)
            return ProcessingResult(status="quarantined", message_id=message_id, error=error)

    def run_until_idle(self, limit: int = 100) -> list[ProcessingResult]:
        results: list[ProcessingResult] = []
        for _ in range(max(1, limit)):
            result = self.run_once()
            if result.status == "idle":
                break
            results.append(result)
        return results


def _farm_codes(value: str) -> list[str]:
    codes = [item.strip() for item in value.split(",") if item.strip()]
    if not codes:
        raise argparse.ArgumentTypeError("至少配置一个场站编码")
    return codes


def _positive_seconds(value: str) -> float:
    seconds = float(value)
    if seconds <= 0:
        raise argparse.ArgumentTypeError("秒数必须大于零")
    return seconds


def _recover_stale_processing(
    processor: BusinessPackageProcessor,
    *,
    older_than_seconds: float,
) -> list[str]:
    recovered = processor.spool.recover_processing(
        older_than_seconds=older_than_seconds
    )
    if recovered:
        LOGGER.warning(
            "已回收 %s 个超时处理中数据包: %s",
            len(recovered),
            ", ".join(recovered),
        )
    return recovered


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="风电系统业务数据包处理器")
    parser.add_argument("--spool", required=True)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument(
        "--processing-timeout-seconds",
        type=_positive_seconds,
        default=300.0,
        help="处理中数据包超过该时长后回收到接入箱",
    )
    parser.add_argument(
        "--recovery-interval-seconds",
        type=_positive_seconds,
        default=60.0,
        help="扫描超时处理中数据包的间隔",
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--nwp-input-root")
    parser.add_argument("--nwp-farm-codes", type=_farm_codes)
    parser.add_argument("--nwp-pattern", default="*.csv")
    parser.add_argument("--source", default="field.nwp")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
    )
    args = _parser().parse_args(argv)
    if bool(args.nwp_input_root) != bool(args.nwp_farm_codes):
        raise SystemExit("--nwp-input-root 与 --nwp-farm-codes 必须同时配置")

    processor = BusinessPackageProcessor(args.spool)
    next_recovery_at = 0.0
    while True:
        now = time.monotonic()
        if now >= next_recovery_at:
            _recover_stale_processing(
                processor,
                older_than_seconds=args.processing_timeout_seconds,
            )
            next_recovery_at = now + args.recovery_interval_seconds

        ingress_results = []
        if args.nwp_input_root:
            root = Path(args.nwp_input_root)
            for farm_code in args.nwp_farm_codes:
                result = ingest_directory_once(
                    input_dir=root / farm_code,
                    spool_dir=args.spool,
                    source=args.source,
                    farm_code=farm_code,
                    data_type="nwp",
                    pattern=args.nwp_pattern,
                    minimum_age_seconds=1.0,
                )
                if result.accepted or result.errors:
                    ingress_results.append({"farm_code": farm_code, **result.to_dict()})

        results = [item.__dict__ for item in processor.run_until_idle()]
        if ingress_results or results:
            print(
                json.dumps(
                    {"ingress": ingress_results, "processing": results},
                    ensure_ascii=False,
                    default=str,
                ),
                flush=True,
            )
        if args.once:
            return 0
        time.sleep(max(0.2, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
