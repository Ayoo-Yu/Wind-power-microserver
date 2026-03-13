# 首页大屏代码级完整拆解

## 1. 页面概览

### 1.1 基础信息

| 字段 | 内容 |
|---|---|
| 页面名称 | 首页大屏 |
| 所属模块 | 首页 / 运行总览模块 |
| 路由路径 | `/` |
| 页面入口文件 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\HomePage.vue` |
| 页面依赖的子组件列表 | `KpiCards.vue`、`PowerTrendChart.vue`、`StationRankChart.vue`、`FleetMap.vue` |
| 页面依赖的 store/hooks/model/service/api 文件 | `src/services/dashboardService.js`、`src/utils/farmService.js`，以及服务层继续依赖 `src/api/farmApi.js`、`src/api/powerCompareApi.js`、`src/api/reportApi.js` |
| 页面是否受权限控制 | 页面本身没有单独 `requiredPermissions`；受父路由 `requiresAuth = true` 控制。代码中未发现首页单独权限拦截 |

### 1.2 页面定位

首页大屏是系统登录后的默认落地页，承担“全局运行看板”职责，核心能力包括：

1. 展示顶部刷新时间与手动刷新入口。
2. 展示 4 张 KPI 指标卡。
3. 展示功率趋势图。
4. 展示场站排名图。
5. 展示场站任务状态矩阵。
6. 展示气象快照区。
7. 展示事件/告警流，并支持标签筛选与自动滚动。

该页面本身是“页面组装层”，实际业务数据转换与 fallback 逻辑主要在 `dashboardService.js` 中完成。

### 1.3 页面复杂度评估

- 复杂度：中高
- 原因：
  - 页面 UI 结构清晰，但依赖 4 个图表/展示子组件
  - 数据不是直接接口返回即用，而是通过 `dashboardService` 聚合、转换、容错、fallback
  - 页面存在场站切换监听、手动刷新、事件轮播定时器
  - 接口来自多个域：场站、功率对比、上报日志

---

## 2. 页面结构树

```text
HomePage.vue
├─ dashboard-head 顶部标题区
│  ├─ 标题
│  ├─ 更新时间
│  └─ 刷新按钮
├─ KpiCards
│  └─ 4 张 KPI 卡片
├─ dashboard-grid
│  ├─ panel-trend
│  │  └─ PowerTrendChart
│  ├─ panel-left
│  │  └─ StationRankChart
│  └─ panel-center
│     └─ FleetMap
└─ dashboard-bottom
   ├─ weather-card
   │  ├─ fleet-weather-grid（全场模式）
   │  └─ weather-grid（单场模式）
   └─ events-card
      ├─ 事件标签 tabs
      └─ event-list 事件列表
```

---

## 3. 区块说明

### 3.1 顶部标题区

| 字段 | 内容 |
|---|---|
| 区块名称 | 顶部标题区 |
| 对应组件名 | `HomePage` 内部区块 |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\HomePage.vue` |
| 展示内容 | 页面标题、最近更新时间、刷新按钮 |
| 数据来源 | `updatedAt` 本地状态 |
| 是否可交互 | 是，刷新按钮可点击 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 更新时间只在 `loadData()` 成功后更新；无固定轮询 |

说明：
- 点击刷新按钮直接调用 `loadData()`。
- 页面不会自动周期性拉取数据，只有首次加载、场站切换、手动点击刷新时触发。

### 3.2 KPI 卡片区

| 字段 | 内容 |
|---|---|
| 区块名称 | KPI 卡片区 |
| 对应组件名 | `KpiCards` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\KpiCards.vue` |
| 展示内容 | 场站通信状态、功率/容量、预测准确率、上报完成情况 4 张卡片 |
| 数据来源 | `cards`，由 `getDashboardOverview()` 返回 |
| 是否可交互 | 否 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 跟随页面 `loadData()` 刷新 |

说明：
- `KpiCards` 本身不拉接口，只按 `item.type` 决定展示模板。
- 图标和圆环样式都是前端本地映射。

### 3.3 功率趋势图区

| 字段 | 内容 |
|---|---|
| 区块名称 | 功率趋势图区 |
| 对应组件名 | `PowerTrendChart` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\PowerTrendChart.vue` |
| 展示内容 | 实际功率、短期预测、超短期预测、可用容量四条线 |
| 数据来源 | `trendPoints`，由 `getDashboardTrend()` 返回 |
| 是否可交互 | 是，支持 ECharts tooltip 和 dataZoom |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 跟随页面刷新；图内无独立定时器 |

