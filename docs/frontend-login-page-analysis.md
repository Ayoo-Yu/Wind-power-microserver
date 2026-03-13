# 登录页代码级完整拆解

## 1. 页面概览

### 1.1 基础信息

| 字段 | 内容 |
|---|---|
| 页面名称 | 登录页 |
| 所属模块 | 认证模块 |
| 路由路径 | `/login` |
| 页面入口文件 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\Login.vue` |
| 页面依赖的子组件列表 | 代码中未发现自定义子组件；仅使用 Element Plus 内置组件 `el-form`、`el-input`、`el-button`、`el-dialog`、`el-icon` |
| 页面依赖的 store/hooks/model/service/api 文件 | `src/api/auth.js`、`src/store/authReady.js`、`src/router/index.js`、`src/api/axios.js` |
| 页面是否受权限控制 | 不受菜单权限控制；路由元信息为 `meta.requiresAuth = false`。但受全局路由守卫控制，已登录用户访问 `/login` 时会被重定向到首页 |

### 1.2 页面定位

该页面是系统唯一已识别的认证入口页，负责以下闭环：

1. 采集用户名、密码、验证码。
2. 在前端执行表单校验、验证码校验和失败锁定策略。
3. 调用认证接口完成登录。
4. 将登录成功结果写入本地存储：
   - `localStorage.user`
   - `localStorage.accessToken`
5. 更新全局认证状态：
   - `isAuthReady`
   - `isAuthLoading`
6. 登录成功后跳转 `/`。
7. 支持“修改密码”弹窗及提交。

### 1.3 页面复杂度评估

- 复杂度：中
- 原因：
  - UI 结构不复杂，但认证链路完整
  - 有本地锁定策略、验证码、定时器、本地存储、路由跳转、全局认证状态联动
  - 存在与 `axios` 401 拦截器、路由守卫、认证接口的跨文件交互

---

## 2. 页面结构树

```text
Login.vue
├─ login-shell
│  ├─ login-visual
│  │  ├─ 背景纹理层
│  │  │  ├─ texture-grid
│  │  │  ├─ texture-lines
│  │  │  ├─ particle-layer
│  │  │  ├─ turbine-watermark
│  │  │  └─ wind-scene
│  │  └─ visual-overlay
│  │     ├─ 标题与说明文案
│  │     ├─ visual-metrics 指标列表
│  │     │  ├─ 场站数指标
│  │     │  ├─ 总功率指标
│  │     │  └─ 准确率指标
│  │     └─ announcement-ticker 系统公告滚动条
│  ├─ login-panel
│  │  └─ login-card
│  │     ├─ logo-line 品牌头部
│  │     ├─ security-alert 锁定提示
│  │     ├─ login-form 登录表单
│  │     │  ├─ username 输入框
│  │     │  ├─ password 输入框
│  │     │  ├─ captchaInput 输入框
│  │     │  ├─ captcha-challenge 验证码按钮
│  │     │  └─ login-button 登录按钮
│  │     ├─ form-meta
│  │     │  ├─ rememberMe 复选框
│  │     │  └─ helper-link 帮助链接
│  │     ├─ footer 页脚说明
│  │     └─ version 版本号
│  └─ change-password dialog
│     ├─ passwordForm
│     │  ├─ newPassword 输入框
│     │  └─ confirmPassword 输入框
│     └─ 提交按钮
```

---

## 3. 区块说明

### 3.1 左侧视觉展示区

| 字段 | 内容 |
|---|---|
| 区块名称 | 左侧视觉展示区 |
| 对应组件名 | `LoginView` 内部模板区块 |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\Login.vue` |
| 展示内容 | 大标题、说明文案、3 个指标卡、系统公告滚动条、多个纯装饰背景层 |
| 数据来源 | `maskedMetrics`、`systemNotice`，均为页面本地 state |
| 是否可交互 | 基本不可交互；仅公告为自动滚动动画，指标不响应点击 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 公告滚动依赖纯 CSS 动画；指标数据无自动刷新；无接口拉取 |

说明：
- `maskedMetrics` 初始值固定为 `'----'`，代码中未发现接口填充逻辑。
- `systemNotice` 为页面本地固定文案。
- 该区块主要承担品牌与氛围展示，不参与认证闭环。

### 3.2 登录卡片区

