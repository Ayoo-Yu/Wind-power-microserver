"""Helpers to manage autopredict scheduling configuration per wind farm."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError

from db_models.autopredict import AutopredictJobConfig
from db_session import db_session

VALID_TASK_TYPES = {"supershort", "short", "medium"}


def _validate_task_type(task_type: str) -> None:
    if task_type not in VALID_TASK_TYPES:
        raise ValueError(f"Unsupported task_type: {task_type}")


def get_or_create_job(
    task_type: str,
    wind_farm_code: str,
    *,
    default_cron: Optional[str] = None,
) -> AutopredictJobConfig:
    """Fetch the job config or create a disabled one if missing."""

    _validate_task_type(task_type)

    with db_session() as session:
        job = (
            session.query(AutopredictJobConfig)
            .filter(
                AutopredictJobConfig.task_type == task_type,
                AutopredictJobConfig.wind_farm_code == wind_farm_code,
            )
            .one_or_none()
        )
        if job:
            return job

        job = AutopredictJobConfig(
            task_type=task_type,
            wind_farm_code=wind_farm_code,
            enabled=False,
            schedule_cron=default_cron,
        )
        session.add(job)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            # Another process inserted it; fetch again recursively.
            return get_or_create_job(task_type, wind_farm_code, default_cron=default_cron)
        return job


def set_job_enabled(task_type: str, wind_farm_code: str, *, enabled: bool) -> AutopredictJobConfig:
    job = get_or_create_job(task_type, wind_farm_code)
    with db_session() as session:
        job = session.merge(job)
        job.enabled = enabled
        job.updated_at = datetime.utcnow()
        session.flush()
        return job


def update_last_triggered(task_type: str, wind_farm_code: str) -> None:
    with db_session() as session:
        session.query(AutopredictJobConfig).filter(
            AutopredictJobConfig.task_type == task_type,
            AutopredictJobConfig.wind_farm_code == wind_farm_code,
        ).update({
            AutopredictJobConfig.last_triggered_at: datetime.utcnow(),
            AutopredictJobConfig.updated_at: datetime.utcnow(),
        })


def list_jobs_for_wind_farm(wind_farm_code: str) -> list[AutopredictJobConfig]:
    with db_session() as session:
        jobs = (
            session.query(AutopredictJobConfig)
            .filter(AutopredictJobConfig.wind_farm_code == wind_farm_code)
            .all()
        )
        return jobs


def list_all_jobs() -> list[AutopredictJobConfig]:
    with db_session() as session:
        return session.query(AutopredictJobConfig).all()


def delete_job(task_type: str, wind_farm_code: str) -> None:
    _validate_task_type(task_type)
    with db_session() as session:
        session.query(AutopredictJobConfig).filter(
            AutopredictJobConfig.task_type == task_type,
            AutopredictJobConfig.wind_farm_code == wind_farm_code,
        ).delete()


__all__ = [
    "VALID_TASK_TYPES",
    "get_or_create_job",
    "set_job_enabled",
    "update_last_triggered",
    "list_jobs_for_wind_farm",
    "list_all_jobs",
    "delete_job",
]


