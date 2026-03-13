# 上报配置与调度页面代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 上报配置与调度 |
| 所属模块 | 数据交互 |
| 路由路径 | `/reportmanagement` |
| 页面入口文件 | [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) |
| 页面依赖的子组件列表 | 代码中未发现自定义业务子组件；页面使用 Element Plus 组件和图标 `Edit/Delete/View/Plus/Refresh/Search/RefreshLeft` |
| 页面依赖的 store/hooks/model/service/api 文件 | [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js)、[router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)、[AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) |
| 页面是否受权限控制 | 是。路由 `meta.requiredPermissions = ['manage_reports']`；侧边栏菜单通过 `hasPermission('manage_reports')` 显示；但全局路由守卫当前只校验登录态，代码中未发现按 `requiredPermissions` 强制拦截 |

### 1.2 页面定位

该页面是当前仓库中最复杂的业务页之一，已经形成“配置 + 调度 + 监控 + 预览 + 日志 + 手工上报”的完整操作台。它同时承担：

- 上报调度器启动/停止/刷新
- 上报统计总览
- 实时监控矩阵与失败重试
- 手工文件生成、预览、下载、强制推送
- 上报配置 CRUD
- 上报日志查询、分页、详情
- 预览报文并在前端直接编辑 payload

### 1.3 关键事实

1. 页面体量约 3918 行，功能高度集中在 [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)。
2. 页面核心依赖 [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js) 中的 10+ 个接口。
3. 页面存在 60 秒自动刷新逻辑，但仅用于“实时监控矩阵”。
4. 页面对上报配置的部分敏感字段使用 `localStorage` 做本地补充缓存：
   - `protocol_type`
   - `server_username`
   - `server_password`
   - `remote_directory`
   - `file_name_template`
5. 预览报文在数据为空时，会按不同上报类型生成前端模板数据，不完全依赖后端真实返回。
6. 手工上报链路并不只是在预览里编辑后提交，还额外提供了“生成文件 -> 预览文件内容 -> 下载 -> 强制推送”的工具区。

---

## 2. 页面结构树

```text
上报配置与调度 ReportManagement.vue
├─ 页面头部
│  ├─ 标题
│  ├─ 总结告警条
│  └─ 统计更新时间
├─ 调度器状态卡
│  ├─ 运行状态标签
│  ├─ 启动/停止/刷新按钮
│  └─ 调度说明信息
├─ 内容区
│  ├─ 统计总览卡
│  │  ├─ 场站/月度筛选
│  │  ├─ 查询按钮
│  │  ├─ 日/月四个统计值
│  │  ├─ 四个 dashboard 仪表
│  │  └─ 每日统计表
│  ├─ 实时监控卡
│  │  ├─ 场站筛选
│  │  ├─ 刷新按钮
│  │  ├─ 08:00 上报状态
│  │  └─ 15 分钟槽位监控表
│  ├─ 手工工具卡
│  │  ├─ 场站/类型/日期筛选
│  │  ├─ 生成文件
│  │  ├─ 预览文件内容
│  │  ├─ 下载到本地
│  │  └─ 强制推送
│  ├─ 配置列表卡
│  │  ├─ 新增配置按钮
│  │  └─ 配置表
│  │     ├─ 启停开关
│  │     ├─ 编辑
│  │     ├─ 预览
│  │     └─ 删除
│  └─ 日志列表卡
│     ├─ 场站/类型/状态/时间筛选
│     ├─ 搜索/重置/刷新
│     ├─ 日志表
│     └─ 分页
├─ 配置弹窗
├─ 日志详情弹窗
├─ 预览弹窗（可编辑数据）
└─ 手工文件预览弹窗
```

---

## 3. 区块说明

### 3.1 页面头部区

| 项目 | 说明 |
|---|---|
| 区块名称 | 页面头部区 |
| 对应组件名 | `ReportManagement` |
| 文件路径 | [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) |
| 展示内容 | 页面标题、统计总结告警条、统计更新时间 |
| 数据来源 | `statsConclusion`、`statsUpdatedAt` |
| 是否可交互 | 否 |
| 是否有权限控制 | 页面进入依赖路由和菜单权限 |
| 是否有定时刷新或自动更新 | `statsUpdatedAt` 仅在 `fetchStatistics()` 成功后更新 |

### 3.2 调度器状态卡

