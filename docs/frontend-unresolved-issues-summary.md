# 前后端联动修复剩余问题清单

## 1. 文档目的

本文件用于汇总当前仓库中“仍未彻底解决”的问题。

判断标准：

- 以当前代码仓库为准。
- 只记录“尚未完整闭环”或“仅部分完成”的事项。
- 不再把登录态、当前场站选择、登录失败锁定这类前端会话级 `localStorage` 当作本轮业务缺口。

---

## 2. 总体结论

当前最主要的未完成项共有 4 类：

1. 审计日志仍未完成后端分页/过滤/排序闭环
2. 统一告警中心仍缺规则配置与通知策略配置
3. 人工修正版本化已落地，但“版本比对/回滚”仍不完整
4. 一致性治理类事项仍未完成
   - 页面口径统一
   - 页面路由/query 联动统一

---

## 3. 未完成问题明细

### 3.1 审计日志服务端化未完全收口

**优先级**

- 高

**当前状态**

- 前端写审计日志已经走后端接口
- 前端读审计日志已经走后端接口
- 但当前审计页仍然在前端执行筛选、排序、导出
- 审计页仍拼接“本地审计日志 + 系统日志”两类数据源

**已完成部分**

- 后端已提供：
  - `GET /audit-logs`
  - `POST /audit-logs`
- 前端 [auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js) 已改为调用后端

**未完成部分**

- 计划要求的“后端分页、后端过滤、后端排序”尚未落地
- 当前 `GET /audit-logs` 没有看到：
  - 时间范围筛选参数
  - 操作人筛选参数
  - 模块筛选参数
  - 来源筛选参数
  - 分页参数
- 当前前端 [AuditLog.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AuditLog.vue) 仍本地计算：
  - `filteredLogs`
  - 时间范围过滤
  - 操作人模糊过滤
  - 模块过滤
  - 来源过滤
  - 合并后的排序

**影响**

- 数据量增大后，前端列表性能和一致性会变差
- 审计页与后端真实查询口径不一致
- “系统日志 + 审计日志”混合展示仍然缺统一模型

**关键证据**

- [auth_extensions.py](D:/my-vue-project/wind-power-forecast/backend/routes/auth_extensions.py)
  - `list_operation_audit_logs()`
- [auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js)
  - `listAuditLogs()`
  - `appendAuditLog()`
- [AuditLog.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AuditLog.vue)
  - `filteredLogs`
  - `fetchLogs()`
  - `exportLogs()`

**建议后续动作**

- 后端审计日志接口增加分页、过滤、排序参数
- 前端审计页改为直接消费后端分页结果
- 明确“审计日志”和“系统日志”是否继续混表展示

---

### 3.2 统一告警中心未完成规则化与策略化

**优先级**

- 高

**当前状态**

- 告警列表、确认、关闭、通知记录已具备
- 但当前告警仍带有“由系统日志种子生成告警”的过渡逻辑
- 未发现“告警规则配置页/接口”和“通知策略配置页/接口”

**已完成部分**

- 后端已提供：
  - 告警列表
  - 告警确认
  - 告警关闭
  - 通知记录
- 前端页面已接入真实告警 API 和 WebSocket

**未完成部分**

- 未发现告警规则管理模型/接口
- 未发现通知策略模型/接口
- 未发现：
  - 告警阈值配置
  - 告警级别规则配置
  - 通知渠道配置
  - 通知重试/抑制/升级链路配置
- 当前后端 [alarm_router.py](D:/my-vue-project/wind-power-forecast/backend/routes/alarm_router.py) 中仍有 `_seed_alarms_from_logs()`，说明告警流还带过渡性质

**影响**

- 当前告警中心更像“告警记录页”，还不是完整“告警治理中心”
- 规则和策略不可配置，后续扩展成本高

**关键证据**

- [alarm_router.py](D:/my-vue-project/wind-power-forecast/backend/routes/alarm_router.py)
  - `_seed_alarms_from_logs()`
  - `list_alarms()`
  - `list_alarm_notifications()`
  - `ack_alarm()`
  - `close_alarm()`
- [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue)

**建议后续动作**

- 增加告警规则模型与接口
- 增加通知策略模型与接口
- 将“日志种子生成告警”过渡逻辑逐步替换为规则引擎或明确的告警源

---

### 3.3 人工修正版本化未完成比对与回滚增强

