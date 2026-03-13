# 人工修正工作台页面代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 人工修正工作台 |
| 所属模块 | 预测与控制 |
| 路由路径 | `/manual-workspace` |
| 页面入口文件 | [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue) |
| 页面依赖的子组件 | 代码中未发现自定义子组件；页面仅使用 Element Plus 基础组件和原生 `svg/polyline/line` |
| 页面依赖的 store/hooks/model/service/api 文件 | 代码中未发现自定义 store/hooks/model/service/api 引入；仅引入 Vue `ref/computed` 与 Element Plus `ElMessage` |
| 页面是否受权限控制 | 是。路由 `meta.requiredPermissions = ['manual_intervention_workspace', 'auto_predictions']`；侧边栏菜单通过 `hasPermission('manual_intervention_workspace') || hasPermission('auto_predictions')` 显示；但全局路由守卫当前只校验登录态，代码中未发现按 `requiredPermissions` 强制拦截 |

### 1.2 页面定位

从当前代码实现看，该页面是一个“本地 mock 型人工修正原型页”，核心能力是：

- 选择场站
- 选择日期
- 选择修正工具
- 对一组本地生成的 24 点序列做放大、平移、限幅
- 用原生 SVG 把修正后的曲线画出来
- 点击保存后弹出成功提示

代码中未发现以下能力：

- 后端接口读取原始预测曲线
- 保存修正结果到后端
- 读取状态监控页面跳入时携带的 `farm_code` / `mode`
- 版本历史
- 审批流
- 权限到按钮级别控制
- 与其他页面真正的数据闭环

### 1.3 关键事实

1. 页面没有引入任何 `src/api`、`src/services`、`src/composables`、`src/store` 文件。
2. 页面数据源完全来自本地函数 `buildMockSeries()`。
3. 页面图表不是 ECharts，也不是公共图表组件，而是原生 `svg + polyline`。
4. 保存动作只执行 `ElMessage.success(...)`，没有真实持久化。
5. 状态监控页 [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue) 会跳转到该页面的路由，但当前页面代码中未发现 `useRoute()` 或 `$route.query` 读取逻辑，因此跳转参数不会被消费。

---

## 2. 页面结构树

```text
人工修正工作台 ManualInterventionWorkspace.vue
├─ 页面容器
│  ├─ 标题
│  └─ 描述文案
├─ 左侧工具面板 el-card
│  ├─ 场站选择 el-select
│  ├─ 日期选择 el-date-picker
│  ├─ 修正工具选择 el-select
│  ├─ 修正参数输入 el-input-number
│  └─ 操作按钮区
│     ├─ 应用修正
│     ├─ 重置
│     └─ 保存版本
└─ 右侧图形面板 el-card
   ├─ 图标题
   ├─ svg 曲线图
   │  ├─ polyline 预测曲线
   │  └─ line 限幅参考线（条件渲染）
   └─ 底部提示文案
```

---

## 3. 区块说明

### 3.1 页面头部区

| 项目 | 说明 |
|---|---|
| 区块名称 | 页面头部区 |
| 对应组件名 | `ManualInterventionWorkspace` |
| 文件路径 | [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue) |
| 展示内容 | 标题和说明文案 |
| 数据来源 | 页面模板内写死文案 |
| 是否可交互 | 否 |
| 是否有权限控制 | 页面进入依赖路由和菜单权限；区块本身无额外权限逻辑 |
| 是否有定时刷新或自动更新 | 否 |

说明：

- 标题和说明文案在终端中出现乱码，但页面结构可确认。
- 文案没有绑定任何动态数据。

### 3.2 左侧修正工具面板

| 项目 | 说明 |
|---|---|
| 区块名称 | 左侧修正工具面板 |
| 对应组件名 | `ManualInterventionWorkspace` |
| 文件路径 | [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue) |
| 展示内容 | 场站、日期、修正工具、参数输入、操作按钮 |
| 数据来源 | `station`、`targetDate`、`tool`、`toolValue` 等本地 `ref` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现按钮级权限控制 |
| 是否有定时刷新或自动更新 | 否 |

关键事实：

