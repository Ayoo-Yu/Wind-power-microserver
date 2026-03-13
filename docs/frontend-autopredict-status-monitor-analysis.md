# 状态监控页面代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 状态监控 |
| 所属模块 | 预测与控制 |
| 路由路径 | `/autopredict` |
| 页面入口文件 | [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue) |
| 页面依赖的子组件 | [StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue)、[SparklineMini.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/SparklineMini.vue) |
| 页面依赖的 store/hooks/model/service/api 文件 | [autopredictApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/autopredictApi.js)、[farmService.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/farmService.js)、[router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)、[AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)、[farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js) |
| 页面是否受权限控制 | 是。路由 `meta.requiredPermissions = ['auto_predictions']`；侧边栏菜单通过 `hasPermission('auto_predictions')` 控制显示；但全局路由守卫当前只校验登录态，代码中未发现按 `requiredPermissions` 做强制拦截 |

### 1.2 页面定位

该页面不是单纯的状态展示页，而是“自动预测运行控制台”。从代码实现看，它同时承担以下职责：

- 单场站维度的预测任务启停控制
- 多场站维度的业务状态矩阵监控
- 批量启停/批量删除
- 日志查看
- 失败场站明细查看与导出
- 与“功率可视化对比”“上报配置与调度”页面之间的跳转联动

### 1.3 关键事实

1. 页面真实接口主要集中在 [autopredictApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/autopredictApi.js)。
2. 页面共享的场站上下文由 [farmService.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/farmService.js) 管理，而不是 Vuex/Pinia。
3. 页面存在 60 秒轮询和 1 秒倒计时刷新。
4. 页面中的“趋势预览 Sparkline”“执行耗时”“下次执行倒计时”“部分运行指标”不是后端原始返回，而是前端本地计算或模拟生成。
5. 页面注释中明确写出若干历史功能已移除，包括“定时重启设置”“脚本详情”“任务历史”“状态详情”等。

---

## 2. 页面结构树

```text
状态监控 AutoPredict.vue
├─ 页面容器
│  ├─ loading 遮罩
│  ├─ 页面标题
├─ 预测类型运行矩阵
│  └─ el-table
│     ├─ 预测类型列
│     ├─ 状态列 -> StatusDot
│     ├─ 启停列 -> el-switch
│     └─ 趋势预览列 -> SparklineMini
├─ 多场站业务状态监控矩阵
│  ├─ 降级策略说明
│  ├─ 场站筛选 el-select
│  ├─ 批量类型筛选 el-checkbox-group
│  ├─ 批量动作按钮
│  └─ el-table
│     ├─ 选择列
│     ├─ 场站名称列
│     ├─ NWP 状态列
│     ├─ 超短期状态列
│     ├─ 短期状态列
│     ├─ 中期状态列
│     └─ 操作列
│        ├─ 查看当前曲线
│        └─ 人工修正
├─ 三张预测卡片（supershort / short / medium）
│  ├─ 卡片头
│  │  ├─ 标题
│  │  ├─ 运行状态 -> StatusDot
│  │  ├─ 全局启停开关
│  │  └─ 下拉菜单
│  ├─ 指标区
│  │  ├─ 上次执行时间
│  │  ├─ 执行耗时
│  │  ├─ 预计下次执行
│  │  └─ 场站聚合状态
│  ├─ 倒计时区
│  ├─ 降级告警区
│  └─ 底部查看日志按钮
├─ 弹窗区
│  ├─ 操作确认弹窗
│  ├─ 脚本日志弹窗
│  ├─ 错误详情弹窗
│  ├─ 批量操作结果弹窗
│  └─ 失败场站明细弹窗
└─ 页面副作用
   ├─ onMounted 初始化加载
   ├─ farmService 场站变化监听
   ├─ 60 秒轮询刷新
   ├─ 1 秒倒计时刷新
   └─ onUnmounted 清理定时器与监听器
```

---

## 3. 区块说明

### 3.1 页面容器区

| 项目 | 说明 |
|---|---|
| 区块名称 | 页面容器区 |
| 对应组件名 | `AutoPredict` |
| 文件路径 | [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue) |
| 展示内容 | 整页背景、标题、加载遮罩 |
| 数据来源 | `loading`、`isAnimatedBackground` |
| 是否可交互 | 否 |
| 是否有权限控制 | 页面进入依赖路由与菜单权限；区块本身无额外按钮级权限 |
| 是否有定时刷新或自动更新 | 容器样式受 `inject('isAnimatedBackground')` 影响，`loading` 会随请求变化 |

补充说明：

