import os
import re
import sys
import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.exc import OperationalError, DisconnectionError, InterfaceError

from . import celery_app
from db_session import db_session
from db_models import PredictionTask, PredictionRun

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_FARM_CODE_RE = re.compile(r'^[A-Za-z0-9_-]{1,50}$')


_BJ_TZ = timezone(timedelta(hours=8))


def _utc_now():
    return datetime.now(_BJ_TZ).replace(tzinfo=None)


def _validate_farm_code(farm_code):
    if not _FARM_CODE_RE.match(farm_code):
        raise ValueError(f"Invalid farm_code: {farm_code!r}")


def _is_db_error(exc):
    """Check if an exception is a database connectivity error."""
    if isinstance(exc, (OperationalError, DisconnectionError, InterfaceError)):
        return True
    if isinstance(exc, RuntimeError) and "database connection unavailable" in str(exc):
        return True
    return False


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
            started_at=_utc_now(),
        )
        session.add(run)
        session.flush()
        return run.id


def _finish_run_and_update_task(run_id, task_id, action, status, error_message=None, result_data=None):
    with db_session() as session:
        if run_id:
            run = session.query(PredictionRun).get(run_id)
            if run:
                run.status = status
                run.finished_at = _utc_now()
                if run.started_at:
                    run.duration_sec = int((run.finished_at - run.started_at).total_seconds())
                run.error_message = error_message
                if result_data is not None:
                    run.result_json = json.dumps(result_data, default=str, ensure_ascii=False)
        if task_id:
            task = session.query(PredictionTask).get(task_id)
            if task:
                now = _utc_now()
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
        task.updated_at = _utc_now()


def _map_task_type(task_type: str) -> str:
    """Map Celery task_type to forecast_service type. 'medium' -> 'mid'."""
    return "mid" if task_type == "medium" else task_type


@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800)
def train_model(self, farm_code, task_type):
    _validate_farm_code(farm_code)
    try:
        task_id = _get_task_id(farm_code, task_type)
        run_id = _create_run_record(task_id, "train", self.request.id) if task_id else None
    except Exception as exc:
        if _is_db_error(exc):
            logger.warning(f"train_model DB unavailable at startup for {farm_code}/{task_type}, will retry: {exc}")
            raise self.retry(exc=exc, countdown=120)
        raise
    try:
        _update_task_running(task_id, "train")
        from services.model_manager import ModelManager
        mgr = ModelManager()

        if task_type == "supershort":
            from services.forecast_service import run_ultrashort_monthly_training
            with db_session() as session:
                result = run_ultrashort_monthly_training(farm_code, mgr, session)
        else:
            from services.forecast_service import run_monthly_training
            ftype = _map_task_type(task_type)
            with db_session() as session:
                result = run_monthly_training(farm_code, ftype, mgr, session)

        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "training failed"))
        _finish_run_and_update_task(run_id, task_id, "train", "success", result_data=result)
        return {"status": "success", "farm_code": farm_code, "task_type": task_type}
    except Exception as exc:
        db_down = _is_db_error(exc)
        if not db_down:
            try:
                _finish_run_and_update_task(run_id, task_id, "train", "failed", str(exc))
            except Exception:
                logger.warning(f"train_model: failed to record failure status (DB may be down)")
        else:
            logger.warning(f"train_model DB error for {farm_code}/{task_type}, will retry: {exc}")
        raise self.retry(exc=exc, countdown=120 if db_down else 60)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=600)
def run_prediction(self, farm_code, task_type):
    _validate_farm_code(farm_code)
    try:
        task_id = _get_task_id(farm_code, task_type)
        run_id = _create_run_record(task_id, "predict", self.request.id) if task_id else None
    except Exception as exc:
        if _is_db_error(exc):
            logger.warning(f"run_prediction DB unavailable at startup for {farm_code}/{task_type}, will retry: {exc}")
            raise self.retry(exc=exc, countdown=120)
        raise
    try:
        _update_task_running(task_id, "predict")
        from services.forecast_service import run_daily_prediction
        from services.model_manager import ModelManager
        from services.calibration_manager import CalibrationManager

        ftype = _map_task_type(task_type)
        model_mgr = ModelManager()
        cal_mgr = CalibrationManager()
        with db_session() as session:
            result = run_daily_prediction(farm_code, ftype, model_mgr, cal_mgr, session)

        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "prediction failed"))
        _finish_run_and_update_task(run_id, task_id, "predict", "success", result_data=result)
        return {"status": "success", "farm_code": farm_code, "task_type": task_type}
    except Exception as exc:
        db_down = _is_db_error(exc)
        if not db_down:
            try:
                _finish_run_and_update_task(run_id, task_id, "predict", "failed", str(exc))
            except Exception:
                logger.warning(f"run_prediction: failed to record failure status (DB may be down)")
        else:
            logger.warning(f"run_prediction DB error for {farm_code}/{task_type}, will retry: {exc}")
        raise self.retry(exc=exc, countdown=120 if db_down else 30)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=300)
