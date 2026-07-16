import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from routes.report_management_router import (
    _read_report_config_meta,
    _read_report_config_meta_payload,
    _upsert_report_config_meta,
)
from services.weather_connection_security import (
    apply_connection_secrets,
    build_connection_config,
    serialize_connection_secret_state,
)
from utils.credential_cipher import (
    CredentialConfigurationError,
    CredentialDecryptionError,
    ENCRYPTED_PREFIX,
    decrypt_secret,
    encrypt_secret,
    is_encrypted_secret,
    resolve_encryption_secret,
)


PRIMARY_KEY = "a-secure-credential-key-with-more-than-32-characters"
SECONDARY_KEY = "another-secure-credential-key-with-adequate-length"


@pytest.fixture(autouse=True)
def credential_environment(monkeypatch):
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", PRIMARY_KEY)
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY_FILE", raising=False)


def test_secret_round_trip_is_encrypted_and_idempotent():
    encrypted = encrypt_secret("weather-source-password")

    assert encrypted.startswith(ENCRYPTED_PREFIX)
    assert "weather-source-password" not in encrypted
    assert is_encrypted_secret(encrypted) is True
    assert encrypt_secret(encrypted) == encrypted
    assert decrypt_secret(encrypted) == "weather-source-password"


def test_decrypt_rejects_wrong_key(monkeypatch):
    encrypted = encrypt_secret("weather-source-password")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", SECONDARY_KEY)

    with pytest.raises(CredentialDecryptionError, match="凭据解密失败"):
        decrypt_secret(encrypted)


def test_tampered_prefixed_value_is_not_accepted_as_existing_ciphertext():
    with pytest.raises(CredentialDecryptionError):
        encrypt_secret(f"{ENCRYPTED_PREFIX}tampered")


def test_plaintext_values_remain_readable_during_migration_window():
    assert decrypt_secret("legacy-plaintext") == "legacy-plaintext"
    assert decrypt_secret("") == ""
    assert decrypt_secret(None) is None


@pytest.mark.parametrize(
    "value",
    ["", "too-short", "change-me-in-production"],
)
def test_invalid_direct_key_is_rejected(monkeypatch, value):
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", value)

    with pytest.raises(CredentialConfigurationError):
        resolve_encryption_secret()


def test_key_file_is_supported(monkeypatch, tmp_path):
    key_path = tmp_path / "credential.key"
    key_path.write_text(PRIMARY_KEY, encoding="utf-8")
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY_FILE", str(key_path))

    assert resolve_encryption_secret() == PRIMARY_KEY
    assert decrypt_secret(encrypt_secret("file-backed-secret")) == "file-backed-secret"


def test_direct_key_and_key_file_cannot_be_combined(monkeypatch, tmp_path):
    key_path = tmp_path / "credential.key"
    key_path.write_text(SECONDARY_KEY, encoding="utf-8")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY_FILE", str(key_path))

    with pytest.raises(CredentialConfigurationError, match="不能同时设置"):
        resolve_encryption_secret()


def test_weather_connection_secrets_are_masked_preserved_and_decrypted():
    connection = SimpleNamespace(
        host="10.0.0.8",
        port=22,
        username="forecast",
        auth_type="password",
        password=None,
        private_key_path="/keys/forecast",
        key_passphrase=None,
    )

    apply_connection_secrets(
        connection,
        {"password": "sftp-password", "key_passphrase": "key-passphrase"},
    )
    encrypted_password = connection.password

    assert is_encrypted_secret(connection.password)
    assert is_encrypted_secret(connection.key_passphrase)
    assert serialize_connection_secret_state(connection) == {
        "password_set": True,
        "key_passphrase_set": True,
    }
    assert build_connection_config(connection) == {
        "host": "10.0.0.8",
        "port": 22,
        "username": "forecast",
        "auth_type": "password",
        "password": "sftp-password",
        "private_key_path": "/keys/forecast",
        "key_passphrase": "key-passphrase",
    }

    apply_connection_secrets(connection, {"password": ""})
    assert connection.password == encrypted_password

    apply_connection_secrets(connection, {"clear_password": True})
    assert connection.password is None


class _MetaQuery:
    def __init__(self, meta):
        self.meta = meta

    def filter(self, *args):
        return self

    def first(self):
        return self.meta


class _MetaSession:
    def __init__(self, meta=None):
        self.meta = meta
        self.added = []

    def query(self, model):
        return _MetaQuery(self.meta)

    def add(self, value):
        self.added.append(value)
        self.meta = value


