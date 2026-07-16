from contextlib import contextmanager

from flask import Flask

from routes import health_router
from services.health_service import (
    build_liveness_status,
    build_readiness_status,
    is_ready,
)


class _Session:
    def __init__(self, engine):
        self.engine = engine
        self.executed = []

    def execute(self, statement):
        self.executed.append(str(statement))

    def get_bind(self):
        return self.engine


def _session_factory(session):
    @contextmanager
    def factory():
        yield session

    return factory


def test_liveness_does_not_depend_on_database():
    status = build_liveness_status()

    assert status["status"] == "ok"
    assert status["liveness"] == "ok"
    assert "database" not in status


def test_readiness_requires_database_and_current_schema():
    engine = object()
    session = _Session(engine)

    status = build_readiness_status(
        session_factory=_session_factory(session),
        schema_inspector=lambda value: {"state": "ready", "ready": True},
        engine_invalidator=lambda: None,
    )

    assert is_ready(status) is True
    assert status["database"] == "ok"
    assert status["schema"] == "ok"
    assert status["schema_state"] == "ready"
    assert session.executed == ["SELECT 1"]


def test_readiness_returns_error_and_invalidates_pool_when_database_is_down():
    invalidations = []

    @contextmanager
    def unavailable_session():
        raise RuntimeError("database connection unavailable")
        yield

    status = build_readiness_status(
        session_factory=unavailable_session,
        schema_inspector=lambda engine: {"state": "ready", "ready": True},
        engine_invalidator=lambda: invalidations.append(True),
    )

    assert is_ready(status) is False
    assert status["status"] == "error"
    assert status["database"] == "error"
    assert status["reason"] == "database_unavailable"
    assert invalidations == [True]


def test_readiness_rejects_pending_schema_even_when_database_connects():
    status = build_readiness_status(
        session_factory=_session_factory(_Session(object())),
        schema_inspector=lambda engine: {"state": "pending", "ready": False},
        schema_message_builder=lambda value: "数据库存在待执行迁移",
        engine_invalidator=lambda: None,
    )

    assert is_ready(status) is False
    assert status["database"] == "ok"
    assert status["schema"] == "error"
    assert status["schema_state"] == "pending"
    assert status["reason"] == "schema_pending"


def test_health_routes_use_http_status_to_express_readiness(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(health_router.health_bp)
    client = app.test_client()

    monkeypatch.setattr(
        health_router,
        "build_readiness_status",
        lambda: {
            "status": "error",
            "liveness": "ok",
            "readiness": "error",
            "database": "error",
        },
    )

    legacy = client.get("/health")
    explicit = client.get("/health/ready")
    versioned = client.get("/api/v1/health")
    live = client.get("/health/live")

    assert legacy.status_code == 503
    assert explicit.status_code == 503
    assert legacy.get_json()["database"] == "error"
    assert versioned.status_code == 503
    assert versioned.get_json()["code"] == 1503
    assert live.status_code == 200
    assert live.get_json()["liveness"] == "ok"
    assert legacy.headers["Cache-Control"] == "no-store, max-age=0"


def test_health_routes_return_200_after_readiness_recovers(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(health_router.health_bp)
    monkeypatch.setattr(
        health_router,
        "build_readiness_status",
        lambda: {
            "status": "ok",
            "liveness": "ok",
            "readiness": "ok",
            "database": "ok",
            "schema": "ok",
        },
    )

    response = app.test_client().get("/health/ready")

    assert response.status_code == 200
    assert response.get_json()["database"] == "ok"
