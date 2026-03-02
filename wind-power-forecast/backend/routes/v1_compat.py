from flask import Blueprint

from routes.farm_management import get_farms
from routes.power_compare import get_fleet_metrics, get_fleet_series, get_power_data

v1_compat_bp = Blueprint("v1_compat", __name__, url_prefix="/api/v1")


@v1_compat_bp.route("/farms", methods=["GET"])
def get_farms_v1():
    """
    v1 compat bridge:
    - `/api/v1/farms` reuses current `/api/farms` handler behavior.
    - `/api/v1/auth/*` is registered as alias of legacy auth blueprint in app.py.
    """
    return get_farms()


@v1_compat_bp.route("/power-compare/fleet_metrics", methods=["POST"])
def get_fleet_metrics_v1():
    """
    v1 compat bridge:
    - `/api/v1/power-compare/fleet_metrics` reuses legacy `/power-compare/fleet_metrics`.
    """
    return get_fleet_metrics()


@v1_compat_bp.route("/power-compare/fleet_series", methods=["POST"])
def get_fleet_series_v1():
    """
    v1 compat bridge:
    - `/api/v1/power-compare/fleet_series` reuses legacy `/power-compare/fleet_series`.
    """
    return get_fleet_series()


@v1_compat_bp.route("/power-compare/data", methods=["POST"])
def get_power_data_v1():
    """
    v1 compat bridge:
    - `/api/v1/power-compare/data` reuses legacy `/power-compare/data`.
    """
    return get_power_data()
