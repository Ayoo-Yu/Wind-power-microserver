# Celery 任务清单（2025-11-08）

## 总览

| 队列/服务 | Broker | Result Backend | 任务来源 | 说明 |
| --- | --- | --- | --- | --- |
| `windpower_backend`（主后端） | `Config.REDIS_URL` | `Config.CELERY_RESULT_BACKEND`（默认与 Redis 相同） | Flask 单体应用，经 `backend/task_queue.py` 初始化 | 处理人工触发的模型训练/预测任务，任务 ID 由 `services/job_service` 管理 |
| `autopredict`（自动预测后端） | `Config.REDIS_URL` | `Config.CELERY_RESULT_BACKEND` | 独立 Flask + Celery 服务，经 `backend-autopredict/celery_app.py` 初始化 | 负责超短期/短期/中期训练与预测脚本的调度与执行，内置周期调度 |

> 目前两个服务共用同一 Redis，但任务命名空间（queue/exchange）不同。尚无统一的任务 registry，前端只能分别调用。

## 主后端（`backend/`）任务

| 任务名 | 定义位置 | 队列（默认） | 触发入口 | 说明 / 产物 |
| --- | --- | --- | --- | --- |
| `jobs.train_model` | `backend/tasks/training_tasks.py` | `Config.CELERY_TASK_DEFAULT_QUEUE`（默认 `windpower-default`） | `POST /jobs/train` (`backend/routes/jobs.py`) | 根据上传的数据集运行 `services.modeltrain_service.run_modeltrain`。产出训练预测结果/模型/scaler，写入 MinIO，并更新 `Job` 状态。依赖 DB（`SessionLocal`）和 MinIO。 |
| `jobs.predict` | `backend/tasks/prediction_tasks.py` | 同上 | `POST /jobs/predict` (`backend/routes/jobs.py`) | 使用已上传的 CSV/模型/scaler 执行 `windpower_core.training.run_prediction`，生成预测文件并上传 MinIO。更新 `Job` 状态。 |

**关联组件**
- `task_queue.celery_app`：注册任务并在 `init_celery(app)` 时绑定 Flask 上下文。
- `services.job_service`：创建/更新 `Job` 表，提供任务状态查询。
- `routes/jobs.py`：暴露 REST API，负责参数校验、任务入队。

**未覆盖的任务**
- 主后端暂无其他 Celery 任务；长耗时流程（如 `routes/modeltrain.py` 同步训练）仍需迁移至队列。

## 自动预测后端（`backend-autopredict/`）任务

### 脚本执行任务

| 任务名 | 定义位置 | 队列 | 触发方式 | 说明 |
| --- | --- | --- | --- | --- |
| `autopredict.short.train` | `tasks/autopredict.py::train_short` | `autopredict` | 调度任务或手动调用 | 调用 `auto_scripts/scripts/short/auto_pre_train.py`，支持 `mode=train/predict`。 |
| `autopredict.short.predict` | `tasks/autopredict.py::predict_short` | 同上 | 调度任务或手动调用 | 执行短期预测脚本。 |
| `autopredict.middle.train` | `tasks/autopredict.py::train_middle` | 同上 | 调度任务或手动调用 | 调用 `middle/auto_pre_train.py`。 |
| `autopredict.middle.predict` | `tasks/autopredict.py::predict_middle` | 同上 | 调度任务或手动调用 | 中期预测脚本执行。 |
| `autopredict.supershort.train` | `tasks/autopredict.py::train_supershort` | 同上 | 调度任务或手动调用 | 调用 `supershort/train_supershort.py`。 |
| `autopredict.supershort.predict` | `tasks/autopredict.py::predict_supershort` | 同上 | 调度任务或手动调用 | 调用 `supershort/predict_supershort.py`。 |

> 以上任务通过 `_execute_script` 在子进程运行 legacy 脚本，并通过 `services.task_history_service` 记录执行结果。

### 调度分发任务

| 任务名 | 定义位置 | 作用 | 触发方式 |
| --- | --- | --- | --- |
| `autopredict.schedule.dispatch.short.train` | `tasks/autopredict.py::enqueue_short_training` | 遍历配置表 `list_all_jobs()`，为启用的短期任务入队 `train_short` | 由 `setup_periodic_tasks` 注册的周期任务 |
| `autopredict.schedule.dispatch.short.predict` | 同上 | 入队短期预测 | 同上 |
| `autopredict.schedule.dispatch.medium.train` | 同上 | 入队中期训练 | 同上 |
| `autopredict.schedule.dispatch.medium.predict` | 同上 | 入队中期预测 | 同上 |
| `autopredict.schedule.dispatch.supershort.train` | 同上 | 入队超短期训练 | 同上 |
| `autopredict.schedule.dispatch.supershort.predict` | 同上 | 入队超短期预测 | 同上 |

**周期调度**
- `@celery_app.on_after_finalize.connect` 注册了 6 个 `add_periodic_task`，默认 Cron：
  - 短期训练：每日 03:00
  - 短期预测：每日 08:00
  - 中期训练：每日 04:00
  - 中期预测：每日 09:00
  - 超短期训练：每日 04:30
  - 超短期预测：每 15 分钟
- 调度器遍历 `services.autopredict_config_service.list_all_jobs()` 返回的任务配置，筛选启用状态再入队具体执行任务。

## 发现的问题 / 待办

1. **任务分散**：主后端与自动预测后端各自维护 Celery 实例，任务状态管理方式不同，需要后续统一（目标：`/tasks` 接口涵盖全部任务）。
2. **队列配置透明度低**：主后端的默认队列名取自环境变量，部署中缺少说明；应在文档或配置中明确。
3. **监控缺失**：任务执行日志仅写入数据库或 MinIO，缺乏统一的任务事件流/告警。
4. **Legacy 脚本耦合**：自动预测任务仍依赖 `auto_scripts` 子进程运行，难以追踪进度与输出，需重构为 Python pipeline。
5. **缺少测试**：当前单元测试仅覆盖配置；后续需要为任务入队、调度逻辑、任务执行成功/失败分支补齐测试。

## 下一步建议

- 统一任务注册与查询：设计集中式任务 API/服务（参考 `services.job_service`），包含自动预测任务。
- 梳理每个任务的输入/输出契约，为 pipeline 重构打基础。
- 引入任务监控与告警（Celery Flower、Prometheus、自定义日志）并纳入架构文档。
- 随着 pipeline 改造，逐步替换子进程脚本为可测试的 Python 模块，并补充单元/集成测试。


