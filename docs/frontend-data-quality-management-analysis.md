# 数据质量与限电标记代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 数据质量与限电标记 |
| 所属模块 | 运维与质量 |
| 路由路径 | `/data-quality` |
| 页面入口文件 | [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue) |
| 页面依赖的子组件列表 | 代码中未发现自定义子组件；页面直接使用 Element Plus 组件 `el-card`、`el-progress`、`el-button`、`el-table`、`el-table-column`、`el-tag`、`el-dialog`、`el-form`、`el-form-item`、`el-input`、`el-date-picker`、`el-select`、`el-option`、`el-switch` |
| 页面依赖的 store/hooks/model/service/api 文件 | 页面代码中未发现 `store/hooks/model/service/api` 直接引用；仅使用 Vue `ref`、`reactive` |
| 页面是否受权限控制 | 路由声明 `meta.requiredPermissions = ['manage_data_quality', 'view_all_data']`；侧边栏菜单显隐条件为 `hasPermission('manage_data_quality') || hasPermission('view_all_data')`；代码中未发现页面内部按钮级权限控制 |

### 1.2 页面定位结论

基于当前代码，这一页是“本地静态质量看板 + 本地标记录入弹窗”的前端原型页，已实现的闭环只有：

- 本地展示各场站 SCADA / 测风塔完整率
- 本地展示已有异常/免考标记
- 本地新增一条标记并立即插入表格

页面未闭环的业务能力包括：

- 从后端读取质量统计
- 从后端读取限电/大修/结冰等标记记录
- 保存标记到后端
- 编辑/删除/撤销标记
- 标记对准确率/合格率考核口径的真实联动
- 场站筛选、时间筛选、分页、导出

### 1.3 关键判断

1. `completeness` 与 `markers` 都是本地静态数组，不来自接口。
2. 页面没有 `onMounted`、`watch`、`setInterval`、`async/await`，不存在初始化请求和自动刷新。
3. “新增标记”提交只会 `markers.unshift(...)` 写入本地数组，不会持久化。
4. 页面文案明确提到“用于免考剔除”，但代码中未发现与报表页或功率对比页的真实数据联动。

---

## 2. 页面结构树

```text
数据质量与限电标记 DataQualityManagement.vue
├─ 页面根容器 data-quality page-shell
│  ├─ 页面头部 page-header
│  │  ├─ 标题 h2
│  │  └─ 描述文本 p
│  ├─ 主卡片 el-card.card-shell
│  │  ├─ 完整率看板 quality-grid
│  │  │  └─ quality-card * N
│  │  │     ├─ 场站名称
│  │  │     ├─ SCADA/测风塔完整率摘要
│  │  │     └─ 两条 el-progress 进度条
│  │  ├─ 表格头 table-header
│  │  │  ├─ 标记列表标题
│  │  │  └─ 新增标记按钮
│  │  └─ 标记表格 el-table(markers)
│  │     ├─ 场站列
│  │     ├─ 开始时间列
│  │     ├─ 结束时间列
│  │     ├─ 标记类型列
│  │     ├─ 原因列
│  │     └─ 是否剔除考核列 el-tag
│  └─ 新增标记弹窗 el-dialog
│     ├─ 场站输入框
│     ├─ 时间范围选择器
│     ├─ 标记类型下拉框
│     ├─ 原因文本域
│     ├─ 是否剔除考核开关
│     └─ 取消/提交按钮
```

---

## 3. 区块说明

### 3.1 页面头部

| 字段 | 说明 |
|---|---|
| 区块名称 | 页面头部 |
| 对应组件名 | `DataQualityManagement` |
| 文件路径 | [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue) |
| 展示内容 | 页面标题、说明文案 |
| 数据来源 | 模板内硬编码文本 |
| 是否可交互 | 否 |
| 是否有权限控制 | 无单独权限控制 |
| 是否有定时刷新或自动更新 | 否 |

补充说明：

- 页面头部说明文案直接写死在模板中。
- 文案提到“SCADA/测风塔完整率”“限电/大修/结冰”“免考剔除”，但这些业务对象目前并没有真实后端数据源。

