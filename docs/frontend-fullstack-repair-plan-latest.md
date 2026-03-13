# 前后端联动最新修复计划

## 1. 当前判断

经过前面几轮修复，前端已经从“几乎全部是静态原型”推进到“核心页面多数可跑、部分页面接入真实接口、部分页面仍为过渡方案”的状态。

但系统还存在三类核心问题：

1. 前端仍有多处 `localStorage` 过渡存储，没有真正后端持久化。
2. 多个页面的业务口径不统一，例如：
   - 准确率 / 合格率
   - 完整率 / 及时率
   - 告警 / 日志 / 质量标记
3. 部分页面虽然已经“可用”，但仍不是完整闭环，例如：
   - 告警中心缺少确认/关闭/通知链路
   - 数据质量缺少后端标记接口
   - 人工修正缺少版本、历史、追踪

因此后续修复不再适合只做前端补丁，而应转为“前后端联动修复”。

---

## 2. 修复总目标

### 目标 A：去本地化

将目前前端依赖 `localStorage` 的业务数据逐步迁移到后端持久化接口，包括：

- 系统基础配置
- 数据质量标记
- 本地审计日志
- 用户扩展元数据
- 场站扩展配置

### 目标 B：统一业务口径

统一以下业务定义和接口输出字段：

- 准确率
- 合格率
- 完整率
- 及时率
- 告警级别
- 告警来源
- 质量标记类型

### 目标 C：补齐关键闭环

优先打通以下闭环：

- 人工修正 -> 保存 -> 手工上报 -> 质量统计
- 质量标记 -> 报表剔除 -> 审计留痕
- 告警产生 -> 告警确认 -> 告警关闭 -> 日志记录
- 系统配置 -> 保存 -> 回显 -> 审计

---

## 3. 最新优先级

## P0：必须优先完成

### P0-1 数据质量标记后端化

现状：
- [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue) 目前质量卡片已接真实统计。
- 但标记仍写入 [dataQualityStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/dataQualityStore.js)。

修复目标：
- 新增后端“质量标记”数据模型和接口。
- 前端改为真实 CRUD。
- 后续让质量标记参与报表剔除口径。

建议后端新增：
- `GET /api/v1/data-quality/markers`
- `POST /api/v1/data-quality/markers`
- `PUT /api/v1/data-quality/markers/:id`
- `DELETE /api/v1/data-quality/markers/:id`

字段建议：
- `id`
- `farm_code`
- `start_time`
- `end_time`
- `marker_type`
- `reason`
- `exclude_from_score`
- `created_by`
- `created_at`
- `updated_at`

### P0-2 系统基础配置后端化

现状：
- [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue) 目前已能本地保存。
- 但代码中仍未发现真实系统配置接口。

修复目标：
- 新增系统配置读取/保存接口。
- 替换前端 [systemSettingsStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/systemSettingsStore.js) 过渡存储。
- 配置保存后进入审计链路。

建议后端新增：
- `GET /api/v1/system/settings`
- `PUT /api/v1/system/settings`

建议配置结构：
- `holidays`
- `dict`
- `retention_policy`
- `updated_by`
- `updated_at`

### P0-3 审计日志服务端化

现状：
- [AuditLog.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AuditLog.vue) 现在是“本地审计 + 系统日志”汇总。
- 本地审计仍依赖 [auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js)。

修复目标：
- 将前端写本地审计日志，逐步切换为写后端审计接口。
- 审计页改为后端分页、后端过滤、后端排序。

建议后端新增：
- `GET /api/v1/audit/logs`
- `POST /api/v1/audit/logs`

建议字段：
- `id`
- `operation_time`
- `operator`
- `module`
- `operation_type`
- `details`
- `result`
- `ip_address`
- `source`

### P0-4 用户扩展元数据后端化

现状：
- [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue) 中的手机号、场站范围仍大量依赖 [userMetaStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/userMetaStore.js)。