- 容器通过 `v-loading="loading"` 显示全页遮罩。
- 背景动画开关来自父级布局 [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 的 `provide('isAnimatedBackground', isAnimatedBackground)`。

### 3.2 预测类型运行矩阵

| 项目 | 说明 |
|---|---|
| 区块名称 | 预测类型运行矩阵 |
| 对应组件名 | `AutoPredict` + `StatusDot` + `SparklineMini` |
| 文件路径 | [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)、[StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue)、[SparklineMini.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/SparklineMini.vue) |
| 展示内容 | 三类预测类型的名称、当前启停状态、启停开关、趋势预览 |
| 数据来源 | `predictions` 本地配置数组 + `fetchStatus()` 返回的状态值 + `predictionTableRows` 前端生成的趋势数组 |
| 是否可交互 | 是，启停开关可操作 |
| 是否有权限控制 | 代码中未发现区块内按钮级权限控制 |
| 是否有定时刷新或自动更新 | 是。状态受初始化加载、场站切换、60 秒轮询、控制成功后 1 秒延迟刷新影响 |

关键事实：

- 表格中的 `title/name` 来自页面本地 `predictions`。
- `row.status` 来自 `getAutoPredictStatus(currentFarm)` 返回结果映射到 `predictions[i].status`。
- `row.trend` 不是接口字段，而是 `predictionTableRows` 中根据索引和状态拼出的固定数列，用于驱动 `SparklineMini`。

### 3.3 多场站业务状态监控矩阵

| 项目 | 说明 |
|---|---|
| 区块名称 | 多场站业务状态监控矩阵 |
| 对应组件名 | `AutoPredict` |
| 文件路径 | [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue) |
| 展示内容 | 多场站 NWP 状态、超短期/短期/中期状态、批量选择与批量控制、曲线查看/人工修正跳转 |
| 数据来源 | `fetchFleetStatus()` 返回的 `fleetStatus`；再由 `fleetMatrixRows` 进行前端二次归一化 |
| 是否可交互 | 是 |
| 是否有权限控制 | 菜单与路由受控；区块内按钮代码中未发现单独权限判断 |
| 是否有定时刷新或自动更新 | 是。初始化、场站变化、60 秒轮询、批量控制成功后会刷新 |

关键事实：

- 页面优先请求 `getAutoPredictOverview()`，失败时降级调用 `getAutoPredictStatusAll()`。
- `fleetMatrixRows` 会对每个场站的 NWP 状态和三类预测状态做二次加工。
- 当 NWP 状态被识别为失败时，超短期状态会被前端强制覆盖成失败文案 `NWP缺失`，这是前端业务规则，不一定等于后端原始状态。

### 3.4 预测卡片区

| 项目 | 说明 |
|---|---|
| 区块名称 | 预测卡片区 |
| 对应组件名 | `AutoPredict` + `StatusDot` |
| 文件路径 | [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)、[StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue) |
| 展示内容 | 三类预测的卡片式总览、全局开关、更多菜单、聚合指标、倒计时、降级提示、日志入口 |
| 数据来源 | `predictions`、`globalPredictStatus`、`aggregateByTypeMap`、`getPredictMetrics()` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现按钮级权限控制 |
| 是否有定时刷新或自动更新 | 是。`nowTick` 每秒更新一次，驱动倒计时与进度条；轮询刷新会影响状态与聚合统计 |

关键事实：

- 卡片运行状态 `globalPredictStatus` 不是接口直接返回，而是根据 `fleetStatus` 中同类型任务是否有任一场站为活动状态来聚合。
- `lastRun` 使用 `statusUpdatedAt` 本地时间戳格式化得出，不是后端任务真实开始时间。
- `duration` 是根据预测类型名称长度构造的演示值，不是后端真实执行耗时。
- `nextRun` 和倒计时完全由 `predictionCycleMap` + 当前时间计算，不是后端调度中心返回值。

### 3.5 日志弹窗区

| 项目 | 说明 |
|---|---|
| 区块名称 | 脚本日志弹窗 |
| 对应组件名 | `AutoPredict` |
| 文件路径 | [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue) |
| 展示内容 | 日志类型筛选、日期筛选、日志文本内容 |
| 数据来源 | `getAutoPredictLogs()` 返回结果 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现弹窗级权限判断 |
| 是否有定时刷新或自动更新 | 否，只有点击“查询/刷新/切换日志类型/重置”时触发请求 |

补充说明：

- 日志类型选项根据 `currentPrediction` 动态变化。
- 超短期支持 `train`、`predict` 两类；短期和中期仅显示 `train`。
- 日期默认取当天并格式化为 `YYYYMMDD`。

### 3.6 操作确认与错误反馈区

| 项目 | 说明 |
|---|---|
| 区块名称 | 确认/错误反馈区 |
| 对应组件名 | `AutoPredict` |
| 文件路径 | [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue) |
| 展示内容 | 操作确认弹窗、错误详情弹窗、批量结果弹窗、失败场站弹窗 |
| 数据来源 | `confirmDialog`、`errorDetails`、`batchResult`、`failedStationsMap` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

---

## 4. 组件明细表

### 4.1 页面主组件 `AutoPredict`

| 项目 | 说明 |
|---|---|
| 组件名称 | `AutoPredict` |
| 文件路径 | [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue) |
| 父子关系 | 父级为路由页面；子组件为 `StatusDot`、`SparklineMini` |
| props / emits / callbacks | `script setup` 页面组件，无 props / emits；接收的外部回调来自 `farmService.addListener(handleFarmChanged)` |
| 内部 state / computed / hooks / store 使用情况 | 使用大量 `ref/reactive/computed`；使用 `inject('isAnimatedBackground')`；使用 `useRouter()`；使用 `farmService` 单例 |
| 生命周期或副作用逻辑 | `onMounted` 初始化场站、状态、矩阵、轮询、倒计时；`onUnmounted` 清理监听器与定时器 |
| 实现的具体功能 | 状态展示、单项启停、全局启停、矩阵批量控制、日志查看、失败场站查看、结果导出、跨页面跳转 |
| 触发了哪些接口 | `getAutoPredictStatus`、`getAutoPredictOverview`、`getAutoPredictStatusAll`、`controlAutoPredict`、`controlAutoPredictMatrix`、`getAutoPredictLogs`；初始化前还间接触发 `farmService.loadAvailableFarms()`，从而调用 `getAutoPredictFarms/getReportFarms/getFarms` |
| 与其他组件的联动关系 | 场站切换会影响本页所有查询；点击“查看当前曲线”跳转 `PowerCompare`；点击“人工修正”跳转 `ReportManagement`；日志/失败数/批量结果通过弹窗联动 |
| 加载态 / 空态 / 异常态如何处理 | 使用整页 `v-loading` 和 `fleetLoading`；日志默认文案为“暂无日志信息”；接口异常多数 `console.error`，部分操作通过错误弹窗或消息提示反馈；代码中未发现专门空态组件 |

#### 4.1.1 关键本地状态

主要本地状态如下：

- `predictions`
  - 页面内三类预测的本地配置数组
  - 包含 `name/title/status`
- `loading`
  - 全页请求遮罩
- `fleetLoading`
  - 业务状态矩阵局部加载
- `fleetStatus`
  - 多场站概览接口返回的原始或半原始数据
- `selectedFleetFarmCodes`
  - 场站筛选条件
- `selectedMatrixFarmCodes`
  - 表格勾选结果
- `selectedBatchTypes`
  - 批量操作的预测类型集合
- `controlBusyMap/globalControlBusyMap/matrixControlLoading`
  - 单项控制、全局控制、矩阵批量控制的忙碌态
- `logsDialogVisible/logsContent/logsFilters/currentPrediction`
  - 日志弹窗状态
- `confirmDialog`
  - 删除确认与其他确认动作的参数容器
- `batchResult`
  - 矩阵批量操作的返回汇总与明细
- `failedDialogPredictionType/failedStationsDialogVisible`
  - 失败场站明细弹窗状态
- `nowTick`
  - 每秒自增型时间基准，用于驱动倒计时和进度条
- `statusUpdatedAt`
  - 成功获取单场站状态后的本地时间戳

#### 4.1.2 关键计算属性和派生逻辑

1. `predictionTableRows`
- 作用：把 `predictions` 转成顶部“运行矩阵”表格数据。
- 关键加工：
  - 复制 `name/title/status`
  - 构造 `trend` 数组
- 结论：`trend` 为前端本地模拟值，不是后端趋势接口返回。

2. `fleetMatrixRows`
- 作用：把 `fleetStatus` 标准化成矩阵表可直接消费的数据。
- 关键加工：
  - 归一化 NWP 业务状态
  - 归一化三类预测状态
  - 在 NWP 失败时，前端将超短期状态覆盖为失败
  - 根据 `selectedFleetFarmCodes` 做前端过滤

3. `globalPredictStatus`
- 作用：得到卡片级总开关状态。
- 规则：只要任何场站该类型任务状态为运行，即视为该卡片“运行中”。

4. `aggregateByTypeMap`
- 作用：按预测类型汇总成功/失败/未启用/降级数量。
- 来源：基于 `fleetMatrixRows` 二次统计。

5. `failedStationsMap` / `failedStationsForDialog`
- 作用：收集每种预测类型下失败的场站列表，给“失败数点击查看”弹窗使用。

6. `getPredictMetrics(predictionName)`
- 作用：为卡片生成显示指标。
- 来源拆分：
  - `lastRun`：来自本地 `statusUpdatedAt`
  - `duration`：前端构造值
  - `nextRun`：前端按调度规则推算
  - `countdownText/countdownProgress`：前端按 `nowTick` 计算
  - `aggregate`：来自 `aggregateByTypeMap`

#### 4.1.3 生命周期和副作用

`onMounted` 中执行：

1. 注册场站变化监听 `farmService.addListener(handleFarmChanged)`。
2. 调用 `farmService.loadAvailableFarms()` 加载场站列表。
3. 读取当前场站 `farmService.getCurrentFarm()`。
4. 并行调用 `fetchStatus()` 和 `fetchFleetStatus()`。
5. 启动每秒一次的 `countdownTimerId`，更新时间基准 `nowTick`。
6. 启动每 60 秒一次的 `intervalId`，重新调用 `fetchStatus()` 和 `fetchFleetStatus()`。

`onUnmounted` 中执行：

- 移除场站监听
- 清理 60 秒轮询定时器
- 清理 1 秒倒计时定时器
- 清理场站切换防抖定时器

#### 4.1.4 加载态、空态、异常态

- 加载态
  - `loading`：覆盖整页，主要用于 `fetchStatus`、日志查询、控制类接口
  - `fleetLoading`：覆盖矩阵区
- 空态
  - 日志为空时显示文案“暂无日志信息”
  - 失败场站、批量结果表依赖数组本身，代码中未发现单独空态占位
- 异常态
  - `fetchStatus` / `fetchFleetStatus` 失败：仅 `console.error`，无页面提示
  - 控制类接口失败：`409` 提示 `ElMessage.warning`；其他错误通过 `showErrorDialog`
  - 日志接口失败：弹出错误详情弹窗

### 4.2 状态点组件 `StatusDot`

| 项目 | 说明 |
|---|---|
| 组件名称 | `StatusDot` |
| 文件路径 | [StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue) |
| 父子关系 | 被 `AutoPredict` 复用 |
| props / emits / callbacks | `props.active: Boolean`；无 emits |
| 内部 state / computed / hooks / store 使用情况 | 仅 `computed(statusClass)` |
| 生命周期或副作用逻辑 | 无 |
| 实现的具体功能 | 把布尔状态映射成绿色脉冲点或灰色静态点 |
| 触发了哪些接口 | 无 |
| 与其他组件的联动关系 | 仅作为状态展示原子组件 |
| 加载态 / 空态 / 异常态如何处理 | 无专门处理 |

补充说明：

- 它只接收布尔值，无法表达“降级/失败/延迟”等多级业务状态。
- 因此矩阵区使用的是 `biz-status` 文本标签，而不是 `StatusDot`。

### 4.3 趋势微图组件 `SparklineMini`

| 项目 | 说明 |
|---|---|
| 组件名称 | `SparklineMini` |
| 文件路径 | [SparklineMini.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/SparklineMini.vue) |
| 父子关系 | 被 `AutoPredict` 顶部运行矩阵复用 |
| props / emits / callbacks | `props.values: Array`、`props.active: Boolean`；无 emits |
| 内部 state / computed / hooks / store 使用情况 | `chartRef`、局部变量 `chart` |
| 生命周期或副作用逻辑 | `onMounted` 初始化 ECharts；`watch([values, active])` 重新渲染；`onBeforeUnmount` 销毁实例 |
| 实现的具体功能 | 用 ECharts 绘制 120x28 的迷你折线图 |
| 触发了哪些接口 | 无 |
| 与其他组件的联动关系 | 数据完全来自父组件传值 |
| 加载态 / 空态 / 异常态如何处理 | 无专门空态；若 `values` 为空则图表会渲染空序列 |

关键结论：

- 该组件本身不感知业务，也不请求接口。
- 本页中的 `values` 来自 `predictionTableRows` 本地生成，因此这里展示的不是后端“真实运行趋势”。

---

## 5. 交互明细表

### 5.1 顶部运行矩阵区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 表格 | 顶部第一个卡片 | 预测类型运行矩阵 | 展示三类预测状态与开关 | 只读展示 | 否 | 否 | 否 |
| 状态图标 | 表格状态列 | `运行中/已停止` | 展示布尔运行状态 | 无 | 否 | 否 | 否 |
| 开关 | 表格启停列 | 无固定文案 | 单项启停控制 | 调用 `handleSwitchToggle -> handleControl` | 否 | 是，`controlAutoPredict` | 会刷新顶部矩阵、卡片和部分状态 |
| 趋势微图 | 表格趋势列 | 无 | 展示模拟趋势线 | 无 | 否 | 否 | 否 |

### 5.2 多场站业务状态矩阵区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 标签说明 | 矩阵顶部 | 失败降级策略说明 | 告知 NWP 缺失时的降级策略 | 无 | 否 | 否 | 否 |
| 多选下拉框 | 矩阵工具栏 | 筛选场站 | 按场站过滤矩阵行 | 更新 `selectedFleetFarmCodes`，驱动 `fleetMatrixRows` 重算 | 否 | 否 | 影响矩阵表、批量全选范围、统计视图 |
| 复选框组 | 矩阵工具栏 | 超短期/短期/中期 | 批量控制作用类型选择 | 更新 `selectedBatchTypes` | 否 | 否 | 影响批量控制请求参数 |
| 按钮 | 矩阵工具栏 | 全选当前表格 | 勾选当前可见行 | 调用 `selectAllVisibleMatrixRows` | 否 | 否 | 影响批量控制目标场站 |
| 按钮 | 矩阵工具栏 | 清空勾选 | 取消勾选矩阵行 | 调用 `clearMatrixSelection` | 否 | 否 | 影响批量控制目标场站 |
| 按钮 | 矩阵工具栏 | 批量启用 | 对所选场站和类型批量启动 | 调用 `handleControlMatrix('start')` | 否 | 是，`controlAutoPredictMatrix` | 影响矩阵状态、卡片聚合、批量结果弹窗 |
| 按钮 | 矩阵工具栏 | 批量停止 | 对所选场站和类型批量停止 | 调用 `handleControlMatrix('stop')` | 否 | 是 | 同上 |
| 按钮 | 矩阵工具栏 | 批量删除 | 对所选场站和类型批量删除 | 调用 `handleControlMatrix('delete')` | 否 | 是 | 同上 |
| 表格勾选列 | 矩阵表 | 选择框 | 维护批量操作目标场站 | 触发 `handleMatrixSelectionChange` | 否 | 否 | 影响批量请求参数 |
| 按钮 | 矩阵操作列 | 查看当前曲线 | 跳转功率对比页 | 设置当前场站后 `router.push({ name:'PowerCompare', query })` | 否 | 否 | 会切换 `farmService` 当前场站，影响其它依赖场站上下文的页面 |
| 按钮 | 矩阵操作列 | 人工修正 | 跳转上报配置页 | 设置当前场站后 `router.push({ name:'ReportManagement', query })` | 否 | 否 | 同上 |

### 5.3 预测卡片区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 卡片 | 主体下半区 | 超短期/短期/中期 | 展示每类预测卡片总览 | 倒计时每秒变化 | 否 | 否 | 影响用户认知，不直接驱动其他组件 |
| 状态图标 | 卡片头 | 运行中/已停止 | 展示全局聚合状态 | 无 | 否 | 否 | 否 |
| 全局开关 | 卡片头 | 无固定文案 | 对所有场站的某类预测做统一启停 | 调用 `handleGlobalSwitchToggle`；关闭前先二次确认 | 否 | 是，`controlAutoPredictMatrix` | 刷新矩阵和卡片状态 |
| 更多菜单 | 卡片头 | 查看日志/删除任务 | 打开日志或确认删除 | `logs` 调日志接口；`delete` 打开确认弹窗 | 否 | 部分触发 | 影响日志弹窗/确认弹窗 |
| 标签型数字 | 指标区失败数 | `失败: n` | 查看失败场站明细 | 当 `n > 0` 时可点击，打开失败场站弹窗 | 否 | 否 | 影响失败弹窗 |
| 进度条 | 倒计时区 | 无 | 展示到下次执行的进度 | 随 `nowTick` 变化 | 否 | 否 | 否 |
| 按钮 | 卡片底部 | 查看日志 | 打开日志弹窗 | 调用 `fetchLogs(item.name)` | 否 | 是，`getAutoPredictLogs` | 影响日志弹窗 |

### 5.4 弹窗区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 弹窗 | 中间层 | 操作确认 | 对危险动作做确认 | 点击“确定”执行 `executeConfirmedAction` | 否 | 取决于待执行动作 | 影响任务状态 |
| 下拉框 | 日志弹窗 | 日志类型 | 切换日志类别 | `handleLogTypeChange -> fetchLogsByFilter` | 否 | 是 | 更新日志内容 |
| 日期选择器 | 日志弹窗 | 日期 | 按天查询日志 | 配合查询按钮使用 | 否 | 是 | 更新日志内容 |
| 按钮 | 日志弹窗 | 查询 | 按筛选条件查日志 | 调用 `fetchLogsByFilter` | 否 | 是 | 更新日志内容 |
| 按钮 | 日志弹窗 | 重置 | 恢复默认筛选 | 重置为 `train + 当天` 后再查一次 | 否 | 是 | 更新日志内容 |
| 按钮 | 日志弹窗 | 刷新 | 重新拉取当前日志 | 调用 `fetchLogsByFilter` | 否 | 是 | 更新日志内容 |
| 弹窗 | 中间层 | 错误详情 | 展示接口错误细节 | 只读 | 否 | 否 | 否 |
| 弹窗 | 中间层 | 批量操作结果明细 | 展示批量接口返回 summary/items | 只读+筛选+导出 | 否 | 否 | 否 |
| 下拉框 | 批量结果弹窗 | 按场站筛选明细 | 过滤结果明细 | 更新 `batchResultFarmFilter` | 否 | 否 | 影响结果表显示 |
| 按钮 | 批量结果弹窗 | 清空筛选 | 清除结果筛选 | 清空本地 filter | 否 | 否 | 影响结果表显示 |
| 按钮 | 批量结果弹窗 | 导出失败场站 | 导出 CSV | 调用 `exportFailedBatchItems` 生成浏览器下载 | 否 | 否 | 无 |
| 弹窗 | 中间层 | 失败场站明细 | 查看失败站点名称/编码/原因 | 只读 | 否 | 否 | 无 |

### 5.5 页面中未发现的元素

- 输入框：代码中未发现文本输入框
- 普通单选框：代码中未发现
- Tabs：代码中未发现
- 图表大盘：代码中未发现独立大图表，只有 `SparklineMini`
- 抽屉：代码中未发现
- Tooltip：表格消息列使用 `show-overflow-tooltip`，但未发现显式 `el-tooltip`
- 导入上传：代码中未发现

---

## 6. 接口明细表

### 6.1 页面直接使用的接口

| 接口名称 | 请求方法 | URL | 所在 api/service 文件 | 调用函数名 | 调用触发条件 | 请求参数 | 返回数据结构 | 返回数据映射位置 | 失败时页面处理 |
|---|---|---|---|---|---|---|---|---|---|
| 获取当前场站自动预测状态 | GET | `/api/v1/autopredict/status`，404/405 或无响应时回退 `/api/status` | [autopredictApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/autopredictApi.js) | `getAutoPredictStatus(farmCode)` | 页面初始化、场站切换、60 秒轮询、单项控制后延迟刷新、全局控制后刷新、批量控制后刷新 | `farm_code` | 代码按 `res.data?.data || res.data || {}` 解包，页面预期为 `{ supershort: boolean, short: boolean, medium: boolean }`；代码中未明确更完整结构 | 映射到 `predictions[i].status`，用于顶部矩阵状态和部分本地指标 | `console.error('获取自动预测状态失败')`，代码中未发现用户可见提示 |
| 获取多场站自动预测概览 | GET | `/api/v1/autopredict/overview`，回退 `/api/overview` | [autopredictApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/autopredictApi.js) | `getAutoPredictOverview()` | 页面初始化、场站切换、60 秒轮询、全局控制后刷新、矩阵批量控制后刷新 | 无 | 页面预期 `payload.items` 为数组，每项至少包含 `farm_code/farm_name/nwp/status` 等字段；字段完整定义代码中未明确 | 映射到 `fleetStatus`，再经 `fleetMatrixRows` 生成矩阵和卡片聚合 | 捕获异常后降级调用 `getAutoPredictStatusAll()` |
| 获取多场站状态汇总降级接口 | GET | `/api/v1/autopredict/status_all`，回退 `/api/status_all` | [autopredictApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/autopredictApi.js) | `getAutoPredictStatusAll()` | `getAutoPredictOverview()` 失败时作为 fallback | 无 | 页面同样按 `payload.items` 预期；需结合后端确认实际结构 | 映射到 `fleetStatus` | 若再次失败，仅 `console.error('获取矩阵状态失败')` |
| 单项启停/删除控制 | POST | `/api/v1/autopredict/{action}`，回退 `/api/{action}`；其中 `action` 为 `start/stop/delete` | [autopredictApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/autopredictApi.js) | `controlAutoPredict(action, predictionType, farmCode)` | 顶部表格开关、确认删除弹窗执行 | `{ type, farm_code }` | 页面读取 `res.data?.data || res.data || {}`，重点消费 `warning` 字段 | 仅用于消息提示；成功 1 秒后触发 `fetchStatus()` | `409` 弹 warning；其他错误打开错误详情弹窗 |
| 矩阵批量控制 | POST | `/api/v1/autopredict/control_matrix`，回退 `/api/control_matrix` | [autopredictApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/autopredictApi.js) | `controlAutoPredictMatrix(action, predictionTypes, farmCodes)` | 卡片全局开关、矩阵批量启用/停止/删除 | `{ action, types, farm_codes }` | 页面消费 `payload.summary`、`payload.items`；预期 `summary.success/failed` 和 `items[]` 中含 `farm_code/type/status_code/success/message`；需结合后端确认完整字段 | 映射到 `batchResult`，驱动批量结果弹窗、失败导出、消息提示 | `409` warning；其他错误打开错误详情弹窗 |
| 获取日志 | GET | `/api/v1/autopredict/logs`，回退 `/api/logs` | [autopredictApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/autopredictApi.js) | `getAutoPredictLogs(predictionType, farmCode, options)` | 点击“查看日志”、切换日志类型、点击查询、点击重置、点击刷新 | `{ type, farm_code, logType, date, lines }` | 页面消费 `payload.logs` 或 `res.data.logs` 文本；代码中未发现结构化日志数组 | 映射到 `logsContent` 文本区域 | 异常时弹出错误详情弹窗 |

### 6.2 页面初始化间接依赖的接口

这些接口不是页面直接 import，但页面初始化会通过 `farmService.loadAvailableFarms()` 间接触发。

| 接口名称 | 请求方法 | URL | 所在 api/service 文件 | 调用函数名 | 调用触发条件 | 请求参数 | 返回数据结构 | 返回数据映射位置 | 失败时页面处理 |
|---|---|---|---|---|---|---|---|---|---|
| 获取自动预测可用场站 | GET | `/api/v1/autopredict/farms`，回退 `/api/farms` | [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js) | `getAutoPredictFarms()` | `farmService.loadAvailableFarms()` 初始化时 | 无 | 预期数组项含 `farm_code/farm_name` | 映射到 `farmService.availableFarms` 候选源 | `console.warn`，继续尝试其他场站接口 |
| 获取上报模块场站 | GET | `/api/v1/report/farms`，回退 `/api/report/farms` | [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js) | `getReportFarms()` | 同上 | 无 | 预期数组项含 `farm_code/farm_name` | 作为场站名称补全与 fallback 数据源 | `console.warn` |
| 获取通用场站列表 | GET | `/api/v1/farms`，回退 `/api/farms` | [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js) | `getFarms()` | 同上 | 无 | 预期数组项含 `farm_code/farm_name` | 作为场站 fallback 数据源 | `console.warn`；最终仍失败则使用本地默认场站 `DEFAULT_FARM` |

### 6.3 接口封装层的隐性逻辑

`autopredictApi.js` 里还有页面会受到影响但页面本身不直接感知的逻辑：

1. v1/legacy 双路径兼容
- 先调用 `/api/v1/autopredict/...`
- 如果无响应、404 或 405，则自动回退到旧路径 `/api/...`

2. 场站编码兜底
- 若 `farmCode` 为空，则优先取 `farmService.getCurrentFarm()`
- 若仍为空，则取 `getFallbackFarmCode()`，最终兜底为 `DEFAULT_FARM`

3. 无效场站自动切换
- 当后端返回 `400` 且错误文案包含“无效的场站代码”时，API 层会：
  - 自动选一个 fallback 场站
  - 调用 `farmService.setCurrentFarm(fallbackFarmCode)`
  - 使用 fallback 场站重试请求

这意味着：

- 页面当前看到的场站状态有可能是 API 层自动切换后的结果，不一定仍然是最初请求的场站。
- 代码中未发现用户可见提示来说明“因场站无效已自动切换”。

---

## 7. 数据流说明

### 7.1 初始化加载流程

1. 进入 `/autopredict` 路由。
2. `AutoPredict` 挂载。
3. `onMounted` 调用 `farmService.addListener(handleFarmChanged)`，注册场站变化监听。
4. `onMounted` 调用 `farmService.loadAvailableFarms()`。
5. `farmService.loadAvailableFarms()` 依次尝试：
   - `getAutoPredictFarms()`
   - `getReportFarms()`
   - `getFarms()`
6. `farmService` 归一化和去重场站列表，并校验当前场站是否有效。
7. 页面读取 `currentFarm = farmService.getCurrentFarm()`。
8. 页面执行 `fetchStatus()`：
   - 查询当前场站三类预测的启停状态
   - 写入 `predictions[].status`
   - 记录 `statusUpdatedAt`
9. 页面执行 `fetchFleetStatus()`：
   - 优先调用 `getAutoPredictOverview()`
   - 失败则回退 `getAutoPredictStatusAll()`
   - 写入 `fleetStatus`
10. 计算属性自动更新：
   - `predictionTableRows`
   - `fleetMatrixRows`
   - `globalPredictStatus`
   - `aggregateByTypeMap`
   - `failedStationsMap`
11. 启动：
   - 1 秒倒计时定时器
   - 60 秒轮询定时器

### 7.2 用户操作后的数据变化

#### 7.2.1 单项开关

1. 用户在顶部矩阵切换某一预测类型开关。
2. 调用 `handleSwitchToggle(name, enabled)`。
3. 转换成 `start/stop` 动作，进入 `handleControl(name, action)`。
4. 调用 `controlAutoPredict(action, name, currentFarm.value)`。
5. 接口成功后：
   - 显示成功或 warning 提示
   - 1 秒后重新调用 `fetchStatus()`
6. 顶部矩阵状态变化。
7. 卡片派生指标也可能变化。

#### 7.2.2 卡片全局开关

1. 用户切换卡片头部总开关。
2. 取 `fleetStatus` 中所有场站编码作为作用范围。
3. 若是关闭动作，先弹 `ElMessageBox.confirm` 进行高风险确认。
4. 调用 `controlAutoPredictMatrix(action, [predictionType], allFarmCodes)`。
5. 根据返回 `summary.success/failed` 给出消息提示。
6. 调用 `fetchStatus()` 和 `fetchFleetStatus()` 刷新页面。

#### 7.2.3 矩阵批量控制

1. 用户勾选场站行。
2. 用户勾选目标类型。
3. 点击批量启用/停止/删除。
4. 调用 `handleControlMatrix(action)`。
5. 若未勾选场站或未选择类型，则直接 `ElMessage.warning`，不发请求。
6. 调用 `controlAutoPredictMatrix(action, targetTypes, targetFarmCodes)`。
7. 成功后将 `summary/items` 写入 `batchResult`。
8. 打开批量结果弹窗。
9. 刷新单场站状态和矩阵状态。

#### 7.2.4 日志查看

1. 用户点击卡片“查看日志”或下拉菜单“查看日志”。
2. 调用 `fetchLogs(predictionType)`。
3. 初始化：
   - `logsDialogVisible = true`
   - `currentPrediction = predictionType`
   - 重置筛选条件为 `train + 今天`
4. 调用 `fetchLogsByFilter()`。
5. 接口返回的 `logs` 文本写入 `logsContent`。

#### 7.2.5 场站切换

1. 用户在布局层 [FarmSelector.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmSelector.vue) 切换场站。
2. `farmService.setCurrentFarm()` 修改全局当前场站并通知监听器。
3. `AutoPredict` 中 `handleFarmChanged(farmCode)` 被触发。
4. 使用 300ms `setTimeout` 做简单防抖。
5. 调用 `fetchStatus()` 和 `fetchFleetStatus()`。

### 7.3 哪些状态是本地状态

本地状态包括：

- 所有弹窗显隐
- 所有筛选值
- 所有忙碌态
- 所有倒计时和进度条
- `statusUpdatedAt`
- `batchResult`
- `errorDetails`
- `selectedMatrixFarmCodes`
- `selectedFleetFarmCodes`
- `selectedBatchTypes`
- 顶部趋势线数组

### 7.4 哪些状态来自全局 store / 全局单例

- `currentFarm` 来自 `farmService`
- `availableFarms` 也由 `farmService` 维护
- 当前用户作用域会通过 `farmService -> getUserMeta()` 影响可见场站范围
- 代码中未发现 Vuex/Pinia 的页面级状态依赖

### 7.5 哪些数据来自后端接口

- 当前场站三类预测启停状态
- 多场站概览/状态矩阵原始数据
- 日志文本
- 批量控制结果摘要与明细
- 可用场站列表

### 7.6 哪些字段经过二次加工/格式化

前端二次加工明显存在于：

- `predictionTableRows.trend`
- `fleetMatrixRows` 各种 `xxxState`
- `globalPredictStatus`
- `aggregateByTypeMap`
- `failedStationsMap`
- `getPredictMetrics()` 生成的：
  - `lastRun`
  - `duration`
  - `nextRun`
  - `countdownText`
  - `countdownProgress`
  - `scheduleLabel`

---

## 8. 权限与状态控制说明

### 8.1 权限控制

1. 路由级
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js) 中 `/autopredict` 路由声明：
  - `meta.requiredPermissions = ['auto_predictions']`