def run_calibration(self, farm_code, task_type):
    _validate_farm_code(farm_code)
    try:
        task_id = _get_task_id(farm_code, task_type)
        run_id = _create_run_record(task_id, "calibrate", self.request.id) if task_id else None
    except Exception as exc:
        if _is_db_error(exc):
            logger.warning(f"run_calibration DB unavailable at startup for {farm_code}/{task_type}, will retry: {exc}")
            raise self.retry(exc=exc, countdown=120)
        raise
    try:
        _update_task_running(task_id, "calibrate")
        from services.calibration_manager import CalibrationManager
        cal_mgr = CalibrationManager()

        if task_type == "supershort":
            from services.forecast_service import run_ultrashort_calibration
            with db_session() as session:
                result = run_ultrashort_calibration(farm_code, cal_mgr, session)
        else:
            from services.forecast_service import run_daily_calibration
            ftype = _map_task_type(task_type)
            with db_session() as session:
                result = run_daily_calibration(farm_code, ftype, cal_mgr, session)

        status = "success" if result.get("status") == "ok" else "skipped"
        _finish_run_and_update_task(run_id, task_id, "calibrate", status, result_data=result)
        return {"status": status, "farm_code": farm_code, "task_type": task_type, **result}
    except Exception as exc:
        db_down = _is_db_error(exc)
        if not db_down:
            try:
                _finish_run_and_update_task(run_id, task_id, "calibrate", "failed", str(exc))
            except Exception:
                logger.warning(f"run_calibration: failed to record failure status (DB may be down)")
        else:
            logger.warning(f"run_calibration DB error for {farm_code}/{task_type}, will retry: {exc}")
        raise self.retry(exc=exc, countdown=120 if db_down else 30)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=300)
def run_supershort_predict(self, farm_code):
    _validate_farm_code(farm_code)
    try:
        task_id = _get_task_id(farm_code, "supershort")
        run_id = _create_run_record(task_id, "predict", self.request.id) if task_id else None
    except Exception as exc:
        if _is_db_error(exc):
            logger.warning(f"run_supershort_predict DB unavailable at startup for {farm_code}, will retry: {exc}")
            raise self.retry(exc=exc, countdown=120)
        raise
    try:
        _update_task_running(task_id, "predict")
        from services.forecast_service import run_ultrashort_prediction
        from services.model_manager import ModelManager
        from services.calibration_manager import CalibrationManager

        model_mgr = ModelManager()
        cal_mgr = CalibrationManager()
        with db_session() as session:
            result = run_ultrashort_prediction(farm_code, model_mgr, cal_mgr, session)

        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "supershort prediction failed"))
        _finish_run_and_update_task(run_id, task_id, "predict", "success", result_data=result)
        return {"status": "success", "farm_code": farm_code}
    except Exception as exc:
        db_down = _is_db_error(exc)
        if not db_down:
            try:
                _finish_run_and_update_task(run_id, task_id, "predict", "failed", str(exc))
            except Exception:
                logger.warning(f"run_supershort_predict: failed to record failure status (DB may be down)")
        else:
            logger.warning(f"run_supershort_predict DB error for {farm_code}, will retry: {exc}")
        raise self.retry(exc=exc, countdown=120 if db_down else 15)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=300)
def merge_predictions(self, farm_code, date_str):
    import subprocess
    _validate_farm_code(farm_code)
    try:
        task_id = _get_task_id(farm_code, "medium")
        run_id = _create_run_record(task_id, "merge", self.request.id) if task_id else None
    except Exception as exc:
        if _is_db_error(exc):
            logger.warning(f"merge_predictions DB unavailable at startup for {farm_code}, will retry: {exc}")
            raise self.retry(exc=exc, countdown=120)
        raise
    merge_script = os.path.join(BASE_DIR, "auto_scripts", "scripts", "middle", "run_auto_predict.py")
    try:
        env = os.environ.copy()
        env["FARM_CODE"] = farm_code
        env["TARGET_DATE"] = date_str
        if os.path.exists(merge_script):
            subprocess.run(
                [sys.executable, merge_script, "--farm_code", farm_code, "--date", date_str],
                capture_output=True, text=True, timeout=300, env=env,
            )
        _finish_run_and_update_task(run_id, task_id, "merge", "success")
        return {"status": "success", "farm_code": farm_code, "date": date_str}
    except Exception as exc:
        db_down = _is_db_error(exc)
        if not db_down:
            try:
                _finish_run_and_update_task(run_id, task_id, "merge", "failed", str(exc))
            except Exception:
                logger.warning(f"merge_predictions: failed to record failure status (DB may be down)")
        else:
            logger.warning(f"merge_predictions DB error for {farm_code}, will retry: {exc}")
        if db_down:
            raise self.retry(exc=exc, countdown=120)
        return {"status": "failed", "error": str(exc)}
