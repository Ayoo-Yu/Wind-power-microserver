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
        input_snapshot_id = None
        model_version_id = None
        if run_id:
            from services.prediction_lineage_service import capture_prediction_input_snapshot
            with db_session() as lineage_session:
                snapshot = capture_prediction_input_snapshot(
                    lineage_session,
                    prediction_run_id=run_id,
                    farm_code=farm_code,
                    task_type=task_type,
                )
                input_snapshot_id = snapshot.id
                model_version_id = snapshot.model_version_id
        from services.forecast_service import run_daily_prediction
        from services.model_manager import ModelManager
        from services.calibration_manager import CalibrationManager

        ftype = _map_task_type(task_type)
        model_mgr = ModelManager()
        cal_mgr = CalibrationManager()
        with db_session() as session:
            result = run_daily_prediction(
                farm_code,
                ftype,
                model_mgr,
                cal_mgr,
                session,
                prediction_run_id=run_id,
                input_snapshot_id=input_snapshot_id,
                model_version_id=model_version_id,
            )

        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "prediction failed"))
        result["input_snapshot_id"] = input_snapshot_id
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
        input_snapshot_id = None
        model_version_id = None
        if run_id:
            from services.prediction_lineage_service import capture_prediction_input_snapshot
            with db_session() as lineage_session:
                snapshot = capture_prediction_input_snapshot(
                    lineage_session,
                    prediction_run_id=run_id,
                    farm_code=farm_code,
                    task_type="supershort",
                )
                input_snapshot_id = snapshot.id
                model_version_id = snapshot.model_version_id
        from services.forecast_service import run_ultrashort_prediction
        from services.model_manager import ModelManager
        from services.calibration_manager import CalibrationManager

        model_mgr = ModelManager()
        cal_mgr = CalibrationManager()
        with db_session() as session:
            result = run_ultrashort_prediction(
                farm_code,
                model_mgr,
                cal_mgr,
                session,
                prediction_run_id=run_id,
                input_snapshot_id=input_snapshot_id,
                model_version_id=model_version_id,
            )

        if result.get("status") != "ok":
            raise RuntimeError(result.get("message", "supershort prediction failed"))
        result["input_snapshot_id"] = input_snapshot_id
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


@celery_app.task(bind=True, max_retries=1, soft_time_limit=600)
def run_regulatory_evaluation(self, end_date_str=None, lookback_days=None):
    """滚动复算南网日评估，吸收延迟到达的实测和限电数据。"""

    from db_models import WindFarm
    from services.regulatory_evaluation_service import evaluate_regulatory_period

    try:
        if end_date_str:
            evaluation_end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            evaluation_end = datetime.now(_BJ_TZ).date() - timedelta(days=1)
        days = int(
            lookback_days
            if lookback_days is not None
            else os.environ.get("REGULATORY_EVALUATION_LOOKBACK_DAYS", "3")
        )
        days = min(max(days, 1), 31)
        evaluation_start = evaluation_end - timedelta(days=days - 1)

        with db_session() as session:
            query = session.query(WindFarm)
            if hasattr(WindFarm, "deleted_at"):
                query = query.filter(WindFarm.deleted_at.is_(None))
            if hasattr(WindFarm, "is_active"):
                query = query.filter(WindFarm.is_active.is_(True))
            farms = query.order_by(WindFarm.farm_code).all()
            summaries = []
            for farm in farms:
                capacity = float(farm.capacity or 0)
                if capacity <= 0:
                    summaries.append({
                        "farm_code": farm.farm_code,
                        "status": "blocked",
                        "message": "场站装机容量未配置",
                    })
                    continue
                result = evaluate_regulatory_period(
                    session,
                    farm_code=farm.farm_code,
                    capacity_mw=capacity,
                    start_date=evaluation_start,
                    end_date=evaluation_end,
                    persist=True,
                )
                summaries.append({
                    "farm_code": farm.farm_code,
                    "status": "success",
                    "metrics": {
                        key: {
                            "status": value["status"],
                            "complete_day_count": value["complete_day_count"],
                            "accuracy_percent": value["accuracy_percent"],
                        }
                        for key, value in result["metrics"].items()
                    },
                })
        return {
            "status": "success",
            "start_date": evaluation_start.isoformat(),
            "end_date": evaluation_end.isoformat(),
            "farm_count": len(summaries),
            "farms": summaries,
        }
    except Exception as exc:
        logger.exception("南网日评估任务执行失败")
        raise self.retry(exc=exc, countdown=120)


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


@celery_app.task(bind=True, max_retries=3, soft_time_limit=240)
def process_report_outbox(self, batch_size=20):
    """发送已持久化的上报任务并恢复中断任务。"""

    try:
        from services.report_outbox_service import dispatch_batch

        return dispatch_batch(
            db_session,
            limit=max(1, min(int(batch_size), 100)),
            worker_id=self.request.hostname,
        )
    except Exception as exc:
        logger.exception("Report outbox dispatch failed")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=240)
def scan_scheduled_reports(self):
    """由 Celery Beat 扫描到期的自动上报配置。"""

    if os.environ.get("REPORT_SCHEDULER_MODE", "embedded").lower() != "celery":
        return {"status": "skipped", "reason": "scheduler mode is not celery"}
    try:
        from routes.report_management_router import check_and_execute_scheduled_reports

        result = check_and_execute_scheduled_reports()
        return {"status": "ok", "result": result}
    except Exception as exc:
        logger.exception("Scheduled report scan failed")
        raise self.retry(exc=exc, countdown=30)
