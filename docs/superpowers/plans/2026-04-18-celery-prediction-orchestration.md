# Celery + Redis 预测任务编排 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Celery + Redis 替代 PM2 进程管理，实现预测任务的状态可观测、调度可配置、执行可追溯。

**Architecture:** Flask API 下发任务到 Redis 队列，Celery Worker 消费执行，Beat 定时调度。任务状态全部存储在 PostgreSQL 中，前端直接查 DB 获取结构化状态。保留现有 `auto_pre_train.py` 等预测脚本，由 Worker 调用。

**Tech Stack:** Python 3.10, Flask, Celery 5.x, Redis, SQLAlchemy, PostgreSQL/KingBase

---

## File Structure

```
backend-autopredict/
├── celery_app/                    # NEW - Celery 配置和任务定义
│   ├── __init__.py               # Celery app 实例 + 配置
│   ├── tasks.py                  # 4 个预测任务定义
│   └── scheduler.py             # Beat 动态调度构建
├── db_models/
│   ├── prediction_task.py        # NEW - prediction_tasks 表模型
│   └── prediction_run.py         # NEW - prediction_runs 表模型
├── routes/
│   └── autopredict.py            # MODIFY - 移除 PM2，改为 Celery + DB
├── config.py                     # MODIFY - 添加 Redis/Celery 配置
├── db_models/__init__.py         # MODIFY - 注册新模型
├── database_config.py            # MODIFY - 添加新表自动创建
└── requirements.txt              # MODIFY - 添加 celery, redis 依赖
```

---

### Task 1: 添加依赖和配置

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/requirements.txt`
- Modify: `wind-power-forecast/backend-autopredict/config.py`

- [ ] **Step 1: 添加 Celery 和 Redis 依赖**

在 `requirements.txt` 末尾添加：

```
celery>=5.3.0
redis>=5.0.0
flower>=2.0.0
```

- [ ] **Step 2: 在 config.py 中添加 Redis 和 Celery 配置**

在 `Config` 类的 `SCRIPT_PATHS` 之后添加：

```python
# Redis / Celery 配置
REDIS_HOST = _env('REDIS_HOST', 'localhost')
REDIS_PORT = _env('REDIS_PORT', '6379')
REDIS_PASSWORD = _env('REDIS_PASSWORD', '')
REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
```

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/backend-autopredict/requirements.txt wind-power-forecast/backend-autopredict/config.py
git commit -m "feat: add celery and redis dependencies and config"
```

---

### Task 2: 创建数据库模型

**Files:**
- Create: `wind-power-forecast/backend-autopredict/db_models/prediction_task.py`
- Create: `wind-power-forecast/backend-autopredict/db_models/prediction_run.py`
- Modify: `wind-power-forecast/backend-autopredict/db_models/__init__.py`

- [ ] **Step 1: 创建 PredictionTask 模型**

创建 `db_models/prediction_task.py`：

```python
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, UniqueConstraint
from datetime import datetime
from .base import Base


class PredictionTask(Base):
    __tablename__ = "prediction_tasks"
    __table_args__ = (
        UniqueConstraint("farm_code", "task_type", name="uq_prediction_tasks_farm_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    farm_code = Column(String(50), nullable=False, index=True)
    task_type = Column(String(20), nullable=False)  # supershort / short / medium
    enabled = Column(Boolean, default=False)

    train_schedule = Column(String(20))       # "03:00"
    predict_schedule = Column(String(100))     # "*/15 * * * *" or "08:00"

    last_train_at = Column(DateTime)
    last_predict_at = Column(DateTime)
    last_train_status = Column(String(20))     # success / failed / running
    last_predict_status = Column(String(20))
    last_error = Column(Text)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

- [ ] **Step 2: 创建 PredictionRun 模型**

创建 `db_models/prediction_run.py`：

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from .base import Base


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("prediction_tasks.id"), index=True)
    celery_task_id = Column(String(100))
    action = Column(String(20))        # train / predict
    status = Column(String(20))        # pending / running / success / failed
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration_sec = Column(Integer)
    error_message = Column(Text)
    result_summary = Column(JSONB)
    created_at = Column(DateTime, default=datetime.now)
```

- [ ] **Step 3: 注册新模型到 `__init__.py`**

