import os
import sys
from celery.schedules import crontab

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from db_session import db_session
from db_models import PredictionTask

DEFAULT_SCHEDULES = {
    "short": {"train": "03:00", "predict": "08:00"},
    "medium": {"train": "02:00", "predict": "08:30"},
    "supershort": {"train": "04:30", "predict_cron": "14,29,44,59"},
}


def build_beat_schedule():
    """Build Celery Beat schedule from prediction_tasks table.

    NOTE: This is called once at Beat startup. To pick up schedule changes
    (new farms, changed times, enabled/disabled), restart the Beat process.
    For dynamic scheduling, consider celery-redbeat or a custom DatabaseScheduler.
    """
    schedule = {}
    with db_session() as session:
        tasks = session.query(PredictionTask).filter_by(enabled=True).all()
        for t in tasks:
            fc = t.farm_code
            tt = t.task_type

            if tt == "supershort":
                schedule[f"{fc}_supershort_predict"] = {
                    "task": "celery_app.tasks.run_supershort_predict",
                    "args": (fc,),
                    "schedule": crontab(minute="14,29,44,59"),
                }
                train_time = t.train_schedule or DEFAULT_SCHEDULES["supershort"]["train"]
                h, m = train_time.split(":")
                schedule[f"{fc}_supershort_train"] = {
                    "task": "celery_app.tasks.train_model",
                    "args": (fc, "supershort"),
                    "schedule": crontab(minute=int(m), hour=int(h)),
                }
            else:
                train_time = t.train_schedule or DEFAULT_SCHEDULES[tt]["train"]
                h, m = train_time.split(":")
                schedule[f"{fc}_{tt}_train"] = {
                    "task": "celery_app.tasks.train_model",
                    "args": (fc, tt),
                    "schedule": crontab(minute=int(m), hour=int(h)),
                }

                predict_time = t.predict_schedule or DEFAULT_SCHEDULES[tt]["predict"]
                ph, pm = predict_time.split(":")
                schedule[f"{fc}_{tt}_predict"] = {
                    "task": "celery_app.tasks.run_prediction",
                    "args": (fc, tt),
                    "schedule": crontab(minute=int(pm), hour=int(ph)),
                }
    return schedule
