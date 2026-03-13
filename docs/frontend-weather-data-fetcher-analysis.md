# 气象数据拉取页面代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 气象数据拉取 |
| 所属模块 | 数据交互 |
| 路由路径 | `/weatherdatafetcher` |
| 页面入口文件 | [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue) |
| 页面依赖的子组件列表 | 代码中未发现自定义业务子组件；仅使用 Element Plus 基础组件与图标 `UploadFilled` |
| 页面依赖的 store/hooks/model/service/api 文件 | [weatherFetchApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/weatherFetchApi.js)、[farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js)、[router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)、[AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) |
| 页面是否受权限控制 | 是。路由 `meta.requiredPermissions = ['manage_weather_data']`；侧边栏菜单通过 `hasPermission('manage_weather_data')` 控制显示；但全局路由守卫当前只校验登录态，代码中未发现按 `requiredPermissions` 强制拦截 |

### 1.2 页面定位

该页面是“气象数据采集运维控制台”，当前代码已经形成较完整的业务闭环，包含：

- 数据源连接配置（FTP/SFTP）
- 文件追踪任务配置
- 手动触发任务
- 任务启停
- 任务日志查看
- 调度器状态检查与重启
- 手动气象文件补录上传与解析
- 健康看板展示

### 1.3 关键事实

1. 页面核心逻辑集中在 [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue)。
2. 页面不使用 Vuex/Pinia，状态全部由本页 `ref/reactive/computed` 管理。
3. 健康看板不是独立接口直接返回，而是前端基于：
   - 连接状态
   - 调度器状态
   - 任务今日运行情况
   做二次计算。
4. 手动上传接口在 [weatherFetchApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/weatherFetchApi.js) 中存在兜底分支：
   - 优先 `/api/v1/weather-fetch/manual-upload`
   - 若失败且上传文件是 `.csv`，则 fallback 到 `/operational/api/upload_operational_csv`
5. 页面当前没有轮询或自动刷新，所有刷新都由用户操作触发。

---

## 2. 页面结构树

```text
气象数据拉取 WeatherDataFetcher.vue
├─ 页面头部
│  ├─ 标题
│  ├─ 描述
│  └─ 调度器状态更新时间
├─ 今日系统气象健康大盘
│  ├─ 刷新状态按钮
│  ├─ 重启调度器按钮
│  └─ 4 个健康节点
│     ├─ 通道状态
│     ├─ 定时任务状态
│     ├─ 今日数据到达率 dashboard
│     └─ 解析入库状态
├─ 手动气象数据补录
│  ├─ 打开上传弹窗按钮
│  └─ 上传结果告警条
├─ 数据源通道配置表
│  ├─ 新增连接按钮
│  └─ 连接表
│     ├─ 测试连接
│     ├─ 编辑
│     └─ 删除
├─ 文件追踪任务表
│  ├─ 创建任务按钮
│  └─ 任务表
│     ├─ 手动触发一次
│     ├─ 查看解析日志
│     ├─ 启用/停用
│     ├─ 编辑
│     └─ 删除
├─ 连接配置弹窗
├─ 任务配置弹窗
├─ 手动补录上传弹窗
└─ 任务日志弹窗
```

---

## 3. 区块说明

### 3.1 页面头部区

| 项目 | 说明 |
|---|---|
| 区块名称 | 页面头部区 |
| 对应组件名 | `WeatherDataFetcher` |
| 文件路径 | [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue) |
| 展示内容 | 页面标题、描述、调度器状态更新时间 |
| 数据来源 | 静态文案 + `schedulerCheckedAt` |
| 是否可交互 | 否 |
| 是否有权限控制 | 页面进入依赖路由与菜单权限；区块自身无额外权限 |
| 是否有定时刷新或自动更新 | 否，更新时间只在调用 `checkSchedulerStatus()` 成功后更新 |

### 3.2 健康大盘区

| 项目 | 说明 |
|---|---|
| 区块名称 | 今日系统气象健康大盘 |
| 对应组件名 | `WeatherDataFetcher` |
| 文件路径 | [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue) |
| 展示内容 | 通道状态、定时任务状态、今日数据到达率、解析入库状态 |
| 数据来源 | `connections`、`tasks`、`schedulerInfo` 通过 `healthBoard` 计算属性二次加工 |
| 是否可交互 | 是，按钮支持刷新状态和重启调度器 |
| 是否有权限控制 | 代码中未发现按钮级权限控制 |
| 是否有定时刷新或自动更新 | 否 |

关键事实：

- 健康大盘没有专门接口返回一份完整看板数据。
- `healthBoard` 通过前端计算得出：
  - `channel`
  - `scheduler`
  - `arrival`
  - `parse`

### 3.3 手动补录区

| 项目 | 说明 |
|---|---|
| 区块名称 | 手动气象数据补录区 |
| 对应组件名 | `WeatherDataFetcher` |
| 文件路径 | [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue) |
| 展示内容 | 打开手动上传弹窗按钮、上传结果提示 |
| 数据来源 | `manualUploadResult` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现按钮级权限控制 |
| 是否有定时刷新或自动更新 | 否 |

关键事实：