2. 菜单级
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 中：
  - 一级菜单组：`hasPermission('auto_predictions') || hasPermission('manual_intervention_workspace')`
  - 二级菜单项 `/autopredict`：`hasPermission('auto_predictions')`

3. 实际路由守卫
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js) 的 `beforeEach` 当前只判断是否登录。
- 代码中未发现守卫读取 `requiredPermissions` 并做拒绝跳转。

4. 页面内部按钮权限
- 代码中未发现单项开关、批量操作、日志查看等按钮的额外权限判断。
- 结论：当前更像“菜单可见性控制”，不是“页面内部动作权限控制”。

### 8.2 状态控制

1. 请求忙碌态
- `loading`
- `fleetLoading`
- `controlBusyMap`
- `globalControlBusyMap`
- `matrixControlLoading`

2. 操作保护
- 单项控制通过 `controlBusyMap[name]` 防重复点击
- 卡片全局控制通过 `globalControlBusyMap[predictionType]` 防重复点击
- 批量控制通过 `matrixControlLoading` 防重复提交

3. 并发请求保护
- `fetchStatus()` 使用 `statusRequestSeq`
- 若后发请求已经产生，先发请求结果会被丢弃，避免旧状态覆盖新状态

4. 危险动作确认
- 删除类操作通过自定义确认弹窗 `confirmDialog`
- 全局关闭通过 `ElMessageBox.confirm`

