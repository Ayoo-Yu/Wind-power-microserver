# 功率可视化对比页面代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 功率可视化对比 |
| 所属模块 | 分析与报表 |
| 路由路径 | `/powercompare` |
| 页面入口文件 | [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) |
| 页面依赖的子组件 | [LoadingIndicator.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/LoadingIndicator.vue) |
| 页面依赖的 store/hooks/model/service/api 文件 | [powerCompareApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/powerCompareApi.js)、[farmService.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/farmService.js)、[router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)、[AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) |
| 页面是否受权限控制 | 是。路由 `meta.requiredPermissions = ['view_all_data']`；侧边栏菜单通过 `hasPermission('view_all_data')` 控制显示；但全局路由守卫当前只校验登录态，代码中未发现按 `requiredPermissions` 做强制拦截 |

### 1.2 页面定位

该页面是一个“单站深度分析 + 多站横向对比”的综合分析页，当前实现承担以下职责：

- 按时间范围查询单场站多条功率/风速序列
- 计算短期、超短期的精度与合格率
- 绘制主曲线、误差曲线、风速-功率散点图
- 按多场站汇总精度指标并画柱状图
- 导出原始对比数据、导出指标、导出当前图表 PNG

### 1.3 关键事实

1. 页面主逻辑全部集中在 [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue)，没有进一步拆分为业务子组件。
2. 页面使用 ECharts 直接在本页面内渲染 4 类图表，没有统一图表封装层。
3. 单站模式依赖 `getPowerCompareData()`，多站模式依赖 `getFleetMetrics()`。
4. 多个指标不是后端直接返回，而是页面按 RMSE/装机容量等公式二次计算。
5. 页面与 `farmService` 有双向联动，但代码中未发现读取路由 query 参数，因此【状态监控】跳转带来的 `farm_code/prediction_type` 不会被直接消费。

---

## 2. 页面结构树

```text
功率可视化对比 PowerCompare.vue
├─ 页面标题
├─ 分析模式 Tabs
│  ├─ 单站深度分析
│  └─ 多站横向对比
├─ KPI 摘要卡片区
├─ 控制区 el-card
│  ├─ Group 1: 数据范围定义
│  │  ├─ 场站选择（单站 / 多站）
│  │  ├─ 时间范围选择
│  │  ├─ 快捷时间按钮
│  │  └─ 查询按钮
│  ├─ Group 2: 图表展示控制
│  │  ├─ 数据类型 checkbox group
│  │  ├─ 可用容量线开关
│  │  └─ 限电标识开关
│  └─ Group 3: 数据与报表导出
│     └─ 导出下拉菜单
├─ 单站模式区域
│  ├─ 单站视图 Tabs
│  │  ├─ 曲线分析
│  │  └─ 散点图
│  ├─ 主曲线图
│  ├─ 误差图
│  └─ 风速-功率散点图
├─ 多站模式区域
│  ├─ 多站精度对比柱状图
│  └─ 多场站指标表
├─ 空态卡片
└─ 全屏 LoadingIndicator
```

---

## 3. 区块说明

### 3.1 页面头部与模式切换区

| 项目 | 说明 |
|---|---|
| 区块名称 | 页面头部与模式切换区 |
| 对应组件名 | `PowerCompare` |
| 文件路径 | [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) |
| 展示内容 | 页面标题、分析模式 Tab |
| 数据来源 | `analysisTab` 本地状态 |
| 是否可交互 | 是 |
| 是否有权限控制 | 页面进入受菜单/路由权限控制；区块内部无额外权限判断 |
| 是否有定时刷新或自动更新 | 否 |

说明：

- `analysisTab` 在 `single` 和 `fleet` 之间切换。
- 切换后通过 watcher 自动重新调用 `fetchComparisonData()`。

### 3.2 KPI 摘要卡片区

| 项目 | 说明 |
|---|---|
| 区块名称 | KPI 摘要卡片区 |
| 对应组件名 | `PowerCompare` |
| 文件路径 | [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) |
| 展示内容 | 4 张摘要卡，单站和多站模式下内容不同 |
| 数据来源 | `kpiCards` 计算属性 |
| 是否可交互 | 否 |
| 是否有权限控制 | 否 |
| 是否有定时刷新或自动更新 | 否，取决于查询结果与模式切换 |

关键事实：

