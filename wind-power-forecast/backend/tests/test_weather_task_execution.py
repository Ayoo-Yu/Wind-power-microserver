from types import SimpleNamespace

from db_models.weather_fetch import WeatherLog
from services import task_executor


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    def commit(self):
        return None


def test_weather_execution_logs_keep_farm_identity(monkeypatch):
    session = FakeSession()
    task = SimpleNamespace(
        id=11,
        farm_code="zyx",
        status="idle",
        last_run=None,
        remote_path="/remote",
        path_pattern="YYYY_MMDDHHNN",
        time_strategy="latest",
        specific_time=None,
        time_range_start=None,
        time_range_end=None,
        file_pattern="*.dat",
        save_path="/tmp/weather/{date}",
    )
    connection = SimpleNamespace(id=7)
    monkeypatch.setattr(task_executor, "build_connection_config", lambda value: {})
    monkeypatch.setattr(
        task_executor.ssh_service,
        "list_files_dynamic_path",
        lambda *args, **kwargs: [],
    )

    result = task_executor.execute_weather_task(task, connection, session)

    assert result["success"] is True
    assert task.status == "not_found"
    logs = [value for value in session.added if isinstance(value, WeatherLog)]
    assert logs
    assert {log.farm_code for log in logs} == {"zyx"}