| 字段 | 内容 |
|---|---|
| 区块名称 | 登录卡片区 |
| 对应组件名 | `LoginView` 内部模板区块 |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\Login.vue` |
| 展示内容 | Logo、锁定提示、登录表单、记住登录复选框、帮助链接、页脚、版本号 |
| 数据来源 | `formData`、`rememberMe`、`lockoutMessage`、`loading` |
| 是否可交互 | 是 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 有。锁定提示依赖 `nowTs` 每秒刷新 |

说明：
- 登录卡片是页面的核心业务区。
- `lockoutMessage` 只有在 `isLocked === true` 时显示。
- `rememberMe` 虽然有 UI 和状态，但代码中未发现被登录逻辑消费。

### 3.3 登录表单区

| 字段 | 内容 |
|---|---|
| 区块名称 | 登录表单区 |
| 对应组件名 | `el-form` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\Login.vue` |
| 展示内容 | 用户名、密码、验证码、登录按钮 |
| 数据来源 | `formData`、`loginRules`、`captchaText`、`loading`、`isLocked` |
| 是否可交互 | 是 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 间接有，验证码可手动刷新；锁定状态每秒变化 |

说明：
- 用户名、密码、验证码都使用 Element Plus 表单校验。
- 密码框和验证码框支持回车触发 `handleLogin`。
- 验证码按钮点击调用 `refreshCaptcha()`。
- 验证码输入框和登录按钮在锁定期间会被禁用。

### 3.4 修改密码弹窗区

| 字段 | 内容 |
|---|---|
| 区块名称 | 修改密码弹窗 |
| 对应组件名 | `el-dialog` + `passwordForm` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\Login.vue` |
| 展示内容 | 新密码、确认密码、提交按钮 |
| 数据来源 | `showChangePasswordDialog`、`passwordData`、`passwordRules`、`changingPassword` |
| 是否可交互 | 是 |
| 是否有权限控制 | 无 |
| 是否有定时刷新或自动更新 | 无 |

说明：
- 代码中存在完整的修改密码交互逻辑。
- 但当前页面代码中未发现打开该弹窗的按钮或自动触发逻辑。
- 因此该弹窗处于“逻辑已写、入口未发现”的状态。

---

## 4. 组件明细表

> 该页面没有自定义子组件，因此本节以“页面组件 + 内部 Element Plus 组件组”的方式拆解。

### 4.1 页面组件：LoginView

| 字段 | 内容 |
|---|---|
| 组件名称 | `LoginView` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\Login.vue` |
| 父子关系 | 父级为路由页面；无自定义子组件 |
| props / emits / callbacks | 无 props；无 emits；内部回调包括 `handleLogin`、`handleChangePassword`、`refreshCaptcha` |
| 内部 state / computed / store 使用情况 | 使用 `ref`、`reactive`、`computed`、`watch`；使用全局认证状态 `isAuthReady`、`isAuthLoading` |
| 生命周期或副作用逻辑 | `onMounted` 初始化验证码、加载锁定状态、启动 1 秒定时器；`watch(formData.username)` 重新读取锁定状态；`onBeforeUnmount` 清理定时器 |
| 实现的具体功能 | 登录、验证码校验、失败锁定、修改密码、本地存储写入、跳转 |
| 触发了哪些接口 | `login()`、`changePassword()` |
| 与其他组件的联动关系 | 与路由守卫、`axios` 拦截器、认证状态 store、本地存储联动 |
| 加载态 / 空态 / 异常态如何处理 | 登录按钮加载态 `loading`；改密按钮加载态 `changingPassword`；异常通过 `ElMessage.error` 提示；无独立空态 |

#### 4.1.1 内部状态明细

| 状态名 | 类型 | 来源 | 用途 |
|---|---|---|---|
| `formData` | `reactive` | 本地状态 | 登录表单数据 |
| `passwordData` | `reactive` | 本地状态 | 修改密码表单数据 |
| `rememberMe` | `ref` | 本地状态 | “记住登录”勾选状态，代码中未发现实际消费 |
| `loading` | `ref` | 本地状态 | 登录提交加载态 |
| `changingPassword` | `ref` | 本地状态 | 改密提交加载态 |
| `showChangePasswordDialog` | `ref` | 本地状态 | 控制修改密码弹窗显隐 |
| `nowTs` | `ref` | 本地状态 | 锁定倒计时计算基准时间 |
| `timerId` | `ref` | 本地状态 | 定时器 ID |
| `systemNotice` | `ref` | 本地静态文案 | 左侧公告文本 |
| `captchaText` | `ref` | 本地计算生成 | 验证码题面 |
| `captchaAnswer` | `ref` | 本地计算生成 | 验证码正确答案 |
| `lockState` | `reactive` | 本地状态 + localStorage | 登录失败次数与锁定截止时间 |
| `maskedMetrics` | `reactive` | 本地静态数据 | 左侧指标展示占位 |
| `isAuthReady` | `ref` | 全局 store | 认证完成标识 |
| `isAuthLoading` | `ref` | 全局 store | 认证检查加载标识 |

