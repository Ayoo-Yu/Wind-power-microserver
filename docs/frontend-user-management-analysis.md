# 用户列表代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 用户列表 |
| 所属模块 | 系统管理 |
| 路由路径 | `/users` |
| 页面入口文件 | [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue) |
| 页面依赖的子组件列表 | 代码中未发现本项目自定义子组件；页面直接使用 Element Plus 组件 `el-card`、`el-input`、`el-button`、`el-table`、`el-table-column`、`el-tag`、`el-tooltip`、`el-button-group`、`el-pagination`、`el-dialog`、`el-form`、`el-form-item`、`el-select`、`el-option`、`el-switch` |
| 页面依赖的 store/hooks/model/service/api 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js)、[farmService.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/farmService.js)、[auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js)、[userMetaStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/userMetaStore.js)、[farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js)、[axios.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/axios.js) |
| 页面是否受权限控制 | 路由声明 `meta.requiredPermissions = ['manage_users']`；侧边栏菜单显隐条件为 `hasPermission('manage_users')`；页面内部还有 `canManageUsers` 计算属性控制新增/操作按钮显隐 |

### 1.2 页面定位结论

基于当前代码，用户列表不是纯后端用户管理页面，而是三类数据的拼装结果：

1. 后端用户与角色主数据  
来自 `getUsers()`、`getRoles()`、`createUser()`、`updateUser()`、`deleteUser()`、`resetUserPassword()`

2. 前端补充用户档案元数据  
通过 [userMetaStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/userMetaStore.js) 保存：
- `phone`
- `stations`

3. 前端本地审计日志  
通过 [auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js) 写入用户操作日志

因此，这页已经形成完整业务闭环，但要特别注意：

- `phone` 和 `stations` 不是通过 `createUser/updateUser` 发给后端
- 页面展示的手机号、管理场站，实际上主要来自本地 `localStorage`
- 这意味着不同浏览器或清理缓存后，用户信息展示会变化

### 1.3 关键判断

1. 页面已接真实用户与角色接口。
2. 页面同时依赖 `farmService.loadAvailableFarms(true)` 为“管理场站”下拉提供选项。
3. 用户表格中的 `phone`、`stations` 通过 `hydrateUserWithMeta()` 从本地 `userMetaStore` 注入，不是后端接口原样返回。
4. 每次新增、编辑、重置密码、启停、删除都会写本地审计日志。
5. 页面既有路由权限，又有按钮级 `canManageUsers` 控制，但全局守卫仍然只校验登录态。

---

## 2. 页面结构树

```text
用户列表 UserManagement.vue
├─ 页面根容器 user-management page-shell
│  ├─ 页面头部 page-header
│  │  ├─ 标题 h2
│  │  └─ 描述文本 p
│  ├─ 主卡片 el-card.card-shell
│  │  ├─ 工具栏 toolbar
│  │  │  ├─ 搜索输入框
│  │  │  ├─ 刷新按钮
│  │  │  └─ 新增用户按钮
│  │  ├─ 用户表格 el-table(pagedUsers)
│  │  │  ├─ ID 列
│  │  │  ├─ 用户名列
│  │  │  ├─ 姓名列
│  │  │  ├─ 角色列 el-tag
│  │  │  ├─ 手机号列
│  │  │  ├─ 管理场站列
│  │  │  ├─ 状态列 el-tag
│  │  │  ├─ 最近登录列
│  │  │  └─ 操作列
│  │  │     ├─ 编辑按钮
│  │  │     ├─ 启停按钮
│  │  │     ├─ 重置密码按钮
│  │  │     └─ 删除按钮
│  │  └─ 分页区 el-pagination
│  ├─ 用户新增/编辑弹窗 el-dialog
│  │  └─ 用户表单 el-form
│  │     ├─ 用户名
│  │     ├─ 密码(仅新增)
│  │     ├─ 姓名
│  │     ├─ 手机号
│  │     ├─ 邮箱
│  │     ├─ 角色
│  │     ├─ 管理场站
│  │     └─ 启停状态
│  └─ 重置密码弹窗 el-dialog
│     └─ 重置表单
│        ├─ 新密码
│        └─ 确认密码
```

---