### 3.2 完整率看板区

| 字段 | 说明 |
|---|---|
| 区块名称 | 完整率看板 |
| 对应组件名 | `DataQualityManagement` |
| 文件路径 | [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue) |
| 展示内容 | 多个场站的 SCADA 完整率、测风塔完整率、两条进度条 |
| 数据来源 | 本地 `completeness` 数组 |
| 是否可交互 | 否 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 否 |

数据结构：

- `station`
- `scada`
- `mast`

展示规则：

- 每个场站渲染一张 `quality-card`
- `el-progress` 的 `percentage` 分别绑定 `item.scada` 和 `item.mast`
- 当百分比 `< 90` 时，状态设为 `exception`，否则为 `success`

结论：

- 看板没有筛选器、无点击下钻、无图表交互。
- 阈值 `90` 是前端硬编码规则，不来自配置中心或接口。

### 3.3 标记表格区

| 字段 | 说明 |
|---|---|
| 区块名称 | 标记表格区 |
| 对应组件名 | `DataQualityManagement` |
| 文件路径 | [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue) |
| 展示内容 | 已有标记列表与“新增标记”按钮 |
| 数据来源 | 本地 `markers` 数组 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

表格列：

- `station`
- `start`
- `end`
- `type`
- `reason`
- `excludeFromScore`

“是否剔除考核”列逻辑：

- `row.excludeFromScore === true`
  - `el-tag type="success"`
  - 显示“是”
- `row.excludeFromScore === false`
  - `el-tag type="info"`
  - 显示“否”

结论：

- 表格没有操作列，因此不能编辑、删除、撤销标记。
- 表格没有分页、排序、搜索、筛选。

### 3.4 新增标记弹窗区

| 字段 | 说明 |
|---|---|
| 区块名称 | 新增标记弹窗 |
| 对应组件名 | `DataQualityManagement` |
| 文件路径 | [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue) |
| 展示内容 | 录入场站、时间范围、标记类型、原因、是否剔除考核 |
| 数据来源 | 本地 `form` 响应式对象 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

表单字段：

- `station`
- `range`
- `type`
- `reason`
- `excludeFromScore`

提交行为：

- 校验仅覆盖：
  - `form.station` 非空
  - `form.range` 是长度为 2 的数组
- 校验通过后将新对象插入 `markers` 首位
- 关闭弹窗

问题点：

- 提交后没有重置表单
- 没有表单校验提示信息
- 没有接口保存
- 没有失败分支提示

---

## 4. 组件明细表

### 4.1 页面组件：DataQualityManagement