---

## 9. 风险点/待确认点

### 9.1 风险点

1. 页面存在“展示真实状态”和“前端模拟状态”混用风险
- 顶部趋势线、执行耗时、上次执行时间、下次执行时间、倒计时、部分聚合指标均有明显前端推导成分。
- 若业务方把这些字段当作真实调度结果，容易误解。

2. 路由权限配置与实际守卫不一致
- 路由配置声明了 `requiredPermissions`
- 但全局守卫只校验登录态
- 如果用户直接输入路由地址，是否仍可进入页面，需结合运行态确认

3. 页面内部动作没有额外权限收口
- 单项开关、批量启停、批量删除等动作在页面代码中未发现基于权限的显隐或禁用逻辑
- 需要结合后端接口鉴权确认是否由服务端兜底

4. 状态接口失败没有页面级可见提示
- `fetchStatus`、`fetchFleetStatus` 失败仅 `console.error`
- 用户可能看到旧数据而无感知

5. API 层可能自动切换场站
- 当请求场站无效时，API 层会自动切换到 fallback 场站并重试
- 页面层没有明显提示，可能造成“为什么展示的不是当前选中场站”的认知偏差

6. 矩阵业务状态映射有前端主观规则
- `fleetMatrixRows` 会根据 NWP 失败强行覆盖超短期状态
- 这属于前端业务解释层，不一定完全等于后端原始语义

