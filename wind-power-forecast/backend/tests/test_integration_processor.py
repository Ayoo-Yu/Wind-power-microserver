from contextlib import contextmanager
from datetime import datetime, timezone
import os
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models.data_lineage import IngestionBatch
from integration.contracts import build_manifest
from integration.processor import (
    BusinessPackageProcessor,
    _recover_stale_processing,
)
from integration.spool import DurableSpool


def _session_context(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'processor.db'}")
    IngestionBatch.__table__.create(engine)
    factory = sessionmaker(bind=engine)

    @contextmanager
    def context():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return context, factory, engine


def _enqueue_nwp(spool_dir):
    payload = (
        b"forecast_source,forecast_time,latitude,longitude,100u,100v\n"
        b"2026-07-15T08:00:00+08:00,2026-07-15T08:15:00+08:00,23.8,103.2,4,3\n"
    )
    manifest = build_manifest(
        payload,
        payload_filename="nwp_CF.csv",
        source="zone3.nwp",
        farm_code="CF",
        data_type="nwp",
        event_time=datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc),
        message_id="nwp-CF-20260715-0800",
        record_count=1,
    )
    DurableSpool(spool_dir).accept(manifest, payload)
    return manifest


def test_processor_records_lineage_and_completes_spool(tmp_path):
    spool_dir = tmp_path / "spool"
    manifest = _enqueue_nwp(spool_dir)
    context, factory, engine = _session_context(tmp_path)
    calls = []

    def importer(path, farm_code):
        calls.append((path, farm_code))
        return {"processed_rows": 1, "ingested_count": 1, "error_count": 0}

    processor = BusinessPackageProcessor(
        spool_dir,
        session_context=context,
        nwp_importer=importer,
        nwp_enabled=True,
    )
    result = processor.run_once()

    assert result.status == "processed"
    assert result.accepted_count == 1
    assert calls[0][1] == "CF"
    assert DurableSpool(spool_dir).summary()["processed"] == 1

    session = factory()
    try:
        batch = session.query(IngestionBatch).one()
        assert batch.message_id == manifest.message_id
        assert batch.status == "completed"
        assert batch.quality_status == "good"
        assert batch.accepted_count == 1
        assert batch.payload_sha256 == manifest.payload_sha256
    finally:
        session.close()
        engine.dispose()


def test_processor_retries_nwp_package_while_capability_is_disabled(tmp_path):
    spool_dir = tmp_path / "spool"
    _enqueue_nwp(spool_dir)
    context, factory, engine = _session_context(tmp_path)
    processor = BusinessPackageProcessor(
        spool_dir,
        session_context=context,
        nwp_enabled=False,
        retry_base_seconds=0.01,
    )

    result = processor.run_once()

    assert result.status == "retry"
    assert "未启用" in result.error
    session = factory()
    try:
        batch = session.query(IngestionBatch).one()
        assert batch.status == "retry"
    finally:
        session.close()
        engine.dispose()


def test_processor_quarantines_unsupported_business_payload(tmp_path):
    spool_dir = tmp_path / "spool"
    payload = b"value=1"
    manifest = build_manifest(
        payload,
        payload_filename="scada.dat",
        source="zone2.scada",
        farm_code="CF",
        data_type="scada",
        event_time=datetime.now(timezone.utc),
        message_id="scada-CF-unsupported",
    )
    DurableSpool(spool_dir).accept(manifest, payload)
    context, factory, engine = _session_context(tmp_path)
    processor = BusinessPackageProcessor(spool_dir, session_context=context)

    result = processor.run_once()

    assert result.status == "quarantined"
    assert DurableSpool(spool_dir).summary()["quarantine"] == 1
    session = factory()
    try:
        batch = session.query(IngestionBatch).one()
        assert batch.status == "quarantined"
        assert "适配器" in batch.error_message
    finally:
        session.close()
        engine.dispose()


def test_processor_startup_recovery_returns_interrupted_package_to_inbox(tmp_path):
    spool_dir = tmp_path / "spool"
    manifest = _enqueue_nwp(spool_dir)
    spool = DurableSpool(spool_dir)
    claimed = spool.claim(manifest.message_id)
    old = time.time() - 600
    os.utime(claimed.path, (old, old))
    context, _factory, engine = _session_context(tmp_path)
    processor = BusinessPackageProcessor(
        spool_dir,
        session_context=context,
        nwp_enabled=True,
    )

    recovered = _recover_stale_processing(
        processor,
        older_than_seconds=300,
    )

    assert recovered == [manifest.message_id]
    assert spool.locate(manifest.message_id)[0] == "inbox"
    engine.dispose()
