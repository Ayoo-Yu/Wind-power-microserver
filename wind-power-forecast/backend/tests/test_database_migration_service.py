from services import database_migration_service as migration_service


class _Inspector:
    def __init__(self, tables):
        self._tables = list(tables)

    def get_table_names(self, schema=None):
        return list(self._tables)


def _patch_schema(monkeypatch, *, tables, model_tables, revisions, heads):
    monkeypatch.setattr(migration_service, "inspect", lambda engine: _Inspector(tables))
    monkeypatch.setattr(migration_service, "model_table_names", lambda: set(model_tables))
    monkeypatch.setattr(migration_service, "database_revisions", lambda engine: list(revisions))
    monkeypatch.setattr(migration_service, "migration_heads", lambda: list(heads))


def test_schema_status_ready_with_dynamic_tables(monkeypatch):
    _patch_schema(
        monkeypatch,
        tables={"users", "roles", "ecmwf_grid_cf", "alembic_version"},
        model_tables={"users", "roles"},
        revisions={"20260715_01"},
        heads={"20260715_01"},
    )

    status = migration_service.inspect_schema_status(object())

    assert status["state"] == "ready"
    assert status["ready"] is True
    assert status["missing_tables"] == []
    assert status["unmanaged_tables"] == ["ecmwf_grid_cf"]


def test_schema_status_rejects_unversioned_database(monkeypatch):
    _patch_schema(
        monkeypatch,
        tables={"users", "roles"},
        model_tables={"users", "roles"},
        revisions=set(),
        heads={"20260715_01"},
    )

    status = migration_service.inspect_schema_status(object())

    assert status["state"] == "unversioned"
    assert "prepare" in migration_service.schema_state_message(status)


def test_schema_status_reports_missing_model_tables_before_version(monkeypatch):
    _patch_schema(
        monkeypatch,
        tables={"users", "alembic_version"},
        model_tables={"users", "roles"},
        revisions={"20260715_01"},
        heads={"20260715_01"},
    )

    status = migration_service.inspect_schema_status(object())

    assert status["state"] == "drift"
    assert status["missing_tables"] == ["roles"]
