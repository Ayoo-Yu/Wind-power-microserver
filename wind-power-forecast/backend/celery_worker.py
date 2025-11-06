"""Celery worker entrypoint ensuring Flask app context."""

import sys
from pathlib import Path

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app_factory import create_app  # noqa: E402

flask_app = create_app()
celery = flask_app.celery_app

__all__ = ["celery"]


