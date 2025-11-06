from celery import states
from flask import current_app

from task_queue import celery_app
from services.job_service import mark_job_started, update_job_status


@celery_app.task(bind=True, name="jobs.train_model")
def train_model_task(self, payload: dict):
    job_id = self.request.id
    mark_job_started(job_id)
    try:
        current_app.logger.info("[Job %s] 接收到训练任务: %s", job_id, payload)
        # TODO: Step4 将训练流程接入此处
        current_app.logger.info("[Job %s] 训练任务占位执行完成", job_id)
        update_job_status(job_id, states.SUCCESS)
        return {"status": "ok"}
    except Exception as exc:
        current_app.logger.exception("[Job %s] 训练任务失败: %s", job_id, exc)
        update_job_status(job_id, states.FAILURE, error=str(exc))
        raise