## 3. 区块说明

### 3.1 页面头部

| 字段 | 说明 |
|---|---|
| 区块名称 | 页面头部 |
| 对应组件名 | `UserManagement` |
| 文件路径 | [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue) |
| 展示内容 | 页面标题、副标题说明文案 |
| 数据来源 | 模板内硬编码文本 |
| 是否可交互 | 否 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 否 |

### 3.2 工具栏

| 字段 | 说明 |
|---|---|
| 区块名称 | 工具栏 |
| 对应组件名 | `UserManagement` |
| 文件路径 | [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue) |
| 展示内容 | 搜索框、刷新按钮、新增用户按钮 |
| 数据来源 | `searchQuery`、`loading`、`canManageUsers` |
| 是否可交互 | 是 |
| 是否有权限控制 | “新增用户”受 `canManageUsers` 控制 |
| 是否有定时刷新或自动更新 | 否 |

交互：

- 搜索输入框修改 `searchQuery`
- 刷新按钮执行 `fetchData()`
- 新增用户按钮执行 `openCreateDialog()`

### 3.3 用户表格区

| 字段 | 说明 |
|---|---|
| 区块名称 | 用户表格区 |
| 对应组件名 | `UserManagement` |
| 文件路径 | [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue) |
| 展示内容 | 用户基础信息、角色、手机号、管理场站、状态、最后登录时间、操作按钮 |
| 数据来源 | `pagedUsers`，由 `users -> filteredUsers -> pagedUsers` 计算得到 |
| 是否可交互 | 是 |
| 是否有权限控制 | 操作列按钮整体受 `canManageUsers` 控制 |
| 是否有定时刷新或自动更新 | 否 |

字段来源说明：

- `id`、`username`、`full_name`、`email`、`role`、`is_active`、`last_login`
  - 主要来自后端 `getUsers()`
- `phone`、`stations`
  - 来自本地 `userMetaStore`

管理场站列渲染逻辑：

- 包含 `__ALL__` 时显示“全部场站”
- `stations.length <= 2` 时直接展示场站编码拼接
- `stations.length > 2` 时用 tooltip 展示完整列表，正文显示数量摘要

### 3.4 分页区

| 字段 | 说明 |
|---|---|
| 区块名称 | 分页区 |
| 对应组件名 | `UserManagement` |
| 文件路径 | [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue) |
| 展示内容 | 总数、页码、每页大小、跳页 |
| 数据来源 | `filteredUsers.length`、`currentPage`、`pageSize` |
| 是否可交互 | 是 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 否 |

说明：

- 分页是前端本地分页，不是服务端分页。

### 3.5 用户新增/编辑弹窗

| 字段 | 说明 |
|---|---|
| 区块名称 | 用户新增/编辑弹窗 |
| 对应组件名 | `UserManagement` |
| 文件路径 | [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue) |
| 展示内容 | 用户表单 |
| 数据来源 | `userForm`、`roles`、`farmOptions` |
| 是否可交互 | 是 |
| 是否有权限控制 | 弹窗入口受 `canManageUsers` 控制 |
| 是否有定时刷新或自动更新 | 否 |

字段：

- `username`
- `password`（仅新增时展示）
- `full_name`
- `phone`
- `email`
- `role_id`
- `stations`
- `is_active`

关键事实：

- `phone` 和 `stations` 会写入本地 `userMetaStore`
- `createUser/updateUser` 请求体并不包含 `phone` 与 `stations`

### 3.6 重置密码弹窗

| 字段 | 说明 |
|---|---|
| 区块名称 | 重置密码弹窗 |
| 对应组件名 | `UserManagement` |
| 文件路径 | [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue) |
| 展示内容 | 新密码、确认密码 |
| 数据来源 | `resetForm` |
| 是否可交互 | 是 |
| 是否有权限控制 | 入口按钮受 `canManageUsers` 控制 |
| 是否有定时刷新或自动更新 | 否 |

说明：

- 通过 `resetRules.confirmPassword.validator` 做两次密码一致性校验。

---

## 4. 组件明细表

### 4.1 页面组件：UserManagement

