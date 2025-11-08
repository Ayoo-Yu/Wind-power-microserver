from pathlib import Path
from datetime import datetime
import json

from celery import states
from flask import current_app

from task_queue import celery_app
from services.job_service import mark_job_started, update_job_status
from services.file_service import find_file_by_id
from windpower_core.training import run_prediction
from database_config import SessionLocal, minio_client
try:
    from ..config import MINIO_CONFIG
except ImportError:  # 在脚本模式下回退到绝对导入
    from config import MINIO_CONFIG

try:
    from ..db_models import Dataset
except ImportError:  # 在脚本模式下回退到绝对导入
    from db_models import Dataset  # type: ignore
from services.storage_service import get_prediction_path
from windpower_core.storage import normalize_wind_farm_code, sanitize_filename


@celery_app.task(bind=True, name="jobs.predict")
def predict_task(self, payload: dict):
    job_id = self.request.id
    mark_job_started(job_id)
    try:
        current_app.logger.info("[Job %s] 接收到预测任务: %s", job_id, payload)

        csv_id = payload["csvfileId"]
        model_id = payload["modelfileId"]
        scaler_id = payload["scalerfileId"]
        window_size = int(payload.get("window_size", 16))

        csv_path = find_file_by_id(csv_id, current_app.config['UPLOAD_FOLDER'])
        model_path = find_file_by_id(model_id, current_app.config['UPLOAD_FOLDER'])
        scaler_path = find_file_by_id(scaler_id, current_app.config['UPLOAD_FOLDER'])

        if not all([csv_path, model_path, scaler_path]):
            raise ValueError("上传文件未找到，请检查 file_id 是否有效")

        result = run_prediction(
            csv_path=Path(csv_path),
            model_path=Path(model_path),
            scaler_path=Path(scaler_path),
            window_size=window_size,
        )
        output_file = Path(result.output_file)

        dataset_record = None
        if SessionLocal is not None:
            session = SessionLocal()
            try:
                dataset_record = session.query(Dataset).filter(Dataset.file_id == csv_id).first()
            finally:
                session.close()

        default_wind_farm_code = MINIO_CONFIG.get("default_wind_farm_code", "default-farm")
        raw_wind_farm_code = None
        if dataset_record:
            raw_wind_farm_code = dataset_record.wind_farm_code or dataset_record.wind_farm
        raw_wind_farm_code = raw_wind_farm_code or payload.get("wind_farm_code")
        wind_farm_code = normalize_wind_farm_code(raw_wind_farm_code, default_wind_farm_code)

        generated_at = datetime.utcnow()
        prediction_type = payload.get("prediction_type", "batch")
        model_identifier = payload.get("model_identifier") or model_id

        artifact = {
            "bucket": None,
            "object": None,
            "uri": None,
            "local_path": str(output_file),
        }

        try:
            if minio_client is not None:
                prediction_object = get_prediction_path(
                    prediction_type=prediction_type,
                    model_id=str(model_identifier),
                    wind_farm_code=wind_farm_code,
                    filename=sanitize_filename(output_file.name, fallback="prediction.csv"),
                    generated_at=generated_at,
                )
                minio_client.fput_object(
                    MINIO_CONFIG["buckets"]["predictions"],
                    prediction_object,
                    str(output_file),
                )
                artifact.update(
                    bucket=MINIO_CONFIG["buckets"]["predictions"],
                    object=prediction_object,
                    uri=f"s3://{MINIO_CONFIG['buckets']['predictions']}/{prediction_object}",
                )
        except Exception as upload_exc:
            current_app.logger.exception("[Job %s] 上传预测结果到 MinIO 失败: %s", job_id, upload_exc)

        result_payload = {
            "wind_farm_code": wind_farm_code,
            "artifacts": {
                "forecast": artifact,
            },
        }

        current_app.logger.info("[Job %s] 预测结果文件: %s", job_id, result_payload)
        update_job_status(job_id, states.SUCCESS, result_path=json.dumps(result_payload, ensure_ascii=False))
        return result_payload
    except Exception as exc:
        current_app.logger.exception("[Job %s] 预测任务失败: %s", job_id, exc)
        update_job_status(job_id, states.FAILURE, error=str(exc))
        raise