- 场站下拉选项是写死的两个 `el-option`，不是从 `farmService` 或接口加载。
- 日期默认值为 `new Date().toISOString().slice(0, 10)`，即当前浏览器日期。
- 修正工具只有三种：百分比放大、MW 平移、限幅裁切。
- 输入框使用 `el-input-number`，允许范围 `-1000 ~ 1000`。

### 3.3 右侧曲线图面板

| 项目 | 说明 |
|---|---|
| 区块名称 | 右侧曲线图面板 |
| 对应组件名 | `ManualInterventionWorkspace` |
| 文件路径 | [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue) |
| 展示内容 | 24 点曲线图、限幅参考线、提示文案 |
| 数据来源 | `series` 本地数组，经 `linePoints` 计算属性拼装为 SVG 点串 |
| 是否可交互 | 间接交互。图本身不可拖拽，受左侧工具按钮影响 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

关键事实：

- `series` 初始值来自 `buildMockSeries()`，是前端本地模拟 24 点数据。
- `polyline` 使用 `linePoints` 渲染主曲线。
- 当 `capValue !== null` 时，会额外渲染一条横向虚线，表示限幅阈值。
- 图面板没有缩放、hover tooltip、点选编辑、拖拽编辑等交互。

---

## 4. 组件明细表

### 4.1 页面主组件 `ManualInterventionWorkspace`

| 项目 | 说明 |
|---|---|
| 组件名称 | `ManualInterventionWorkspace` |
| 文件路径 | [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue) |
| 父子关系 | 路由页面组件；代码中未发现自定义子组件 |
| props / emits / callbacks | 无 props，无 emits，无外部回调注册 |
| 内部 state / computed / hooks / store 使用情况 | 使用 `ref` 管理表单和曲线状态；使用 `computed` 计算 `maxY` 和 `linePoints`；未使用 store/hooks/service |
| 生命周期或副作用逻辑 | 代码中未发现 `onMounted/watch/watchEffect/onUnmounted` 等副作用逻辑 |
| 实现的具体功能 | 本地曲线修正、重置、保存成功提示、SVG 曲线展示 |
| 触发了哪些接口 | 代码中未发现 |
| 与其他组件的联动关系 | 无自定义子组件联动；左侧表单和按钮影响右侧 SVG 曲线 |
| 加载态 / 空态 / 异常态如何处理 | 代码中未发现加载态、空态、异常态处理 |

#### 4.1.1 内部状态拆解

页面内部状态全部是本地 `ref`：

- `station`
  - 当前选中的场站
  - 默认值为写死的第一个场站文案
- `targetDate`
  - 当前修正日期
  - 默认值为当天
- `tool`
  - 当前修正工具类型
  - 默认值 `scaleUp`
- `toolValue`
  - 修正参数
  - 默认值 `10`
- `capValue`
  - 当前限幅值
  - 默认值 `null`
  - 仅当工具为 `cap` 并执行后才会生效
- `series`
  - 当前曲线数组
  - 默认值 `buildMockSeries()`

#### 4.1.2 本地计算逻辑

1. `buildMockSeries()`
- 作用：生成初始的 24 点模拟曲线。
- 公式：
  - 以 `35 + sin(...) * 18` 生成正弦波式数据
  - 再通过 `Math.max(0, base)` 保证非负
  - 最后保留两位小数
- 结论：这是纯前端 mock 数据，不依赖后端。

2. `maxY`
- 作用：决定 SVG y 轴缩放上限。
- 逻辑：取 `series.value`、`capValue.value`、`1` 三者中的最大值。
- 这样可以避免全 0 时除数为 0。

3. `toY(v)`
- 作用：把功率值映射到 SVG 坐标系。
- 逻辑：`330 - (v / maxY.value) * 300`
- 结论：固定把值压缩到高度 300 的绘图区内。

4. `toX(index)`
- 作用：把 24 个点映射到宽度 960 的 SVG 横轴。
- 逻辑：`(index / 23) * 960`

5. `linePoints`
- 作用：把 `series` 转换成 `polyline` 的 `points` 字符串。
- 输出形如 `"x1,y1 x2,y2 ..."`。

#### 4.1.3 用户动作函数

1. `applyTool()`
- 根据 `tool.value` 对 `series` 做不同修正。

