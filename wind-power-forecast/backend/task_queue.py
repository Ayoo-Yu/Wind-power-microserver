"""Celery 任务队列初始化封装。"""

from __future__ import annotations

import sys
from pathlib import Path

from celery import Celery

from .config import Config

# 确保可以导入项目包（worker 直接运行此模块时不会经过 Flask app）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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

        # 在绑定上下文后再导入任务，确保使用新的 Task 基类
        import backend.tasks  # noqa: F401, E402

    return celery_app


__all__ = ["celery_app", "init_celery"]


