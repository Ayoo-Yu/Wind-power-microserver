# 用户与权限代码级完整拆解

## 1. 页面概览

### 1.1 页面基础信息

| 字段 | 结论 |
|---|---|
| 页面名称 | 用户与权限 |
| 所属模块 | 系统管理 |
| 路由路径 | `/users/roles` |
| 页面入口文件 | [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue) |
| 页面依赖的子组件列表 | 代码中未发现本项目自定义子组件；页面直接使用 Element Plus 组件 `el-card`、`el-button`、`el-table`、`el-table-column`、`el-tag`、`el-button-group`、`el-dialog`、`el-form`、`el-form-item`、`el-input`、`el-tree` |
| 页面依赖的 store/hooks/model/service/api 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js)、[permissions.js](D:/my-vue-project/wind-power-forecast/frontend/src/constants/permissions.js)、[auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js)、[axios.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/axios.js) |
| 页面是否受权限控制 | 路由声明 `meta.requiredPermissions = ['manage_roles']`；侧边栏菜单显隐条件为 `hasPermission('manage_roles')`；页面内部还有 `canManageRoles` 控制新增、初始化预设、编辑、删除按钮 |

### 1.2 页面定位结论

基于当前代码，这一页是一个已经接入真实角色 CRUD 接口的角色管理页，能力闭环包括：

- 角色列表拉取
- 角色新增
- 角色编辑
- 角色删除
- 权限树勾选
- 角色预设一键初始化

同时，这页有一个非常关键的特征：

- 后端角色数据里的 `permissions` 只是权限 key 集合
- 权限中文名称、权限树结构、预设角色模板，全部来自前端常量 [permissions.js](D:/my-vue-project/wind-power-forecast/frontend/src/constants/permissions.js)

因此这页实际是：

`后端角色数据` + `前端权限树定义` + `前端角色预设模板` + `本地审计日志`

### 1.3 关键判断

1. 页面已接真实接口：
   - `getRoles`
   - `createRole`
   - `updateRole`
   - `deleteRole`
2. 权限树不是从后端加载，而是直接使用 `PERMISSION_TREE`。
3. 角色预设初始化逻辑基于 `ROLE_PRESETS`，属于前端主动补种角色数据。
4. 页面内部 `isBuiltinRole()` 会对内置角色名做特殊处理，用于编辑态禁用角色名称输入框。
5. 页面每次新增、编辑、删除、预设初始化都会写本地审计日志。

---

## 2. 页面结构树

```text
用户与权限 RoleManagement.vue
├─ 页面根容器 role-management page-shell
│  ├─ 页面头部 page-header
│  │  ├─ 标题 h2
│  │  └─ 描述文本 p
│  ├─ 主卡片 el-card.card-shell
│  │  ├─ 工具栏 toolbar
│  │  │  ├─ 刷新按钮
│  │  │  ├─ 初始化预设角色按钮
│  │  │  └─ 新增角色按钮
│  │  └─ 角色表格 el-table(roles)
│  │     ├─ 角色名称列
│  │     ├─ 描述列
│  │     ├─ 权限数量列
│  │     ├─ 权限标签预览列
│  │     └─ 操作列
│  │        ├─ 编辑按钮
│  │        └─ 删除按钮
│  └─ 新增/编辑角色弹窗 el-dialog
│     └─ 角色表单 el-form
│        ├─ 角色名称输入框
│        ├─ 角色描述输入框
│        └─ 权限树 el-tree(show-checkbox)
```

---

## 3. 区块说明

### 3.1 页面头部

| 字段 | 说明 |
|---|---|
| 区块名称 | 页面头部 |
| 对应组件名 | `RoleManagement` |
| 文件路径 | [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue) |
| 展示内容 | 页面标题、说明文案 |
| 数据来源 | 模板硬编码 |
| 是否可交互 | 否 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 否 |

### 3.2 工具栏

| 字段 | 说明 |
|---|---|
| 区块名称 | 工具栏 |
| 对应组件名 | `RoleManagement` |
| 文件路径 | [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue) |
| 展示内容 | 刷新、初始化预设角色、新增角色 |
| 数据来源 | `loading`、`canManageRoles` |
| 是否可交互 | 是 |
| 是否有权限控制 | 初始化预设角色、新增角色受 `canManageRoles` 控制 |
| 是否有定时刷新或自动更新 | 否 |