| 维度 | 结论 |
|---|---|
| 组件名称 | `UserManagement` |
| 文件路径 | [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue) |
| 父子关系 | 父级为 [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 中的 `<router-view>`；代码中未发现本项目自定义子组件 |
| props / emits / callbacks | 未定义 `props`、未定义 `emits` |
| 内部 state / computed / hooks / store 使用情况 | `loading`、`submitting`、`resetting`、`users`、`roles`、`farmOptions`、`searchQuery`、`currentPage`、`pageSize`、`showUserDialog`、`showResetDialog`、`isEdit`、`currentUserId`、`userFormRef`、`resetFormRef`、`userForm`、`resetForm`、`currentUser`、`canManageUsers`、`filteredUsers`、`pagedUsers` |
| 生命周期或副作用逻辑 | `onMounted(fetchData)` |
| 实现的具体功能 | 用户查询、搜索、前端分页、新增、编辑、启停、重置密码、删除、角色选择、场站范围选择、本地审计日志记录 |
| 触发了哪些接口 | `getUsers`、`getRoles`、`createUser`、`updateUser`、`deleteUser`、`resetUserPassword`、`farmService.loadAvailableFarms(true)` |
| 与其他组件的联动关系 | 与 `farmService` 联动获取可选场站；与 `auditLogStore`、`userMetaStore` 联动补充元数据和记录本地审计 |
| 加载态 / 空态 / 异常态如何处理 | `loading` 驱动表格加载；无专门空态；局部大量使用 `ElMessage.error/success`；API 还受 axios 全局错误兜底 |

#### 4.1.1 本地状态与计算属性

1. `loading`
- 拉取列表时为 `true`

2. `submitting`
- 新增/编辑用户提交时为 `true`

3. `resetting`
- 重置密码提交时为 `true`

4. `users`
- 用户表格基础数据
- 由 `getUsers()` 返回并经 `hydrateUserWithMeta()` 注入本地元数据

5. `roles`
- 角色下拉选项
- 由 `getRoles()` 返回

6. `farmOptions`
- 管理场站多选下拉选项
- 由 `farmService.loadAvailableFarms(true)` 返回

7. `currentUser`
- 从 `localStorage.user` 解析得到

8. `canManageUsers`
- 计算当前登录用户是否有 `manage_users` 或 `admin`
- 用于按钮显隐

9. `filteredUsers`
- 基于 `searchQuery` 的前端搜索结果

10. `pagedUsers`
- 基于 `filteredUsers` 的前端分页结果

#### 4.1.2 表单模型

1. `userForm`
- 默认由 `EMPTY_USER_FORM()` 创建
- 字段：
  - `id`
  - `username`
  - `password`
  - `full_name`
  - `phone`
  - `email`
  - `role_id`
  - `stations`
  - `is_active`

2. `resetForm`
- 字段：
  - `password`
  - `confirmPassword`

#### 4.1.3 校验规则

`rules`：

- `username` 必填
- `password` 必填且长度至少 8（仅新增时字段显示）
- `full_name` 必填
- `phone` 必填
- `email` 必填且符合 email 格式
- `role_id` 必填
- `stations` 至少选择 1 个

`resetRules`：

- 新密码必填，至少 8 位
- 确认密码必填，且必须与 `resetForm.password` 一致

#### 4.1.4 核心辅助逻辑

1. `normalizeStationSelection(selected)`
- 如果用户同时选了 `__ALL__` 和其他场站
- 强制改回 `['__ALL__']`

2. `hydrateUserWithMeta(user)`
- 从 `getUserMeta(user.username)` 读取本地元数据
- 为用户对象补入：
  - `phone`
  - `stations`

3. `isAllStations(stations)`
- 判断是否包含 `__ALL__`

4. `formatDate(value)`
- 用 `toLocaleString('zh-CN', { hour12: false })` 格式化最后登录时间

#### 4.1.5 核心业务方法

1. `fetchData()`
- 触发时机：
  - 页面 `onMounted`
  - 点击刷新
  - 新增/编辑成功后
  - 启停成功后
  - 删除成功后
- 并行拉取：
  - `getUsers()`
  - `getRoles()`
  - `farmService.loadAvailableFarms(true)`
- 后处理：
  - 用户列表执行 `hydrateUserWithMeta()`
  - 角色列表赋给 `roles`
  - 场站选项赋给 `farmOptions`

2. `openCreateDialog()`
- 重置 `userForm`
- `isEdit = false`
- 打开用户弹窗

3. `openEditDialog(row)`
- 将行数据写入 `userForm`
- `currentUserId = row.id`
- `isEdit = true`

4. `submitUser()`
- 表单校验通过后：
  - 编辑：
    - `updateUser(currentUserId, { full_name, email, role_id, is_active })`
  - 新增：
    - `createUser({ username, password, full_name, email, role_id, is_active })`
- 无论新增还是编辑：
  - `setUserMeta(userForm.username, { phone, stations })`
  - 写本地审计日志
  - 成功提示
  - 关闭弹窗
  - 重新拉取数据

关键事实：

- 编辑时不会把 `phone/stations` 发给后端
- 新增时也不会把 `phone/stations` 发给后端

5. `openResetDialog(row)`
- 设置 `currentUserId`
- 清空 `resetForm`
- 打开重置密码弹窗

6. `submitResetPassword()`
- 校验新密码与确认密码
- 调用 `resetUserPassword(currentUserId, resetForm.password)`
- 写本地审计日志
- 成功后关闭弹窗

7. `toggleStatus(row)`
- 先确认
- 再 `updateUser(row.id, { is_active: nextActive })`
- 写本地审计日志
- 刷新列表

8. `removeUser(row)`
- 先确认
- 再 `deleteUser(row.id)`
- 同时 `removeUserMeta(row.username)`
- 写本地审计日志
- 刷新列表

---

## 5. 交互明细表

### 5.1 工具栏

| 元素类型 | 位置 | 文案 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 输入框 | 工具栏左侧 | 搜索用户/姓名/手机号/角色 | 前端搜索过滤 | 更新 `searchQuery`，驱动 `filteredUsers`/`pagedUsers` 变化 | 否 | 否 | 影响表格与分页 |
| 按钮 | 工具栏右侧 | 刷新 | 重新加载用户、角色、场站选项 | 调用 `fetchData()` | 否 | 是 | 影响表格、角色下拉、场站下拉 |
| 按钮 | 工具栏右侧 | 新增用户 | 打开新增弹窗 | `openCreateDialog()` | 是，`canManageUsers` | 否 | 影响弹窗 |

### 5.2 表格展示与操作

| 元素类型 | 位置 | 文案/字段 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 标签 | 角色列 | 角色名称 | 展示用户角色 | 管理员角色显示 `danger`，其他显示 `info` | 否 | 否 | 否 |
| 文本/tooltip | 管理场站列 | 全部场站/编码列表/数量摘要 | 展示可管理场站范围 | `stations > 2` 时 tooltip 展示完整内容 | 否 | 否 | 否 |
| 标签 | 状态列 | 启用/禁用 | 展示用户状态 | 无点击行为 | 否 | 否 | 否 |
| 按钮 | 操作列 | 编辑 | 打开编辑弹窗 | `openEditDialog(row)` | 是，`canManageUsers` | 否 | 影响弹窗 |
| 按钮 | 操作列 | 启停 | 切换用户启停 | `toggleStatus(row)` | 是，`canManageUsers` | 是，`updateUser` | 影响表格 |
| 按钮 | 操作列 | 重置密码 | 打开重置弹窗 | `openResetDialog(row)` | 是，`canManageUsers` | 否 | 影响弹窗 |
| 按钮 | 操作列 | 删除 | 删除用户 | `removeUser(row)` | 是，`canManageUsers` | 是，`deleteUser` | 影响表格、本地 meta |

### 5.3 用户新增/编辑弹窗元素

| 元素类型 | 位置 | 字段 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 输入框 | 用户弹窗 | 用户名 | 录入用户名 | 更新 `userForm.username`；编辑态禁用 | 是，弹窗入口受权限控制 | 否 | 影响提交 payload |
| 密码框 | 用户弹窗 | 密码 | 新增用户时录入密码 | 更新 `userForm.password` | 是 | 否 | 影响新增 payload |
| 输入框 | 用户弹窗 | 姓名 | 录入姓名 | 更新 `userForm.full_name` | 是 | 否 | 影响提交 payload |
| 输入框 | 用户弹窗 | 手机号 | 录入手机号 | 更新 `userForm.phone` | 是 | 否 | 写入本地 meta，不进后端 payload |
| 输入框 | 用户弹窗 | 邮箱 | 录入邮箱 | 更新 `userForm.email` | 是 | 否 | 影响提交 payload |
| 下拉框 | 用户弹窗 | 角色 | 选择角色 | 更新 `userForm.role_id` | 是 | 否 | 影响提交 payload |
| 多选框 | 用户弹窗 | 管理场站 | 选择场站范围 | 更新 `userForm.stations`；`__ALL__` 互斥规则由 `normalizeStationSelection()` 处理 | 是 | 否 | 写入本地 meta |
| 开关 | 用户弹窗 | 启用状态 | 设置用户启停 | 更新 `userForm.is_active` | 是 | 否 | 影响提交 payload |
| 按钮 | 用户弹窗 footer | 取消 | 关闭弹窗 | `showUserDialog = false` | 是 | 否 | 否 |
| 按钮 | 用户弹窗 footer | 提交 | 保存用户 | `submitUser()` | 是 | 是，`createUser/updateUser` | 影响表格、本地 meta、本地审计 |

### 5.4 重置密码弹窗元素

| 元素类型 | 位置 | 字段 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 密码框 | 重置弹窗 | 新密码 | 输入新密码 | 更新 `resetForm.password` | 是 | 否 | 影响重置 payload |
| 密码框 | 重置弹窗 | 确认密码 | 二次确认 | 更新 `resetForm.confirmPassword` | 是 | 否 | 影响校验 |
| 按钮 | 重置弹窗 footer | 取消 | 关闭弹窗 | `showResetDialog = false` | 是 | 否 | 否 |
| 按钮 | 重置弹窗 footer | 提交 | 提交重置密码 | `submitResetPassword()` | 是 | 是，`resetUserPassword` | 写本地审计 |

### 5.5 分页元素

| 元素类型 | 位置 | 文案 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 分页器 | 表格下方 | total/sizes/pager/jumper | 前端分页 | 更新 `currentPage`、`pageSize`，重新计算 `pagedUsers` | 否 | 否 | 影响表格 |

### 5.6 页面中未发现的元素

- 日期选择器
- tab
- 图表
- 抽屉
- 导出下载
- 上传导入
- 批量操作

---

## 6. 接口明细表

### 6.1 `getUsers`

| 字段 | 说明 |
|---|---|
| 接口名称 | 获取用户列表 |
| 请求方法 | `GET` |
| URL | 优先 `/api/v1/auth/users`，回退 `/api/auth/users` |
| 所在 api/service 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js) |
| 调用函数名 | `getUsers()` |
| 调用触发条件 | 页面初始化、点击刷新、新增/编辑/启停/删除成功后 |
| 请求参数 | 无 |
| 返回数据结构 | `response.data`；页面兼容数组或 `{ users: [] }` |
| 返回数据映射到页面哪个组件/哪个字段 | 经 `hydrateUserWithMeta()` 后映射到 `users`，再参与搜索和分页 |
| 失败时页面怎么处理 | `fetchData()` catch 中 `ElMessage.error(...)` |

