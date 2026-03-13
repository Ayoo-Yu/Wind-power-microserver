# 前后端联动修复进展（阶段 G）

## 本轮目标

- 用户扩展元数据后端化
- 审计日志服务端化

## 已完成内容

### 1. 用户扩展元数据后端化

- 后端新增用户扩展元数据模型 `UserProfileMeta`
- 后端新增接口：
  - `GET /auth/users-meta`
  - `GET /auth/me/profile-meta`
  - `PUT /auth/users/:id/meta`
  - `DELETE /auth/users/:id/meta`
- 前端用户管理页不再依赖本地 `userMetaStore`
- 用户页中的手机号、管理场站范围改为后端读取与保存
- 登录后与布局刷新用户信息时，会补拉当前用户扩展元数据并写入 `localStorage.user`

### 2. 审计日志服务端化

- 后端新增审计日志模型 `OperationAuditLog`
- 后端新增接口：
  - `GET /auth/audit-logs`
  - `POST /auth/audit-logs`
- 前端 `auditLogStore` 从本地 `localStorage` 改为调用后端接口
- 用户管理、角色管理等页面继续沿用 `appendAuditLog()`，但数据已落到后端
- 审计日志页的本地审计来源，已切换为服务端审计日志来源

## 影响页面

- `frontend/src/components/UserManagement.vue`
- `frontend/src/components/Login.vue`
- `frontend/src/components/AppLayout.vue`
- `frontend/src/components/AuditLog.vue`

## 影响接口与模型

- `backend/db_models/auth_extensions.py`
- `backend/routes/auth_extensions.py`
- `backend/app.py`
- `frontend/src/api/auth.js`
- `frontend/src/utils/auditLogStore.js`

## 本轮收益

- 用户扩展信息不再只存在浏览器本地
- 审计日志不再依赖前端本地存储，跨设备可共享
- 登录态中的用户权限与场站范围信息更完整，能直接支撑布局和页面权限判断

## 当前仍未完全解决的问题

- 审计日志页仍将服务端审计日志标记为 `local` 来源，语义上还不够准确
- 用户扩展元数据目前只覆盖手机号和管理场站，若后续还需要更多用户画像字段，仍需扩展模型
- 后端接口当前是轻量扩展实现，还未补分页、条件查询和批量导出能力

## 下一步建议

- 告警中心后端业务化
- 准确率/合格率真实统计接口化
- 场站扩展配置去本地化