- 单站模式下卡片来自 `singleMetricsSummary`。
- 多站模式下卡片来自 `fleetCompareRows` 的平均值、总计值再计算。
- KPI 文案在页面前端拼装，不是接口原样返回。

### 3.3 查询控制区

| 项目 | 说明 |
|---|---|
| 区块名称 | 查询控制区 |
| 对应组件名 | `PowerCompare` |
| 文件路径 | [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) |
| 展示内容 | 场站选择、时间范围、快捷时间、查询按钮、数据类型筛选、容量线/限电开关、导出菜单 |
| 数据来源 | `singleFarmCode`、`fleetCompareFarmCodes`、`timeRange`、`selectedTypes`、`showCapacityLine`、`showCurtailmentTag`、`fleetCompareFarms` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现按钮级权限控制 |
| 是否有定时刷新或自动更新 | 否 |

关键事实：

- 单站模式显示单选场站下拉，多站模式显示多选下拉。
- 场站列表来自 `farmService.loadAvailableFarms(true)`。
- 快捷时间按钮点击后会立即重新查询，不只是修改日期。
- 数据类型复选框、容量线开关、限电开关只影响单站图表渲染，不会再次请求接口。

### 3.4 单站图表区

| 项目 | 说明 |
|---|---|
| 区块名称 | 单站图表区 |
| 对应组件名 | `PowerCompare` |
| 文件路径 | [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) |
| 展示内容 | 曲线分析 Tab、主曲线图、误差图、散点图 |
| 数据来源 | `singleSeriesState`、`chartData`、`selectedTypes`、`showCapacityLine`、`showCurtailmentTag` |
| 是否可交互 | 是 |
| 是否有权限控制 | 否 |
| 是否有定时刷新或自动更新 | 否。切换 Tab 或复选框时会本地重绘 |

关键事实：

- 主曲线图是双 Y 轴，左轴功率、右轴风速。
- 误差图由短期误差柱状图、超短期误差折线、0 轴组成。
- 散点图用“风速-功率”点对绘制。
- 图表依赖 `singleSeriesState`，这是接口数据经前端对齐和重组后的结果，不是后端原样结构。

### 3.5 多站图表与明细表区

| 项目 | 说明 |
|---|---|
| 区块名称 | 多站图表与明细表区 |
| 对应组件名 | `PowerCompare` |
| 文件路径 | [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) |
| 展示内容 | 多站精度柱状图、指标表 |
| 数据来源 | `fleetCompareRows` |
| 是否可交互 | 有限交互。图表支持缩放，表格只读 |
| 是否有权限控制 | 否 |
| 是否有定时刷新或自动更新 | 否 |

关键事实：

- 多站模式只请求短期和超短期两套指标，不查询中期。
- `fleetCompareRows` 中的 `short_acc`、`supershort_acc`、`qualified_rate` 等值是前端基于 `rmse / installedCapacity` 推导，不一定是后端直接返回的“官方考核值”。

### 3.6 空态与加载区

| 项目 | 说明 |
|---|---|
| 区块名称 | 空态与加载区 |
| 对应组件名 | `PowerCompare` + `LoadingIndicator` |
| 文件路径 | [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue)、[LoadingIndicator.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/LoadingIndicator.vue) |
| 展示内容 | “暂无数据”提示卡片、全屏加载遮罩 |
| 数据来源 | `loading`、`showEmptyState` |
| 是否可交互 | 否 |
| 是否有权限控制 | 否 |
| 是否有定时刷新或自动更新 | 由请求状态变化驱动 |

---

## 4. 组件明细表

### 4.1 页面主组件 `PowerCompare`

