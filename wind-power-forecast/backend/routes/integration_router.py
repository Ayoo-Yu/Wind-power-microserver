"""统一跨区数据接入接口。"""

from __future__ import annotations

import hmac
import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from integration.contracts import (
    ContractValidationError,
    IntegrationManifest,
    validate_message_id,
)
from integration.spool import DurableSpool, PackageConflictError


integration_bp = Blueprint("integration", __name__, url_prefix="/api/v1/integration")


def _error(message: str, status_code: int, *, details: list[str] | None = None):
    body = {"status": "error", "message": message}
    if details:
        body["details"] = details
    return jsonify(body), status_code


def _authorize():
    if not current_app.config.get("INTEGRATION_API_ENABLED", False):
        return _error("统一数据接入接口未启用", 503)
    expected = str(current_app.config.get("INTEGRATION_API_TOKEN", ""))
    if not expected:
        current_app.logger.error("INTEGRATION_API_ENABLED 已启用，但未配置令牌")
        return _error("统一数据接入接口配置不完整", 503)
    supplied = request.headers.get("X-Integration-Token", "")
    if not supplied or not hmac.compare_digest(supplied, expected):
        return _error("接入令牌无效", 401)
    return None


def _spool() -> DurableSpool:
    root = Path(current_app.config["INTEGRATION_SPOOL_DIR"])
    return DurableSpool(root)


@integration_bp.before_request
def authorize_integration_request():
    return _authorize()


@integration_bp.post("/packages")
def receive_package():
    max_payload = int(current_app.config.get("INTEGRATION_MAX_PAYLOAD_BYTES", 256 * 1024 * 1024))
    max_request_size = max_payload + 256 * 1024
    if request.content_length is not None and request.content_length > max_request_size:
        return _error("请求总大小超过接入限制", 413)

    manifest_text = request.form.get("manifest", "")
    payload_file = request.files.get("payload")
    if not manifest_text or payload_file is None:
        return _error("请求必须包含 manifest 和 payload", 400)
    if len(manifest_text.encode("utf-8")) > 64 * 1024:
        return _error("manifest 超过 64 KiB 限制", 413)

    try:
        raw_manifest = json.loads(manifest_text)
        manifest = IntegrationManifest.from_dict(raw_manifest)
    except json.JSONDecodeError:
        return _error("manifest 不是有效的 JSON", 400)
    except ContractValidationError as exc:
        return _error("manifest 未通过契约校验", 400, details=list(exc.errors))

    payload = payload_file.stream.read(max_payload + 1)
    if len(payload) > max_payload:
        return _error("payload 超过接入大小限制", 413)

    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key and idempotency_key != manifest.message_id:
        return _error("Idempotency-Key 与 message_id 不一致", 400)

    try:
        result = _spool().accept(manifest, payload)
    except ContractValidationError as exc:
        return _error("payload 未通过完整性校验", 400, details=list(exc.errors))
    except PackageConflictError as exc:
        return _error(str(exc), 409)

    status_code = 200 if result.duplicate else 201
    return (
        jsonify(
            {
                "status": "accepted",
                "message_id": result.message_id,
                "state": result.state,
                "duplicate": result.duplicate,
            }
        ),
        status_code,
    )


@integration_bp.get("/packages/<message_id>")
def package_status(message_id: str):
    try:
        validate_message_id(message_id)
        package = _spool().describe(message_id)
    except ContractValidationError as exc:
        return _error("message_id 未通过契约校验", 400, details=list(exc.errors))
    if package is None:
        return _error("数据包不存在", 404)
    return jsonify({"status": "ok", "package": package})


@integration_bp.get("/health")
def integration_health():
    return jsonify(
        {
            "status": "ok",
            "schema_version": "1.0",
            "queue": _spool().summary(),
        }
    )