说明：
- 图表有 `Now` 标记线，用当前时间对应的最近刻度索引绘制。
- `ultraShort` 只展示未来 4 小时内的数据，超出时间窗口置为 `null`。

### 3.4 场站排名图区

| 字段 | 内容 |
|---|---|
| 区块名称 | 场站排名图区 |
| 对应组件名 | `StationRankChart` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\StationRankChart.vue` |
| 展示内容 | 场站平均功率排名柱状图 |
| 数据来源 | `rankRows`，由 `getDashboardStationRank()` 返回 |
| 是否可交互 | 是，支持 tooltip |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 跟随页面刷新 |

说明：
- 数据进入组件前已是 `[{ name, value }]` 结构。
- 组件内部再次做降序排序，并对第 1 名加 `TOP1` 富文本标记。

### 3.5 场站任务状态矩阵区

| 字段 | 内容 |
|---|---|
| 区块名称 | 场站任务状态矩阵区 |
| 对应组件名 | `FleetMap` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\FleetMap.vue` |
| 展示内容 | 每个场站在 `SCADA`、`NWP`、`超短期`、`短期`、`电网/上报` 等任务上的状态矩阵 |
| 数据来源 | `topologyPoints`，由 `getDashboardOverview()` 内部 `buildTaskMatrix()` 生成 |
| 是否可交互 | 否 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 跟随页面刷新 |

说明：
- 这里不是地图，而是任务状态矩阵表格。
- 列头来自 `dashboardService` 导出的 `TASK_KEYS`。

### 3.6 气象快照区

| 字段 | 内容 |
|---|---|
| 区块名称 | 气象快照区 |
| 对应组件名 | `HomePage` 内部模板区块 |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\HomePage.vue` |
| 展示内容 | 全场天气摘要或单场风速/风向/温度/气压卡片 |
| 数据来源 | `weatherMode`、`weatherRows`，由 `getDashboardWeatherSnapshot()` 返回 |
| 是否可交互 | 否 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 跟随页面刷新 |

说明：
- `weatherMode === 'fleet'` 时展示摘要型指标卡。
- `weatherMode !== 'fleet'` 时展示单站天气明细卡。
- 当前服务层逻辑主要是前端构造数据，代码中未发现真实气象接口请求。

### 3.7 事件流区

| 字段 | 内容 |
|---|---|
| 区块名称 | 事件流区 |
| 对应组件名 | `HomePage` 内部模板区块 |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\HomePage.vue` |
| 展示内容 | 事件标签筛选按钮、事件列表、事件时间/等级/消息 |
| 数据来源 | `events`，由 `getDashboardEvents()` 返回 |
| 是否可交互 | 是，可切换标签 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 有，`startEventTicker()` 每 2.6 秒循环滚动事件数组 |

说明：
- 标签只做前端筛选，不额外请求接口。
- 事件滚动方式不是 CSS，而是通过重排 `events` 数组实现。

---

## 4. 组件明细表

### 4.1 页面组件：HomePage

