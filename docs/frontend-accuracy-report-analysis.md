# 准确率/合格率报表页面代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 准确率/合格率报表 |
| 所属模块 | 分析与报表 |
| 路由路径 | `/accuracy-report` |
| 页面入口文件 | [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue) |
| 页面依赖的子组件 | 代码中未发现自定义子组件；页面仅使用 Element Plus 基础组件 |
| 页面依赖的 store/hooks/model/service/api 文件 | 代码中未发现自定义 store/hooks/model/service/api 引入；仅引入 Vue `ref` |
| 页面是否受权限控制 | 是。路由 `meta.requiredPermissions = ['view_accuracy_report', 'view_all_data']`；侧边栏菜单通过 `hasPermission('view_accuracy_report') || hasPermission('view_all_data')` 显示；但全局路由守卫当前只校验登录态，代码中未发现按 `requiredPermissions` 强制拦截 |

### 1.2 页面定位

从当前代码看，这不是已经接好报表接口的正式“准确率/合格率报表”，而是一个静态报表占位页。当前实现只完成了：

- 月份选择 UI
- 场站选择 UI
- “查询”按钮 UI
- “导出报表”按钮 UI
- 一张静态表格

代码中未发现：

- 查询按钮事件绑定
- 导出按钮事件绑定
- 场站/月份变更后的数据请求
- 报表接口调用
- 分页、排序、汇总、图表、空态、异常态处理

### 1.3 关键事实

1. 页面没有引入任何 `src/api`、`src/services`、`src/composables`、`src/store` 文件。
2. 表格数据来自 `rows = ref([...])` 的本地静态数组。
3. “查询”和“导出报表”按钮都没有 `@click` 绑定。
4. 页面没有 `watch/onMounted/computed` 等副作用或衍生逻辑。
5. 仓库里与“准确率/合格率”最相关的真实计算逻辑实际上更多出现在 [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) 中，而不是本页。

---

## 2. 页面结构树

```text
准确率/合格率报表 AccuracyReport.vue
├─ 页面头部
│  ├─ 标题
│  └─ 说明文案
└─ 报表卡片 el-card
   ├─ 工具栏
   │  ├─ 月份选择器
   │  ├─ 场站选择下拉框
   │  ├─ 查询按钮
   │  └─ 导出报表按钮
   └─ 报表表格 el-table
      ├─ 场站列
      ├─ 月份列
      ├─ 平均准确率列
      ├─ 合格率列
      ├─ 免考小时列
      └─ 备注列
```

---

## 3. 区块说明

### 3.1 页面头部区

| 项目 | 说明 |
|---|---|
| 区块名称 | 页面头部区 |
| 对应组件名 | `AccuracyReport` |
| 文件路径 | [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue) |
| 展示内容 | 页面标题、说明文案 |
| 数据来源 | 模板内写死文案 |
| 是否可交互 | 否 |
| 是否有权限控制 | 页面进入依赖路由和菜单权限；区块本身无额外权限判断 |
| 是否有定时刷新或自动更新 | 否 |

说明：

- 页面标题已可从代码搜索中确认是“准确率/合格率考核报表”。
- 头部说明文案在终端输出有乱码，但结构明确。

### 3.2 工具栏区

| 项目 | 说明 |
|---|---|
| 区块名称 | 工具栏区 |
| 对应组件名 | `AccuracyReport` |
| 文件路径 | [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue) |
| 展示内容 | 月份选择、场站选择、查询按钮、导出报表按钮 |
| 数据来源 | `month`、`station` 本地 `ref` |
| 是否可交互 | 是，但只有输入控件有状态变化 |
| 是否有权限控制 | 代码中未发现按钮级权限判断 |
| 是否有定时刷新或自动更新 | 否 |

关键事实：

- `month` 初始值是 `new Date().toISOString().slice(0, 7)`。
- `station` 初始值是 `'all'`。
- 场站选项是写死的 3 个 `el-option`：
  - 全部场站
  - 场站 A
  - 场站 B
