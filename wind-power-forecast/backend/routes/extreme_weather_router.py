# routes/extreme_weather_router.py
"""Flask Blueprint for extreme weather detection API endpoints.

Provides endpoints to manage detection thresholds, query current weather
status, and retrieve historical extreme weather events.
"""
from __future__ import annotations

import logging
import json
import threading
from typing import Any

from flask import Blueprint, jsonify, request

from db_session import db_session
from db_models import SystemSetting
from services.extreme_weather_detector import DEFAULT_THRESHOLDS
from utils.database_schema import require_model_tables
from utils.authorization import permission_required

logger = logging.getLogger(__name__)

_THRESHOLDS_KEY = "extreme_weather_thresholds"
_threshold_lock = threading.Lock()

extreme_weather_bp = Blueprint("extreme_weather", __name__)


# ---------------------------------------------------------------------------
# 配置与数据源辅助函数
# ---------------------------------------------------------------------------


def _ensure_settings_table(session):
    require_model_tables(session, SystemSetting.__table__)


def _load_thresholds() -> dict[str, float]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    with db_session() as session:
        _ensure_settings_table(session)
        setting = session.query(SystemSetting).filter_by(settings_key=_THRESHOLDS_KEY).first()
        if setting and setting.payload:
            parsed = json.loads(setting.payload)
            if isinstance(parsed, dict):
                thresholds.update({
                    key: float(value)
                    for key, value in parsed.items()
                    if key in DEFAULT_THRESHOLDS
                })
    return thresholds


def _save_thresholds(thresholds: dict[str, float]) -> None:
    payload = json.dumps(thresholds, ensure_ascii=False)
    with db_session() as session:
        _ensure_settings_table(session)
        setting = session.query(SystemSetting).filter_by(settings_key=_THRESHOLDS_KEY).first()
        if setting is None:
            setting = SystemSetting(settings_key=_THRESHOLDS_KEY, payload=payload)
            session.add(setting)
        else:
            setting.payload = payload


def _get_alarm_history(
    farm_code: str, page: int, per_page: int
) -> list[dict[str, Any]]:
    """Return historical extreme weather alarm events.

    当前尚未接入历史事件存储，因此调用方必须同时检查 data_available。
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
@permission_required("view_all_data")
def get_thresholds() -> tuple[dict[str, float], int]:
    """Return current detection thresholds as JSON."""
    logger.debug("GET /thresholds")
    try:
        return jsonify(_load_thresholds()), 200
    except Exception:
        logger.exception("Failed to load extreme weather thresholds")
        return jsonify(DEFAULT_THRESHOLDS), 200


@extreme_weather_bp.route("/thresholds", methods=["PUT"])
@permission_required("configure_system")
def update_thresholds() -> tuple[dict[str, float], int]:
    """Update thresholds from a JSON body.

    Only keys that already exist in the thresholds dict are accepted.
    Values are converted to float; invalid values are silently skipped.
    """
    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    # Validate individual values
    MIN_BOUNDS: dict[str, float] = {
        "high_wind_speed": 10.0,
        "typhoon_speed": 15.0,
        "calm_wind_speed": 0.0,
        "cold_wave_temp": -50.0,
        "cold_wave_drop_24h": 1.0,
        "icing_temp_low": -30.0,
        "icing_temp_high": -30.0,
        "icing_tcwv": 0.0,
    }

    with _threshold_lock:
        try:
            current = _load_thresholds()
        except Exception:
            logger.exception("Failed to load thresholds before update")
            return jsonify({"error": "Failed to load existing thresholds"}), 500

        pending: dict[str, float] = {}
        for key, value in body.items():
            if key not in current:
                logger.debug("Ignoring unknown threshold key: %s", key)
                continue
            try:
                converted = float(value)
            except (TypeError, ValueError):
                return jsonify({"error": f"Invalid value for {key}: {value!r}"}), 400
            if converted < MIN_BOUNDS.get(key, 0.0):
                return jsonify({"error": f"Value for {key} too low: {converted}"}), 400
            pending[key] = converted

        current.update(pending)

        # Inter-threshold consistency: calm < high < typhoon
        calm = current.get("calm_wind_speed", 0.0)
        high = current.get("high_wind_speed", 25.0)
        typhoon = current.get("typhoon_speed", 32.0)
        if not (calm < high < typhoon):
            return jsonify(
                {"error": f"Inconsistent thresholds: calm({calm}) < high({high}) < typhoon({typhoon}) violated"}
            ), 400

        try:
            _save_thresholds(current)
        except Exception:
            logger.exception("Failed to persist extreme weather thresholds")
            return jsonify({"error": "Failed to persist thresholds"}), 500

    logger.info("Updated thresholds: %s", pending)
    return jsonify(current), 200


@extreme_weather_bp.route("/status", methods=["GET"])
@permission_required("view_all_data")
def get_status() -> tuple[dict[str, Any], int]:
    """Return current weather condition for a farm.

    Query parameters
    ----------------
    farm_code : str, optional
        Wind farm identifier.
    """
    farm_code: str = request.args.get("farm_code", "")

    # 当前没有实时输入时，显式返回未知状态，防止界面展示虚假正常。
    payload: dict[str, Any] = {
        "farm_code": farm_code,
        "current_condition": {
            "type": "unknown",
            "severity": "info",
            "details": {
                "reason": "live_weather_feed_not_connected",
            },
        },
        "data_available": False,
        "source_status": "not_connected",
        "active_alerts": None,
        "last_checked": None,
        "message": "实时天气数据源尚未接入，无法判断当前天气状态",
    }

    logger.debug("GET /status farm_code=%s", farm_code)
    return jsonify(payload), 200


@extreme_weather_bp.route("/history", methods=["GET"])
@permission_required("view_all_data")
def get_history() -> tuple[dict[str, Any], int]:
    """Return paginated historical extreme weather events.

    Query parameters
    ----------------
    farm_code : str, optional
        Wind farm identifier.
    page : int, optional
        Page number (default 1).
    per_page : int, optional
        Items per page (default 20).
    """
    farm_code: str = request.args.get("farm_code", "")
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
        "total": None,
        "data_available": False,
        "source_status": "not_connected",
        "message": "极端天气历史事件存储尚未接入",
    }

    logger.debug(
        "GET /history farm_code=%s page=%d per_page=%d",
        farm_code,
        page,
        per_page,
    )
    return jsonify(payload), 200