| 项目 | 说明 |
|---|---|
| 区块名称 | 调度器状态卡 |
| 对应组件名 | `ReportManagement` |
| 文件路径 | [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) |
| 展示内容 | 调度器当前运行状态、启动/停止/刷新按钮、下一次上报时间、调度说明 |
| 数据来源 | `schedulerStatus` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现按钮级权限控制 |
| 是否有定时刷新或自动更新 | 否，需手动刷新；实时监控刷新不会带动此区域自动更新 |

### 3.3 统计总览卡

| 项目 | 说明 |
|---|---|
| 区块名称 | 上报统计总览卡 |
| 对应组件名 | `ReportManagement` |
| 文件路径 | [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) |
| 展示内容 | 场站/月度筛选、查询按钮、日/月完整率与及时率、4 个 dashboard 仪表、每日统计表 |
| 数据来源 | `getReportStatistics()` 返回的 `today_stats/monthly_summary/daily_stats`，再经前端格式化 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否，用户主动查询 |

### 3.4 实时监控卡

| 项目 | 说明 |
|---|---|
| 区块名称 | 实时监控卡 |
| 对应组件名 | `ReportManagement` |
| 文件路径 | [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) |
| 展示内容 | 指定场站 15 分钟槽位监控、失败原因、失败重试、08:00 长周期上报状态 |
| 数据来源 | `getReportLogs()` 返回的日志，再由前端聚合成 `realtimeMonitorRows` 和 `shortTermStatus` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 是。`setInterval` 每 60 秒自动刷新一次 |

### 3.5 手工工具卡

| 项目 | 说明 |
|---|---|
| 区块名称 | 手工工具卡 |
| 对应组件名 | `ReportManagement` |
| 文件路径 | [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) |
| 展示内容 | 手工文件生成、预览、下载、强制推送 |
| 数据来源 | `manualToolForm`、`previewReportApi` 返回数据、前端 `payloadToCsv()` 结果 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

### 3.6 配置列表卡

| 项目 | 说明 |
|---|---|
| 区块名称 | 配置列表卡 |
| 对应组件名 | `ReportManagement` |
| 文件路径 | [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) |
| 展示内容 | 上报配置表、启停、编辑、预览、删除、新增配置 |
| 数据来源 | `getReportConfigs()` 返回数据 + `localStorage` 中的配置元信息补全 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现表内按钮级权限控制 |
| 是否有定时刷新或自动更新 | 否 |

### 3.7 日志列表卡

| 项目 | 说明 |
|---|---|
| 区块名称 | 日志列表卡 |
| 对应组件名 | `ReportManagement` |
| 文件路径 | [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) |
| 展示内容 | 场站/类型/状态/时间筛选、搜索、重置、刷新、日志表、分页、详情 |
| 数据来源 | `getReportLogs()` 返回的 `logs/total` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

### 3.8 预览弹窗区

| 项目 | 说明 |
|---|---|
| 区块名称 | 报文预览弹窗区 |
| 对应组件名 | `ReportManagement` |
| 文件路径 | [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) |
| 展示内容 | 配置信息、数据概览、可编辑表格/JSON、分页、原始数据显示、保存推送 |
| 数据来源 | `previewReportApi(config.id)` 返回值；当返回数据为空时，前端按类型生成模板数据 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

---

## 4. 组件明细表

### 4.1 页面主组件 `ReportManagement`

| 项目 | 说明 |
|---|---|
| 组件名称 | `ReportManagement` |
| 文件路径 | [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) |
| 父子关系 | 路由页面组件；无自定义业务子组件 |
| props / emits / callbacks | 无 props / emits |
| 内部 state / computed / hooks / store 使用情况 | 使用 `ref/reactive/computed/onMounted/onUnmounted`；无 Vuex/Pinia |
| 生命周期或副作用逻辑 | `onMounted` 初始化多个数据源，并启动 60 秒实时监控轮询；`onUnmounted` 清理轮询并恢复 `console.error` |
| 实现的具体功能 | 调度器控制、统计总览、实时监控、配置 CRUD、日志查询、预览编辑、手工生成与推送 |
| 触发了哪些接口 | `getReportFarms/getReportConfigs/getReportSchedulerStatus/startReportScheduler/stopReportScheduler/getReportLogs/createReportConfig/updateReportConfig/deleteReportConfig/previewReport/manualReport/getReportStatistics` |
| 与其他组件的联动关系 | 同一页内部多个区块联动：配置、日志、实时监控、手工工具、预览弹窗相互影响 |
| 加载态 / 空态 / 异常态如何处理 | 多个局部 loading；多数异常通过 `ElMessage.error`；部分预览数据为空时有前端模板兜底 |