- 上传成功/警告/失败都通过 `manualUploadResult` + `ElMessage` 双重反馈。
- 页面文案明确写了支持 `.csv/.txt/.nc`。

### 3.4 数据源通道配置区

| 项目 | 说明 |
|---|---|
| 区块名称 | 数据源通道配置区 |
| 对应组件名 | `WeatherDataFetcher` |
| 文件路径 | [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue) |
| 展示内容 | 连接列表、协议、地址、端口、用户名、连接状态、测试/编辑/删除按钮 |
| 数据来源 | `connections`，由 `getWeatherConnections()` 返回并做最小映射 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现行级权限控制 |
| 是否有定时刷新或自动更新 | 否，靠手动触发 `fetchConnections()` 更新 |

### 3.5 文件追踪任务区

| 项目 | 说明 |
|---|---|
| 区块名称 | 文件追踪任务区 |
| 对应组件名 | `WeatherDataFetcher` |
| 文件路径 | [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue) |
| 展示内容 | 任务列表、今日状态、执行频率、最后执行时间、操作按钮 |
| 数据来源 | `tasks`，由 `getWeatherTasks()` 返回 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

关键事实：

- 今日状态标签不是接口原样文案唯一来源。
- `getTodayStatusTag(task)` 会优先读取后端给的 `today_status_text/business_status_text`，否则按 `task.status` 和 `task.enabled` 前端兜底生成文案。

### 3.6 连接配置弹窗

| 项目 | 说明 |
|---|---|
| 区块名称 | 连接配置弹窗 |
| 对应组件名 | `WeatherDataFetcher` |
| 文件路径 | [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue) |
| 展示内容 | 连接名称、场站、协议、地址、端口、用户名、认证方式、密码/密钥路径 |
| 数据来源 | `connectionForm` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

### 3.7 任务配置弹窗

| 项目 | 说明 |
|---|---|
| 区块名称 | 任务配置弹窗 |
| 对应组件名 | `WeatherDataFetcher` |
| 文件路径 | [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue) |
| 展示内容 | 任务名称、场站、连接、目录、文件匹配模板、频率、保存路径、超时、重试次数、描述 |
| 数据来源 | `taskForm`、`connections`、`farms` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

### 3.8 日志弹窗区

| 项目 | 说明 |
|---|---|
| 区块名称 | 任务日志弹窗 |
| 对应组件名 | `WeatherDataFetcher` |
| 文件路径 | [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue) |
| 展示内容 | 当前任务名、日志级别筛选、刷新按钮、日志列表 |
| 数据来源 | `currentTaskName`、`logLevel`、`taskLogs` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否，日志只在打开弹窗、切换级别、点击刷新时重新请求 |

---

## 4. 组件明细表

### 4.1 页面主组件 `WeatherDataFetcher`

| 项目 | 说明 |
|---|---|
| 组件名称 | `WeatherDataFetcher` |
| 文件路径 | [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue) |
| 父子关系 | 路由页面组件；代码中未发现自定义业务子组件 |
| props / emits / callbacks | 无 props / emits |
| 内部 state / computed / hooks / store 使用情况 | 使用 `ref/reactive/computed/onMounted`；无 Vuex/Pinia |
| 生命周期或副作用逻辑 | `onMounted` 并行拉取场站、连接、任务、调度器状态 |
| 实现的具体功能 | 连接 CRUD、任务 CRUD、任务执行、日志查看、调度器检查与重启、手动文件上传 |
| 触发了哪些接口 | `getWeatherConnections/getWeatherTasks/createWeatherConnection/updateWeatherConnection/testWeatherConnection/deleteWeatherConnection/runWeatherTask/toggleWeatherTask/createWeatherTask/updateWeatherTask/deleteWeatherTask/getWeatherTaskLogs/getWeatherSchedulerStatus/restartWeatherScheduler/uploadManualWeatherFile/getFarms` |
| 与其他组件的联动关系 | 无自定义子组件；多个弹窗与主表单、表格、健康看板相互联动 |
| 加载态 / 空态 / 异常态如何处理 | 通过多个 loading 状态、表格 `v-loading`、日志区 `v-loading`、`el-alert`、`el-empty`、`ElMessage` 实现 |

#### 4.1.1 内部状态

主要状态如下：

- 列表数据
  - `farms`
  - `connections`
  - `tasks`
  - `taskLogs`
- 加载态
  - `loadingConnections`
  - `loadingTasks`
  - `loadingLogs`
  - `savingConnection`
  - `savingTask`
  - `checkingScheduler`
  - `restartingScheduler`
  - `uploadingManual`
- 弹窗态
  - `showConnectionDialog`
  - `showTaskDialog`
  - `showLogsDialog`
  - `showManualUploadDialog`
- 编辑态
  - `editingConnection`
  - `editingTask`
- 表单 Ref
  - `connectionFormRef`
  - `taskFormRef`
  - `manualUploadFormRef`
- 当前日志上下文
  - `currentTaskId`
  - `currentTaskName`
  - `logLevel`
- 调度器状态
  - `schedulerInfo`
  - `schedulerCheckedAt`
- 表单模型
  - `connectionForm`
  - `taskForm`
  - `manualUploadForm`
  - `manualUploadFileList`
  - `manualUploadResult`