- 两个按钮没有事件绑定，因此当前仅有 UI，未形成业务动作。

### 3.3 报表表格区

| 项目 | 说明 |
|---|---|
| 区块名称 | 报表表格区 |
| 对应组件名 | `AccuracyReport` |
| 文件路径 | [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue) |
| 展示内容 | 场站、月份、平均准确率、合格率、免考小时、备注 |
| 数据来源 | `rows` 本地静态数组 |
| 是否可交互 | 否。未配置排序、筛选、点击动作 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

关键事实：

- 表格没有调用接口，也没有根据 `month/station` 联动过滤。
- 表格展示值是硬编码样例数据。
- `accuracy`、`qualified` 直接以数字形式展示，代码中未做格式化函数封装。

---

## 4. 组件明细表

### 4.1 页面主组件 `AccuracyReport`

| 项目 | 说明 |
|---|---|
| 组件名称 | `AccuracyReport` |
| 文件路径 | [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue) |
| 父子关系 | 路由页面组件；代码中未发现自定义子组件 |
| props / emits / callbacks | 无 props / emits / 自定义回调 |
| 内部 state / computed / hooks / store 使用情况 | 仅使用 `ref` 管理 `month`、`station`、`rows` |
| 生命周期或副作用逻辑 | 代码中未发现 `onMounted/watch/computed` 等逻辑 |
| 实现的具体功能 | 展示静态筛选 UI 和静态报表表格 |
| 触发了哪些接口 | 代码中未发现 |
| 与其他组件的联动关系 | 无 |
| 加载态 / 空态 / 异常态如何处理 | 代码中未发现 |

#### 4.1.1 内部状态

页面内部只有三个状态：

- `month`
  - 默认值：当前年月 `YYYY-MM`
- `station`
  - 默认值：`all`
- `rows`
  - 默认值：本地 2 条静态报表记录

#### 4.1.2 本地静态数据结构

`rows` 中每条记录包含字段：

- `station`
- `month`
- `accuracy`
- `qualified`
- `excludedHours`
- `note`

结论：

- 这些字段已经构成当前页面唯一的数据模型。
- 代码中未发现后端接口结构映射或字段转换逻辑。

#### 4.1.3 生命周期、副作用与联动

代码中未发现：

- `onMounted`
- `watch`
- `computed`
- 异步函数
- 请求函数
- 表单校验
- 路由参数监听
- 全局场站联动

因此该页面没有真正的“初始化拉数”和“筛选重算”流程。

#### 4.1.4 加载态 / 空态 / 异常态

- 加载态：代码中未发现
- 空态：代码中未发现
- 异常态：代码中未发现
- 表单校验：代码中未发现

结论：

- 当前页面只是静态展示壳，不具备生产级报表页的数据反馈能力。

### 4.2 子组件递归分析结论

代码中未发现需要继续递归拆解的自定义子组件。

当前页面使用的 UI 元素均为 Element Plus 原生组件：

- `el-card`
- `el-date-picker`
- `el-select`
- `el-option`
- `el-button`
- `el-table`
- `el-table-column`

由于没有二次封装，不再继续递归。

---

## 5. 交互明细表

### 5.1 工具栏元素

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 日期选择器 | 工具栏 | 月份 | 选择月份 | 更新 `month` 本地状态 | 否 | 否 | 当前代码中不影响表格 |
| 下拉框 | 工具栏 | 场站 | 选择场站 | 更新 `station` 本地状态 | 否 | 否 | 当前代码中不影响表格 |
| 按钮 | 工具栏 | 查询 | 设计上应为查询报表 | 当前代码无 `@click`，点击无页面逻辑 | 否 | 否 | 否 |
| 按钮 | 工具栏 | 导出报表 | 设计上应为导出 | 当前代码无 `@click`，点击无页面逻辑 | 否 | 否 | 否 |

关键事实：

- 用户虽然可以修改 `month` 和 `station`，但表格不会联动变化。
- “查询”“导出报表”目前只是视觉按钮。