### 6.2 `getRoles`

| 字段 | 说明 |
|---|---|
| 接口名称 | 获取角色列表 |
| 请求方法 | `GET` |
| URL | 优先 `/api/v1/auth/roles`，回退 `/api/auth/roles` |
| 所在 api/service 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js) |
| 调用函数名 | `getRoles()` |
| 调用触发条件 | `fetchData()` |
| 请求参数 | 无 |
| 返回数据结构 | `response.data` |
| 返回数据映射到页面哪个组件/哪个字段 | `roles`，用于用户弹窗角色下拉 |
| 失败时页面怎么处理 | `fetchData()` catch 中 `ElMessage.error(...)` |

### 6.3 `farmService.loadAvailableFarms(true)`

| 字段 | 说明 |
|---|---|
| 接口名称 | 加载可选场站列表 |
| 请求方法 | 内部会串行/并行调用多个 GET |
| URL | 可能使用 `/api/v1/autopredict/farms`、`/api/farms`、`/api/v1/report/farms`、`/api/report/farms`、`/api/v1/farms`、`/api/farms` |
| 所在 api/service 文件 | [farmService.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/farmService.js)、[farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js) |
| 调用函数名 | `farmService.loadAvailableFarms(true)` |
| 调用触发条件 | `fetchData()` |
| 请求参数 | `forceReload = true` |
| 返回数据结构 | 标准化后的 `{ code, name }[]` |
| 返回数据映射到页面哪个组件/哪个字段 | `farmOptions`，用于“管理场站”多选下拉 |
| 失败时页面怎么处理 | `farmService` 内部多层 fallback；全部失败时返回默认场站 `DEFAULT_FARM` |

