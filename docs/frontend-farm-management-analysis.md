# 场站管理代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 场站管理 |
| 所属模块 | 系统管理 |
| 路由路径 | `/farmmanagement` |
| 页面入口文件 | [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue) |
| 页面依赖的子组件列表 | [StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue) |
| 页面依赖的 store/hooks/model/service/api 文件 | [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js)、[axios.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/axios.js)；页面代码中未发现 store/hooks/model 直接引用 |
| 页面是否受权限控制 | 路由声明 `meta.requiredPermissions = ['manage_reports']`；侧边栏菜单显隐条件为 `hasPermission('manage_reports')`；页面内部按钮未发现额外权限控制 |

### 1.2 页面定位结论

基于当前代码，场站管理是一个已经接入真实后端 CRUD 的管理页，但不是纯后端主数据页。它实际上由两部分数据拼装而成：

1. 后端场站主数据  
来自 `getFarms/createFarm/updateFarm/deleteFarm`

2. 前端本地扩展配置  
通过 `localStorage` 的 `farm_management_ext_configs_v1` 存储补充字段

因此，这页已经形成了“查询列表 -> 新建/编辑 -> 更新启停 -> 删除 -> 刷新”的闭环，但同时存在一个重要特征：

- 部分字段持久化到后端
- 部分字段只保存在前端 `localStorage`

### 1.3 关键判断

1. 页面支持三种视图：卡片、表格、地图散点视图。
2. 页面已调用真实接口：
   - `getFarms`
   - `createFarm`
   - `updateFarm`
   - `deleteFarm`
3. 页面“地图视图”并不是真正地图底图，而是基于经纬度的二维散点图。
4. 抽屉表单字段很多，但并不是所有字段都可靠落库到后端；页面通过 `localStorage` 补充扩展配置。
5. 页面没有轮询，也没有场站上下文联动，数据刷新主要依赖每次操作成功后重新 `fetchFarms()`。

---

## 2. 页面结构树

```text
场站管理 FarmManagement.vue
├─ 页面根容器 page-shell farm-management
│  └─ 主卡片 el-card.panel-card
│     ├─ 头部 header
│     │  ├─ 标题与说明
│     │  ├─ 视图切换 radio-group
│     │  └─ 新增场站按钮
│     ├─ 空态区 empty-state
│     ├─ 卡片视图 farm-grid
│     │  └─ farm-card * N
│     │     ├─ 标题/编码
│     │     ├─ 状态胶囊 + StatusDot
│     │     ├─ 基础元信息
│     │     ├─ 业务状态
│     │     └─ 启停开关 + 编辑/启停预测/删除按钮
│     ├─ 表格视图 el-table
│     │  ├─ 编码列
│     │  ├─ 名称列
│     │  ├─ 装机容量列
│     │  ├─ 经度列
│     │  ├─ 纬度列
│     │  ├─ 模型列
│     │  ├─ 状态列 StatusDot + switch
│     │  └─ 操作列
│     ├─ 地图视图 map-view-wrap
│     │  ├─ echarts 容器
│     │  └─ 无坐标空态提示
│     └─ 编辑/新增抽屉 el-drawer
│        └─ el-form
│           ├─ basic tab 基础信息
│           ├─ hardware tab 设备信息
│           ├─ model tab 模型配置
│           └─ mapping tab 点位与状态映射
```

---

## 3. 区块说明

### 3.1 页面头部与工具栏

| 字段 | 说明 |
|---|---|
| 区块名称 | 页面头部与工具栏 |
| 对应组件名 | `FarmManagement` |
| 文件路径 | [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue) |
| 展示内容 | 页面标题、说明、副标题、视图切换按钮、新增场站按钮 |
| 数据来源 | 本地状态 `viewMode` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现内部权限判断 |
| 是否有定时刷新或自动更新 | 否 |

交互：

- `viewMode` 支持：
  - `card`
  - `table`
  - `map`
- 点击“新增场站”调用 `openCreateDrawer()`

### 3.2 空态区

| 字段 | 说明 |
|---|---|
| 区块名称 | 空态提示 |
| 对应组件名 | `FarmManagement` |
| 文件路径 | [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue) |
| 展示内容 | 当 `!loading && farms.length === 0` 时显示空态图标和提示 |
| 数据来源 | 本地状态 `loading`、`farms` |
| 是否可交互 | 否 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 否 |

