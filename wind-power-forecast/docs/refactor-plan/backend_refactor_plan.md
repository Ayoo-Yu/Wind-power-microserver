## 后端重构总体目标

- **统一服务架构**：整合 `backend` 与 `backend-autopredict`，识别可复用的核心库，按职责拆分 API、任务调度、数据管道。
- **强化任务化执行**：所有长耗时操作（训练、预测、自动预测、气象拉取、上报）纳入统一队列与状态管理，向前端暴露一致的任务 API。
- **规范配置与部署**：建立多环境配置体系、统一 Docker/Compose 入口，清理遗留脚本，完善运维手册。
- **健全文档与测试**：形成权威文档、自动化验证和上线 checklist，保障后续演进。

## 现状痛点复盘

- **双后端重复**：`backend` 与 `backend-autopredict` 拥有各自的 `routes/ services/ scripts/ tasks/ config`，导致维护双份逻辑、配置分散、依赖难升级。
- **任务状态割裂**：
  - 主后端部分任务已使用 Celery（`backend/task_queue.py`、`backend/tasks/prediction_tasks.py`），但路由仍同步执行大量工作（如 `routes/modeltrain.py` 将训练、评估、MinIO 上传串行完成）。
  - 自动预测后端 `tasks/autopredict.py` 通过子进程跑脚本，状态写入自定义历史表，接口与主后端不一致。
- **脚本散乱**：`backend/scripts/` 与 `backend-autopredict/auto_scripts/`、根目录下还有多套一次性脚本与日志，缺少入口和生命周期管理。
- **配置硬编码**：`config.py` 打印配置、定义常量，环境变量命名不统一；MinIO、数据库、Celery 等在多处重复定义。
- **文档缺失**：部署、数据流、任务管线、脚本用途等文档陈旧或缺失，难以交接。

## 目标架构蓝图

```text
backend/
  apps/
    api/                     # 主 REST API (Flask/FastAPI)
    autopredict/             # 自动预测调度 API（轻量适配，仅保留必要接口）
    admin/                   # 运维工具（可选）
  workers/
    tasks/
      training.py
      prediction.py
      autopredict.py
      reporting.py
      weather_fetch.py
    scheduler/
      apscheduler.py         # 统一调度入口
  pipelines/
    training/                # 数据处理、特征工程、评估
    prediction/
    autopredict/legacy       # 包裹 legacy 脚本
  libs/
    config/                  # Pydantic/BaseSettings 配置模型
    storage/                 # MinIO / 本地文件操作
    database/                # SQLAlchemy session、模型
    auth/
    logging/
  scripts/
    cli.py                   # click/Typer 统一命令入口（train、predict、data-fix）
  tests/
docs/
  backend-architecture.md
  tasks-api.md
  deployment-guide.md
```

核心思路：

- **拆分 Apps 与 Workers**：API 负责接收请求/返回任务 ID；实际计算在 `workers` 中进行。
- **构建 pipelines**：将 `backend/scripts/*.py` 与 `backend-autopredict/auto_scripts` 重构为可调用的 pipeline（模块函数），再由 CLI、任务、调度器复用。
- **共享 libs**：配置、数据库连接、存储、日志、权限等集中在 `libs/`，供 API 与任务共享，避免跨项目复制。

## 任务调度与状态管理

1. **统一 Celery 集群**
   - 单一 `celery_app`，按业务定义队列：`training`, `prediction`, `autopredict`, `reporting`, `weather`.
   - 所有任务采用一致的任务 ID、状态字段（reuse `services/job_service.py`）：
     ```python
     job = create_job(job_id, job_type="training.batch", payload=payload, user_id=current_user.id)
     predict_task.apply_async(args=[payload], task_id=job.job_id, queue="prediction")
     ```
   - `backend-autopredict` 目前的子进程任务 `_execute_script` 改造为 pipeline 模块 + Celery 任务，记录 stdout/stderr 到日志表，废弃手动 `subprocess.run`.

2. **任务查询接口**
   - 在 `apps/api` 暴露统一 REST：`GET /tasks`, `GET /tasks/{id}`, `POST /tasks/{id}/cancel`, `GET /tasks/{id}/logs`.
   - 对接前端任务中心（参见 `frontend_refactor_plan.md` 的任务中心设计）。

3. **调度统一**
   - `workers/scheduler/apscheduler.py` 负责天气拉取、自动预测周期任务，配置存储在数据库（现有 `WeatherTask`、`autopredict_config`）。
   - 对外提供 `scheduler` 管理 API（启动/停止/刷新/日志），避免前端直接感知 apscheduler 细节。

4. **日志与审计**
   - 任务执行统一写入 `job_logs` (新增表)；同时保留原 `WeatherLog`/`TaskHistory` 供历史兼容。
   - MinIO 上传、数据库写入失败的异常捕获后写入日志，任务状态置为 `failed`。

## 配置与环境管理

- 引入 `pydantic-settings`（或自研 BaseSettings）统一管理配置：
  - `CoreSettings`：数据库、Redis、MinIO、日志、CORS。
  - `AppSettings`：上传路径、文件大小限制、默认场站。
  - `SchedulerSettings`：默认 cron、队列名称。
- 支持 `.env`, `.env.local`, `.env.production`，Docker 通过 environment 注入。
- 去除 `config.py` 中直接 `print`，改为日志输出，避免容器启动时泄露密码。
- 提供 `config.sample.env`，配合 `docs/deployment-guide.md` 说明变量含义。

## Pipeline / 脚本治理