#### 4.1.2 表单校验规则

1. `connectionRules`
- 必填：
  - `name`
  - `farm_code`
  - `protocol`
  - `host`
  - `username`

2. `taskRules`
- 必填：
  - `name`
  - `farm_code`
  - `connection_id`
  - `remote_path`
  - `filename_template`
  - `save_path`

3. `manualUploadRules`
- 必填：
  - `farm_code`
  - `weather_type`
  - `file`

说明：

- 认证方式切换后，密码和密钥路径的显示靠 `v-if` 控制。
- 但 `connectionRules` 里没有针对 `password/private_key_path` 的条件式必填规则，代码中未发现更细校验。

#### 4.1.3 关键计算属性

`healthBoard`

数据来源：

- `connections`
- `tasks`
- `schedulerInfo`

计算内容：

1. `channel`
- 统计连接总数与 `status === 'connected'` 数量
- 全部连通才判定为 `ready`

2. `scheduler`
- 取 `schedulerInfo.is_running`

3. `arrival`
- 以任务的 `farm_code` 去重，统计站点总数
- 只要任务 `last_run` 是今天，且 `status` 在 `success/parsed/completed` 内，就记为“已就绪”
- 生成 `percent/ready/total/color/text`

4. `parse`
- 统计今日执行任务里解析成功的比例

关键结论：

- 健康看板是前端聚合结果，不是一个独立的后端看板接口返回。

#### 4.1.4 生命周期

`onMounted` 执行：

1. `Promise.all([fetchFarms(), fetchConnections(), fetchTasks(), checkSchedulerStatus()])`
2. 如果连接表单和任务表单默认未选场站，则设为第一个场站

代码中未发现：

- 轮询
- 自动刷新
- watcher
- route query 监听

#### 4.1.5 关键函数链路

1. `fetchFarms()`
- 调用 `getFarms()`
- 把通用场站结构映射成 `{ farm_code, farm_name }`
- 异常时静默设为空数组

2. `fetchConnections()`
- 调用 `getWeatherConnections()`
- 结果最少补充 `protocol: item.protocol || 'sftp'`

3. `fetchTasks()`
- 调用 `getWeatherTasks()`
- 结果补齐 `filename_template = item.filename_template || item.file_pattern`

4. `checkSchedulerStatus()`
- 调用 `getWeatherSchedulerStatus()`
- 成功后更新 `schedulerInfo` 和 `schedulerCheckedAt`
- 失败则把 `schedulerInfo` 重置为关闭态

5. `restartScheduler()`
- 弹确认框
- 调用 `restartWeatherScheduler()`
- 成功后再刷新调度器状态和任务列表

6. `saveConnection()`
- 表单校验
- 根据 `editingConnection` 决定 `create` 或 `update`
- 成功后关闭弹窗并刷新连接列表

7. `testConnection(row)`
- 调用 `testWeatherConnection(row.id)`
- 根据 `response.data.success` 更新 `row.status`

8. `saveTask()`
- 表单校验
- 把 UI 表单字段组装成后台 payload
- 成功后关闭弹窗并刷新任务列表

9. `runTask(row)`
- 调用 `runWeatherTask(row.id)`
- 成功后刷新任务列表

10. `toggleTask(row)`
- 调用 `toggleWeatherTask(row.id)`
- 成功后刷新任务列表

11. `viewTaskLogs(row)` / `fetchTaskLogs()`
- 打开日志弹窗
- 调用 `getWeatherTaskLogs(taskId, { level, per_page: 100 })`

12. `submitManualUpload()`
- 校验表单
- 组装 `FormData`
- 调用 `uploadManualWeatherFile(formData)`
- 根据响应中的 `warning/error/errors[0]` 判定是成功还是“上传成功但解析失败”
- 成功后刷新任务列表

#### 4.1.6 加载态 / 空态 / 异常态

- 加载态
  - 连接表：`loadingConnections`
  - 任务表：`loadingTasks`
  - 日志弹窗：`loadingLogs`
  - 按钮级 loading：保存、检查、重启、上传
- 空态
  - 日志为空时使用 `el-empty`
- 异常态
  - 统一通过 `extractErrorMessage(error, fallback)` 提取错误文案
  - 再通过 `ElMessage.error` 或 `ElMessage.warning` 反馈
- 上传结果态
  - `manualUploadResult` 同时驱动页面内 `el-alert`

### 4.2 子组件递归分析结论

代码中未发现自定义业务子组件，因此无需继续递归拆解。

本页引用的 `UploadFilled` 只是 Element Plus 图标组件，不承载业务逻辑。

---

## 5. 交互明细表

### 5.1 健康大盘区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 按钮 | 健康大盘头部 | 刷新状态 | 重新检查调度器状态 | 调用 `checkSchedulerStatus()` | 否 | 是，`getWeatherSchedulerStatus` | 影响 `schedulerInfo`、`schedulerCheckedAt`、`healthBoard` |
| 按钮 | 健康大盘头部 | 重启调度器 | 重启采集调度器 | 确认后调用 `restartScheduler()` | 否 | 是，`restartWeatherScheduler`，随后再次调用状态和任务接口 | 影响任务列表、健康看板 |
| 卡片/节点 | 健康大盘 | 通道状态/定时任务/到达率/解析入库 | 展示系统健康状态 | 只读 | 否 | 否 | 跟随 `healthBoard` 更新 |

