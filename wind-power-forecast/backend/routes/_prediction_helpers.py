"""Prediction task helpers: action locks, status tracking, and task history."""

import uuid
import logging

from db_session import db_session
from db_models import TaskHistory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Task history recording
# ---------------------------------------------------------------------------

def record_task_history(task_type, action, status, details=None, user=None):
    """记录任务操作历史

    Args:
        task_type: 任务类型 (supershort, short, medium)
        action: 操作类型 (start, stop, delete, schedule, etc.)
        status: 操作状态 (success, failed)
        details: 操作详情，可选
        user: 操作用户，可选

    Returns:
        UUID: 任务历史ID
    """
    task_id = str(uuid.uuid4())
    try:
        with db_session() as db:
            task_history = TaskHistory(
                task_id=task_id,
                task_type=task_type,
                action=action,
                status=status,
                details=details,
                user=user
            )
            db.add(task_history)
            db.commit()
            return task_id
    except Exception as e:
        logger.warning("记录任务历史出错: %s", e)
        return None