| 字段 | 内容 |
|---|---|
| 组件名称 | `HomePage` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\HomePage.vue` |
| 父子关系 | 父级为 `AppLayout` 中的 `<router-view>`；子组件为 `KpiCards`、`PowerTrendChart`、`StationRankChart`、`FleetMap` |
| props / emits / callbacks | 无 props；无 emits；内部回调 `loadData`、`windLevelStyle`、`startEventTicker` |
| 内部 state / computed / hooks / store 使用情况 | 使用 `ref`、`computed`、`onMounted`、`onBeforeUnmount`；无 Vuex/store；依赖 `farmService` 单例 |
| 生命周期或副作用逻辑 | `onMounted` 加载场站列表、拉取数据、启动事件滚动、注册场站监听；`onBeforeUnmount` 清理定时器和监听器 |
| 实现的具体功能 | 组装首页所有数据区块；响应场站变化；控制事件筛选和滚动 |
| 触发了哪些接口 | 间接通过 `dashboardService` 触发 `getFarms`、`getPowerCompareData`、`getReportLogs` |
| 与其他组件的联动关系 | 通过 props 向 4 个子组件分发数据；通过 `farmService.addListener` 响应布局层场站切换 |
| 加载态 / 空态 / 异常态如何处理 | 顶部刷新按钮显示 `loading`；页面内部没有统一空态；接口失败主要由服务层 fallback 吞掉并返回兜底数据 |

#### 4.1.1 页面内部状态

| 状态名 | 类型 | 用途 |
|---|---|---|
| `loading` | `ref<boolean>` | 页面数据加载中 |
| `cards` | `ref<Array>` | KPI 卡片数据 |
| `topologyPoints` | `ref<Array>` | 状态矩阵数据 |
| `rankRows` | `ref<Array>` | 排名图数据 |
| `trendPoints` | `ref<Array>` | 趋势图数据 |
| `weatherMode` | `ref<string>` | 天气区展示模式：`fleet` 或 `station` |
| `weatherRows` | `ref<Array>` | 天气区数据 |
| `events` | `ref<Array>` | 事件源数组 |
| `updatedAt` | `ref<string>` | 最近刷新时间 |
| `activeEventTab` | `ref<string>` | 当前事件筛选标签 |

#### 4.1.2 页面 computed

| computed | 作用 | 依赖 |
|---|---|---|
| `filteredEvents` | 根据 `activeEventTab` 过滤事件 | `activeEventTab`、`events` |
| `scrollingEvents` | 截取前 8 条事件用于展示 | `filteredEvents` |

#### 4.1.3 页面副作用逻辑

| 逻辑 | 位置 | 说明 |
|---|---|---|
| 首次加载场站列表 | `onMounted` | 调用 `farmService.loadAvailableFarms()` |
| 首次拉取首页数据 | `onMounted` | 调用 `loadData()` |
| 启动事件滚动 | `onMounted` | `setInterval` 每 2.6 秒滚动数组 |
| 注册场站变化监听 | `onMounted` | `farmService.addListener(farmListener)` |
| 场站变化重载数据 | `farmListener` | 切换场站后重新调用 `loadData()` |
| 清理定时器与监听器 | `onBeforeUnmount` | 清理 `eventTicker` 与 `farmListener` |

### 4.2 子组件：KpiCards

| 字段 | 内容 |
|---|---|
| 组件名称 | `KpiCards` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\KpiCards.vue` |
| 父子关系 | 父级为 `HomePage`；无继续拆分的自定义子组件 |
| props / emits / callbacks | `props.items:Array`；无 emits |
| 内部 state / computed / hooks / store 使用情况 | 无响应式 state；仅本地函数 `resolveIcon`、`ringStyle` |
| 生命周期或副作用逻辑 | 无 |
| 实现的具体功能 | 按 `item.type` 渲染不同 KPI 模板 |
| 触发了哪些接口 | 无 |
| 与其他组件的联动关系 | 只消费 `HomePage.cards` |
| 加载态 / 空态 / 异常态如何处理 | 无专门加载态/空态；`items=[]` 时会渲染空容器 |

组件内部支持的 `type`：
- `station-comm`
- `power-capacity`
- `accuracy-split`
- `report-completion`
- 其他类型则回退为直接显示 `item.value`

### 4.3 子组件：PowerTrendChart

| 字段 | 内容 |
|---|---|
| 组件名称 | `PowerTrendChart` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\PowerTrendChart.vue` |
| 父子关系 | 父级为 `HomePage` |
| props / emits / callbacks | `props.points:Array`；无 emits |
| 内部 state / computed / hooks / store 使用情况 | `chartRef`、`chart`；无 store |
| 生命周期或副作用逻辑 | `onMounted` 初始化 ECharts 并绑定 resize；`watch(props.points)` 重新渲染；`onBeforeUnmount` 卸载图表 |
| 实现的具体功能 | 绘制功率趋势折线图并标注当前时间位置 |
| 触发了哪些接口 | 无 |
| 与其他组件的联动关系 | 只消费 `HomePage.trendPoints` |
| 加载态 / 空态 / 异常态如何处理 | 无单独加载态；空数组时仍会绘制空图；无异常 UI |

关键逻辑：
- `resolveNowIndex(labels)`：寻找最接近当前时间的 x 轴刻度
- `render()`：组装 4 条线和 `markLine`
- 支持 `dataZoom`

### 4.4 子组件：StationRankChart

| 字段 | 内容 |
|---|---|
| 组件名称 | `StationRankChart` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\StationRankChart.vue` |
| 父子关系 | 父级为 `HomePage` |
| props / emits / callbacks | `props.rows:Array`；无 emits |
| 内部 state / computed / hooks / store 使用情况 | `chartRef`、`chart` |
| 生命周期或副作用逻辑 | `onMounted` 初始化图表；`watch(props.rows)` 重绘；`onBeforeUnmount` 销毁 |
| 实现的具体功能 | 绘制场站平均功率排名横向柱状图 |
| 触发了哪些接口 | 无 |
| 与其他组件的联动关系 | 只消费 `HomePage.rankRows` |
| 加载态 / 空态 / 异常态如何处理 | 无显式加载态；空数组显示空图 |