### 5.2 手动补录区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 按钮 | 手动补录卡片头部 | 手动上传气象文件 | 打开补录上传弹窗 | 调用 `openManualUploadDialog()` | 否 | 否 | 影响上传弹窗 |
| 告警条 | 手动补录卡片 | 上传结果提示 | 展示最近一次上传结果 | 点击关闭仅清空 `manualUploadResult.message` | 否 | 否 | 否 |

### 5.3 连接配置表区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 按钮 | 连接表头部 | 添加连接 | 打开新增连接弹窗 | 调用 `openConnectionDialog()` | 否 | 否 | 影响连接弹窗 |
| 表格 | 连接配置区 | 连接列表 | 展示连接数据 | 只读展示 | 否 | 否 | 否 |
| 按钮 | 连接表操作列 | 测试连接 | 测试当前连接可达性 | 调用 `testConnection(scope.row)` | 否 | 是，`testWeatherConnection` | 更新当前行状态 |
| 按钮 | 连接表操作列 | 编辑 | 打开编辑连接弹窗 | 调用 `editConnection(scope.row)` | 否 | 否 | 影响连接弹窗 |
| 按钮 | 连接表操作列 | 删除 | 删除连接 | 确认后调用 `deleteConnection(scope.row)` | 否 | 是，`deleteWeatherConnection` | 刷新连接列表 |

### 5.4 任务表区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 按钮 | 任务表头部 | 创建任务 | 打开任务配置弹窗 | 调用 `openTaskDialog()` | 否 | 否 | 影响任务弹窗 |
| 表格 | 任务区 | 文件追踪列表 | 展示任务配置与状态 | 只读展示 | 否 | 否 | 否 |
| 标签 | 任务表今日状态列 | 今日状态 | 显示今日执行状态 | 由 `getTodayStatusTag(scope.row)` 生成 | 否 | 否 | 否 |
| 按钮 | 任务表操作列 | 手动触发一次 | 立即执行任务 | 调用 `runTask(scope.row)` | 否 | 是，`runWeatherTask` | 刷新任务列表、影响健康看板 |
| 按钮 | 任务表操作列 | 查看解析日志 | 打开日志弹窗 | 调用 `viewTaskLogs(scope.row)` | 否 | 是，`getWeatherTaskLogs` | 影响日志弹窗 |
| 按钮 | 任务表操作列 | 启用/停用 | 切换任务可用状态 | 调用 `toggleTask(scope.row)` | 否 | 是，`toggleWeatherTask` | 刷新任务列表、影响今日状态 |
| 按钮 | 任务表操作列 | 编辑 | 打开编辑弹窗 | 调用 `editTask(scope.row)` | 否 | 否 | 影响任务弹窗 |
| 按钮 | 任务表操作列 | 删除 | 删除任务 | 确认后调用 `deleteTask(scope.row)` | 否 | 是，`deleteWeatherTask` | 刷新任务列表 |

### 5.5 连接弹窗

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 输入框 | 连接弹窗 | 连接名称 | 输入连接名称 | 更新 `connectionForm.name` | 否 | 否 | 影响保存请求 |
| 下拉框 | 连接弹窗 | 归属场站 | 选择连接归属场站 | 更新 `connectionForm.farm_code` | 否 | 否 | 影响保存请求 |
| 单选组 | 连接弹窗 | 协议选择 | FTP/SFTP | 更新 `connectionForm.protocol` | 否 | 否 | 影响保存请求 |
| 输入框 | 连接弹窗 | 服务器地址 | 输入 host | 更新 `connectionForm.host` | 否 | 否 | 影响保存请求 |
| 数字输入框 | 连接弹窗 | 端口 | 输入 port | 更新 `connectionForm.port` | 否 | 否 | 影响保存请求 |
| 输入框 | 连接弹窗 | 用户名 | 输入 username | 更新 `connectionForm.username` | 否 | 否 | 影响保存请求 |
| 单选组 | 连接弹窗 | 认证方式 | 密码/密钥认证 | 更新 `connectionForm.auth_type` | 否 | 否 | 影响条件渲染字段 |
| 输入框 | 连接弹窗 | 密码 | 密码输入 | 仅 `auth_type=password` 时显示 | 否 | 否 | 影响保存请求 |
| 输入框 | 连接弹窗 | 私钥路径 | 输入密钥路径 | 仅 `auth_type=key` 时显示 | 否 | 否 | 影响保存请求 |
| 输入框 | 连接弹窗 | 私钥密码 | 输入 passphrase | 仅 `auth_type=key` 时显示 | 否 | 否 | 影响保存请求 |
| 按钮 | 连接弹窗页脚 | 保存 | 保存连接配置 | 调用 `saveConnection()` | 否 | 是，`createWeatherConnection` 或 `updateWeatherConnection` | 关闭弹窗并刷新连接表 |