| 项目 | 说明 |
|---|---|
| 组件名称 | `PowerCompare` |
| 文件路径 | [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) |
| 父子关系 | 路由页面组件；子组件为 `LoadingIndicator` |
| props / emits / callbacks | 无 props / emits；通过 `farmService.addListener(this.handleFarmChanged)` 接收全局场站变化 |
| 内部 state / computed / hooks / store 使用情况 | 使用 Options API；状态集中在 `data()`；无 Vuex/Pinia；依赖 `farmService` 单例 |
| 生命周期或副作用逻辑 | `mounted` 初始化时间范围、场站列表、默认场站、首次查询、窗口 resize 监听；`beforeUnmount` 移除监听并销毁图表 |
| 实现的具体功能 | 单站/多站切换查询、图表渲染、指标计算、导出、图表重绘 |
| 触发了哪些接口 | `getPowerCompareData`、`getFleetMetrics`；初始化前还会通过 `farmService.loadAvailableFarms(true)` 间接触发场站列表接口 |
| 与其他组件的联动关系 | 与 `farmService` 双向同步场站；子组件 `LoadingIndicator` 跟随 `loading`；图表与导出依赖同一份 `singleSeriesState/exportData` |
| 加载态 / 空态 / 异常态如何处理 | `LoadingIndicator` 覆盖全屏；`showEmptyState` 控制空态；接口错误未在本页显式 catch，异常处理主要依赖上层 Promise 抛错，代码中未发现统一错误弹窗 |

#### 4.1.1 关键本地状态

- `analysisTab`
  - `single` 或 `fleet`
- `singleViewTab`
  - `curve` 或 `scatter`
- `timeRange`
  - `datetimerange` 的开始结束时间
- `loading`
  - 全屏加载状态
- `chartData`
  - 单站接口返回的原始数据容器
- `fleetCompareFarms`
  - 可选场站列表
- `singleFarmCode`
  - 单站模式当前场站
- `fleetCompareFarmCodes`
  - 多站模式已选场站数组
- `selectedTypes`
  - 主曲线中需要展示的数据序列类型
- `showCapacityLine`
  - 是否渲染可用容量线
- `showCurtailmentTag`
  - 是否渲染限电时段标记
- `installedCapacity`
  - 装机容量基准，初始 453.5，后续会被查询结果动态扩大
- `mainChart/errorChart/scatterChart/fleetBarChart`
  - 四个 ECharts 实例
- `exportData`
  - 导出所需的原始序列和指标摘要
- `singleSeriesState`
  - 单站图表统一状态容器
- `singleMetricsSummary`
  - 单站 KPI 指标汇总
- `fleetCompareRows`
  - 多站汇总表格数据

#### 4.1.2 计算属性与核心加工逻辑

1. `showEmptyState`
- 单站模式：`!chartData`
- 多站模式：`fleetCompareRows.length === 0`

2. `kpiCards`
- 单站模式下读取 `singleMetricsSummary`
- 多站模式下对 `fleetCompareRows` 进行再次聚合：
  - 平均短期准确率
  - 平均超短期准确率
  - 平均 RMSE
  - 不合格点总和

3. `formatPct/formatNum/mean`
- 都是本地格式化和统计函数
- 返回 `'--'` 作为空值显示兜底

4. `getSeries(apiData, names)`
- 用模糊匹配从接口返回对象里找到某一类数据序列
- 比较规则是去掉空格和下划线后做包含判断
- 说明接口字段名可以是中文，也可以是英文近似名

5. `alignedSeries(baseSeries, targetSeries, valueKey)`
- 以 `baseSeries` 时间戳为主轴
- 构建 target 的 `timestamp -> value` 映射
- 没找到对应时间点则补 `null`
- 这是单站图表多序列对齐的关键逻辑

6. `calcMetrics(actual, predicted)`
- 前端自行计算：
  - `mae`
  - `rmse`
  - `mse`
  - `acc = 1 - rmse / installedCapacity`
  - `k`
  - `unqualifiedPoints`
  - `pe`
- 阈值为 `0.2 * installedCapacity`

7. `calcDailyStats(actualSeries, predSeries, qualifiedThreshold)`
- 先按天分桶
- 每天调用 `calcMetrics`
- 再得到：
  - `avgAcc`
  - `qualifiedRate`

#### 4.1.3 生命周期和副作用

`mounted()` 执行流程：

1. 初始化当天 00:00:00 ~ 23:59:59 时间范围
2. 调用 `loadFleetCompareFarms()`
3. 将 `singleFarmCode` 设置为：
   - `farmService.getCurrentFarm()` 或
   - `fleetCompareFarms[0].code`
4. 多站模式默认 `fleetCompareFarmCodes = 全部场站`
5. 注册 `farmService` 监听
6. 首次调用 `fetchComparisonData()`
7. 注册 `window.resize` 监听以便图表自适应

`beforeUnmount()`：

- 移除 `farmService` 监听
- 移除窗口 resize 监听
- 销毁全部图表实例

#### 4.1.4 关键方法链路

