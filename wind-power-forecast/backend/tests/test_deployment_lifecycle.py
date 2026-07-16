from pathlib import Path

import deployment_init


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent


def test_deployment_init_runs_schema_once_before_user_bootstrap(monkeypatch):
    calls = []
    monkeypatch.setenv("DB_SCHEMA_ACTION", "upgrade")
    monkeypatch.setenv("DB_WAIT_TIMEOUT_SECONDS", "75")
    monkeypatch.setattr(deployment_init, "_run", calls.append)

    assert deployment_init.main() == 0
    assert calls == [
        ["manage_db.py", "wait", "--timeout", "75"],
        ["manage_db.py", "upgrade"],
        ["-m", "init_users"],
        ["manage_db.py", "check"],
    ]


def test_deployment_init_rejects_skip_action(monkeypatch):
    calls = []
    monkeypatch.setenv("DB_SCHEMA_ACTION", "skip")
    monkeypatch.setattr(deployment_init, "_run", calls.append)

    assert deployment_init.main() == 2
    assert calls == []


def test_web_entrypoints_are_read_only():
    entrypoints = [
        BACKEND_ROOT / "docker-entrypoint.sh",
        PROJECT_ROOT / "deploy" / "backend-entrypoint.sh",
    ]
    for path in entrypoints:
        content = path.read_text(encoding="utf-8")
        assert "manage_db.py prepare" not in content
        assert "manage_db.py upgrade" not in content
        assert "init_users" not in content
        assert "fix_admin_permissions" not in content
        assert "rglob(\"*.py\")" not in content
        assert "--preload" not in content


def test_compose_services_wait_for_deployment_init():
    for path in (
        PROJECT_ROOT / "frontend-backend-compose.yaml",
        PROJECT_ROOT / "deploy" / "docker-compose.prod.yaml",
    ):
        content = path.read_text(encoding="utf-8")
        assert "deployment-init:" in content
        assert "condition: service_completed_successfully" in content
        assert "DB_SCHEMA_ACTION=check" in content


def test_web_app_has_no_embedded_weather_scheduler_startup():
    content = (BACKEND_ROOT / "app.py").read_text(encoding="utf-8")
    assert "init_scheduler" not in content
    assert "scheduler_service" not in content


def test_report_routes_have_no_embedded_scheduler():
    content = (
        BACKEND_ROOT / "routes" / "report_management_router.py"
    ).read_text(encoding="utf-8")
    assert "BackgroundScheduler" not in content
    assert "start_report_scheduler" not in content
