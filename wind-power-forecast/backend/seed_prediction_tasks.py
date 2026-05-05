"""Seed prediction_tasks for all 5 farms x short/medium.

Run:  cd wind-power-forecast/backend && python seed_prediction_tasks.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from db_session import db_session
from db_models.prediction_task import PredictionTask
from farm_registry.farms_config import get_all_farms

SCHEDULES = {
    "short": {"train": "03:00", "predict": "08:50"},
    "medium": {"train": "02:00", "predict": "08:50"},
    "supershort": {"train": "04:30"},
}


def seed():
    farms = get_all_farms()
    created = 0
    skipped = 0

    with db_session() as session:
        for farm in farms:
            fc = farm["farm_code"]
            for task_type, sched in SCHEDULES.items():
                existing = (
                    session.query(PredictionTask)
                    .filter_by(farm_code=fc, task_type=task_type)
                    .first()
                )
                if existing:
                    print(f"  skip {fc}/{task_type} (id={existing.id})")
                    skipped += 1
                    continue

                task = PredictionTask(
                    farm_code=fc,
                    task_type=task_type,
                    enabled=True,
                    train_schedule=sched["train"],
                    predict_schedule=sched.get("predict", ""),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                session.add(task)
                created += 1
                print(f"  + {fc}/{task_type} train={sched['train']} predict={sched.get('predict', 'cron')}")
        session.commit()

    print(f"\nDone: {created} created, {skipped} skipped (total farms={len(farms)})")


if __name__ == "__main__":
    seed()