补充事实：

- `farmService` 会优先尝试自动预测场站接口，再尝试报表场站接口，再尝试通用场站接口。
- 还会按当前登录用户在 `userMetaStore` 中的 `stations` 范围做过滤。

### 6.4 `createUser`

| 字段 | 说明 |
|---|---|
| 接口名称 | 新增用户 |
| 请求方法 | `POST` |
| URL | 优先 `/api/v1/auth/users`，回退 `/api/auth/users` |
| 所在 api/service 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js) |
| 调用函数名 | `createUser(userData)` |
| 调用触发条件 | 新增用户弹窗提交且校验通过 |
| 请求参数 | `{ username, password, full_name, email, role_id, is_active }` |
| 返回数据结构 | `response.data` |
| 返回数据映射到页面哪个组件/哪个字段 | 不直接消费；成功后重新 `fetchData()` |
| 失败时页面怎么处理 | `submitUser()` catch 中写失败审计日志并 `ElMessage.error(...)` |

关键说明：

- `phone` 与 `stations` 不在请求体里。

### 6.5 `updateUser`

| 字段 | 说明 |
|---|---|
| 接口名称 | 更新用户 |
| 请求方法 | `PUT` |
| URL | 优先 `/api/v1/auth/users/{userId}`，回退 `/api/auth/users/{userId}` |
| 所在 api/service 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js) |
| 调用函数名 | `updateUser(userId, userData)` |
| 调用触发条件 | 编辑用户提交；状态切换 |
| 请求参数 | 编辑时 `{ full_name, email, role_id, is_active }`；状态切换时 `{ is_active }` |
| 返回数据结构 | `response.data` |
| 返回数据映射到页面哪个组件/哪个字段 | 不直接消费；成功后刷新列表 |
| 失败时页面怎么处理 | 局部 catch + `ElMessage.error(...)` |