### 5.6 任务弹窗

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 输入框 | 任务弹窗 | 任务名称 | 输入任务名 | 更新 `taskForm.name` | 否 | 否 | 影响保存请求 |
| 下拉框 | 任务弹窗 | 归属场站 | 选择场站 | 更新 `taskForm.farm_code` | 否 | 否 | 影响保存请求 |
| 下拉框 | 任务弹窗 | 数据源通道 | 选择连接 | 更新 `taskForm.connection_id` | 否 | 否 | 影响保存请求 |
| 输入框 | 任务弹窗 | 远程目录路径 | 输入目录 | 更新 `taskForm.remote_path` | 否 | 否 | 影响保存请求 |
| 输入框 | 任务弹窗 | 文件名动态匹配模板 | 输入匹配规则 | 更新 `taskForm.filename_template` | 否 | 否 | 影响保存请求 |
| 下拉框 | 任务弹窗 | 执行频率 | 选择 cron 模板 | 更新 `taskForm.schedule` | 否 | 否 | 影响条件渲染与保存 payload |
| 输入框 | 任务弹窗 | Cron表达式 | 自定义 cron | 仅 `schedule=custom` 显示 | 否 | 否 | 影响保存 payload |
| 输入框 | 任务弹窗 | 本地保存路径 | 输入目录 | 更新 `taskForm.save_path` | 否 | 否 | 影响保存请求 |
| 数字输入框 | 任务弹窗 | 超时时间 | 输入秒数 | 更新 `taskForm.timeout` | 否 | 否 | 影响保存请求 |
| 数字输入框 | 任务弹窗 | 重试次数 | 输入次数 | 更新 `taskForm.retry_count` | 否 | 否 | 影响保存请求 |
| 文本域 | 任务弹窗 | 任务描述 | 输入描述 | 更新 `taskForm.description` | 否 | 否 | 影响保存请求 |
| 按钮 | 任务弹窗页脚 | 保存 | 保存任务配置 | 调用 `saveTask()` | 否 | 是，`createWeatherTask` 或 `updateWeatherTask` | 关闭弹窗并刷新任务表 |

### 5.7 手动上传弹窗

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 下拉框 | 上传弹窗 | 归属场站 | 选择补录目标场站 | 更新 `manualUploadForm.farm_code` | 否 | 否 | 影响上传参数 |
| 下拉框 | 上传弹窗 | 气象类型 | 选择 `nwp/mast/typhoon/other` | 更新 `manualUploadForm.weather_type` | 否 | 否 | 影响上传参数 |
| 上传控件 | 上传弹窗 | 上传文件 | 选择文件 | `handleManualFileChange/Remove` 更新 `manualUploadForm.file` 与 `manualUploadFileList` | 否 | 否 | 影响上传参数 |
| 按钮 | 上传弹窗页脚 | 上传并解析 | 上传文件并触发解析 | 调用 `submitManualUpload()` | 否 | 是，`uploadManualWeatherFile` | 更新上传结果提示并刷新任务表 |

### 5.8 日志弹窗

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 下拉框 | 日志弹窗 | 全部/信息/成功/警告/错误 | 按级别筛选日志 | `@change="fetchTaskLogs"` | 否 | 是，`getWeatherTaskLogs` | 更新日志列表 |
| 按钮 | 日志弹窗 | 刷新 | 重新拉取当前日志 | 调用 `fetchTaskLogs()` | 否 | 是 | 更新日志列表 |
| 日志列表 | 日志弹窗 | 日志项 | 展示日志级别、时间、消息、详情 | 只读 | 否 | 否 | 否 |

---

## 6. 接口明细表

### 6.1 页面直接使用的接口