在 `db_models/__init__.py` 中添加导入和导出：

```python
# 在 from .task import TaskHistory 之后添加：
from .prediction_task import PredictionTask
from .prediction_run import PredictionRun

# 在 __all__ 列表中添加：
'PredictionTask', 'PredictionRun'
```

- [ ] **Step 4: Commit**

```bash
git add wind-power-forecast/backend-autopredict/db_models/prediction_task.py wind-power-forecast/backend-autopredict/db_models/prediction_run.py wind-power-forecast/backend-autopredict/db_models/__init__.py
git commit -m "feat: add PredictionTask and PredictionRun database models"
```

---

### Task 3: 创建 Celery App 和任务定义

**Files:**
- Create: `wind-power-forecast/backend-autopredict/celery_app/__init__.py`
- Create: `wind-power-forecast/backend-autopredict/celery_app/tasks.py`
- Create: `wind-power-forecast/backend-autopredict/celery_app/scheduler.py`

- [ ] **Step 1: 创建 Celery App 实例**

创建 `celery_app/__init__.py`：

```python
from celery import Celery
import os

celery_app = Celery("wind_power_predict")

celery_app.conf.update(
    broker_url=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
)

celery_app.autodiscover_tasks(["celery_app"])
```

- [ ] **Step 2: 创建预测任务函数**

创建 `celery_app/tasks.py`：