### 5.2 表格元素

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 表格 | 卡片主体 | 报表表格 | 展示静态报表数据 | 无 | 否 | 否 | 否 |
| 表格列 | 表格内 | 场站 | 展示场站名称 | 无 | 否 | 否 | 否 |
| 表格列 | 表格内 | 月份 | 展示月份 | 无 | 否 | 否 | 否 |
| 表格列 | 表格内 | 平均准确率(%) | 展示准确率 | 无 | 否 | 否 | 否 |
| 表格列 | 表格内 | 合格率(%) | 展示合格率 | 无 | 否 | 否 | 否 |
| 表格列 | 表格内 | 免考小时 | 展示免考/剔除时长 | 无 | 否 | 否 | 否 |
| 表格列 | 表格内 | 备注 | 展示说明文字 | 无 | 否 | 否 | 否 |

### 5.3 页面中未发现的元素

- 输入框：代码中未发现
- tab：代码中未发现
- 图表：代码中未发现
- KPI 卡片：代码中未发现
- 状态图标：代码中未发现
- 标签：代码中未发现
- 弹窗/抽屉/tooltip：代码中未发现
- 刷新、重置、保存、提交：代码中未发现
- 导出下载逻辑：代码中未发现
- 上传导入：代码中未发现

---

## 6. 接口明细表

### 6.1 当前页面实际接口使用情况

结论：代码中未发现任何接口调用。

依据：

- [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue) 中没有引入 `src/api`、`src/services`、`axios`、`request`。
- 页面中没有异步函数，也没有请求触发事件。

### 6.2 与页面主题相关但当前未接入的接口线索

仓库中与“准确率/合格率/考核”最接近的真实接口线索有两类，但当前页面均未使用。

#### 6.2.1 功率对比指标接口

| 接口名称 | 请求方法 | URL | 所在文件 | 调用函数名 | 当前页面是否调用 | 说明 |
|---|---|---|---|---|---|---|
| 多站考核指标 | POST | `/api/v1/power-compare/fleet_metrics`，回退 `/power-compare/fleet_metrics` | [powerCompareApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/powerCompareApi.js) | `getFleetMetrics(payload)` | 否 | 当前被 [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) 使用，用于多站准确率/合格率计算 |

#### 6.2.2 报表统计接口

| 接口名称 | 请求方法 | URL | 所在文件 | 调用函数名 | 当前页面是否调用 | 说明 |
|---|---|---|---|---|---|---|
| 报表统计 | GET | `/api/v1/report/statistics`，回退 `/api/report/statistics` | [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js) | `getReportStatistics(params)` | 否 | 从命名上可能与统计/报表相关，但当前页面未接入；需结合后端确认是否适用于准确率报表 |

### 6.3 对无法确认信息的标注

由于当前页面未调用接口，以下字段需要明确标注：

- 接口名称：代码中未发现
- 请求方法：代码中未发现
- URL：代码中未发现
- 调用触发条件：代码中未发现
- 请求参数：代码中未发现
- 返回数据结构：代码中未发现
- 返回数据映射：代码中未发现
- 失败时页面处理：代码中未发现

---

## 7. 数据流说明

### 7.1 初始化加载流程

当前页面没有真实的“加载流程”，实际流程如下：

1. 页面初始化执行 `setup()`
2. 创建本地状态：
   - `month`
   - `station`
   - `rows`
3. 模板直接渲染工具栏和表格

结论：

- 无请求
- 无异步
- 无过滤计算
- 无派生统计

### 7.2 用户操作后数据如何变化

#### 7.2.1 修改月份

- 只更新 `month`
- 不触发表格变化
- 不触发接口

#### 7.2.2 修改场站

- 只更新 `station`
- 不触发表格变化
- 不触发接口

#### 7.2.3 点击“查询”

- 当前无事件绑定
- 代码层面没有任何行为

#### 7.2.4 点击“导出报表”

- 当前无事件绑定
- 代码层面没有任何行为

