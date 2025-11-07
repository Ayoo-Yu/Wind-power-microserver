"""Celery tasks wrapping the legacy auto prediction scripts.

These tasks execute the existing training / prediction entrypoints in a
subprocess while injecting the desired ``WIND_FARM_CODE`` so that the
storage isolation logic that was implemented previously continues to work.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from celery.schedules import crontab
from celery.utils.log import get_task_logger

from config import Config
from celery_app import celery_app
from services.task_history_service import record_task_history
from services.autopredict_config_service import update_last_triggered, list_all_jobs
DEFAULT_SCHEDULES = {
    "short": {
        "train": crontab(hour=3, minute=0),
        "predict": crontab(hour=8, minute=0),
    },
    "medium": {
        "train": crontab(hour=4, minute=0),
        "predict": crontab(hour=9, minute=0),
    },
    "supershort": {
        "train": crontab(hour=4, minute=30),
        "predict": crontab(minute="*/15"),
    },
}



LOGGER = get_task_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
AUTO_SCRIPTS_DIR = BASE_DIR / "auto_scripts" / "scripts"


SHORT_AUTO_PRE_TRAIN = AUTO_SCRIPTS_DIR / "short" / "auto_pre_train.py"
MIDDLE_AUTO_PRE_TRAIN = AUTO_SCRIPTS_DIR / "middle" / "auto_pre_train.py"
SUPERSHORT_TRAIN = AUTO_SCRIPTS_DIR / "supershort" / "train_supershort.py"
SUPERSHORT_PREDICT = AUTO_SCRIPTS_DIR / "supershort" / "predict_supershort.py"


def _execute_script(
    script_path: Path,
    *,
    args: Iterable[str],
    wind_farm_code: str,
    task_type: str,
    action: str,
) -> dict[str, str | int]:
    """Execute a python script in a subprocess with the requested env."""

    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    env = os.environ.copy()
    env["WIND_FARM_CODE"] = wind_farm_code
    env.setdefault("DEFAULT_WIND_FARM_CODE", Config.DEFAULT_WIND_FARM_CODE)

    command = [sys.executable, str(script_path), *args]
    LOGGER.info("Executing autopredict script", extra={
        "script": str(script_path),
        "args": list(args),
        "wind_farm_code": wind_farm_code,
    })

    completed = subprocess.run(
        command,
        env=env,
        cwd=str(script_path.parent),
        capture_output=True,
        text=True,
    )

    result_payload: dict[str, str | int] = {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "script": str(script_path),
    }

    if completed.returncode == 0:
        LOGGER.info(
            "Autopredict script completed successfully",
            extra={"script": str(script_path), "wind_farm_code": wind_farm_code},
        )
        record_task_history(
            task_type=task_type,
            wind_farm_code=wind_farm_code,
            action=action,
            status="success",
        )
        update_last_triggered(task_type, wind_farm_code)
    else:
        LOGGER.error(
            "Autopredict script failed",
            extra={
                "script": str(script_path),
                "wind_farm_code": wind_farm_code,
                "returncode": completed.returncode,
                "stderr": completed.stderr,
            },
        )
        record_task_history(
            task_type=task_type,
            wind_farm_code=wind_farm_code,
            action=action,
            status="failed",
            details=(completed.stderr or completed.stdout)[:2000],
        )
        completed.check_returncode()

    return result_payload


@celery_app.task(name="autopredict.short.train", bind=True)
def train_short(self, wind_farm_code: str, mode: str = "train") -> dict[str, str | int]:
    """Train short-term model using the legacy script."""

    return _execute_script(
        SHORT_AUTO_PRE_TRAIN,
        args=["--mode", mode],
        wind_farm_code=wind_farm_code,
        task_type="short",
        action=f"train:{mode}",
    )


@celery_app.task(name="autopredict.short.predict", bind=True)
def predict_short(self, wind_farm_code: str) -> dict[str, str | int]:
    """Run short-term prediction using the legacy script."""

    return _execute_script(
        SHORT_AUTO_PRE_TRAIN,
        args=["--mode", "predict"],
        wind_farm_code=wind_farm_code,
        task_type="short",
        action="predict",
    )


@celery_app.task(name="autopredict.middle.train", bind=True)
def train_middle(self, wind_farm_code: str, mode: str = "train") -> dict[str, str | int]:
    """Train middle-term model using the legacy script."""

    return _execute_script(
        MIDDLE_AUTO_PRE_TRAIN,
        args=["--mode", mode],
        wind_farm_code=wind_farm_code,
        task_type="medium",
        action=f"train:{mode}",
    )


@celery_app.task(name="autopredict.middle.predict", bind=True)
def predict_middle(self, wind_farm_code: str) -> dict[str, str | int]:
    """Run middle-term prediction using the legacy script."""

    return _execute_script(
        MIDDLE_AUTO_PRE_TRAIN,
        args=["--mode", "predict"],
        wind_farm_code=wind_farm_code,
        task_type="medium",
        action="predict",
    )


@celery_app.task(name="autopredict.supershort.train", bind=True)
def train_supershort(self, wind_farm_code: str) -> dict[str, str | int]:
    """Run supershort training script."""

    return _execute_script(
        SUPERSHORT_TRAIN,
        args=[],
        wind_farm_code=wind_farm_code,
        task_type="supershort",
        action="train",
    )


@celery_app.task(name="autopredict.supershort.predict", bind=True)
def predict_supershort(self, wind_farm_code: str) -> dict[str, str | int]:
    """Run supershort prediction script."""

    return _execute_script(
        SUPERSHORT_PREDICT,
        args=[],
        wind_farm_code=wind_farm_code,
        task_type="supershort",
        action="predict",
    )


@celery_app.task(name="autopredict.schedule.dispatch.short.train")
def enqueue_short_training() -> None:
    for job in list_all_jobs():
        if job.task_type != "short" or not job.enabled:
            continue
        train_short.apply_async((job.wind_farm_code, "train"))


@celery_app.task(name="autopredict.schedule.dispatch.short.predict")
def enqueue_short_prediction() -> None:
    for job in list_all_jobs():
        if job.task_type != "short" or not job.enabled:
            continue
        predict_short.apply_async((job.wind_farm_code,))


@celery_app.task(name="autopredict.schedule.dispatch.medium.train")
def enqueue_middle_training() -> None:
    for job in list_all_jobs():
        if job.task_type != "medium" or not job.enabled:
            continue
        train_middle.apply_async((job.wind_farm_code, "train"))


@celery_app.task(name="autopredict.schedule.dispatch.medium.predict")
def enqueue_middle_prediction() -> None:
    for job in list_all_jobs():
        if job.task_type != "medium" or not job.enabled:
            continue
        predict_middle.apply_async((job.wind_farm_code,))


@celery_app.task(name="autopredict.schedule.dispatch.supershort.train")
def enqueue_supershort_training() -> None:
    for job in list_all_jobs():
        if job.task_type != "supershort" or not job.enabled:
            continue
        train_supershort.apply_async((job.wind_farm_code,))


@celery_app.task(name="autopredict.schedule.dispatch.supershort.predict")
def enqueue_supershort_prediction() -> None:
    for job in list_all_jobs():
        if job.task_type != "supershort" or not job.enabled:
            continue
        predict_supershort.apply_async((job.wind_farm_code,))


@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        DEFAULT_SCHEDULES["short"]["train"],
        enqueue_short_training.s(),
        name="autopredict.schedule.short.train",
    )
    sender.add_periodic_task(
        DEFAULT_SCHEDULES["short"]["predict"],
        enqueue_short_prediction.s(),
        name="autopredict.schedule.short.predict",
    )
    sender.add_periodic_task(
        DEFAULT_SCHEDULES["medium"]["train"],
        enqueue_middle_training.s(),
        name="autopredict.schedule.medium.train",
    )
    sender.add_periodic_task(
        DEFAULT_SCHEDULES["medium"]["predict"],
        enqueue_middle_prediction.s(),
        name="autopredict.schedule.medium.predict",
    )
    sender.add_periodic_task(
        DEFAULT_SCHEDULES["supershort"]["train"],
        enqueue_supershort_training.s(),
        name="autopredict.schedule.supershort.train",
    )
    sender.add_periodic_task(
        DEFAULT_SCHEDULES["supershort"]["predict"],
        enqueue_supershort_prediction.s(),
        name="autopredict.schedule.supershort.predict",
    )


__all__ = [
    "train_short",
    "predict_short",
    "train_middle",
    "predict_middle",
    "train_supershort",
    "predict_supershort",
]