交互：

- “刷新” -> `fetchRoles()`
- “初始化预设角色” -> `initPresetRoles()`
- “新增角色” -> `openCreateDialog()`

### 3.3 角色表格区

| 字段 | 说明 |
|---|---|
| 区块名称 | 角色表格区 |
| 对应组件名 | `RoleManagement` |
| 文件路径 | [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue) |
| 展示内容 | 角色名、描述、权限数量、权限标签预览、操作按钮 |
| 数据来源 | `roles` |
| 是否可交互 | 是 |
| 是否有权限控制 | 操作列整体受 `canManageRoles` 控制 |
| 是否有定时刷新或自动更新 | 否 |

权限数量列：

- 通过 `normalizePermissions(row.permissions).length` 计算

权限预览列：

- 取前 6 个权限 key
- 用 `getPermissionLabel(perm)` 映射成人类可读标签
- 超过 6 个时显示 `+N`

关键事实：

- 权限标签显示完全依赖前端常量映射，不依赖后端返回中文名。

### 3.4 新增/编辑角色弹窗

| 字段 | 说明 |
|---|---|
| 区块名称 | 角色编辑弹窗 |
| 对应组件名 | `RoleManagement` |
| 文件路径 | [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue) |
| 展示内容 | 角色名称、角色描述、权限树 |
| 数据来源 | `roleForm`、`permissionTree` |
| 是否可交互 | 是 |
| 是否有权限控制 | 入口受 `canManageRoles` 控制 |
| 是否有定时刷新或自动更新 | 否 |

权限树特征：

- `node-key="id"`
- `show-checkbox`
- `default-expand-all`
- `check-strictly=false`

说明：

- 勾选时不会自动把所有树节点原样发给后端，而是通过 `syncCheckedPermissions()` 过滤成 `ALL_PERMISSION_KEYS` 中的叶子权限 key。

---

## 4. 组件明细表

### 4.1 页面组件：RoleManagement

| 维度 | 结论 |
|---|---|
| 组件名称 | `RoleManagement` |
| 文件路径 | [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue) |
| 父子关系 | 父级为 [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue) 中的 `<router-view>`；代码中未发现本项目自定义子组件 |
| props / emits / callbacks | 未定义 `props`、未定义 `emits` |
| 内部 state / computed / hooks / store 使用情况 | `loading`、`submitting`、`roles`、`showRoleDialog`、`isEdit`、`roleFormRef`、`permissionTreeRef`、`roleForm`、`currentUser`、`canManageRoles`、`permissionTree`、`permissionLabelMap` |
| 生命周期或副作用逻辑 | `onMounted(fetchRoles)` |
| 实现的具体功能 | 角色列表展示、权限标签映射、角色新增、角色编辑、角色删除、预设角色初始化、权限树勾选同步 |
| 触发了哪些接口 | `getRoles`、`createRole`、`updateRole`、`deleteRole` |
| 与其他组件的联动关系 | 与 `permissions.js` 常量联动构建权限树和标签映射；与 `auditLogStore` 联动记录操作日志 |
| 加载态 / 空态 / 异常态如何处理 | `loading` 驱动表格加载；无专门空态；局部 `ElMessage` 处理异常 |

#### 4.1.1 本地状态与计算属性

1. `loading`
- 拉取角色列表、初始化预设角色时使用

2. `submitting`
- 提交角色弹窗时使用

3. `roles`
- 角色列表主数据
- 来自 `getRoles()`

4. `showRoleDialog`
- 控制角色弹窗显隐

5. `isEdit`
- 区分新增和编辑

6. `roleForm`
- 角色表单
- 字段：
  - `id`
  - `name`
  - `description`
  - `permissions`

7. `currentUser`
- 从 `localStorage.user` 读取当前登录用户

8. `canManageRoles`
- 判断当前用户是否有 `manage_roles` 或 `admin`

9. `permissionTree`
- 直接引用 `PERMISSION_TREE`

10. `permissionLabelMap`
- 通过 `ALL_PERMISSION_KEYS` 和 `PERMISSION_TREE` 生成映射
- 用于表格标签显示

#### 4.1.2 关键辅助函数

1. `normalizePermissions(value)`
- 兼容后端权限字段结构：
  - 直接数组
  - `{ permissions: [] }`