```python
import os
import sys
import subprocess
import logging
from datetime import datetime
from celery import group, chain
from . import celery_app
from db_session import db_session
from db_models import PredictionTask, PredictionRun

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT_PATHS = {
    "short": os.path.join(BASE_DIR, "auto_scripts", "scripts", "short", "auto_pre_train.py"),
    "medium": os.path.join(BASE_DIR, "auto_scripts", "scripts", "middle", "auto_pre_train.py"),
    "supershort_predict": os.path.join(BASE_DIR, "auto_scripts", "scripts", "supershort", "predict_supershort.py"),
    "supershort_train": os.path.join(BASE_DIR, "auto_scripts", "scripts", "supershort", "train_supershort.py"),
    "merge": os.path.join(BASE_DIR, "auto_scripts", "scripts", "middle", "run_auto_predict.py"),
}

PYTHON_BIN = sys.executable


def _create_run_record(task_id, action, celery_task_id):
    """创建 prediction_runs 记录"""
    with db_session() as session:
        run = PredictionRun(
            task_id=task_id,
            celery_task_id=celery_task_id,
            action=action,
            status="running",
            started_at=datetime.now(),
        )
        session.add(run)
        session.flush()
        return run.id


def _finish_run_record(run_id, status, error_message=None, result_summary=None):
    """更新 prediction_runs 记录"""
    with db_session() as session:
        run = session.query(PredictionRun).get(run_id)
        if run:
            run.status = status
            run.finished_at = datetime.now()
            run.duration_sec = int((run.finished_at - run.started_at).total_seconds())
            run.error_message = error_message
            if result_summary:
                run.result_summary = result_summary


def _update_task_status(task_id, action, status, error_message=None):
    """更新 prediction_tasks 的 last_*_status"""
    with db_session() as session:
        task = session.query(PredictionTask).get(task_id)
        if not task:
            return
        now = datetime.now()
        if action == "train":
            task.last_train_status = status
            task.last_train_at = now
        else:
            task.last_predict_status = status
            task.last_predict_at = now
        if error_message:
            task.last_error = error_message
        task.updated_at = now


def _get_task_id(farm_code, task_type):
    """根据 farm_code 和 task_type 获取 prediction_tasks.id"""
    with db_session() as session:
        task = session.query(PredictionTask).filter_by(
            farm_code=farm_code, task_type=task_type
        ).first()
        return task.id if task else None


@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800)
def train_model(self, farm_code, task_type):
    """执行训练"""
    task_id = _get_task_id(farm_code, task_type)
    run_id = _create_run_record(task_id, "train", self.request.id) if task_id else None
    script = SCRIPT_PATHS.get(task_type)
    if not script or not os.path.exists(script):
        msg = f"训练脚本不存在: {script}"
        if run_id:
            _finish_run_record(run_id, "failed", msg)
        if task_id:
            _update_task_status(task_id, "train", "failed", msg)
        return {"status": "failed", "error": msg}

    try:
        _update_task_status(task_id, "train", "running") if task_id else None
        env = os.environ.copy()
        env["FARM_CODE"] = farm_code
        result = subprocess.run(
            [PYTHON_BIN, script, "--mode", "train", "--farm_code", farm_code],
            capture_output=True, text=True, timeout=1700, env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-2000:] if result.stderr else "训练进程非零退出")
        if run_id:
            _finish_run_record(run_id, "success")
        if task_id:
            _update_task_status(task_id, "train", "success")
        return {"status": "success", "farm_code": farm_code, "task_type": task_type}

    except Exception as exc:
        if run_id:
            _finish_run_record(run_id, "failed", str(exc))
        if task_id:
            _update_task_status(task_id, "train", "failed", str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=600)
def run_prediction(self, farm_code, task_type):
    """执行预测"""
    task_id = _get_task_id(farm_code, task_type)
    run_id = _create_run_record(task_id, "predict", self.request.id) if task_id else None
    script = SCRIPT_PATHS.get(task_type)
    if not script or not os.path.exists(script):
        msg = f"预测脚本不存在: {script}"
        if run_id:
            _finish_run_record(run_id, "failed", msg)
        if task_id:
            _update_task_status(task_id, "predict", "failed", msg)
        return {"status": "failed", "error": msg}

    try:
        _update_task_status(task_id, "predict", "running") if task_id else None
        env = os.environ.copy()
        env["FARM_CODE"] = farm_code
        result = subprocess.run(
            [PYTHON_BIN, script, "--mode", "predict", "--farm_code", farm_code],
            capture_output=True, text=True, timeout=550, env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-2000:] if result.stderr else "预测进程非零退出")
        if run_id:
            _finish_run_record(run_id, "success")
        if task_id:
            _update_task_status(task_id, "predict", "success")
        return {"status": "success", "farm_code": farm_code, "task_type": task_type}

    except Exception as exc:
        if run_id:
            _finish_run_record(run_id, "failed", str(exc))
        if task_id:
            _update_task_status(task_id, "predict", "failed", str(exc))
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, max_retries=1, soft_time_limit=300)
def run_supershort_predict(self, farm_code):
    """超短期预测"""
    task_id = _get_task_id(farm_code, "supershort")
    run_id = _create_run_record(task_id, "predict", self.request.id) if task_id else None
    script = SCRIPT_PATHS.get("supershort_predict")
    if not script or not os.path.exists(script):
        msg = f"超短期预测脚本不存在: {script}"
        if run_id:
            _finish_run_record(run_id, "failed", msg)
        if task_id:
            _update_task_status(task_id, "predict", "failed", msg)
        return {"status": "failed", "error": msg}

    try:
        _update_task_status(task_id, "predict", "running") if task_id else None
        env = os.environ.copy()
        env["FARM_CODE"] = farm_code
        result = subprocess.run(
            [PYTHON_BIN, script],
            capture_output=True, text=True, timeout=280, env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-2000:] if result.stderr else "超短期预测进程非零退出")
        if run_id:
            _finish_run_record(run_id, "success")
        if task_id:
            _update_task_status(task_id, "predict", "success")
        return {"status": "success", "farm_code": farm_code}

    except Exception as exc:
        if run_id:
            _finish_run_record(run_id, "failed", str(exc))
        if task_id:
            _update_task_status(task_id, "predict", "failed", str(exc))
        raise self.retry(exc=exc, countdown=15)


@celery_app.task
def merge_predictions(farm_code, date_str):
    """合并短期+中期预测"""
    task_id = _get_task_id(farm_code, "medium")
    run_id = _create_run_record(task_id, "merge", None) if task_id else None
    try:
        env = os.environ.copy()
        env["FARM_CODE"] = farm_code
        env["TARGET_DATE"] = date_str
        # 调用现有的合并逻辑（scheduler_middle.py 中的合并步骤）
        # 这里直接导入并调用，避免 subprocess
        script_dir = os.path.join(BASE_DIR, "auto_scripts", "scripts", "middle")
        merge_script = os.path.join(script_dir, "run_auto_predict.py")
        if os.path.exists(merge_script):
            subprocess.run(
                [PYTHON_BIN, merge_script, "--farm_code", farm_code, "--date", date_str],
                capture_output=True, text=True, timeout=300, env=env,
            )
        if run_id:
            _finish_run_record(run_id, "success")
        return {"status": "success", "farm_code": farm_code, "date": date_str}
    except Exception as exc:
        if run_id:
            _finish_run_record(run_id, "failed", str(exc))
        return {"status": "failed", "error": str(exc)}
```