1. `fetchComparisonData()`
- 校验时间范围
- 根据 `analysisTab` 分发到：
  - `fetchSingleStationData()`
  - `fetchFleetCompareData()`
- 用 `loading` 包裹

2. `fetchSingleStationData()`
- 取 `singleFarmCode || farmService.getCurrentFarm()`
- 调用 `farmService.setCurrentFarm(farmCode)`
- 请求 `getPowerCompareData(payload)`
- 从接口返回中提取：
  - 实测值
  - 超短期预测
  - 短期预测
  - 中期预测
  - 短期风速预测
  - 中期风速预测
  - 可用容量
  - 限电
  - 风向
- 按实测序列排序作为主时间轴
- 调用 `alignedSeries()` 生成多条对齐序列
- 用本地公式计算单站指标
- 写入 `singleMetricsSummary`
- 写入 `singleSeriesState`
- 写入 `exportData`
- `nextTick` 后绘制单站图表

3. `fetchFleetCompareData()`
- 校验至少选择一个场站
- 并发请求：
  - `getFleetMetrics(... prediction_type: 'short')`
  - `getFleetMetrics(... prediction_type: 'supershort')`
- 把两次返回按 `farm_code` 合并
- 用 `rmse/installedCapacity` 推导准确率和合格率
- 写入 `fleetCompareRows`
- 写入 `exportData.metrics`
- `nextTick` 后绘制柱状图

4. 导出链路
- `handleExportCommand(command)` 分发三种导出
- `downloadRawCSV()`
  - 基于 `exportData.comparison` 生成 CSV
- `downloadMetricsExcel()`
  - 实际是构造 HTML table，以 `.xls` 下载
- `downloadChartPNG()`
  - 调用 ECharts `getDataURL()`

#### 4.1.5 加载态 / 空态 / 异常态

- 加载态
  - `loading` 驱动 `LoadingIndicator`
- 空态
  - `showEmptyState` + 空态卡片
- 异常态
  - `fetchComparisonData()` 里没有 `catch`
  - `fetchSingleStationData()` / `fetchFleetCompareData()` 也没有本页级别错误捕获
  - 仅输入校验时用 `this.$message.warning`
  - 结论：真实接口异常时的可见反馈代码中未明确，需结合全局拦截器确认

### 4.2 加载遮罩组件 `LoadingIndicator`

| 项目 | 说明 |
|---|---|
| 组件名称 | `LoadingIndicator` |
| 文件路径 | [LoadingIndicator.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/LoadingIndicator.vue) |
| 父子关系 | 被 `PowerCompare` 引用 |
| props / emits / callbacks | `visible: Boolean`、`message: String`；无 emits |
| 内部 state / computed / hooks / store 使用情况 | 无 |
| 生命周期或副作用逻辑 | 无 |
| 实现的具体功能 | 以 fixed 遮罩形式显示加载动画和文案 |
| 触发了哪些接口 | 无 |
| 与其他组件的联动关系 | 完全由父组件 `loading` 和 `message` 驱动 |
| 加载态 / 空态 / 异常态如何处理 | 只处理加载态，不处理空态或错误态 |

补充说明：

- 默认文案在文件中有乱码，但本页实际传入 `message="数据加载中..."`。
- 组件内部使用 `el-spinner`，没有业务逻辑。

---

## 5. 交互明细表

### 5.1 顶部模式与 KPI 区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| Tab | 页面顶部 | 单站深度分析 / 多站横向对比 | 切换分析模式 | 更新 `analysisTab`，watcher 触发 `fetchComparisonData()` | 否 | 是 | 切换后影响 KPI、查询条件、图表区、导出内容 |
| 卡片 | KPI 区 | 4 张摘要卡 | 展示指标摘要 | 只读 | 否 | 否 | 跟随查询结果变化 |