2. `getPermissionLabel(key)`
- 从 `permissionLabelMap` 返回显示名

3. `isBuiltinRole(name)`
- 识别内置角色名：
  - 系统管理员
  - `admin`
  - `Administrator`
- 用于编辑态禁用角色名称输入框

4. `syncCheckedPermissions()`
- 从 `permissionTreeRef.getCheckedKeys()` 取勾选节点
- 过滤出 `ALL_PERMISSION_KEYS` 中的有效权限 key
- 写回 `roleForm.permissions`

说明：

- 这个函数避免把分组节点如 `menu_user`、`menu_report` 直接提交给后端。

#### 4.1.3 核心业务方法

1. `fetchRoles()`
- 触发时机：
  - 页面初始化
  - 点击刷新
  - 新增/编辑/删除/初始化预设后
- 行为：
  - `loading = true`
  - 调用 `getRoles()`
  - 返回值若为数组则直接赋给 `roles`

2. `openCreateDialog()`
- 设置新增态
- 重置 `roleForm`
- 打开弹窗
- `nextTick` 后清空权限树勾选

3. `openEditDialog(row)`
- 设置编辑态
- 把 `row` 的 `id/name/description/permissions` 写入 `roleForm`
- 打开弹窗
- `nextTick` 后用 `setCheckedKeys(roleForm.permissions)` 回填权限树

4. `submitRole()`
- 先 `syncCheckedPermissions()`
- 再 `roleFormRef.validate(...)`
- 组装 payload：
  - `name`
  - `description`
  - `permissions`
- 编辑时：
  - `updateRole(roleForm.id, payload)`
- 新增时：
  - `createRole(payload)`
- 成功后：
  - 写本地审计日志
  - 成功提示
  - 关闭弹窗
  - 刷新列表
- 失败时：
  - 写失败审计日志
  - 错误提示

5. `removeRole(row)`
- 先确认
- 调用 `deleteRole(row.id)`
- 写本地审计日志
- 成功提示并刷新列表

6. `initPresetRoles()`
- 先收集现有角色名
- 用 `ROLE_PRESETS` 过滤出缺失角色
- 如果没有缺失角色：
  - `ElMessage.info(...)`
- 否则：
  - 循环 `createRole(...)`
  - 每创建一个就写审计日志
  - 最后成功提示并刷新列表

关键事实：

- “初始化预设角色”不是只做本地填充，而是实际调用后端创建角色接口。

---

## 5. 交互明细表

### 5.1 工具栏

| 元素类型 | 位置 | 文案 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 按钮 | 工具栏左侧 | 刷新 | 重新加载角色列表 | 调用 `fetchRoles()` | 否 | 是，`getRoles` | 影响表格 |
| 按钮 | 工具栏左侧 | 初始化预设角色 | 一键补种缺失预设角色 | 调用 `initPresetRoles()` | 是，`canManageRoles` | 是，循环 `createRole` | 影响表格 |
| 按钮 | 工具栏右侧 | 新增角色 | 打开新增角色弹窗 | `openCreateDialog()` | 是，`canManageRoles` | 否 | 影响弹窗 |

### 5.2 角色表格区

| 元素类型 | 位置 | 文案/字段 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 表格 | 主内容区 | 角色列表 | 展示所有角色 | 无行点击 | 否 | 否 | 否 |
| 文本列 | 权限数量 | 数量值 | 展示权限数量 | 无点击行为 | 否 | 否 | 否 |
| 标签 | 权限预览列 | 权限标签 | 显示前 6 个权限标签 | 无点击行为 | 否 | 否 | 否 |
| 标签 | 权限预览列 | `+N` | 表示更多权限未展开 | 无点击行为 | 否 | 否 | 否 |
| 按钮 | 操作列 | 编辑 | 打开编辑弹窗 | `openEditDialog(row)` | 是，`canManageRoles` | 否 | 影响弹窗 |
| 按钮 | 操作列 | 删除 | 删除角色 | `removeRole(row)` | 是，`canManageRoles` | 是，`deleteRole` | 影响表格 |

### 5.3 角色弹窗表单

