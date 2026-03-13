# 前端核心页面不足总表

## 1. 文档目的

本文基于已完成的页面级代码拆解文档，汇总当前前端项目各核心页面的主要不足、缺失闭环和共性风险，为后续《修复计划》《开发排期》《联调清单》提供输入。

约束说明：

- 仅基于当前代码仓库与已沉淀的页面文档整理
- 不臆测不存在的功能
- 对无法确认的事项明确标注“代码中未发现”或“需结合后端确认”

---

## 2. 全局共性不足

### 2.1 路由权限声明普遍未真正落地

事实：

- 多数业务页路由都声明了 `meta.requiredPermissions`
- 全局路由守卫 [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js) 当前只校验登录态 `localStorage.user`
- 代码中未发现统一按 `requiredPermissions` 做强制拦截

影响：

- 菜单隐藏并不等于真正禁止访问
- 权限控制更多停留在“UI 入口显隐”，不是“路由/动作层硬控制”

涉及页面：

- 状态监控
- 人工修正工作台
- 功率可视化对比
- 准确率/合格率报表
- 气象数据拉取
- 上报配置与调度
- 统一告警中心
- 数据质量与限电标记
- 场站管理
- 用户列表
- 用户与权限
- 系统基础配置
- 操作日志审计

### 2.2 多个页面仍是静态原型或半成品页面

明确属于“未形成真实后端闭环”的页面：

- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue)
- [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue)
- [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue)
- [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)
- [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue)

共性特征：

- 代码中未发现 API 调用
- 主要依赖本地 `ref/reactive` 静态数组
- 操作按钮只影响前端状态
- 无持久化保存

### 2.3 多个页面存在“后端主数据 + 前端本地存储补数据”的混合模式

代表页面：

- [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue)
- [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue)
- [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)
- [AuditLog.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AuditLog.vue)

典型问题：

- 不同浏览器/不同终端数据不一致
- 清理缓存后部分页面展示信息丢失
- 数据来源不可单点追溯

### 2.4 多个页面存在“前端占位按钮”或“文案与行为不一致”

典型例子：

- 统一告警中心“刷新”只播放蜂鸣音，不刷新数据
- 系统基础配置“保存配置”按钮没有点击事件
- 准确率/合格率报表“查询”“导出”没有真实逻辑
- 人工修正工作台“保存”只有成功提示，没有持久化

### 2.5 多个页面缺少按钮级权限控制

虽有菜单权限或页面权限，但代码中普遍未发现：

- 按钮级 `v-if` 权限控制
- 字段级权限控制
- 行操作权限细分

风险：

- 页面入口有权限，但页面内的关键操作未做细分约束

### 2.6 异常处理不一致，部分页面静默降级

典型例子：

- 操作日志审计页远端系统日志失败时静默降级
- 告警中心音频播放失败时静默吞错
- 功率对比页对部分接口异常的可视反馈代码中未明确

### 2.7 真实实时能力与页面接入脱节

事实：

- 仓库存在 [websocketService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/websocketService.js)
- 但统一告警中心等实时场景页并未接入

影响：

- 底层能力存在，业务页却仍停留在静态或手动刷新阶段

---

## 3. 页面级不足清单

## 3.1 登录页

页面文件：

- [Login.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/Login.vue)

主要不足：

1. “记住登录”只有 UI，没有实际业务逻辑
2. 修改密码弹窗逻辑已写，但代码中未发现打开入口
3. 左侧指标区和公告为静态占位数据
4. 登录失败锁定主要依赖前端 `localStorage`，是否有后端协同限制需确认

状态判断：

- 已接登录接口
- 但仍有占位与未闭环部分

## 3.2 首页大屏

页面文件：

- [HomePage.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/HomePage.vue)

主要不足：

1. 首页聚合逻辑较多依赖前端二次加工，不是后端原始结果直出
2. 天气等部分块存在前端 fallback / 构造数据
3. 页面内部未发现细粒度权限控制
4. 代码中未发现 WebSocket/SSE 实时接入

状态判断：

- 已接部分真实服务层
- 但存在口径不透明和 fallback 偏重问题

## 3.3 状态监控

页面文件：

- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)

主要不足：

1. 顶部趋势微图、倒计时等部分信息由前端推导或模拟，不完全来自后端原始字段
2. 页面动作按钮代码中未发现细粒度权限收口
3. API 层存在场站 fallback 重试，但页面无明显提示
4. 跳转到功率对比/人工修正的参数传递，目标页并未完整消费

状态判断：

- 已接真实核心接口
- 但链路闭环还不完整

## 3.4 人工修正工作台

页面文件：

- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue)

主要不足：

1. 当前是纯前端 mock 页面
2. 曲线数据来自 `buildMockSeries()` 本地构造
3. 保存动作只有提示，无持久化
4. 不消费路由 query，上游跳转上下文无法落地
5. 代码中未发现接口、校验、版本管理、审批链路