#### 4.1.1 关键状态

页面核心状态包括：

- 列表与基础数据
  - `windFarms`
  - `reportConfigs`
  - `reportLogs`
- loading
  - `farmsLoading`
  - `configsLoading`
  - `logsLoading`
  - `schedulerLoading`
  - `statsLoading`
  - `monitorLoading`
  - `previewLoading`
  - `configSaving`
  - `manualToolLoading`
  - `manualPushing`
- 调度器
  - `schedulerStatus`
- 统计
  - `statsQuery`
  - `statistics`
  - `dailyStats`
  - `monthlyStats`
  - `statsUpdatedAt`
  - `statsConclusion`
- 配置弹窗
  - `configDialogVisible`
  - `configForm`
  - `configRules`
  - `configDialogTitle`
- 日志查询
  - `logQuery`
  - `logPagination`
  - `logDetailVisible`
  - `currentLog`
- 预览
  - `previewDialogVisible`
  - `previewData`
  - `editableData`
  - `allEditableData`
  - `showRawData`
  - `currentPage`
  - `pageSize`
  - `totalRows`
  - `isPaginated`
- 实时监控
  - `monitorFarmCode`
  - `realtimeMonitorRows`
  - `shortTermStatus`
- 手工工具
  - `manualToolForm`
  - `manualGeneratedPayload`
  - `manualGeneratedText`
  - `manualGeneratedFilename`
  - `manualTargetConfigId`
  - `manualPreviewVisible`

#### 4.1.2 本地缓存逻辑

配置元信息本地缓存 key：

- `CONFIG_META_STORAGE_KEY = 'report_config_meta_v2'`

缓存内容：

- `protocol_type`
- `server_username`
- `server_password`
- `remote_directory`
- `file_name_template`

逻辑：

1. `fetchConfigs()` 时：
   - 先从接口拿配置列表
   - 再用 `normalizeConfig(config, storedMeta)` 把 localStorage 中的敏感补充字段合并回配置对象

2. `saveConfig()` 成功后：
   - `persistConfigMeta(configId, saveData)` 把上述字段写入 localStorage

关键结论：

- 配置管理并不完全依赖后端返回
- 页面存在“接口数据 + 本地缓存补充”双源合并逻辑

#### 4.1.3 统计总览逻辑

核心函数：`fetchStatistics()`

调用接口：

- `getReportStatistics(params)`

请求参数：

- `farm_code` 可选
- `month` 可选

返回字段消费：

- `response.data.today_stats` -> `dailyStats`
- `response.data.monthly_summary` -> `monthlyStats`
- `response.data.daily_stats` -> `statistics`

前端二次加工：

- `statsUpdatedAt = formatNow()`
- `statsConclusion` 从日/月多个率中找最弱项，拼接为顶部总结文案
- `formatRate/normalizeRate/getGaugeColor/getRateColor` 用于展示色彩和格式

#### 4.1.4 调度器逻辑

核心函数：

- `fetchSchedulerStatus()`
- `startScheduler()`
- `stopScheduler()`
- `refreshSchedulerStatus()`

接口：

- `getReportSchedulerStatus`
- `startReportScheduler`
- `stopReportScheduler`

页面行为：

- 启动/停止成功后重新获取状态
- 刷新按钮只做状态刷新
- 状态标签由 `schedulerStatus.running` 控制

#### 4.1.5 配置 CRUD 逻辑

核心函数：

- `fetchConfigs()`
- `showAddConfigDialog()`
- `editConfig(config)`
- `saveConfig()`
- `toggleConfig(config)`
- `deleteConfig(config)`
- `handleReportTypeChange()`
- `resetConfigForm()`

关键规则：

1. `forecast_long`
- 使用 `report_time`
- 强制 `report_interval = -1`
- 若为空默认 `report_time = '09:00'`

2. 非 `forecast_long`
- 使用 `report_interval`
- 强制 `report_time = null`
- 默认 `report_interval = 15`

3. 启停配置
- `toggleConfig()` 直接调用 `updateReportConfig(config.id, { is_enabled: config.is_enabled })`
- 失败时会把 UI 开关状态回滚

#### 4.1.6 日志逻辑

核心函数：

- `fetchLogs()`
- `refreshLogs()`
- `resetLogQuery()`
- `viewLogDetail(log)`
- `handleSizeChange()`
- `handleCurrentChange()`

接口：

