# 前端页面修复计划

## 1. 文档目的

本文基于已完成的页面拆解文档与《前端页面不足汇总》整理当前前端项目的修复路线，用于后续排期、开发执行、联调准备与验收。

约束说明：
- 仅基于当前仓库代码与已沉淀文档输出，不补充代码中未实现的能力。
- 对于需后端配合的部分，统一标注“需结合后端确认”。
- 本计划优先解决“权限缺口、核心业务闭环缺失、混合数据源、复杂页面稳定性”四类问题。

---

## 2. 修复目标分层

### 2.1 P0：必须优先解决

适用范围：
- 权限校验缺失
- 核心业务页面只有前端展示、无真实接口闭环
- 影响主流程可信度的数据混合与本地假数据问题

目标：
- 让核心页面具备“可访问控制、可真实读写、可联调、可验收”的基础能力。

### 2.2 P1：高优先级增强

适用范围：
- 复杂页面接口不完整
- 前端二次加工口径不稳定
- 局部轮询、导出、日志、预览、调度链路不完整

目标：
- 让复杂页面具备一致的数据来源、稳定的状态流、明确的异常反馈与更可维护的实现。

### 2.3 P2：体验与治理优化

适用范围：
- 页面结构重构
- 公共能力抽象
- 审计、日志、监控、错误处理、空态兜底治理

目标：
- 降低后续维护成本，补足工程化能力。

---

## 3. 修复阶段建议

### 阶段 A：权限与访问控制补齐

目标：
- 先补系统最底层访问控制，避免菜单可见但路由/按钮不可控。

修复项：
1. 在 [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js) 的全局守卫中真正消费 `meta.requiredPermissions`。
2. 统一梳理页面级、按钮级权限收口规则，避免仅靠菜单显隐。
3. 将 [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 中的 `hasPermission()` 与路由守卫权限口径统一。
4. 对以下关键页补按钮级权限核验：
   - [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)
   - [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)
   - [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue)
   - [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue)
   - [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue)

验收标准：
- 未登录用户无法进入受保护页面。
- 无权限用户即使直接输入 URL 也无法进入受限页面。
- 无权限用户无法执行增删改、调度、启停、重置密码等高风险操作。

---

### 阶段 B：原型页补真实业务闭环

目标：
- 将当前仍停留在本地静态/mock 的页面补齐为真实业务页，至少完成读取、保存、异常反馈闭环。

#### B1. 人工修正工作台

目标页面：
- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue)

当前问题：
- 曲线来自 `buildMockSeries()` 本地模拟。
- 保存无真实接口。
- 不接收上游页面上下文。

修复建议：
1. 新增人工修正查询接口与保存接口。需结合后端确认。
2. 消费路由 query 或场站上下文，承接 [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue) 跳转参数。
3. 将修正前、修正后、提交状态、审核状态拆为明确状态流。
4. 增加保存失败、冲突覆盖、无数据时段提示。

验收标准：
- 可根据场站/日期/预测类型读取真实曲线。
- 可保存人工修正结果并回显。
- 从状态监控页跳转后能自动带入上下文。

#### B2. 准确率/合格率报表

目标页面：
- [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue)

当前问题：
- 页面完全静态。
- 查询、导出无实际行为。

修复建议：
1. 新增报表查询接口与导出接口。需结合后端确认。
2. 明确页面口径与 [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) 的计算口径关系。
3. 将筛选条件真正驱动数据刷新。
4. 增加空态、加载态、失败态。

验收标准：
- 查询条件变化后表格刷新。
- 导出返回真实报表文件或后端下载地址。
- 页面指标口径可追溯。

#### B3. 统一告警中心

目标页面：
- [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue)

当前问题：
- 告警列表静态。
- 刷新仅蜂鸣，不刷新数据。
- 未接仓库已有 WebSocket 告警链路。

修复建议：
1. 接入告警查询接口。需结合后端确认。
2. 接入 [websocketService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/websocketService.js) 告警事件流或补 SSE 方案。
3. 明确告警确认、消音、通知方式开关是否真实落库。
4. 将告警级别、状态、来源系统统一标准化。

验收标准：
- 页面可展示实时或准实时告警。
- 刷新操作真正拉取新数据。
- 告警确认/通知开关有真实业务含义。

#### B4. 数据质量与限电标记

目标页面：
- [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)

