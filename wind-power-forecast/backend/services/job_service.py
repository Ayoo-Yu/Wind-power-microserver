from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from db_models import Job
from db_session import db_session


def create_job(
    job_id: str,
    job_type: str,
    payload: Optional[dict] = None,
    user_id: Optional[int] = None,
    *,
    wind_farm_id: Optional[int] = None,
    wind_farm_code: Optional[str] = None,
) -> Job:
    with db_session() as session:
        job = Job(
            job_id=job_id,
            job_type=job_type,
            status="pending",
            payload=payload,
            user_id=user_id,
            submit_time=datetime.utcnow(),
            wind_farm_id=wind_farm_id,
            wind_farm_code=wind_farm_code,
        )
        session.add(job)
        session.flush()
        session.refresh(job)
        return job


def update_job_metadata(job_id: str, **kwargs) -> None:
    with db_session() as session:
        job = session.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)


def update_job_status(job_id: str, status: str, *, result_path: Optional[str] = None, error: Optional[str] = None) -> None:
    with db_session() as session:
        job = session.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return

        job.status = status
        if result_path is not None:
            job.result_path = result_path
        if error is not None:
            job.error = error
        if status in {"success", "failed", "revoked"}:
            job.end_time = datetime.utcnow()


def mark_job_started(job_id: str) -> None:
    with db_session() as session:
        job = session.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return
        job.status = "running"
        job.start_time = datetime.utcnow()


def get_job(job_id: str) -> Optional[Job]:
    with db_session() as session:
        job = session.query(Job).filter(Job.job_id == job_id).first()
        if job:
            session.expunge(job)
        return job


def _parse_result(value: Optional[str]):
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def serialize_job(job: Job) -> dict:
    return {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "status": job.status,
        "payload": job.payload,
        "error": job.error,
        "result": _parse_result(job.result_path),
        "result_raw": job.result_path,
        "submit_time": job.submit_time.isoformat() if job.submit_time else None,
        "start_time": job.start_time.isoformat() if job.start_time else None,
        "end_time": job.end_time.isoformat() if job.end_time else None,
        "user_id": job.user_id,
        "wind_farm_id": job.wind_farm_id,
        "wind_farm_code": job.wind_farm_code,
    }