#### 4.1.2 computed 明细

| computed | 作用 | 依赖 |
|---|---|---|
| `isLocked` | 判断当前账号是否处于锁定期 | `lockState.lockedUntil`、`nowTs` |
| `lockoutMessage` | 生成锁定提示文案 | `isLocked`、`lockState.lockedUntil`、`nowTs` |

#### 4.1.3 副作用逻辑

| 逻辑 | 位置 | 说明 |
|---|---|---|
| 初始化验证码 | `onMounted` | 首次进入页面就生成一道加法验证码 |
| 加载锁定状态 | `onMounted` | 根据当前用户名从 `localStorage` 读取锁定信息 |
| 每秒更新时间戳 | `onMounted` + `setInterval` | 用于驱动锁定倒计时 |
| 用户名变化重新读取锁定状态 | `watch(formData.username)` | 不同用户名对应不同锁定记录 |
| 清理定时器 | `onBeforeUnmount` | 避免内存泄漏 |

### 4.2 内部组件组：登录表单

| 字段 | 内容 |
|---|---|
| 组件名称 | `el-form` / `el-form-item` / `el-input` / `el-button` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\Login.vue` |
| 父子关系 | 父级 `LoginView`，无进一步自定义子组件 |
| props / emits / callbacks | 通过 `v-model` 绑定 `formData`；按钮点击触发 `handleLogin`；回车触发 `handleLogin` |
| 内部 state / computed / hooks / store 使用情况 | 依赖父组件状态，不独立持有业务状态 |
| 生命周期或副作用逻辑 | 无独立生命周期 |
| 实现的具体功能 | 采集用户名、密码、验证码；提交登录 |
| 触发了哪些接口 | 通过父组件 `handleLogin` 间接触发 `login()` |
| 与其他组件的联动关系 | 与锁定提示、验证码按钮、路由跳转联动 |
| 加载态 / 空态 / 异常态如何处理 | 登录按钮用 `loading` 展示加载；校验失败和异常通过消息提示 |

### 4.3 内部组件组：修改密码弹窗

| 字段 | 内容 |
|---|---|
| 组件名称 | `el-dialog` / `el-form` / `el-input` / `el-button` |
| 文件路径 | `D:\my-vue-project\wind-power-forecast\frontend\src\components\Login.vue` |
| 父子关系 | 父级 `LoginView` |
| props / emits / callbacks | `v-model="showChangePasswordDialog"`；按钮点击 `handleChangePassword` |
| 内部 state / computed / hooks / store 使用情况 | 依赖父组件中的 `passwordData`、`passwordRules`、`changingPassword` |
| 生命周期或副作用逻辑 | 无独立生命周期 |
| 实现的具体功能 | 校验并提交修改密码 |
| 触发了哪些接口 | `changePassword()` |
| 与其他组件的联动关系 | 改密成功后清理 `localStorage.user`、清空当前密码输入、跳转回 `/login` |
| 加载态 / 空态 / 异常态如何处理 | 提交按钮 `changingPassword`；失败消息提示；无空态 |

---

## 5. 交互明细表

### 5.1 可见元素清单

| 元素类型 | 位置 | 文案/标识 | 功能 | 点击/变更后的行为 | 是否依赖权限 | 是否触发接口 | 是否影响其他组件 |
|---|---|---|---|---|---|---|---|
| 标题 | 左侧视觉区 | 页面主标题 | 品牌展示 | 无 | 否 | 否 | 否 |
| 指标卡 1 | 左侧视觉区 | 场站数 | 展示占位指标 | 无 | 否 | 否 | 否 |
| 指标卡 2 | 左侧视觉区 | 总功率 | 展示占位指标 | 无 | 否 | 否 | 否 |
| 指标卡 3 | 左侧视觉区 | 准确率 | 展示占位指标 | 无 | 否 | 否 | 否 |
| 公告滚动条 | 左侧视觉区 | 系统公告 | 展示公告 | CSS 自动滚动 | 否 | 否 | 否 |
| 用户名输入框 | 登录表单 | 用户名 placeholder | 录入用户名 | 更新 `formData.username`，触发 `watch` 重新加载锁定状态 | 否 | 否 | 影响锁定提示、登录逻辑 |
| 密码输入框 | 登录表单 | 密码 placeholder | 录入密码 | 更新 `formData.password`；回车触发登录 | 否 | 否 | 影响登录逻辑 |
| 验证码输入框 | 登录表单 | 验证码 placeholder | 输入验证码答案 | 更新 `formData.captchaInput`；回车触发登录 | 否 | 否 | 影响登录逻辑 |
| 验证码按钮 | 登录表单 | `captchaText` | 刷新验证码 | 调用 `refreshCaptcha()` 重新生成题面与答案，并清空输入 | 否 | 否 | 影响验证码校验 |
| 登录按钮 | 登录表单 | 登录 | 提交登录 | 调用 `handleLogin()` | 否 | 是 | 影响全局认证状态、路由、本地存储 |
| 记住登录复选框 | 登录卡片底部 | 记住登录 | 勾选偏好 | 仅更新 `rememberMe` | 否 | 否 | 代码中未发现后续联动 |
| 帮助链接 | 登录卡片底部 | 帮助文案 | 占位链接 | `@click.prevent` 阻止默认行为，无后续逻辑 | 否 | 否 | 否 |
| 锁定提示条 | 登录卡片顶部 | `lockoutMessage` | 展示锁定剩余时间 | 随 `nowTs` 每秒变化 | 否 | 否 | 影响用户可操作性判断 |
| 改密弹窗新密码输入框 | 改密弹窗 | 新密码 | 输入新密码 | 更新 `passwordData.newPassword` | 否 | 否 | 影响改密校验 |
| 改密弹窗确认密码输入框 | 改密弹窗 | 确认密码 | 输入确认密码 | 更新 `passwordData.confirmPassword` | 否 | 否 | 影响改密校验 |
| 改密弹窗提交按钮 | 改密弹窗 | 提交/保存 | 提交改密 | 调用 `handleChangePassword()` | 否 | 是 | 影响本地存储、路由 |

### 5.2 关键交互流程

#### A. 正常登录

1. 用户输入用户名、密码、验证码。
2. 点击“登录”或在密码框/验证码框按回车。
3. 页面执行 `loginForm.validate()`。
4. 前端比对 `captchaInput` 与 `captchaAnswer`。
5. 通过后设置：
   - `loading = true`
   - `isAuthReady = false`
   - `isAuthLoading = true`
6. 清理旧登录态：
   - 删除 `localStorage.user`
   - 删除 `localStorage.accessToken`
7. 调用 `login(username, password)`。
8. 成功后：
   - `localStorage.user = JSON.stringify(userData.user)`
   - 若返回 `access_token`，写入 `localStorage.accessToken`
   - 清除锁定状态
   - `ElMessage.success`
   - `router.push('/')`
9. finally 中结束 `loading`。

#### B. 登录失败

1. 若接口报错，执行 `recordFailAndMaybeLock()`。
2. 重新生成验证码 `refreshCaptcha()`。
3. 提示错误消息，优先显示后端 `error.response?.data?.message`。
4. 设置：
   - `isAuthReady = false`
   - `isAuthLoading = false`
5. 若累计失败达到 5 次，则锁定 15 分钟。

#### C. 锁定中的登录尝试

1. 先执行 `loadLockState()`。
2. 若 `isLocked === true`：
   - 直接提示 `lockoutMessage`
   - 不触发表单校验
   - 不触发接口

#### D. 验证码错误

1. 表单校验通过后，先比对验证码答案。
2. 若错误：
   - `ElMessage.error`
   - 重新生成验证码
   - 不调用登录接口

#### E. 修改密码

1. 只有 `showChangePasswordDialog = true` 时弹窗可见。
2. 点击弹窗确认按钮后执行 `passwordForm.validate()`。
3. 调用 `changePassword(username, currentPassword, newPassword)`。
4. 成功后：
   - 关闭弹窗
   - `ElMessage.success`
   - 删除 `localStorage.user`
   - 清空 `formData.password`
   - 跳转 `/login`
5. 失败后仅消息提示。

说明：
- 当前代码中未发现打开改密弹窗的触发条件。
- 因此“修改密码”是一个已实现但入口未闭环的功能点。

---

## 6. 接口明细表

### 6.1 登录接口

| 字段 | 内容 |
|---|---|
| 接口名称 | 登录 |
| 请求方法 | `POST` |
| URL | 优先 `/api/v1/auth/login`，fallback `/api/auth/login` |
| 所在 api/service 文件 | `D:\my-vue-project\wind-power-forecast\frontend\src\api\auth.js` |
| 调用函数名 | `login(username, password)` |
| 调用触发条件 | 登录表单校验通过且验证码校验通过后，由 `handleLogin()` 调用 |
| 请求参数 | `{ username, password }` |
| 返回数据结构 | 代码中按 `response.data` 使用；页面已明确消费字段：`userData.user`、`userData.access_token`；其他字段代码中未明确 |
| 返回数据映射到页面哪个组件/哪个字段 | `userData.user` 写入 `localStorage.user`；`userData.access_token` 写入 `localStorage.accessToken`；不直接映射到页面显示字段 |
| 失败时页面怎么处理 | 记录失败次数、可能进入锁定、刷新验证码、消息提示、恢复 `loading`，并将 `isAuthReady`/`isAuthLoading` 置为失败态 |

补充说明：
- `auth.js` 通过 `withLegacyFallback()` 自动在 v1 接口失败且状态为 404/405 或无响应时回退到旧路径。
- 该页面不直接处理 `401`；`axios.js` 会统一处理响应 `401`。

### 6.2 修改密码接口

| 字段 | 内容 |
|---|---|
| 接口名称 | 修改密码 |
| 请求方法 | `POST` |
| URL | 优先 `/api/v1/auth/change-password`，fallback `/api/auth/change-password` |
| 所在 api/service 文件 | `D:\my-vue-project\wind-power-forecast\frontend\src\api\auth.js` |
| 调用函数名 | `changePassword(username, currentPassword, newPassword)` |
| 调用触发条件 | 修改密码弹窗提交且表单校验通过后 |
| 请求参数 | `{ username, current_password, new_password }` |
| 返回数据结构 | 代码中仅使用 `response.data`；页面未消费具体字段 |
| 返回数据映射到页面哪个组件/哪个字段 | 不映射显示字段；成功后仅驱动消息、关闭弹窗、清理部分本地状态和路由跳转 |
| 失败时页面怎么处理 | `ElMessage.error(error.response?.data?.message || 默认文案)`，结束 `changingPassword` |

### 6.3 页面关联但非直接调用的认证接口

| 接口名称 | 请求方法 | URL | 所在文件 | 调用函数名 | 与登录页关系 |
|---|---|---|---|---|---|
| 获取当前用户 | `GET` | `/api/v1/auth/me` 或 `/api/auth/me` | `src/api/auth.js` | `getCurrentUser()` | 登录页不直接调用；登录后由布局页 `AppLayout.vue` 用于校验登录态 |

### 6.4 全局请求封装对登录页的影响

| 项目 | 说明 |
|---|---|
| 请求基地址 | 本地开发默认 `'/'`，非 localhost 时为 `http://{hostname}:8080` |
| 请求头处理 | 若有 `accessToken`，自动添加 `Authorization: Bearer {token}` |
| 401 处理 | 清空 `localStorage.accessToken`、`localStorage.user`，并跳转 `/login` |
| 网络错误处理 | `ElMessage.error` 提示 |

