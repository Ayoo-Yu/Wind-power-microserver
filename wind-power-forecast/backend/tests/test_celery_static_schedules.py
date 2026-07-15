from contextlib import contextmanager

from celery_app import scheduler
from celery_app.tasks import scan_scheduled_reports


def test_static_report_schedules_survive_database_outage(monkeypatch):
    @contextmanager
    def unavailable_database():
        raise RuntimeError("database unavailable")
        yield

    monkeypatch.setattr(scheduler, "db_session", unavailable_database)

    schedule = scheduler.build_beat_schedule()

    assert schedule["report_outbox_dispatch"]["task"] == "celery_app.tasks.process_report_outbox"
    assert schedule["report_schedule_scan"]["task"] == "celery_app.tasks.scan_scheduled_reports"


def test_report_scan_task_skips_when_embedded_mode_is_selected(monkeypatch):
    monkeypatch.setenv("REPORT_SCHEDULER_MODE", "embedded")

    result = scan_scheduled_reports.run()

    assert result["status"] == "skipped"
