"""初始化 prediction_tasks 表。

从 wind_farms 表读取所有活跃场站，为每个场站创建 3 条默认任务记录
（supershort / short / medium）。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_session import db_session
from db_models import PredictionTask
from sqlalchemy import text


DEFAULT_TASK_CONFIGS = [
    {
        "task_type": "supershort",
        "train_schedule": "04:30",
        "predict_schedule": "14,29,44,59",
    },
    {
        "task_type": "short",
        "train_schedule": "03:00",
        "predict_schedule": "08:00",
    },
    {
        "task_type": "medium",
        "train_schedule": "02:00",
        "predict_schedule": "08:30",
    },
]


def init_tasks():
    with db_session() as session:
        rows = session.execute(
            text("SELECT farm_code, farm_name FROM wind_farms WHERE is_active = TRUE")
        ).fetchall()

        if not rows:
            print("[WARN] wind_farms 表中没有活跃场站，跳过初始化")
            return

        created = 0
        for farm_code, farm_name in rows:
            for cfg in DEFAULT_TASK_CONFIGS:
                exists = session.query(PredictionTask).filter_by(
                    farm_code=farm_code, task_type=cfg["task_type"]
                ).first()
                if exists:
                    print(f"[SKIP] {farm_code} {cfg['task_type']} already exists")
                    continue

                task = PredictionTask(
                    farm_code=farm_code,
                    task_type=cfg["task_type"],
                    enabled=False,
                    train_schedule=cfg["train_schedule"],
                    predict_schedule=cfg["predict_schedule"],
                )
                session.add(task)
                created += 1
                print(f"[OK] Created: {farm_code} {cfg['task_type']}")

        print(f"\n初始化完成: 新建 {created} 条任务记录")


if __name__ == "__main__":
    init_tasks()
