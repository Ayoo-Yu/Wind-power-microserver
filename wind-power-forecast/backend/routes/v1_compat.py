from flask import Blueprint

from routes.farm_management import get_farms, get_farm_by_code, get_farm_stats
from routes.power_compare import get_fleet_metrics, get_fleet_series, get_power_data
from routes.report_management_router import (
    get_wind_farms,
    create_wind_farm,
    update_wind_farm,
    get_report_configs,
    create_report_config,
    update_report_config,
    delete_report_config,
    get_report_logs,
    preview_report,
    manual_report,
    get_report_statistics,
    start_scheduler,
    stop_scheduler,
    get_scheduler_status
)
from routes.physical_simulation_router import (
    batch_add_turbines,
    batch_add_conditions,
    batch_add_readings,
    get_turbines,
    get_conditions,
    get_readings
)
from routes.system_info_router import (
    get_hardware_info,
    get_software_info,
    get_runtime_info,
    get_system_logs
)

v1_compat_bp = Blueprint("v1_compat", __name__, url_prefix="/api/v1")


@v1_compat_bp.route("/farms", methods=["GET"])
def get_farms_v1():
    """
    v1 compat bridge:
    - `/api/v1/farms` reuses current `/api/farms` handler behavior.
    - `/api/v1/auth/*` is registered as alias of legacy auth blueprint in app.py.
    """
    return get_farms()


@v1_compat_bp.route("/farms/<farm_code>", methods=["GET"])
def get_farm_by_code_v1(farm_code):
    """
    v1 compat bridge:
    - `/api/v1/farms/<farm_code>` reuses current `/api/farms/<farm_code>` handler behavior.
    """
    return get_farm_by_code(farm_code)


@v1_compat_bp.route("/farms/<farm_code>/stats", methods=["GET"])
@v1_compat_bp.route("/farms/<farm_code>/statistics", methods=["GET"])
def get_farm_stats_v1(farm_code):
    """
    v1 compat bridge:
    - `/api/v1/farms/<farm_code>/stats` reuses current farm stats handler.
    - `/api/v1/farms/<farm_code>/statistics` is provided as compatibility alias.
    """
    return get_farm_stats(farm_code)


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


@v1_compat_bp.route("/report/farms", methods=["GET"])
def get_report_farms_v1():
    return get_wind_farms()


@v1_compat_bp.route("/report/farms", methods=["POST"])
def create_report_farm_v1():
    return create_wind_farm()


@v1_compat_bp.route("/report/farms/<int:farm_id>", methods=["PUT"])
def update_report_farm_v1(farm_id):
    return update_wind_farm(farm_id)


@v1_compat_bp.route("/report/configs", methods=["GET"])
def get_report_configs_v1():
    return get_report_configs()


@v1_compat_bp.route("/report/configs", methods=["POST"])
def create_report_config_v1():
    return create_report_config()


@v1_compat_bp.route("/report/configs/<int:config_id>", methods=["PUT"])
def update_report_config_v1(config_id):
    return update_report_config(config_id)


@v1_compat_bp.route("/report/configs/<int:config_id>", methods=["DELETE"])
def delete_report_config_v1(config_id):
    return delete_report_config(config_id)


@v1_compat_bp.route("/report/logs", methods=["GET"])
def get_report_logs_v1():
    return get_report_logs()


@v1_compat_bp.route("/report/preview-report", methods=["POST"])
def preview_report_v1():
    return preview_report()


@v1_compat_bp.route("/report/manual-report", methods=["POST"])
def manual_report_v1():
    return manual_report()


@v1_compat_bp.route("/report/statistics", methods=["GET"])
def get_report_statistics_v1():
    return get_report_statistics()


@v1_compat_bp.route("/report/scheduler/start", methods=["POST"])
def start_report_scheduler_v1():
    return start_scheduler()


@v1_compat_bp.route("/report/scheduler/stop", methods=["POST"])
def stop_report_scheduler_v1():
    return stop_scheduler()


@v1_compat_bp.route("/report/scheduler/status", methods=["GET"])
def get_report_scheduler_status_v1():
    return get_scheduler_status()


@v1_compat_bp.route("/physical-simulation/turbines/batch", methods=["POST"])
def batch_add_turbines_v1():
    return batch_add_turbines()


@v1_compat_bp.route("/physical-simulation/conditions/batch", methods=["POST"])
def batch_add_conditions_v1():
    return batch_add_conditions()


@v1_compat_bp.route("/physical-simulation/readings/batch", methods=["POST"])
def batch_add_readings_v1():
    return batch_add_readings()


@v1_compat_bp.route("/physical-simulation/turbines", methods=["GET"])
def get_turbines_v1():
    return get_turbines()


@v1_compat_bp.route("/physical-simulation/conditions", methods=["GET"])
def get_conditions_v1():
    return get_conditions()


@v1_compat_bp.route("/physical-simulation/readings", methods=["GET"])
def get_readings_v1():
    return get_readings()


@v1_compat_bp.route("/system/hardware", methods=["GET"])
def get_system_hardware_v1():
    return get_hardware_info()


@v1_compat_bp.route("/system/software", methods=["GET"])
def get_system_software_v1():
    return get_software_info()


@v1_compat_bp.route("/system/runtime", methods=["GET"])
def get_system_runtime_v1():
    return get_runtime_info()


@v1_compat_bp.route("/system/logs", methods=["GET"])
def get_system_logs_v1():
    return get_system_logs()
