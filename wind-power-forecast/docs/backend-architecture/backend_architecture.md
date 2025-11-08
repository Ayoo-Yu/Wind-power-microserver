# 后端架构概览（草稿 | 2025-11-08）

## 1. 总体拓扑

```
┌──────────────────────────┐        ┌─────────────────────────────┐
│      Frontend (Vue)      │        │     External Systems        │
│  SPA + Axios -> REST API │        │  • 金仓数据库 (Kingbase)    │
└─────────────┬────────────┘        │  • MinIO 对象存储           │
              │                     │  • Redis (队列/缓存)        │
              │                     │  • Legacy 脚本/任务执行环境 │
              ▼                     └──────────┬──────────────────┘
┌────────────────────────────────────────────────────────────────┐
│                        Backend Monolith                        │
│  Flask + SocketIO + Celery worker (queue: windpower-default)   │
│                                                                │
│  • REST 路由 (`backend/routes/`)                                │
│    - Auth / User / WindFarm / Report / Weather 等功能           │
│    - `/jobs/*` 入队训练/预测任务                               │
│  • Services (`backend/services/`)                               │
│    - 业务逻辑封装 (modeltrain, predict, storage, job_service)  │
│  • Pipelines & Scripts (`backend/scripts/`)                      │
│    - 传统的训练/预测/预处理脚本                                 │
│  • CELERY (`backend/task_queue.py`, `backend/tasks/*.py`)        │
│    - `jobs.train_model`, `jobs.predict`                         │
│  • Database Access (`backend/db_models`, `backend/db_session`)  │
│                                                                │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│                 backend-autopredict Service                    │
│  Flask (管理接口) + Celery (queue: autopredict) + Celery Beat  │
│                                                                │
│  • Routes / Services                                           │
│    - 任务配置、日志、触发接口 (`routes/autopredict.py` 等)     │
│    - `services.autopredict_config_service` 维护任务表          │
│  • Tasks (`tasks/autopredict.py`)                               │
│    - 子进程执行短/中/超短期训练与预测脚本                      │
│    - 周期调度：增量触发具体训练/预测任务                      │
│  • auto_scripts                                                │
│    - legacy LightGBM/XGBoost 流水线，直接操作文件系统、MinIO   │
└────────────────────────────────────────────────────────────────┘
```

## 2. 运行组件

### 2.1 Flask 单体（`backend/`）
- **App Factory**：`backend/app_factory.py` 负责加载配置、注册蓝图、初始化 SocketIO/JWT/CORS、绑定 Celery。
- **REST 路由**：
  - 预测链路：`routes/modeltrain.py`（同步流程）、`routes/predict.py`、`routes/power_compare.py`。
  - 数据管理：`routes/feature_upload.py`、`routes/operational_data_upload.py`。
  - 运维：`routes/report_management_router.py`、`routes/system_info_router.py`。
  - 认证与用户：`routes/auth.py`、`routes/user.py`。
  - 任务 API：`routes/jobs.py` 提供 `/jobs/train` 与 `/jobs/predict` REST 接口。
- **Service 层**：`services/` 目录抽象了文件存储、模型训练、任务记录、气象拉取等逻辑。
- **Celery Worker**：通过 `backend/task_queue.py` 初始化，任务位于 `backend/tasks/`。
- **数据库与配置**：
  - `backend/libs/config`（新）基于 Pydantic 管理配置。
  - `backend/database_config.py` 初始化 SQLAlchemy 引擎、MinIO 客户端。

### 2.2 自动预测服务（`backend-autopredict/`）
- **App Factory / Celery**：独立于主后端，拥有自己的 `celery_app.py`, `tasks/autopredict.py`。
- **Legacy Pipelines**：`auto_scripts/` 下按 `short/middle/supershort` 划分，运行脚本写入 MinIO 与日志文件夹。
- **调度**：Celery Beat 在 `tasks/autopredict.py::setup_periodic_tasks` 注册 cron 任务；分发任务扫描数据库配置。

### 2.3 外部依赖
- **Kingbase 数据库**：保存用户、任务、训练记录、自动预测配置等。通过 SQLAlchemy (`db_models`) 访问。
- **MinIO 对象存储**：存放上传文件、模型、评估报告、预测结果等；路径生成由 `services.storage_service` / `windpower_core.storage` 统一。
- **Redis**：既作为缓存（待整理）又作为 Celery broker/result backend。
- **Legacy 环境**：自动预测脚本需要特定 Python 环境及配置（见 `backend-autopredict/auto_scripts/scripts/*`）。

## 3. 数据流概览

### 3.1 人工训练/预测
1. 前端调用 `/upload` 接口上传数据集 -> 保存本地/MinIO。
2. `/jobs/train` 或 `/jobs/predict` 入队任务；`services.job_service` 记录 `Job`。
3. Celery Worker 消费任务，调用 `services.modeltrain_service` 或 `windpower_core.training.run_prediction`。
4. 产物（模型、预测、评估）上传 MinIO，`Job` 更新状态；前端轮询 `/jobs/{id}` 获取结果。

### 3.2 自动预测
1. 运维人员通过自动预测管理界面配置任务（场站、频率等）。
2. Celery Beat 根据默认 cron 触发分发任务，遍历 `list_all_jobs()`。
3. 对每个启用任务调用 `train_*` / `predict_*` 脚本（子进程）；脚本负责读取数据、训练、上传结果并记录日志。
4. `services.task_history_service` 记录成功/失败，用于界面显示。

### 3.3 气象拉取 / 其他任务
- 现有 APScheduler (`services/scheduler_service.py`) 控制气象数据拉取过程，但与 Celery 或自动预测未统一；后续需评估整合。

## 4. 部署视角

| 组件 | 部署方式 | 备注 |
| --- | --- | --- |
| backend Flask + Celery worker | Docker 镜像 / docker-compose | Celery worker 需与 Flask 应用共享代码与配置 |
| backend-autopredict Flask + Celery + Celery Beat | Docker 镜像 / 独立容器 | auto_scripts 目录体积大，需挂载数据卷 |
| Redis | 外部服务或 Compose | 与两个后端共享，注意隔离队列名称 |
| MinIO | 外部服务 | 需准备 bucket/policy，见 `MINIO_CONFIG` |
| Kingbase | 外部服务 | 连接信息通过环境变量注入 |

## 5. 关键问题与重构方向

1. **任务割裂**：主后端与自动预测后端各有一套任务/队列/状态管理。目标是在重构后统一成一个任务中心和任务 API。
2. **同步流程仍存在**：`routes/modeltrain.py` 等仍包含同步训练逻辑，应迁移到统一的 pipeline + Celery。
3. **配置分散**：虽然引入 `libs/config`，但自动预测服务尚未使用，需要逐步迁移。
4. **监控与告警不足**：缺少 Celery 状态监控、任务重试策略与异常告警。
5. **Legacy 脚本难以测试**：`auto_scripts` 仍通过子进程执行，需重写为模块化 pipeline 并添加测试。

## 6. 后续文档计划

- **tasks-api.md**：定义统一任务 API 契约、状态枚举、错误码。
- **pipelines/** 文档：训练、预测、自动预测 pipeline 的输入/输出规范。
- **deployment-guide.md** 更新：补充新的配置项、队列名称、服务启动命令。
- **ops/scheduler.md**：说明气象拉取与自动预测调度的管理方式。

> 本文档为重构前的结构快照，后续随着目录拆分、pipeline 重写，需要持续更新，确保团队对系统拓扑与依赖保持一致认知。