| 维度 | 结论 |
|---|---|
| 组件名称 | `DataQualityManagement` |
| 文件路径 | [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue) |
| 父子关系 | 父级为布局路由容器 [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 中的 `<router-view>`；代码中未发现自定义子组件 |
| props / emits / callbacks | 代码中未定义 `props`、未定义 `emits`、未向外抛出回调 |
| 内部 state / computed / hooks / store 使用情况 | `ref(completeness)`、`ref(markers)`、`ref(showDialog)`、`reactive(form)`；未使用 computed、未使用 store/hooks |
| 生命周期或副作用逻辑 | 代码中未发现 `onMounted`、`onUnmounted`、`watch`、`watchEffect` |
| 实现的具体功能 | 展示本地完整率卡片、展示本地标记列表、打开新增标记弹窗、本地新增一条标记 |
| 触发了哪些接口 | 代码中未发现 |
| 与其他组件的联动关系 | 与 [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 在路由和菜单层联动；页面内部无自定义子组件联动 |
| 加载态 / 空态 / 异常态如何处理 | 代码中未发现加载态、空态、异常态；提交前置条件不满足时直接 `return`，没有错误提示 |

#### 4.1.1 内部状态拆解

1. `completeness`
- 类型：`ref<Array>`
- 默认值：3 个场站的本地完整率样例
- 字段：
  - `station`
  - `scada`
  - `mast`

2. `markers`
- 类型：`ref<Array>`
- 默认值：1 条本地样例标记
- 字段：
  - `station`
  - `start`
  - `end`
  - `type`
  - `reason`
  - `excludeFromScore`

3. `showDialog`
- 类型：`ref<boolean>`
- 默认值：`false`
- 用途：控制新增标记弹窗显示/隐藏

4. `form`
- 类型：`reactive<Object>`
- 字段：
  - `station: ''`
  - `range: []`
  - `type: '限电时段'`（实际终端显示乱码，但从 option/value 可确认是默认类型之一）
  - `reason: ''`
  - `excludeFromScore: true`

#### 4.1.2 方法拆解

1. `openDialog()`
- 触发条件：
  - 点击“新增标记”按钮
- 行为：
  - `showDialog.value = true`
- 说明：
  - 不会初始化或重置表单

2. `submitMarker()`
- 触发条件：
  - 弹窗点击“提交”
- 前置校验：
  - `form.station` 必须有值
  - `form.range` 必须是长度为 2 的数组
- 通过后的行为：
  - 构造新对象写入 `markers.value.unshift(...)`
  - `start = form.range[0]`
  - `end = form.range[1]`
  - 其余字段直接来自 `form`
  - `showDialog.value = false`
- 未通过时行为：
  - 直接 `return`
  - 不弹提示，不高亮错误，不滚动定位

#### 4.1.3 组件内未发现的逻辑

- `computed`
- `watch`
- `watchEffect`
- `onMounted`
- `onUnmounted`
- `setInterval`
- `setTimeout`
- `useRoute`
- `useRouter`
- API 调用
- WebSocket 订阅
- 本地缓存读写

### 4.2 使用到的三方组件

本页没有本项目自定义子组件，但直接依赖以下 Element Plus 组件：

| 组件 | 用途 |
|---|---|
| `el-card` | 承载主内容 |
| `el-progress` | 展示完整率进度条 |
| `el-button` | 打开弹窗、取消、提交 |
| `el-table` | 展示标记记录 |
| `el-table-column` | 定义表格列 |
| `el-tag` | 展示是否剔除考核 |
| `el-dialog` | 新增标记弹窗 |
| `el-form` | 承载录入表单 |
| `el-form-item` | 表单项布局 |
| `el-input` | 场站、原因输入 |
| `el-date-picker` | 时间范围输入 |
| `el-select` | 标记类型选择 |
| `el-option` | 标记类型选项 |
| `el-switch` | 是否剔除考核开关 |

---

## 5. 交互明细表

### 5.1 页面主要交互

| 元素类型 | 位置 | 文案 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 按钮 | 表格头右侧 | 新增标记 | 打开标记录入弹窗 | 调用 `openDialog()`，`showDialog = true` | 否 | 否 | 影响本页弹窗显示 |
| 按钮 | 弹窗 footer | 取消 | 关闭弹窗 | `showDialog = false` | 否 | 否 | 影响本页弹窗显示 |
| 按钮 | 弹窗 footer | 提交 | 本地新增标记 | 调用 `submitMarker()`；校验通过后插入 `markers` 首位并关闭弹窗 | 否 | 否 | 影响本页表格数据 |

### 5.2 表单元素

| 元素类型 | 位置 | 文案/字段 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 输入框 | 弹窗 | 场站 | 录入标记归属场站 | 更新 `form.station` | 否 | 否 | 影响提交入表的数据 |
| 日期选择器 | 弹窗 | 时间范围 | 录入开始/结束时间 | 更新 `form.range`；`value-format` 为 `YYYY-MM-DD HH:mm:ss` | 否 | 否 | 影响提交入表的数据 |
| 下拉框 | 弹窗 | 标记类型 | 选择标记类别 | 更新 `form.type` | 否 | 否 | 影响提交入表的数据 |
| 文本域 | 弹窗 | 原因 | 录入标记原因 | 更新 `form.reason` | 否 | 否 | 影响提交入表的数据 |
| 开关 | 弹窗 | 是否剔除考核 | 控制免考标识 | 更新 `form.excludeFromScore` | 否 | 否 | 影响表格最后一列标签显示 |

### 5.3 展示元素

| 元素类型 | 位置 | 文案/字段 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 卡片 | 完整率看板 | 场站名称 | 展示场站完整率摘要 | 无点击行为 | 否 | 否 | 否 |
| 进度条 | 完整率看板 | SCADA 完整率 | 展示百分比与达标状态 | 无点击行为 | 否 | 否 | 否 |
| 进度条 | 完整率看板 | 测风塔完整率 | 展示百分比与达标状态 | 无点击行为 | 否 | 否 | 否 |
| 表格 | 主内容区 | 标记列表 | 展示标记记录 | 无行点击、无操作列 | 否 | 否 | 否 |
| 标签 | 表格最后一列 | 是/否 | 显示是否剔除考核 | 无点击行为 | 否 | 否 | 否 |

### 5.4 页面中未发现的可见元素

以下元素在代码中未发现：

- 搜索输入框
- 页面级下拉筛选
- 页面级日期筛选
- tab
- 图表
- tooltip
- 抽屉
- 刷新按钮
- 重置按钮
- 导出按钮
- 上传导入入口
- 行操作按钮

---

## 6. 接口明细表

### 6.1 页面直接接口

| 接口名称 | 请求方法 | URL | 所在 api/service 文件 | 调用函数名 | 调用触发条件 | 请求参数 | 返回数据结构 | 返回数据映射到页面哪个组件/哪个字段 | 失败时页面怎么处理 |
|---|---|---|---|---|---|---|---|---|---|
| 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 |

结论：

- 本页面没有任何 HTTP 接口调用。

### 6.2 关联能力核查

本轮已在以下目录检索“质量/限电/标记/curtail/quality/mark”等关键词：

- `src/api`
- `src/services`
- `src/utils`

结果：

- 代码中未发现与本页面直接对应的数据质量接口封装
- 代码中未发现“限电标记”保存、查询、删除、编辑 API
- 代码中未发现质量标记与报表考核口径联动的 service

补充说明：

- [dashboardService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/dashboardService.js) 中仅发现一条首页提示文案包含“建议关注限电策略”，不构成本页数据来源。

---

## 7. 数据流说明

### 7.1 初始化加载流程

页面初始化流程如下：

1. Vue 执行 `setup()`
2. 初始化本地状态：
   - `completeness = 本地完整率样例数组`
   - `markers = 本地标记样例数组`
   - `showDialog = false`
   - `form = 本地响应式表单对象`
3. 模板直接渲染看板、表格和弹窗

说明：

- 没有 `onMounted`
- 没有接口请求
- 没有读取路由参数
- 没有场站上下文联动

### 7.2 用户操作后的数据变化

1. 点击“新增标记”
- `showDialog = true`
- 弹窗打开

2. 修改表单字段
- 各字段写回 `form`

3. 点击“提交”
- 如果 `station` 为空，或 `range` 不是长度为 2 的数组
  - 直接返回
  - 无提示
- 如果通过校验
  - 生成新标记对象
  - 插入 `markers` 首位
  - 关闭弹窗

4. 新标记渲染到表格
- 表格自动响应式更新
- “是否剔除考核”列基于 `excludeFromScore` 显示标签

### 7.3 状态分类

#### 本地状态

- `completeness`
- `markers`
- `showDialog`
- `form.station`
- `form.range`
- `form.type`
- `form.reason`
- `form.excludeFromScore`

#### 全局 store 状态

- 代码中未发现

#### 后端接口数据

- 代码中未发现

#### 二次加工/格式化字段

- `el-progress` 的异常/正常状态：
  - `< 90` -> `exception`
  - `>= 90` -> `success`
- 表格“是否剔除考核”列标签：
  - `true` -> `success` / “是”
  - `false` -> `info` / “否”

### 7.4 与其他页面的业务闭环核查

页面文案声称标记将“用于免考剔除”，但当前代码中未发现：

- 与 [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue) 的联动
- 与 [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) 的联动
- 与任何报表 service 的联动

结论：

- 当前“免考剔除”只体现在本页展示层，不构成真实计算链路。

---

## 8. 权限与状态控制说明

### 8.1 路由与菜单权限

1. 路由声明位置
- 文件：[router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- 路由：
  - `path: 'data-quality'`
  - `name: 'DataQualityManagement'`
  - `meta.requiredPermissions = ['manage_data_quality', 'view_all_data']`

2. 菜单显隐位置
- 文件：[AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- 菜单项：
  - `index="/data-quality"`
  - 条件：`hasPermission('manage_data_quality') || hasPermission('view_all_data')`

### 8.2 实际守卫行为

全局守卫位于 [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)：

- 只校验 `localStorage.getItem('user')`
- 未发现基于 `meta.requiredPermissions` 的真正拦截逻辑

结论：

- 前端路由层实际只有登录态校验。
- 权限更多体现为菜单隐藏，而不是路由硬拦截。

### 8.3 页面内部权限控制

代码中未发现：

- `v-permission`
- `hasPermission`
- 新增按钮权限判断
- 弹窗字段级权限判断
- 提交按钮权限判断

---

## 9. 风险点 / 待确认点

### 9.1 明确风险点

1. 页面为静态原型，未接真实质量/标记数据源  
证据：页面未引入任何 `api/service`，核心数据 `completeness`、`markers` 为本地硬编码数组。

2. “新增标记”不会持久化  
证据：`submitMarker()` 只执行 `markers.value.unshift(...)`。

3. 表单校验极弱且无错误提示  
证据：只做两个条件判断，不满足时直接 `return`。

4. 提交后不重置表单  
证据：`submitMarker()` 关闭弹窗后未清空 `form`。

5. 无编辑/删除/撤销能力  
证据：表格没有操作列。

6. “用于免考剔除”仅停留在本页展示层  
证据：代码中未发现与准确率/功率对比/报表 service 的联动。

7. 路由权限声明未在全局守卫中落地  
证据：`beforeEach` 只检查登录态，不检查 `requiredPermissions`。

### 9.2 待确认点

1. 该页是否只是占位原型，真实质量管理模块尚未接后端  
当前判断：高度可能，需结合后端确认。

2. 标记类型是否应来自统一字典或配置中心  
当前判断：当前为页面硬编码 option，需结合后端确认。

3. 完整率阈值 `90%` 是否真实业务规则  
当前判断：当前为前端硬编码，需结合业务确认。

4. 标记是否应与场站上下文联动  
当前判断：当前页未使用 `farmService`，需结合产品要求确认。

5. 页面中文文案在终端输出存在乱码  
当前判断：更可能是终端编码问题，不影响逻辑分析；原文建议在编辑器内复核。

---

## 10. 代码证据清单

### 10.1 页面文件

- [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)
  - 组件名：`DataQualityManagement`
  - 状态：`completeness`、`markers`、`showDialog`、`form`
  - 方法：`openDialog()`、`submitMarker()`

### 10.2 路由与权限入口

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - 路由名：`DataQualityManagement`
  - 路由路径：`data-quality`
  - 权限元信息：`requiredPermissions: ['manage_data_quality', 'view_all_data']`
  - 守卫：`beforeEach(...)`

- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - 菜单项：`index="/data-quality"`
  - 权限判断：`hasPermission('manage_data_quality') || hasPermission('view_all_data')`

### 10.3 关联能力核查范围

- [dashboardService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/dashboardService.js)
  - 仅发现首页提示文案提到“限电策略”，不构成本页数据源

---

## 关键代码证据清单

- [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- [dashboardService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/dashboardService.js)

## 可能遗漏点检查清单

- 是否存在后续未接入本页的质量管理后端 API，当前代码中未发现
- 是否存在其他页面承担标记编辑/撤销能力，当前本页未体现
- 是否存在质量标记与准确率报表的真实计算联动，当前代码中未追到
- 是否存在统一字典源为标记类型提供数据，当前代码中未发现
- 是否存在与场站切换组件 `FarmSelector` 的联动需求，当前页面未接入
