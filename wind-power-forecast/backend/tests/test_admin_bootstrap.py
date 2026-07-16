from pathlib import Path
from types import SimpleNamespace

import pytest

from init_users import init_admin_user
from utils.admin_password import (
    AdminPasswordConfigurationError,
    load_admin_password,
    validate_admin_password,
)
from utils.password_utils import verify_password


class _QueryResult:
    def __init__(self, value):
        self.value = value

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.value


class _BootstrapSession:
    def __init__(self, query_values):
        self.query_values = list(query_values)
        self.added = []
        self.committed = False

    def query(self, model):
        return _QueryResult(self.query_values.pop(0))

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.committed = True


def test_admin_password_rejects_defaults_and_short_values():
    for value in ("admin123", "12345678ab", "change-me-in-production", "too-short"):
        with pytest.raises(AdminPasswordConfigurationError):
            validate_admin_password(value)


def test_admin_password_accepts_long_non_default_value():
    value = "Field.Admin.2026!Safe"

    assert validate_admin_password(value) == value


def test_load_admin_password_from_environment():
    value = "Field.Admin.2026!Safe"

    assert load_admin_password(
        "BOOTSTRAP_ADMIN_PASSWORD",
        "BOOTSTRAP_ADMIN_PASSWORD_FILE",
        environ={"BOOTSTRAP_ADMIN_PASSWORD": value},
    ) == value


def test_load_admin_password_from_utf8_file(tmp_path):
    password_file = tmp_path / "admin-password.txt"
    password_file.write_text("场站.Admin.2026!Safe\n", encoding="utf-8")

    assert load_admin_password(
        "BOOTSTRAP_ADMIN_PASSWORD",
        "BOOTSTRAP_ADMIN_PASSWORD_FILE",
        environ={"BOOTSTRAP_ADMIN_PASSWORD_FILE": str(password_file)},
    ) == "场站.Admin.2026!Safe"


def test_load_admin_password_requires_exactly_one_source(tmp_path):
    password_file = tmp_path / "admin-password.txt"
    password_file.write_text("Field.Admin.2026!Safe", encoding="utf-8")

    with pytest.raises(AdminPasswordConfigurationError):
        load_admin_password(
            "BOOTSTRAP_ADMIN_PASSWORD",
            "BOOTSTRAP_ADMIN_PASSWORD_FILE",
            environ={},
        )
    with pytest.raises(AdminPasswordConfigurationError):
        load_admin_password(
            "BOOTSTRAP_ADMIN_PASSWORD",
            "BOOTSTRAP_ADMIN_PASSWORD_FILE",
            environ={
                "BOOTSTRAP_ADMIN_PASSWORD": "Field.Admin.2026!Safe",
                "BOOTSTRAP_ADMIN_PASSWORD_FILE": str(password_file),
            },
        )


def test_existing_admin_is_never_reset_when_bootstrap_secret_is_absent(monkeypatch):
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD_FILE", raising=False)
    session = _BootstrapSession([SimpleNamespace(username="admin")])

    init_admin_user(session)

    assert session.added == []
    assert session.committed is False


def test_new_admin_requires_explicit_bootstrap_secret(monkeypatch):
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD_FILE", raising=False)
    session = _BootstrapSession([None, SimpleNamespace(id=7)])

    with pytest.raises(AdminPasswordConfigurationError):
        init_admin_user(session)

    assert session.added == []
    assert session.committed is False


def test_new_admin_uses_explicit_secret_without_logging_or_defaults():
    password = "Field.Admin.2026!Safe"
    session = _BootstrapSession([None, SimpleNamespace(id=7)])

    init_admin_user(session, password=password)

    assert session.committed is True
    assert len(session.added) == 1
    assert session.added[0].username == "admin"
    assert verify_password(password, session.added[0].password_hash) is True


def test_production_entrypoints_do_not_reset_admin_automatically():
    project_root = Path(__file__).resolve().parents[2]
    for relative_path in ("deploy/backend-entrypoint.sh", "backend/docker-entrypoint.sh"):
        content = (project_root / relative_path).read_text(encoding="utf-8")
        assert "python -m reset_admin" not in content
        assert "admin_initialized.flag" not in content
