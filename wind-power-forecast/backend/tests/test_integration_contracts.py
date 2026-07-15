from datetime import datetime, timezone

import pytest

from integration.contracts import (
    ContractValidationError,
    IntegrationManifest,
    build_manifest,
)


def _manifest(payload=b"timestamp,power\n2026-07-15T08:00:00+08:00,12.5\n"):
    return build_manifest(
        payload,
        payload_filename="scada.csv",
        source="zone2.scada",
        farm_code="CF",
        data_type="scada",
        event_time="2026-07-15T08:00:00+08:00",
        created_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
        record_count=1,
        sequence=42,
        quality={"iec104": "GD"},
    )


def test_build_manifest_and_validate_payload():
    payload = b"power=12.5"
    manifest = build_manifest(
        payload,
        payload_filename="payload.txt",
        source="zone2.scada",
        farm_code="CF",
        data_type="scada",
        event_time="2026-07-15T08:00:00+08:00",
    )

    manifest.validate_payload(payload)
    assert manifest.payload_size == len(payload)
    assert len(manifest.payload_sha256) == 64
    assert manifest.schema_version == "1.0"


def test_manifest_json_round_trip():
    manifest = _manifest()
    restored = IntegrationManifest.from_dict(manifest.to_dict())
    assert restored == manifest


def test_manifest_rejects_naive_event_time():
    raw = _manifest().to_dict()
    raw["event_time"] = "2026-07-15T08:00:00"
    with pytest.raises(ContractValidationError, match="UTC offset"):
        IntegrationManifest.from_dict(raw)


def test_manifest_rejects_path_traversal():
    raw = _manifest().to_dict()
    raw["payload_filename"] = "../scada.csv"
    with pytest.raises(ContractValidationError, match="safe base name"):
        IntegrationManifest.from_dict(raw)


@pytest.mark.parametrize(
    "filename",
    [
        r"folder\\scada.csv",
        'scada".csv',
        "scada\r\n.csv",
        "scada\x00.csv",
        "manifest.json",
        "CON.txt",
        "scada.csv.",
    ],
)
def test_manifest_rejects_unsafe_cross_platform_filename(filename):
    raw = _manifest().to_dict()
    raw["payload_filename"] = filename
    with pytest.raises(ContractValidationError, match="safe base name"):
        IntegrationManifest.from_dict(raw)


def test_manifest_rejects_message_id_that_cannot_be_a_directory_name():
    raw = _manifest().to_dict()
    raw["message_id"] = "zone2:message"
    with pytest.raises(ContractValidationError, match="message_id"):
        IntegrationManifest.from_dict(raw)


def test_manifest_rejects_reserved_windows_message_id():
    raw = _manifest().to_dict()
    raw["message_id"] = "CON.log"
    with pytest.raises(ContractValidationError, match="message_id"):
        IntegrationManifest.from_dict(raw)


def test_manifest_rejects_unknown_fields():
    raw = _manifest().to_dict()
    raw["unexpected"] = True
    with pytest.raises(ContractValidationError, match="unknown manifest fields"):
        IntegrationManifest.from_dict(raw)


def test_payload_checksum_mismatch_is_rejected():
    manifest = _manifest(b"expected")
    with pytest.raises(ContractValidationError, match="payload_sha256 mismatch"):
        manifest.validate_payload(b"modified")
