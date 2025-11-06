# Ensure tasks are registered when Celery app initializes
from . import training_tasks  # noqa: F401
from . import prediction_tasks  # noqa: F401
