from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models import ModelVersion
from services import model_registry as registry_module


@pytest.fixture()
def registry_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    ModelVersion.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def test_db_session():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(registry_module, "db_session", test_db_session)
    monkeypatch.setenv("DEPLOYMENT_MODE", "field")
    monkeypatch.setenv("MODEL_AUTO_APPROVAL_ENABLED", "false")
    return factory


def _register_candidate(tmp_path, registry, suffix, accuracy=0.9):
    model_path = tmp_path / f"model-{suffix}.bin"
    dataset_path = tmp_path / f"dataset-{suffix}.csv"
    model_path.write_bytes(f"model:{suffix}".encode("utf-8"))
    dataset_path.write_text(f"time,power\n{suffix},1\n", encoding="utf-8")
    result = registry.register(
        farm_code="WF001",
        task_type="supershort",
        algorithm="xgboost",
        model_path=str(model_path),
        dataset_path=str(dataset_path),
        val_accuracy=accuracy,
        val_rmse=1.2,
        feature_cols=["wind_speed", "power"],
        feature_contract_version="forecast-feature-v1",
    )
    return result, model_path


def test_field_mode_registration_requires_manual_approval(tmp_path, registry_db):
    registry = registry_module.ModelRegistry()
    registered, model_path = _register_candidate(tmp_path, registry, "a")

    assert registered["lifecycle_status"] == "candidate"
    assert registered["is_active"] is False
    assert len(registered["artifact_sha256"]) == 64
    assert len(registered["dataset_version"]) == 64

    approved = registry.approve(registered["id"], "model-admin")
    assert approved == {"id": registered["id"], "status": "approved", "active": True}

    with registry_db() as session:
        stored = session.get(ModelVersion, registered["id"])
        assert stored.lifecycle_status == "approved"
        assert stored.approved_by == "model-admin"
        assert stored.is_active is True
        assert stored.artifact_sha256 == registry_module._sha256_file(str(model_path))


def test_reject_and_rollback_are_auditable(tmp_path, registry_db):
    registry = registry_module.ModelRegistry()
    first, _ = _register_candidate(tmp_path, registry, "first", accuracy=0.91)
    second, _ = _register_candidate(tmp_path, registry, "second", accuracy=0.92)
    rejected, _ = _register_candidate(tmp_path, registry, "rejected", accuracy=0.93)

    registry.approve(first["id"], "reviewer-a")
    registry.approve(second["id"], "reviewer-b")
    reject_result = registry.reject(rejected["id"], "reviewer-b", "离线回放偏差超限")
    assert reject_result["status"] == "rejected"

    rollback_result = registry.rollback_to(first["id"], "duty-operator")
    assert rollback_result["active"] is True

    with registry_db() as session:
        first_row = session.get(ModelVersion, first["id"])
        second_row = session.get(ModelVersion, second["id"])
        rejected_row = session.get(ModelVersion, rejected["id"])
        assert first_row.is_active is True
        assert second_row.is_active is False
        assert rejected_row.lifecycle_status == "rejected"
        assert "离线回放偏差超限" in rejected_row.rejection_reason


def test_approval_rejects_tampered_artifact(tmp_path, registry_db):
    registry = registry_module.ModelRegistry()
    registered, model_path = _register_candidate(tmp_path, registry, "tampered")
    model_path.write_bytes(b"changed-after-registration")

    with pytest.raises(ValueError, match="摘要"):
        registry.approve(registered["id"], "model-admin")