- `getReportLogs(params)`

查询参数组装：

- `page`
- `per_page`
- `farm_code`
- `report_type`
- `status`
- `start_date`
- `end_date`

返回字段消费：

- `response.data.logs` -> `reportLogs`
- `response.data.total` -> `logPagination.total`

#### 4.1.7 实时监控逻辑

核心函数：

- `refreshRealtimeMonitor()`
- `retryMonitorTask(row)`
- `resolveRetryConfigId(farmCode, reportType)`

实现方式：

1. 取当前时间前后各 1 小时窗口
2. 调 `getReportLogs({ page:1, per_page:300, report_type:'forecast_short', start_date })`
3. 按 15 分钟时间槽聚合日志
4. 为每个槽位构造：
   - `statusType`
   - `statusText`
   - `reason`
   - `canRetry`
   - `configId`
5. 再单独查询 `forecast_long`，判断当天 08:00 附近是否成功上报

自动刷新：

- `onMounted` 中 `setInterval(() => refreshRealtimeMonitor(), 60 * 1000)`

#### 4.1.8 预览与编辑逻辑

核心函数：

- `previewReport(config)`
- `editableDataJson`
- `updateEditableDataFromJson()`
- `handleJsonKeydown()`
- `updateCurrentPageData()`
- `handlePageChange()`
- `syncCurrentPageToAll()`
- `getAllDataForSubmit()`

关键事实：

1. 先调 `previewReportApi(config.id)` 获取预览数据。
2. 若 `response.data.payload.data` 为空：
   - 页面会按不同 `report_type` 生成模板数据。
3. 对长周期和部分大数据量场景，页面还做了分页编辑和 JSON 编辑。
4. 对 `actual/forecast_long/forecast_short` 等类型，编辑时会自动修正 `data_source`：
   - `empty -> manual`
   - `manual -> empty`

说明：

- 预览页不是只读预览，而是一个前端数据编辑器。

#### 4.1.9 手工工具逻辑

核心函数：

- `resolveManualToolConfig()`
- `buildTemplateFilename()`
- `payloadToCsv()`
- `generateManualFile()`
- `openManualPreview()`
- `downloadManualFile()`
- `forcePushManualFile()`

链路：

1. 根据 `manualToolForm.farm_id + report_type` 找到目标配置
2. 调 `previewReportApi(config.id)` 获取 payload
3. 按 `report_date` 过滤出目标日期数据
4. 生成：
   - `manualGeneratedPayload`
   - `manualGeneratedText`
   - `manualGeneratedFilename`
   - `manualTargetConfigId`
5. 可：
   - 预览文本
   - 下载文件
   - 调 `manualReportApi({ config_id, data })` 强制推送

#### 4.1.10 生命周期与副作用

`onMounted`：

1. `fetchFarms()`
2. 初始化 `monitorFarmCode`、`manualToolForm.farm_id`
3. `fetchConfigs()`
4. `fetchLogs()`
5. `fetchSchedulerStatus()`
6. `fetchStatistics()`
7. `refreshRealtimeMonitor()`
8. 启动 60 秒监控轮询
9. 增加 `ResizeObserver` 错误吞掉逻辑
10. 覆盖 `console.error`，屏蔽 `ResizeObserver loop completed...`

`onUnmounted`：

- 清理 `tableUpdateTimer`
- 清理 `monitorTimer`
- 恢复原始 `console.error`

#### 4.1.11 加载态 / 空态 / 异常态

- loading
  - 各区块独立 `statsLoading/configsLoading/logsLoading/monitorLoading/...`
- 空态
  - 统计表 `empty-text`
  - 预览空数据时用前端模板兜底
- 异常态
  - 大部分接口失败后 `ElMessage.error`
  - 预览失败同样提示
  - 配置开关失败会回滚

### 4.2 子组件递归分析结论

代码中未发现自定义业务子组件，因此不需要继续递归拆解。

---

## 5. 交互明细表

### 5.1 调度器区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 标签 | 调度器卡 | 运行中/已停止 | 显示调度器状态 | 只读 | 否 | 否 | 否 |
| 按钮 | 调度器卡 | 启动 | 启动调度器 | 调 `startScheduler()` | 否 | 是，`startReportScheduler` | 影响调度器状态区 |
| 按钮 | 调度器卡 | 停止 | 停止调度器 | 调 `stopScheduler()` | 否 | 是，`stopReportScheduler` | 同上 |
| 按钮 | 调度器卡 | 刷新 | 刷新状态 | 调 `refreshSchedulerStatus()` | 否 | 是，`getReportSchedulerStatus` | 同上 |

