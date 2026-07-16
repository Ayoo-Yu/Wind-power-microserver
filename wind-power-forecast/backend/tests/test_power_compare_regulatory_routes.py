from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

from routes import power_compare
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


def test_power_data_returns_requested_prediction_intervals(monkeypatch):
    @contextmanager
    def fake_auth_db_session():
        yield _Session()

    @contextmanager
    def fake_route_db_session():
        yield object()

    monkeypatch.setattr(authorization, "db_session", fake_auth_db_session)
    monkeypatch.setattr(power_compare, "db_session", fake_route_db_session)
    monkeypatch.setattr(power_compare, "_query_prediction_series", lambda *args, **kwargs: [])

    def fake_interval(db, farm_code, prediction_type, bound, start_dt, end_dt):
        return [{"timestamp": start_dt.isoformat(), "power": 1.0 if bound == "lower" else 2.0}]

    monkeypatch.setattr(power_compare, "_query_prediction_interval_series", fake_interval)
    app = _app()
    with app.app_context():
        token = create_access_token(identity="1")

    response = app.test_client().post(
        "/api/v1/power-compare/data",
        json={
            "start": "2026-07-15T00:00:00",
            "end": "2026-07-15T01:00:00",
            "farm_code": "zyx",
            "types": ["短期预测区间", "中期预测区间", "超短期预测区间"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload) == {
        "短期预测下限", "短期预测上限",
        "中期预测下限", "中期预测上限",
        "超短期预测下限", "超短期预测上限",
    }
    assert payload["短期预测下限"][0]["power"] == 1.0
    assert payload["超短期预测上限"][0]["power"] == 2.0


def test_supershort_interval_uses_matching_horizon_bounds():
    target = datetime.fromisoformat("2026-07-15T01:00:00")
    records = [
        SimpleNamespace(
            timestamp=target,
            wp_pred2_lower=8.0,
            wp_pred2_upper=12.0,
        ),
        SimpleNamespace(
            timestamp=target - timedelta(minutes=15),
            wp_pred3_lower=18.0,
            wp_pred3_upper=22.0,
        ),
    ]

    class _RowsQuery:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return records

    class _RowsSession:
        def query(self, *args, **kwargs):
            return _RowsQuery()

    lower = power_compare._query_supershort_average(
        _RowsSession(), "zyx", target, target, 1, False, column_suffix="_lower"
    )
    upper = power_compare._query_supershort_average(
        _RowsSession(), "zyx", target, target, 1, False, column_suffix="_upper"
    )

    assert lower == [{"timestamp": target.isoformat(), "power": 13.0}]
    assert upper == [{"timestamp": target.isoformat(), "power": 17.0}]
