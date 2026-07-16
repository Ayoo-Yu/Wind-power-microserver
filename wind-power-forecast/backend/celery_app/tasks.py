import os
import re
import sys
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.exc import OperationalError, DisconnectionError, InterfaceError

from . import celery_app
from db_session import db_session
from services.prediction_run_service import (
    claim_prediction_run,
    finish_prediction_run,
)

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_FARM_CODE_RE = re.compile(r'^[A-Za-z0-9_-]{1,50}$')


_BJ_TZ = timezone(timedelta(hours=8))


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


def _claim_run_record(
    farm_code,
    task_type,
    action,
    celery_task_id,
    attempt_number,
):
    with db_session() as session:
        return claim_prediction_run(
            session,
            farm_code=farm_code,
            task_type=task_type,
            action=action,
            celery_task_id=celery_task_id,
            attempt_number=attempt_number,
        )


def _finish_run(
    run_id,
    attempt_number,
    status,
    error_message=None,
    result_data=None,
):
    with db_session() as session:
        return finish_prediction_run(
            session,
            run_id=run_id,
            attempt_number=attempt_number,
            status=status,
            error_message=error_message,
            result_data=result_data,
        )


def _claim_skip_result(claim, farm_code, task_type):
    return {
        "status": "skipped",
        "farm_code": farm_code,
        "task_type": task_type,
        "prediction_run_id": claim.run_id,
        "reason": claim.reason,
        "active_run_id": claim.active_run_id,
    }


def _map_task_type(task_type: str) -> str:
    """Map Celery task_type to forecast_service type. 'medium' -> 'mid'."""
    return "mid" if task_type == "medium" else task_type


@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800)
def train_model(self, farm_code, task_type):
    _validate_farm_code(farm_code)
    attempt_number = int(self.request.retries or 0) + 1
    try:
        claim = _claim_run_record(
            farm_code,
            task_type,
            "train",
            self.request.id,
            attempt_number,
        )
    except Exception as exc:
        if _is_db_error(exc):
            logger.warning(f"train_model DB unavailable at startup for {farm_code}/{task_type}, will retry: {exc}")
            raise self.retry(exc=exc, countdown=120)
        raise
    if not claim.should_execute:
        return _claim_skip_result(claim, farm_code, task_type)
    run_id = claim.run_id
    try:
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
        _finish_run(run_id, attempt_number, "success", result_data=result)
        return {
            "status": "success",
            "farm_code": farm_code,
            "task_type": task_type,
            "prediction_run_id": run_id,
        }
    except Exception as exc:
        db_down = _is_db_error(exc)
        if not db_down:
            try:
                _finish_run(run_id, attempt_number, "failed", str(exc))
            except Exception:
                logger.warning("train_model: failed to record failure status (DB may be down)")
        else:
            logger.warning(f"train_model DB error for {farm_code}/{task_type}, will retry: {exc}")
        raise self.retry(exc=exc, countdown=120 if db_down else 60)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=600)
def run_prediction(self, farm_code, task_type):
    _validate_farm_code(farm_code)
    attempt_number = int(self.request.retries or 0) + 1
    try:
        claim = _claim_run_record(
            farm_code,
            task_type,
            "predict",
            self.request.id,
            attempt_number,
        )
    except Exception as exc:
        if _is_db_error(exc):
            logger.warning(f"run_prediction DB unavailable at startup for {farm_code}/{task_type}, will retry: {exc}")
            raise self.retry(exc=exc, countdown=120)
        raise
    if not claim.should_execute:
        return _claim_skip_result(claim, farm_code, task_type)
    run_id = claim.run_id
    try:
        input_snapshot_id = None
        model_version_id = None
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
        _finish_run(run_id, attempt_number, "success", result_data=result)
        return {
            "status": "success",
            "farm_code": farm_code,
            "task_type": task_type,
            "prediction_run_id": run_id,
        }
    except Exception as exc:
        db_down = _is_db_error(exc)
        if not db_down:
            try:
                _finish_run(run_id, attempt_number, "failed", str(exc))
            except Exception:
                logger.warning("run_prediction: failed to record failure status (DB may be down)")
        else:
            logger.warning(f"run_prediction DB error for {farm_code}/{task_type}, will retry: {exc}")
        raise self.retry(exc=exc, countdown=120 if db_down else 30)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=300)