### 5.2 统计总览区

| 元素类型 | 位置 | 文案/标识 | 功能 | 行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 下拉框 | 统计卡头部 | 场站 | 筛选统计场站 | `@change="fetchStatistics"` | 否 | 是，`getReportStatistics` | 影响统计卡全部内容 |
| 月份选择器 | 统计卡头部 | 月份 | 筛选月份 | `@change="fetchStatistics"` | 否 | 是 | 同上 |
| 按钮 | 统计卡头部 | 查询 | 手动查询统计 | 调 `fetchStatistics()` | 否 | 是 | 同上 |
| 仪表盘 | 统计卡主体 | 四个 dashboard | 展示完整率/及时率 | 只读 | 否 | 否 | 否 |
| 表格 | 统计卡主体 | 每日统计表 | 展示 daily stats | 只读 | 否 | 否 | 否 |

### 5.3 实时监控区

| 元素类型 | 位置 | 文案/标识 | 功能 | 行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 下拉框 | 监控卡头部 | 场站 | 筛选监控场站 | `@change="refreshRealtimeMonitor"` | 否 | 是，`getReportLogs` | 影响监控矩阵与 08:00 状态 |
| 按钮 | 监控卡头部 | 刷新监控 | 手动刷新 | 调 `refreshRealtimeMonitor()` | 否 | 是 | 同上 |
| 表格 | 监控卡主体 | 15 分钟监控表 | 展示每个槽位状态 | 只读 + 重试按钮 | 否 | 否 | 无 |
| 按钮 | 监控表操作列 | 重试 | 对失败槽位执行重试 | 调 `retryMonitorTask(row)` | 否 | 是，`manualReportApi`，必要时先 `getReportConfigs` | 刷新监控和日志 |

### 5.4 手工工具区

| 元素类型 | 位置 | 文案/标识 | 功能 | 行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 下拉框 | 手工工具卡 | 场站 | 选择目标场站 | 更新 `manualToolForm.farm_id` | 否 | 否 | 影响生成文件 |
| 下拉框 | 手工工具卡 | 上报类型 | 选择目标类型 | 更新 `manualToolForm.report_type` | 否 | 否 | 影响生成文件 |
| 日期选择器 | 手工工具卡 | 上报日期 | 选择报文日期 | 更新 `manualToolForm.report_date` | 否 | 否 | 影响生成文件 |
| 按钮 | 手工工具卡 | 生成文件 | 生成手工报文 | 调 `generateManualFile()` | 否 | 是，`getReportConfigs` + `previewReportApi` | 更新手工预览/下载/强推数据 |
| 按钮 | 手工工具卡 | 预览文件内容 | 打开文本预览 | 调 `openManualPreview()` | 否 | 否 | 打开预览弹窗 |
| 按钮 | 手工工具卡 | 下载到本地 | 下载 CSV | 调 `downloadManualFile()` | 否 | 否 | 无 |
| 按钮 | 手工工具卡 | 强制推送 | 直接推送手工报文 | 调 `forcePushManualFile()` | 否 | 是，`manualReportApi` | 刷新监控和日志 |

### 5.5 配置列表区

| 元素类型 | 位置 | 文案/标识 | 功能 | 行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 按钮 | 配置卡头部 | 新增配置 | 打开配置弹窗 | 调 `showAddConfigDialog()` | 否 | 否 | 打开配置弹窗 |
| 开关 | 配置表 | 启用/禁用 | 切换配置 | 调 `toggleConfig(config)` | 否 | 是，`updateReportConfig` | 刷新/回滚当前行 |
| 按钮 | 配置表 | 编辑 | 打开编辑弹窗 | 调 `editConfig(config)` | 否 | 否 | 打开配置弹窗 |
| 按钮 | 配置表 | 预览 | 打开报文预览 | 调 `previewReport(config)` | 否 | 是，`previewReportApi` | 打开预览弹窗 |
| 按钮 | 配置表 | 删除 | 删除配置 | 调 `deleteConfig(config)` | 否 | 是，`deleteReportConfig` | 刷新配置表 |

### 5.6 日志区

