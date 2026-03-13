# 统一告警中心代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 统一告警中心 |
| 所属模块 | 运维与质量 |
| 路由路径 | `/alarm-center` |
| 页面入口文件 | [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue) |
| 页面依赖的子组件列表 | 代码中未发现自定义子组件；页面直接使用 Element Plus 组件 `el-card`、`el-switch`、`el-button`、`el-table`、`el-table-column`、`el-tag` |
| 页面依赖的 store/hooks/model/service/api 文件 | 页面代码中未发现 `store/hooks/model/service/api` 直接引用；仅使用 Vue `ref`、`computed`。仓库中存在 [websocketService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/websocketService.js) 的告警接收能力，但本页面未接入 |
| 页面是否受权限控制 | 路由声明 `meta.requiredPermissions = ['view_alarm_center', 'manage_reports']`；侧边栏菜单显隐条件为 `hasPermission('view_alarm_center') || hasPermission('manage_reports')`；代码中未发现页面内部按钮级权限控制 |

### 1.2 页面定位结论

基于当前代码，统一告警中心更像一个前端静态原型页，而不是已经接入真实告警数据流的正式业务页。页面功能闭环只覆盖：

- 本地告警列表展示
- 本地红色/黄色告警数量统计
- 本地“页面告警音”开关
- 本地“短信网关”开关展示
- 点击“刷新”时触发浏览器蜂鸣声

页面未闭环的能力包括：

- 后端告警列表拉取
- 告警确认、消警、指派、屏蔽、升级
- 告警来源订阅
- 实时推送接入
- 告警查询筛选
- 告警详情
- 持久化通知策略

### 1.3 关键判断

1. 页面主数据 `alerts` 是本地静态数组，不来自接口。
2. 页面没有 `onMounted`、`watch`、`setInterval`、`async/await`，不存在初始化请求和自动刷新。
3. 页面没有调用任何 API，但仓库底层已存在 `farm:alert` / `farm:alert:received` 的 WebSocket 事件链。
4. 页面权限控制只存在于路由 `meta` 和布局菜单层；全局路由守卫当前只校验登录态，不真正执行 `requiredPermissions`。

---

## 2. 页面结构树

```text
统一告警中心 AlarmCenter.vue
├─ 页面根容器 alarm-center page-shell
│  ├─ 页面头部 page-header
│  │  ├─ 标题 h2
│  │  └─ 描述文本 p
│  └─ 告警主卡片 el-card.card-shell
│     ├─ 工具栏 toolbar
│     │  ├─ 告警音开关 el-switch(enableSound)
│     │  ├─ 短信网关开关 el-switch(enableSms)
│     │  └─ 刷新按钮 el-button(refresh)
│     ├─ 统计区 stats
│     │  ├─ 红色告警计数卡 dangerCount
│     │  └─ 黄色告警计数卡 warningCount
│     └─ 告警表格 el-table(alerts)
│        ├─ 告警时间列
│        ├─ 场站列
│        ├─ 级别列 el-tag
│        ├─ 模块列
│        ├─ 告警内容列
│        └─ 处置策略列
```

---

## 3. 区块说明

### 3.1 页面头部

| 字段 | 说明 |
|---|---|
| 区块名称 | 页面头部 |
| 对应组件名 | `AlarmCenter` |
| 文件路径 | [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue) |
| 展示内容 | 标题、副标题说明文案 |
| 数据来源 | 模板内硬编码文本 |
| 是否可交互 | 否 |
| 是否有权限控制 | 无单独权限控制 |
| 是否有定时刷新或自动更新 | 否 |

补充说明：

- 页面头部没有绑定任何状态变量。
- 文案不是通过常量文件或接口下发。

### 3.2 工具栏

| 字段 | 说明 |
|---|---|
| 区块名称 | 工具栏 |
| 对应组件名 | `AlarmCenter` |
| 文件路径 | [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue) |
| 展示内容 | 两个开关和一个刷新按钮 |
| 数据来源 | `enableSound`、`enableSms` 两个本地 `ref` |
| 是否可交互 | 是 |
| 是否有权限控制 | 代码中未发现 |
| 是否有定时刷新或自动更新 | 否 |

