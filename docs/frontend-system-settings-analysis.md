# 系统基础配置代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 系统基础配置 |
| 所属模块 | 系统管理 |
| 路由路径 | `/system-settings` |
| 页面入口文件 | [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue) |
| 页面依赖的子组件列表 | 代码中未发现本项目自定义子组件；页面直接使用 Element Plus 组件 `el-row`、`el-col`、`el-card`、`el-date-picker`、`el-input`、`el-button`、`el-table`、`el-table-column`、`el-form`、`el-form-item`、`el-input-number` |
| 页面依赖的 store/hooks/model/service/api 文件 | 页面代码中未发现 `store/hooks/model/service/api` 直接引用；仓库存在 [systemApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/systemApi.js)，但本页未使用 |
| 页面是否受权限控制 | 路由声明 `meta.requiredPermissions = ['manage_system_settings', 'system_maintenance']`；侧边栏菜单显隐条件为 `hasPermission('manage_system_settings') || hasPermission('system_maintenance')`；页面内部未发现按钮级权限控制 |

### 1.2 页面定位结论

基于当前代码，系统基础配置是一个本地静态配置原型页，并未接入真实系统配置保存或读取接口。当前页面真正形成的闭环只有：

- 本地新增节假日记录
- 本地修改字典输入框内容
- 本地修改数据保留参数

但这些改动都只停留在前端内存状态，不会持久化。

### 1.3 关键判断

1. 页面没有引入任何 API/service/store/hooks。
2. “新增节假日”只会把一条记录插入本地 `holidays` 数组。
3. “保存配置”按钮没有绑定点击事件，不会触发任何逻辑。
4. 仓库虽然存在 [systemApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/systemApi.js)，但它提供的是硬件/软件/runtime/logs 查询，不是本页配置保存接口。

---

## 2. 页面结构树

```text
系统基础配置 SystemSettings.vue
├─ 页面根容器 system-settings page-shell
│  ├─ 页面头部 page-header
│  │  ├─ 标题 h2
│  │  └─ 描述文本 p
│  ├─ 上半区 el-row
│  │  ├─ 左卡片 节假日配置
│  │  │  ├─ 日期选择器
│  │  │  ├─ 节假日说明输入框
│  │  │  ├─ 新增按钮
│  │  │  └─ 节假日表格
│  │  └─ 右卡片 字典配置
│  │     └─ 两个输入框
│  └─ 下半区 el-card
│     ├─ 数据保留参数表单
│     │  ├─ 预测数据保留月数
│     │  ├─ 日志保留天数
│     │  └─ 磁盘告警阈值
│     └─ 保存配置按钮
```

---

## 3. 区块说明

### 3.1 页面头部

| 字段 | 说明 |
|---|---|
| 区块名称 | 页面头部 |
| 对应组件名 | `SystemSettings` |
| 文件路径 | [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue) |
| 展示内容 | 页面标题和说明文案 |
| 数据来源 | 模板硬编码文本 |
| 是否可交互 | 否 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 否 |

### 3.2 节假日配置区

| 字段 | 说明 |
|---|---|
| 区块名称 | 节假日配置区 |
| 对应组件名 | `SystemSettings` |
| 文件路径 | [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue) |
| 展示内容 | 日期选择器、节假日说明输入框、新增按钮、节假日表格 |
| 数据来源 | `holidayDate`、`holidayNote`、`holidays` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

数据结构：

- `holidayDate`
- `holidayNote`
- `holidays = [{ date, note }]`

交互逻辑：

- `addHoliday()`
  - 如果 `holidayDate` 为空则直接返回
  - 否则向 `holidays` 首位插入新记录
  - 默认说明文案为“特殊日历”（终端显示有乱码，但逻辑可确认）
  - 清空 `holidayDate` 与 `holidayNote`

结论：

- 没有删除节假日、编辑节假日、持久化保存逻辑。

### 3.3 字典配置区

| 字段 | 说明 |
|---|---|
| 区块名称 | 字典配置区 |
| 对应组件名 | `SystemSettings` |
| 文件路径 | [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue) |
| 展示内容 | 风机机型字典、厂家字典两个输入框 |
| 数据来源 | `dict` 响应式对象 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

字段：

- `dict.turbineModels`
- `dict.vendors`

