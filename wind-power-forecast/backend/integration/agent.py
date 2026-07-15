"""跨区数据包传输代理。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .contracts import ContractValidationError, IntegrationManifest, load_manifest
from .spool import DurableSpool, PackageConflictError


RETRYABLE_HTTP_CODES = {408, 425, 429}


class TemporaryTransferError(RuntimeError):
    """网络、目标服务等可恢复故障。"""


class PermanentTransferError(RuntimeError):
    """数据契约、鉴权或目标冲突等需人工处理的故障。"""


@dataclass(frozen=True)
class DeliveryReceipt:
    message_id: str
    duplicate: bool = False
    remote_state: str = "inbox"


@dataclass(frozen=True)
class TransferResult:
    status: str
    message_id: str | None = None
    duplicate: bool = False
    error: str | None = None


class PackageSender(Protocol):
    def send(self, manifest: IntegrationManifest, payload: bytes) -> DeliveryReceipt:
        ...


class DirectoryPackageSender:
    """通过挂载目录或移动介质将数据包写入下一跳。"""

    def __init__(self, target_spool: str | Path):
        self.target = DurableSpool(target_spool)

    def send(self, manifest: IntegrationManifest, payload: bytes) -> DeliveryReceipt:
        try:
            result = self.target.accept(manifest, payload)
        except (ContractValidationError, PackageConflictError) as exc:
            raise PermanentTransferError(str(exc)) from exc
        return DeliveryReceipt(
            message_id=manifest.message_id,
            duplicate=result.duplicate,
            remote_state=result.state,
        )


class HttpPackageSender:
    """通过服务端统一接入接口发送数据包。"""

    def __init__(self, endpoint: str, token: str, timeout_seconds: float = 30.0):
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds

    def send(self, manifest: IntegrationManifest, payload: bytes) -> DeliveryReceipt:
        body, content_type = self._multipart_body(manifest, payload)
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": content_type,
                "Content-Length": str(len(body)),
                "X-Integration-Token": self.token,
                "Idempotency-Key": manifest.message_id,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                status_code = response.getcode()
                response_body = response.read()
        except urllib.error.HTTPError as exc:
            detail = self._http_error_detail(exc)
            if 400 <= exc.code < 500 and exc.code not in RETRYABLE_HTTP_CODES:
                raise PermanentTransferError(f"HTTP {exc.code}: {detail}") from exc
            raise TemporaryTransferError(f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TemporaryTransferError(str(exc)) from exc
        if not 200 <= status_code < 300:
            raise TemporaryTransferError(f"目标服务返回了状态码 {status_code}")
        try:
            response_data = (
                json.loads(response_body.decode("utf-8")) if response_body.strip() else {}
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TemporaryTransferError("目标服务返回了无法解析的响应") from exc
        if not isinstance(response_data, dict):
            raise TemporaryTransferError("目标服务返回的回执必须是 JSON 对象")
        remote_message_id = response_data.get("message_id", manifest.message_id)
        if remote_message_id != manifest.message_id:
            raise PermanentTransferError("目标服务返回的 message_id 与发送消息不一致")
        return DeliveryReceipt(
            message_id=manifest.message_id,
            duplicate=bool(response_data.get("duplicate", False)),
            remote_state=str(response_data.get("state", "inbox")),
        )

    @staticmethod
    def _multipart_body(
        manifest: IntegrationManifest,
        payload: bytes,
    ) -> tuple[bytes, str]:
        boundary = f"windpower-{uuid.uuid4().hex}"
        line_break = b"\r\n"
        chunks = [
            f"--{boundary}".encode("ascii"),
            b'Content-Disposition: form-data; name="manifest"',
            b"Content-Type: application/json; charset=utf-8",
            b"",
            manifest.to_json().encode("utf-8"),
            f"--{boundary}".encode("ascii"),
            (
                'Content-Disposition: form-data; name="payload"; '
                f'filename="{manifest.payload_filename}"'
            ).encode("utf-8"),
            b"Content-Type: application/octet-stream",
            b"",
            payload,
            f"--{boundary}--".encode("ascii"),
            b"",
        ]
        return line_break.join(chunks), f"multipart/form-data; boundary={boundary}"

    @staticmethod
    def _http_error_detail(exc: urllib.error.HTTPError) -> str:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            return str(payload.get("message") or payload.get("error") or payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return str(exc.reason)


class TransferAgent:
    """从本地可靠队列取出数据包，并幂等传递到下一跳。"""

    def __init__(
        self,
        source_spool: str | Path,
        sender: PackageSender,
        *,
        retry_base_seconds: float = 5.0,
        retry_max_seconds: float = 300.0,
    ):
        self.source = DurableSpool(source_spool)
        self.sender = sender
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds

    def run_once(self) -> TransferResult:
        claimed = self.source.claim()
        if claimed is None:
            return TransferResult(status="idle")

        message_id = claimed.message_id
        try:
            manifest = load_manifest(claimed.path / "manifest.json")
            payload = (claimed.path / manifest.payload_filename).read_bytes()
            manifest.validate_payload(payload)
            receipt = self.sender.send(manifest, payload)
            self.source.complete(message_id)
            return TransferResult(
                status="sent",
                message_id=message_id,
                duplicate=receipt.duplicate,
            )
        except (PermanentTransferError, ContractValidationError, PackageConflictError) as exc:
            self.source.fail(message_id, str(exc))
            return TransferResult(status="quarantined", message_id=message_id, error=str(exc))
        except Exception as exc:
            self.source.retry(
                message_id,
                str(exc),
                base_delay_seconds=self.retry_base_seconds,
                max_delay_seconds=self.retry_max_seconds,
            )
            return TransferResult(status="retry", message_id=message_id, error=str(exc))

    def run_until_idle(self, limit: int = 100) -> list[TransferResult]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        results: list[TransferResult] = []
        for _ in range(limit):
            result = self.run_once()
            if result.status == "idle":
                break
            results.append(result)
        return results