分支一：`scaleUp`
- 逻辑：`factor = 1 + toolValue / 100`
- 对 `series` 每一项执行 `v * factor`
- 结果保留两位小数并保证不小于 0

分支二：`shift`
- 逻辑：对 `series` 每一项执行 `v + toolValue`
- 结果保留两位小数并保证不小于 0

分支三：`cap`
- 先把 `capValue` 设为当前 `toolValue`
- 再把 `series` 每一项裁切为 `Math.min(v, capValue)`

关键结论：
- 所有修正都直接在当前 `series` 上原地覆盖
- 不保留“原始序列”和“修正序列”双轨对比
- 多次点击“应用修正”会在上一次结果基础上继续叠加

2. `resetSeries()`
- 把 `capValue` 重置为 `null`
- 把 `series` 重置为新的 `buildMockSeries()`
- 不保留用户修改历史

3. `saveVersion()`
- 仅弹出 `ElMessage.success(...)`
- 提示文案中拼接 `station` 和 `targetDate`
- 代码中未发现接口调用、本地存储、文件保存、版本号生成

#### 4.1.4 生命周期、副作用与联动

代码中未发现：

- `onMounted`
- `watch`
- `watchEffect`
- `computed` 之外的异步副作用
- 路由参数监听
- 场站切换监听
- 轮询
- 定时器

因此该页面没有真正的“页面初始化拉数”流程。

#### 4.1.5 加载态 / 空态 / 异常态

- 加载态：代码中未发现
- 空态：代码中未发现
- 异常态：代码中未发现
- 表单校验：代码中未发现 `rules` 或 `validate`

结论：

- 页面当前是 demo/原型实现，不具备生产级异常和校验能力。

### 4.2 子组件递归分析结论

代码中未发现需要继续递归拆解的自定义子组件。

当前页面使用的 UI 元素都来自 Element Plus 原生组件：

- `el-card`
- `el-form`
- `el-form-item`
- `el-select`
- `el-option`
- `el-date-picker`
- `el-input-number`
- `el-button`

这些组件在本页中没有二次封装，因此不再递归。

---

## 5. 交互明细表

### 5.1 可见元素总览

#### 5.1.1 下拉框

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 下拉框 | 左侧工具面板 | 场站 | 选择场站 | 更新 `station` 本地状态 | 否 | 否 | 仅影响保存成功提示文案，不影响曲线数据 |
| 下拉框 | 左侧工具面板 | 修正工具 | 选择修正方式 | 更新 `tool` 本地状态 | 否 | 否 | 影响 `applyTool()` 的算法分支 |

说明：

- 场站切换不会重新拉取曲线，因为代码中未发现接口调用或 watcher。
- 工具切换只是改变下一次“应用修正”时的计算逻辑。

#### 5.1.2 日期选择器

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 日期选择器 | 左侧工具面板 | 日期 | 选择修正目标日期 | 更新 `targetDate` | 否 | 否 | 仅影响保存成功提示文案 |

结论：

- 日期并不会驱动曲线重新计算，也不会拉取对应日期的历史数据。

#### 5.1.3 数值输入框

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 输入框 | 左侧工具面板 | 修正参数 | 输入修正值 | 更新 `toolValue` | 否 | 否 | 影响 `applyTool()` 结果 |

说明：

- 范围限制为 `-1000 ~ 1000`。
- 页面没有对不同工具类型设置不同校验规则。

#### 5.1.4 按钮

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 按钮 | 左侧工具面板 | 应用修正 | 对当前曲线执行修正 | 调用 `applyTool()`，直接修改 `series` | 否 | 否 | 影响右侧曲线图和限幅参考线 |
| 按钮 | 左侧工具面板 | 重置 | 恢复初始曲线 | 调用 `resetSeries()`，重建 mock 曲线并清除 `capValue` | 否 | 否 | 影响右侧曲线图 |
| 按钮 | 左侧工具面板 | 保存版本 | 模拟保存修正结果 | 调用 `saveVersion()`，只弹成功消息 | 否 | 否 | 不影响其他组件 |