### 7.3 哪些状态是本地状态

当前页面全部状态都是本地状态：

- `month`
- `station`
- `rows`

### 7.4 哪些状态来自全局 store

代码中未发现。

### 7.5 哪些数据来自后端接口

代码中未发现。

### 7.6 哪些字段经过二次加工/格式化

代码中未发现格式化函数或计算字段。

表格数据原样来自 `rows` 静态数组。

---

## 8. 权限与状态控制说明

### 8.1 权限控制

1. 路由级权限
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js) 中：
  - `path: 'accuracy-report'`
  - `meta.requiredPermissions = ['view_accuracy_report', 'view_all_data']`

2. 菜单级权限
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 中：
  - `/accuracy-report` 菜单项条件：
    - `hasPermission('view_accuracy_report') || hasPermission('view_all_data')`

3. 实际路由守卫
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js) 的 `beforeEach` 当前只校验登录态。
- 代码中未发现按 `requiredPermissions` 执行拒绝访问。

4. 页面内部权限
- 页面中没有 `v-if hasPermission`、按钮禁用、权限指令等逻辑。

### 8.2 状态控制

当前页面状态控制极轻：

- 无 loading
- 无分页
- 无筛选提交态
- 无校验
- 无空态
- 无异常态

结论：

- 当前页不是完整业务页，而是静态报表壳。

---

## 9. 风险点/待确认点

### 9.1 风险点

1. 页面名称与实际实现不匹配
- 名称上是“准确率/合格率考核报表”
- 但代码实现只是静态表格展示
- 容易被误认为已落地报表模块

2. 查询与导出按钮无行为
- 用户可见按钮存在
- 但当前代码没有绑定任何逻辑
- 这属于典型“界面已搭，能力未接”的状态

3. 页面与其他分析页口径可能脱节
- [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) 已经在前端计算准确率/合格率
- 本页面却没有复用任何接口或计算逻辑
- 两者很可能会出现口径不一致风险

4. 场站和月份筛选是展示型控件
- 用户改变筛选条件后，页面结果不变
- 容易造成误导

### 9.2 待确认点

- 本页面是否只是占位页/原型页，需结合产品规划确认
- 准确率报表未来是否应直接复用 [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) 的 `fleet_metrics` 结果，需结合后端确认
- [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js) 中的 `getReportStatistics()` 是否原本计划供本页使用，代码中未明确
- 表格中的“免考小时”是否对应 [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue) 的免考/限电标记规则，需结合业务确认
- 页面中文文案在终端部分乱码，需结合编辑器确认真实展示文本

---

## 10. 代码证据清单

### 10.1 页面主文件

- [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue)
  - `month`
  - `station`
  - `rows`

### 10.2 路由与权限

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - `/accuracy-report` 路由定义
  - `meta.requiredPermissions = ['view_accuracy_report', 'view_all_data']`
  - `beforeEach`
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - `/accuracy-report` 菜单项显示条件
  - `hasPermission`

### 10.3 相关但未接入的业务线索

- [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue)
  - `fetchFleetCompareData`
  - `calcMetrics`
  - `calcDailyStats`
  - 多站准确率/合格率计算和展示
- [powerCompareApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/powerCompareApi.js)
  - `getFleetMetrics`
- [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js)
  - `getReportStatistics`
- [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)
  - 免考标记相关字段与表单

---

## 关键代码证据清单

- [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue)
- [powerCompareApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/powerCompareApi.js)
- [reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js)
- [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)

## 可能遗漏点检查清单

- 若本页的真实逻辑依赖运行时动态注入或后续未提交代码，本次静态扫描无法覆盖
- 本次未沿 git 历史追踪该页是否曾接入接口，仅基于当前工作树判断
- 文案终端乱码不影响结构、依赖和交互判断，但最终沉淀到 Wiki 时建议用编辑器复核
- 若未来该页面复用 `fleet_metrics` 或 `report/statistics`，需要重新补充接口字段和映射关系