def test_report_meta_never_returns_password_and_partial_update_preserves_it():
    meta = SimpleNamespace(
        payload=json.dumps(
            {
                "protocol_type": "sftp",
                "server_username": "forecast",
                "server_password": encrypt_secret("report-password"),
                "remote_directory": "/old",
            }
        ),
        updated_at=None,
    )
    session = _MetaSession(meta)

    response_payload = _read_report_config_meta(meta)
    assert response_payload["server_password_set"] is True
    assert "server_password" not in response_payload

    original_password = _read_report_config_meta_payload(meta)["server_password"]
    _upsert_report_config_meta(session, 7, {"remote_directory": "/new"})
    updated_payload = _read_report_config_meta_payload(meta)

    assert updated_payload["server_password"] == original_password
    assert updated_payload["remote_directory"] == "/new"


def test_report_meta_encrypts_replacement_and_supports_explicit_clear():
    meta = SimpleNamespace(payload="{}", updated_at=None)
    session = _MetaSession(meta)

    _upsert_report_config_meta(
        session,
        8,
        {"server_password": "replacement-password"},
    )
    encrypted = _read_report_config_meta_payload(meta)["server_password"]
    assert is_encrypted_secret(encrypted)
    assert decrypt_secret(encrypted) == "replacement-password"

    _upsert_report_config_meta(session, 8, {"clear_server_password": True})
    assert "server_password" not in _read_report_config_meta_payload(meta)
    assert _read_report_config_meta(meta)["server_password_set"] is False


def test_frontend_sources_do_not_persist_or_rehydrate_secret_values():
    frontend_root = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components"
    report_source = (frontend_root / "ReportManagement.vue").read_text(encoding="utf-8")
    weather_source = (frontend_root / "WeatherDataFetcher.vue").read_text(encoding="utf-8")

    assert "storedMeta.server_password" not in report_source
    assert "server_password: payload.server_password" not in report_source
    assert "password: row.password" not in weather_source
    assert "key_passphrase: row.key_passphrase" not in weather_source


def test_deployment_contract_requires_independent_credential_key():
    project_root = Path(__file__).resolve().parents[2]
    compose_source = (project_root / "deploy" / "docker-compose.prod.yaml").read_text(
        encoding="utf-8"
    )
    validator_source = (project_root / "deploy" / "validate-field-config.sh").read_text(
        encoding="utf-8"
    )
    local_start_source = (project_root / "start-local.bat").read_text(encoding="utf-8")

    assert "CREDENTIAL_ENCRYPTION_KEY=${CREDENTIAL_ENCRYPTION_KEY:-}" in compose_source
    assert "require_secret CREDENTIAL_ENCRYPTION_KEY 32" in validator_source
    assert "CREDENTIAL_ENCRYPTION_KEY_FILE" in validator_source
    assert "LOCAL_CREDENTIAL_ENCRYPTION_KEY" in local_start_source


def test_legacy_deployment_entries_do_not_embed_fixed_operator_passwords():
    project_root = Path(__file__).resolve().parents[2]
    source_paths = [
        project_root / "database" / "docker-compose.yaml",
        project_root / "linux_frontend-backend-compose.yaml",
        project_root / "local-images.yaml",
        project_root / "kingbase-init.sh",
        project_root / "db_connection_check.py",
        project_root / "backend" / "check_db.py",
        project_root / "backend" / "test_db_connection.py",
    ]
    combined_source = "\n".join(
        path.read_text(encoding="utf-8") for path in source_paths
    )

    assert "yzz0216yh" not in combined_source
    assert "PGADMIN_DEFAULT_PASSWORD: admin" not in combined_source
    assert "os.environ.get('DB_PASSWORD', '12345678ab')" not in combined_source
    assert "PGPASSWORD=12345678ab" not in combined_source


def test_security_migration_encrypts_existing_plaintext_rows():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260716_02_encrypt_credentials.py"
    )
    spec = importlib.util.spec_from_file_location("encrypt_credentials_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE report_config_meta ("
                "id INTEGER PRIMARY KEY, payload TEXT, updated_at DATETIME)"
            )
        )
        connection.execute(
            sa.text(
                "CREATE TABLE weather_connections ("
                "id INTEGER PRIMARY KEY, password TEXT, key_passphrase TEXT)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO report_config_meta (id, payload) "
                "VALUES (1, :payload)"
            ),
            {"payload": json.dumps({"server_password": "legacy-report-password"})},
        )
        connection.execute(
            sa.text(
                "INSERT INTO weather_connections (id, password, key_passphrase) "
                "VALUES (1, 'legacy-weather-password', 'legacy-key-passphrase')"
            )
        )

        migration._encrypt_report_credentials(connection)
        migration._encrypt_weather_credentials(connection)

        report_payload = json.loads(
            connection.execute(
                sa.text("SELECT payload FROM report_config_meta WHERE id = 1")
            ).scalar_one()
        )
        weather_row = connection.execute(
            sa.text(
                "SELECT password, key_passphrase FROM weather_connections WHERE id = 1"
            )
        ).mappings().one()

    assert decrypt_secret(report_payload["server_password"]) == "legacy-report-password"
    assert decrypt_secret(weather_row["password"]) == "legacy-weather-password"
    assert decrypt_secret(weather_row["key_passphrase"]) == "legacy-key-passphrase"
