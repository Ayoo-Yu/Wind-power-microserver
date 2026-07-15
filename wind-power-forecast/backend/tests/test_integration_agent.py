import io
import json
import urllib.error
import urllib.request

import pytest

from integration.agent import (
    DirectoryPackageSender,
    HttpPackageSender,
    PermanentTransferError,
    TemporaryTransferError,
    TransferAgent,
)
from integration.contracts import build_manifest
from integration.spool import DurableSpool


def _enqueue(root, message_id="agent-001", payload=b"power=12.5"):
    manifest = build_manifest(
        payload,
        message_id=message_id,
        payload_filename="payload.txt",
        source="zone3.relay",
        farm_code="CF",
        data_type="scada",
        event_time="2026-07-15T08:00:00+08:00",
    )
    DurableSpool(root).accept(manifest, payload)
    return manifest


class _FailingSender:
    def __init__(self, error):
        self.error = error

    def send(self, manifest, payload):
        raise self.error


def test_directory_agent_transfers_and_completes_source(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    manifest = _enqueue(source)
    agent = TransferAgent(source, DirectoryPackageSender(target))

    result = agent.run_once()

    assert result.status == "sent"
    assert DurableSpool(source).locate(manifest.message_id)[0] == "processed"
    assert DurableSpool(target).locate(manifest.message_id)[0] == "inbox"


def test_agent_duplicate_delivery_is_success(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    manifest = _enqueue(source)
    target_spool = DurableSpool(target)
    target_spool.accept_package(DurableSpool(source).locate(manifest.message_id)[1])

    result = TransferAgent(source, DirectoryPackageSender(target)).run_once()

    assert result.status == "sent"
    assert result.duplicate is True


def test_temporary_failure_requeues_with_error(tmp_path):
    source = tmp_path / "source"
    manifest = _enqueue(source)
    agent = TransferAgent(
        source,
        _FailingSender(TemporaryTransferError("link unavailable")),
        retry_base_seconds=0,
        retry_max_seconds=0,
    )

    result = agent.run_once()
    description = DurableSpool(source).describe(manifest.message_id)

    assert result.status == "retry"
    assert description["state"] == "inbox"
    assert description["runtime"]["last_error"] == "link unavailable"


def test_permanent_failure_moves_to_quarantine(tmp_path):
    source = tmp_path / "source"
    manifest = _enqueue(source)
    agent = TransferAgent(source, _FailingSender(PermanentTransferError("token rejected")))

    result = agent.run_once()

    assert result.status == "quarantined"
    assert DurableSpool(source).locate(manifest.message_id)[0] == "quarantine"


def test_http_sender_accepts_empty_success_response(monkeypatch):
    manifest = build_manifest(
        b"power=12.5",
        message_id="http-204",
        payload_filename="payload.txt",
        source="zone2.scada",
        farm_code="CF",
        data_type="scada",
        event_time="2026-07-15T08:00:00+08:00",
    )

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        @staticmethod
        def getcode():
            return 204

        @staticmethod
        def read():
            return b""

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: _Response())
    receipt = HttpPackageSender("http://127.0.0.1/packages", "token").send(
        manifest,
        b"power=12.5",
    )

    assert receipt.message_id == "http-204"
    assert receipt.duplicate is False


def test_http_sender_retries_rate_limit(monkeypatch):
    manifest = build_manifest(
        b"payload",
        message_id="http-429",
        payload_filename="payload.txt",
        source="zone2.scada",
        farm_code="CF",
        data_type="scada",
        event_time="2026-07-15T08:00:00+08:00",
    )
    error = urllib.error.HTTPError(
        "http://127.0.0.1/packages",
        429,
        "rate limited",
        {},
        io.BytesIO(json.dumps({"message": "slow down"}).encode("utf-8")),
    )
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )

    with pytest.raises(TemporaryTransferError, match="429"):
        HttpPackageSender("http://127.0.0.1/packages", "token").send(
            manifest,
            b"payload",
        )


def test_http_sender_rejects_mismatched_receipt(monkeypatch):
    manifest = build_manifest(
        b"payload",
        message_id="http-receipt",
        payload_filename="payload.txt",
        source="zone2.scada",
        farm_code="CF",
        data_type="scada",
        event_time="2026-07-15T08:00:00+08:00",
    )

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        @staticmethod
        def getcode():
            return 200

        @staticmethod
        def read():
            return b'{"message_id":"another-message"}'

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: _Response())
    with pytest.raises(PermanentTransferError, match="message_id"):
        HttpPackageSender("http://127.0.0.1/packages", "token").send(
            manifest,
            b"payload",
        )