状态判断：

- 原型页/占位页

## 3.5 功率可视化对比

页面文件：

- [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue)

主要不足：

1. 多个考核指标由前端二次计算，口径依赖前端实现
2. 与状态监控页跳转的 query 参数没有真正消费
3. 异常提示与失败反馈代码中未完全明确
4. 导出 Excel 本质是 HTML 伪装 `.xls`

状态判断：

- 已接真实接口
- 但数据口径与导出实现需要重点整改

## 3.6 准确率/合格率报表

页面文件：

- [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue)

主要不足：

1. 当前为静态占位页
2. 查询条件不驱动表格变化
3. 查询按钮没有事件
4. 导出按钮没有事件
5. 代码中未发现接口调用

状态判断：

- 原型页/占位页

## 3.7 气象数据拉取

页面文件：

- [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue)

主要不足：

1. 页面没有轮询和自动刷新
2. 健康看板依赖前端根据多个接口结果拼装
3. 上传存在 fallback 到运营 CSV 接口的隐性逻辑，链路较复杂
4. 页面内配置面与执行面耦合较重

状态判断：

- 已接真实接口
- 但状态更新与链路透明度仍需加强

## 3.8 上报配置与调度

页面文件：

- [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)

主要不足：

1. 页面体量过大，职责过于集中
2. 配置敏感字段部分依赖 `localStorage` 补充缓存
3. 轮询仅覆盖实时监控，不覆盖全部区块
4. 代码中未发现多项关键操作的细粒度权限控制
5. 覆盖 `console.error` 吞掉 `ResizeObserver` 报错，存在掩盖其他错误风险

状态判断：

- 已接真实核心接口
- 当前最复杂、最值得重点整改模块之一

## 3.9 统一告警中心

页面文件：

- [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue)

主要不足：

1. 当前为静态原型页
2. `alerts` 为本地静态数组
3. “刷新”按钮只会播放蜂鸣音
4. “短信网关”只是文案开关，没有真实通知链路
5. 仓库已有 WebSocket 告警能力，但本页未接入

状态判断：

- 原型页/占位页

## 3.10 数据质量与限电标记

页面文件：

- [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)

主要不足：

1. 当前为静态原型页
2. 完整率与标记数据都来自本地数组
3. “新增标记”不持久化
4. 表单校验极弱且无错误提示
5. 与准确率/功率对比的“免考剔除”没有真实联动

状态判断：

- 原型页/占位页

## 3.11 场站管理

页面文件：

- [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue)

主要不足：

1. 页面数据来源混合：后端主数据 + `localStorage` 扩展配置
2. “启停预测”与场站启停实际共用 `is_active`
3. 地图视图不是地理底图，而是经纬度散点图
4. 后端是否真正落全部扩展字段，前端代码中未明确

状态判断：

- 已接真实 CRUD
- 但主数据边界不清晰

## 3.12 用户列表

页面文件：

- [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue)

主要不足：

1. `phone` 与 `stations` 主要来自本地 `userMetaStore`
2. 新增/编辑用户时这两个字段不发给后端
3. 审计日志是本地 `localStorage` 审计，不是服务端审计
4. 搜索、分页都是前端本地能力

状态判断：

- 已接真实用户/角色接口
- 但页面展示并非纯后端主数据

## 3.13 用户与权限

页面文件：

- [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue)

主要不足：

1. 权限树、权限标签、角色预设全由前端常量维护
2. 初始化预设角色会直接向后端写入角色
3. 内置角色仅禁用名称编辑，没有禁止删除或改权限
4. 页面没有搜索、分页、筛选能力

状态判断：

- 已接真实角色 CRUD
- 但权限体系前后端对齐风险较高

## 3.14 系统基础配置

页面文件：

- [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue)

主要不足：

1. 当前为静态原型页
2. 只有 `addHoliday()` 有本地状态逻辑
3. “保存配置”按钮无绑定事件
4. 字典与保留策略都不持久化
5. 仓库虽有 `systemApi.js`，但并不是本页配置保存链路

状态判断：

- 原型页/占位页

## 3.15 操作日志审计

页面文件：

- [AuditLog.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AuditLog.vue)

主要不足：

1. 页面混合本地审计日志和远端系统日志
2. 筛选全在前端，不是服务端查询
3. 远端日志失败时静默降级
4. 合并后无排序、无去重
5. 本地审计日志不可视为服务端不可篡改审计

状态判断：

- 已接真实系统日志接口
- 但审计口径和日志治理还不够严谨

---

## 4. 按成熟度分组

### 4.1 原型/占位页

- 人工修正工作台
- 准确率/合格率报表
- 统一告警中心
- 数据质量与限电标记
- 系统基础配置

共性问题：

- 代码中未发现真实接口
- 操作不持久化
- 无真实业务链路闭环

### 4.2 已接真实接口但存在明显前端补洞/混合数据页