交互事实：

- `enableSound` 默认 `true`
- `enableSms` 默认 `false`
- 点击“刷新”只执行 `refresh()`，而 `refresh()` 内部只调用 `playBeep()`

结论：

- 工具栏并不触发后端刷新。
- “短信网关”开关只是本地 UI 状态，不代表真实短信链路。

### 3.3 统计区

| 字段 | 说明 |
|---|---|
| 区块名称 | 告警统计卡片 |
| 对应组件名 | `AlarmCenter` |
| 文件路径 | [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue) |
| 展示内容 | 红色告警数量、黄色告警数量 |
| 数据来源 | 基于本地 `alerts` 通过 `computed` 计算 |
| 是否可交互 | 否 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 否，只有 `alerts` 变化时响应式重算 |

具体计算：

- `dangerCount = alerts.filter(item => item.level === '红色').length`
- `warningCount = alerts.filter(item => item.level === '黄色').length`

说明：

- 当前 `alerts` 不会被异步更新，因此统计卡只会在本地数组被修改时变化。

### 3.4 告警表格区

| 字段 | 说明 |
|---|---|
| 区块名称 | 告警列表表格 |
| 对应组件名 | `AlarmCenter` |
| 文件路径 | [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue) |
| 展示内容 | 告警时间、场站、级别、模块、内容、处置策略 |
| 数据来源 | 本地 `alerts` 静态数组 + 本地开关 `enableSound`、`enableSms` |
| 是否可交互 | 部分可交互；表格本身无行操作按钮，但“处置策略”列会随开关变化 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 无接口刷新；随本地状态变化响应式更新 |

表格字段来源：

- `time`
- `station`
- `level`
- `module`
- `message`

“处置策略”列逻辑：

- 如果 `row.level === '红色'`
  - `enableSound === true` 时显示“页面警报声”
  - `enableSms === true` 时显示“短信网关”
  - 如果两个开关都关闭，则显示“未配置”
- 如果 `row.level !== '红色'`
  - 固定显示“观察”

结论：

- “处置策略”是前端即时拼接文案，不是后端返回字段。
- 表格没有确认、忽略、转派、查看详情等真实处理动作。

---

## 4. 组件明细表

### 4.1 页面组件：AlarmCenter

