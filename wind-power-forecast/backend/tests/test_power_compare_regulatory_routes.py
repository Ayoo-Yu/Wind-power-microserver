from flask import Flask

from routes.power_compare import bp


def _app():
    app = Flask(__name__)
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


def test_regulatory_metrics_route_limits_synchronous_range():
    client = _app().test_client()

    response = client.post(
        "/api/v1/power-compare/regulatory_metrics",
        json={"start": "2026-01-01", "end": "2026-02-01"},
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "date range must not exceed 31 days"