关键说明：

- 编辑时也不会把 `phone` 与 `stations` 传给后端。

### 6.6 `resetUserPassword`

| 字段 | 说明 |
|---|---|
| 接口名称 | 重置用户密码 |
| 请求方法 | `POST` |
| URL | 优先 `/api/v1/auth/users/{userId}/reset-password`，回退 `/api/auth/users/{userId}/reset-password` |
| 所在 api/service 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js) |
| 调用函数名 | `resetUserPassword(userId, newPassword)` |
| 调用触发条件 | 重置密码弹窗提交且校验通过 |
| 请求参数 | `{ new_password }` |
| 返回数据结构 | `response.data` |
| 返回数据映射到页面哪个组件/哪个字段 | 无直接映射 |
| 失败时页面怎么处理 | `submitResetPassword()` catch 中写失败审计日志并提示错误 |

### 6.7 `deleteUser`

| 字段 | 说明 |
|---|---|
| 接口名称 | 删除用户 |
| 请求方法 | `DELETE` |
| URL | 优先 `/api/v1/auth/users/{userId}`，回退 `/api/auth/users/{userId}` |
| 所在 api/service 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js) |
| 调用函数名 | `deleteUser(userId)` |
| 调用触发条件 | 删除确认后 |
| 请求参数 | `userId` 路径参数 |
| 返回数据结构 | `response.data` |
| 返回数据映射到页面哪个组件/哪个字段 | 无直接映射；成功后重新拉取数据 |
| 失败时页面怎么处理 | `removeUser()` catch 中写失败审计日志并提示错误 |

