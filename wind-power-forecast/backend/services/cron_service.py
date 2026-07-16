"""统一校验并构造五段式 cron 表达式。"""

from celery.schedules import crontab


def build_crontab(expression: str):
    """将标准五段式 cron 表达式转换为 Celery 调度对象。"""

    fields = str(expression or "").split()
    if len(fields) != 5:
        raise ValueError("cron 表达式必须包含分钟、小时、日期、月份和星期五个字段")

    minute, hour, day_of_month, month_of_year, day_of_week = fields
    try:
        return crontab(
            minute=minute,
            hour=hour,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"cron 表达式无效: {exc}") from exc


def validate_cron_expression(expression: str) -> str:
    """校验表达式并返回去除多余空白后的标准形式。"""

    normalized = " ".join(str(expression or "").split())
    build_crontab(normalized)
    return normalized