登录页影响说明：
- 登录前通常没有 token，因此 `axios` 会打印“无 token 请求”日志，但不会阻止请求。
- 登录成功后写入的 token 会被后续请求自动附带。

---

## 7. 数据流说明

### 7.1 初始化加载流程

1. 路由进入 `/login`。
2. 全局路由守卫检查：
   - 若 `localStorage.user` 存在，则直接重定向到首页 `/`
   - 若不存在，则允许进入登录页
3. `LoginView` 挂载。
4. `onMounted()` 执行：
   - 调用 `refreshCaptcha()` 生成验证码题目与答案
   - 调用 `loadLockState()` 从 `localStorage.login_security_lock_v1` 读取当前用户名锁定状态
   - 启动每秒定时器，更新 `nowTs`
5. 页面展示初始 UI：
   - 左侧指标仍为 `'----'`
   - 登录表单可编辑

### 7.2 用户操作后的数据变化

#### 用户名变化

- `formData.username` 改变
- `watch(formData.username)` 触发
- 再次调用 `loadLockState()`
- `lockState` 改变
- `isLocked` / `lockoutMessage` 重新计算

#### 点击刷新验证码

- 重新生成两个 1~9 的随机数
- `captchaText` 更新为类似 `3 + 7 = ?`
- `captchaAnswer` 更新为对应答案
- `formData.captchaInput` 被清空