7. 删除操作语义需结合后端确认
- 页面中“删除任务”走 `controlAutoPredict('delete', ...)` 或矩阵 `action='delete'`
- 删除后实际删除的是 PM2 任务、调度配置、运行实例还是仅逻辑停用，代码中未明确

### 9.2 待确认点

- `getAutoPredictOverview()` 与 `getAutoPredictStatusAll()` 的实际返回字段完整定义，代码中未明确，需结合后端确认
- `summary/items` 中字段是否固定包含 `status_code/success/message/type/farm_code`，需结合后端确认
- 日志接口 `logType` 支持值在后端是否仅 `train/predict`，代码中未明确
- 卡片“上次执行时间/执行耗时/下次执行时间”是否后续计划改成真实后端字段，代码中未明确
- 页面注释掉的历史功能是否已永久下线，还是仅前端暂时移除，代码中未明确

---

## 10. 代码证据清单

### 10.1 页面与路由

- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)
  - 页面主体模板
  - `predictionTableRows`
  - `fleetMatrixRows`
  - `globalPredictStatus`
  - `aggregateByTypeMap`
  - `failedStationsMap`
  - `getPredictMetrics`
  - `fetchStatus`
  - `fetchFleetStatus`
  - `handleControl`
  - `handleGlobalSwitchToggle`
  - `handleControlMatrix`
  - `fetchLogsByFilter`
  - `openFarmCurve`
  - `openManualCorrection`
  - `exportFailedBatchItems`
  - `onMounted`
  - `onUnmounted`
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - `/autopredict` 路由定义
  - `meta.requiredPermissions = ['auto_predictions']`
  - `beforeEach` 登录态守卫
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - `/autopredict` 菜单显示条件
  - `hasPermission`
  - `provide('isAnimatedBackground', ...)`