修复目标：
- 将用户扩展字段并入后端用户模型或独立元数据接口。
- 前端不再依赖本地补数。

建议后端修复方式二选一：

方案 A：
- 扩展用户表字段

方案 B：
- 新增用户元数据接口
  - `GET /api/v1/users/meta`
  - `PUT /api/v1/users/:id/meta`

---

## P1：核心业务闭环增强

### P1-1 告警中心真正业务化

现状：
- [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue) 目前接的是系统日志快照 + WebSocket 日志流。
- 不是完整告警中心。

修复目标：
- 新增“告警事件”后端模型与接口。
- 支持告警确认、关闭、通知记录。
- WebSocket 由“日志流”升级为“告警流”。

建议后端新增：
- `GET /api/v1/alarms`
- `POST /api/v1/alarms/:id/ack`
- `POST /api/v1/alarms/:id/close`
- `GET /api/v1/alarms/notifications`

### P1-2 人工修正版本化

现状：
- [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue) 已能接预览和手工上报。
- 但没有修正版本、历史记录、比对和回滚。

修复目标：
- 引入人工修正版本表。
- 保存修正不只是立即上报，也能保留版本历史。

建议后端新增：
- `GET /api/v1/manual-intervention/versions`
- `POST /api/v1/manual-intervention/versions`
- `GET /api/v1/manual-intervention/versions/:id`
- `POST /api/v1/manual-intervention/versions/:id/apply`

### P1-3 准确率/合格率真实统计

现状：
- [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue) 目前接的是 `report/statistics` 的完整率/及时率。
- 页面名称与真实数据口径不一致。

修复目标：
- 明确“准确率/合格率”真实算法和后端输出。
- 页面改为真实准确率报表。

建议后端新增：
- `GET /api/v1/report/accuracy-statistics`

建议输出：
- `farm_code`
- `farm_name`
- `month`
- `accuracy_rate`
- `qualified_rate`
- `excluded_hours`
- `notes`

---

## P2：一致性治理

### P2-1 场站扩展配置去本地化

现状：
- [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue) 仍有“后端主数据 + 本地扩展配置”的混合模式。

修复目标：
- 将扩展字段并入后端。

### P2-2 页面口径统一

需要统一的地方：
- 首页、状态监控、功率对比、报表页的数据定义
- 质量统计和准确率统计的区别
- 告警和日志的边界

### P2-3 页面路由联动统一

现状：
- 某些页面之间虽然有跳转，但 query 并不总是被完整消费。

修复目标：
- 统一页面 query 参数规范：
  - `farm_code`
  - `report_type`
  - `source`
  - `date`

---

## 4. 推荐实施顺序

### 第一阶段：先做后端基础模型与接口

建议顺序：
1. 数据质量标记接口
2. 系统基础配置接口
3. 审计日志接口
4. 用户扩展元数据接口

原因：
- 这四项能最快消灭大量 `localStorage`
- 能把多个页面从“过渡方案”升级为真正业务页

### 第二阶段：前端切换真实接口

建议顺序：
1. [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)
2. [SystemSettings.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/SystemSettings.vue)
3. [AuditLog.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AuditLog.vue)
4. [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue)

### 第三阶段：增强核心业务闭环

建议顺序：
1. 告警中心业务化
2. 人工修正版本化
3. 准确率报表真实化

---

## 5. 每轮修复要求

后续每轮都按以下标准执行：

1. 先补接口或模型，再改页面。
2. 每轮都补 md 修复记录。
3. 每轮完成后：
   - lint / 必要验证
   - `git add -A`
   - commit
   - push 到 `codex-0302`

---

## 6. 下一轮建议直接开工项

建议下一轮直接做：

### 第一优先
- 数据质量标记后端接口 + 前端切换

### 第二优先
- 系统基础配置后端接口 + 前端切换

这是当前性价比最高的两项，因为：
- 页面已经修到“可用过渡态”
- 改造点集中
- 能明显减少 `localStorage`
- 能为后续审计和报表剔除打基础