### 5.2 查询区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 下拉框 | Group 1 | 单站场站选择 | 选择单站模式场站 | 更新 `singleFarmCode`，watcher 同步到 `farmService`；不会立即查询，需点击“查询”或场站全局监听触发 | 否 | 间接影响后续请求 | 影响单站查询目标场站 |
| 下拉框 | Group 1 | 多站场站多选 | 选择多站模式场站集合 | 更新 `fleetCompareFarmCodes` | 否 | 否 | 影响多站查询目标 |
| 日期选择器 | Group 1 | 开始/结束时间 | 选择时间范围 | 更新 `timeRange` | 否 | 否 | 影响后续查询参数 |
| 按钮组 | Group 1 | 今日 / 近三天 / 近一周 | 快速设置时间范围 | 调用 `setQuickTimeRange()`，更新 `timeRange` 后立即触发查询 | 否 | 是 | 影响查询结果、图表、KPI |
| 按钮 | Group 1 | 查询 | 手动查询 | 调用 `fetchComparisonData()` | 否 | 是 | 刷新全页核心数据 |

### 5.3 图表控制区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 复选框组 | Group 2 | 实测值/超短期预测/短期预测/中期预测/短期风速预测/中期风速预测 | 控制主曲线图显示哪些序列 | 更新 `selectedTypes`，watcher 本地重绘单站图表 | 否 | 否 | 影响主曲线图与导出原始数据字段集合 |
| 开关 | Group 2 | 显示可用容量线 | 控制主图是否叠加容量线 | 更新 `showCapacityLine`，watcher 本地重绘 | 否 | 否 | 影响主曲线图和导出数据内容 |
| 开关 | Group 2 | 显示限电标识 | 控制主图是否标出限电时段 | 更新 `showCurtailmentTag`，watcher 本地重绘 | 否 | 否 | 影响主曲线图 `markArea` |

### 5.4 导出区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 下拉菜单 | Group 3 | 导出报表 | 展示三种导出类型 | 触发 `handleExportCommand` | 否 | 否 | 无 |
| 菜单项 | 导出下拉 | 导出原始数据(CSV) | 导出单站时序数据 | 调用 `downloadRawCSV()` | 否 | 否 | 无 |
| 菜单项 | 导出下拉 | 导出考核指标(Excel) | 导出单站/多站指标 | 调用 `downloadMetricsExcel()` | 否 | 否 | 无 |
| 菜单项 | 导出下拉 | 导出图表(PNG) | 导出当前图表截图 | 调用 `downloadChartPNG()` | 否 | 否 | 无 |

### 5.5 单站图表区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| Tab | 单站模式 | 曲线分析 / 风机出力特性（散点图） | 切换单站图表视图 | 更新 `singleViewTab`，watcher 本地重绘 | 否 | 否 | 影响显示的图表区域和 PNG 导出目标 |
| 图表 | 单站模式 | 主曲线（双 Y 轴） | 展示功率/风速/容量/限电时段 | 支持 ECharts tooltip、dataZoom | 否 | 否 | 无 |
| 图表 | 单站模式 | 误差曲线 | 展示短期/超短期误差 | 支持 tooltip、dataZoom | 否 | 否 | 无 |
| 图表 | 单站模式 | 风速-功率散点图 | 展示风速和实际功率关系 | 支持 tooltip | 否 | 否 | 无 |

### 5.6 多站图表区

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 图表 | 多站模式 | 多站准确率对比 | 展示短期/超短期准确率柱状图 | 支持 tooltip、dataZoom | 否 | 否 | 无 |
| 表格 | 多站模式 | 多场站详细指标表 | 展示 farm_code、farm_name、准确率、合格率、RMSE、MAE、不合格点 | 只读 | 否 | 否 | 无 |

### 5.7 页面中未发现的元素

- 文本输入框：代码中未发现
- 弹窗/抽屉：代码中未发现
- 上传导入：代码中未发现
- 刷新按钮：无单独刷新，依赖“查询”或快捷时间
- 保存/提交：代码中未发现
- Tooltip 组件：未显式使用 `el-tooltip`，但 ECharts 自带 tooltip
- 状态图标：代码中未发现业务状态 icon

---

## 6. 接口明细表

### 6.1 页面直接使用的接口

