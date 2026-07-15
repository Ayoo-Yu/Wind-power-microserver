"""跨区数据包契约。

数据文件与清单文件共同组成一个不可变数据包。清单承担来源追踪、
幂等识别、时间语义和完整性校验职责。
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "1.0"
SUPPORTED_DATA_TYPES = frozenset(
    {
        "scada",
        "actual_power",
        "nwp",
        "weather",
        "operational",
        "forecast",
        "report_receipt",
    }
)

_MESSAGE_ID_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,126}[A-Za-z0-9_-])?$"
)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_FARM_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,49}$")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_UNSAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
_PACKAGE_CONTROL_FILENAMES = {"manifest.json", "state.json", "error.json"}


class ContractValidationError(ValueError):
    """数据包清单或载荷不符合统一契约。"""

    def __init__(self, errors: list[str] | tuple[str, ...]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def validate_message_id(value: str) -> str:
    """校验可安全映射为跨平台目录名的消息编号。"""

    reserved_stem = value.split(".", 1)[0].upper() if isinstance(value, str) else ""
    if (
        not isinstance(value, str)
        or not _MESSAGE_ID_RE.fullmatch(value)
        or reserved_stem in _WINDOWS_RESERVED_NAMES
    ):
        raise ContractValidationError(
            ["message_id contains unsupported characters or length"]
        )
    return value


def _parse_timestamp(value: str, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty ISO 8601 string")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must use ISO 8601 format") from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return parsed


def _canonical_timestamp(value: datetime | str) -> str:
    parsed = value if isinstance(value, datetime) else _parse_timestamp(value, "timestamp")
    if parsed.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.isoformat(timespec="seconds")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class IntegrationManifest:
    """统一数据包清单。"""

    message_id: str
    source: str
    farm_code: str
    data_type: str
    event_time: str
    created_at: str
    payload_filename: str
    payload_sha256: str
    payload_size: int
    schema_version: str = SCHEMA_VERSION
    record_count: int | None = None
    sequence: int | None = None
    quality: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "IntegrationManifest":
        if not isinstance(raw, Mapping):
            raise ContractValidationError(["manifest must be a JSON object"])

        known_fields = {item.name for item in cls.__dataclass_fields__.values()}
        unknown = sorted(set(raw) - known_fields)
        errors: list[str] = []
        if unknown:
            errors.append(f"unknown manifest fields: {', '.join(unknown)}")

        required = {
            "message_id",
            "source",
            "farm_code",
            "data_type",
            "event_time",
            "created_at",
            "payload_filename",
            "payload_sha256",
            "payload_size",
        }
        missing = sorted(name for name in required if name not in raw)
        if missing:
            errors.append(f"missing manifest fields: {', '.join(missing)}")
        if errors:
            raise ContractValidationError(errors)

        try:
            manifest = cls(**dict(raw))
        except TypeError as exc:
            raise ContractValidationError([str(exc)]) from exc
        manifest.validate()
        return manifest

    def validate(self) -> None:
        errors: list[str] = []

        try:
            validate_message_id(self.message_id)
        except ContractValidationError as exc:
            errors.extend(exc.errors)
        if not isinstance(self.source, str) or not _IDENTIFIER_RE.fullmatch(self.source):
            errors.append("source contains unsupported characters or length")
        if not isinstance(self.farm_code, str) or not _FARM_CODE_RE.fullmatch(self.farm_code):
            errors.append("farm_code contains unsupported characters or length")
        if self.data_type not in SUPPORTED_DATA_TYPES:
            errors.append(f"unsupported data_type: {self.data_type}")
        if self.schema_version != SCHEMA_VERSION:
            errors.append(f"unsupported schema_version: {self.schema_version}")

        try:
            _parse_timestamp(self.event_time, "event_time")
        except ValueError as exc:
            errors.append(str(exc))
        try:
            _parse_timestamp(self.created_at, "created_at")
        except ValueError as exc:
            errors.append(str(exc))

        if not isinstance(self.payload_filename, str):
            errors.append("payload_filename must be a string")
        else:
            path = Path(self.payload_filename)
            reserved_stem = self.payload_filename.split(".", 1)[0].upper()
            if (
                path.name != self.payload_filename
                or self.payload_filename in {"", ".", ".."}
                or _UNSAFE_FILENAME_RE.search(self.payload_filename)
                or self.payload_filename.endswith((" ", "."))
                or len(self.payload_filename.encode("utf-8")) > 240
                or reserved_stem in _WINDOWS_RESERVED_NAMES
                or self.payload_filename.lower() in _PACKAGE_CONTROL_FILENAMES
            ):
                errors.append("payload_filename must be a safe base name")

        if not isinstance(self.payload_sha256, str) or not _SHA256_RE.fullmatch(self.payload_sha256):
            errors.append("payload_sha256 must be a lowercase SHA256 value")
        if not isinstance(self.payload_size, int) or isinstance(self.payload_size, bool) or self.payload_size < 0:
            errors.append("payload_size must be a non-negative integer")
        if self.record_count is not None and (
            not isinstance(self.record_count, int)
            or isinstance(self.record_count, bool)
            or self.record_count < 0
        ):
            errors.append("record_count must be a non-negative integer")
        if self.sequence is not None and (
            not isinstance(self.sequence, int)
            or isinstance(self.sequence, bool)
            or self.sequence < 0
        ):
            errors.append("sequence must be a non-negative integer")
        if not isinstance(self.quality, dict):
            errors.append("quality must be an object")
        if not isinstance(self.metadata, dict):
            errors.append("metadata must be an object")

        if errors:
            raise ContractValidationError(errors)

    def validate_payload(self, payload: bytes) -> None:
        errors: list[str] = []
        if len(payload) != self.payload_size:
            errors.append(
                f"payload_size mismatch: expected {self.payload_size}, received {len(payload)}"
            )
        digest = sha256_bytes(payload)
        if digest != self.payload_sha256:
            errors.append(
                f"payload_sha256 mismatch: expected {self.payload_sha256}, received {digest}"
            )
        if errors:
            raise ContractValidationError(errors)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2)


def build_manifest(
    payload: bytes,
    *,
    payload_filename: str,
    source: str,
    farm_code: str,
    data_type: str,
    event_time: datetime | str,
    message_id: str | None = None,
    created_at: datetime | str | None = None,
    record_count: int | None = None,
    sequence: int | None = None,
    quality: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> IntegrationManifest:
    """根据不可变载荷生成经过校验的清单。"""

    now = created_at or datetime.now(timezone.utc)
    manifest = IntegrationManifest(
        message_id=message_id or str(uuid.uuid4()),
        source=source,
        farm_code=farm_code,
        data_type=data_type,
        event_time=_canonical_timestamp(event_time),
        created_at=_canonical_timestamp(now),
        payload_filename=payload_filename,
        payload_sha256=sha256_bytes(payload),
        payload_size=len(payload),
        record_count=record_count,
        sequence=sequence,
        quality=dict(quality or {}),
        metadata=dict(metadata or {}),
    )
    manifest.validate()
    return manifest


def load_manifest(path: str | Path) -> IntegrationManifest:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return IntegrationManifest.from_dict(raw)