关键逻辑：
- 组件内部再次按 `value` 排序
- 第 1 名使用富文本 `TOP1` 标签强调

### 4.5 子组件：FleetMap

| 字段 | 内容 |
|---|---|
| 组件名称 | `FleetMap` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\FleetMap.vue` |
| 父子关系 | 父级为 `HomePage` |
| props / emits / callbacks | `props.points:Array`；无 emits |
| 内部 state / computed / hooks / store 使用情况 | 无本地响应式 state；使用服务层导出的 `TASK_KEYS` |
| 生命周期或副作用逻辑 | 无 |
| 实现的具体功能 | 将场站任务状态渲染为矩阵表 |
| 触发了哪些接口 | 无 |
| 与其他组件的联动关系 | 只消费 `HomePage.topologyPoints`；列头来自 `dashboardService.TASK_KEYS` |
| 加载态 / 空态 / 异常态如何处理 | 无显式加载态；空数组时表体为空 |

关键逻辑：
- `statusSymbol(status)` 将 `ok/warn/error` 映射为不同符号
- 状态色块通过 class 名控制

### 4.6 页面依赖服务：dashboardService

| 字段 | 内容 |
|---|---|
| 组件/模块名称 | `dashboardService` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\services\dashboardService.js` |
| 父子关系 | 被 `HomePage.vue` 调用；继续依赖 `farmApi`、`powerCompareApi`、`reportApi`、`farmService` |
| props / emits / callbacks | 不适用 |
| 内部 state / computed / hooks / store 使用情况 | 无 Vue 响应式状态；纯函数 + async 服务函数 |
| 生命周期或副作用逻辑 | 无组件生命周期；服务函数内部会发起多个接口请求 |
| 实现的具体功能 | 首页数据聚合、接口兼容、结构归一、指标计算、fallback 数据生成 |
| 触发了哪些接口 | `getFarms()`、`getPowerCompareData()`、`getReportLogs()` |
| 与其他组件的联动关系 | 直接服务于 `HomePage` 及 `FleetMap`（通过导出 `TASK_KEYS`） |
| 加载态 / 空态 / 异常态如何处理 | 大量使用 `try/catch` 吞错，并返回 fallback 结果 |

#### 4.6.1 `getDashboardOverview({ farmCode })`

功能：
- 聚合首页 KPI 卡片与场站任务矩阵。

触发接口：
- `farmService.loadAvailableFarms()`
- `getFarms()`
- `getReportLogs()`
- 多次 `getPowerCompareData()`

输出结构：

```js
{
  cards: [...],
  topology: [...]
}
```

核心处理：
- 先拿可用场站列表和场站元数据
- 若无数据，则 fallback 到 `buildFallbackFarms()`
- 调用 `getReportLogs()` 获取今日日志
- 对每个选中场站调用 `getPowerCompareData()`，推导：
  - 最新实测功率
  - 短期准确率
  - 超短期准确率
  - 是否在线
- 计算：
  - 在线/离线场站数
  - 总功率与总容量
  - 负荷率
  - 加权准确率
  - 上报完成率
- 通过 `buildTaskMatrix()` 生成状态矩阵

异常处理：
- 每个子接口失败都尽量局部兜底
- 最终仍返回可展示结构，而不是抛错给页面

#### 4.6.2 `getDashboardTrend({ farmCode, start, end })`

功能：
- 从功率对比接口提取并合并趋势图数据。

触发接口：
- `getPowerCompareData()`

关键处理：
- `extractSeriesFromPowerCompare()`：从不同候选字段名中抽取 `actual` / `shortTerm` / `ultraShort` / `predicted` / `availableCap`
- `mergeTrendSeries()`：合并为统一点位结构
- 对未来时段的 `actual` 置空
- 对超出 4 小时窗口的 `ultraShort` 置空

