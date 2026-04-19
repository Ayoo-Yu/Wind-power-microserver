# routes/extreme_weather_router.py
"""Flask Blueprint for extreme weather detection API endpoints.

Provides endpoints to manage detection thresholds, query current weather
status, and retrieve historical extreme weather events.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, jsonify, request

from services.extreme_weather_detector import DEFAULT_THRESHOLDS, ExtremeWeatherDetector

logger = logging.getLogger(__name__)

# Module-level detector instance (uses default thresholds initially).
_detector = ExtremeWeatherDetector()

extreme_weather_bp = Blueprint("extreme_weather", __name__)


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


def _get_alarm_history(
    farm_code: str, page: int, per_page: int
) -> list[dict[str, Any]]:
    """Return historical extreme weather alarm events.

    Stub implementation -- returns an empty list until database
    integration is wired up.
    """
    logger.debug(
        "Fetching alarm history: farm_code=%s page=%d per_page=%d",
        farm_code,
        page,
        per_page,
    )
    return []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@extreme_weather_bp.route("/thresholds", methods=["GET"])
def get_thresholds() -> tuple[dict[str, float], int]:
    """Return current detection thresholds as JSON."""
    logger.debug("GET /thresholds")
    return jsonify(_detector.thresholds), 200


@extreme_weather_bp.route("/thresholds", methods=["PUT"])
def update_thresholds() -> tuple[dict[str, float], int]:
    """Update thresholds from a JSON body.

    Only keys that already exist in the thresholds dict are accepted.
    Values are converted to float; invalid values are silently skipped.
    """
    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    updated: dict[str, float] = {}
    current = _detector.thresholds

    for key, value in body.items():
        if key not in current:
            logger.debug("Ignoring unknown threshold key: %s", key)
            continue
        try:
            converted = float(value)
        except (TypeError, ValueError):
            logger.warning("Invalid value for %s: %r -- skipping", key, value)
            continue
        current[key] = converted
        updated[key] = converted

    logger.info("Updated thresholds: %s", updated)
    return jsonify(_detector.thresholds), 200


@extreme_weather_bp.route("/status", methods=["GET"])
def get_status() -> tuple[dict[str, Any], int]:
    """Return current weather condition for a farm.

    Query parameters
    ----------------
    farm_code : str, optional
        Wind farm identifier (default ``"DEFAULT_FARM"``).
    """
    farm_code: str = request.args.get("farm_code", "DEFAULT_FARM")

    # Placeholder response until live data feed is connected.
    payload: dict[str, Any] = {
        "farm_code": farm_code,
        "current_condition": {
            "type": "normal",
            "severity": "info",
            "details": {},
        },
        "active_alerts": 0,
        "last_checked": None,
    }

    logger.debug("GET /status farm_code=%s", farm_code)
    return jsonify(payload), 200


@extreme_weather_bp.route("/history", methods=["GET"])
def get_history() -> tuple[dict[str, Any], int]:
    """Return paginated historical extreme weather events.

    Query parameters
    ----------------
    farm_code : str, optional
        Wind farm identifier (default ``"DEFAULT_FARM"``).
    page : int, optional
        Page number (default 1).
    per_page : int, optional
        Items per page (default 20).
    """
    farm_code: str = request.args.get("farm_code", "DEFAULT_FARM")
    try:
        page: int = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page: int = max(1, int(request.args.get("per_page", 20)))
    except (TypeError, ValueError):
        per_page = 20

    events = _get_alarm_history(farm_code, page, per_page)

    payload: dict[str, Any] = {
        "events": events,
        "page": page,
        "per_page": per_page,
    }

    logger.debug(
        "GET /history farm_code=%s page=%d per_page=%d",
        farm_code,
        page,
        per_page,
    )
    return jsonify(payload), 200