| 接口名称 | 请求方法 | URL | 所在 api/service 文件 | 调用函数名 | 调用触发条件 | 请求参数 | 返回数据结构 | 返回数据映射位置 | 失败时页面处理 |
|---|---|---|---|---|---|---|---|---|---|
| 获取连接列表 | GET | `/api/v1/weather-fetch/connections`，回退 `/api/weather-fetch/connections` | [weatherFetchApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/weatherFetchApi.js) | `getWeatherConnections()` | 页面初始化、保存连接后、删除连接后 | 无 | 页面按 `response.data || []` 读取，预期每项含 `id/name/farm_code/protocol/host/port/username/status/...`；完整字段代码中未明确 | 映射到 `connections` | `ElMessage.error('获取连接列表失败')` |
| 创建连接 | POST | `/api/v1/weather-fetch/connections`，回退 `/api/weather-fetch/connections` | 同上 | `createWeatherConnection(payload)` | 新增连接弹窗保存 | `connectionForm` 拷贝 | 返回结构代码中未消费 | 成功后仅提示并刷新列表 | `ElMessage.error('保存连接失败')` |
| 更新连接 | PUT | `/api/v1/weather-fetch/connections/{id}`，回退 `/api/weather-fetch/connections/{id}` | 同上 | `updateWeatherConnection(connectionId, payload)` | 编辑连接弹窗保存 | `connectionForm.id + payload` | 返回结构代码中未消费 | 成功后仅提示并刷新列表 | 同上 |
| 测试连接 | POST | `/api/v1/weather-fetch/connections/{id}/test`，回退 `/api/weather-fetch/connections/{id}/test` | 同上 | `testWeatherConnection(connectionId)` | 点击“测试连接” | URL 路径 `id` | 页面只消费 `response?.data?.success` 布尔值 | 更新当前行 `row.status` | 失败置为 `disconnected` 并 `ElMessage.error` |
| 删除连接 | DELETE | `/api/v1/weather-fetch/connections/{id}`，回退 `/api/weather-fetch/connections/{id}` | 同上 | `deleteWeatherConnection(connectionId)` | 点击删除并确认 | URL 路径 `id` | 代码中未消费返回 | 成功后刷新连接列表 | `ElMessage.error('删除连接失败')` |
| 获取任务列表 | GET | `/api/v1/weather-fetch/tasks`，回退 `/api/weather-fetch/tasks` | 同上 | `getWeatherTasks()` | 页面初始化、创建/更新/删除/触发/切换任务后 | 无 | 页面按 `response.data || []` 读取，预期每项含 `id/name/farm_code/connection_id/connection_name/file_pattern/filename_template/schedule/last_run/status/enabled/...`；完整字段代码中未明确 | 映射到 `tasks`，并补齐 `filename_template` | `ElMessage.error('获取任务列表失败')` |
| 创建任务 | POST | `/api/v1/weather-fetch/tasks`，回退 `/api/weather-fetch/tasks` | 同上 | `createWeatherTask(payload)` | 新增任务弹窗保存 | 页面组装后的 `payload` | 返回结构代码中未消费 | 成功后刷新任务列表 | `ElMessage.error('保存任务失败')` |
| 更新任务 | PUT | `/api/v1/weather-fetch/tasks/{id}`，回退 `/api/weather-fetch/tasks/{id}` | 同上 | `updateWeatherTask(taskId, payload)` | 编辑任务弹窗保存 | `taskForm.id + payload` | 返回结构代码中未消费 | 成功后刷新任务列表 | 同上 |
| 手动触发任务 | POST | `/api/v1/weather-fetch/tasks/{id}/run`，回退 `/api/weather-fetch/tasks/{id}/run` | 同上 | `runWeatherTask(taskId)` | 点击“手动触发一次” | URL 路径 `id` | 返回结构代码中未消费 | 成功后刷新任务列表 | `ElMessage.error('触发任务失败')` |
| 启停任务 | POST | `/api/v1/weather-fetch/tasks/{id}/toggle`，回退 `/api/weather-fetch/tasks/{id}/toggle` | 同上 | `toggleWeatherTask(taskId)` | 点击“启用/停用” | URL 路径 `id` | 返回结构代码中未消费 | 成功后刷新任务列表 | `ElMessage.error('切换任务状态失败')` |
| 删除任务 | DELETE | `/api/v1/weather-fetch/tasks/{id}`，回退 `/api/weather-fetch/tasks/{id}` | 同上 | `deleteWeatherTask(taskId)` | 点击删除并确认 | URL 路径 `id` | 返回结构代码中未消费 | 成功后刷新任务列表 | `ElMessage.error('删除任务失败')` |
| 获取任务日志 | GET | `/api/v1/weather-fetch/tasks/{id}/logs`，回退 `/api/weather-fetch/tasks/{id}/logs` | 同上 | `getWeatherTaskLogs(taskId, params)` | 打开日志弹窗、切换日志级别、点击刷新 | `{ level?, per_page: 100 }` | 页面消费 `response?.data?.logs || []`；每项预期含 `id/level/created_at/message/details` | 映射到 `taskLogs` | 失败清空日志并 `ElMessage.error('获取日志失败')` |
| 获取调度器状态 | GET | `/api/v1/weather-fetch/scheduler/status`，回退 `/api/weather-fetch/scheduler/status` | 同上 | `getWeatherSchedulerStatus()` | 页面初始化、点击“刷新状态”、重启调度器后 | 无 | 页面消费 `response.data`，预期至少含 `is_running/jobs/total_jobs` | 映射到 `schedulerInfo`，进而驱动 `healthBoard` | 失败时重置为关闭态并 `ElMessage.error` |
| 重启调度器 | POST | `/api/v1/weather-fetch/scheduler/restart`，回退 `/api/weather-fetch/scheduler/restart` | 同上 | `restartWeatherScheduler()` | 点击“重启调度器”并确认 | 无 | 返回结构代码中未消费 | 成功后刷新调度器状态和任务列表 | `ElMessage.error('重启调度器失败')` |
| 手动上传气象文件 | POST | `/api/v1/weather-fetch/manual-upload`，回退 `/api/weather-fetch/manual-upload` | 同上 | `uploadManualWeatherFile(formData)` | 点击“上传并解析” | `FormData(file, farm_code, weather_type)` | 页面消费 `response?.data` 中的 `warning/error/errors[0]/message` | 映射到 `manualUploadResult`；成功/警告后刷新任务表 | 失败时 `manualUploadResult.type='error'` 并 `ElMessage.error` |
| 获取场站列表 | GET | `/api/v1/farms`，回退 `/api/farms` | [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js) | `getFarms()` | 页面初始化 | 无 | 页面预期数组项含 `farm_code/farm_name` 或 `code/name/id` | 映射到 `farms` 下拉列表 | 失败时静默置空数组 |

### 6.2 上传接口的隐性兜底逻辑

`uploadManualWeatherFile(formData)` 还包含一个重要 fallback：

