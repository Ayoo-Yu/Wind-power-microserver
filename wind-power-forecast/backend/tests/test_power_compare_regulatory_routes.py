from contextlib import contextmanager
from types import SimpleNamespace

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

from routes.power_compare import bp
from utils import authorization


class _Query:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return SimpleNamespace(
            id="1",
            username="operator",
            is_active=True,
            role=SimpleNamespace(
                name="运行操作人员",
                permissions={"permissions": ["view_all_data"]},
            ),
        )


class _Session:
    def query(self, model):
        return _Query()


def _app():
    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = "power-compare-route-test-secret"
    JWTManager(app)
    app.register_blueprint(bp)
    app.register_blueprint(
        bp,
        url_prefix="/api/v1/power-compare",
        name="power_compare_v1",
    )
    return app


def test_regulatory_metrics_route_keeps_legacy_and_v1_paths():
    rules = {rule.rule for rule in _app().url_map.iter_rules()}

    assert "/power-compare/regulatory_metrics" in rules
    assert "/api/v1/power-compare/regulatory_metrics" in rules


def test_regulatory_metrics_route_limits_synchronous_range(monkeypatch):
    @contextmanager
    def fake_db_session():
        yield _Session()

    monkeypatch.setattr(authorization, "db_session", fake_db_session)
    app = _app()
    with app.app_context():
        token = create_access_token(identity="1")

    response = app.test_client().post(
        "/api/v1/power-compare/regulatory_metrics",
        json={"start": "2026-01-01", "end": "2026-02-01"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "date range must not exceed 31 days"


def test_power_data_requires_object_body_and_farm_code(monkeypatch):
    @contextmanager
    def fake_db_session():
        yield _Session()

    monkeypatch.setattr(authorization, "db_session", fake_db_session)
    app = _app()
    with app.app_context():
        token = create_access_token(identity="1")
    headers = {"Authorization": f"Bearer {token}"}

    malformed = app.test_client().post(
        "/api/v1/power-compare/data",
        json="invalid-body",
        headers=headers,
    )
    missing_farm = app.test_client().post(
        "/api/v1/power-compare/data",
        json={
            "start": "2026-07-15T00:00:00",
            "end": "2026-07-15T01:00:00",
            "types": ["实测值"],
        },
        headers=headers,
    )

    assert malformed.status_code == 400
    assert missing_farm.status_code == 400
    assert "场站编码" in missing_farm.get_json()["error"]
