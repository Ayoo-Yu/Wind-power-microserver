import pytest

from services.cron_service import build_crontab, validate_cron_expression
from services.etext_config import validate_and_apply_config_updates
from services.etext_job_service import describe_schedule


def test_weather_cron_contract_accepts_standard_five_fields():
    normalized = validate_cron_expression("  5   */6  * * * ")

    assert normalized == "5 */6 * * *"
    assert build_crontab(normalized) is not None


@pytest.mark.parametrize("expression", ["", "0 6 * *", "61 * * * *"])
def test_weather_cron_contract_rejects_invalid_values(expression):
    with pytest.raises(ValueError):
        validate_cron_expression(expression)


def test_etext_schedule_requires_at_least_one_minute():
    config = {
        "incoming_dir": "",
        "schedule_hour": 8,
        "schedule_minutes": [40],
        "enabled": True,
    }

    updated, error = validate_and_apply_config_updates(config, {"schedule_minutes": []})

    assert updated == config
    assert error == "至少需要配置一个执行分钟"


def test_etext_schedule_description_reports_celery_ownership():
    job = describe_schedule({
        "enabled": True,
        "schedule_hour": 8,
        "schedule_minutes": [55, 40],
    })

    assert job["trigger"] == "40,55 8 * * *"
    assert job["mode"] == "celery"
    assert job["managed_externally"] is True
