"""Celery 任务队列初始化封装。"""

from __future__ import annotations

from celery import Celery

from config import Config


celery_app = Celery("windpower_backend")

celery_app.conf.update(
    broker_url=Config.REDIS_URL,
    result_backend=Config.CELERY_RESULT_BACKEND,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=Config.CELERY_TIMEZONE,
    enable_utc=False,
    task_default_queue=Config.CELERY_TASK_DEFAULT_QUEUE,
    task_track_started=True,
)


def init_celery(app=None) -> Celery:
    """初始化 Celery，并与 Flask 应用上下文绑定。"""

    if app is not None:
        celery_app.conf.update(app.config)

        class ContextTask(celery_app.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return super().__call__(*args, **kwargs)

        celery_app.Task = ContextTask

    return celery_app


__all__ = ["celery_app", "init_celery"]