当前问题：
- 完整率与标记表均为本地数组。
- 新增标记仅前端插入，不持久化。
- 与考核/报表页面无联动。

修复建议：
1. 新增质量统计、质量标记、限电标记查询与保存接口。需结合后端确认。
2. 明确“免考剔除”与报表口径联动关系。
3. 标记新增/编辑/撤销要有完整操作流。
4. 补场站、时间范围筛选与批量处理能力。

验收标准：
- 新增标记后刷新仍可回显。
- 标记可影响相关报表口径或至少有明确下游消费关系。

#### B5. 系统基础配置

目标页面：
- [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue)

当前问题：
- 仅本地状态，无保存接口。
- “保存配置”按钮无行为。

修复建议：
1. 新增系统配置读取/保存接口。需结合后端确认。
2. 将节假日、字典、保留策略拆为独立配置域。
3. 明确是否需要版本、审计、发布生效机制。
4. 对修改操作补提交反馈、失败提示、脏数据保护。

验收标准：
- 页面初始化能回显后端配置。
- 保存后刷新可保持配置结果。

---

### 阶段 C：混合数据页去本地化

目标：
- 将“后端数据 + localStorage 扩展字段”的混合页逐步收敛到统一后端模型，减少前端伪持久化。

#### C1. 场站管理

目标页面：
- [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue)

当前问题：
- 场站主数据与 `localStorage` 扩展配置混用。
- 部分配置字段是否真实落库，代码中未明确。

修复建议：
1. 梳理字段主数据边界，区分“必须后端持久化”和“仅前端展示配置”。
2. 清理 `farm_management_ext_configs_v1` 本地扩展缓存或迁移到后端。
3. 明确 `is_active` 与“启停预测”业务语义。
4. 地图视图应标明为散点图，若需真实地图需另行改造。

验收标准：
- 表单字段都能明确对应持久化位置。
- 刷新后场站配置不依赖本地缓存恢复。

#### C2. 用户列表

目标页面：
- [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue)

当前问题：
- `phone`、`stations` 来源于本地 `userMetaStore`。
- 用户资料与授权信息未完全后端化。

修复建议：
1. 推动用户元数据后端化，至少包含手机号与管理场站范围。需结合后端确认。
2. 减少 `userMetaStore.js` 对页面主数据的补丁式影响。
3. 统一用户详情、角色、场站授权的接口返回模型。
4. 本地审计保留可作为前端补充，但不能替代正式审计。

验收标准：
- 用户字段全部可从后端读回。
- 新增/编辑后无需本地缓存也能恢复完整信息。

#### C3. 操作日志审计

目标页面：
- [AuditLog.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AuditLog.vue)

当前问题：
- 本地审计日志与远端系统日志混合展示。
- 筛选全部前端完成，远端日志结构不稳定。

修复建议：
1. 明确正式审计日志来源，是后端统一审计表还是现有本地补充。需结合后端确认。
2. 若保留混合展示，需补排序、去重、来源标签、失败提示。
3. 筛选条件应尽量下推服务端。
4. 本地日志应仅作为调试补充，不应作为正式审计唯一来源。

验收标准：
- 日志来源可区分。
- 查询结果有稳定排序与一致字段。

---

### 阶段 D：复杂核心页稳定性与一致性治理

目标：
- 针对已接真实接口但逻辑复杂、状态耦合较重的页面进行接口、状态流、异常流与前端计算口径治理。

#### D1. 状态监控

目标页面：
- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)

当前问题：
- 页面内存在推导值、模拟值、轮询与倒计时混合。
- API fallback 隐性较强。
- 按钮权限收口不足。

修复建议：
1. 区分真实后端字段与前端推导字段。
2. 明确 overview 与 fallback 接口的切换策略，并补用户提示。
3. 统一轮询、倒计时、页面离开清理逻辑。
4. 将批量操作、日志、失败明细、跳转动作拆分为更清晰的状态流。

验收标准：
- 页面关键指标来源可追溯。
- 接口失败时能明确感知当前是否走 fallback。

#### D2. 功率可视化对比

目标页面：
- [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue)

当前问题：
- 指标大量前端计算。
- 导出为 HTML 伪 `.xls`。
- 未消费上游路由 query。

修复建议：
1. 明确哪些指标应由后端直接提供，哪些允许前端推导。
2. 接入真实导出接口或统一下载方案。
3. 消费来自状态监控等页面的跳转参数。
4. 补显式接口异常处理与图表空态提示。