#### 登录成功

- `formData` 不会被显式清空
- `localStorage.user` 和 `localStorage.accessToken` 被更新
- `lockState` 被清空并持久化
- `router.push('/')`

#### 登录失败

- `lockState.failCount` 增加
- 可能新增 `lockState.lockedUntil`
- 失败信息写回 `localStorage.login_security_lock_v1`
- 新验证码重新生成

### 7.3 本地状态 / 全局状态 / 后端数据划分

#### 本地状态

- `formData`
- `passwordData`
- `rememberMe`
- `loading`
- `changingPassword`
- `showChangePasswordDialog`
- `nowTs`
- `captchaText`
- `captchaAnswer`
- `lockState`
- `maskedMetrics`
- `systemNotice`

#### 全局 store 状态

- `isAuthReady`
- `isAuthLoading`

#### 来自后端接口的数据

- 登录返回的 `userData.user`
- 登录返回的 `userData.access_token`
- 修改密码接口的成功/失败结果

### 7.4 二次加工 / 格式化逻辑

| 数据 | 加工逻辑 |
|---|---|
| 验证码文案 | `left + right = ?` 字符串拼装 |
| 锁定提示文案 | 将剩余秒数格式化为 `mm:ss` |
| 用户维度锁定 key | `normalizeUserKey()` 将用户名 trim 后转小写，空值时使用 `__anonymous__` |
| 改密确认校验 | `confirmPassword` 必须严格等于 `newPassword` |

