# 统一任务中心与 Pipeline 重构方案（草稿 | 2025-11-08）

## 1. 目标

- **统一任务管理**：无论是人工训练/预测还是自动预测调度，都通过一套任务模型与 API 管理，方便前端任务中心展示、状态查询、告警。
- **消除同步流程**：将仍在路由中串行执行的大型流程（如 `routes/modeltrain.py`）逐步迁移到 Celery 队列，提升可用性与扩展能力。
- **为 Pipeline 重构铺路**：明确各任务的输入/输出、产物，便于后续重写脚本为可测试的 Python 模块。

## 2. 现状概述

| 领域 | 当前实现 | 问题 |
| --- | --- | --- |
| 人工训练/预测 | `backend/routes/jobs.py` -> Celery (`jobs.train_model`, `jobs.predict`) -> `Job` 表记录状态 | 仅覆盖人工任务；同步接口仍存在（`routes/modeltrain.py`）；缺少任务日志/产物结构化信息 |
| 自动预测 | 独立服务 `backend-autopredict` + Celery + legacy scripts + `TaskHistory` 表 | 任务状态与记录与主后端不统一；子进程执行难以追踪实时状态；调度信息散落 |
| 同步流程 | `routes/modeltrain.py` 等直接执行训练/评估/上传；`services/scheduler_service` 管理 APScheduler | 阻塞请求、难以横向扩展；调度未纳入任务中心；缺少重试/失败处理 |

## 3. 统一任务模型提议

### 3.1 数据模型（草案）

- **TaskInstance**（替换/扩充现有 `Job` 表）
  - `id`, `task_id`（UUID）
  - `domain`（枚举：`manual`, `autopredict`, `weather`, `reporting`, ...）
  - `task_type`（如 `train.batch`, `predict.batch`, `autopredict.short.train`）
  - `status`（`pending`, `running`, `success`, `failed`, `cancelled`）
  - `queue`, `worker_host`
  - `payload`（JSON 输入快照）
  - `result`（JSON 输出/产物索引）
  - `logs`（可选，指向日志表或 MinIO 对象）
  - `submit_time`, `start_time`, `end_time`
  - `user_id`, `wind_farm_id`, `wind_farm_code`
- **TaskArtifact**（可选）：记录产物类型、URI/MinIO 路径
- **TaskLog**：结构化日志（时间、级别、消息、异常）

> 现有 `jobs` 表可迁移为 `tasks`, 添加新字段；自动预测的 `TaskHistory` 可合并或迁移至 `TaskLog`。

### 3.2 API 设计（v1）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST /tasks` | 提交任务（人工训练/预测，未来包括自动预测手动触发）。返回 `task_id`。 |
| `GET /tasks` | 支持分页/过滤（状态、domain、wind_farm、日期）。 |
| `GET /tasks/{id}` | 返回任务详情、产物列表、日志摘要。 |
| `GET /tasks/{id}/logs` | 流式或分页获取日志。 |
| `POST /tasks/{id}/cancel` | 请求取消任务（若 Celery 支持 revoke）。 |
| `GET /tasks/stats` | 汇总统计（运行中、失败数等）。 |

**Webhook / 推送（后续）**：通过 SocketIO 或 SSE 将任务状态推送给前端，配合任务中心 UI。

### 3.3 前端任务中心对接要点

- Store 统一维护任务列表、筛选条件、详情；与导航标签（keep-alive）联动。
- 长任务（训练、预测、自动预测运行）统一显示在任务中心，可跳转至对应页面。
- 完成/失败任务支持通知或提示条。

## 4. Pipeline 重构路线

### 4.1 待迁移的同步流程

| 模块 | 文件 | 问题 | 目标 |
| --- | --- | --- | --- |
| 模型训练 | `backend/routes/modeltrain.py` | 同步执行、直接操作 MinIO/数据库 | 拆分为：① 上传/入队接口；② Celery 任务复用 pipeline |
| 预测 | `backend/routes/predict.py` | 路由内执行 `run_prediction` | 改为 `/jobs/predict` + pipeline |
| 模型评估 | `services/evaluation_service.py` | 作为同步步骤嵌入 | 拆分为 pipeline 步骤，由 Celery 任务串联 |
| 气象拉取 | `services/scheduler_service.py` + APScheduler | 状态脱离任务中心 | 迁移至 Celery/统一调度 |
| 自动预测脚本 | `backend-autopredict/auto_scripts` | 子进程执行、日志散落 | 替换为 Python pipeline + Celery 任务，输出结构化日志 |