- [ ] **Step 3: 创建 Beat 动态调度器**

创建 `celery_app/scheduler.py`：

```python
"""Celery Beat 动态调度配置生成器。

从 prediction_tasks 表读取启用的任务，生成 Celery Beat 调度计划。
"""
from celery.schedules import crontab
from db_session import db_session
from db_models import PredictionTask


# 默认调度时间（当数据库中未配置时使用）
DEFAULT_SCHEDULES = {
    "short": {"train": "03:00", "predict": "08:00"},
    "medium": {"train": "02:00", "predict": "08:30"},
    "supershort": {"predict_cron": "14,29,44,59"},
}

PREDICT_SCHEDULE_MAP = {
    "short": "08:00",
    "medium": "08:30",
}


def build_beat_schedule():
    """从数据库构建 Beat 调度计划。每次 Beat tick 时调用。"""
    schedule = {}
    with db_session() as session:
        tasks = session.query(PredictionTask).filter_by(enabled=True).all()
        for t in tasks:
            fc = t.farm_code
            tt = t.task_type

            if tt == "supershort":
                # 超短期：每15分钟执行一次预测
                schedule[f"{fc}_supershort_predict"] = {
                    "task": "celery_app.tasks.run_supershort_predict",
                    "args": (fc,),
                    "schedule": crontab(minute="14,29,44,59"),
                }
                # 超短期：每日训练一次
                train_time = t.train_schedule or DEFAULT_SCHEDULES["supershort"].get("train", "04:30")
                h, m = train_time.split(":")
                schedule[f"{fc}_supershort_train"] = {
                    "task": "celery_app.tasks.train_model",
                    "args": (fc, "supershort"),
                    "schedule": crontab(minute=int(m), hour=int(h)),
                }
            else:
                # 短期/中期：每日训练
                train_time = t.train_schedule or DEFAULT_SCHEDULES[tt]["train"]
                h, m = train_time.split(":")
                schedule[f"{fc}_{tt}_train"] = {
                    "task": "celery_app.tasks.train_model",
                    "args": (fc, tt),
                    "schedule": crontab(minute=int(m), hour=int(h)),
                }
                # 短期/中期：每日预测
                predict_time = t.predict_schedule or PREDICT_SCHEDULE_MAP.get(tt, "08:00")
                ph, pm = predict_time.split(":")
                schedule[f"{fc}_{tt}_predict"] = {
                    "task": "celery_app.tasks.run_prediction",
                    "args": (fc, tt),
                    "schedule": crontab(minute=int(pm), hour=int(ph)),
                }

    return schedule
```

- [ ] **Step 4: Commit**

```bash
git add wind-power-forecast/backend-autopredict/celery_app/
git commit -m "feat: add Celery app, prediction tasks, and beat scheduler"
```

---

### Task 4: 创建数据库初始化脚本

**Files:**
- Create: `wind-power-forecast/backend-autopredict/scripts/init_prediction_tasks.py`

- [ ] **Step 1: 创建初始化脚本**

创建 `scripts/init_prediction_tasks.py`：

```python
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
        # 获取所有活跃场站
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
```

- [ ] **Step 2: Commit**

```bash
git add wind-power-forecast/backend-autopredict/scripts/init_prediction_tasks.py
git commit -m "feat: add prediction tasks initialization script"
```

---