| 元素类型 | 位置 | 文案/标识 | 功能 | 行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 下拉框 | 日志区 | 场站 | 筛选日志 | 更新 `logQuery.farm_code` | 否 | 否，待点击搜索/刷新 | 影响日志查询参数 |
| 下拉框 | 日志区 | 类型 | 筛选日志 | 更新 `logQuery.report_type` | 否 | 否 | 同上 |
| 下拉框 | 日志区 | 状态 | 筛选日志 | 更新 `logQuery.status` | 否 | 否 | 同上 |
| 日期范围 | 日志区 | 时间 | 筛选日志时间 | 更新 `logQuery.dateRange` | 否 | 否 | 同上 |
| 按钮 | 日志区 | 搜索 | 查询日志 | 调 `fetchLogs()` | 否 | 是，`getReportLogs` | 刷新日志表 |
| 按钮 | 日志区 | 重置 | 清空筛选 | 调 `resetLogQuery()` | 否 | 否/后续会查 | 刷新日志表 |
| 按钮 | 日志区 | 刷新 | 重新查询 | 调 `refreshLogs()` | 否 | 是 | 刷新日志表 |
| 表格行按钮 | 日志区 | 详情 | 查看日志详情 | 调 `viewLogDetail(log)` | 否 | 否 | 打开详情弹窗 |
| 分页器 | 日志区 | 页码/每页数 | 翻页 | 调 `handleCurrentChange/handleSizeChange` | 否 | 是 | 刷新日志表 |

### 5.7 配置弹窗与预览弹窗

这两个区块元素较多，当前代码可确认的关键交互：

- 配置弹窗
  - 场站、类型、协议、目标 IP/端口、账号密码、目录、文件名模板、周期、时间、格式、超时、重试、启用开关
  - 保存时触发 `saveConfig()`
- 预览弹窗
  - 可切换表格编辑 / JSON 编辑 / 原始数据显示
  - 可分页编辑大数据量
  - 可在弹窗内直接调用 `manualReportApi` 提交

---

## 6. 接口明细表

### 6.1 页面使用的接口

| 接口名称 | 请求方法 | URL | 所在文件 | 调用函数名 | 触发条件 | 请求参数 | 返回结构 | 页面消费位置 | 失败处理 |
|---|---|---|---|---|---|---|---|---|---|
| 获取上报场站 | GET | `/api/v1/report/farms`，回退 `/api/report/farms` | [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js) | `getReportFarms()` | 页面初始化 | 无 | 页面按 `response.data` 读取，预期为场站数组 | `windFarms` | `ElMessage.error` |
| 获取配置列表 | GET | `/api/v1/report/configs`，回退 `/api/report/configs` | 同上 | `getReportConfigs(params)` | 页面初始化、筛选后、保存/删除配置后、重试场景查配置 | `farm_id` 可选 | 页面按 `response.data` 读取数组 | `reportConfigs`、`resolveManualToolConfig`、`resolveRetryConfigId` | `ElMessage.error` |
| 获取调度器状态 | GET | `/api/v1/report/scheduler/status`，回退 `/api/report/scheduler/status` | 同上 | `getReportSchedulerStatus()` | 页面初始化、启动/停止/刷新后 | 无 | 页面按 `response.data` 读取，预期至少含 `running/next_report_times` | `schedulerStatus` | `ElMessage.error` |
| 启动调度器 | POST | `/api/v1/report/scheduler/start`，回退 `/api/report/scheduler/start` | 同上 | `startReportScheduler()` | 点击启动 | 无 | 页面消费 `response.data.message` | 消息提示 + 重新拉状态 | `ElMessage.error` |
| 停止调度器 | POST | `/api/v1/report/scheduler/stop`，回退 `/api/report/scheduler/stop` | 同上 | `stopReportScheduler()` | 点击停止 | 无 | 页面消费 `response.data.message` | 同上 | `ElMessage.error` |
| 查询日志 | GET | `/api/v1/report/logs`，回退 `/api/report/logs` | 同上 | `getReportLogs(params)` | 页面初始化、日志筛选、实时监控、轮询 | `page/per_page/farm_code/report_type/status/start_date/end_date` | 页面预期 `response.data.logs` 和 `response.data.total` | `reportLogs`、`realtimeMonitorRows`、`shortTermStatus` | `ElMessage.error` |
| 创建配置 | POST | `/api/v1/report/configs`，回退 `/api/report/configs` | 同上 | `createReportConfig(payload)` | 新增配置保存 | `configForm` 加工后 payload | 页面消费 `createResp?.data?.config_id` | localStorage 元信息缓存 + 刷新配置列表 | `ElMessage.error` |
| 更新配置 | PUT | `/api/v1/report/configs/{id}`，回退 `/api/report/configs/{id}` | 同上 | `updateReportConfig(configId, payload)` | 编辑保存、切换启停 | `configId + payload` | 页面不深度消费返回 | 刷新配置 / 回滚状态 | `ElMessage.error` |
| 删除配置 | DELETE | `/api/v1/report/configs/{id}`，回退 `/api/report/configs/{id}` | 同上 | `deleteReportConfig(configId)` | 点击删除并确认 | URL `id` | 返回结构代码中未消费 | 刷新配置列表 + 删除本地 meta | `ElMessage.error` |
| 预览报文 | POST | `/api/v1/report/preview-report`，回退 `/api/report/preview-report` | 同上 | `previewReport(configId)` | 点击预览、手工工具生成文件 | `{ config_id }` | 页面预期 `response.data.config_info/payload/data/data_structure/data_summary` | `previewData`、`editableData`、手工文件生成 | `ElMessage.error` |
| 手工上报 | POST | `/api/v1/report/manual-report`，回退 `/api/report/manual-report` | 同上 | `manualReport(payload)` | 监控失败重试、预览弹窗提交、手工工具强推 | 常见 payload 为 `{ config_id }` 或 `{ config_id, data }` | 页面不深度消费返回 | 成功后刷新监控和日志 | `ElMessage.error` |
| 获取统计 | GET | `/api/v1/report/statistics`，回退 `/api/report/statistics` | 同上 | `getReportStatistics(params)` | 页面初始化、筛选统计 | `farm_code/month` 可选 | 页面预期 `today_stats/monthly_summary/daily_stats` | `dailyStats/monthlyStats/statistics` | `ElMessage.error` |

