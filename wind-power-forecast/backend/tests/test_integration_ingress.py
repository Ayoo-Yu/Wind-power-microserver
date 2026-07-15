import os
from pathlib import Path

from integration.ingress import ingest_directory_once
from integration.spool import DurableSpool


def test_directory_ingress_is_content_idempotent_without_rereading(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    spool_dir = tmp_path / "spool"
    input_dir.mkdir()
    source_file = input_dir / "nwp.dat"
    source_file.write_bytes(b"forecast-content")

    first = ingest_directory_once(
        input_dir=input_dir,
        spool_dir=spool_dir,
        source="zone3.nwp",
        farm_code="CF",
        data_type="nwp",
        pattern="*.dat",
        minimum_age_seconds=0,
    )
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path):
        if path == source_file:
            raise AssertionError("稳定且已接入的文件不应再次读取")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    second = ingest_directory_once(
        input_dir=input_dir,
        spool_dir=spool_dir,
        source="zone3.nwp",
        farm_code="CF",
        data_type="nwp",
        pattern="*.dat",
        minimum_age_seconds=0,
    )

    assert first.accepted == 1
    assert second.duplicates == 1
    assert spool_dir.joinpath(".ingress-index.json").is_file()
    assert DurableSpool(spool_dir).summary()["inbox"] == 1


def test_directory_ingress_creates_new_message_when_content_changes(tmp_path):
    input_dir = tmp_path / "input"
    spool_dir = tmp_path / "spool"
    input_dir.mkdir()
    source_file = input_dir / "scada.csv"
    source_file.write_bytes(b"power=1")
    common = {
        "input_dir": input_dir,
        "spool_dir": spool_dir,
        "source": "zone2.scada",
        "farm_code": "CF",
        "data_type": "scada",
        "minimum_age_seconds": 0,
    }

    ingest_directory_once(**common)
    source_file.write_bytes(b"power=2")
    ingest_directory_once(**common)

    assert DurableSpool(spool_dir).summary()["inbox"] == 2


def test_directory_ingress_skips_recent_file(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "writing.dat").write_bytes(b"partial")

    result = ingest_directory_once(
        input_dir=input_dir,
        spool_dir=tmp_path / "spool",
        source="zone3.nwp",
        farm_code="CF",
        data_type="nwp",
        minimum_age_seconds=60,
    )

    assert result.skipped_writing == 1
    assert result.accepted == 0


def test_directory_ingress_uses_modified_time_in_message_identity(tmp_path):
    input_dir = tmp_path / "input"
    spool_dir = tmp_path / "spool"
    input_dir.mkdir()
    source_file = input_dir / "scada.dat"
    source_file.write_bytes(b"same-content")
    common = {
        "input_dir": input_dir,
        "spool_dir": spool_dir,
        "source": "zone2.scada",
        "farm_code": "CF",
        "data_type": "scada",
        "minimum_age_seconds": 0,
    }

    ingest_directory_once(**common)
    first_stat = source_file.stat()
    os.utime(
        source_file,
        ns=(first_stat.st_atime_ns, first_stat.st_mtime_ns - 2_000_000_000),
    )
    second = ingest_directory_once(**common)

    assert second.accepted == 1
    assert DurableSpool(spool_dir).summary()["inbox"] == 2