def run_calibration(self, farm_code, task_type):
    _validate_farm_code(farm_code)
    attempt_number = int(self.request.retries or 0) + 1
    try:
        claim = _claim_run_record(
            farm_code,
            task_type,
            "calibrate",
            self.request.id,
            attempt_number,
        )
    except Exception as exc:
        if _is_db_error(exc):
            logger.warning(f"run_calibration DB unavailable at startup for {farm_code}/{task_type}, will retry: {exc}")
            raise self.retry(exc=exc, countdown=120)
        raise
    if not claim.should_execute:
        return _claim_skip_result(claim, farm_code, task_type)
    run_id = claim.run_id
    try:
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
        _finish_run(run_id, attempt_number, status, result_data=result)
        return {
            "status": status,
            "farm_code": farm_code,
            "task_type": task_type,
            "prediction_run_id": run_id,
            **result,
        }
    except Exception as exc:
        db_down = _is_db_error(exc)
        if not db_down:
            try:
                _finish_run(run_id, attempt_number, "failed", str(exc))
            except Exception:
                logger.warning("run_calibration: failed to record failure status (DB may be down)")
        else:
            logger.warning(f"run_calibration DB error for {farm_code}/{task_type}, will retry: {exc}")
        raise self.retry(exc=exc, countdown=120 if db_down else 30)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=300)
def run_supershort_predict(self, farm_code):
    _validate_farm_code(farm_code)
    attempt_number = int(self.request.retries or 0) + 1
    try:
        claim = _claim_run_record(
            farm_code,
            "supershort",
            "predict",
            self.request.id,
            attempt_number,
        )
    except Exception as exc:
        if _is_db_error(exc):
            logger.warning(f"run_supershort_predict DB unavailable at startup for {farm_code}, will retry: {exc}")
            raise self.retry(exc=exc, countdown=120)
        raise
    if not claim.should_execute:
        return _claim_skip_result(claim, farm_code, "supershort")
    run_id = claim.run_id
    try:
        input_snapshot_id = None
        model_version_id = None
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
        _finish_run(run_id, attempt_number, "success", result_data=result)
        return {
            "status": "success",
            "farm_code": farm_code,
            "prediction_run_id": run_id,
        }
    except Exception as exc:
        db_down = _is_db_error(exc)
        if not db_down:
            try:
                _finish_run(run_id, attempt_number, "failed", str(exc))
            except Exception:
                logger.warning("run_supershort_predict: failed to record failure status (DB may be down)")
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
    attempt_number = int(self.request.retries or 0) + 1
    try:
        claim = _claim_run_record(
            farm_code,
            "medium",
            "merge",
            self.request.id,
            attempt_number,
        )
    except Exception as exc:
        if _is_db_error(exc):
            logger.warning(f"merge_predictions DB unavailable at startup for {farm_code}, will retry: {exc}")
            raise self.retry(exc=exc, countdown=120)
        raise
    if not claim.should_execute:
        return _claim_skip_result(claim, farm_code, "medium")
    run_id = claim.run_id
    merge_script = os.path.join(BASE_DIR, "auto_scripts", "scripts", "middle", "run_auto_predict.py")
    try:
        env = os.environ.copy()
        env["FARM_CODE"] = farm_code
        env["TARGET_DATE"] = date_str
        if os.path.exists(merge_script):
            completed = subprocess.run(
                [sys.executable, merge_script, "--farm_code", farm_code, "--date", date_str],
                capture_output=True, text=True, timeout=300, env=env,
            )
            if completed.returncode != 0:
                message = (completed.stderr or completed.stdout or "合并脚本执行失败").strip()
                raise RuntimeError(message[-2000:])
        else:
            raise FileNotFoundError(f"合并脚本不存在: {merge_script}")
        result = {"farm_code": farm_code, "date": date_str}
        _finish_run(run_id, attempt_number, "success", result_data=result)
        return {
            "status": "success",
            "prediction_run_id": run_id,
            **result,
        }
    except Exception as exc:
        db_down = _is_db_error(exc)
        if not db_down:
            try:
                _finish_run(run_id, attempt_number, "failed", str(exc))
            except Exception:
                logger.warning("merge_predictions: failed to record failure status (DB may be down)")
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

    try:
        from routes.report_management_router import check_and_execute_scheduled_reports

        result = check_and_execute_scheduled_reports()
        return {"status": "ok", "result": result}
    except Exception as exc:
        logger.exception("Scheduled report scan failed")
        raise self.retry(exc=exc, countdown=30)