| 接口名称 | 请求方法 | URL | 所在 api/service 文件 | 调用函数名 | 调用触发条件 | 请求参数 | 返回数据结构 | 返回数据映射位置 | 失败时页面处理 |
|---|---|---|---|---|---|---|---|---|---|
| 单站功率对比数据 | POST | `/api/v1/power-compare/data`，回退 `/power-compare/data` | [powerCompareApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/powerCompareApi.js) | `getPowerCompareData(payload)` | 首次进入页面默认查询、点击查询、快捷时间按钮、切换全局当前场站且当前处于单站模式时 | `{ start, end, types, farm_code, supershort_horizon: 'average' }` | 页面按 `response?.data?.data || response?.data || {}` 解包；预期为一个对象，内部包含若干按类型命名的数组序列；每个序列项至少含 `timestamp`，功率类含 `power`，风速类含 `wind_speed`，风向类含 `wind_direction`，容量类含 `available_capacity`，限电类含 `value`；完整字段代码中未明确 | 映射到 `chartData`，再通过 `getSeries/alignedSeries` 生成 `singleSeriesState`；并参与 `singleMetricsSummary` 和 `exportData.comparison` 构造 | 本页未显式 catch，代码中未发现用户可见错误弹窗；需结合全局拦截器确认 |
| 多站考核指标 | POST | `/api/v1/power-compare/fleet_metrics`，回退 `/power-compare/fleet_metrics` | [powerCompareApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/powerCompareApi.js) | `getFleetMetrics(payload)` | 多站模式下首次进入、点击查询、快捷时间按钮、切换模式后自动查询 | `{ start, end, farm_codes, prediction_type }`，其中页面分别请求 `short` 和 `supershort` 两次 | 页面读取 `response?.data?.data?.items || []`；每个 item 预期至少包含 `farm_code`、`farm_name`、`rmse`、`mae`、`points`；完整结构代码中未明确 | 映射到 `fleetCompareRows`，并驱动多站 KPI、柱状图和指标表 | 本页未显式 catch，代码中未发现页面级错误反馈 |

### 6.2 页面初始化间接依赖的接口

页面初始化会通过 `farmService.loadAvailableFarms(true)` 间接拉取场站列表，具体接口在 [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js) 中定义。本轮由于本页直接依赖的是 `farmService`，接口级说明沿用已确认链路：

- `getAutoPredictFarms()`
- `getReportFarms()`
- `getFarms()`

这些接口用于构造 `fleetCompareFarms`，从而驱动场站选择器。

### 6.3 页面未使用但同文件存在的接口

| 接口名称 | 请求方法 | URL | 文件 | 当前页面是否使用 | 说明 |
|---|---|---|---|---|---|
| 多站时序对比接口 | POST | `/api/v1/power-compare/fleet_series`，回退 `/power-compare/fleet_series` | [powerCompareApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/powerCompareApi.js) | 否 | 当前页面没有使用该接口，多站模式只取 metrics，不取多站时序序列 |

### 6.4 接口返回后的前端二次映射

#### 单站模式

接口返回后，页面会做以下加工：

1. 用 `getSeries()` 按名称模糊提取各类序列
2. 以“实测值”排序后序列作为主时间轴
3. 通过 `alignedSeries()` 对齐其它序列
4. 对 `capacitySeries` 做兜底：
   - 若没有有效容量序列，则整段使用 `installedCapacity`
5. 对 `installedCapacity` 做动态更新：
   - 取实际值、预测值、容量值中的最大值，再乘以 `1.1`
6. 计算：
   - `shortDaily`
   - `superDaily`
   - `shortMetrics`
   - `superMetrics`
7. 写入 `singleMetricsSummary`

#### 多站模式

接口返回后，页面会做以下加工：

1. 先用短期结果初始化 `Map`
2. 再把超短期结果合并进去
3. 通过 `rmse / installedCapacity` 推导：
   - `short_acc`
   - `short_qualified_rate`
   - `supershort_acc`
   - `supershort_qualified_rate`
4. 对 `rmse_avg` 和 `mae_avg` 做平均
5. 用阈值规则累加 `unqualified_points`

结论：

- 页面展示的准确率/合格率很大一部分是前端计算结果，不是接口直接返回。

---

## 7. 数据流说明

### 7.1 初始化加载流程

1. 进入 `/powercompare` 页面。
2. `mounted()` 设置当天时间范围。
3. 调用 `loadFleetCompareFarms()`。
4. `loadFleetCompareFarms()` 调 `farmService.loadAvailableFarms(true)` 获取场站集合。
5. 页面设置：
   - `singleFarmCode = farmService.getCurrentFarm() || firstFarm`
   - `fleetCompareFarmCodes = 全部场站 code`
6. 注册 `farmService.addListener(this.handleFarmChanged)`。
7. 调用 `fetchComparisonData()`。
8. 默认 `analysisTab = 'single'`，因此首次走 `fetchSingleStationData()`。
9. 单站数据请求完成后：
   - `chartData`
   - `singleSeriesState`
   - `singleMetricsSummary`
   - `exportData`
