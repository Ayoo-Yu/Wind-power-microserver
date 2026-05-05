# Plan: 气象预测数据上传改造 — 从 ecmwf_grid 到 train_pre_*

## 需求重述

**现状**：前端「数据补齐」页面的「气象预测数据」tab 上传 CSV 到 `ecmwf_grid_{farm_code}` 表（长表，JSONB features）。

**目标**：
1. 新增「数据类型」选择（短期 / 中期），分别映射到 `train_pre_short` 和 `train_pre_middle` 表
2. 修改上传接口，让 CSV 宽表数据直接导入对应表（按 `farm_code` 分区）

## 关键发现

| 项目 | 现状 |
|------|------|
| 前端组件 | `frontend/src/views/DataPopulation.vue` — "ecmwf" tab |
| 当前上传接口 | `POST /api/ecmwf/grid/ingest_async`（异步，有 job_id + 轮询） |
| 目标接口 | `POST /api/upload_feature_csv`（同步，已有 chunked upsert） |
| 目标表结构 | 宽表：`record_id`, `Timestamp`, `farm_code` + ~300 个 DOUBLE PRECISION 列 |
| 表分区 | LIST(farm_code) + RANGE(Timestamp 月分区) |
| CSV 格式 | `Timestamp,100u_23.8_103.2,10u_23.8_103.2,...` — 与目标表列名完全匹配 |

## 实现步骤

### Step 1: 前端 API 层 — 新增 feature 上传函数

**文件**: `frontend/src/api/dataImportApi.js`

- 新增 `uploadFeatureCsv({ file, farmCode, tableName, onUploadProgress, signal })`
- `POST /api/upload_feature_csv`，FormData: `file`, `farm_code`, `table_name`
- 超时 600s（大文件支持）

### Step 2: 前端组件 — 新增数据类型选择器

**文件**: `frontend/src/views/DataPopulation.vue`

**配置区变更**（ecmwf tab 内）：
- `ecmwfForm` 新增 `dataType` 字段，默认 `'train_pre_short'`
- 新增 `el-select`，选项：
  - `train_pre_short` → 「短期预测」
  - `train_pre_middle` → 「中期预测」
- `canUploadEcmwf` 计算属性增加 `ecmwfForm.dataType` 检查

**上传逻辑变更**：
- `uploadOneFile` 函数中 ecmwf 分支：调用 `uploadFeatureCsv` 替代 `uploadEcmwfGridAsync`
- 因为 `/api/upload_feature_csv` 是同步接口（直接返回结果），不需要轮询 job
- 改为：上传后直接从 response 中提取 `inserted_count` / `updated_count` / `error_count`
- 更新 `buildResultFromJob` 适配同步返回格式

**CSV 格式说明更新**：
- 更新提示文字，说明列名需匹配 train_pre 表列名

### Step 3: 后端 — 确认接口兼容性（无需改动）

`feature_upload.py` 的 `POST /api/upload_feature_csv` 已支持：
- ✅ `table_name` 参数（train_pre_short / train_pre_middle）
- ✅ `farm_code` 参数
- ✅ chunked 读取 + upsert（查重 + 更新/插入）
- ✅ 返回 `{ inserted_count, updated_count, error_count }`

**无需后端改动**，直接复用现有接口。

## 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/api/dataImportApi.js` | 新增 `uploadFeatureCsv` 函数 |
| `frontend/src/views/DataPopulation.vue` | 新增数据类型选择 + 修改上传逻辑 |

## 风险评估

- **LOW**: 后端接口已完整可用，无需修改
- **LOW**: 前端改动局限在一个组件 + 一个 API 文件
- **MEDIUM**: 同步接口 vs 异步轮询 — 大文件上传时前端体验差异（无服务端处理进度），但上传进度（onUploadProgress）仍可用
