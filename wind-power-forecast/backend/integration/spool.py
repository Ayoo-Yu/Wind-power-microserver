"""基于目录的可靠接入箱。

所有状态转换都通过同一文件系统内的原子重命名完成。载荷在进入接入箱前
必须通过统一契约与 SHA256 校验。
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .contracts import (
    ContractValidationError,
    IntegrationManifest,
    load_manifest,
    validate_message_id,
)


class PackageConflictError(RuntimeError):
    """同一消息编号对应了不同载荷。"""


@dataclass(frozen=True)
class PackageResult:
    message_id: str
    state: str
    path: Path
    duplicate: bool = False


class DurableSpool:
    """统一管理接收、处理、完成和隔离目录。"""

    STATE_NAMES = ("inbox", "processing", "processed", "quarantine")

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.staging_dir = self.root / ".staging"
        self._lock = threading.RLock()
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        for state in self.STATE_NAMES:
            (self.root / state).mkdir(parents=True, exist_ok=True)

    def state_path(self, state: str, message_id: str) -> Path:
        if state not in self.STATE_NAMES:
            raise ValueError(f"unsupported spool state: {state}")
        validate_message_id(message_id)
        return self.root / state / message_id

    def locate(self, message_id: str) -> tuple[str, Path] | None:
        for state in self.STATE_NAMES:
            candidate = self.state_path(state, message_id)
            if candidate.is_dir():
                return state, candidate
        return None

    def accept(self, manifest: IntegrationManifest, payload: bytes) -> PackageResult:
        manifest.validate()
        manifest.validate_payload(payload)

        with self._lock:
            existing = self.locate(manifest.message_id)
            if existing:
                return self._resolve_existing(manifest, existing)

            staging = self.staging_dir / f"{manifest.message_id}.{uuid.uuid4().hex}.tmp"
            destination = self.state_path("inbox", manifest.message_id)
            try:
                staging.mkdir(parents=False, exist_ok=False)
                self._write_bytes(staging / manifest.payload_filename, payload)
                self._write_text(staging / "manifest.json", manifest.to_json())
                self._write_text(
                    staging / "state.json",
                    json.dumps(
                        {
                            "state": "inbox",
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                            "attempts": 0,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        indent=2,
                    ),
                )
                os.replace(staging, destination)
                self._sync_directory(destination.parent)
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                # 另一个进程可能在本进程写入暂存目录期间先完成了提交。
                existing = self.locate(manifest.message_id)
                if existing:
                    return self._resolve_existing(manifest, existing)
                raise

            return PackageResult(manifest.message_id, "inbox", destination)

    @staticmethod
    def _resolve_existing(
        manifest: IntegrationManifest,
        existing: tuple[str, Path],
    ) -> PackageResult:
        state, path = existing
        stored = load_manifest(path / "manifest.json")
        identity_fields = (
            "schema_version",
            "source",
            "farm_code",
            "data_type",
            "event_time",
            "payload_filename",
            "payload_sha256",
            "payload_size",
        )
        if all(getattr(stored, name) == getattr(manifest, name) for name in identity_fields):
            return PackageResult(manifest.message_id, state, path, duplicate=True)
        raise PackageConflictError(
            f"message_id {manifest.message_id} already exists with another identity"
        )

    def accept_package(self, package_dir: str | Path) -> PackageResult:
        package_path = Path(package_dir)
        manifest = load_manifest(package_path / "manifest.json")
        payload = (package_path / manifest.payload_filename).read_bytes()
        return self.accept(manifest, payload)

    def claim(self, message_id: str | None = None) -> PackageResult | None:
        with self._lock:
            if message_id:
                source = self.state_path("inbox", message_id)
                candidates = [source] if source.is_dir() else []
            else:
                candidates = sorted(
                    (path for path in (self.root / "inbox").iterdir() if path.is_dir()),
                    key=lambda path: (path.stat().st_mtime_ns, path.name),
                )
            for source in candidates:
                state = self._read_state(source)
                if not self._is_due(state):
                    continue
                destination = self.state_path("processing", source.name)
                try:
                    os.replace(source, destination)
                except FileNotFoundError:
                    # 其他进程可能已抢占该数据包，继续尝试下一个。
                    continue
                state["state"] = "processing"
                state["updated_at"] = datetime.now(timezone.utc).isoformat()
                state["attempts"] = int(state.get("attempts", 0)) + 1
                state.pop("next_attempt_at", None)
                self._write_text(
                    destination / "state.json",
                    json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2),
                )
                return PackageResult(source.name, "processing", destination)
            return None

    def complete(self, message_id: str) -> PackageResult:
        return self._move_processing(message_id, "processed")

    def fail(self, message_id: str, error: str) -> PackageResult:
        source = self.state_path("processing", message_id)
        if not source.is_dir():
            raise FileNotFoundError(f"processing package not found: {message_id}")
        self._write_text(
            source / "error.json",
            json.dumps(
                {
                    "error": error,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        return self._move_processing(message_id, "quarantine")

    def retry(
        self,
        message_id: str,
        error: str,
        *,
        base_delay_seconds: float = 5.0,
        max_delay_seconds: float = 300.0,
    ) -> PackageResult:
        """将临时失败的数据包放回接入箱并安排指数退避。"""

        if base_delay_seconds < 0 or max_delay_seconds < 0:
            raise ValueError("retry delays must be non-negative")
        with self._lock:
            source = self.state_path("processing", message_id)
            if not source.is_dir():
                raise FileNotFoundError(f"processing package not found: {message_id}")
            destination = self.state_path("inbox", message_id)
            if destination.exists():
                raise PackageConflictError(f"retry destination already exists: {message_id}")

            state = self._read_state(source)
            attempts = max(1, int(state.get("attempts", 1)))
            delay = min(max_delay_seconds, base_delay_seconds * (2 ** (attempts - 1)))
            now = datetime.now(timezone.utc)
            state.update(
                {
                    "state": "inbox",
                    "updated_at": now.isoformat(),
                    "next_attempt_at": (now + timedelta(seconds=delay)).isoformat(),
                    "last_error": error,
                }
            )
            self._write_text(
                source / "state.json",
                json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2),
            )
            os.replace(source, destination)
            return PackageResult(message_id, "inbox", destination)

    def recover_processing(self, older_than_seconds: float = 300.0) -> list[str]:
        now = datetime.now(timezone.utc).timestamp()
        recovered: list[str] = []
        with self._lock:
            for source in sorted((self.root / "processing").iterdir()):
                if not source.is_dir():
                    continue
                age = now - source.stat().st_mtime
                if age < older_than_seconds:
                    continue
                destination = self.state_path("inbox", source.name)
                if destination.exists():
                    if not source.exists():
                        continue
                    raise PackageConflictError(f"recovery destination exists: {source.name}")
                state = self._read_state(source)
                state["state"] = "inbox"
                state["updated_at"] = datetime.now(timezone.utc).isoformat()
                state["recovered"] = True
                state.pop("next_attempt_at", None)
                self._write_text(
                    source / "state.json",
                    json.dumps(state, ensure_ascii=False, indent=2),
                )
                try:
                    os.replace(source, destination)
                except FileNotFoundError:
                    # 另一个恢复进程可能已经完成同一数据包的原子移动。
                    continue
                recovered.append(source.name)
        return recovered

    def summary(self) -> dict[str, int]:
        return {
            state: sum(1 for path in (self.root / state).iterdir() if path.is_dir())
            for state in self.STATE_NAMES
        }

    def describe(self, message_id: str) -> dict | None:
        """返回数据包清单与运行状态，供状态接口和运维检查使用。"""

        located = self.locate(message_id)
        if not located:
            return None
        state_name, package_dir = located
        manifest = load_manifest(package_dir / "manifest.json")
        state = self._read_state(package_dir)
        error_file = package_dir / "error.json"
        error = None
        if error_file.exists():
            with error_file.open("r", encoding="utf-8") as handle:
                error = json.load(handle)
        return {
            "message_id": message_id,
            "state": state_name,
            "manifest": manifest.to_dict(),
            "runtime": state,
            "error": error,
        }

    def _move_processing(self, message_id: str, target_state: str) -> PackageResult:
        with self._lock:
            source = self.state_path("processing", message_id)
            if not source.is_dir():
                raise FileNotFoundError(f"processing package not found: {message_id}")
            destination = self.state_path(target_state, message_id)
            if destination.exists():
                raise PackageConflictError(f"destination already exists: {message_id}")
            state = self._read_state(source)
            state["state"] = target_state
            state["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_text(source / "state.json", json.dumps(state, ensure_ascii=False, indent=2))
            os.replace(source, destination)
            return PackageResult(message_id, target_state, destination)

    @staticmethod
    def _is_due(state: dict) -> bool:
        value = state.get("next_attempt_at")
        if not value:
            return True
        try:
            due_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return True
        if due_at.utcoffset() is None:
            return True
        return due_at <= datetime.now(timezone.utc)

    @staticmethod
    def _read_state(package_dir: Path) -> dict:
        state_file = package_dir / "state.json"
        if not state_file.exists():
            return {}
        with state_file.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _write_bytes(path: Path, data: bytes) -> None:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _write_text(path: Path, data: str) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    @staticmethod
    def _sync_directory(path: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