---

## 8. 权限与状态控制说明

### 8.1 权限控制

- 页面本身不受业务权限 key 控制。
- 路由配置中仅标记 `meta.requiresAuth = false`。
- 侧边栏菜单中也不存在该页面。
- 已登录用户访问 `/login` 时，`router.beforeEach` 会重定向到首页。

### 8.2 路由守卫

相关文件：
- `D:\my-vue-project\wind-power-forecast\frontend\src\router\index.js`

守卫逻辑：

1. 读取 `localStorage.user`
2. 计算目标路由是否 `requiresAuth`
3. 分支：
   - 目标页需要认证且无 `user` -> 跳转 `Login`
   - 已有 `user` 且目标页是 `Login` -> 跳转 `HomePage`
   - 其他情况 -> 放行

对登录页的影响：
- 登录页本身不阻止匿名访问
- 但阻止已登录用户重复进入登录页

### 8.3 全局认证状态控制

相关文件：
- `D:\my-vue-project\wind-power-forecast\frontend\src\store\authReady.js`

状态说明：
- `isAuthReady`：认证是否完成
- `isAuthLoading`：认证过程是否处于检查中

登录页使用方式：
- 登录发起前将二者置为“重新认证中”
- 登录失败时恢复为失败态
- 登录成功后本页未显式将 `isAuthReady` 置回 true，代码中未明确由谁在登录成功瞬间完成该赋值

说明：
- 从仓库其他代码看，`AppLayout.vue` 会在加载用户信息成功后设置 `isAuthReady = true`
- 因此实际认证完成闭环落在“登录页写 token -> 进入布局页 -> 布局页拉取当前用户”这一链路上

### 8.4 加载态 / 异常态 / 空态

| 类型 | 实现方式 |
|---|---|
| 登录加载态 | 登录按钮 `:loading="loading"` |
| 改密加载态 | 弹窗确认按钮 `:loading="changingPassword"` |
| 锁定态 | 显示 `security-alert`，并禁用验证码输入框与登录按钮 |
| 表单校验异常 | Element Plus 校验提示 + 不继续执行 |
| 验证码异常 | `ElMessage.error` |
| 接口异常 | `ElMessage.error(error.response?.data?.message || 默认文案)` |
| 空态 | 代码中未设计专门空态 |

