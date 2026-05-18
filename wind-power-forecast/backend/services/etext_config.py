"""E text pipeline configuration: read/write etext_config.json with path validation."""

import json
import logging
import os
import platform

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(PROJECT_ROOT, "data", "etext", "etext_config.json")

DEFAULT_CONFIG = {
    "incoming_dir": "",
    "schedule_hour": 8,
    "schedule_minutes": [40, 45, 50, 55],
    "enabled": True,
}


def _normalize(path):
    """Normalize path for comparison. On Windows, also lowercase."""
    p = os.path.normpath(os.path.abspath(path))
    if platform.system() == "Windows":
        p = p.lower()
    return p


def _is_allowed_path(path):
    """Check that path is under the project root."""
    if not path:
        return True
    try:
        norm_path = _normalize(path)
        norm_root = _normalize(PROJECT_ROOT)
        return norm_path.startswith(norm_root + os.sep) or norm_path == norm_root
    except Exception:
        return False


def read_config():
    """Read config from JSON file, falling back to defaults on error."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            cfg = {**DEFAULT_CONFIG, **saved}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Etext config file corrupt (%s), using defaults", e)
            cfg = dict(DEFAULT_CONFIG)
    else:
        cfg = dict(DEFAULT_CONFIG)
    if not cfg["incoming_dir"]:
        cfg["incoming_dir"] = os.path.join(PROJECT_ROOT, "data", "etext", "incoming")
    try:
        os.makedirs(cfg["incoming_dir"], exist_ok=True)
    except OSError as e:
        logger.warning("Failed to create Etext incoming directory %s: %s", cfg["incoming_dir"], e)
    return cfg


def write_config(cfg):
    """Atomic write config to JSON file."""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_FILE)


def validate_and_apply_config_updates(cfg, updates):
    """Apply validated updates to config dict. Returns (updated_cfg, error_msg_or_None)."""
    if "incoming_dir" in updates:
        path = updates["incoming_dir"].strip()
        if path and not _is_allowed_path(path):
            return cfg, "目录必须在项目根目录下"
        if path:
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                return cfg, f"failed to create incoming_dir: {e}"
        cfg = {**cfg, "incoming_dir": path}

    if "schedule_hour" in updates:
        try:
            hour = int(updates["schedule_hour"])
        except (ValueError, TypeError):
            return cfg, "schedule_hour must be 0-23"
        if not 0 <= hour <= 23:
            return cfg, "schedule_hour must be 0-23"
        cfg = {**cfg, "schedule_hour": hour}

    if "schedule_minutes" in updates:
        try:
            minutes = [int(m) for m in updates["schedule_minutes"]]
        except (ValueError, TypeError):
            return cfg, "minutes must be integers"
        if not all(0 <= m <= 59 for m in minutes):
            return cfg, "minutes must be 0-59"
        cfg = {**cfg, "schedule_minutes": sorted(minutes)}

    if "enabled" in updates:
        cfg = {**cfg, "enabled": bool(updates["enabled"])}

    return cfg, None
