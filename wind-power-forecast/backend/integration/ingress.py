"""将分区落地目录中的完整文件封装为统一数据包。"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .contracts import build_manifest
from .spool import DurableSpool


@dataclass
class IngressResult:
    scanned: int = 0
    accepted: int = 0
    duplicates: int = 0
    skipped_writing: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "accepted": self.accepted,
            "duplicates": self.duplicates,
            "skipped_writing": self.skipped_writing,
            "errors": self.errors,
        }


def _load_index(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        files = raw.get("files", {}) if isinstance(raw, dict) else {}
        return files if isinstance(files, dict) else {}
    except (OSError, json.JSONDecodeError):
        # 索引只用于避免重复读取，损坏时重新扫描即可恢复。
        return {}


def _write_index(path: Path, files: dict[str, dict]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    serialized = json.dumps(
        {"version": 1, "files": files},
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _cached_message(
    entry: dict | None,
    *,
    stat_result,
    source: str,
    farm_code: str,
    data_type: str,
) -> str | None:
    if not isinstance(entry, dict):
        return None
    expected = {
        "size": stat_result.st_size,
        "mtime_ns": stat_result.st_mtime_ns,
        "source": source,
        "farm_code": farm_code,
        "data_type": data_type,
    }
    if any(entry.get(name) != value for name, value in expected.items()):
        return None
    message_id = entry.get("message_id")
    return message_id if isinstance(message_id, str) else None


def ingest_directory_once(
    *,
    input_dir: str | Path,
    spool_dir: str | Path,
    source: str,
    farm_code: str,
    data_type: str,
    pattern: str = "*",
    recursive: bool = False,
    minimum_age_seconds: float = 2.0,
) -> IngressResult:
    """扫描稳定文件，使用内容派生的消息编号完成幂等封装。"""

    if minimum_age_seconds < 0:
        raise ValueError("minimum_age_seconds must be non-negative")
    root = Path(input_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"input directory not found: {root}")

    spool = DurableSpool(spool_dir)
    index_path = spool.root / ".ingress-index.json"
    index = _load_index(index_path)
    index_changed = False
    candidates = root.rglob(pattern) if recursive else root.glob(pattern)
    result = IngressResult()
    now = time.time()
    for path in sorted(item for item in candidates if item.is_file()):
        result.scanned += 1
        try:
            first_stat = path.stat()
            if now - first_stat.st_mtime < minimum_age_seconds:
                result.skipped_writing += 1
                continue

            index_key = str(path.resolve())
            cached_message_id = _cached_message(
                index.get(index_key),
                stat_result=first_stat,
                source=source,
                farm_code=farm_code,
                data_type=data_type,
            )
            if cached_message_id:
                try:
                    cached_package = spool.locate(cached_message_id)
                except Exception:
                    cached_package = None
                if cached_package:
                    result.duplicates += 1
                    continue

            payload = path.read_bytes()
            second_stat = path.stat()
            if (
                first_stat.st_size != second_stat.st_size
                or first_stat.st_mtime_ns != second_stat.st_mtime_ns
            ):
                result.skipped_writing += 1
                continue

            payload_digest = hashlib.sha256(payload).hexdigest()
            event_time = datetime.fromtimestamp(second_stat.st_mtime, tz=timezone.utc)
            identity = (
                f"{source}:{farm_code}:{data_type}:{path.name}:"
                f"{second_stat.st_mtime_ns}:{payload_digest}"
            ).encode("utf-8")
            message_id = f"{farm_code}-{data_type}-{hashlib.sha256(identity).hexdigest()[:40]}"
            manifest = build_manifest(
                payload,
                message_id=message_id,
                payload_filename=path.name,
                source=source,
                farm_code=farm_code,
                data_type=data_type,
                event_time=event_time,
                metadata={
                    "ingress": "directory",
                    "original_filename": path.name,
                    "source_mtime": event_time.isoformat(),
                },
            )
            accepted = spool.accept(manifest, payload)
            if accepted.duplicate:
                result.duplicates += 1
            else:
                result.accepted += 1
            index[index_key] = {
                "size": second_stat.st_size,
                "mtime_ns": second_stat.st_mtime_ns,
                "source": source,
                "farm_code": farm_code,
                "data_type": data_type,
                "message_id": message_id,
            }
            index_changed = True
        except Exception as exc:
            result.errors.append({"file": str(path), "error": str(exc)})

    if index_changed:
        try:
            _write_index(index_path, index)
        except OSError as exc:
            result.errors.append({"file": str(index_path), "error": str(exc)})
    return result
