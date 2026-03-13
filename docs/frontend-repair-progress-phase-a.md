# 前端修复进展 - 阶段 A 权限与访问控制补齐

## 1. 本轮目标

根据 [前端页面修复计划](D:/my-vue-project/docs/frontend-page-repair-plan.md) 的阶段 A，先补齐权限与访问控制基线，解决“菜单可见性控制存在，但路由与高风险操作未真正收口”的问题。

---

## 2. 本轮已完成修复

### 2.1 路由权限守卫补齐

修复内容：
- 在 [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js) 中新增对 `meta.requiredPermissions` 的实际校验。
- 未登录用户仍然跳转登录页。
- 已登录但无页面权限的用户，统一弹出提示并重定向到首页。

本轮结果：
- 路由权限不再只校验 `localStorage.user`。
- 页面级权限声明开始真正生效。

### 2.2 新增公共权限工具

新增文件：
- [permission.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/permission.js)

提供能力：
- `getStoredUser()`
- `normalizePermissions()`
- `isSuperAdmin()`
- `hasPermission()`
- `hasAnyPermission()`

本轮结果：
- 后续页面、路由、按钮权限可复用同一套口径。
- 避免多个页面重复手写 `localStorage + permissions.includes(...)`。

### 2.3 布局权限入口修正

修复文件：
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)

修复内容：
- 系统管理菜单分组补入 `system_maintenance`、`view_audit_logs` 显示条件。
- 顶部告警按钮改为仅在具备 `view_alarm_center` 或 `manage_reports` 时显示。
- 点击告警按钮前增加前端权限保护。

本轮结果：
- 修复了“拥有系统配置/审计权限但一级菜单分组不显示”的入口缺口。
- 修复了顶部告警按钮可能成为越权入口的问题。

### 2.4 用户与角色页面权限判断口径统一

修复文件：
- [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue)
- [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue)

修复内容：
- 页面内部 `canManageUsers` / `canManageRoles` 改为复用公共权限工具。

本轮结果：
- 按钮级权限判断与路由、菜单口径一致。

### 2.5 核心高风险页面增加方法级权限兜底

修复文件：
- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)
- [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)

修复内容：
- 状态监控页：
  - 启停开关增加禁用态
  - 批量启用/停止/删除增加禁用态
  - 卡片级启停开关增加禁用态
  - 删除任务、单项控制、全局控制、矩阵批量控制增加方法级权限校验
- 上报配置与调度页：
  - 调度器启动/停止
  - 新增配置
  - 保存配置
  - 启停配置
  - 删除配置
  - 实时监控重试
  - 手工生成文件
  - 强制推送文件
  均增加方法级权限校验

本轮结果：
- 即使未来页面入口变化或组件被复用，高风险方法也不会只依赖模板按钮显隐。

---

## 3. 校验结果

已执行校验：
- `npm.cmd run lint -- src/router/index.js src/components/AppLayout.vue src/components/AutoPredict.vue src/components/ReportManagement.vue src/components/UserManagement.vue src/components/RoleManagement.vue src/utils/permission.js`

校验结果：
- `No lint errors found`

说明：
- 终端中存在 PowerShell profile 脚本策略提示，但不影响本次 lint 结果。

---

## 4. 本轮未处理项

以下内容仍未在本轮完成：

1. [FarmManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/FarmManagement.vue) 的按钮级权限收口尚未统一。
2. 其余原型页虽然已有路由级权限保护，但尚未做更细的页面内操作权限治理。
3. 401/403 的统一页面反馈与跳转策略仍需继续完善。
4. 尚未补“权限矩阵总表”文档。

---

## 5. 下一步建议

建议直接进入修复计划阶段 B：

1. 补 [ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue) 真实查询/保存闭环。
2. 补 [AccuracyReport.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AccuracyReport.vue) 查询/导出闭环。
3. 视后端能力情况，继续推进 [AlarmCenter.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AlarmCenter.vue) 与 [DataQualityManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/DataQualityManagement.vue)。

---

## 6. 关键代码证据清单

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [permission.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/permission.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- [AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)
- [ReportManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ReportManagement.vue)
- [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue)
- [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue)

## 7. 可能遗漏点检查清单

- 是否存在其他页面仍然手写 `localStorage.getItem('user') + permissions.includes(...)`
- 是否存在弹窗子组件内部未纳入方法级权限校验
- 是否需要为无权限跳转增加独立 403 页而不是统一回首页
- 是否需要把权限工具进一步下沉为全局注入或组合式函数