| 元素类型 | 位置 | 字段 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 输入框 | 弹窗 | 角色名称 | 录入角色名 | 更新 `roleForm.name`；编辑内置角色时禁用 | 是，入口受权限控制 | 否 | 影响提交 payload |
| 文本域 | 弹窗 | 角色描述 | 录入描述 | 更新 `roleForm.description` | 是 | 否 | 影响提交 payload |
| 权限树 | 弹窗 | 权限矩阵 | 勾选权限 | 触发 `syncCheckedPermissions()` 更新 `roleForm.permissions` | 是 | 否 | 影响提交 payload、表格预览 |
| 按钮 | 弹窗 footer | 取消 | 关闭弹窗 | `showRoleDialog = false` | 是 | 否 | 否 |
| 按钮 | 弹窗 footer | 提交 | 保存角色 | `submitRole()` | 是 | 是，`createRole/updateRole` | 影响表格、本地审计 |

### 5.4 页面中未发现的元素

- 搜索框
- 日期选择器
- tab
- 图表
- 抽屉
- 分页
- 导出下载
- 上传导入
- 批量操作

---

## 6. 接口明细表

### 6.1 `getRoles`

| 字段 | 说明 |
|---|---|
| 接口名称 | 获取角色列表 |
| 请求方法 | `GET` |
| URL | 优先 `/api/v1/auth/roles`，回退 `/api/auth/roles` |
| 所在 api/service 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js) |
| 调用函数名 | `getRoles()` |
| 调用触发条件 | 页面初始化、点击刷新、角色新增/编辑/删除/预设初始化成功后 |
| 请求参数 | 无 |
| 返回数据结构 | `response.data`，页面按数组处理 |
| 返回数据映射到页面哪个组件/哪个字段 | 赋给 `roles`，用于表格渲染 |
| 失败时页面怎么处理 | `fetchRoles()` catch 中 `ElMessage.error(...)` |

### 6.2 `createRole`

| 字段 | 说明 |
|---|---|
| 接口名称 | 新增角色 |
| 请求方法 | `POST` |
| URL | 优先 `/api/v1/auth/roles`，回退 `/api/auth/roles` |
| 所在 api/service 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js) |
| 调用函数名 | `createRole(roleData)` |
| 调用触发条件 | 新增角色提交；初始化预设角色时 |
| 请求参数 | `{ name, description, permissions }` |
| 返回数据结构 | `response.data` |
| 返回数据映射到页面哪个组件/哪个字段 | 不直接消费；成功后刷新列表 |
| 失败时页面怎么处理 | `submitRole()` 或 `initPresetRoles()` 内局部 catch 提示错误 |

### 6.3 `updateRole`

| 字段 | 说明 |
|---|---|
| 接口名称 | 更新角色 |
| 请求方法 | `PUT` |
| URL | 优先 `/api/v1/auth/roles/{roleId}`，回退 `/api/auth/roles/{roleId}` |
| 所在 api/service 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js) |
| 调用函数名 | `updateRole(roleId, roleData)` |
| 调用触发条件 | 编辑角色提交 |
| 请求参数 | `{ name, description, permissions }` |
| 返回数据结构 | `response.data` |
| 返回数据映射到页面哪个组件/哪个字段 | 不直接消费；成功后刷新列表 |
| 失败时页面怎么处理 | `submitRole()` catch 中写失败审计日志并提示错误 |

### 6.4 `deleteRole`

| 字段 | 说明 |
|---|---|
| 接口名称 | 删除角色 |
| 请求方法 | `DELETE` |
| URL | 优先 `/api/v1/auth/roles/{roleId}`，回退 `/api/auth/roles/{roleId}` |
| 所在 api/service 文件 | [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js) |
| 调用函数名 | `deleteRole(roleId)` |
| 调用触发条件 | 删除确认后 |
| 请求参数 | `roleId` 路径参数 |
| 返回数据结构 | `response.data` |
| 返回数据映射到页面哪个组件/哪个字段 | 无直接映射；成功后刷新列表 |
| 失败时页面怎么处理 | `removeRole()` catch 中写失败审计日志并提示错误 |

### 6.5 前端权限树与预设角色，不属于后端接口但属于关键数据源

#### `PERMISSION_TREE`

| 字段 | 说明 |
|---|---|
| 能力名称 | 权限树定义 |
| 类型 | 前端常量 |
| 文件 | [permissions.js](D:/my-vue-project/wind-power-forecast/frontend/src/constants/permissions.js) |
| 作用 | 提供 `el-tree` 的层级结构和标签 |
| 被谁消费 | `permissionTree`、`permissionLabelMap`、`getPermissionLabel()` |