**优先级**

- 中高

**当前状态**

- 人工修正页已经支持：
  - 保存版本
  - 查看版本列表
  - 应用版本
- 但未看到完整的版本比对视图、差异展示、显式回滚流程

**已完成部分**

- 后端版本接口已存在
- 前端版本历史列表已存在
- 页面已能应用历史版本回到工作区

**未完成部分**

- 未发现独立 diff 比对能力
- 未发现“当前工作区 vs 某历史版本”的可视化差异展示
- 未发现显式回滚审计语义
- 未发现版本标签、审批态、发布态等更完整治理字段

**影响**

- 当前更接近“版本保存/重新载入”
- 距离“可追踪、可比对、可回滚”的人工修正治理平台还有差距

**关键证据**

- [report_management_router.py](D:/my-vue-project/wind-power-forecast/backend/routes/report_management_router.py)
  - `GET /manual-intervention/versions`
  - `POST /manual-intervention/versions`
  - `GET /manual-intervention/versions/<id>`
  - `POST /manual-intervention/versions/<id>/apply`
- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue)

**建议后续动作**

- 增加版本差异比对视图
- 增加显式回滚操作与审计记录
- 视业务需要增加版本状态、备注、审批人等字段

---

### 3.4 页面口径统一未完成

**优先级**

- 中

**当前状态**

- 准确率/合格率页面已真实化
- 数据质量标记已可进入统计链路
- 告警、日志、质量、报表之间仍是分模块实现
- 未发现统一的“口径定义中心”或“统计口径配置层”

**未完成部分**

- 未统一明确并代码固化以下边界：
  - 准确率 vs 合格率
  - 完整率 vs 及时率
  - 质量标记 vs 告警事件
  - 审计日志 vs 系统日志
- 不同页面仍可能各自解释和展示相近概念

**影响**

- 后续文档、报表和审计之间可能出现“名词相同但口径不同”
- 系统交接和验收时容易出现歧义

**关键证据**

- [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue)
- [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)
- [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue)
- [AuditLog.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AuditLog.vue)
- [report_management_router.py](D:/my-vue-project/wind-power-forecast/backend/routes/report_management_router.py)

**建议后续动作**

- 输出统一术语与指标口径说明
- 在前后端都建立统一字段定义
- 将质量标记、告警、审计三类事件的边界文档化

---

### 3.5 页面路由/query 联动统一未完成

**优先级**

- 中

**当前状态**

- 部分页已开始消费路由 query
- 但不是全系统统一策略

**已完成部分**

- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue) 已读取：
  - `route.query.farm_code`
  - `route.query.report_type`

**未完成部分**

- [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue) 中未发现 `useRoute()` 或 `route.query` 读取逻辑
- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue) 已在跳转时传递 query，但下游页面并未全部消费

**影响**

- 页面间跳转上下文不统一
- 用户从矩阵页跳转到分析页时，场站/模式上下文可能丢失

**关键证据**

- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)
  - `router.push({ query: ... })`
- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue)
  - `useRoute()`
  - `route.query.farm_code`
  - `route.query.report_type`
- [PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue)
  - 代码中未发现 query 消费

**建议后续动作**

- 统一约定跨页 query 字段
- 统一落地：
  - `farm_code`
  - `report_type`
  - `prediction_type`
  - `source`
  - `date`
- 对关键页面补 query 初始化逻辑

---

## 4. 已不再视为本轮缺口的事项

以下内容仍存在于代码中，但不再算作本轮业务修复未完成项：

- 登录态存储 `user/accessToken`
- 当前选中场站 `selectedFarm`
- 登录失败锁定 `LOCK_STORAGE_KEY`

原因：

- 这些属于前端会话级状态，不是业务主数据持久化缺口。

---

## 5. 建议优先级排序

### 第一优先

1. 审计日志后端分页/过滤/排序闭环
2. 告警规则与通知策略配置化

### 第二优先

3. 人工修正版本比对/回滚增强
4. 页面 query 联动统一

### 第三优先

5. 页面口径统一文档与代码定义

---

## 6. 收尾判断

如果以“核心页面是否已接真实接口并能形成主业务闭环”为标准：

- 当前已经基本达标

如果以“系统是否已经达到一致、可治理、可审计、可持续演进”为标准：

- 当前仍未完全达标

主要差距就集中在本文件列出的 4 类问题上。
