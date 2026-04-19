# tests/test_extreme_weather_api.py
"""Tests for the extreme weather API blueprint.

Covers: GET /thresholds, PUT /thresholds, GET /status, GET /history.
Uses a fresh Flask app with only the extreme_weather blueprint registered
so no database or external services are required.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask

from routes.extreme_weather_router import extreme_weather_bp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Create a minimal Flask app with the extreme_weather blueprint."""
    app = Flask(__name__)
    app.register_blueprint(extreme_weather_bp, url_prefix="/api/extreme-weather")
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app):
    """Return a test client for the app."""
    return app.test_client()


# ---------------------------------------------------------------------------
# GET /api/extreme-weather/thresholds
# ---------------------------------------------------------------------------

class TestGetThresholds:
    """GET /api/extreme-weather/thresholds returns current detection thresholds."""

    EXPECTED_KEYS = {
        "high_wind_speed",
        "typhoon_speed",
        "calm_wind_speed",
        "cold_wave_temp",
        "cold_wave_drop_24h",
        "icing_temp_low",
        "icing_temp_high",
        "icing_tcwv",
    }

    def test_returns_200(self, client):
        resp = client.get("/api/extreme-weather/thresholds")
        assert resp.status_code == 200

    def test_returns_all_eight_threshold_keys(self, client):
        resp = client.get("/api/extreme-weather/thresholds")
        data = resp.get_json()
        assert set(data.keys()) == self.EXPECTED_KEYS

    def test_values_are_numbers(self, client):
        resp = client.get("/api/extreme-weather/thresholds")
        data = resp.get_json()
        for key in self.EXPECTED_KEYS:
            assert isinstance(data[key], (int, float)), f"{key} should be numeric"


# ---------------------------------------------------------------------------
# PUT /api/extreme-weather/thresholds
# ---------------------------------------------------------------------------

class TestPutThresholds:
    """PUT /api/extreme-weather/thresholds updates threshold values."""

    def test_valid_update_returns_200(self, client):
        resp = client.put(
            "/api/extreme-weather/thresholds",
            data=json.dumps({"high_wind_speed": 30.0}),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_updated_value_reflected_in_response(self, client):
        resp = client.put(
            "/api/extreme-weather/thresholds",
            data=json.dumps({"high_wind_speed": 30.0}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["high_wind_speed"] == 30.0

    def test_invalid_key_is_ignored(self, client):
        # First get original thresholds
        orig = client.get("/api/extreme-weather/thresholds").get_json()

        # Attempt to update a non-existent key
        resp = client.put(
            "/api/extreme-weather/thresholds",
            data=json.dumps({"nonexistent_key": 999.0}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "nonexistent_key" not in data
        # Original values unchanged
        for key in orig:
            assert data[key] == orig[key]

    def test_multiple_keys_updated(self, client):
        resp = client.put(
            "/api/extreme-weather/thresholds",
            data=json.dumps({"calm_wind_speed": 5.0, "icing_tcwv": 20.0}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["calm_wind_speed"] == 5.0
        assert data["icing_tcwv"] == 20.0

    def test_string_value_converted_to_float(self, client):
        resp = client.put(
            "/api/extreme-weather/thresholds",
            data=json.dumps({"typhoon_speed": "40.5"}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["typhoon_speed"] == 40.5


# ---------------------------------------------------------------------------
# GET /api/extreme-weather/status
# ---------------------------------------------------------------------------

class TestGetStatus:
    """GET /api/extreme-weather/status returns current weather condition."""

    def test_returns_200_with_farm_code(self, client):
        resp = client.get("/api/extreme-weather/status?farm_code=zyx01")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        resp = client.get("/api/extreme-weather/status?farm_code=zyx01")
        data = resp.get_json()
        assert "farm_code" in data
        assert "current_condition" in data
        assert "active_alerts" in data
        assert "last_checked" in data

    def test_condition_fields(self, client):
        resp = client.get("/api/extreme-weather/status?farm_code=zyx01")
        data = resp.get_json()
        cond = data["current_condition"]
        assert "type" in cond
        assert "severity" in cond
        assert "details" in cond

    def test_default_farm_code(self, client):
        resp = client.get("/api/extreme-weather/status")
        data = resp.get_json()
        assert data["farm_code"] == "DEFAULT_FARM"

    def test_custom_farm_code(self, client):
        resp = client.get("/api/extreme-weather/status?farm_code=zyx01")
        data = resp.get_json()
        assert data["farm_code"] == "zyx01"


# ---------------------------------------------------------------------------
# GET /api/extreme-weather/history
# ---------------------------------------------------------------------------

class TestGetHistory:
    """GET /api/extreme-weather/history returns paginated event list."""

    def test_returns_200(self, client):
        resp = client.get("/api/extreme-weather/history")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        resp = client.get("/api/extreme-weather/history")
        data = resp.get_json()
        assert "events" in data
        assert "page" in data
        assert "per_page" in data
        assert isinstance(data["events"], list)

    def test_default_pagination(self, client):
        resp = client.get("/api/extreme-weather/history")
        data = resp.get_json()
        assert data["page"] == 1
        assert data["per_page"] == 20

    def test_custom_pagination(self, client):
        resp = client.get("/api/extreme-weather/history?page=2&per_page=50")
        data = resp.get_json()
        assert data["page"] == 2
        assert data["per_page"] == 50

    def test_custom_farm_code(self, client):
        resp = client.get("/api/extreme-weather/history?farm_code=zyx01")
        data = resp.get_json()
        assert "events" in data
