import json
import os
import time

import pytest

from integration.contracts import ContractValidationError, build_manifest
from integration.spool import DurableSpool, PackageConflictError


def _package(message_id="msg-001", payload=b"power=12.5"):
    manifest = build_manifest(
        payload,
        message_id=message_id,
        payload_filename="payload.txt",
        source="zone2.scada",
        farm_code="CF",
        data_type="scada",
        event_time="2026-07-15T08:00:00+08:00",
    )
    return manifest, payload


def test_accept_claim_and_complete(tmp_path):
    spool = DurableSpool(tmp_path)
    manifest, payload = _package()

    accepted = spool.accept(manifest, payload)
    assert accepted.state == "inbox"
    assert accepted.path.joinpath("payload.txt").read_bytes() == payload

    claimed = spool.claim()
    assert claimed is not None
    assert claimed.state == "processing"

    completed = spool.complete(manifest.message_id)
    assert completed.state == "processed"
    assert spool.summary() == {
        "inbox": 0,
        "processing": 0,
        "processed": 1,
        "quarantine": 0,
    }


def test_duplicate_payload_is_idempotent(tmp_path):
    spool = DurableSpool(tmp_path)
    manifest, payload = _package()
    first = spool.accept(manifest, payload)
    second = spool.accept(manifest, payload)

    assert first.path == second.path
    assert second.duplicate is True
    assert spool.summary()["inbox"] == 1


def test_same_message_id_with_different_payload_is_rejected(tmp_path):
    spool = DurableSpool(tmp_path)
    first, first_payload = _package(payload=b"first")
    second, second_payload = _package(payload=b"second")
    spool.accept(first, first_payload)

    with pytest.raises(PackageConflictError):
        spool.accept(second, second_payload)


def test_same_message_id_and_payload_with_different_source_is_rejected(tmp_path):
    spool = DurableSpool(tmp_path)
    first, payload = _package()
    second = build_manifest(
        payload,
        message_id=first.message_id,
        payload_filename=first.payload_filename,
        source="zone3.scada",
        farm_code=first.farm_code,
        data_type=first.data_type,
        event_time=first.event_time,
    )
    spool.accept(first, payload)

    with pytest.raises(PackageConflictError, match="another identity"):
        spool.accept(second, payload)


def test_status_lookup_rejects_unsafe_message_id(tmp_path):
    spool = DurableSpool(tmp_path)
    with pytest.raises(ContractValidationError, match="message_id"):
        spool.describe("../outside")


def test_failed_package_moves_to_quarantine(tmp_path):
    spool = DurableSpool(tmp_path)
    manifest, payload = _package()
    spool.accept(manifest, payload)
    spool.claim(manifest.message_id)

    result = spool.fail(manifest.message_id, "schema mapping failed")
    error = json.loads(result.path.joinpath("error.json").read_text(encoding="utf-8"))

    assert result.state == "quarantine"
    assert error["error"] == "schema mapping failed"


def test_stale_processing_package_is_recovered(tmp_path):
    spool = DurableSpool(tmp_path)
    manifest, payload = _package()
    spool.accept(manifest, payload)
    claimed = spool.claim(manifest.message_id)
    old = time.time() - 600
    os.utime(claimed.path, (old, old))

    recovered = spool.recover_processing(older_than_seconds=300)

    assert recovered == [manifest.message_id]
    assert spool.locate(manifest.message_id)[0] == "inbox"


def test_retry_records_error_and_honors_delay(tmp_path):
    spool = DurableSpool(tmp_path)
    manifest, payload = _package()
    spool.accept(manifest, payload)
    spool.claim(manifest.message_id)

    result = spool.retry(
        manifest.message_id,
        "next hop unavailable",
        base_delay_seconds=60,
        max_delay_seconds=60,
    )

    assert result.state == "inbox"
    assert spool.claim(manifest.message_id) is None
    description = spool.describe(manifest.message_id)
    assert description["runtime"]["last_error"] == "next hop unavailable"
