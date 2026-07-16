from flask import Blueprint
from flask_jwt_extended import verify_jwt_in_request

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
    list_manual_intervention_versions,
    create_manual_intervention_version,
    get_manual_intervention_version,
    apply_manual_intervention_version,
    get_report_statistics,
    get_accuracy_statistics,
    get_quality_markers,
    create_quality_marker,
    update_quality_marker,
    delete_quality_marker,
    start_scheduler,
    stop_scheduler,
    get_scheduler_status
)
from routes.system_info_router import (
    get_hardware_info,
    get_software_info,
    get_runtime_info,
    get_system_logs
)
from routes.system_settings_router import (
    get_system_settings,
    save_system_settings,
    reset_system_settings
)
from routes.weather_fetch_router import (
    get_connections as get_weather_connections,
    create_connection as create_weather_connection,
    update_connection as update_weather_connection,
    delete_connection as delete_weather_connection,
    test_connection as test_weather_connection,
    get_tasks as get_weather_tasks,
    create_task as create_weather_task,
    update_task as update_weather_task,
    delete_task as delete_weather_task,
    toggle_task as toggle_weather_task,
    run_task as run_weather_task,
    get_logs as get_weather_logs,
    get_task_logs as get_weather_task_logs,
    get_scheduler_status as get_weather_scheduler_status,
    get_stats as get_weather_stats,
    check_directories as check_weather_directories,
    restart_scheduler as restart_weather_scheduler
)

v1_compat_bp = Blueprint("v1_compat", __name__, url_prefix="/api/v1")


@v1_compat_bp.before_request
def require_v1_authentication():
    """兼容桥只承载登录后的业务接口，统一拒绝匿名访问。"""

    verify_jwt_in_request()


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


@v1_compat_bp.route("/report/manual-intervention/versions", methods=["GET"])
def list_manual_intervention_versions_v1():
    return list_manual_intervention_versions()


@v1_compat_bp.route("/report/manual-intervention/versions", methods=["POST"])
def create_manual_intervention_version_v1():
    return create_manual_intervention_version()


@v1_compat_bp.route("/report/manual-intervention/versions/<int:version_id>", methods=["GET"])
def get_manual_intervention_version_v1(version_id):
    return get_manual_intervention_version(version_id)


@v1_compat_bp.route("/report/manual-intervention/versions/<int:version_id>/apply", methods=["POST"])
def apply_manual_intervention_version_v1(version_id):
    return apply_manual_intervention_version(version_id)


@v1_compat_bp.route("/report/statistics", methods=["GET"])
def get_report_statistics_v1():
    return get_report_statistics()


@v1_compat_bp.route("/report/accuracy-statistics", methods=["GET"])
def get_accuracy_statistics_v1():
    return get_accuracy_statistics()


@v1_compat_bp.route("/report/quality-markers", methods=["GET"])
def get_quality_markers_v1():
    return get_quality_markers()


@v1_compat_bp.route("/report/quality-markers", methods=["POST"])
def create_quality_marker_v1():
    return create_quality_marker()


@v1_compat_bp.route("/report/quality-markers/<int:marker_id>", methods=["PUT"])
def update_quality_marker_v1(marker_id):
    return update_quality_marker(marker_id)


@v1_compat_bp.route("/report/quality-markers/<int:marker_id>", methods=["DELETE"])
def delete_quality_marker_v1(marker_id):
    return delete_quality_marker(marker_id)


@v1_compat_bp.route("/report/scheduler/start", methods=["POST"])
def start_report_scheduler_v1():
    return start_scheduler()


@v1_compat_bp.route("/report/scheduler/stop", methods=["POST"])
def stop_report_scheduler_v1():
    return stop_scheduler()


@v1_compat_bp.route("/report/scheduler/status", methods=["GET"])
def get_report_scheduler_status_v1():
    return get_scheduler_status()


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


@v1_compat_bp.route("/system/settings", methods=["GET"])
def get_system_settings_v1():
    return get_system_settings()


@v1_compat_bp.route("/system/settings", methods=["PUT"])
def save_system_settings_v1():
    return save_system_settings()


@v1_compat_bp.route("/system/settings/reset", methods=["POST"])
def reset_system_settings_v1():
    return reset_system_settings()


@v1_compat_bp.route("/weather-fetch/connections", methods=["GET"])
def get_weather_connections_v1():
    return get_weather_connections()


@v1_compat_bp.route("/weather-fetch/connections", methods=["POST"])
def create_weather_connection_v1():
    return create_weather_connection()


@v1_compat_bp.route("/weather-fetch/connections/<int:connection_id>", methods=["PUT"])
def update_weather_connection_v1(connection_id):
    return update_weather_connection(connection_id)


@v1_compat_bp.route("/weather-fetch/connections/<int:connection_id>", methods=["DELETE"])
def delete_weather_connection_v1(connection_id):
    return delete_weather_connection(connection_id)


@v1_compat_bp.route("/weather-fetch/connections/<int:connection_id>/test", methods=["POST"])
def test_weather_connection_v1(connection_id):
    return test_weather_connection(connection_id)


@v1_compat_bp.route("/weather-fetch/tasks", methods=["GET"])
def get_weather_tasks_v1():
    return get_weather_tasks()


@v1_compat_bp.route("/weather-fetch/tasks", methods=["POST"])
def create_weather_task_v1():
    return create_weather_task()


@v1_compat_bp.route("/weather-fetch/tasks/<int:task_id>", methods=["PUT"])
def update_weather_task_v1(task_id):
    return update_weather_task(task_id)


@v1_compat_bp.route("/weather-fetch/tasks/<int:task_id>", methods=["DELETE"])
def delete_weather_task_v1(task_id):
    return delete_weather_task(task_id)


@v1_compat_bp.route("/weather-fetch/tasks/<int:task_id>/toggle", methods=["POST"])
def toggle_weather_task_v1(task_id):
    return toggle_weather_task(task_id)


@v1_compat_bp.route("/weather-fetch/tasks/<int:task_id>/run", methods=["POST"])
def run_weather_task_v1(task_id):
    return run_weather_task(task_id)


@v1_compat_bp.route("/weather-fetch/logs", methods=["GET"])
def get_weather_logs_v1():
    return get_weather_logs()


@v1_compat_bp.route("/weather-fetch/tasks/<int:task_id>/logs", methods=["GET"])
def get_weather_task_logs_v1(task_id):
    return get_weather_task_logs(task_id)


@v1_compat_bp.route("/weather-fetch/scheduler/status", methods=["GET"])
def get_weather_scheduler_status_v1():
    return get_weather_scheduler_status()


@v1_compat_bp.route("/weather-fetch/stats", methods=["GET"])
def get_weather_stats_v1():
    return get_weather_stats()


@v1_compat_bp.route("/weather-fetch/check-directories", methods=["POST"])
def check_weather_directories_v1():
    return check_weather_directories()


@v1_compat_bp.route("/weather-fetch/scheduler/restart", methods=["POST"])
def restart_weather_scheduler_v1():
    return restart_weather_scheduler()