验收标准：
- 口径稳定且可解释。
- 导出文件格式与内容符合真实业务预期。

#### D3. 首页大屏

目标页面：
- [HomePage.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/HomePage.vue)

当前问题：
- 依赖聚合服务层与 fallback。
- 天气块存在前端构造痕迹。
- 无实时刷新机制。

修复建议：
1. 梳理 [dashboardService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/dashboardService.js) 的聚合加工规则。
2. 区分真实数据、前端拼装数据、fallback 数据。
3. 明确是否需要轮询或 WebSocket 大屏刷新。
4. 子组件输入输出结构标准化。

验收标准：
- 首页每个区块的数据来源都可追踪。
- fallback 使用条件明确。

#### D4. 气象数据拉取

目标页面：
- [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue)

当前问题：
- 无自动刷新，任务状态可能滞后。
- 上传 fallback 链路复杂。

修复建议：
1. 为连接、任务、调度器状态增加手动刷新与可选自动刷新。
2. 统一标准上传与 CSV fallback 的结果反馈。
3. 将复杂表单拆为更清晰的连接/任务编辑域。
4. 记录任务执行历史与失败原因。

验收标准：
- 任务状态更新及时。
- 上传失败链路清晰可追踪。

#### D5. 上报配置与调度

目标页面：
- [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)

当前问题：
- 单页承载能力过多。
- `localStorage` 补配置。
- 轮询覆盖不完整。
- 覆盖 `console.error` 存在风险。

修复建议：
1. 拆分页面职责，至少拆为配置管理、调度监控、日志查询、预览编辑四块。
2. 清理或后端化本地敏感配置缓存。
3. 梳理统计区、调度器区、监控区刷新策略。
4. 移除全局 `console.error` 覆盖，改为局部兜底。
5. 明确预览模板、真实报文、手工生成之间的数据边界。

验收标准：
- 页面职责更清晰。
- 刷新逻辑一致。
- 本地配置补丁不再成为正式数据源。

---

## 4. 页面修复优先级总表

| 优先级 | 页面 | 当前成熟度判断 | 修复重点 |
|---|---|---|---|
| P0 | [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue) | 已接接口但高耦合 | 权限、状态流、轮询、fallback 透明化 |
| P0 | [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue) | 已接接口但复杂度最高 | 页面拆分、配置后端化、轮询与异常治理 |
| P0 | [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue) | 已接接口 | 自动刷新、上传链路、任务状态可追踪 |
| P0 | [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue) | 原型页 | 补真实数据与保存接口 |
| P0 | [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue) | 原型页 | 补查询与导出闭环 |
| P1 | [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue) | 原型页 | 接实时告警或查询接口 |
| P1 | [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue) | 原型页 | 质量标记后端化与报表联动 |
| P1 | [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue) | 混合页 | 去本地化、字段边界治理 |
| P1 | [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue) | 混合页 | 用户元数据后端化 |
| P1 | [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue) | 已接接口 | 权限口径与内置角色保护增强 |
| P1 | [AuditLog.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AuditLog.vue) | 混合页 | 审计来源统一、筛选服务端化 |
| P2 | [HomePage.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/HomePage.vue) | 聚合展示页 | 聚合规则与实时性治理 |
| P2 | [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) | 已接接口 | 口径统一、导出正规化 |
| P2 | [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue) | 原型页 | 配置后端化 |
| P2 | [Login.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/Login.vue) | 可用但需增强 | 认证策略与修改密码入口完善 |

---

## 5. 建议实施顺序

建议按以下顺序推进：

1. 权限基线治理
2. 状态监控与上报配置治理
3. 气象数据拉取治理
4. 人工修正工作台与准确率报表补后端闭环
5. 告警中心与数据质量页补业务闭环
6. 场站、用户、日志等混合页去本地化
7. 首页与功率对比的口径/体验优化
8. 系统基础配置补接口

排序原因：
- 先补底层权限，避免后续联调阶段暴露访问缺口。
- 再优先修复核心业务主链路：预测、调度、数据输入、人工干预。
- 最后处理报表、可视化、治理类页面与配置类页面。

---

## 6. 修复工作包建议

### 工作包 1：权限与基线
- 路由权限守卫
- 按钮级权限控制
- 401/403 统一处理
- 权限矩阵文档同步更新

