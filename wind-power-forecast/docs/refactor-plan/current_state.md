## 项目现状梳理

### 运行组件
- `backend/app.py`：单体 Flask 应用，整合数据上传、模型训练、预测、调度、运维、认证等全部接口，并直接初始化数据库、MinIO、SocketIO、调度器。
- `backend-autopredict/app.py`：为自动预测脚本提供的 Flask 应用，现已改造成通过 Celery 队列触发训练/预测任务，并复用公共的数据库、日志、配置初始化逻辑。
- `frontend/`：Vue 2 + Element UI 前端，所有页面通过一个 `axios` 实例调用后端 REST 接口。

### 主要功能与代码分布
- **数据上传/下载**：`routes/upload.py`、`routes/download.py`；配套服务 `services/file_service.py`，MinIO 操作逻辑散落在路由内。
- **模型训练/管理**：`routes/modeltrain.py`、`routes/training.py`、`services/modeltrain_service.py`；训练脚本位于 `scripts/train.py`、`scripts/data_processor.py` 等。
- **人工预测**：`routes/predict.py` 调用 `services/predict_service.py` → `scripts/predict.py`，直接在请求内读取本地文件并执行 joblib 模型。
- **自动预测/调度**：`backend-autopredict/routes/autopredict.py` 通过 Celery 任务封装 short/middle/supershort 的训练与预测脚本，路由负责创建/启停调度配置、触发任务、查询日志和任务历史。
- **运维监控**：`routes/system_info_router.py`、`routes/report_management_router.py` 等用于系统状态上报。
- **用户与权限**：`routes/auth.py`、`routes/user.py` 与 JWT 配置；角色表定义在 `db_models/user_roles.py`。

### 脚本与调度
- `backend/scripts/`：人工触发的训练、预测、评估脚本，与 Web 路由紧耦合。
- `backend-autopredict/auto_scripts/`：三套（short/middle/supershort）独立的训练与预测脚本树，仍由 Celery worker 在子进程中调用执行。
- 调度方式：主后端 `services/scheduler_service.py` 试图初始化 APScheduler；自动预测后端通过 Celery Beat（或外部编排）周期性触发任务，flag 文件仅作为脚本内部的完成标记。

### 数据与存储
- 数据库：使用 Kingbase（PostgreSQL 方言），SQLAlchemy 模型集中在 `db_models/`，但没有统一的 `wind_farm` 表，多数表缺少外键约束。
- 对象存储：依赖 MinIO；不同模块对桶名、路径、连接方式各自硬编码，缺乏统一封装。
- 本地文件：上传内容先保存到 `UPLOAD_FOLDER`，再复制/上传到 MinIO；预测结果写入 `DOWNLOAD_FOLDER`。

### 前端结构
- `src/components` 下按页面功能堆叠组件，如 `PowerPredict.vue`、`AutoPredict.vue`、`ModelTrain.vue`。
- API 调用集中在 `src/api/*.js`，缺乏域内封装；没有对多场站做任何抽象。

### 测试与运维现状
- 仓库中无自动化测试（无 pytest、无前端测试）；`scripts` 和 `logs` 目录存放手工执行记录。
- 部署依赖多份 Dockerfile、shell/bat 脚本，没有统一的 compose/CI 管理。

### 现存痛点
1. **代码重复**：`backend` 与 `backend-autopredict` 共享模型、配置、数据库逻辑，但分别维护，修改易遗漏。
2. **层次混乱**：路由里夹杂业务逻辑、存储操作、脚本调用；难以扩展或替换实现。
3. **任务调度脆弱**：（已部分改善）已引入 Celery 任务，但调度与容器化仍待统一落地，日志/监控需要纳入平台化方案。
4. **多场站不可用**：数据库与存储路径未区分场站，配置散落，无法支撑多场站并行。
5. **缺少基线测试**：任何改动都要手动全链路验证，风险高。

### 基线测试计划（后续实施）
- **接口冒烟**：登录、数据上传、触发预测、下载结果、查询任务状态、获取系统信息。
- **训练/预测回归**：使用仓库内样例数据（如 `training_data_middle.csv`）完成一次训练+预测，校验生成的模型与预测文件。
- **自动预测路径**：在测试环境启动 Celery worker/beat，验证任务触发、状态查询、日志抓取流程。
- **前端检查**：关键页面（登录、预测、自动预测、模型管理）加载与交互无错误。