结论：

- 字典数据只存在本地内存。
- 代码中未发现字典项拆分、增删行、枚举服务、统一字典中心。

### 3.4 数据保留参数区

| 字段 | 说明 |
|---|---|
| 区块名称 | 数据保留参数区 |
| 对应组件名 | `SystemSettings` |
| 文件路径 | [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue) |
| 展示内容 | 预测数据保留月数、日志保留天数、磁盘告警阈值、保存按钮 |
| 数据来源 | `params` 响应式对象 |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

字段：

- `params.retentionMonths`
- `params.logRetentionDays`
- `params.diskAlertPercent`

关键事实：

- 页面底部“保存配置”按钮没有 `@click`
- 也没有任何方法名与之绑定

结论：

- 当前这块只能改 UI 状态，不能真正保存。

---

## 4. 组件明细表

### 4.1 页面组件：SystemSettings

| 维度 | 结论 |
|---|---|
| 组件名称 | `SystemSettings` |
| 文件路径 | [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue) |
| 父子关系 | 父级为 [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 中的 `<router-view>`；代码中未发现本项目自定义子组件 |
| props / emits / callbacks | 未定义 `props`、未定义 `emits` |
| 内部 state / computed / hooks / store 使用情况 | `ref(holidayDate)`、`ref(holidayNote)`、`ref(holidays)`、`reactive(dict)`、`reactive(params)`；未使用 computed、未使用 store/hooks |
| 生命周期或副作用逻辑 | 代码中未发现 `onMounted`、`watch`、`setInterval` |
| 实现的具体功能 | 本地节假日列表管理、本地字典输入、本地保留参数输入 |
| 触发了哪些接口 | 代码中未发现 |
| 与其他组件的联动关系 | 无自定义子组件联动 |
| 加载态 / 空态 / 异常态如何处理 | 代码中未发现加载态、空态、异常态 |

#### 4.1.1 本地状态拆解

1. `holidayDate`
- 节假日日期输入

2. `holidayNote`
- 节假日说明输入

3. `holidays`
- 节假日表格数据
- 默认有 1 条样例数据

4. `dict`
- 字典配置
- 包含：
  - `turbineModels`
  - `vendors`

5. `params`
- 数据保留参数
- 包含：
  - `retentionMonths`
  - `logRetentionDays`
  - `diskAlertPercent`

#### 4.1.2 方法拆解

1. `addHoliday()`
- 触发条件：
  - 点击节假日区“新增”按钮
- 前置判断：
  - `holidayDate` 必须有值
- 行为：
  - `holidays.unshift({ date, note })`
  - 没填说明时使用默认说明文案
  - 清空 `holidayDate`、`holidayNote`

结论：

- 页面中只定义了这一个方法。
- 没有保存配置方法、删除方法、重置方法。

#### 4.1.3 页面内未发现的逻辑

- `computed`
- `watch`
- `watchEffect`
- `onMounted`
- `onUnmounted`
- `async/await`
- API 请求
- 本地缓存
- WebSocket

### 4.2 使用到的三方组件

本页没有本项目自定义子组件，但直接依赖以下 Element Plus 组件：

| 组件 | 用途 |
|---|---|
| `el-row` / `el-col` | 左右布局 |
| `el-card` | 承载配置区 |
| `el-date-picker` | 节假日日期选择 |
| `el-input` | 节假日说明、字典输入 |
| `el-button` | 新增按钮、保存按钮 |
| `el-table` | 节假日表格 |
| `el-table-column` | 表格列 |
| `el-form` / `el-form-item` | 数据保留参数表单 |
| `el-input-number` | 数值配置输入 |

---

## 5. 交互明细表

### 5.1 节假日配置区

| 元素类型 | 位置 | 文案/字段 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 日期选择器 | 节假日卡片 | 日期 | 选择节假日日期 | 更新 `holidayDate` | 否 | 否 | 影响新增入表数据 |
| 输入框 | 节假日卡片 | 说明 | 输入节假日说明 | 更新 `holidayNote` | 否 | 否 | 影响新增入表数据 |
| 按钮 | 节假日卡片 | 新增 | 新增节假日记录 | 调用 `addHoliday()` | 否 | 否 | 影响节假日表格 |
| 表格 | 节假日卡片 | 日期/说明 | 展示节假日记录 | 无行操作 | 否 | 否 | 否 |

### 5.2 字典配置区

| 元素类型 | 位置 | 文案/字段 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 输入框 | 字典卡片 | 风机机型字典 | 编辑字典文本 | 更新 `dict.turbineModels` | 否 | 否 | 否 |
| 输入框 | 字典卡片 | 厂家字典 | 编辑字典文本 | 更新 `dict.vendors` | 否 | 否 | 否 |

### 5.3 数据保留参数区

| 元素类型 | 位置 | 文案/字段 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 数字输入 | 下方卡片 | 预测数据保留月数 | 修改保留月数 | 更新 `params.retentionMonths` | 否 | 否 | 否 |
| 数字输入 | 下方卡片 | 日志保留天数 | 修改日志保留天数 | 更新 `params.logRetentionDays` | 否 | 否 | 否 |
| 数字输入 | 下方卡片 | 磁盘告警阈值 | 修改阈值 | 更新 `params.diskAlertPercent` | 否 | 否 | 否 |
| 按钮 | 下方卡片 | 保存配置 | 视觉上表示保存 | 代码中未绑定事件，点击无业务行为 | 否 | 否 | 否 |

### 5.4 页面中未发现的元素

- 搜索框
- 下拉框
- tab
- 图表
- 标签
- 状态图标
- 弹窗
- 抽屉
- tooltip
- 刷新按钮
- 重置按钮
- 导出下载
- 上传导入

---

## 6. 接口明细表

### 6.1 页面直接接口

| 接口名称 | 请求方法 | URL | 所在 api/service 文件 | 调用函数名 | 调用触发条件 | 请求参数 | 返回数据结构 | 返回数据映射到页面哪个组件/哪个字段 | 失败时页面怎么处理 |
|---|---|---|---|---|---|---|---|---|---|
| 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 |

结论：

- 本页面没有任何 HTTP 接口调用。

### 6.2 仓库内存在但本页未接入的相关系统接口

| 能力名称 | 请求方法 | URL | 文件 | 当前页面是否接入 |
|---|---|---|---|---|
| 获取系统硬件信息 | `GET` | `/api/v1/system/hardware` 或 `/api/system/hardware` | [systemApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/systemApi.js) | 否 |
| 获取系统软件信息 | `GET` | `/api/v1/system/software` 或 `/api/system/software` | [systemApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/systemApi.js) | 否 |
| 获取系统运行时信息 | `GET` | `/api/v1/system/runtime` 或 `/api/system/runtime` | [systemApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/systemApi.js) | 否 |
| 获取系统日志 | `GET` | `/api/v1/system/logs` 或 `/api/system/logs` | [systemApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/systemApi.js) | 否 |

说明：

- `systemApi.js` 存在，但它服务的更像系统监控/系统日志能力，不是本页的“基础配置保存”能力。
- 代码中未发现“读取基础配置”“保存基础配置”的系统配置 API。

---

## 7. 数据流说明

### 7.1 初始化加载流程

页面初始化流程如下：

1. 进入 `setup()`
2. 初始化本地状态：
   - `holidayDate = ''`
   - `holidayNote = ''`
   - `holidays = 默认样例数组`
   - `dict = 默认字典文本`
   - `params = 默认保留参数`
3. 模板直接渲染页面

说明：

- 没有 `onMounted`
- 没有接口请求
- 没有本地存储恢复

### 7.2 用户操作后的数据变化

#### 新增节假日

1. 选择日期
2. 输入说明
3. 点击“新增”
4. 调用 `addHoliday()`
5. 若日期为空则直接返回
6. 否则新记录插入 `holidays` 首位
7. 清空输入框

#### 修改字典

- 直接写入 `dict.turbineModels`
- 直接写入 `dict.vendors`

#### 修改保留参数

- 直接写入 `params.retentionMonths`
- 直接写入 `params.logRetentionDays`
- 直接写入 `params.diskAlertPercent`

#### 点击“保存配置”

- 代码中未绑定点击事件
- 不会触发任何数据变化

### 7.3 状态分类

#### 本地状态

- `holidayDate`
- `holidayNote`
- `holidays`
- `dict`
- `params`

#### 全局 store 状态

- 代码中未发现

#### 后端接口数据

- 代码中未发现

#### 二次加工/格式化字段

- `addHoliday()` 中新增记录的默认 `note`

### 7.4 数据源闭环结论

当前页面的数据闭环是：

`本地默认值` -> `页面交互修改` -> `本地响应式更新`

没有形成：

`后端读取配置` -> `页面编辑` -> `后端保存配置` -> `重新回显`

---

## 8. 权限与状态控制说明

### 8.1 路由与菜单权限

1. 路由声明位置
- 文件：[router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- 路由：
  - `path: 'system-settings'`
  - `name: 'SystemSettings'`
  - `meta.requiredPermissions = ['manage_system_settings', 'system_maintenance']`

2. 菜单显隐位置
- 文件：[AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- 菜单项：
  - `index="/system-settings"`
  - 条件：`hasPermission('manage_system_settings') || hasPermission('system_maintenance')`

### 8.2 实际守卫行为

全局守卫位于 [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)：

- 只校验 `localStorage.getItem('user')`
- 未发现基于 `requiredPermissions` 的真正拦截逻辑

### 8.3 页面内部权限控制

代码中未发现：

- `v-permission`
- `hasPermission`
- 按钮级 `v-if`
- 字段级禁用

---

## 9. 风险点 / 待确认点

### 9.1 明确风险点

1. 页面为静态原型，未接真实系统配置接口  
证据：页面未引入任何 API/service；“保存配置”没有事件绑定。

2. 页面所有配置修改都不会持久化  
证据：仅修改本地 `ref/reactive` 状态，没有本地存储和后端提交。

3. 节假日只有新增，没有删除/编辑  
证据：表格无操作列，代码中无对应方法。

4. 字典配置只是两个文本输入框，不是结构化字典管理  
证据：`dict` 仅有两个字符串字段。

5. 页面与系统 API 文件脱节  
证据：`systemApi.js` 存在，但本页未使用；且其接口语义并非配置保存。

6. 路由权限声明未在全局守卫中落地  
证据：`beforeEach` 只检查登录态。

### 9.2 待确认点

1. 是否存在后端系统配置接口但前端尚未接入  
当前判断：很可能，需结合后端确认。

2. “字典配置”是否计划拆成独立模块  
当前判断：当前代码中未明确。

3. “保存配置”按钮是否只是 UI 占位  
当前判断：从代码看是占位按钮。

4. 节假日数据是否本应参与报表/免考逻辑  
当前判断：页面文案未明确，代码中未发现联动。

5. 页面中文文案终端存在乱码  
当前判断：更可能是终端编码问题，不影响逻辑分析；显示文案建议在编辑器内复核。

---

## 10. 代码证据清单

### 10.1 页面文件

- [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue)
  - 组件名：`SystemSettings`
  - 状态：`holidayDate`、`holidayNote`、`holidays`、`dict`、`params`
  - 方法：`addHoliday()`

### 10.2 相关但未接入的系统 API

- [systemApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/systemApi.js)
  - `getSystemHardware()`
  - `getSystemSoftware()`
  - `getSystemRuntime()`
  - `getSystemLogs()`

### 10.3 路由与权限入口

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - 路由名：`SystemSettings`
  - 路由路径：`system-settings`
  - 权限元信息：`requiredPermissions: ['manage_system_settings', 'system_maintenance']`
  - 守卫：`beforeEach(...)`

- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - 菜单项：`index="/system-settings"`
  - 权限判断：`hasPermission('manage_system_settings') || hasPermission('system_maintenance')`

- [permissions.js](D:/my-vue-project/wind-power-forecast/frontend/src/constants/permissions.js)
  - 权限 key：`manage_system_settings`
  - 权限 key：`system_maintenance`

---

## 关键代码证据清单

- [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue)
- [systemApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/systemApi.js)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- [permissions.js](D:/my-vue-project/wind-power-forecast/frontend/src/constants/permissions.js)

## 可能遗漏点检查清单

- 是否存在真实系统配置接口在后端但前端未接入，当前代码中未发现
- 是否存在系统配置本地缓存或统一配置中心，当前页面未接入
- 节假日是否应与报表/考核逻辑联动，当前代码中未发现
- 页面中文文案终端乱码，建议在编辑器中复核展示内容