### Task 5: 改造 autopredict 路由（核心替换）

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/routes/autopredict.py`

这是最大的改动。需要：
1. 移除所有 PM2 相关代码（`safe_pm2_command`、`get_pm2_processes`、`is_process_online` 等）
2. `status_all` 改为查 `prediction_tasks` 表
3. `start` 改为 `UPDATE enabled=TRUE`
4. `stop` 改为 `UPDATE enabled=FALSE`
5. `control_all` 改为批量更新
6. 新增 `/trigger`、`/runs`、`/schedule_config` 端点
7. 删除 PM2 专有端点

- [ ] **Step 1: 在 autopredict.py 顶部替换 PM2 导入为 DB 查询**

在 `autopredict.py` 的导入区域，移除对 `prediction_status` 全局字典和 PM2 函数的依赖。添加：

```python
from db_session import db_session
from db_models import PredictionTask, PredictionRun
from sqlalchemy import text, desc
from celery_app.tasks import train_model, run_prediction, run_supershort_predict
from datetime import datetime
```

注释掉或移除 `prediction_status` 全局字典、`status_lock`、`BackgroundScheduler` 等定时更新 PM2 状态的代码。

- [ ] **Step 2: 重写 `get_status_all` 端点**

替换现有的 `status_all` 函数体为：

```python
@autopredict_bp.route('/status_all', methods=['GET'])
@autopredict_bp.route('/v1/autopredict/status_all', methods=['GET'])
def get_status_all():
    try:
        with db_session() as session:
            tasks = session.query(PredictionTask).all()

            # 按 farm_code 分组
            farm_map = {}
            for t in tasks:
                if t.farm_code not in farm_map:
                    farm_map[t.farm_code] = {
                        "farm_code": t.farm_code,
                        "farm_name": _get_farm_name(session, t.farm_code),
                        "status": {},
                    }
                farm_map[t.farm_code]["status"][t.task_type] = {
                    "enabled": t.enabled,
                    "last_train_at": t.last_train_at.isoformat() if t.last_train_at else None,
                    "last_predict_at": t.last_predict_at.isoformat() if t.last_predict_at else None,
                    "last_train_status": t.last_train_status,
                    "last_predict_status": t.last_predict_status,
                    "last_error": t.last_error,
                }

            items = list(farm_map.values())
            return api_success(data={"items": items, "count": len(items)})

    except Exception as e:
        return api_error(f"获取多场站状态失败: {str(e)}")


def _get_farm_name(session, farm_code):
    """查询场站名称"""
    row = session.execute(
        text("SELECT farm_name FROM wind_farms WHERE farm_code = :code"),
        {"code": farm_code},
    ).fetchone()
    return row[0] if row else farm_code