10. `nextTick` 后绘制图表。

### 7.2 用户操作后数据如何变化

#### 7.2.1 切换分析模式

1. 用户切换 `analysisTab`
2. watcher 自动调用 `fetchComparisonData()`
3. 如果切到 `single`：
   - 查询单站数据
   - 更新单站图表和指标
4. 如果切到 `fleet`：
   - 查询多站 metrics
   - 更新柱状图和表格

#### 7.2.2 切换场站

单站模式：

1. 用户选择 `singleFarmCode`
2. watcher 触发 `farmService.setCurrentFarm(newCode)`
3. 页面本身不会仅凭这个 watcher 自动查询
4. 但如果其他地方改了 `farmService` 当前场站，`handleFarmChanged` 会在单站模式下自动查询

多站模式：

- 用户修改 `fleetCompareFarmCodes`
- 仅更新本地状态
- 需点击“查询”或切换模式后才重新请求

#### 7.2.3 切换时间范围

- 直接修改 `timeRange` 不会自动请求
- 点击“查询”或快捷时间按钮才会触发请求

#### 7.2.4 快捷时间按钮

- `setQuickTimeRange(period)` 会：
  - 修改 `timeRange`
  - 立即调用 `fetchComparisonData()`

#### 7.2.5 切换数据类型/容量线/限电标识

- 这些操作不重新请求接口
- 只在单站模式下通过 watcher 调用 `renderSingleCharts()`
- 属于“本地重绘”

#### 7.2.6 切换单站视图 Tab

- `singleViewTab` watcher 调用 `renderSingleCharts()`
- 在 `curve` 下绘制主图+误差图
- 在 `scatter` 下绘制散点图

### 7.3 哪些状态是本地状态

- `analysisTab`
- `singleViewTab`
- `timeRange`
- `loading`
- `chartData`
- `singleFarmCode`
- `fleetCompareFarmCodes`
- `selectedTypes`
- `showCapacityLine`
- `showCurtailmentTag`
- `installedCapacity`
- `singleSeriesState`
- `singleMetricsSummary`
- `fleetCompareRows`
- `exportData`
- 图表实例对象

### 7.4 哪些状态来自全局 store / 全局单例

- `farmService.getCurrentFarm()` 当前场站
- `farmService.loadAvailableFarms(true)` 返回的可用场站集合

代码中未发现 Vuex/Pinia。

### 7.5 哪些数据来自后端接口

单站模式来自后端：

- 实测功率序列
- 超短期、短期、中期预测序列
- 风速预测序列
- 可用容量序列
- 限电序列
- 风向序列

多站模式来自后端：

- `rmse`
- `mae`
- `points`
- `farm_code`
- `farm_name`

### 7.6 哪些字段经过二次加工/格式化

前端二次加工包括：

- `labels`
- `actualValues/superValues/shortValues/midValues`
- `shortWindValues/midWindValues/windDirectionValues`
- `capacityValues`
- `curtailmentValues`
- `singleMetricsSummary`
- `fleetCompareRows.short_acc`
- `fleetCompareRows.short_qualified_rate`
- `fleetCompareRows.supershort_acc`
- `fleetCompareRows.supershort_qualified_rate`
- `fleetCompareRows.rmse_avg/mae_avg`
- 所有导出数据结构

---

## 8. 权限与状态控制说明

### 8.1 权限控制

1. 路由级
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - `/powercompare`
  - `meta.requiredPermissions = ['view_all_data']`

2. 菜单级
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - `/powercompare` 菜单项条件：`hasPermission('view_all_data')`

3. 实际路由守卫
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js) `beforeEach`
  - 当前只检查登录态
  - 代码中未发现按 `requiredPermissions` 拦截

4. 页面内部动作权限
- 查询、导出、切换图表类型等页面内操作未发现额外权限判断

### 8.2 状态控制

1. 加载控制
- `loading` 控制 `LoadingIndicator`

2. 图表实例控制
- `destroyAllCharts()` 负责统一销毁，防止页面卸载后泄漏

3. 空态控制
- `showEmptyState`

4. 图表重绘控制
- `selectedTypes/showCapacityLine/showCurtailmentTag/singleViewTab` 的 watcher 只做重绘，不发请求

