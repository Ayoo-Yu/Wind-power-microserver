import os
import sys
import subprocess
import logging
from datetime import datetime

# Ensure backend-autopredict root is on sys.path for db_session / db_models imports
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from . import celery_app
from db_session import db_session
from db_models import PredictionTask, PredictionRun

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT_PATHS = {
    "short": os.path.join(BASE_DIR, "auto_scripts", "scripts", "short", "auto_pre_train.py"),
    "medium": os.path.join(BASE_DIR, "auto_scripts", "scripts", "middle", "auto_pre_train.py"),
    "supershort_predict": os.path.join(BASE_DIR, "auto_scripts", "scripts", "supershort", "predict_supershort.py"),
    "supershort_train": os.path.join(BASE_DIR, "auto_scripts", "scripts", "supershort", "train_supershort.py"),
}

PYTHON_BIN = sys.executable


def _get_task_id(farm_code, task_type):
    with db_session() as session:
        task = session.query(PredictionTask).filter_by(
            farm_code=farm_code, task_type=task_type
        ).first()
        return task.id if task else None


def _create_run_record(task_id, action, celery_task_id):
    with db_session() as session:
        run = PredictionRun(
            task_id=task_id,
            celery_task_id=celery_task_id,
            action=action,
            status="running",
            started_at=datetime.now(),
        )
        session.add(run)
        session.flush()
        return run.id


def _finish_run_and_update_task(run_id, task_id, action, status, error_message=None):
    """Atomically finish a run record and update the task status in one session."""
    with db_session() as session:
        if run_id:
            run = session.query(PredictionRun).get(run_id)
            if run:
                run.status = status
                run.finished_at = datetime.now()
                if run.started_at:
                    run.duration_sec = int((run.finished_at - run.started_at).total_seconds())
                run.error_message = error_message
        if task_id:
            task = session.query(PredictionTask).get(task_id)
            if task:
                now = datetime.now()
                if action == "train":
                    task.last_train_status = status
                    task.last_train_at = now
                else:
                    task.last_predict_status = status
                    task.last_predict_at = now
                if error_message:
                    task.last_error = error_message
                task.updated_at = now


def _update_task_running(task_id, action):
    """Mark task as running (separate from finish since run record stays 'running')."""
    if not task_id:
        return
    with db_session() as session:
        task = session.query(PredictionTask).get(task_id)
        if not task:
            return
        if action == "train":
            task.last_train_status = "running"
        else:
            task.last_predict_status = "running"
        task.updated_at = datetime.now()


@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800)
def train_model(self, farm_code, task_type):
    task_id = _get_task_id(farm_code, task_type)
    run_id = _create_run_record(task_id, "train", self.request.id) if task_id else None
    script = SCRIPT_PATHS.get(task_type)
    if not script or not os.path.exists(script):
        msg = f"训练脚本不存在: {script}"
        _finish_run_and_update_task(run_id, task_id, "train", "failed", msg)
        return {"status": "failed", "error": msg}
    try:
        _update_task_running(task_id, "train")
        env = os.environ.copy()
        env["FARM_CODE"] = farm_code
        result = subprocess.run(
            [PYTHON_BIN, script, "--mode", "train", "--farm_code", farm_code],
            capture_output=True, text=True, timeout=1700, env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-2000:] if result.stderr else "训练进程非零退出")
        _finish_run_and_update_task(run_id, task_id, "train", "success")
        return {"status": "success", "farm_code": farm_code, "task_type": task_type}
    except Exception as exc:
        _finish_run_and_update_task(run_id, task_id, "train", "failed", str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=600)
def run_prediction(self, farm_code, task_type):
    task_id = _get_task_id(farm_code, task_type)
    run_id = _create_run_record(task_id, "predict", self.request.id) if task_id else None
    script = SCRIPT_PATHS.get(task_type)
    if not script or not os.path.exists(script):
        msg = f"预测脚本不存在: {script}"
        _finish_run_and_update_task(run_id, task_id, "predict", "failed", msg)
        return {"status": "failed", "error": msg}
    try:
        _update_task_running(task_id, "predict")
        env = os.environ.copy()
        env["FARM_CODE"] = farm_code
        result = subprocess.run(
            [PYTHON_BIN, script, "--mode", "predict", "--farm_code", farm_code],
            capture_output=True, text=True, timeout=550, env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-2000:] if result.stderr else "预测进程非零退出")
        _finish_run_and_update_task(run_id, task_id, "predict", "success")
        return {"status": "success", "farm_code": farm_code, "task_type": task_type}
    except Exception as exc:
        _finish_run_and_update_task(run_id, task_id, "predict", "failed", str(exc))
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=300)
def run_supershort_predict(self, farm_code):
    task_id = _get_task_id(farm_code, "supershort")
    run_id = _create_run_record(task_id, "predict", self.request.id) if task_id else None
    script = SCRIPT_PATHS.get("supershort_predict")
    if not script or not os.path.exists(script):
        msg = f"超短期预测脚本不存在: {script}"
        _finish_run_and_update_task(run_id, task_id, "predict", "failed", msg)
        return {"status": "failed", "error": msg}
    try:
        _update_task_running(task_id, "predict")
        env = os.environ.copy()
        env["FARM_CODE"] = farm_code
        result = subprocess.run(
            [PYTHON_BIN, script, "--farm_code", farm_code],
            capture_output=True, text=True, timeout=280, env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-2000:] if result.stderr else "超短期预测进程非零退出")
        _finish_run_and_update_task(run_id, task_id, "predict", "success")
        return {"status": "success", "farm_code": farm_code}
    except Exception as exc:
        _finish_run_and_update_task(run_id, task_id, "predict", "failed", str(exc))
        raise self.retry(exc=exc, countdown=15)


@celery_app.task
def merge_predictions(farm_code, date_str):
    task_id = _get_task_id(farm_code, "medium")
    run_id = _create_run_record(task_id, "merge", None) if task_id else None
    script_dir = os.path.join(BASE_DIR, "auto_scripts", "scripts", "middle")
    merge_script = os.path.join(script_dir, "run_auto_predict.py")
    try:
        env = os.environ.copy()
        env["FARM_CODE"] = farm_code
        env["TARGET_DATE"] = date_str
        if os.path.exists(merge_script):
            subprocess.run(
                [PYTHON_BIN, merge_script, "--farm_code", farm_code, "--date", date_str],
                capture_output=True, text=True, timeout=300, env=env,
            )
        _finish_run_and_update_task(run_id, task_id, "merge", "success")
        return {"status": "success", "farm_code": farm_code, "date": date_str}
    except Exception as exc:
        _finish_run_and_update_task(run_id, task_id, "merge", "failed", str(exc))
        return {"status": "failed", "error": str(exc)}
