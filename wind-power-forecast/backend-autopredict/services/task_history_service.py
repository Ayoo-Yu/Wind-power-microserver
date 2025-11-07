"""Utilities for recording autopredict task history events."""

from __future__ import annotations

import uuid
from typing import Optional

from db_models.task import TaskHistory
from db_session import db_session


def record_task_history(
    *,
    task_type: str,
    wind_farm_code: str,
    action: str,
    status: str,
    details: Optional[str] = None,
    user: Optional[str] = None,
) -> None:
    """Persist a task history entry for auditing and UI usage."""

    with db_session() as session:
        history = TaskHistory(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            wind_farm_code=wind_farm_code,
            action=action,
            status=status,
            details=details,
            user=user,
        )
        session.add(history)


__all__ = ["record_task_history"]