def _acquire_weather_lock(task_id, timeout_seconds):
    """使用 Redis 防止同一个气象任务并发执行。"""

    import uuid
    import redis

    broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    client = redis.Redis.from_url(broker_url)
    key = f"windpower:weather-task-lock:{int(task_id)}"
    token = uuid.uuid4().hex
    acquired = client.set(
        key,
        token,
        nx=True,
        ex=max(7500, int(timeout_seconds) + 120),
    )
    return client, key, token, bool(acquired)


def _release_weather_lock(client, key, token):
    """仅释放当前执行者持有的气象任务锁。"""

    client.eval(
        """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        end
        return 0
        """,
        1,
        key,
        token,
    )


@celery_app.task(bind=True, max_retries=10, soft_time_limit=7200)
def run_weather_fetch(self, task_id, scheduled=True):
    """在独立 Worker 中执行气象文件拉取任务。"""

    from db_models import WeatherConnection, WeatherLog, WeatherTask
    from services.task_executor import execute_weather_task

    with db_session() as session:
        task = session.query(WeatherTask).filter(
            WeatherTask.id == int(task_id),
            WeatherTask.deleted_at.is_(None),
        ).first()
        if not task:
            return {"status": "skipped", "reason": "task_not_found", "task_id": task_id}
        if scheduled and not task.enabled:
            return {"status": "skipped", "reason": "task_disabled", "task_id": task_id}

        connection = session.query(WeatherConnection).filter(
            WeatherConnection.id == task.connection_id,
            WeatherConnection.deleted_at.is_(None),
        ).first()
        if not connection:
            session.add(WeatherLog(
                task_id=task.id,
                farm_code=task.farm_code,
                log_level="error",
                message="关联的 SSH 连接不存在",
                created_at=datetime.now(),
            ))
            return {"status": "failed", "reason": "connection_not_found", "task_id": task_id}

        try:
            lock = _acquire_weather_lock(task.id, task.timeout or 300)
        except Exception as exc:
            logger.exception("Weather task lock is unavailable")
            raise self.retry(exc=exc, countdown=30)

        client, key, token, acquired = lock
        if not acquired:
            return {"status": "skipped", "reason": "already_running", "task_id": task_id}

        try:
            result = execute_weather_task(task, connection, session)
            if result.get("success"):
                return {"status": "success", "task_id": task_id, **result}

            error = RuntimeError(result.get("error") or "气象任务执行失败")
            retry_count = max(0, min(int(task.retry_count or 0), 10))
            if self.request.retries < retry_count:
                raise self.retry(
                    exc=error,
                    countdown=min(300, 30 * (self.request.retries + 1)),
                    max_retries=retry_count,
                )
            return {"status": "failed", "task_id": task_id, **result}
        finally:
            try:
                _release_weather_lock(client, key, token)
            except Exception:
                logger.exception("Failed to release weather task lock: %s", task_id)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800)
def run_partition_maintenance(self):
    """创建未来分区并整理默认分区。"""

    try:
        from services.partition_maintenance_service import ensure_future_partitions

        return ensure_future_partitions()
    except Exception as exc:
        logger.exception("Partition maintenance failed")
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(bind=True, max_retries=0, soft_time_limit=7200)
def run_etext_pipeline(
    self,
    job_id=None,
    incoming_dir=None,
    force=False,
    started_at=None,
):
    """在独立 Worker 中执行 E 文本入库管道。"""

    from services.etext_config import read_config
    from services.etext_job_service import execute_pipeline

    if incoming_dir is None:
        config = read_config()
        if not config.get("enabled", True):
            return {"status": "skipped", "reason": "pipeline_disabled"}
        incoming_dir = config.get("incoming_dir") or None

    return execute_pipeline(
        incoming_dir=incoming_dir,
        force=bool(force),
        job_id=job_id,
        started_at=started_at,
    )
