from pathlib import Path
from datetime import datetime
import json

from celery import states
from flask import current_app

from task_queue import celery_app
from services.job_service import mark_job_started, update_job_status
from services.file_service import find_file_by_id
from services.modeltrain_service import run_modeltrain
from database_config import SessionLocal, minio_client
try:
    from ..config import MINIO_CONFIG
except ImportError:  # 在脚本模式下回退到绝对导入
    from config import MINIO_CONFIG

try:
    from ..db_models import Dataset
except ImportError:  # 在脚本模式下回退到绝对导入
    from db_models import Dataset  # type: ignore
from services.storage_service import get_model_path, get_scaler_path, get_prediction_path
from windpower_core.storage import normalize_wind_farm_code, sanitize_filename


@celery_app.task(bind=True, name="jobs.train_model")
def train_model_task(self, payload: dict):
    job_id = self.request.id
    mark_job_started(job_id)
    try:
        current_app.logger.info("[Job %s] 接收到训练任务: %s", job_id, payload)

        file_id = payload["file_id"]
        model = payload.get("model", "DEFAULT")
        train_ratio = float(payload.get("train_ratio", 0.9))
        custom_params = payload.get("custom_params")

        upload_path = find_file_by_id(file_id, current_app.config['UPLOAD_FOLDER'])
        if not upload_path:
            raise ValueError(f"未找到 file_id={file_id} 对应的训练数据")

        forecast_file_path, model_filepath, scaler_filepath = run_modeltrain(
            upload_path,
            model,
            train_ratio,
            custom_params,
        )

        dataset_record = None
        if SessionLocal is not None:
            session = SessionLocal()
            try:
                dataset_record = session.query(Dataset).filter(Dataset.file_id == file_id).first()
            finally:
                session.close()

        default_wind_farm_code = MINIO_CONFIG.get("default_wind_farm_code", "default-farm")
        raw_wind_farm_code = None
        if dataset_record:
            raw_wind_farm_code = dataset_record.wind_farm_code or dataset_record.wind_farm
        raw_wind_farm_code = raw_wind_farm_code or payload.get("wind_farm_code")
        wind_farm_code = normalize_wind_farm_code(raw_wind_farm_code, default_wind_farm_code)

        trained_at = datetime.utcnow()
        model_version = payload.get("model_version") or trained_at.strftime("%Y%m%d%H%M%S")

        artifacts = {
            "model": {
                "bucket": None,
                "object": None,
                "uri": None,
                "local_path": str(model_filepath),
            },
            "scaler": {
                "bucket": None,
                "object": None,
                "uri": None,
                "local_path": str(scaler_filepath),
            },
            "forecast": {
                "bucket": None,
                "object": None,
                "uri": None,
                "local_path": str(forecast_file_path),
            },
        }

        try:
            if minio_client is not None:
                model_object_name = get_model_path(
                    model_type=model,
                    model_name=model_version,
                    wind_farm_code=wind_farm_code,
                    trained_at=trained_at,
                )
                minio_client.fput_object(
                    MINIO_CONFIG["buckets"]["models"],
                    model_object_name,
                    model_filepath,
                )
                artifacts["model"].update(
                    bucket=MINIO_CONFIG["buckets"]["models"],
                    object=model_object_name,
                    uri=f"s3://{MINIO_CONFIG['buckets']['models']}/{model_object_name}",
                )

                scaler_object_name = get_scaler_path(
                    model_type=model,
                    wind_farm_code=wind_farm_code,
                    created_at=trained_at,
                )
                minio_client.fput_object(
                    MINIO_CONFIG["buckets"]["scalers"],
                    scaler_object_name,
                    scaler_filepath,
                )
                artifacts["scaler"].update(
                    bucket=MINIO_CONFIG["buckets"]["scalers"],
                    object=scaler_object_name,
                    uri=f"s3://{MINIO_CONFIG['buckets']['scalers']}/{scaler_object_name}",
                )

                forecast_object_name = get_prediction_path(
                    prediction_type="train",
                    model_id=model_version,
                    wind_farm_code=wind_farm_code,
                    filename=sanitize_filename(Path(forecast_file_path).name, fallback="forecast.csv"),
                    generated_at=trained_at,
                )
                minio_client.fput_object(
                    MINIO_CONFIG["buckets"]["predictions"],
                    forecast_object_name,
                    forecast_file_path,
                )
                artifacts["forecast"].update(
                    bucket=MINIO_CONFIG["buckets"]["predictions"],
                    object=forecast_object_name,
                    uri=f"s3://{MINIO_CONFIG['buckets']['predictions']}/{forecast_object_name}",
                )
        except Exception as upload_exc:
            current_app.logger.exception("[Job %s] 上传训练成果到 MinIO 失败: %s", job_id, upload_exc)

        result_payload = {
            "wind_farm_code": wind_farm_code,
            "model_version": model_version,
            "artifacts": artifacts,
        }

        current_app.logger.info("[Job %s] 训练结果: %s", job_id, result_payload)
        update_job_status(job_id, states.SUCCESS, result_path=json.dumps(result_payload, ensure_ascii=False))
        return result_payload
    except Exception as exc:
        current_app.logger.exception("[Job %s] 训练任务失败: %s", job_id, exc)
        update_job_status(job_id, states.FAILURE, error=str(exc))
        raise