说明：

- 空态只在非加载态且列表为空时显示。
- 没有空态重试按钮。

### 3.3 卡片视图

| 字段 | 说明 |
|---|---|
| 区块名称 | 卡片视图 |
| 对应组件名 | `FarmManagement` + `StatusDot` |
| 文件路径 | [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue)、[StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue) |
| 展示内容 | 场站标题、编码、容量、状态、区域信息、机位数、当前功率、SCADA/NWP 状态、操作按钮 |
| 数据来源 | `farms` 列表 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

卡片内关键展示字段：

- `row.farm_name`
- `row.farm_code`
- `row.capacity`
- `row.is_active`
- `row.province`
- `row.region`
- `row.turbine_count`
- `row.current_actual_power`
- `row.scada_status`
- `row.nwp_status`

卡片内操作：

- `el-switch`：切换场站启停状态，调用 `handleSetActive(row, val)`
- “编辑配置”：`openEditDrawer(row)`
- “启停预测”：`handleTogglePredict(row)`
- “删除”：`handleDelete(row)`

### 3.4 表格视图

| 字段 | 说明 |
|---|---|
| 区块名称 | 表格视图 |
| 对应组件名 | `FarmManagement` + `StatusDot` |
| 文件路径 | [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue)、[StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue) |
| 展示内容 | 场站编码、名称、容量、经纬度、模型、状态、操作 |
| 数据来源 | `farms` 列表 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

状态列结构：

- `el-tag`
- 内嵌 `StatusDot`
- 旁边再放一个 `el-switch`

说明：

- 表格和卡片视图操作能力一致，只是展示方式不同。
- 表格没有分页、搜索、筛选、导出。

### 3.5 地图视图

| 字段 | 说明 |
|---|---|
| 区块名称 | 地图视图 |
| 对应组件名 | `FarmManagement` |
| 文件路径 | [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue) |
| 展示内容 | 基于经纬度的 ECharts 散点图 |
| 数据来源 | `coordFarms`（从 `farms` 过滤经纬度有效项） |
| 是否可交互 | 是，支持 tooltip |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 无自动刷新；切视图和数据变化时重绘 |

关键事实：

- 代码中未引入地理底图或地图 GeoJSON。
- `xAxis` / `yAxis` 都是普通数值轴。
- 这不是传统“地图组件”，而是经纬度散点图。

tooltip 展示内容：

- 场站名 + 编码
- 经纬度
- 容量
- 状态

### 3.6 编辑/新增抽屉

| 字段 | 说明 |
|---|---|
| 区块名称 | 场站编辑抽屉 |
| 对应组件名 | `FarmManagement` |
| 文件路径 | [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue) |
| 展示内容 | 多 tab 表单：基础信息、设备信息、模型配置、点位映射 |
| 数据来源 | `formData` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

Tab 划分：

1. `basic`
- 名称、编码、投运日期、容量、经纬度、海拔、省份、区域

2. `hardware`
- 风机数量、轮毂高度、测风塔数量、功率曲线文件名、功率曲线 URL/说明

3. `model`
- 超短期模型、短期模型、下限功率、限电阈值

4. `mapping`
- 实际功率点位、风速点位、可用机位点位、SCADA/NWP 数据源状态、当前实际功率、场站启停状态

---

## 4. 组件明细表

### 4.1 页面组件：FarmManagement