### 4.2 Pipeline 抽象建议

1. **输入结构**：标准化 `DatasetReference`（file_id, local_path, storage_uri）、`ModelReference`、`WindFarmContext` 等。
2. **步骤划分**：
   - 训练：准备数据 -> 调用算法 -> 评估 -> 产物上传 -> 更新 TaskInstance。
   - 预测：数据准备 -> 模型加载 -> 推理 -> 产物上传 -> 更新 TaskInstance。
3. **异常处理**：统一捕获异常，记录在 TaskLog，并设置任务失败状态。
4. **产物注册**：通过 `TaskArtifact` 记录 MinIO 路径/下载链接，为前端任务详情页提供下载。

### 4.3 实施阶段

#### 阶段 A：统一任务模型基础
1. 数据库迁移：扩充 `jobs` 表或创建新 `tasks` 表，增加字段（domain、queue、result、logs 等）。
2. `services/job_service` 改造为 `services/task_service`，提供创建、更新、查询、日志记录接口。
3. 更新现有 `/jobs/*` 路由和 Celery 任务以适配新模型。
4. 在自动预测任务中引入 `task_service`（提交任务、更新状态），逐步取代 `TaskHistory`。

#### 阶段 B：任务 API 与前端对接
1. 实现 `GET /tasks`, `GET /tasks/{id}` 等新 API。
2. 前端任务中心改造，初步接入统一任务列表。
3. 引入 SocketIO/SSE 推送或轮询策略，优化实时性。

#### 阶段 C：同步流程迁移
1. 将 `routes/modeltrain.py` 拆为：
   - 上传/参数验证 -> 仅负责创建 `TaskInstance` 并入队。
   - 新 Celery 任务 `tasks.training.run_pipeline` 调用 pipeline。
2. 重构预测路由 -> Celery 任务 `tasks.prediction.run_pipeline`。
3. 自动预测脚本重写为 pipeline + Celery 任务：
   - 将 `auto_scripts/...` 逐步迁移到 `backend/pipelines/autopredict/`。
   - 替换子进程调用，直接在任务中执行。
4. 气象拉取、报表调度改造为 Celery 周期任务，纳入统一任务中心。

#### 阶段 D：监控与测试
1. 引入结构化日志（JSON logging）及任务指标（Prometheus/FastAPI exporter）。
2. 补充单元/集成测试：任务创建、状态更新、失败重试、产物校验。
3. 设置 Celery Flower 或自定义监控面板，辅助运维。

## 5. 近期行动项（针对阶段 A）

1. **任务模型设计细化**：定义 TaskInstance/TaskArtifact/TaskLog 数据结构与 Alembic 迁移脚本。
2. **task_service 草稿实现**：统一封装 `create_task`, `mark_started`, `mark_success`, `mark_failed`, `append_log` 等。
3. **任务 API 原型**：实现 `GET /tasks`, `GET /tasks/{id}`，用于前端联调。
4. **自动预测接入计划**：梳理 `autopredict.tasks` 如何包装为 `TaskInstance`，明确迁移步骤。
5. **Legacy 接口兼容**：为现有前端提供兼容层，在新 API 就绪前，`/jobs/*` 仍可使用但逐步弃用。

## 6. 风险与依赖

- **数据库迁移**：需同步更新主后端与自动预测后端使用的 ORM 模型，避免版本错位。
- **部署复杂度**：统一队列后，需要协调两个服务的配置与发布节奏。
- **Pipeline 重写工作量大**：自动预测脚本逻辑复杂，建议先对核心任务做封装再逐步替换。
- **监控缺口**：在统一任务中心前，运维需要同步关注旧有监控方式，避免中间状态的盲区。

## 7. 文档 & 跟踪

- 本文档随改造推进持续更新。
- 相关计划文件：
  - `docs/backend-architecture/backend_architecture.md`
  - `docs/backend-architecture/celery_task_inventory.md`
  - 未来：`docs/tasks-api.md`, `docs/pipelines/*`
- 建议在 issue/项目管理工具中拆解为具体任务（数据库迁移、API 实现、pipeline 重写、前端改造等），便于团队协作。