### 工作包 2：核心业务闭环
- 状态监控
- 人工修正工作台
- 气象数据拉取
- 上报配置与调度

### 工作包 3：报表与质量
- 功率可视化对比
- 准确率/合格率报表
- 告警中心
- 数据质量与限电标记

### 工作包 4：系统管理与治理
- 场站管理
- 用户列表
- 用户与权限
- 系统基础配置
- 操作日志审计

---

## 7. 需优先补齐的后端配合点

以下事项当前前端修复会被后端能力阻塞，需尽早确认：

1. 人工修正工作台的查询、保存、审核接口。
2. 准确率/合格率报表的查询与导出接口。
3. 告警中心的实时/查询接口与确认接口。
4. 数据质量/限电标记的查询、保存、撤销接口。
5. 系统基础配置的读取、保存、版本控制接口。
6. 用户手机号、管理场站范围、用户扩展资料接口。
7. 审计日志统一来源与筛选接口。

说明：
- 以上能力在代码中未发现完整前端调用链，需结合后端确认。

---

## 8. 实施时的工程治理建议

1. 新增真实接口页面时，统一补：
   - 加载态
   - 空态
   - 异常态
   - 成功反馈
   - 权限反馈
2. 对复杂页面优先抽离：
   - 查询条件区
   - 表格列配置
   - 编辑弹窗/抽屉
   - 日志/预览弹窗
3. 避免继续新增 `localStorage` 伪持久化字段作为正式业务数据源。
4. 将导出、上传、轮询、WebSocket 接入方式逐步标准化。
5. 补测试重点：
   - 权限拦截
   - 核心保存链路
   - 上传失败 fallback
   - 轮询与销毁清理
   - 导出文件结果

---

## 9. 关联文档

- [前端页面不足汇总](D:/my-vue-project/docs/frontend-page-gaps-summary.md)
- [登录页拆解](D:/my-vue-project/docs/frontend-login-page-analysis.md)
- [首页大屏拆解](D:/my-vue-project/docs/frontend-homepage-dashboard-analysis.md)
- [状态监控拆解](D:/my-vue-project/docs/frontend-autopredict-status-monitor-analysis.md)
- [人工修正工作台拆解](D:/my-vue-project/docs/frontend-manual-intervention-workspace-analysis.md)
- [功率可视化对比拆解](D:/my-vue-project/docs/frontend-power-compare-analysis.md)
- [准确率/合格率报表拆解](D:/my-vue-project/docs/frontend-accuracy-report-analysis.md)
- [气象数据拉取拆解](D:/my-vue-project/docs/frontend-weather-data-fetcher-analysis.md)
- [上报配置与调度拆解](D:/my-vue-project/docs/frontend-report-management-analysis.md)
- [统一告警中心拆解](D:/my-vue-project/docs/frontend-alarm-center-analysis.md)
- [数据质量与限电标记拆解](D:/my-vue-project/docs/frontend-data-quality-management-analysis.md)
- [场站管理拆解](D:/my-vue-project/docs/frontend-farm-management-analysis.md)
- [用户列表拆解](D:/my-vue-project/docs/frontend-user-management-analysis.md)
- [用户与权限拆解](D:/my-vue-project/docs/frontend-role-management-analysis.md)
- [系统基础配置拆解](D:/my-vue-project/docs/frontend-system-settings-analysis.md)
- [操作日志审计拆解](D:/my-vue-project/docs/frontend-audit-log-analysis.md)

---

## 10. 关键代码证据清单

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)
- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue)
- [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue)
- [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue)
- [WeatherDataFetcher.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/WeatherDataFetcher.vue)
- [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)
- [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue)
- [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)
- [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue)
- [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue)
- [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue)
- [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue)
- [AuditLog.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AuditLog.vue)
- [websocketService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/websocketService.js)
- [dashboardService.js](D:/my-vue-project/wind-power-forecast/frontend/src/services/dashboardService.js)
- [userMetaStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/userMetaStore.js)
- [auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js)

## 11. 可能遗漏点检查清单

- 是否存在尚未分析到的隐藏弹窗组件、详情组件或复用日志组件
- 是否存在后端已提供但前端未接入的配置接口、报表接口、告警接口
- 是否存在页面间共享 query、场站上下文、缓存策略尚未统一
- 是否存在后端真实字段与当前前端本地补充字段命名不一致
- 是否需要单独补一份“接口改造清单”与“权限矩阵清单”
