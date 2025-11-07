"""Celery application instance for the autopredict service."""

from __future__ import annotations

from celery import Celery

from config import Config


celery_app = Celery(
    "backend_autopredict",
    broker=Config.REDIS_URL,
    backend=Config.CELERY_RESULT_BACKEND,
    include=[
        "tasks.autopredict",
    ],
)

celery_app.conf.update(
    task_default_queue="autopredict",
    task_default_exchange="autopredict",
    task_default_routing_key="autopredict.default",
    timezone=Config.CELERY_TIMEZONE,
    enable_utc=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)


__all__ = ["celery_app"]