5. 查询参数控制
- `timeRange` 不完整时，直接 `this.$message.warning` 并 return
- 多站未选场站时，同样 warning 并 return

---

## 9. 风险点/待确认点

### 9.1 风险点

1. 页面没有显式接口异常处理
- `fetchComparisonData/fetchSingleStationData/fetchFleetCompareData` 没有 `catch`
- 真实异常反馈依赖全局 axios 拦截或浏览器控制台，页面层证据不足

2. 多数关键指标是前端推导，不是后端直接下发
- 包括准确率、合格率、考核电量估计等
- 若后端口径不同，页面展示可能与正式报表不一致

3. `installedCapacity` 会被动态改写
- 初始值 453.5
- 查询后按最大序列值 * 1.1 更新
- 这会直接影响后续 `acc/qualifiedRate/unqualifiedPoints/pe` 的计算结果
- 该逻辑更像显示层估算，不像固定业务口径

4. 路由 query 未消费
- 【状态监控】跳转该页时会带 `farm_code` 和 `prediction_type`
- 当前页面代码中未发现 `useRoute` / `$route.query`
- 因此页面不会自动按跳转参数定位到指定场站或预测类型

5. 多站模式只统计短期与超短期
- 中期预测没有进入多站横向对比
- 是否符合业务要求需确认

6. 导出“Excel”本质是 HTML 表格伪装成 `.xls`
- 对复杂兼容性和二次处理能力有限

### 9.2 待确认点

- `getPowerCompareData()` 的真实返回字段名和序列命名规范，需结合后端确认
- `fleet_metrics` 是否本应由后端直接返回准确率/合格率，还是前端计算设计如此，需结合后端确认
- `prediction_type` query 是否原本计划用于默认聚焦特定曲线，当前代码中未实现
- `available_capacity` 和 `curtailment` 的业务口径需结合后端确认
- 页面文案在终端存在乱码，需结合编辑器核对实际显示文本

---

## 10. 代码证据清单

### 10.1 页面主文件

- [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue)
  - `mounted`
  - `beforeUnmount`
  - `loadFleetCompareFarms`
  - `fetchComparisonData`
  - `fetchSingleStationData`
  - `fetchFleetCompareData`
  - `getSeries`
  - `alignedSeries`
  - `calcMetrics`
  - `calcDailyStats`
  - `buildCurtailmentMarkAreas`
  - `getMainSeriesFromState`
  - `renderMainChart`
  - `renderErrorChart`
  - `renderScatterChart`
  - `renderFleetBarChart`
  - `handleExportCommand`
  - `downloadRawCSV`
  - `downloadMetricsExcel`
  - `downloadChartPNG`
  - `downloadBlob`

### 10.2 子组件

- [LoadingIndicator.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/LoadingIndicator.vue)
  - `props.visible`
  - `props.message`

### 10.3 API 与上下文

- [powerCompareApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/powerCompareApi.js)
  - `getPowerCompareData`
  - `getFleetMetrics`
  - `getFleetSeries`（当前页未使用）
- [farmService.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/farmService.js)
  - `loadAvailableFarms`
  - `getCurrentFarm`
  - `setCurrentFarm`
  - `addListener`
  - `removeListener`

### 10.4 路由与权限

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - `/powercompare` 路由
  - `meta.requiredPermissions = ['view_all_data']`
  - `beforeEach`
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - `/powercompare` 菜单显示条件
  - `hasPermission`

### 10.5 跨页面联动证据

- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)
  - `openFarmCurve(row)`：跳转 `PowerCompare` 并携带 `farm_code/prediction_type`

---

## 关键代码证据清单

- [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue)
- [powerCompareApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/powerCompareApi.js)
- [LoadingIndicator.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/LoadingIndicator.vue)
- [farmService.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/farmService.js)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)

## 可能遗漏点检查清单

- 当前文档基于静态代码；若 ECharts option 在运行时被外部插件修改，本次未覆盖
- 页面没有显式错误处理，真实运行态提示方式需结合拦截器或控制台进一步确认
- `fleet_series` 接口当前页未使用，若后续版本接入多站时序对比，需要重新补充分析
- 文案终端乱码不影响函数、字段、依赖和交互链路识别，但最终 Wiki 展示文本建议用编辑器复核