| 维度 | 结论 |
|---|---|
| 组件名称 | `FarmManagement` |
| 文件路径 | [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue) |
| 父子关系 | 父级为 [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 中的 `<router-view>`；子组件为 [StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue) |
| props / emits / callbacks | `script setup` 页面组件无 props/emits；内部通过按钮/开关直接调用本地函数 |
| 内部 state / computed / hooks / store 使用情况 | `loading`、`submitting`、`farms`、`drawerVisible`、`isEdit`、`viewMode`、`activeTab`、`formRef`、`mapChartRef`、`formData`、`rules`、`coordFarms`；未使用 store |
| 生命周期或副作用逻辑 | `onMounted(fetchFarms + add resize listener)`、`onBeforeUnmount(dispose chart)`、`watch(viewMode)`、`watch(farms)` |
| 实现的具体功能 | 场站列表查询、卡片/表格/地图三视图切换、场站新增、场站编辑、启停切换、删除、经纬度散点渲染、本地扩展配置读写 |
| 触发了哪些接口 | `getFarms`、`createFarm`、`updateFarm`、`deleteFarm` |
| 与其他组件的联动关系 | 与 `StatusDot` 联动展示状态；与 ECharts 容器联动渲染地图视图 |
| 加载态 / 空态 / 异常态如何处理 | `loading` 驱动列表加载，空态单独显示；接口失败大多依赖 axios 全局错误提示，局部仅部分方法用 `ElMessage` |

#### 4.1.1 本地状态与计算属性

1. `loading`
- 列表加载态
- 在 `fetchFarms()` 中控制

2. `submitting`
- 抽屉提交态
- 在 `handleSubmit()` 中控制

3. `farms`
- 页面主数据
- 由 `getFarms()` 返回后，经 `normalizeFarm()` 处理得到

4. `drawerVisible`
- 控制抽屉显隐

5. `isEdit`
- 区分新增还是编辑

6. `viewMode`
- 控制页面主视图
- 可选：`card` / `table` / `map`

7. `activeTab`
- 控制抽屉当前 tab

8. `formData`
- 承载场站表单全部字段

9. `coordFarms`
- `computed`
- 仅保留经纬度有效的场站
- 地图视图唯一数据源

#### 4.1.2 数据归一化与辅助函数

1. `parseCoord(value)`
- 将字符串/空值转换为数值或 `null`

2. `toMw(value)`
- 容量和功率统一格式化为保留 2 位小数

3. `formatCoord(value)`
- 经纬度统一格式化为保留 6 位小数

4. `normalizeSourceLabel(value)`
- 将 `normal` / `abnormal` / 其他值映射为前端显示文案

5. `buildLocationText()`
- 将 `province + region` 拼接成 `location`

6. `normalizeFarm(raw)`
- 页面最关键的数据归一化函数
- 先读取 `getExtConfig(raw.farm_code)`
- 将后端数据与本地扩展配置合并
- 再统一修正数值类型和状态字段

结论：

- 页面实际不是直接消费后端原始字段，而是先走 `normalizeFarm()` 做二次加工。

#### 4.1.3 本地扩展配置链路

本页存在一个重要隐性逻辑：场站部分字段不完全依赖后端，而是通过本地缓存补充。

本地 key：

- `farm_management_ext_configs_v1`

相关函数：

1. `readExtConfigMap()`
- 从 `window.localStorage` 读 JSON
- 解析失败时 `console.warn` 并返回空对象

2. `writeExtConfigMap(data)`
- 全量写回 `localStorage`

3. `getExtConfig(farmCode)`
- 按场站编码读取扩展配置

4. `saveExtConfig(farmCode, config)`
- 保存扩展配置

5. `removeExtConfig(farmCode)`
- 删除扩展配置

影响：

- `normalizeFarm()` 会把后端数据和本地扩展配置 merge
- `handleSubmit()` 成功后会额外 `saveExtConfig(formData.farm_code, extPayload)`
- `handleDelete()` 成功后会 `removeExtConfig(row.farm_code)`

结论：

- 页面展示的数据并不完全可追溯到后端。
- 换浏览器或清理本地存储后，部分字段可能消失。

#### 4.1.4 核心业务方法

1. `fetchFarms()`
- 触发时机：
  - 页面 `onMounted`
  - 新增/编辑成功后
  - 启停切换成功后
  - 删除成功后
- 行为：
  - `loading = true`
  - 调用 `getFarms()`
  - 对返回数据执行 `normalizeFarm()`
  - 如果当前是地图视图，则 `nextTick(renderMapChart())`
  - `finally` 里关闭 `loading`

2. `openCreateDrawer()`
- 重置表单
- 设置 `isEdit = false`
- 默认 tab `basic`
- 打开抽屉

3. `openEditDrawer(row)`
- 将当前行字段灌入 `formData`
- 设置 `isEdit = true`
- 打开抽屉

4. `buildExtPayload()`
- 从 `formData` 提取本地扩展字段
- 这些字段会写入 `localStorage`

5. `handleSubmit()`
- 调用 `formRef.validate()`
- 组装：
  - `locationText`
  - `extPayload`
  - `payload`
- 如果是编辑：
  - `updateFarm(formData.farm_code, payload)`
- 如果是新增：
  - `createFarm({ farm_code: formData.farm_code, ...payload })`
- 成功后：
  - `saveExtConfig(formData.farm_code, extPayload)`
  - 关闭抽屉
  - `fetchFarms()`

6. `handleSetActive(row, nextActive)`
- 调用 `updateFarm(row.farm_code, { is_active: !!nextActive })`
- 成功后提示并刷新列表
- 失败时 `ElMessage.error` + `console.error`

7. `handleTogglePredict(row)`
- 只是 `handleSetActive(row, !row.is_active)` 的包装
- 结论：页面文案是“启停预测”，实际底层改的是同一个 `is_active`

8. `handleDelete(row)`
- 先 `ElMessageBox.confirm`
- 再 `deleteFarm(row.farm_code)`
- 删除本地扩展配置
- 刷新列表

9. `renderMapChart()`
- 将 `coordFarms` 转成 ECharts 散点数据
- symbol 大小与容量相关
- 颜色与 `is_active` 状态相关
- label 展示 `farmCode`

### 4.2 子组件：StatusDot

| 维度 | 结论 |
|---|---|
| 组件名称 | `StatusDot` |
| 文件路径 | [StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue) |
| 父子关系 | 被 [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue) 多处引用 |
| props / emits / callbacks | `props.active: Boolean`；无 emits |
| 内部 state / computed / hooks / store 使用情况 | `computed(statusClass)` |
| 生命周期或副作用逻辑 | 无 |
| 实现的具体功能 | 根据 `active` 显示绿色脉冲点或灰色静态点 |
| 触发了哪些接口 | 无 |
| 与其他组件的联动关系 | 纯展示组件，依赖父组件传入的 `row.is_active` |
| 加载态 / 空态 / 异常态如何处理 | 无专门处理 |

细节：

- `active = true`
  - class `active`
  - 绿色 + pulse 动画
- `active = false`
  - class `inactive`
  - 灰色静态点

---

## 5. 交互明细表

### 5.1 页面级操作

| 元素类型 | 位置 | 文案 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 单选组 | 顶部工具栏 | 卡片/表格/地图 | 切换主视图 | 修改 `viewMode`；切到地图时触发 `renderMapChart()` | 否 | 否 | 影响主内容区 |
| 按钮 | 顶部工具栏 | 新增场站 | 打开新增抽屉 | `openCreateDrawer()` | 否 | 否 | 影响抽屉 |

### 5.2 卡片/表格行操作

| 元素类型 | 位置 | 文案 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 开关 | 卡片视图/表格状态列 | 启用/停用 | 切换场站启停状态 | `handleSetActive(row, val)` | 否 | 是，`updateFarm` | 影响列表状态、StatusDot、地图颜色 |
| 按钮 | 卡片/表格操作列 | 编辑配置 | 打开编辑抽屉 | `openEditDrawer(row)` | 否 | 否 | 影响抽屉 |
| 按钮 | 卡片/表格操作列 | 启停预测 | 切换预测状态 | 实际调用 `handleTogglePredict(row)` -> `handleSetActive(row, !row.is_active)` | 否 | 是，`updateFarm` | 影响列表状态 |
| 按钮 | 卡片/表格操作列 | 删除 | 删除场站 | 先确认，再 `deleteFarm`，再删本地 ext 配置 | 否 | 是，`deleteFarm` | 影响列表、地图、本地缓存 |

### 5.3 抽屉表单元素

由于字段较多，这里按 tab 汇总。

#### Basic

| 元素类型 | 字段 | 功能 | 是否触发接口 |
|---|---|---|---|
| 输入框 | `farm_name` | 场站名称 | 否 |
| 输入框 | `farm_code` | 场站编码；编辑态禁用 | 否 |
| 日期选择器 | `commissioning_date` | 投运日期 | 否 |
| 数字输入 | `capacity` | 装机容量 | 否 |
| 数字输入 | `longitude` | 经度 | 否 |
| 数字输入 | `latitude` | 纬度 | 否 |
| 数字输入 | `altitude` | 海拔 | 否 |
| 输入框 | `province` | 省份 | 否 |
| 输入框 | `region` | 区域 | 否 |

#### Hardware

| 元素类型 | 字段 | 功能 | 是否触发接口 |
|---|---|---|---|
| 数字输入 | `turbine_count` | 风机数量 | 否 |
| 数字输入 | `hub_height` | 轮毂高度 | 否 |
| 数字输入 | `met_tower_count` | 测风塔数量 | 否 |
| 输入框 | `power_curve_file_name` | 功率曲线文件名 | 否 |
| 文本域 | `power_curve_url` | 功率曲线地址或说明 | 否 |

#### Model

| 元素类型 | 字段 | 功能 | 是否触发接口 |
|---|---|---|---|
| 下拉框 | `supershort_model` | 超短期模型 | 否 |
| 下拉框 | `short_model` | 短期模型 | 否 |
| 数字输入 | `lower_power_limit` | 下限功率 | 否 |
| 数字输入 | `curtailment_threshold` | 限电阈值 | 否 |

#### Mapping

| 元素类型 | 字段 | 功能 | 是否触发接口 |
|---|---|---|---|
| 输入框 | `point_act_power` | 实际功率点位 | 否 |
| 输入框 | `point_wind_speed` | 风速点位 | 否 |
| 输入框 | `point_avail_count` | 可用机位点位 | 否 |
| 下拉框 | `scada_status` | SCADA 数据状态 | 否 |
| 下拉框 | `nwp_status` | NWP 数据状态 | 否 |
| 数字输入 | `current_actual_power` | 当前实际功率 | 否 |
| 开关 | `is_active` | 场站启停 | 否 |

### 5.4 抽屉 footer 操作

| 元素类型 | 位置 | 文案 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 按钮 | 抽屉 footer | 取消 | 关闭抽屉 | `drawerVisible = false` | 否 | 否 | 否 |
| 按钮 | 抽屉 footer | 提交 | 保存场站 | `handleSubmit()`，根据 `isEdit` 调 `createFarm` 或 `updateFarm` | 否 | 是 | 影响列表、地图、本地缓存 |

### 5.5 页面中未发现的元素

- 搜索栏
- 页面级筛选下拉
- 分页
- 导出
- 上传导入
- URL query 同步

---

## 6. 接口明细表

### 6.1 `getFarms`

| 字段 | 说明 |
|---|---|
| 接口名称 | 获取场站列表 |
| 请求方法 | `GET` |
| URL | 优先 `/api/v1/farms`，回退 `/api/farms` |
| 所在 api/service 文件 | [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js) |
| 调用函数名 | `getFarms()` |
| 调用触发条件 | 页面初始化；新增/编辑/删除/状态切换成功后 |
| 请求参数 | 无 |
| 返回数据结构 | `unwrapList(response?.data)`；支持 `response.data` 为数组，或 `response.data.data` 为数组 |
| 返回数据映射到页面哪个组件/哪个字段 | 映射到 `farms`，再经 `normalizeFarm()` 用于卡片、表格、地图 |
| 失败时页面怎么处理 | 页面内未单独 catch；依赖 [axios.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/axios.js) 全局错误提示 |

### 6.2 `createFarm`

| 字段 | 说明 |
|---|---|
| 接口名称 | 新增场站 |
| 请求方法 | `POST` |
| URL | 优先 `/api/v1/farms`，回退 `/api/farms` |
| 所在 api/service 文件 | [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js) |
| 调用函数名 | `createFarm(payload)` |
| 调用触发条件 | 抽屉点击提交且 `isEdit === false` |
| 请求参数 | `{ farm_code, farm_name, capacity, location, is_active, ...extPayload }` |
| 返回数据结构 | `response?.data`，页面不直接消费返回字段 |
| 返回数据映射到页面哪个组件/哪个字段 | 不直接映射；成功后重新 `fetchFarms()` |
| 失败时页面怎么处理 | 页面内未局部 catch；依赖 axios 全局错误提示；`submitting` 在 finally 里恢复 |

### 6.3 `updateFarm`

| 字段 | 说明 |
|---|---|
| 接口名称 | 更新场站 |
| 请求方法 | `PUT` |
| URL | 优先 `/api/v1/farms/{farmCode}`，回退 `/api/farms/{farmCode}` |
| 所在 api/service 文件 | [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js) |
| 调用函数名 | `updateFarm(farmCode, payload)` |
| 调用触发条件 | 编辑提交；启停切换 |
| 请求参数 | 编辑提交时为完整 payload；启停切换时仅 `{ is_active: !!nextActive }` |
| 返回数据结构 | `response?.data` |
| 返回数据映射到页面哪个组件/哪个字段 | 不直接消费；成功后刷新列表 |
| 失败时页面怎么处理 | 编辑提交未局部 catch，依赖 axios 全局错误；启停切换在 `handleSetActive` 中有局部 `ElMessage.error` |

### 6.4 `deleteFarm`

| 字段 | 说明 |
|---|---|
| 接口名称 | 删除场站 |
| 请求方法 | `DELETE` |
| URL | 优先 `/api/v1/farms/{farmCode}`，回退 `/api/farms/{farmCode}` |
| 所在 api/service 文件 | [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js) |
| 调用函数名 | `deleteFarm(farmCode)` |
| 调用触发条件 | 用户确认删除后 |
| 请求参数 | `farmCode` 路径参数 |
| 返回数据结构 | `response?.data` |
| 返回数据映射到页面哪个组件/哪个字段 | 不直接消费；成功后刷新列表并清理本地缓存 |
| 失败时页面怎么处理 | 代码中未局部 catch；依赖 axios 全局错误提示 |

### 6.5 API 封装隐性逻辑

`farmApi.js` 共有两个重要基础逻辑：

1. `withLegacyFallback(v1Call, legacyCall)`
- 优先调用 v1 接口
- 当无响应或 `404/405` 时自动回退旧接口

2. `unwrapList(payload)`
- 兼容返回结构：
  - 直接数组
  - `{ data: [] }`

结论：

- 该页兼容新旧后端接口协议。
- 页面层看不到回退过程，属于 API 层隐性兼容逻辑。

---

## 7. 数据流说明

### 7.1 初始化加载流程

1. 组件 `onMounted`
2. 调用 `fetchFarms()`
3. `getFarms()` 从后端获取列表
4. 每条数据进入 `normalizeFarm()`
5. `normalizeFarm()` 再合并 `localStorage` 扩展配置
6. `farms` 更新
7. 如果当前视图是 `map`，则 `renderMapChart()`
8. 注册 `window.resize` 监听

### 7.2 用户操作后数据变化

#### 新增场站

1. 点击“新增场站”
2. `resetForm()`
3. 填写表单
4. `handleSubmit()`
5. `createFarm(...)`
6. `saveExtConfig(...)`
7. 关闭抽屉
8. `fetchFarms()`

#### 编辑场站

1. 点击“编辑配置”
2. 行数据写入 `formData`
3. `handleSubmit()`
4. `updateFarm(farmCode, payload)`
5. `saveExtConfig(...)`
6. 刷新列表

#### 启停切换

1. 点击开关或“启停预测”
2. `handleSetActive(row, nextActive)`
3. `updateFarm(row.farm_code, { is_active })`
4. 成功后刷新列表

#### 删除场站

1. 点击删除
2. 弹确认框
3. `deleteFarm(row.farm_code)`
4. `removeExtConfig(row.farm_code)`
5. 刷新列表

### 7.3 状态分类

#### 本地状态

- `loading`
- `submitting`
- `drawerVisible`
- `isEdit`
- `viewMode`
- `activeTab`
- `formData`
- `mapChart`

#### 全局 store 状态

- 代码中未发现

#### 后端接口数据

- `getFarms()` 返回的基础场站数据

#### 本地缓存数据

- `farm_management_ext_configs_v1`

#### 二次加工/格式化字段

- `normalizeFarm()` 合并后的最终列表项
- `coordFarms`
- `toMw()`
- `formatCoord()`
- `normalizeSourceLabel()`

### 7.4 数据源闭环结论

该页当前的数据闭环是：

`后端场站主数据` + `localStorage 扩展字段` -> `normalizeFarm()` -> `三视图展示`

这意味着：

- 同一条场站记录的不同字段可能来自不同持久化介质
- 页面展示结果不完全等于后端原始返回

---

## 8. 权限与状态控制说明

### 8.1 路由与菜单权限

1. 路由声明位置
- 文件：[router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- 路由：
  - `path: 'farmmanagement'`
  - `name: 'FarmManagement'`
  - `meta.requiredPermissions = ['manage_reports']`

2. 菜单显隐位置
- 文件：[AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- 菜单项：
  - `index="/farmmanagement"`
  - 条件：`hasPermission('manage_reports')`

### 8.2 实际守卫行为

全局守卫位于 [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)：

- 只校验 `localStorage.getItem('user')`
- 未发现基于 `requiredPermissions` 的真正拦截逻辑

### 8.3 页面内部权限控制

代码中未发现：

- `v-permission`
- `hasPermission`
- 新增/编辑/删除按钮级权限判断
- 字段级禁用控制（除编辑态禁用 `farm_code` 外）

---

## 9. 风险点 / 待确认点

### 9.1 明确风险点

1. 页面数据来源混合  
证据：`normalizeFarm()` 会把后端返回与 `localStorage` 扩展配置合并。

2. 本地扩展字段可能导致环境不一致  
证据：`saveExtConfig/removeExtConfig/readExtConfigMap` 都基于浏览器 `localStorage`。

3. “启停预测”与“场站启停”实际共用同一接口字段  
证据：`handleTogglePredict(row)` 只是 `handleSetActive(row, !row.is_active)` 的包装。

4. 地图视图不是地图底图  
证据：ECharts 使用的是数值轴散点图，无 Geo 地图配置。

5. 提交失败时多数错误提示依赖 axios 全局兜底  
证据：`handleSubmit()` 未局部 catch。

6. 页面没有搜索、分页、筛选  
证据：模板中未发现对应控件。

7. 路由权限声明未在全局守卫中落地  
证据：`beforeEach` 只检查登录态。

### 9.2 待确认点

1. 扩展字段是否本应由后端统一存储  
当前判断：高度可能，需结合后端确认。

2. `updateFarm` 是否接受全部扩展字段  
当前判断：前端会把 `extPayload` 一并发给后端，但后端是否落库需结合后端确认。

3. “启停预测”是否应独立于 `is_active`  
当前判断：从当前前端实现看并未独立，需结合业务确认。

4. 地图视图是否计划升级为真实地理底图  
当前判断：代码中未发现。

---

## 10. 代码证据清单

### 10.1 页面文件

- [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue)
  - 组件名：`FarmManagement`
  - 关键状态：`farms`、`viewMode`、`formData`、`drawerVisible`
  - 关键函数：
    - `fetchFarms()`
    - `normalizeFarm()`
    - `buildExtPayload()`
    - `handleSubmit()`
    - `handleSetActive()`
    - `handleTogglePredict()`
    - `handleDelete()`
    - `renderMapChart()`
    - `readExtConfigMap()/saveExtConfig()/removeExtConfig()`

### 10.2 子组件

- [StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue)
  - `props.active`
  - `statusClass`

### 10.3 API 文件

- [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js)
  - `getFarms()`
  - `createFarm(payload)`
  - `updateFarm(farmCode, payload)`
  - `deleteFarm(farmCode)`
  - `withLegacyFallback(...)`
  - `unwrapList(...)`

- [axios.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/axios.js)
  - 请求头注入 `Authorization`
  - 401 清登录态并跳登录页
  - 网络错误与通用错误全局提示

### 10.4 路由与权限入口

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - 路由名：`FarmManagement`
  - 路由路径：`farmmanagement`
  - 权限元信息：`requiredPermissions: ['manage_reports']`
  - 守卫：`beforeEach(...)`

- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - 菜单项：`index="/farmmanagement"`
  - 权限判断：`hasPermission('manage_reports')`

---

## 关键代码证据清单

- [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue)
- [StatusDot.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/common/StatusDot.vue)
- [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js)
- [axios.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/axios.js)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)

## 可能遗漏点检查清单

- 后端 `updateFarm` 对扩展字段的真实落库范围，当前代码中未明确
- 页面中文文案终端乱码，字段逻辑已核对，但展示文案建议在编辑器复核
- 是否存在与 `farmService` 的场站上下文同步，当前页面未接入
- 是否存在批量导入/导出能力，当前页面未发现
- 是否存在场站删除后的跨页面联动刷新，当前代码中未发现
