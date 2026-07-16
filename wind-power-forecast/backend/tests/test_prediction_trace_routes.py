from contextlib import contextmanager
from types import SimpleNamespace

from flask import Flask, g
from flask_jwt_extended import JWTManager, create_access_token
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models.auth_extensions import OperationAuditLog
from db_models.prediction_run import PredictionRun
from db_models.prediction_task import PredictionTask
from routes import auth_extensions, autopredict


def _app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        JWT_SECRET_KEY="prediction-trace-route-secret",
    )
    JWTManager(app)
    return app


def _token(app):
    with app.app_context():
        return create_access_token(identity="1")


def _database():
    engine = create_engine("sqlite:///:memory:")
    PredictionTask.__table__.create(engine)
    PredictionRun.__table__.create(engine)
    OperationAuditLog.__table__.create(engine)
    factory = sessionmaker(bind=engine)

    @contextmanager
    def scope():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return engine, factory, scope


class _CeleryTask:
    def __init__(self):
        self.calls = []

    def apply_async(self, *, args, task_id):
        self.calls.append({"args": list(args), "task_id": task_id})
        return SimpleNamespace(id=task_id)


def test_manual_trigger_is_persisted_and_idempotent_before_dispatch(monkeypatch):
    engine, factory, scope = _database()
    app = _app()
    app.register_blueprint(autopredict.autopredict_bp, url_prefix="/autopredict")

    def allow_request(permission):
        g.acting_username = "operator"
        return None

    fake_task = _CeleryTask()
    monkeypatch.setattr(autopredict, "enforce_permission", allow_request)
    monkeypatch.setattr(autopredict, "db_session", scope)
    monkeypatch.setattr(
        autopredict,
        "_get_celery_tasks",
        lambda: (fake_task, fake_task, fake_task),
    )

    with scope() as session:
        session.add(PredictionTask(
            farm_code="WF001",
            task_type="short",
            enabled=True,
        ))

    headers = {
        "Authorization": f"Bearer {_token(app)}",
        "Idempotency-Key": "operator-click-1",
        "X-Request-ID": "request-1",
    }
    client = app.test_client()
    first = client.post(
        "/autopredict/trigger",
        json={"farm_code": "WF001", "type": "short", "action": "predict"},
        headers=headers,
    )
    repeated = client.post(
        "/autopredict/trigger",
        json={"farm_code": "WF001", "type": "short", "action": "predict"},
        headers=headers,
    )

    assert first.status_code == 200
    assert first.get_json()["data"]["status"] == "queued"
    assert repeated.status_code == 200
    assert repeated.get_json()["data"]["deduplicated"] is True
    assert len(fake_task.calls) == 1

    with factory() as session:
        run = session.query(PredictionRun).one()
        audit = session.query(OperationAuditLog).one()
        assert run.status == "queued"
        assert run.requested_by == "operator"
        assert run.trigger_source == "manual_api"
        assert run.request_id == "request-1"
        assert audit.source == "server"
        assert audit.operator == "operator"
        assert audit.request_id == "request-1"

    engine.dispose()


def test_manual_trigger_rejects_missing_task_configuration(monkeypatch):
    engine, factory, scope = _database()
    app = _app()
    app.register_blueprint(autopredict.autopredict_bp, url_prefix="/autopredict")

    def allow_request(permission):
        g.acting_username = "operator"
        return None

    fake_task = _CeleryTask()
    monkeypatch.setattr(autopredict, "enforce_permission", allow_request)
    monkeypatch.setattr(autopredict, "db_session", scope)
    monkeypatch.setattr(
        autopredict,
        "_get_celery_tasks",
        lambda: (fake_task, fake_task, fake_task),
    )

    response = app.test_client().post(
        "/autopredict/trigger",
        json={"farm_code": "MISSING", "type": "short", "action": "predict"},
        headers={"Authorization": f"Bearer {_token(app)}"},
    )

    assert response.status_code == 404
    assert fake_task.calls == []
    with factory() as session:
        audit = session.query(OperationAuditLog).one()
        assert audit.source == "server"
        assert audit.result == "失败"
        assert "MISSING/short" in audit.details
    engine.dispose()


def test_client_audit_cannot_forge_operator_or_ip(monkeypatch):
    engine, factory, scope = _database()
    app = _app()
    app.register_blueprint(auth_extensions.auth_extensions_bp, url_prefix="/auth")
    current_user = SimpleNamespace(username="real-operator")

    monkeypatch.setattr(auth_extensions, "db_session", scope)
    monkeypatch.setattr(auth_extensions, "_ensure_extension_tables", lambda session: None)
    monkeypatch.setattr(auth_extensions, "_get_current_user", lambda session: current_user)

    response = app.test_client().post(
        "/auth/audit-logs",
        json={
            "operator": "forged-admin",
            "ipAddress": "203.0.113.9",
            "module": "用户管理",
            "operationType": "修改",
            "details": "客户端补充说明",
            "result": "成功",
        },
        headers={
            "Authorization": f"Bearer {_token(app)}",
            "X-Request-ID": "audit-request-1",
        },
    )

    assert response.status_code == 201
    with factory() as session:
        row = session.query(OperationAuditLog).one()
        assert row.operator == "real-operator"
        assert row.ip_address == "127.0.0.1"
        assert row.source == "client"
        assert row.request_id == "audit-request-1"
        assert "forged-admin" in row.details
        assert "203.0.113.9" in row.details
    engine.dispose()
