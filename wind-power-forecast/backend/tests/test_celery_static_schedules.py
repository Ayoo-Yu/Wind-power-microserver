from contextlib import contextmanager
from types import SimpleNamespace

from celery_app import scheduler
from celery_app import tasks as celery_tasks


def test_static_report_schedules_survive_database_outage(monkeypatch):
    @contextmanager
    def unavailable_database():
        raise RuntimeError("database unavailable")
        yield

    monkeypatch.setattr(scheduler, "db_session", unavailable_database)
    monkeypatch.setattr(scheduler, "read_config", lambda: {
        "enabled": True,
        "schedule_hour": 8,
        "schedule_minutes": [40, 55],
    })

    schedule = scheduler.build_beat_schedule()

    assert schedule["report_outbox_dispatch"]["task"] == "celery_app.tasks.process_report_outbox"
    assert schedule["report_schedule_scan"]["task"] == "celery_app.tasks.scan_scheduled_reports"
    assert schedule["regulatory_evaluation_daily"]["task"] == "celery_app.tasks.run_regulatory_evaluation"
    assert schedule["partition_maintenance_daily"]["task"] == "celery_app.tasks.run_partition_maintenance"
    assert schedule["etext_pipeline_daily"]["task"] == "celery_app.tasks.run_etext_pipeline"


def test_weather_tasks_are_loaded_into_celery_beat(monkeypatch):
    weather_task = SimpleNamespace(id=17, name="NWP 拉取", schedule="5 */6 * * *")

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter_by(self, **kwargs):
            return self

        def filter(self, *args):
            return self

        def all(self):
            if self.model is scheduler.WeatherTask:
                return [weather_task]
            return []

    class FakeSession:
        def query(self, model):
            return FakeQuery(model)

    @contextmanager
    def available_database():
        yield FakeSession()

    monkeypatch.setattr(scheduler, "db_session", available_database)
    monkeypatch.setattr(scheduler, "read_config", lambda: {"enabled": False})

    schedule = scheduler.build_beat_schedule()

    assert schedule["weather_task_17"]["task"] == "celery_app.tasks.run_weather_fetch"
    assert schedule["weather_task_17"]["args"] == (17, True)


def test_weather_worker_skips_duplicate_execution(monkeypatch):
    weather_task = SimpleNamespace(
        id=17,
        enabled=True,
        connection_id=8,
        farm_code="zyx",
        timeout=300,
        retry_count=2,
    )
    connection = SimpleNamespace(id=8)

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *args):
            return self

        def first(self):
            from db_models import WeatherConnection, WeatherTask

            if self.model is WeatherTask:
                return weather_task
            if self.model is WeatherConnection:
                return connection
            return None

    class FakeSession:
        def query(self, model):
            return FakeQuery(model)

    @contextmanager
    def available_database():
        yield FakeSession()

    monkeypatch.setattr(celery_tasks, "db_session", available_database)
    monkeypatch.setattr(
        celery_tasks,
        "_acquire_weather_lock",
        lambda task_id, timeout: (object(), "key", "token", False),
    )

    result = celery_tasks.run_weather_fetch.run(17, True)

    assert result == {"status": "skipped", "reason": "already_running", "task_id": 17}