- **封装训练/预测流程**：
  - 将 `backend/scripts/data_processor.py`、`scripts/train.py`、`scripts/predict.py` 改为 `pipelines/training/preprocess.py` 等模块。
  - 所有阶段返回结构化结果（路径、指标、日志），便于任务记录。
  - 为 legacy autopredict 脚本创建适配器，逐步消除对多层目录/硬编码路径的依赖。

- **CLI 工具**：
  - 使用 Typer/Click 创建统一入口 `python -m backend.scripts.cli train --data ...`。
  - CLI 内复用 pipeline，替换零散的 `.py` 脚本。

- **清理与归档**：
  - 对旧脚本分类：仍需保留的迁入 `scripts/legacy/`，附 README 标注用途；废弃的删除或归档到 `archive/`.

## 数据与存储策略

- **MinIO**：集中在 `libs/storage/minio.py` 管理 bucket、对象路径；`get_model_path` 等函数迁入，使用统一风电场命名规范。
- **数据库模型**：
  - 建立 `apps/common/models`，拆分领域模型（预测、训练、任务、用户、气象）。
  - 增加外键约束与索引，定义 Alembic 迁移规范。
- **文件系统**：规定 `data/`、`artifacts/`、`logs/` 本地路径，按环境挂载卷；自动清理策略写入文档。

## 文档体系规划

- `docs/backend-architecture.md`：服务拓扑、请求流程、数据流。
- `docs/tasks-api.md`：任务 API 契约、状态定义、样例 payload。
- `docs/pipelines/training.md`：训练 pipeline 步骤、输入输出。
- `docs/deployment-guide.md`：开发环境、Docker Compose、生产部署、监控。
- `docs/ops/scheduler.md`：调度任务管理方式、常见问题。
- `docs/ops/configuration.md`：环境变量说明、密钥管理。
- `docs/runbooks/`：常见运维脚本说明（重置权限、修复任务、清理数据）。
- 为 legacy autopredict 建立迁移说明 `docs/migration/autopredict_legacy.md`。

## 实施路线（建议迭代）

### 阶段 1：基础设施搭建
1. 建立 `libs/config`，切换主后端读取新配置。
2. 整理 `apps/api`（Flask app factory）、`workers/tasks` 目录；迁移现有 Celery 初始化至统一模块。
3. 提供 `GET /tasks` 等任务查询基础接口，前端可消费。
4. 整理 Docker/Compose，形成 **开发/测试** 两份 compose 文件；更新 `README.md`。

### 阶段 2：核心任务迁移
1. 重构 `modeltrain`、`predict` 流程为 pipelines + Celery 任务，路由仅触发任务并立即返回 job_id。
2. 调整 `backend/routes/modeltrain.py`、`routes/predict.py`，接入任务接口。
3. 将 MinIO 上传、评估写入 pipeline / service，统一异常处理。
4. 编写单元测试（pytest）覆盖核心 pipeline。

### 阶段 3：自动预测与调度整合
1. 将 `backend-autopredict/tasks` 迁入 `workers/tasks/autopredict.py`，使用 pipeline 取代子进程。
2. 迁移 `routes/autopredict.py` → `apps/api/modules/autopredict.py`，复用 job API。
3. 整合调度器：`WeatherSchedulerService` 与 autopredict 调度统一由 `scheduler/apscheduler.py` 管理。
4. 定义任务监控、日志采集方式（S3 + 数据库）。

### 阶段 4：脚本治理与文档完善
1. 整理 CLI 工具，迁移剩余脚本并编写使用说明。
2. 完成文档体系撰写，建立发布 checklist。
3. 引入 CI（lint/pytest），为 pipelines 添加集成测试（使用样例 CSV/模型）。

### 阶段 5：性能与鲁棒性
1. 设计任务重试/超时策略，配合 Celery 配置。
2. 加入链路追踪/结构化日志（JSON logging）。
3. 评估将 Flask 升级到 FastAPI 或保留 Flask + 蓝图；同时规划 gRPC/内部服务。

## 近期行动项

1. 创建 `backend/libs/config`，改造主后端读取统一配置（含 `.env.sample`）。
2. 梳理 Celery 任务：列出现有任务（训练、预测、自动预测、系统维护、气象拉取），形成对照表。
3. 拟定数据库迁移计划：新增任务日志表、补充外键。
4. 输出 `docs/backend-architecture.md` 草稿，帮助团队理解新版结构。

完成以上步骤后，可逐项推进 pipeline 重构与自动预测整合，确保与前端重构的任务中心协同。


## 阶段 1 进展记录（2025-11-08）

- 新增 `backend/libs/config/`，通过 `AppSettings`（Pydantic）集中管理数据库、MinIO、Celery、CORS 等配置，提供 `settings = get_settings()` 统一入口。
- `backend/config.py`、`app_factory.py`、`task_queue.py` 等核心入口已切换到新设置，移除分散的 `os.environ` 和重复默认值。
- 更新依赖：`backend/requirements.txt` 与 `backend-autopredict/environment.yml` 引入 `pydantic==1.10.18`。
- 在仓库根目录提供 `env.sample`（部署时重命名为 `.env`），对主要环境变量给出默认或示例值，便于团队统一配置。
- 初始化 `pytest` 测试基座：新增 `backend/tests/`、配置缓存复位 fixture、编写 `test_config_settings.py`，确保配置读取与环境变量覆盖具备回归保障；同时提供 `backend/requirements-dev.txt` 便于安装测试依赖。

### 下一步（阶段 1 剩余事项）

- 梳理并表格式列出现有 Celery 任务（任务名称、队列、触发入口、产物），为后续队列整合做好基线。
- 起草 `docs/backend-architecture.md` 初稿，描述服务拓扑、启动顺序、核心依赖。
- 评估 Docker/Compose 现状，准备拆分开发/测试环境的基础模板。