#### 5.1.5 图形

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 图表 | 右侧面板 | SVG 曲线 | 展示 24 点人工修正结果 | 图本身不可操作，受左侧按钮驱动 | 否 | 否 | 否 |
| 辅助线 | 右侧面板 | 限幅参考线 | 展示 cap 阈值 | `capValue !== null` 时显示 | 否 | 否 | 否 |

### 5.2 页面中未发现的元素

- tab：代码中未发现
- 表格：代码中未发现
- 卡片列表：只有两个功能卡片，不是业务卡片列表
- 标签：代码中未发现业务标签组件
- 状态图标：代码中未发现
- 弹窗/抽屉/tooltip：代码中未发现
- 刷新按钮：代码中未发现
- 导出下载：代码中未发现
- 提交/审批：代码中未发现
- 上传导入：代码中未发现

---

## 6. 接口明细表

### 6.1 当前页面实际接口使用情况

结论：代码中未发现任何接口调用。

依据：

- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue) 中没有 `src/api`、`src/services`、`axios`、`request` 等引入。
- 页面中也没有异步函数、`await`、`Promise` 或生命周期请求逻辑。

### 6.2 与页面主题相关但当前未接入的接口线索

扫描代码仓库后，发现与“人工修正/手动上报”更接近的接口实际位于 [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js) 中，但当前页面未使用。

| 接口名称 | 请求方法 | URL | 所在 api/service 文件 | 调用函数名 | 当前页面是否调用 | 说明 |
|---|---|---|---|---|---|---|
| 手动上报 | POST | `/api/v1/report/manual-report`，回退 `/api/report/manual-report` | [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js) | `manualReport(payload)` | 否 | 实际被 [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) 使用，不在本页面闭环内 |

结论：

- 当前“人工修正工作台”并没有接手动上报接口。
- 仓库中更接近“人工修正落地”的能力实际散落在 [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) 的手工工具区。
- 因此本页面与“状态监控 -> 人工修正”跳转链路在当前代码中并未真正闭环。

### 6.3 接口细节说明

由于当前页面未调用接口，因此以下字段需明确标注：

- 请求方法：代码中未发现
- URL：代码中未发现
- 调用触发条件：代码中未发现
- 请求参数：代码中未发现
- 返回数据结构：代码中未发现
- 返回字段映射：代码中未发现
- 失败时页面处理：代码中未发现

---

## 7. 数据流说明

### 7.1 初始化加载流程

当前页面没有传统意义上的“加载流程”，而是：

1. 页面初始化执行 `setup()`。
2. 直接创建本地状态：
   - `station`
   - `targetDate`
   - `tool`
   - `toolValue`
   - `capValue`
   - `series`
3. `series` 通过 `buildMockSeries()` 生成 24 点模拟数据。
4. `computed`：
   - `maxY`
   - `linePoints`
5. 模板把 `linePoints` 绑定到 `polyline.points`。

结论：

- 页面初始化不依赖后端。
- 页面初始化不依赖全局 store。
- 页面初始化不依赖 URL 参数。

### 7.2 用户操作后数据如何变化

#### 7.2.1 选择场站

- 仅更新 `station`
- 不触发重新加载曲线
- 不影响 `series`

#### 7.2.2 选择日期

- 仅更新 `targetDate`
- 不触发重新加载曲线
- 不影响 `series`

#### 7.2.3 更换工具和参数

- 仅更新 `tool`、`toolValue`
- 直到点击“应用修正”前，右侧图不会变化

#### 7.2.4 点击“应用修正”

- 直接修改 `series`
- `linePoints` 自动重算
- 右侧 `polyline` 更新
- 若工具为 `cap`，同时更新 `capValue`
- 限幅虚线条件渲染生效

#### 7.2.5 点击“重置”

- `capValue = null`
- `series = buildMockSeries()`
- 图恢复到初始模拟值

#### 7.2.6 点击“保存版本”

- 不修改 `series`
- 不持久化
- 只展示 `ElMessage.success`

### 7.3 哪些状态是本地状态

当前页面所有业务状态都是本地状态：

- `station`
- `targetDate`
- `tool`
- `toolValue`
- `capValue`
- `series`

### 7.4 哪些状态来自全局 store

代码中未发现。

### 7.5 哪些数据来自后端接口

代码中未发现。

### 7.6 哪些字段经过二次加工/格式化

以下数据属于前端计算结果：