### 6.2 接口后的前端模板兜底

`previewReport()` 中，如果 `response.data.payload.data` 为空：

- `forecast_long` -> `generateLongForecastTemplate()`
- `forecast_short` -> `generateShortForecastTemplate()`
- `actual` -> `generateActualPowerTemplate()`
- `wind_speed` -> `generateWindSpeedTemplate()`
- `turbine_power` -> `generateTurbinePowerTemplate()`
- `weather` -> `generateWeatherTemplate()`
- `installed_capacity` -> `generateInstalledCapacityTemplate()`
- `available_capacity` -> `generateAvailableCapacityTemplate()`
- `theoretical_power` -> `generateTheoreticalPowerTemplate()`
- `available_power` -> `generateAvailablePowerTemplate()`

结论：

- 预览功能不是纯后端预览
- 页面内含大量 mock/template 兜底逻辑

---

## 7. 数据流说明

### 7.1 初始化加载流程

1. 页面进入
2. `onMounted` 执行：
   - `fetchFarms()`
   - 初始化默认场站到监控和手工工具
   - `fetchConfigs()`
   - `fetchLogs()`
   - `fetchSchedulerStatus()`
   - `fetchStatistics()`
   - `refreshRealtimeMonitor()`
3. 启动 `monitorTimer`，每 60 秒刷新实时监控
4. 注册 `ResizeObserver` 错误吞掉逻辑，并覆盖 `console.error`

### 7.2 用户操作后数据变化

#### 调度器

- 启动/停止 -> 调接口 -> 刷新状态

#### 统计

- 改场站/改月份/点查询 -> 调 `getReportStatistics` -> 更新汇总与日明细

#### 配置

- 新增/编辑 -> 调创建或更新接口 -> 刷新列表 -> 本地缓存敏感字段
- 启停 -> 调更新接口 -> 失败则回滚
- 删除 -> 调删除接口 -> 删除本地 meta -> 刷新列表

#### 日志

- 筛选/翻页/刷新 -> 调 `getReportLogs` -> 更新日志和 total
- 点详情 -> 打开详情弹窗

#### 实时监控

- 刷新/轮询 -> 调 `getReportLogs` 两次（短周期监控 + 08:00 长周期判断） -> 更新监控矩阵和 08:00 状态
- 失败重试 -> `manualReportApi` -> 成功后刷新监控和日志

#### 手工工具

- 生成文件 -> 查配置 -> 预览接口 -> 过滤日期 -> 转 CSV 文本
- 下载 -> 本地 Blob 下载
- 强推 -> `manualReportApi({ config_id, data })` -> 刷新监控和日志

### 7.3 哪些状态是本地状态