#### `ALL_PERMISSION_KEYS`

| 字段 | 说明 |
|---|---|
| 能力名称 | 有效叶子权限 key 集 |
| 类型 | 前端常量 |
| 文件 | [permissions.js](D:/my-vue-project/wind-power-forecast/frontend/src/constants/permissions.js) |
| 作用 | 过滤树勾选结果，只保留真实权限 key |

#### `ROLE_PRESETS`

| 字段 | 说明 |
|---|---|
| 能力名称 | 角色预设模板 |
| 类型 | 前端常量 |
| 文件 | [permissions.js](D:/my-vue-project/wind-power-forecast/frontend/src/constants/permissions.js) |
| 作用 | `initPresetRoles()` 时生成缺失角色 |

#### `appendAuditLog`

| 字段 | 说明 |
|---|---|
| 能力名称 | 本地审计日志写入 |
| 类型 | `localStorage` |
| 文件 | [auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js) |
| 在本页面的触发点 | 新增、编辑、删除、初始化预设角色的成功/失败分支 |

---

## 7. 数据流说明

### 7.1 初始化加载流程

1. `onMounted(fetchRoles)`
2. 调用 `getRoles()`
3. 返回角色数组写入 `roles`
4. 表格渲染：
   - 名称
   - 描述
   - 权限数量
   - 权限标签预览

说明：

- 权限树结构不是从接口返回，而是初始化时直接来自 `PERMISSION_TREE`

### 7.2 用户操作后的数据变化

#### 新增角色

1. 点击“新增角色”
2. 重置 `roleForm`
3. 清空权限树勾选
4. 用户勾选权限树
5. `syncCheckedPermissions()` 更新 `roleForm.permissions`
6. `submitRole()` 调用 `createRole(payload)`
7. 写审计日志
8. 刷新列表

#### 编辑角色

1. 点击编辑按钮
2. 把当前行数据回填到 `roleForm`
3. `setCheckedKeys(roleForm.permissions)` 回填树勾选
4. 提交时调用 `updateRole(roleForm.id, payload)`
5. 写审计日志
6. 刷新列表

#### 删除角色

1. 点击删除
2. 弹确认框
3. 调用 `deleteRole(row.id)`
4. 写审计日志
5. 刷新列表

#### 初始化预设角色

1. 对比现有角色名和 `ROLE_PRESETS`
2. 找出缺失角色
3. 循环调用 `createRole(...)`
4. 每个成功角色写审计日志
5. 全部完成后刷新列表

### 7.3 状态分类

#### 本地状态

- `loading`
- `submitting`
- `showRoleDialog`
- `isEdit`
- `roleForm`

#### 全局 store 状态

- 代码中未发现 Vuex/Pinia store 使用

#### 后端接口数据

- `roles`

#### 前端常量数据

- `PERMISSION_TREE`
- `ALL_PERMISSION_KEYS`
- `ROLE_PRESETS`

#### 本地缓存数据

- `localStorage.user`
- `audit_logs_v1`

#### 二次加工/格式化字段

- `normalizePermissions(row.permissions)`
- `permissionLabelMap`
- 表格权限预览标签

### 7.4 数据源闭环结论

该页当前的数据闭环是：

`后端角色数据` + `前端权限树常量` + `前端预设角色模板` -> `角色表格/权限树弹窗`

因此：

- 页面展示的权限中文名并不是后端直接返回结果
- 初始化预设角色是前端主动向后端“灌数据”

---

## 8. 权限与状态控制说明

### 8.1 路由与菜单权限

