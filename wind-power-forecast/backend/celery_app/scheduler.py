import logging
import os
import time

from celery.beat import PersistentScheduler
from celery.schedules import crontab
from sqlalchemy import func

from db_session import db_session
from db_models import PredictionTask

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULES = {
    "short": {"train": "03:00", "predict": "08:50", "calibrate": "03:03"},
    "medium": {"train": "02:00", "predict": "08:50", "calibrate": "03:03"},
    "supershort": {"train": "04:30", "predict_cron": "14,29,44,59", "calibrate": "04:33"},
}

SCHEDULE_RELOAD_INTERVAL_SEC = int(os.environ.get("CELERY_BEAT_RELOAD_INTERVAL_SEC", "60"))


def _parse_hhmm(value: str, fallback: str) -> tuple[int, int]:
    raw = value or fallback
    hour, minute = raw.split(":", 1)
    return int(hour), int(minute)


def _parse_day_of_week(value):
    """Parse day_of_week field. Accepts 'mon', '1', 'mon,wed', '*' etc. Returns string for crontab."""
    raw = (value or "").strip().lower()
    if not raw or raw == "*":
        return "*"
    day_map = {"mon": "1", "tue": "2", "wed": "3", "thu": "4", "fri": "5", "sat": "6", "sun": "0"}
    parts = []
    for p in raw.split(","):
        p = p.strip()
        parts.append(day_map.get(p, p))
    return ",".join(parts)


def build_beat_schedule():
    schedule = {}
    with db_session() as session:
        tasks = session.query(PredictionTask).filter_by(enabled=True).all()
        for t in tasks:
            fc = t.farm_code
            tt = t.task_type
            dow = _parse_day_of_week(getattr(t, "train_day_of_week", None))

            if tt == "supershort":
                schedule[f"{fc}_supershort_predict"] = {
                    "task": "celery_app.tasks.run_supershort_predict",
                    "args": (fc,),
                    "schedule": crontab(minute="14,29,44,59"),
                }
                h, m = _parse_hhmm(
                    t.train_schedule,
                    DEFAULT_SCHEDULES["supershort"]["train"],
                )
                schedule[f"{fc}_supershort_train"] = {
                    "task": "celery_app.tasks.train_model",
                    "args": (fc, "supershort"),
                    "schedule": crontab(minute=m, hour=h, day_of_week=dow),
                }
                ch, cm = _parse_hhmm(
                    getattr(t, "calibrate_schedule", None),
                    DEFAULT_SCHEDULES["supershort"].get("calibrate", "04:33"),
                )
                schedule[f"{fc}_supershort_calibrate"] = {
                    "task": "celery_app.tasks.run_calibration",
                    "args": (fc, "supershort"),
                    "schedule": crontab(minute=cm, hour=ch, day_of_week=dow),
                }
            else:
                h, m = _parse_hhmm(t.train_schedule, DEFAULT_SCHEDULES[tt]["train"])
                schedule[f"{fc}_{tt}_train"] = {
                    "task": "celery_app.tasks.train_model",
                    "args": (fc, tt),
                    "schedule": crontab(minute=m, hour=h, day_of_week=dow),
                }

                ph, pm = _parse_hhmm(t.predict_schedule, DEFAULT_SCHEDULES[tt]["predict"])
                schedule[f"{fc}_{tt}_predict"] = {
                    "task": "celery_app.tasks.run_prediction",
                    "args": (fc, tt),
                    "schedule": crontab(minute=pm, hour=ph),
                }

                ch, cm = _parse_hhmm(
                    getattr(t, "calibrate_schedule", None),
                    DEFAULT_SCHEDULES[tt].get("calibrate", "03:03"),
                )
                schedule[f"{fc}_{tt}_calibrate"] = {
                    "task": "celery_app.tasks.run_calibration",
                    "args": (fc, tt),
                    "schedule": crontab(minute=cm, hour=ch, day_of_week=dow),
                }
    return schedule


def get_schedule_revision():
    with db_session() as session:
        row = session.query(
            func.count(PredictionTask.id),
            func.max(PredictionTask.updated_at),
        ).one()
        return row[0], row[1].isoformat() if row[1] else None


class DatabaseScheduler(PersistentScheduler):
    """Celery beat scheduler that reloads enabled tasks from the database."""

    def setup_schedule(self):
        super().setup_schedule()
        self._last_schedule_check = 0.0
        self._schedule_revision = None
        self._reload_from_database(force=True)

    def tick(self, *args, **kwargs):
        now = time.monotonic()
        if now - getattr(self, "_last_schedule_check", 0.0) >= SCHEDULE_RELOAD_INTERVAL_SEC:
            self._last_schedule_check = now
            self._reload_from_database(force=False)
        return super().tick(*args, **kwargs)

    def _reload_from_database(self, force: bool):
        try:
            revision = get_schedule_revision()
            if not force and revision == self._schedule_revision:
                return

            schedule = build_beat_schedule()
            self.schedule.clear()
            self.update_from_dict(schedule)
            self._schedule_revision = revision
            self.sync()
            logger.info("Reloaded Celery beat schedule from database: %d entries", len(schedule))
        except Exception:
            logger.exception("Failed to reload Celery beat schedule from database")