### 6.8 审计与本地元数据，不属于后端接口但属于关键数据链

#### `setUserMeta / getUserMeta / removeUserMeta`

| 字段 | 说明 |
|---|---|
| 能力名称 | 用户本地元数据存取 |
| 类型 | `localStorage` |
| 文件 | [userMetaStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/userMetaStore.js) |
| 键名 | `user_profile_meta_v1` |
| 存储字段 | `phone`、`stations` |
| 在本页面的用途 | 用户表格手机号/管理场站展示；新增/编辑保存；删除时清理 |

#### `appendAuditLog`

| 字段 | 说明 |
|---|---|
| 能力名称 | 本地审计日志写入 |
| 类型 | `localStorage` |
| 文件 | [auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js) |
| 键名 | `audit_logs_v1` |
| 在本页面的触发点 | 新增、编辑、重置密码、启停、删除的成功/失败分支 |

---

## 7. 数据流说明

### 7.1 初始化加载流程

1. `onMounted(fetchData)`
2. `fetchData()` 并行调用：
   - `getUsers()`
   - `getRoles()`
   - `farmService.loadAvailableFarms(true)`
3. 用户数据执行 `hydrateUserWithMeta()`
   - 为每个用户补入本地 `phone`
   - 为每个用户补入本地 `stations`
4. 角色列表写入 `roles`
5. 场站选项写入 `farmOptions`
6. 页面渲染表格、表单选项

### 7.2 用户操作后的数据变化

#### 搜索

- 修改 `searchQuery`
- `filteredUsers` 响应式重算
- `pagedUsers` 随之变化

#### 新增用户

1. 打开弹窗并重置 `userForm`
2. 提交时先校验
3. 调用 `createUser(...)`
4. `setUserMeta(username, { phone, stations })`
5. 写成功/失败本地审计日志
6. 重新 `fetchData()`

#### 编辑用户

1. 将行数据灌入 `userForm`
2. 提交时调用 `updateUser(...)`
3. `setUserMeta(username, { phone, stations })`
4. 写审计日志
5. 刷新列表

#### 重置密码

1. 打开重置弹窗
2. 校验两次密码一致
3. 调用 `resetUserPassword(...)`
4. 写审计日志

#### 启停用户

1. 确认框
2. `updateUser(row.id, { is_active })`
3. 写审计日志
4. 刷新列表

#### 删除用户

1. 确认框
2. `deleteUser(row.id)`
3. `removeUserMeta(row.username)`
4. 写审计日志
5. 刷新列表

### 7.3 状态分类

#### 本地状态

- `loading`
- `submitting`
- `resetting`
- `searchQuery`
- `currentPage`
- `pageSize`
- `showUserDialog`
- `showResetDialog`
- `isEdit`
- `currentUserId`
- `userForm`
- `resetForm`

#### 全局 store 状态

- 代码中未发现 Vuex/Pinia store 使用

#### 后端接口数据

- 用户列表
- 角色列表
- 场站选项原始数据（经 `farmService` 间接来自后端）

#### 本地缓存数据

- `localStorage.user`：当前登录用户与权限
- `user_profile_meta_v1`：用户手机号、场站范围
- `audit_logs_v1`：操作审计日志

#### 二次加工/格式化字段

- `hydrateUserWithMeta()` 合并后的用户对象
- `filteredUsers`
- `pagedUsers`
- `formatDate(last_login)`

### 7.4 数据源闭环结论

该页当前的数据闭环是：

`后端用户/角色数据` + `本地用户元数据(phone/stations)` + `后端/本地场站列表` -> `用户表格/用户表单`

因此：

- 用户表格中的手机号、管理场站不一定能从后端接口追溯
- 审计日志也不是服务端审计，而是本地浏览器审计

---

## 8. 权限与状态控制说明

### 8.1 路由与菜单权限