```

- [ ] **Step 3: 重写 `start_prediction` 端点**

```python
@autopredict_bp.route('/start', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/start', methods=['POST'])
def start_prediction():
    data = request.get_json(silent=True) or {}
    prediction_type = data.get('type')
    farm_code = data.get('farm_code', 'DEFAULT_FARM')

    if prediction_type not in ('short', 'medium', 'supershort'):
        return api_error('无效的预测类型', code=1001, status_code=400)

    try:
        with db_session() as session:
            task = session.query(PredictionTask).filter_by(
                farm_code=farm_code, task_type=prediction_type
            ).first()
            if not task:
                return api_error(f'未找到任务配置: {farm_code} {prediction_type}', code=1004, status_code=404)
            task.enabled = True
            task.updated_at = datetime.now()

        return api_success(
            data={"farm_code": farm_code, "type": prediction_type, "enabled": True},
            message=f'{prediction_type} 预测任务已启用 (场站: {farm_code})',
        )
    except Exception as e:
        return api_error(f"启动失败: {str(e)}")
```

- [ ] **Step 4: 重写 `stop_prediction` 端点**

```python
@autopredict_bp.route('/stop', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/stop', methods=['POST'])
def stop_prediction():
    data = request.get_json(silent=True) or {}
    prediction_type = data.get('type')
    farm_code = data.get('farm_code', 'DEFAULT_FARM')

    if prediction_type not in ('short', 'medium', 'supershort'):
        return api_error('无效的预测类型', code=1001, status_code=400)

    try:
        with db_session() as session:
            task = session.query(PredictionTask).filter_by(
                farm_code=farm_code, task_type=prediction_type
            ).first()
            if not task:
                return api_error(f'未找到任务配置: {farm_code} {prediction_type}', code=1004, status_code=404)
            task.enabled = False
            task.updated_at = datetime.now()

        return api_success(
            data={"farm_code": farm_code, "type": prediction_type, "enabled": False},
            message=f'{prediction_type} 预测任务已停止 (场站: {farm_code})',
        )
    except Exception as e:
        return api_error(f"停止失败: {str(e)}")
```

- [ ] **Step 5: 重写 `control_all_prediction` 端点**

```python
@autopredict_bp.route('/control_all', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/control_all', methods=['POST'])
def control_all_prediction():
    data = request.get_json(silent=True) or {}
    action = data.get('action')  # start | stop
    prediction_type = data.get('type')
    farm_codes = data.get('farm_codes')

    if action not in ('start', 'stop'):
        return api_error('无效的操作类型，仅支持 start/stop', code=1001, status_code=400)
    if prediction_type not in ('short', 'medium', 'supershort'):
        return api_error('无效的预测类型', code=1001, status_code=400)

    try:
        with db_session() as session:
            query = session.query(PredictionTask).filter_by(task_type=prediction_type)
            if farm_codes and isinstance(farm_codes, list):
                query = query.filter(PredictionTask.farm_code.in_(farm_codes))

            tasks = query.all()
            enabled = action == 'start'
            for t in tasks:
                t.enabled = enabled
                t.updated_at = datetime.now()

        items = [{"farm_code": t.farm_code, "type": prediction_type, "success": True,
                   "message": f"{prediction_type} {'已启用' if enabled else '已停止'} (场站: {t.farm_code})"}
                  for t in tasks]
        return api_success(
            data={"items": items, "summary": {"total": len(tasks), "success": len(tasks), "failed": 0}},
            message=f"批量{action}完成: 成功 {len(tasks)}/{len(tasks)}",
        )
    except Exception as e:
        return api_error(f"批量操作失败: {str(e)}")
```

- [ ] **Step 6: 新增 `trigger`、`runs`、`schedule_config` 端点**

在文件末尾添加：

```python
@autopredict_bp.route('/trigger', methods=['POST'])
@autopredict_bp.route('/v1/autopredict/trigger', methods=['POST'])
def trigger_prediction():
    """手动触发一次训练或预测"""
    data = request.get_json(silent=True) or {}
    farm_code = data.get('farm_code', 'DEFAULT_FARM')
    action = data.get('action', 'predict')  # train / predict
    prediction_type = data.get('type', 'supershort')

    if prediction_type == 'supershort':
        result = run_supershort_predict.delay(farm_code)
    elif action == 'train':
        result = train_model.delay(farm_code, prediction_type)
    else:
        result = run_prediction.delay(farm_code, prediction_type)

    return api_success(
        data={"celery_task_id": result.id, "farm_code": farm_code, "type": prediction_type, "action": action},
        message=f"已触发 {action} 任务 ({prediction_type}, 场站: {farm_code})",
    )


@autopredict_bp.route('/runs', methods=['GET'])
@autopredict_bp.route('/v1/autopredict/runs', methods=['GET'])
def get_runs():
    """查询执行历史"""
    farm_code = request.args.get('farm_code')
    task_type = request.args.get('type')
    limit = min(int(request.args.get('limit', 50)), 200)

    try:
        with db_session() as session:
            query = session.query(PredictionRun).join(PredictionTask)
            if farm_code:
                query = query.filter(PredictionTask.farm_code == farm_code)
            if task_type:
                query = query.filter(PredictionTask.task_type == task_type)
            runs = query.order_by(desc(PredictionRun.created_at)).limit(limit).all()

            items = [{
                "id": r.id,
                "farm_code": r.task.farm_code if r.task else None,
                "task_type": r.task.task_type if r.task else None,
                "action": r.action,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "duration_sec": r.duration_sec,
                "error_message": r.error_message,
            } for r in runs]

            return api_success(data={"items": items, "count": len(items)})
    except Exception as e:
        return api_error(f"查询执行历史失败: {str(e)}")


@autopredict_bp.route('/schedule_config', methods=['PUT'])
@autopredict_bp.route('/v1/autopredict/schedule_config', methods=['PUT'])
def update_schedule_config():
    """修改调度时间"""
    data = request.get_json(silent=True) or {}
    farm_code = data.get('farm_code')
    task_type = data.get('type')
    train_schedule = data.get('train_schedule')
    predict_schedule = data.get('predict_schedule')

    if not farm_code or not task_type:
        return api_error('farm_code 和 type 为必填项', code=1001, status_code=400)

    try:
        with db_session() as session:
            task = session.query(PredictionTask).filter_by(
                farm_code=farm_code, task_type=task_type
            ).first()
            if not task:
                return api_error(f'未找到任务: {farm_code} {task_type}', code=1004, status_code=404)
            if train_schedule:
                task.train_schedule = train_schedule
            if predict_schedule:
                task.predict_schedule = predict_schedule
            task.updated_at = datetime.now()

        return api_success(
            data={"farm_code": farm_code, "type": task_type},
            message="调度配置已更新",
        )
    except Exception as e:
        return api_error(f"更新失败: {str(e)}")
```

- [ ] **Step 7: 注释掉 PM2 专有端点**

将以下端点函数体替换为简单的 deprecated 响应：
- `delete_prediction` → `return api_error('此端点已弃用，任务管理已迁移到 Celery', code=1001, status_code=410)`
- `schedule_restart` → 同上
- `save_pm2_config` → 同上
- `clear_pm2_save` → 同上
- `resurrect` → 同上
- `get_script_info` → 同上

- [ ] **Step 8: Commit**

```bash
git add wind-power-forecast/backend-autopredict/routes/autopredict.py
git commit -m "feat: replace PM2 with Celery + DB in autopredict routes"
```

---

### Task 6: 更新 docker-compose 配置

**Files:**
- Modify: `wind-power-forecast/frontend-backend-compose.yaml`

- [ ] **Step 1: 在 backend-autopredict 服务中添加 Redis 依赖和环境变量**

在 `backend-autopredict` 服务的 `environment` 部分添加：

```yaml
      - REDIS_HOST=redis
      - REDIS_PORT=6379
```

在 `depends_on` 部分添加：

```yaml
      redis:
        condition: service_started
```

- [ ] **Step 2: 添加 Redis 服务**

在 `services:` 下添加 Redis 服务（放在 kingbase 之后）：

```yaml
  redis:
    image: redis:7-alpine
    container_name: wind-power-redis
    ports:
      - "6379:6379"
    restart: unless-stopped
    networks:
      - wind-power-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
```

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/frontend-backend-compose.yaml
git commit -m "feat: add Redis service and Celery config to docker-compose"
```

---

### Task 7: 更新前端 AutoPredict 组件

**Files:**
- Modify: `wind-power-forecast/frontend/src/components/AutoPredict.vue`

- [ ] **Step 1: 更新 `normalizeBizState` 函数以处理新的结构化状态**

将 `normalizeBizState` 函数替换为：

```javascript
const normalizeBizState = (statusObj) => {
  if (!statusObj) return { level: 'disabled', text: '未配置', reason: '未配置' }
  if (typeof statusObj === 'boolean') {
    return statusObj
      ? { level: 'ready', text: '已启用', reason: '' }
      : { level: 'disabled', text: '未启用', reason: '' }
  }
  // 新格式: { enabled, last_predict_status, last_train_status, ... }
  if (typeof statusObj === 'object') {
    if (!statusObj.enabled) return { level: 'disabled', text: '未启用', reason: '' }

    const lastStatus = statusObj.last_predict_status || statusObj.last_train_status
    if (lastStatus === 'running') return { level: 'running', text: '执行中...', reason: '' }
    if (lastStatus === 'failed') return { level: 'failed', text: '失败', reason: statusObj.last_error || '' }
    if (lastStatus === 'success') {
      const updatedAt = statusObj.last_predict_at || statusObj.last_train_at
      const timeStr = updatedAt ? updatedAt.slice(11, 16) : ''
      return { level: 'ready', text: timeStr ? `${timeStr} 已更新` : '已启用', reason: '' }
    }
    return { level: 'ready', text: '已启用', reason: '' }
  }
  return { level: 'unknown', text: '状态未知', reason: '' }
}
```

- [ ] **Step 2: 更新 `fleetMatrixRows` 计算属性**

替换 `fleetMatrixRows` 为：

```javascript
const fleetMatrixRows = computed(() => {
  const rows = Array.isArray(fleetStatus.value) ? fleetStatus.value : []
  const filterCodes = Array.isArray(selectedFleetFarmCodes.value) ? selectedFleetFarmCodes.value : []
  const applyFilter = filterCodes.length > 0

  return rows
    .filter((farm) => !applyFilter || filterCodes.includes(farm.farm_code))
    .map((farm) => {
      const status = farm.status || {}

      const nwpState = normalizeBizState(
        status.supershort?.enabled ? status.supershort : null
      )

      const supershortState = nwpState.level === 'failed'
        ? { level: 'failed', text: 'NWP缺失', reason: 'NGP缺失' }
        : normalizeBizState(status.supershort)

      const shortState = normalizeBizState(status.short)
      const mediumState = normalizeBizState(status.medium)

      return {
        ...farm,
        nwpState,
        supershortState,
        shortState,
        mediumState,
      }
    })
})
```

- [ ] **Step 3: Commit**

```bash
git add wind-power-forecast/frontend/src/components/AutoPredict.vue
git commit -m "feat: update AutoPredict to use structured status from Celery backend"
```

---

### Task 8: 数据库迁移和初始化

**Files:**
- Modify: `wind-power-forecast/backend-autopredict/database_config.py`

- [ ] **Step 1: 在 `check_migrations` 中添加新表创建**

在 `check_migrations` 函数的 `Base.metadata.create_all(engine)` 调用之前，确认新模型已被导入（`db_models/__init__.py` 中已添加）。现有的 `create_all` 会自动创建 `prediction_tasks` 和 `prediction_runs` 表。

无需额外代码，但需验证：

```bash
cd wind-power-forecast/backend-autopredict
python -c "from db_models import PredictionTask, PredictionRun; print('Models imported OK')"
```

- [ ] **Step 2: 运行初始化脚本创建默认任务**

```bash
cd wind-power-forecast/backend-autopredict
python scripts/init_prediction_tasks.py
```

预期输出：
```
[OK] Created: BNJ supershort
[OK] Created: BNJ short
[OK] Created: BNJ medium
[OK] Created: CF supershort
... (共 15 条)
初始化完成: 新建 15 条任务记录
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: database migration and task initialization"
```

---

### Task 9: 验证和冒烟测试

- [ ] **Step 1: 安装新依赖**

```bash
cd wind-power-forecast/backend-autopredict
pip install celery redis flower
```

- [ ] **Step 2: 启动 Celery Worker（本地测试）**

```bash
cd wind-power-forecast/backend-autopredict
celery -A celery_app worker -c 2 --loglevel=info
```

预期：Worker 启动，显示注册了 4 个任务（train_model, run_prediction, run_supershort_predict, merge_predictions）。

- [ ] **Step 3: 测试 status_all 端点**

```bash
curl -s http://localhost:5001/api/v1/autopredict/status_all | python -m json.tool
```

预期：返回 5 个场站，每个场站有 supershort/short/medium 三个结构化状态对象（`enabled: false`）。

- [ ] **Step 4: 测试 trigger 端点**

```bash
curl -s -X POST http://localhost:5001/api/v1/autopredict/trigger \
  -H "Content-Type: application/json" \
  -d '{"farm_code":"BNJ","type":"short","action":"train"}' | python -m json.tool
```

预期：返回 `celery_task_id`，Worker 日志显示接收到任务。

- [ ] **Step 5: 测试 start/stop 端点**

```bash
curl -s -X POST http://localhost:5001/api/v1/autopredict/start \
  -H "Content-Type: application/json" \
  -d '{"farm_code":"BNJ","type":"short"}' | python -m json.tool

curl -s http://localhost:5001/api/v1/autopredict/status_all | python -m json.tool
```

预期：BNJ 的 short 状态显示 `enabled: true`。

- [ ] **Step 6: 测试 runs 查询**

```bash
curl -s "http://localhost:5001/api/v1/autopredict/runs?farm_code=BNJ&type=short&limit=5" | python -m json.tool
```

预期：返回最近的执行记录，包含 status、duration_sec 等字段。

- [ ] **Step 7: 启动 Flower 监控（可选）**

```bash
cd wind-power-forecast/backend-autopredict
celery -A celery_app flower --port=5555
```

浏览器访问 `http://localhost:5555` 查看 Flower 监控面板。