- 所有 loading
- 所有弹窗显隐
- `statsUpdatedAt`
- `statsConclusion`
- `editableData/allEditableData/showRawData`
- `manualGeneratedPayload/manualGeneratedText/manualGeneratedFilename`
- `realtimeMonitorRows/shortTermStatus`
- localStorage 元信息缓存

### 7.4 哪些数据来自后端接口

- 场站列表
- 配置列表
- 调度器状态
- 日志列表
- 统计汇总与日明细
- 预览原始 payload

### 7.5 哪些字段经过二次加工

- `statsConclusion`
- `reportConfigs` 与 localStorage 元信息合并
- `realtimeMonitorRows`
- `shortTermStatus`
- `editableDataJson`
- `manualGeneratedText`
- 预览模板数据
- `data_source` 自动修正逻辑

---

## 8. 权限与状态控制说明

### 8.1 权限控制

1. 路由级
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - `/reportmanagement`
  - `meta.requiredPermissions = ['manage_reports']`

2. 菜单级
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - `/reportmanagement` 菜单项条件：`hasPermission('manage_reports')`

3. 实际守卫
- `beforeEach` 仍然只校验登录态

4. 页面内部动作权限
- 代码中未发现“删除配置”“强制推送”“启动调度器”等细粒度权限控制

### 8.2 状态控制

- 多块独立 loading
- 实时监控有 60 秒轮询
- 预览编辑支持分页同步与 JSON 同步
- 配置启停失败有 UI 回滚

---

## 9. 风险点/待确认点

### 9.1 风险点

1. 页面过度集中，状态耦合重
- 配置、日志、预览、手工工具、监控都在一个组件内

2. 存在本地缓存与后端配置双源合并
- 容易出现“页面显示值”和“后端真实值”不一致

3. 预览为空时使用前端模板兜底
- 用户可能误以为是后端真实返回

4. 监控轮询只覆盖实时监控，不覆盖统计和调度器状态
- 页面不同区域实时性不一致

5. 覆盖 `console.error`
- 可能掩盖其他真实错误

6. 预览编辑逻辑复杂
- 涉及 JSON 编辑、分页同步、字段自动修正
- 容易出现提交内容与 UI 所见不一致

### 9.2 待确认点

- `getReportStatistics()` 的字段完整结构需结合后端确认
- `previewReportApi()` 返回的 `data_structure` / `supports_bulk_edit` 规则需结合后端确认
- `manualReportApi` 在 `{ config_id }` 与 `{ config_id, data }` 两种 payload 下的后端行为差异，需结合后端确认
- 本地缓存敏感字段（用户名/密码）是否符合安全要求，需结合安全审计确认
- 页面文案终端乱码不影响结构识别，但建议用编辑器核对中文展示

---

## 10. 代码证据清单

### 10.1 页面主文件

- [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)
  - `fetchFarms`
  - `fetchConfigs`
  - `fetchSchedulerStatus`
  - `startScheduler`
  - `stopScheduler`
  - `refreshSchedulerStatus`
  - `fetchLogs`
  - `showAddConfigDialog`
  - `editConfig`
  - `saveConfig`
  - `toggleConfig`
  - `deleteConfig`
  - `previewReport`
  - `fetchStatistics`
  - `refreshRealtimeMonitor`
  - `retryMonitorTask`
  - `resolveManualToolConfig`
  - `generateManualFile`
  - `downloadManualFile`
  - `forcePushManualFile`
  - `editableDataJson`
  - `updateEditableDataFromJson`
  - `onMounted`
  - `onUnmounted`

### 10.2 API 封装

- [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js)
  - `getReportFarms`
  - `getReportConfigs`
  - `getReportSchedulerStatus`
  - `startReportScheduler`
  - `stopReportScheduler`
  - `getReportLogs`
  - `createReportConfig`
  - `updateReportConfig`
  - `deleteReportConfig`
  - `previewReport`
  - `manualReport`
  - `getReportStatistics`

### 10.3 路由与权限

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - `/reportmanagement`
  - `meta.requiredPermissions = ['manage_reports']`
  - `beforeEach`
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - `/reportmanagement` 菜单
  - `hasPermission`

---

## 关键代码证据清单

- [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)
- [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)

## 可能遗漏点检查清单

- 本页模板生成函数较多，本次文档已确认其存在和用途，但未逐个展开每种模板的字段明细
- 预览弹窗内部表格列配置依赖 `previewData.data_structure.columns`，完整列 schema 需结合运行态或后端返回确认
- 终端乱码不影响函数、接口、状态流分析，但最终沉淀建议用编辑器复核中文文案