fallback：
- 若接口失败或合并结果为空，返回 `buildFallbackTrend()` 的 96 点假数据

#### 4.6.3 `getDashboardStationRank({ farmCode, start, end })`

功能：
- 获取场站平均实际功率并排序。

触发接口：
- `farmService.loadAvailableFarms()`
- 多次 `getPowerCompareData()`

关键处理：
- 对所有目标场站逐个拉取功率对比数据
- 从 `actual` 序列求平均值
- 生成 `[{ name, value }]`
- 降序排序后取前 8

fallback：
- 返回固定 4 条假数据：`Station A/B/C/D`

#### 4.6.4 `getDashboardWeatherSnapshot({ farmCode })`

功能：
- 返回首页气象展示区数据。

触发接口：
- 无直接接口请求

关键处理：
- 读取 `farmService.getAvailableFarms()`
- 若无场站：返回全场摘要型默认数据
- 若当前选中了某个具体场站：返回 `station` 模式的两张天气卡
- 否则返回 `fleet` 模式摘要数据

结论：
- 当前天气区数据主要是前端构造，不是实时后端接口。

#### 4.6.5 `getDashboardEvents({ farmCode, limit })`

功能：
- 获取首页事件流。

触发接口：
- `getReportLogs()`

关键处理：
- 拉取当天上报日志
- 将日志映射为：
  - `id`
  - `time`
  - `level`
  - `levelText`
  - `category`
  - `message`
- 分类逻辑：
  - 包含 forecast/report/short/supershort 等关键字 -> `business`
  - 否则 -> `system`

fallback：
- 返回固定 5 条默认事件

---

## 5. 交互明细表

### 5.1 页面可见元素清单

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 按钮 | 顶部标题区右侧 | 刷新按钮 | 手动刷新首页数据 | 调用 `loadData()` | 否 | 是 | 更新全部区块 |
| 卡片 | KPI 区 | 4 张 KPI 卡片 | 展示通信、功率、准确率、上报完成 | 无点击行为 | 否 | 否 | 否 |
| 图表 | 中部 | 趋势图 | 展示功率趋势 | 鼠标悬浮 tooltip、缩放 | 否 | 否 | 否 |
| 图表 | 中部左侧 | 排名图 | 展示场站平均功率排名 | 鼠标悬浮 tooltip | 否 | 否 | 否 |
| 矩阵表 | 中部 | 状态矩阵 | 展示场站任务状态 | 无点击行为 | 否 | 否 | 否 |
| 天气卡片 | 底部左侧 | 全场/单场天气卡 | 展示天气摘要 | 无点击行为 | 否 | 否 | 否 |
| tab 按钮 | 事件流区顶部 | `All` / `System` / `Business` | 过滤事件类别 | 更新 `activeEventTab`，重算 `filteredEvents` | 否 | 否 | 影响事件列表 |
| 事件列表 | 底部右侧 | 事件项 | 展示事件时间、等级、消息 | 无点击行为 | 否 | 否 | 受滚动逻辑和 tab 影响 |
| 状态图标 | 事件项 | `event-dot-*` | 展示事件级别 | 自动根据 level 切换颜色 | 否 | 否 | 否 |

### 5.2 页面交互流程

#### A. 页面首次进入

1. `onMounted` 调用 `farmService.loadAvailableFarms()`
2. 调用 `loadData()`
3. 依次从服务层获得：
   - `overview`
   - `rank`
   - `trend`
   - `weather`
   - `eventRows`
4. 将结果写入页面各 `ref`
5. 设置 `updatedAt`
6. 调用 `startEventTicker()`
7. 注册场站监听器

#### B. 点击刷新按钮

1. 按钮触发 `loadData()`
2. `loading` 设为 `true`
3. 重新获取全部首页数据
4. 刷新所有子组件输入
5. `updatedAt` 变成当前时间
6. `loading` 结束

#### C. 切换场站

1. 场站切换动作不在页面内，而在布局层 `FarmSelector`
2. `FarmSelector` -> `farmService.setCurrentFarm()`
3. `farmService.notifyListeners()` 通知监听器
4. 首页注册的 `farmListener` 被触发
5. `loadData()` 重新执行
6. 所有区块按新场站数据重绘