### 10.2 子组件

- [StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue)
  - `props.active`
  - `statusClass`
- [SparklineMini.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/SparklineMini.vue)
  - `props.values`
  - `props.active`
  - `render`
  - `watch(() => [props.values, props.active], ...)`

### 10.3 API 与数据源

- [autopredictApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/autopredictApi.js)
  - `resolveFarmCode`
  - `isInvalidFarmError`
  - `withLegacyFallback`
  - `autopredictGet`
  - `autopredictPost`
  - `getAutoPredictStatus`
  - `getAutoPredictOverview`
  - `getAutoPredictStatusAll`
  - `controlAutoPredict`
  - `controlAutoPredictMatrix`
  - `getAutoPredictLogs`
- [farmService.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/farmService.js)
  - `getCurrentFarm`
  - `setCurrentFarm`
  - `loadAvailableFarms`
  - `addListener`
  - `removeListener`
  - `notifyListeners`
  - `applyUserScope`
- [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js)
  - `getAutoPredictFarms`
  - `getReportFarms`
  - `getFarms`

---

## 关键代码证据清单

- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)
- [autopredictApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/autopredictApi.js)
- [farmService.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/farmService.js)
- [StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue)
- [SparklineMini.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/SparklineMini.vue)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js)

## 可能遗漏点检查清单

- `getAutoPredictOverview()` / `getAutoPredictStatusAll()` 的后端返回样例代码中未内嵌，需结合后端接口确认
- 页面中注释掉的历史能力未继续追踪到 git 历史，本次仅基于当前工作树代码判断
- 文本存在终端编码乱码，但不影响函数、路由、接口、状态变量的识别
- 若运行态存在后端鉴权、拦截器二次封装或网关权限，本次文档未覆盖，需要结合后端确认
