import socket

import pytest

from scada_manager_main import validate_runtime_config
from services.scada_security import ScadaNetworkPolicyError, validate_scada_target


def _resolve_to(monkeypatch, *addresses):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))
            for address in addresses
        ],
    )


def test_development_target_can_run_without_network_allowlist(monkeypatch):
    _resolve_to(monkeypatch, "127.0.0.1")
    assert validate_scada_target(
        "localhost",
        {"DEPLOYMENT_MODE": "development", "SCADA_ALLOWED_NETWORKS": ""},
    ) == ["127.0.0.1"]


def test_field_target_requires_allowlist_and_rejects_outside_address(monkeypatch):
    _resolve_to(monkeypatch, "10.20.1.8")
    with pytest.raises(ScadaNetworkPolicyError, match="必须配置"):
        validate_scada_target(
            "scada.local",
            {"DEPLOYMENT_MODE": "field", "SCADA_ALLOWED_NETWORKS": ""},
        )
    with pytest.raises(ScadaNetworkPolicyError, match="不在允许网段"):
        validate_scada_target(
            "scada.local",
            {"DEPLOYMENT_MODE": "field", "SCADA_ALLOWED_NETWORKS": "10.30.0.0/16"},
        )
    assert validate_scada_target(
        "scada.local",
        {"DEPLOYMENT_MODE": "field", "SCADA_ALLOWED_NETWORKS": "10.20.0.0/16"},
    ) == ["10.20.1.8"]


def test_metadata_endpoint_is_always_blocked(monkeypatch):
    _resolve_to(monkeypatch, "169.254.169.254")
    with pytest.raises(ScadaNetworkPolicyError, match="元数据"):
        validate_scada_target(
            "169.254.169.254",
            {"DEPLOYMENT_MODE": "development", "SCADA_ALLOWED_NETWORKS": ""},
        )


def test_field_manager_requires_worker_secret_and_backend_url(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "field")
    monkeypatch.setenv("SCADA_REALTIME_ENABLED", "true")
    monkeypatch.delenv("SCADA_WORKER_SECRET", raising=False)
    monkeypatch.delenv("SCADA_BACKEND_URL", raising=False)
    with pytest.raises(RuntimeError, match="SCADA_WORKER_SECRET"):
        validate_runtime_config()

    monkeypatch.setenv("SCADA_WORKER_SECRET", "test-secret")
    with pytest.raises(RuntimeError, match="SCADA_BACKEND_URL"):
        validate_runtime_config()

    monkeypatch.setenv("SCADA_BACKEND_URL", "http://backend:5000")
    validate_runtime_config()
