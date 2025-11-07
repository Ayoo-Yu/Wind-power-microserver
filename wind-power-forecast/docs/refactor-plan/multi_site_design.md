## 多场站数据模型梳理（Phase4-Step1）

### 现状概览
- `Dataset.wind_farm` 仅保存场站名称字符串，缺乏外键约束，模型/预测/任务等表无法可靠关联到场站。
- `Model`、`TrainingRecord`、`PredictionRecord` 等与训练预测相关的表，唯一标识大多指向 `datasets.file_id`，没有场站粒度的数据隔离。
- MinIO 对象路径采用单一桶结构（如 `wind-models`），没有以场站为前缀管理模型/结果，难以分场站维护。
- 配置（风机列表、特征、调度频率等）散落在脚本或静态文件中，没有统一的按场站配置来源。

### 缺口总结
1. **实体缺失**：没有独立的 `WindFarm` 表，相关信息（名称、编码、经纬度、装机容量等）无法统一管理；也缺少风机级别配置（`Turbine`）。
2. **引用不一致**：各业务表仅依赖 `file_id`、字符串字段，后续扩展/迁移极易碰到数据冲突。
3. **存储目录混乱**：MinIO、日志、模型等文件未按场站分层，增加新场站时需要复制目录结构。
4. **任务配置不足**：自动任务（训练/预测、调度）缺乏场站维度的配置输入，队列任务目前也未记录场站。

### 数据模型方案（初稿）

| 表名 | 目的 | 主要字段 |
| --- | --- | --- |
| `wind_farms` | 场站主表 | `id`、`code`、`name`、`capacity`、`location`、`timezone`、`config`(JSON) |
| `turbines` | 风机/子资源信息 | `id`、`wind_farm_id`、`code`、`rated_power`、`status` |
| `datasets`（现有） | 增加外键 | 新增 `wind_farm_id` (`ForeignKey`)，保留 `wind_farm` 字段作为兼容字段并逐步迁移 |
| `models`、`training_records`、`prediction_records`、`training_history`、`jobs` | 新增 `wind_farm_id`，并可选 `turbine_group`、`horizon` 等辅助字段 |
| `auto_prediction_tasks` | 新增 `wind_farm_id`、调度配置 JSON，便于多场站独立调度 |
| `daily_metrics` 等统计表 | 新增 `wind_farm_id`、`turbine_count` |

> 兼容策略：新增外键字段初期允许 `NULL`，通过迁移脚本回填默认场站（例如当前唯一场站），在多场站上线前再设置非空约束。

### 文件/对象存储调整
- MinIO 对象命名调整为 `f"{wind_farm_code}/models/..."`、`"{wind_farm_code}/datasets/..."` 等；上传/下载服务根据场站决定路径。
- 本地缓存（`UPLOAD_FOLDER`、`DOWNLOAD_FOLDER`）调整为 `uploads/{wind_farm_code}/...` 结构。
- 日志、自动预测脚本输出目录按场站拆分，避免混用。

### 配置与应用层影响
- 在 `Config`/`.env` 中增加 `DEFAULT_WIND_FARM`，用于回填迁移及本地环境默认值。
- 队列任务 payload 增加 `wind_farm_id` 或 `wind_farm_code`，worker 在运行前检查并注入上下文。
- API 请求新增 `wind_farm_id` 参数（如上传、训练、预测、调度），并在响应中返回场站信息。
- 前端路由与 store 需要引入场站选择器，所有页面调用 API 时附带场站上下文。
- 前端全局 Axios 拦截器默认附带 `X-Windfarm-Code` 请求头；表单/任务提交额外携带 `wind_farm_code` 字段以兼容旧接口。

### 前端适配与 UI 提示
- 布局右上角新增场站选择器，状态保存在本地并通过 `windFarmStore` 对外暴露。
- 关键页面（功率预测、功率对比、气象数据拉取、系统维护等）在 UI 顶部展示“当前场站”标识，切换时自动刷新各自数据。
- 自定义 API 请求或第三方库调用需复用 `axiosInstance` 或手动附带 `X-Windfarm-Code`/`wind_farm_code`，以避免数据串场。

### 下一步（Step2 参考）
1. 设计 Alembic/SQL 脚本：创建 `wind_farms` 表，向相关表添加 `wind_farm_id` 列并建立索引。
2. 填充默认场站：添加脚本或管理接口用于维护场站基础信息。
3. 更新 ORM 模型、Pydantic schema、服务层逻辑，使其在读写时统一携带场站信息。

> 已新增 SQL 迁移草稿：`database/migrations/20250101_add_wind_farm_support.sql`，执行前请先备份数据库，确保新增列与外键符合环境需求。

此文档供后续数据库迁移与应用改造参考，如需补充额外字段或业务限制（如调度频率、数据源 URL），请告知，我会纳入最终设计。