1. 先尝试：
- `/api/v1/weather-fetch/manual-upload`
- 或旧路径 `/api/weather-fetch/manual-upload`

2. 如果失败，且上传文件扩展名是 `.csv`
- 会重新构造 `fallbackData`
- 并调用：
  - `POST /operational/api/upload_operational_csv`
- 额外附带：
  - `farm_code`
  - `table_name = 'weather_data'`

关键结论：

- 手动 CSV 上传存在与“运营 CSV 上传接口”的兼容通道。
- 页面层并不知道最终走的是哪一条后端链路。

### 6.3 页面组装任务保存 payload 的规则

`saveTask()` 把 UI 表单转成后端 payload 时会追加以下字段：

- `file_pattern = taskForm.filename_template`
- `schedule = taskForm.schedule === 'custom' ? taskForm.custom_schedule : taskForm.schedule`
- `path_pattern = 'custom'`
- `custom_path_pattern = 'manual-template'`
- `time_strategy = 'latest'`
- `processing_options = ['integrity_check']`
- `deduplication_options = ['skip_existing']`
- `target_table = 'weather_data_records'`

这说明：

- 页面不是原样提交用户所见字段
- 而是前端内置了任务处理策略默认值

---

## 7. 数据流说明

### 7.1 初始化加载流程

1. 进入 `/weatherdatafetcher`
2. `onMounted` 触发并行请求：
   - `fetchFarms()`
   - `fetchConnections()`
   - `fetchTasks()`
   - `checkSchedulerStatus()`
3. 返回后：
   - 生成 `farms`
   - 生成 `connections`
   - 生成 `tasks`
   - 生成 `schedulerInfo`
4. 若连接表单和任务表单未设置默认场站：
   - 自动赋值为 `farms[0]?.farm_code`
5. `healthBoard` 计算属性自动基于连接、任务、调度器状态重新计算

### 7.2 用户操作后数据如何变化

#### 7.2.1 新增/编辑连接

1. 打开连接弹窗
2. 修改 `connectionForm`
3. 点击保存
4. 表单校验通过后调创建或更新接口
5. 成功后关闭弹窗并刷新连接列表
6. 连接列表变化会影响：
   - 健康看板 `channel`
   - 任务弹窗中的连接下拉

#### 7.2.2 测试连接

1. 点击“测试连接”
2. 当前行 `row.testing = true`
3. 调接口测试
4. 成功则 `row.status = connected`
5. 失败则 `row.status = disconnected`
6. 连接状态变化会影响健康看板 `channel`

#### 7.2.3 新增/编辑任务

1. 打开任务弹窗
2. 修改 `taskForm`
3. 点击保存
4. 前端组装额外策略字段
5. 调创建或更新任务接口
6. 成功后刷新任务列表
7. 任务列表变化会影响：
   - 健康看板 `arrival`
   - 健康看板 `parse`
   - 任务表展示

#### 7.2.4 手动触发任务

1. 点击“手动触发一次”
2. 当前行 `row.running = true`
3. 调 `runWeatherTask`
4. 成功后刷新任务列表
5. 今日状态和最后执行时间可能随之变化

#### 7.2.5 启停任务

1. 点击“启用/停用”
2. 调 `toggleWeatherTask`
3. 成功后刷新任务列表
4. `getTodayStatusTag()` 结果可能变化

#### 7.2.6 查看日志

1. 点击“查看解析日志”
2. 记录 `currentTaskId/currentTaskName`
3. 打开日志弹窗
4. 请求日志
5. 根据 `logLevel` 或刷新按钮重新请求

#### 7.2.7 刷新/重启调度器

1. 刷新状态
   - 只更新 `schedulerInfo` 和 `schedulerCheckedAt`
2. 重启调度器
   - 先确认
   - 再调重启接口
   - 成功后重新拉状态和任务

#### 7.2.8 手动上传补录

1. 打开上传弹窗
2. 选择场站、气象类型、文件
3. 点击“上传并解析”
4. 表单校验通过后构造 `FormData`
5. 调上传接口
6. 根据后端 `warning/error/message`：
   - 设为 `success`
   - 或 `warning`
   - 或 `error`
7. 成功/警告后关闭弹窗并刷新任务表

### 7.3 哪些状态是本地状态

- 所有 loading 状态
- 所有弹窗显隐
- 所有表单数据
- `taskLogs`
- `manualUploadResult`
- `currentTaskId/currentTaskName/logLevel`
- `schedulerCheckedAt`

### 7.4 哪些状态来自全局 store

代码中未发现 Vuex/Pinia。

### 7.5 哪些数据来自后端接口

- 场站列表
- 连接列表
- 任务列表
- 调度器状态
- 任务日志
- 上传解析结果

### 7.6 哪些字段经过二次加工/格式化

前端二次加工包括：

- `farms` 统一映射成 `{ farm_code, farm_name }`
- `connections` 补默认 `protocol`
- `tasks` 补 `filename_template`
- `healthBoard`
- `schedulerCheckedAt` 格式化
- `formatDateTime`
- `getTodayStatusTag`
- `getScheduleDescription`
- `manualUploadResult`
- 任务保存请求 payload 的策略字段补全

---