| 维度 | 结论 |
|---|---|
| 组件名称 | `AlarmCenter` |
| 文件路径 | [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue) |
| 父子关系 | 父级为布局路由容器 [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 中的 `<router-view>`；代码中未发现自定义子组件 |
| props / emits / callbacks | 代码中未定义 `props`、未定义 `emits`、未向外抛出回调 |
| 内部 state / computed / hooks / store 使用情况 | `ref(enableSound)`、`ref(enableSms)`、`ref(alerts)`、`computed(dangerCount)`、`computed(warningCount)`；未使用 store/hooks |
| 生命周期或副作用逻辑 | 代码中未发现 `onMounted`、`onUnmounted`、`watch`、`watchEffect` |
| 实现的具体功能 | 展示静态告警列表、根据本地数组计算红黄告警数量、根据本地开关生成处置策略文本、点击刷新时播放蜂鸣声 |
| 触发了哪些接口 | 代码中未发现 |
| 与其他组件的联动关系 | 与 [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 在路由和菜单层联动；页面内部无子组件联动 |
| 加载态 / 空态 / 异常态如何处理 | 代码中未发现加载态、空态；播放音频失败时 `catch` 后静默返回 |

#### 4.1.1 内部状态拆解

1. `enableSound`
- 类型：`ref<boolean>`
- 默认值：`true`
- 用途：
  - 控制刷新时是否播放蜂鸣声
  - 控制表格“处置策略”列是否显示“页面警报声”

2. `enableSms`
- 类型：`ref<boolean>`
- 默认值：`false`
- 用途：
  - 控制表格“处置策略”列是否显示“短信网关”

3. `alerts`
- 类型：`ref<Array>`
- 默认值：本地硬编码 4 条告警
- 字段：
  - `time`
  - `station`
  - `level`
  - `module`
  - `message`

#### 4.1.2 计算属性拆解

1. `dangerCount`
- 计算规则：过滤 `level === '红色'`
- 消费位置：统计区红色告警数量卡片

2. `warningCount`
- 计算规则：过滤 `level === '黄色'`
- 消费位置：统计区黄色告警数量卡片

#### 4.1.3 方法拆解

1. `playBeep()`
- 触发条件：
  - 用户点击刷新按钮
- 业务前置条件：
  - `enableSound.value === true`
  - `dangerCount.value > 0`
- 实现细节：
  - 通过 `window.AudioContext()` 创建音频上下文
  - 创建 `oscillator` 与 `gain`
  - 波形类型：`square`
  - 频率：`880`
  - 音量：`0.04`
  - 播放时长：`0.2` 秒
- 异常处理：
  - 使用 `try/catch`
  - 出现浏览器权限或兼容问题时静默返回，不给用户任何提示

2. `refresh()`
- 触发条件：
  - 点击刷新按钮
- 实现细节：
  - 只调用 `playBeep()`
- 结论：
  - 名称为“刷新”，但不执行数据刷新

### 4.2 使用到的三方组件

本页没有本项目自定义子组件，但直接依赖以下 Element Plus 组件：

| 组件 | 用途 |
|---|---|
| `el-card` | 承载主内容卡片 |
| `el-switch` | 切换告警音、短信网关 |
| `el-button` | 刷新按钮 |
| `el-table` | 展示告警列表 |
| `el-table-column` | 定义表格列 |
| `el-tag` | 显示告警级别标签 |

---

## 5. 交互明细表

### 5.1 工具栏交互

| 元素类型 | 位置 | 文案 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 开关 | 工具栏 | 红色告警播放警报声 | 控制是否允许浏览器蜂鸣音 | 修改 `enableSound`；影响刷新时是否发声，也影响表格“处置策略”列文本 | 否 | 否 | 影响本页统计表格展示 |
| 开关 | 工具栏 | 红色告警触发短信网关 | 控制处置策略列展示 | 修改 `enableSms`；只影响表格“处置策略”列文案 | 否 | 否 | 影响本页表格展示 |
| 按钮 | 工具栏 | 刷新 | 触发本地提醒 | 执行 `refresh()` -> `playBeep()`；不会重新拉取列表 | 否 | 否 | 不影响其他组件 |

### 5.2 统计与表格元素

| 元素类型 | 位置 | 文案/字段 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 卡片 | 统计区 | 红色告警 | 展示红色告警数量 | 无点击行为；依赖 `alerts` 自动更新 | 否 | 否 | 否 |
| 卡片 | 统计区 | 黄色告警 | 展示黄色告警数量 | 无点击行为；依赖 `alerts` 自动更新 | 否 | 否 | 否 |
| 表格 | 内容区 | 告警表格 | 展示所有告警行 | 无行点击、无操作列 | 否 | 否 | 否 |
| 标签 | 级别列 | 红色/黄色 | 用 `el-tag` 表示等级 | 无点击行为；红色映射 `danger`，其余映射 `warning` | 否 | 否 | 否 |
| 文本列 | 处置策略列 | 页面警报声/短信网关/未配置/观察 | 展示推导出的策略说明 | 由 `enableSound`、`enableSms`、`row.level` 共同决定 | 否 | 否 | 否 |

### 5.3 页面中未发现的可见元素

以下元素在代码中未发现：

- 输入框
- 下拉框
- 日期选择器
- tab
- 图表
- 弹窗
- 抽屉
- tooltip
- 重置按钮
- 导出按钮
- 保存按钮
- 提交按钮
- 上传导入入口

---

## 6. 接口明细表

### 6.1 页面直接接口

| 接口名称 | 请求方法 | URL | 所在 api/service 文件 | 调用函数名 | 调用触发条件 | 请求参数 | 返回数据结构 | 返回数据映射到页面哪个组件/哪个字段 | 失败时页面怎么处理 |
|---|---|---|---|---|---|---|---|---|---|
| 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 | 代码中未发现 |

结论：

- 本页面没有任何 HTTP 接口调用。

### 6.2 仓库内已存在但本页面未接入的相关实时能力

下表不是“本页已调用接口”，而是“仓库中与告警中心高度相关、但本页未接入的底层能力”，用于说明功能缺口。

| 能力名称 | 类型 | 文件 | 关键函数/事件 | 当前页面是否接入 |
|---|---|---|---|---|
| WebSocket 连接服务 | service | [websocketService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/websocketService.js) | `connect()`、`subscribeToFarm()`、`handleFarmAlert()` | 否 |
| 告警接收事件 | socket event | [websocketService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/websocketService.js) | `farm:alert` -> `farm:alert:received` | 否 |
| WebSocket 组合式封装 | composable | [websocketService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/websocketService.js) | `useWebSocketService(...).alerts` | 否 |

补充事实：

- `websocketService.js` 中 `handleFarmAlert(data)` 会在订阅场站命中后触发 `emit('farm:alert:received', data)`。
- 同文件下方组合式封装里，`alerts = ref([])`，并在 `handleAlertReceived(alert)` 中 `alerts.value.push(alert)`。
- 当前 [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue) 没有 `import websocketService`，也没有使用上述 `alerts` 响应式流。

---

## 7. 数据流说明

### 7.1 初始化加载流程

当前页面初始化流程非常简单：

1. Vue 执行 `setup()`
2. 初始化本地状态：
   - `enableSound = true`
   - `enableSms = false`
   - `alerts = 本地静态数组`
3. 基于 `alerts` 计算：
   - `dangerCount`
   - `warningCount`
4. 模板直接渲染页面

说明：

- 没有 `onMounted`
- 没有接口请求
- 没有异步加载
- 没有从路由参数读取条件

### 7.2 用户操作后的数据变化

1. 切换告警音开关
- 修改 `enableSound`
- 影响：
  - 刷新按钮是否会发声
  - 表格处置策略列的文案

2. 切换短信网关开关
- 修改 `enableSms`
- 影响：
  - 表格处置策略列的文案

3. 点击刷新
- 调用 `refresh()`
- `refresh()` 内部只调用 `playBeep()`
- 不会修改 `alerts`
- 不会重新计算来源数据

### 7.3 状态分类

#### 本地状态

- `enableSound`
- `enableSms`
- `alerts`

#### 全局 store 状态

- 代码中未发现

#### 后端接口数据

- 代码中未发现

#### 二次加工/格式化字段

- `dangerCount`
- `warningCount`
- 处置策略列展示文本

### 7.4 数据源闭环结论

本页当前的数据闭环为：

`本地静态 alerts` -> `computed 统计` -> `表格渲染/标签渲染/策略文本渲染`

没有形成：

`后端告警源` -> `前端接收` -> `告警列表更新` -> `确认/消警/通知`

---

## 8. 权限与状态控制说明

### 8.1 路由与菜单权限

1. 路由声明位置
- 文件：[router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- 路由：
  - `path: 'alarm-center'`
  - `name: 'AlarmCenter'`
  - `meta.requiredPermissions = ['view_alarm_center', 'manage_reports']`

2. 菜单显隐位置
- 文件：[AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- 菜单项：
  - `index="/alarm-center"`
  - 条件：`hasPermission('view_alarm_center') || hasPermission('manage_reports')`

3. 顶部铃铛入口
- 文件：[AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- `goAlerts()` 直接 `router.push('/alarm-center')`

### 8.2 实际守卫行为

全局守卫位于 [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)：

- 只校验 `localStorage.getItem('user')`
- 未发现基于 `meta.requiredPermissions` 的真正拦截逻辑

结论：

- 路由虽然声明了权限标识，但当前仓库中页面访问限制主要依赖菜单隐藏和登录态判断。
- 如果用户已登录且知道地址，是否能直接访问该页，需结合运行时验证；从当前守卫代码看，前端路由层未做权限拦截。

### 8.3 页面内部权限控制

代码中未发现：

- `v-permission`
- `hasPermission`
- 按钮级 `v-if` 权限判断
- 数据字段级权限脱敏

---

## 9. 风险点 / 待确认点

### 9.1 明确风险点

1. 页面为静态原型，未接真实告警源  
证据：页面未引入任何 `api/service`，`alerts` 为本地硬编码数组。

2. “刷新”命名与行为不一致  
证据：`refresh()` 只调用 `playBeep()`，不重新获取数据。

3. “短信网关”只有展示层逻辑，没有真实通知链路  
证据：`enableSms` 只影响表格文案，未发现接口、WebSocket、任务调度或第三方网关调用。

4. 浏览器音频异常被静默吞掉  
证据：`playBeep()` 使用 `try/catch`，catch 后直接 `return`，没有提示。

5. 路由权限声明未在全局守卫中落地  
证据：`beforeEach` 只检查登录态，不检查 `requiredPermissions`。

6. 仓库已有告警 WebSocket 能力，但页面未使用  
证据：[websocketService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/websocketService.js) 已存在 `farm:alert` 事件链；[AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue) 未接入。

### 9.2 待确认点

1. 页面是否只是占位页，真实告警中心尚未开发完成  
当前判断：高度可能，但需结合产品/后端确认。

2. 顶部铃铛 `alertCount` 是否计划与本页数据联动  
当前判断：代码中未发现联动来源，需结合后续实现确认。

3. 告警确认、消警、屏蔽、通知升级等流程是否在其他页面承载  
当前判断：本页未发现，需继续全仓检索确认。

4. 告警中文文案在终端输出存在乱码  
当前判断：更可能是终端编码问题，不影响逻辑分析；文案原文建议在编辑器内复核。

---

## 10. 代码证据清单

### 10.1 页面文件

- [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue)
  - 组件名：`AlarmCenter`
  - 状态：`enableSound`、`enableSms`、`alerts`
  - 计算：`dangerCount`、`warningCount`
  - 方法：`playBeep()`、`refresh()`

### 10.2 路由与权限入口

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - 路由名：`AlarmCenter`
  - 路由路径：`alarm-center`
  - 权限元信息：`requiredPermissions: ['view_alarm_center', 'manage_reports']`
  - 守卫：`beforeEach(...)`

- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - 菜单项：`index="/alarm-center"`
  - 权限判断：`hasPermission('view_alarm_center') || hasPermission('manage_reports')`
  - 顶部告警入口：`goAlerts()`

### 10.3 相关但未接入的底层实时能力

- [websocketService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/websocketService.js)
  - 事件监听：`this.socket.on('farm:alert', ...)`
  - 事件处理：`handleFarmAlert(data)`
  - 事件分发：`emit('farm:alert:received', data)`
  - 组合式状态：`const alerts = ref([])`
  - 接收处理：`handleAlertReceived(alert)`

- [useSocket.js](D:/my-vue-project/wind-power-forecast/frontend/src/composables/useSocket.js)
  - 通用 Socket.io 连接封装
  - 当前页面未引用

- [socket.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/socket.js)
  - 旧式 Socket.io 实例封装
  - 当前页面未引用

---

## 关键代码证据清单

- [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- [websocketService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/websocketService.js)
- [useSocket.js](D:/my-vue-project/wind-power-forecast/frontend/src/composables/useSocket.js)
- [socket.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/socket.js)

## 可能遗漏点检查清单

- 是否存在后续未接入本页的后端告警 REST API，当前代码中未发现
- 是否存在其他页面承担告警确认/消警功能，当前本页未体现
- 是否存在顶部铃铛角标 `alertCount` 的独立数据源，当前代码中未追到与本页联动
- 是否存在真正的短信网关配置页或通知策略页，当前本页未发现
- 是否存在与场站切换联动的告警筛选逻辑，当前本页未接入 `farmService`
