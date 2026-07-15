import io

from flask import Flask

from integration.contracts import build_manifest
from routes.integration_router import integration_bp


def _client(tmp_path, *, enabled=True, token="secret-token"):
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        INTEGRATION_API_ENABLED=enabled,
        INTEGRATION_API_TOKEN=token,
        INTEGRATION_SPOOL_DIR=str(tmp_path / "spool"),
        INTEGRATION_MAX_PAYLOAD_BYTES=1024,
    )
    app.register_blueprint(integration_bp)
    return app.test_client()


def _request_data(payload=b"power=12.5", message_id="api-001"):
    manifest = build_manifest(
        payload,
        message_id=message_id,
        payload_filename="payload.txt",
        source="zone2.scada",
        farm_code="CF",
        data_type="scada",
        event_time="2026-07-15T08:00:00+08:00",
    )
    return {
        "manifest": manifest.to_json(),
        "payload": (io.BytesIO(payload), "payload.txt"),
    }


def test_integration_api_requires_token(tmp_path):
    response = _client(tmp_path).post(
        "/api/v1/integration/packages",
        data=_request_data(),
        content_type="multipart/form-data",
    )
    assert response.status_code == 401


def test_integration_api_accepts_and_reports_status(tmp_path):
    client = _client(tmp_path)
    headers = {"X-Integration-Token": "secret-token", "Idempotency-Key": "api-001"}

    accepted = client.post(
        "/api/v1/integration/packages",
        data=_request_data(),
        headers=headers,
        content_type="multipart/form-data",
    )
    status = client.get("/api/v1/integration/packages/api-001", headers=headers)

    assert accepted.status_code == 201
    assert accepted.get_json()["duplicate"] is False
    assert status.status_code == 200
    assert status.get_json()["package"]["state"] == "inbox"


def test_integration_api_duplicate_is_idempotent(tmp_path):
    client = _client(tmp_path)
    headers = {"X-Integration-Token": "secret-token"}
    first = client.post(
        "/api/v1/integration/packages",
        data=_request_data(),
        headers=headers,
        content_type="multipart/form-data",
    )
    second = client.post(
        "/api/v1/integration/packages",
        data=_request_data(),
        headers=headers,
        content_type="multipart/form-data",
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.get_json()["duplicate"] is True


def test_integration_api_rejects_corrupted_payload(tmp_path):
    client = _client(tmp_path)
    data = _request_data(payload=b"expected")
    data["payload"] = (io.BytesIO(b"modified"), "payload.txt")

    response = client.post(
        "/api/v1/integration/packages",
        data=data,
        headers={"X-Integration-Token": "secret-token"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "完整性" in response.get_json()["message"]


def test_integration_api_can_be_disabled(tmp_path):
    response = _client(tmp_path, enabled=False).get(
        "/api/v1/integration/health",
        headers={"X-Integration-Token": "secret-token"},
    )
    assert response.status_code == 503


def test_integration_status_rejects_unsafe_message_id(tmp_path):
    response = _client(tmp_path).get(
        "/api/v1/integration/packages/bad%5Cmessage",
        headers={"X-Integration-Token": "secret-token"},
    )
    assert response.status_code == 400