## 8. 权限与状态控制说明

### 8.1 权限控制

1. 路由级
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - `/weatherdatafetcher`
  - `meta.requiredPermissions = ['manage_weather_data']`

2. 菜单级
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - `/weatherdatafetcher` 菜单条件：`hasPermission('manage_weather_data')`

3. 实际路由守卫
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js) `beforeEach`
  - 当前只校验登录态
  - 代码中未发现按 `requiredPermissions` 拦截

4. 页面内部权限
- 页面中所有按钮都未发现细粒度权限显隐
- 例如“删除连接”“重启调度器”“上传补录”没有单独权限判断

### 8.2 状态控制

1. 表格级 loading
- 连接表 `loadingConnections`
- 任务表 `loadingTasks`

2. 按钮级 loading
- `savingConnection`
- `savingTask`
- `checkingScheduler`
- `restartingScheduler`
- `uploadingManual`
- 行级 `row.testing`
- 行级 `row.running`

3. 表单校验
- 连接、任务、上传都有规则校验

4. 危险操作确认
- 删除连接、删除任务、重启调度器使用 `ElMessageBox.confirm`

---

## 9. 风险点/待确认点

### 9.1 风险点

1. 页面无自动刷新
- 任务和调度器状态不会自动更新
- 用户看到的健康看板可能滞后

2. 调度器状态更新时间是前端检查时间，不一定是后端状态产生时间
- `schedulerCheckedAt` 记录的是前端成功请求时刻

3. 任务保存 payload 有较多前端写死策略
- `path_pattern/custom_path_pattern/time_strategy/processing_options/deduplication_options/target_table`
- 若后端策略调整，前端可能与后端配置口径脱节

4. 上传 fallback 路径存在双后端链路
- 既可能走 `weather-fetch/manual-upload`
- 也可能走 `operational/api/upload_operational_csv`
- 审计时需要明确最终是哪个链路生效

5. 连接认证字段校验不够细
- 代码中未发现根据认证方式动态约束密码或私钥路径必填

6. 场站获取失败时静默为空
- `fetchFarms()` 异常没有提示
- 会导致多个弹窗场站下拉为空，用户只能看到后续校验失败

### 9.2 待确认点

- `getWeatherConnections/getWeatherTasks/getWeatherSchedulerStatus/getWeatherTaskLogs` 的完整返回字段需结合后端确认
- `task.status` 可用值集合代码中未完整定义，`getTodayStatusTag()` 只覆盖了部分情况
- 上传成功但解析失败时，后端 `warning/error/errors` 的结构需结合后端确认
- 是否需要为“重启调度器”“删除任务”“删除连接”补充更细权限控制，需结合权限设计确认
- 页面中文文案在终端中部分乱码，需结合编辑器核对实际显示内容

---

## 10. 代码证据清单

### 10.1 页面主文件

- [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue)
  - `extractErrorMessage`
  - `connectionRules`
  - `taskRules`
  - `manualUploadRules`
  - `healthBoard`
  - `formatDateTime`
  - `getTodayStatusTag`
  - `getScheduleDescription`
  - `fetchFarms`
  - `fetchConnections`
  - `fetchTasks`
  - `checkSchedulerStatus`
  - `restartScheduler`
  - `openConnectionDialog`
  - `editConnection`
  - `saveConnection`
  - `deleteConnection`
  - `testConnection`
  - `openTaskDialog`
  - `editTask`
  - `saveTask`
  - `deleteTask`
  - `runTask`
  - `toggleTask`
  - `viewTaskLogs`
  - `fetchTaskLogs`
  - `openManualUploadDialog`
  - `handleManualFileChange`
  - `handleManualFileRemove`
  - `submitManualUpload`
  - `onMounted`

### 10.2 API 封装

- [weatherFetchApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/weatherFetchApi.js)
  - `getWeatherConnections`
  - `getWeatherTasks`
  - `createWeatherConnection`
  - `updateWeatherConnection`
  - `testWeatherConnection`
  - `deleteWeatherConnection`
  - `runWeatherTask`
  - `createWeatherTask`
  - `updateWeatherTask`
  - `toggleWeatherTask`
  - `deleteWeatherTask`
  - `getWeatherTaskLogs`
  - `getWeatherSchedulerStatus`
  - `restartWeatherScheduler`
  - `uploadManualWeatherFile`

### 10.3 场站数据来源

- [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js)
  - `getFarms`

### 10.4 路由与权限

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - `/weatherdatafetcher` 路由
  - `meta.requiredPermissions = ['manage_weather_data']`
  - `beforeEach`
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - `/weatherdatafetcher` 菜单显隐
  - `hasPermission`

---

## 关键代码证据清单

- [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue)
- [weatherFetchApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/weatherFetchApi.js)
- [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)

## 可能遗漏点检查清单

- 页面当前没有自动刷新，如需确认真实运行表现，后续可结合运行态再验证
- 任务和连接返回结构是根据页面消费字段推断的，完整 schema 需结合后端确认
- 上传 fallback 到 `/operational/api/upload_operational_csv` 的后端返回格式需要进一步确认
- 文案终端乱码不影响结构、函数、接口和状态流识别，但最终 Wiki 文案建议用编辑器复核
