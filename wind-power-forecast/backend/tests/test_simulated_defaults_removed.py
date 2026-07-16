import importlib.util
import json
from pathlib import Path

import sqlalchemy as sa


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


def _load_cleanup_migration():
    migration_path = (
        BACKEND_DIR
        / "migrations"
        / "versions"
        / "20260717_01_remove_simulated_defaults.py"
    )
    spec = importlib.util.spec_from_file_location(
        "remove_simulated_defaults_migration",
        migration_path,
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_cleanup_migration_removes_only_known_alarm_defaults():
    migration = _load_cleanup_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE alarm_records ("
            "id INTEGER PRIMARY KEY, source TEXT, module TEXT, message TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE alarm_rules ("
            "id INTEGER PRIMARY KEY, rule_name TEXT, module TEXT, "
            '"level" TEXT, keyword TEXT)'
        )
        connection.exec_driver_sql(
            "CREATE TABLE alarm_notification_policies ("
            "id INTEGER PRIMARY KEY, policy_name TEXT, channel TEXT, target TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO alarm_records VALUES "
            "(1, 'system-log', 'system-log', 'system service heartbeat is normal'), "
            "(2, 'system', 'scheduler', '真实调度异常')"
        )
        connection.exec_driver_sql(
            "INSERT INTO alarm_rules VALUES "
            "(1, '系统错误告警', 'system-log', 'danger', 'error'), "
            "(2, '现场高温告警', 'weather', 'warning', 'temperature')"
        )
        connection.exec_driver_sql(
            "INSERT INTO alarm_notification_policies VALUES "
            "(1, '默认声音通知', 'sound', 'browser-audio'), "
            "(2, '值班室通知', 'sms', '13800000000')"
        )

        existing = {
            "alarm_records",
            "alarm_rules",
            "alarm_notification_policies",
        }
        migration._remove_alarm_defaults(connection, existing)

        alarms = connection.execute(
            sa.text("SELECT message FROM alarm_records ORDER BY id")
        ).scalars().all()
        rules = connection.execute(
            sa.text("SELECT rule_name FROM alarm_rules ORDER BY id")
        ).scalars().all()
        policies = connection.execute(
            sa.text(
                "SELECT policy_name FROM alarm_notification_policies ORDER BY id"
            )
        ).scalars().all()

    assert alarms == ["真实调度异常"]
    assert rules == ["现场高温告警"]
    assert policies == ["值班室通知"]


def test_cleanup_migration_strips_manual_runtime_placeholders():
    migration = _load_cleanup_migration()
    engine = sa.create_engine("sqlite://")
    original_payload = {
        "province": "云南",
        "scada_status": "online",
        "nwp_status": "normal",
        "current_actual_power": 12.5,
    }
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE farm_profile_configs ("
            "id INTEGER PRIMARY KEY, payload TEXT, updated_at DATETIME)"
        )
        connection.execute(
            sa.text(
                "INSERT INTO farm_profile_configs (id, payload, updated_at) "
                "VALUES (1, :payload, CURRENT_TIMESTAMP)"
            ),
            {"payload": json.dumps(original_payload, ensure_ascii=False)},
        )

        migration._remove_profile_placeholders(
            connection,
            {"farm_profile_configs"},
        )
        payload = json.loads(
            connection.execute(
                sa.text("SELECT payload FROM farm_profile_configs WHERE id = 1")
            ).scalar_one()
        )

    assert payload == {"province": "云南"}


def test_local_startup_has_no_synthetic_power_seed():
    start_source = (PROJECT_DIR / "start-local.bat").read_text(encoding="utf-8")
    provision_source = (BACKEND_DIR / "provision_local_farms.py").read_text(
        encoding="utf-8"
    )

    assert "seed_farms.py" not in start_source
    assert "provision_local_farms.py" in start_source
    assert "ActualPower" not in provision_source
    assert "SupershortlPower" not in provision_source
    assert "ShortlPower" not in provision_source
    assert "random" not in provision_source


def test_read_apis_do_not_seed_alarm_or_report_test_data():
    alarm_source = (BACKEND_DIR / "routes" / "alarm_router.py").read_text(
        encoding="utf-8"
    )
    report_source = (
        BACKEND_DIR / "routes" / "report_management_router.py"
    ).read_text(encoding="utf-8")

    assert "_seed_alarms_from_logs" not in alarm_source
    assert "_seed_default_configs" not in alarm_source
    assert "/statistics/test-update" not in report_source


def test_capacity_has_no_hidden_site_specific_default():
    capacity_source = (
        BACKEND_DIR / "auto_scripts" / "scripts" / "utils_base.py"
    ).read_text(encoding="utf-8")
    evaluator_source = (BACKEND_DIR / "scripts" / "evaluator_model.py").read_text(
        encoding="utf-8"
    )

    assert "SELECT capacity FROM wind_farms" in capacity_source
    assert "779.0" not in capacity_source
    assert "779.0" not in evaluator_source