---

## 9. 风险点 / 待确认点

### 9.1 代码中已确认的风险点

1. 修改密码弹窗没有可见入口。
   - 代码中存在 `showChangePasswordDialog`、`handleChangePassword` 和完整弹窗
   - 但页面模板中未发现任何按钮或条件逻辑将其设为 `true`

2. `rememberMe` 仅有 UI，没有实际落库或登录策略逻辑。
   - 勾选状态未写入本地存储
   - 登录请求参数也不包含该字段

3. 左侧指标区是静态占位数据。
   - `maskedMetrics` 固定为 `'----'`
   - 代码中未发现接口拉取或刷新逻辑

4. 登录成功后，本页没有显式把 `isAuthReady` 设为 `true`。
   - 当前闭环依赖跳转后布局页二次校验
   - 这属于跨页面认证状态联动

5. 登录锁定策略完全在前端本地实现。
   - 依赖 `localStorage`
   - 可被清缓存绕过
   - 是否还存在后端防暴力破解机制，需结合后端确认

### 9.2 代码中未明确的事项

1. 登录接口返回结构的完整字段定义，代码中未明确。
2. 是否存在“首次登录强制改密”或“密码过期强制改密”场景，代码中未明确。
3. 帮助链接的真实跳转目标，代码中未发现。
4. 左侧系统公告是否应来自接口，代码中未发现。

### 9.3 需结合后端确认

1. `/api/v1/auth/login` 与 `/api/auth/login` 的实际返回 schema。
2. `change-password` 接口的鉴权要求与返回码规范。
3. 后端是否实现登录失败次数限制、验证码校验或账号锁定。
4. `userData.user` 的最小字段集合。

---

## 10. 代码证据清单

### 页面与组件

- `D:\my-vue-project\wind-power-forecast\frontend\src\components\Login.vue`
  - 组件名：`LoginView`
  - 关键函数：`handleLogin`
  - 关键函数：`handleChangePassword`
  - 关键函数：`refreshCaptcha`
  - 关键函数：`loadLockState`
  - 关键函数：`recordFailAndMaybeLock`
  - computed：`isLocked`
  - computed：`lockoutMessage`

### 接口层

- `D:\my-vue-project\wind-power-forecast\frontend\src\api\auth.js`
  - 函数：`login`
  - 函数：`changePassword`
  - 函数：`getCurrentUser`
  - 工具函数：`withLegacyFallback`
  - 工具函数：`authPost`

### 路由与认证控制

- `D:\my-vue-project\wind-power-forecast\frontend\src\router\index.js`
  - 路由：`/login`
  - 守卫：`router.beforeEach`

- `D:\my-vue-project\wind-power-forecast\frontend\src\store\authReady.js`
  - 全局状态：`isAuthReady`
  - 全局状态：`isAuthLoading`

### 请求封装

- `D:\my-vue-project\wind-power-forecast\frontend\src\api\axios.js`
  - 请求拦截器：附加 `Authorization`
  - 响应拦截器：处理 `401`
  - 跳转逻辑：401 时 `router.push('/login')`

---

## 附：隐性逻辑专项检查

| 检查项 | 结论 |
|---|---|
| 轮询 | 代码中未发现 |
| 自动刷新 | 仅锁定倒计时每秒刷新；无后端数据自动刷新 |
| 防抖/节流 | 代码中未发现 |
| 缓存 | 使用 `localStorage` 缓存登录态与锁定状态 |
| URL query 同步 | 代码中未发现 |
| 本地存储 | 使用 `localStorage.user`、`localStorage.accessToken`、`localStorage.login_security_lock_v1` |
| 权限指令 | 代码中未发现 |
| 路由守卫 | 已发现，全局守卫位于 `router/index.js` |
| 条件渲染 | `v-if="lockoutMessage"`、`v-model="showChangePasswordDialog"` |
| mock 数据 | 左侧 `maskedMetrics` 为静态占位数据；`systemNotice` 为静态文案 |
| 假数据兜底 | 锁定状态读取失败时返回 `{}`；指标固定 `'----'` |
| 导出下载 | 代码中未发现 |
| 上传导入 | 代码中未发现 |
| WebSocket/SSE | 代码中未发现 |
| 埋点日志 | 代码中未发现 |
| 错误边界 | 代码中未发现专门错误边界；使用 `ElMessage` 提示 |