- `series` 初始模拟值
- `maxY`
- `toX(index)`
- `toY(value)`
- `linePoints`
- `capValue` 触发的虚线位置

---

## 8. 权限与状态控制说明

### 8.1 权限控制

1. 路由级权限
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js) 中：
  - `path: 'manual-workspace'`
  - `meta.requiredPermissions = ['manual_intervention_workspace', 'auto_predictions']`

2. 菜单级权限
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 中：
  - 菜单项 `/manual-workspace` 的显示条件为
    - `hasPermission('manual_intervention_workspace') || hasPermission('auto_predictions')`

3. 实际守卫情况
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js) 的 `beforeEach` 当前只校验登录态。
- 代码中未发现守卫按 `requiredPermissions` 进行拒绝访问。

4. 页面内部权限
- 页面中的场站选择、修正、保存按钮均未发现单独权限判断。
- 代码中未发现 `v-if hasPermission(...)`、`disabled by permission`、权限指令等。

### 8.2 状态控制

当前页面状态控制非常轻：

- 没有 loading 状态
- 没有提交中状态
- 没有表单校验状态
- 没有脏数据提示
- 没有撤销/重做
- 没有多版本管理

结论：

- 页面更接近 demo 工具，而不是生产级人工修正工作台。

---

## 9. 风险点/待确认点

### 9.1 风险点

1. 页面与“人工修正”业务名义不匹配
- 名称上是“人工修正工作台”
- 但代码实现只是一个本地曲线编辑 demo
- 没有真实数据读取、没有保存、没有审计、没有回写

2. 与状态监控页面跳转未形成闭环
- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue) 会跳转到该页面
- 并携带 `farm_code/source/mode` 等 query
- 当前页面代码中未发现 `useRoute()` 或 query 读取逻辑
- 因此跳转上下文被丢失

3. 场站与日期选择是“展示型输入”，不是“数据型输入”
- 选择场站、日期后并不会请求对应曲线
- 用户容易误以为正在编辑某个真实场站某天的数据

4. 保存版本没有持久化
- `saveVersion()` 只有成功提示
- 刷新页面后所有修改丢失

5. 无校验、无异常、无权限到按钮级控制
- 生产风险较高
- 不适合作为真实人工修正闭环直接使用

### 9.2 待确认点

- 该页面是否只是原型页/占位页，需结合产品或后端确认
- 真实人工修正能力是否已经迁移到 [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) 的手工工具区，需结合业务确认
- 路由权限为什么允许 `auto_predictions` 用户直接进入，而不是单独要求 `manual_intervention_workspace`，需结合权限设计确认
- 页面中文文案在终端输出中有乱码，需结合编辑器确认真实展示文案

---

## 10. 代码证据清单

### 10.1 页面主文件

- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue)
  - `buildMockSeries`
  - `station`
  - `targetDate`
  - `tool`
  - `toolValue`
  - `capValue`
  - `series`
  - `maxY`
  - `toY`
  - `toX`
  - `linePoints`
  - `applyTool`
  - `resetSeries`
  - `saveVersion`

### 10.2 路由与权限

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - `/manual-workspace` 路由定义
  - `meta.requiredPermissions = ['manual_intervention_workspace', 'auto_predictions']`
  - `beforeEach`
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - `/manual-workspace` 菜单项显隐条件
  - `hasPermission`

### 10.3 相关但未接入的业务线索

- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)
  - `openManualCorrection(row)` 跳转到 `ReportManagement`，不是本页面
- [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js)
  - `manualReport(payload)`
- [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)
  - `manualToolForm`
  - `generateManualFile`
  - `downloadManualFile`
  - `forcePushManualFile`

---

## 关键代码证据清单

- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)
- [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js)
- [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)

## 可能遗漏点检查清单

- 若该页面真实逻辑通过后端动态注入或运行时代码扩展，本次静态代码扫描无法覆盖
- 本次未沿 git 历史追溯该页面是否曾接入接口，仅基于当前工作树判断
- 页面中文文案在终端中显示乱码，但不影响结构、函数和依赖判断
- 若后续人工修正业务已迁移到其他页面，本页应在系统说明中标注为“原型页/占位页”，需结合业务方最终确认