- 首页大屏
- 状态监控
- 功率可视化对比
- 场站管理
- 用户列表
- 用户与权限
- 操作日志审计

共性问题：

- 前端二次加工重
- 本地缓存/本地日志介入较多
- 数据口径和后端边界不够清晰

### 4.3 已接真实接口且业务闭环较完整但复杂度过高页

- 气象数据拉取
- 上报配置与调度

共性问题：

- 页面职责过重
- 状态管理复杂
- 缺少细粒度权限与更清晰的异常处理

---

## 5. 全局修复重点清单

以下问题建议进入下一阶段修复计划的总任务池：

### 5.1 P0 级

1. 路由权限真正按 `requiredPermissions` 落地
2. 原型页与正式页边界梳理，明确哪些页面要补后端、哪些页面要下线/标注占位
3. 清理“前端假保存”“按钮无事件”“文案与行为不一致”的页面交互
4. 梳理本地缓存替代后端主数据的字段，明确持久化归属

### 5.2 P1 级

1. 统一审计日志方案，明确本地审计与服务端审计的职责边界
2. 补齐静态页真实接口：
   - 人工修正
   - 准确率报表
   - 告警中心
   - 数据质量
   - 系统设置
3. 为核心操作补按钮级权限控制
4. 为关键页面补充失败反馈、空态、重试机制

### 5.3 P2 级

1. 减少页面内过重的前端二次加工，把口径下沉到后端或服务层
2. 整理导出、上传、轮询、fallback 等隐性逻辑
3. 拆分超大页面职责，如上报配置与调度

---

## 6. 建议的修复计划分组输入

后续制定修复计划时，建议按以下 4 个工作包推进：

### 6.1 工作包 A：权限与访问控制补齐

包含：

- 路由守卫权限落地
- 页面按钮级权限控制
- 内置角色保护策略

### 6.2 工作包 B：原型页补后端闭环

包含：

- 人工修正工作台
- 准确率/合格率报表
- 统一告警中心
- 数据质量与限电标记
- 系统基础配置

### 6.3 工作包 C：混合数据页去本地化

包含：

- 场站管理扩展字段归后端
- 用户列表 `phone/stations` 归后端
- 审计日志服务端化
- 上报配置敏感配置元数据归后端

### 6.4 工作包 D：复杂核心页重构与增强

包含：

- 上报配置与调度
- 气象数据拉取
- 状态监控
- 功率可视化对比

目标：

- 降低页面职责耦合
- 明确数据口径
- 提升异常处理与操作透明度

---

## 7. 关联文档清单

- [frontend-login-page-analysis.md](D:/my-vue-project/docs/frontend-login-page-analysis.md)
- [frontend-homepage-dashboard-analysis.md](D:/my-vue-project/docs/frontend-homepage-dashboard-analysis.md)
- [frontend-autopredict-status-monitor-analysis.md](D:/my-vue-project/docs/frontend-autopredict-status-monitor-analysis.md)
- [frontend-manual-intervention-workspace-analysis.md](D:/my-vue-project/docs/frontend-manual-intervention-workspace-analysis.md)
- [frontend-power-compare-analysis.md](D:/my-vue-project/docs/frontend-power-compare-analysis.md)
- [frontend-accuracy-report-analysis.md](D:/my-vue-project/docs/frontend-accuracy-report-analysis.md)
- [frontend-weather-data-fetcher-analysis.md](D:/my-vue-project/docs/frontend-weather-data-fetcher-analysis.md)
- [frontend-report-management-analysis.md](D:/my-vue-project/docs/frontend-report-management-analysis.md)
- [frontend-alarm-center-analysis.md](D:/my-vue-project/docs/frontend-alarm-center-analysis.md)
- [frontend-data-quality-management-analysis.md](D:/my-vue-project/docs/frontend-data-quality-management-analysis.md)
- [frontend-farm-management-analysis.md](D:/my-vue-project/docs/frontend-farm-management-analysis.md)
- [frontend-user-management-analysis.md](D:/my-vue-project/docs/frontend-user-management-analysis.md)
- [frontend-role-management-analysis.md](D:/my-vue-project/docs/frontend-role-management-analysis.md)
- [frontend-system-settings-analysis.md](D:/my-vue-project/docs/frontend-system-settings-analysis.md)
- [frontend-audit-log-analysis.md](D:/my-vue-project/docs/frontend-audit-log-analysis.md)

---

## 关键代码证据清单

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue)
- [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue)
- [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)
- [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue)
- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue)
- [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue)
- [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue)
- [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue)
- [AuditLog.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AuditLog.vue)
- [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)
- [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue)

## 可能遗漏点检查清单

- 后端是否已经存在但前端未接入的配置、告警、质量、报表接口，当前仅能从前端代码判断“未接入”
- 页面中文文案在终端输出存在乱码，逻辑分析不受影响，但展示文案建议在编辑器复核
- 某些页面的真实产品定位是否为“占位页/原型页”，仍需结合产品与后端确认