1. 路由声明位置
- 文件：[router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- 路由：
  - `path: 'users/roles'`
  - `name: 'RoleManagement'`
  - `meta.requiredPermissions = ['manage_roles']`

2. 菜单显隐位置
- 文件：[AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
- 菜单项：
  - `index="/users/roles"`
  - 条件：`hasPermission('manage_roles')`

### 8.2 页面内部权限控制

页面内部还有一层 `canManageRoles`：

- 数据来源：`localStorage.user.permissions`
- 规则：
  - 包含 `manage_roles`
  - 或包含 `admin`

受影响元素：

- 初始化预设角色按钮
- 新增角色按钮
- 表格操作列

### 8.3 实际守卫行为

全局守卫位于 [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)：

- 只校验 `localStorage.user`
- 未发现基于 `requiredPermissions` 的真正拦截逻辑

### 8.4 内置角色限制

页面中的 `isBuiltinRole(name)` 会识别以下角色名：

- 系统管理员
- `admin`
- `Administrator`

当前作用：

- 编辑这些角色时，角色名称输入框禁用

代码中未发现：

- 禁止删除内置角色的前端限制
- 禁止修改其权限的前端限制

---

## 9. 风险点 / 待确认点

### 9.1 明确风险点

1. 权限树与权限标签完全依赖前端常量  
证据：`PERMISSION_TREE`、`ALL_PERMISSION_KEYS`、`permissionLabelMap` 都来自 [permissions.js](D:/my-vue-project/wind-power-forecast/frontend/src/constants/permissions.js)。

2. 前端可主动初始化预设角色到后端  
证据：`initPresetRoles()` 会循环调用 `createRole(...)`。

3. 内置角色限制不完整  
证据：`isBuiltinRole()` 只用于禁用名称输入框，未阻止删除或改权限。

4. 页面没有搜索、分页、筛选  
证据：模板中未发现对应控件。

5. 审计日志不是服务端审计  
证据：`appendAuditLog()` 写入 `localStorage`。

6. 路由权限声明未在全局守卫中落地  
证据：`beforeEach` 只检查登录态。

### 9.2 待确认点

1. 后端角色接口是否允许删除内置角色  
当前代码中未明确，需结合后端确认。

2. 前端权限树是否与后端真实权限体系完全一致  
当前代码中未明确，需结合后端确认。

3. `ROLE_PRESETS` 是否应由后端统一下发  
当前判断：当前为前端常量，需结合架构确认。

4. 页面中文文案终端存在乱码  
当前判断：更可能是终端编码问题，不影响逻辑分析；显示文案建议在编辑器复核。

---

## 10. 代码证据清单

### 10.1 页面文件

- [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue)
  - 组件名：`RoleManagement`
  - 关键状态：`roles`、`roleForm`、`canManageRoles`
  - 关键函数：
    - `fetchRoles()`
    - `normalizePermissions()`
    - `getPermissionLabel()`
    - `isBuiltinRole()`
    - `openCreateDialog()`
    - `openEditDialog()`
    - `syncCheckedPermissions()`
    - `submitRole()`
    - `removeRole()`
    - `initPresetRoles()`

### 10.2 API 文件

- [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js)
  - `getRoles()`
  - `createRole()`
  - `updateRole()`
  - `deleteRole()`

- [axios.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/axios.js)
  - 请求鉴权
  - 全局错误提示
  - 401 清登录态

### 10.3 前端权限常量

- [permissions.js](D:/my-vue-project/wind-power-forecast/frontend/src/constants/permissions.js)
  - `PERMISSION_TREE`
  - `ALL_PERMISSION_KEYS`
  - `ROLE_PRESETS`

### 10.4 本地审计能力

- [auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js)
  - `appendAuditLog()`

### 10.5 路由与权限入口

- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
  - 路由名：`RoleManagement`
  - 路由路径：`users/roles`
  - 权限元信息：`requiredPermissions: ['manage_roles']`
  - 守卫：`beforeEach(...)`

- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)
  - 菜单项：`index="/users/roles"`
  - 权限判断：`hasPermission('manage_roles')`

---

## 关键代码证据清单

- [RoleManagement.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/RoleManagement.vue)
- [auth.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/auth.js)
- [permissions.js](D:/my-vue-project/wind-power-forecast/frontend/src/constants/permissions.js)
- [auditLogStore.js](D:/my-vue-project/wind-power-forecast/frontend/src/utils/auditLogStore.js)
- [axios.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/axios.js)
- [router/index.js](D:/my-vue-project/wind-power-forecast/frontend/src/router/index.js)
- [AppLayout.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AppLayout.vue)

## 可能遗漏点检查清单

- 后端是否对内置角色做额外保护，当前前端代码中未体现
- 前端权限树与后端权限体系是否完全对齐，当前代码中未发现自动同步机制
- 角色删除后是否会影响现有用户绑定，当前页面代码中未显示联动提醒
- 页面中文文案终端乱码，建议在编辑器内复核展示内容