1. 路由声明位置
- 文件：[router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- 路由：
  - `path: 'users'`
  - `name: 'UserManagement'`
  - `meta.requiredPermissions = ['manage_users']`

2. 菜单显隐位置
- 文件：[AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- 菜单项：
  - `index="/users"`
  - 条件：`hasPermission('manage_users')`

### 8.2 页面内部权限控制

页面内部还有一层 `canManageUsers`：

- 数据来源：`localStorage.user.permissions`
- 规则：
  - 包含 `manage_users`
  - 或包含 `admin`

受影响元素：

- 新增用户按钮
- 操作列按钮组

### 8.3 实际守卫行为

全局守卫位于 [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)：

- 只校验 `localStorage.user`
- 未发现基于 `requiredPermissions` 的真正拦截逻辑

结论：

- 路由虽然声明了 `manage_users`，但前端硬拦截主要还是靠菜单隐藏和页面内部按钮显隐。

---

## 9. 风险点 / 待确认点

### 9.1 明确风险点

1. 用户手机号与管理场站不是后端用户主数据  
证据：`submitUser()` 的请求体不包含 `phone/stations`，这两个字段只通过 `setUserMeta()` 写本地存储。

2. 本地缓存会影响用户展示一致性  
证据：`hydrateUserWithMeta()` 直接用 `getUserMeta(username)` 覆盖展示字段。

3. 审计日志不是后端审计  
证据：`appendAuditLog()` 写入 `localStorage` 的 `audit_logs_v1`。

4. 前端分页与搜索都不是服务端能力  
证据：`filteredUsers`、`pagedUsers` 完全在前端计算。

5. 编辑用户时不能修改用户名  
证据：编辑态 `username` 输入框禁用。

6. 路由权限声明未在全局守卫中落地  
证据：`beforeEach` 只检查登录态。

### 9.2 待确认点

1. 后端用户接口是否本应支持 `phone`、`stations` 字段  
当前判断：前端明显在本地补充，需结合后端确认。

2. 本地审计是否只是临时替代方案  
当前判断：高度可能，需结合审计要求确认。

3. `farmService.loadAvailableFarms(true)` 受当前登录用户元数据范围影响，是否会导致管理员无法给他人配置更大范围场站  
当前判断：需结合实际角色配置确认。

4. `canManageUsers` 只识别 `permissions` 数组或嵌套数组，是否覆盖所有登录态结构  
当前判断：代码中未明确保证。

---

## 10. 代码证据清单

### 10.1 页面文件

- [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue)
  - 组件名：`UserManagement`
  - 关键状态：`users`、`roles`、`farmOptions`、`userForm`、`resetForm`
  - 关键函数：
    - `fetchData()`
    - `hydrateUserWithMeta()`
    - `normalizeStationSelection()`
    - `submitUser()`
    - `submitResetPassword()`
    - `toggleStatus()`
    - `removeUser()`

### 10.2 API 文件

- [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js)
  - `getUsers()`
  - `createUser()`
  - `updateUser()`
  - `deleteUser()`
  - `resetUserPassword()`
  - `getRoles()`

- [axios.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/axios.js)
  - 请求鉴权
  - 全局错误提示
  - 401 清理登录态

### 10.3 本地数据能力

- [userMetaStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/userMetaStore.js)
  - `getUserMeta()`
  - `setUserMeta()`
  - `removeUserMeta()`

- [auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js)
  - `appendAuditLog()`

- [farmService.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/farmService.js)
  - `loadAvailableFarms(true)`
  - `applyUserScope()`

### 10.4 路由与权限入口

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - 路由名：`UserManagement`
  - 路由路径：`users`
  - 权限元信息：`requiredPermissions: ['manage_users']`
  - 守卫：`beforeEach(...)`

- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - 菜单项：`index="/users"`
  - 权限判断：`hasPermission('manage_users')`

---

## 关键代码证据清单

- [UserManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/UserManagement.vue)
- [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js)
- [userMetaStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/userMetaStore.js)
- [auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js)
- [farmService.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/farmService.js)
- [farmApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/farmApi.js)
- [axios.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/axios.js)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)

## 可能遗漏点检查清单

- 后端 `getUsers/updateUser/createUser` 是否实际支持 `phone/stations`，当前前端代码中未体现
- 是否存在服务端审计接口但本页未接入，当前代码中未发现
- 是否存在用户列表服务端分页/搜索能力，当前页面未接入
- 页面中文文案终端乱码，逻辑已核对，但展示文案建议在编辑器中复核
