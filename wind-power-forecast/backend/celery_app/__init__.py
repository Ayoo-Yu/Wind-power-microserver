import os
import logging

from celery import Celery, signals

logger = logging.getLogger(__name__)

celery_app = Celery("wind_power_predict")

celery_app.conf.update(
    broker_url=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    beat_scheduler="celery_app.scheduler:DatabaseScheduler",
)

celery_app.autodiscover_tasks(["celery_app"])


@signals.worker_process_init.connect
def _init_db_pool(**kwargs):
    from database_config import engine
    engine.dispose()
    logger.info("DB engine disposed for fresh pool in worker process")


def _load_beat_schedule():
    try:
        from celery_app.scheduler import build_beat_schedule
        schedule = build_beat_schedule()
        celery_app.conf.beat_schedule = schedule
        logger.info("Beat schedule loaded: %d entries", len(schedule))
    except Exception as e:
        logger.error("Failed to load beat schedule from database: %s", e, exc_info=True)


@celery_app.on_after_configure.connect
def setup_beat_schedule(sender, **kwargs):
    _load_beat_schedule()