#### D. 切换事件标签

1. 点击 `All/System/Business`
2. 更新 `activeEventTab`
3. `filteredEvents` 重新计算
4. `scrollingEvents` 取前 8 条渲染

#### E. 事件自动滚动

1. `startEventTicker()` 启动定时器
2. 每 2.6 秒将 `events` 数组头元素移到末尾
3. 事件列表视觉上滚动更新

---

## 6. 接口明细表

> 首页页面本身不直接调用 `src/api`，而是调用 `dashboardService`。以下接口按“页面实际触发到的最终接口”梳理。

### 6.1 获取场站列表接口

| 字段 | 内容 |
|---|---|
| 接口名称 | 获取场站列表 |
| 请求方法 | `GET` |
| URL | 优先 `/api/v1/farms`，fallback `/api/farms` |
| 所在 api/service 文件 | `src/api/farmApi.js` |
| 调用函数名 | `getFarms()` |
| 调用触发条件 | `getDashboardOverview()` 内部获取场站元数据时 |
| 请求参数 | 无 |
| 返回数据结构 | 服务层按数组使用，字段至少消费：`farm_code`、`farm_name`、`capacity` |
| 返回数据映射到页面哪个组件/哪个字段 | 映射到 `cards` 和 `topologyPoints` 的基础元数据 |
| 失败时页面怎么处理 | `dashboardService` 吞错后继续使用 `farmService` 已缓存场站，或 fallback 到 `buildFallbackFarms()` |

### 6.2 获取功率对比数据接口

| 字段 | 内容 |
|---|---|
| 接口名称 | 获取功率对比数据 |
| 请求方法 | `POST` |
| URL | 优先 `/api/v1/power-compare/data`，fallback `/power-compare/data` |
| 所在 api/service 文件 | `src/api/powerCompareApi.js` |
| 调用函数名 | `getPowerCompareData(payload)` |
| 调用触发条件 | `getDashboardOverview()`、`getDashboardTrend()`、`getDashboardStationRank()` 内部 |
| 请求参数 | `{ start, end, farm_code }` |
| 返回数据结构 | 代码中未固定 schema，`dashboardService` 通过候选字段名解析：`actual` / `real` / `measured` / `wp_true` / `short_term` / `short` / `supershort` / `forecast` / `available_capacity` 等 |
| 返回数据映射到页面哪个组件/哪个字段 | `trendPoints`、`rankRows`、`cards` 中的功率/准确率、`topologyPoints` 中通信状态 |
| 失败时页面怎么处理 | 局部 catch：对单场站失败记为 `online=false` 或 `value=0`；趋势图会 fallback；排名图会 fallback |

### 6.3 获取上报日志接口

| 字段 | 内容 |
|---|---|
| 接口名称 | 获取上报日志 |
| 请求方法 | `GET` |
| URL | 优先 `/api/v1/report/logs`，fallback `/api/report/logs` |
| 所在 api/service 文件 | `src/api/reportApi.js` |
| 调用函数名 | `getReportLogs(params)` |
| 调用触发条件 | `getDashboardOverview()` 和 `getDashboardEvents()` 内部 |
| 请求参数 | `farm_code`、`start_time`、`end_time`、`page`、`page_size`、`per_page` |
| 返回数据结构 | 服务层通过 `unwrapItems()` 兼容：`payload`、`payload.items`、`payload.logs`、`payload.data.items`、`payload.data.logs`、`payload.data` |
| 返回数据映射到页面哪个组件/哪个字段 | 映射到 `cards` 中上报完成率、`topologyPoints` 中任务状态、`events` 列表 |
| 失败时页面怎么处理 | overview 中日志置空；events 使用 fallback 默认事件列表 |

### 6.4 页面间接调用但不属于首页直连展示的接口

#### 6.4.1 `farmService.loadAvailableFarms()` 触发的接口链

该服务会尝试按顺序调用：

1. `getAutoPredictFarms()`  
   - `GET /api/v1/autopredict/farms` fallback `/api/farms`
2. `getReportFarms()`  
   - `GET /api/v1/report/farms` fallback `/api/report/farms`
3. `getFarms()`  
   - `GET /api/v1/farms` fallback `/api/farms`

这些接口不是首页模板直接消费，但会影响：
- 当前场站列表
- 当前场站名称
- 是否进入全场模式或单场模式

---

