from pathlib import Path

from celery import states
from flask import current_app

from task_queue import celery_app
from services.job_service import mark_job_started, update_job_status
from services.file_service import find_file_by_id
from windpower_core.training import run_prediction


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

        current_app.logger.info("[Job %s] 预测结果文件: %s", job_id, result.output_file)
        update_job_status(job_id, states.SUCCESS, result_path=str(result.output_file))
        return {
            "forecast_file": str(result.output_file),
        }
    except Exception as exc:
        current_app.logger.exception("[Job %s] 预测任务失败: %s", job_id, exc)
        update_job_status(job_id, states.FAILURE, error=str(exc))
        raise
