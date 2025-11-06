from pathlib import Path

from celery import states
from flask import current_app

from task_queue import celery_app
from services.job_service import mark_job_started, update_job_status
from services.file_service import find_file_by_id
from services.modeltrain_service import run_modeltrain
from windpower_core.training import run_training


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

        result = run_training(
            data_file=Path(upload_path),
            model=model,
            train_ratio=train_ratio,
            custom_params=custom_params,
        )

        current_app.logger.info("[Job %s] 训练结果: %s", job_id, result)
        update_job_status(job_id, states.SUCCESS, result_path=str(result.forecast_file))
        return {
            "forecast_file": str(result.forecast_file),
            "model_file": str(result.model_file),
            "scaler_file": str(result.scaler_file),
        }
    except Exception as exc:
        current_app.logger.exception("[Job %s] 训练任务失败: %s", job_id, exc)
        update_job_status(job_id, states.FAILURE, error=str(exc))
        raise