## 7. 数据流说明

### 7.1 初始化加载流程

1. 用户登录后进入 `/`
2. 父路由 `AppLayout` 已完成登录态检查
3. `HomePage` 挂载
4. `farmService.loadAvailableFarms()` 初始化场站列表
5. 执行 `loadData()`
6. `loadData()` 读取当前场站 `farmService.getCurrentFarm()`
7. 并行调用：
   - `getDashboardOverview({ farmCode })`
   - `getDashboardStationRank({ farmCode })`
   - `getDashboardTrend({ farmCode })`
   - `getDashboardWeatherSnapshot({ farmCode })`
   - `getDashboardEvents({ farmCode, limit: 12 })`
8. 将结果拆分写入：
   - `cards`
   - `topologyPoints`
   - `rankRows`
   - `trendPoints`
   - `weatherMode`
   - `weatherRows`
   - `events`
9. `updatedAt = formatNow()`
10. 启动事件轮播定时器

### 7.2 用户操作后数据如何变化

#### 手动刷新
- 重新触发所有首页服务函数
- 所有图表和展示块整体更新

#### 事件标签切换
- 不请求后端
- 只重算 `filteredEvents` 和 `scrollingEvents`

#### 场站切换
- 由布局层修改 `farmService.currentFarm`
- 首页监听器收到通知后重新加载全部数据

### 7.3 哪些状态是本地状态

- `loading`
- `cards`
- `topologyPoints`
- `rankRows`
- `trendPoints`
- `weatherMode`
- `weatherRows`
- `events`
- `updatedAt`
- `activeEventTab`

### 7.4 哪些状态来自全局/共享对象

- 当前场站：来自 `farmService.currentFarm`
- 可用场站列表：来自 `farmService.availableFarms`
- 用户场站范围：间接受 `farmService` 内部 `getUserMeta()` 过滤

### 7.5 哪些数据来自后端接口

- 场站元数据
- 功率对比原始序列
- 上报日志

### 7.6 哪些字段经过二次加工/格式化

| 数据 | 加工逻辑 |
|---|---|
| KPI 卡片 | 从多接口数据聚合计算得到，不是后端直接返回 |
| 趋势图点位 | `mergeTrendSeries()` 合并多序列并裁切未来数据 |
| 排名图数据 | 按实际功率均值重算 |
| 状态矩阵 | 由日志关键字 + 通信状态推导 |
| 事件列表 | 由日志映射为 `level/category/message/time` |
| 天气区数据 | 当前主要是前端构造 |
| 更新时间 | `formatNow()` 生成 |

---

## 8. 权限与状态控制说明

### 8.1 权限控制

- 首页路由位于父路由 `/` 下。
- 父路由要求登录：`meta.requiresAuth = true`
- 首页本身没有独立 `requiredPermissions`
- 代码中未发现页面内部按钮、区块、图表的权限判断

### 8.2 路由守卫

相关文件：
- `D:\my-vue-project\wind-power-forecast\frontend\src\router\index.js`

结论：
- 未登录用户访问首页会被重定向到 `/login`
- 已登录用户正常进入首页

### 8.3 状态控制

- 页面级加载态：`loading`
- 事件标签状态：`activeEventTab`
- 事件滚动定时器：`eventTicker`
- 场站监听器句柄：`farmListener`

### 8.4 共享状态联动

首页最关键的共享状态是“当前场站”：

1. `FarmSelector` 变更场站
2. `farmService.setCurrentFarm()` 写入 `localStorage.selectedFarm`
3. `farmService.notifyListeners()` 通知所有订阅页面
4. 首页收到通知后重拉数据

---

## 9. 风险点 / 待确认点

### 9.1 代码中已确认的风险点

1. 天气区目前没有真实天气接口。
   - `getDashboardWeatherSnapshot()` 仅根据场站数和当前场站拼出前端假数据

2. 首页大量依赖 fallback 数据。
   - 趋势图、排名图、事件流、场站列表都有 fallback
   - 如果后端接口不可用，页面仍可展示，但可能掩盖真实故障

3. 首页服务层吞掉了不少异常。
   - 页面本身几乎不会显示错误态
   - 更偏向“可展示优先”，不利于问题暴露

4. `FleetMap` 实际是状态矩阵，不是地图。
   - 组件命名与实际功能不一致，可能影响后续理解

5. 事件轮播是通过重排原数组实现的。
   - 若后续希望保留原始顺序或做分页/详情，当前实现会带来副作用

### 9.2 代码中未明确的事项

1. 首页标题、部分中文文案在终端读取中存在乱码，需结合编辑器确认展示文案。
2. `getPowerCompareData()` 的完整后端返回 schema，代码中未明确，只能从服务层猜候选字段。
3. 首页 KPI 是否有正式产品口径定义，代码中未发现说明文档。

### 9.3 需结合后端确认

1. 功率对比接口返回的标准字段名集合。
2. 上报日志接口中的状态字段枚举。
3. 首页天气区是否本应接入真实气象接口。
4. KPI 指标计算口径是否与业务规则一致。

---

## 10. 代码证据清单

### 页面组件

- `D:\my-vue-project\wind-power-forecast\frontend\src\components\HomePage.vue`
  - 组件：`HomePage`
  - 函数：`loadData`
  - 函数：`windLevelStyle`
  - 函数：`startEventTicker`
  - computed：`filteredEvents`
  - computed：`scrollingEvents`

### 子组件

- `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\KpiCards.vue`
  - 组件：`KpiCards`
  - 函数：`resolveIcon`
  - 函数：`ringStyle`

- `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\PowerTrendChart.vue`
  - 组件：`PowerTrendChart`
  - 函数：`resolveNowIndex`
  - 函数：`render`

- `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\StationRankChart.vue`
  - 组件：`StationRankChart`
  - 函数：`render`

- `D:\my-vue-project\wind-power-forecast\frontend\src\components\dashboard\FleetMap.vue`
  - 组件：`FleetMap`
  - 常量来源：`TASK_KEYS`
  - 函数：`statusSymbol`

### 服务层

- `D:\my-vue-project\wind-power-forecast\frontend\src\services\dashboardService.js`
  - 常量：`TASK_KEYS`
  - 函数：`getDashboardOverview`
  - 函数：`getDashboardTrend`
  - 函数：`getDashboardStationRank`
  - 函数：`getDashboardWeatherSnapshot`
  - 函数：`getDashboardEvents`
  - 函数：`extractSeriesFromPowerCompare`
  - 函数：`mergeTrendSeries`
  - 函数：`buildTaskMatrix`
  - 函数：`summarizeReportCompletion`

### 场站共享上下文

- `D:\my-vue-project\wind-power-forecast\frontend\src\utils\farmService.js`
  - 函数：`loadAvailableFarms`
  - 函数：`getCurrentFarm`
  - 函数：`addListener`
  - 函数：`removeListener`
  - 函数：`notifyListeners`

### 接口层

- `D:\my-vue-project\wind-power-forecast\frontend\src\api\farmApi.js`
  - 函数：`getFarms`
  - 函数：`getAutoPredictFarms`
  - 函数：`getReportFarms`

- `D:\my-vue-project\wind-power-forecast\frontend\src\api\powerCompareApi.js`
  - 函数：`getPowerCompareData`

- `D:\my-vue-project\wind-power-forecast\frontend\src\api\reportApi.js`
  - 函数：`getReportLogs`

---

## 附：隐性逻辑专项检查

| 检查项 | 结论 |
|---|---|
| 轮询 | 代码中未发现接口轮询 |
| 自动刷新 | 无接口自动刷新；只有场站切换触发重载；事件区有自动滚动 |
| 防抖/节流 | 代码中未发现 |
| 缓存 | 通过 `farmService` 缓存场站列表；当前场站存在 `localStorage.selectedFarm` |
| URL query 同步 | 代码中未发现 |
| 本地存储 | 间接使用 `localStorage.selectedFarm`、`localStorage.user` |
| 权限指令 | 代码中未发现 |
| 路由守卫 | 有，全局守卫控制登录态 |
| 条件渲染 | 天气区 `v-if="weatherMode === 'fleet'"`；事件筛选通过 computed |
| mock 数据 | 天气、趋势图、排名图、事件流、场站列表均有 fallback/mock 数据 |
| 假数据兜底 | 已确认大量存在 |
| 导出下载 | 代码中未发现 |
| 上传导入 | 代码中未发现 |
| WebSocket/SSE | 首页代码中未发现 |
| 埋点日志 | 代码中未发现 |
| 错误边界 | 代码中未发现专门错误边界；服务层主要吞错并 fallback |
