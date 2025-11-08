## 前端重构总体目标

- **支持生产级多任务场景**：页面切换不丢状态，长任务可后台运行并可随时查看进度。
- **建立清晰分层与模块边界**：界面、业务逻辑、数据访问分离，按业务域拆分目录，降低耦合。
- **提升可维护性与扩展性**：组件体量可控、代码复用度高，配套文档与约定完整。
- **连通后端任务化改造**：前端具备统一的任务面板、状态订阅与通知机制，为后端异步化铺路。

## 目标架构概览

- `src/app-shell/`：全局布局、导航、任务中心、守卫逻辑。
- `src/views/`：页面级容器组件（每个业务模块一个目录）。
- `src/modules/`：按业务域划分的逻辑层（预测、训练、自动化、报告、系统管理等），内含 `api/`、`stores/`、`services/`、`components/`。
- `src/components/common/`：跨域复用的基础组件。
- `src/composables/`：跨域的组合式逻辑（如轮询、表单状态、对话框）。
- `src/stores/`：全局状态（会话、场站、任务中心、UI 设置等）+ 领域 store 注册入口。
- `src/router/`：按域分段管理路由配置，提供 keep-alive、标签栏、权限控制。

```
src/
  app-shell/
    AppShell.vue          # 顶层布局（替换 AppLayout）
    SideNav.vue
    TopBar.vue
    TaskCenterDrawer.vue
    useNavigationGuards.js
  views/
    forecasting/          # 功率预测
      ForecastingIndex.vue    # 页面容器
      components/
        ForecastUploader.vue
        ForecastRunPanel.vue
        ForecastResultViewer.vue
      composables/
        useForecastRun.js
    model-training/
      ModelTrainingIndex.vue
      components/
        TrainingStepper.vue
        TrainingDatasetCard.vue
        TrainingTaskSummary.vue
      composables/
        useTrainingWizard.js
    autopredict/
      ...
  modules/
    forecasting/
      api/
        forecastingApi.ts
      services/
        forecastingService.ts
      stores/
        useForecastingStore.ts
    training/
    reporting/
    maintenance/
  stores/
    index.ts               # 统一导出 createPinia 与模块注册
    useSessionStore.ts
    useWindFarmStore.ts    # 迁移自当前 windFarm.js
    useTaskCenterStore.ts
  router/
    index.ts
    modules/
      forecasting.ts
      training.ts
      autopredict.ts
  utils/
    navigation.ts
    request.ts
```

> **说明**：目录示例采用 TypeScript 命名，若继续使用 JavaScript 可保持 `.js`。核心在于按“视图容器（views）+ 业务模块逻辑（modules）+ 全局设施（app-shell/stores/router）”三层划分。

## 导航与路由策略

1. **多标签 / keep-alive**
   - `AppShell` 中新增标签栏（基于 `router-view` 的导航标签），核心路由使用 `defineAsyncComponent` + `keep-alive` 保持状态。
   - 通过 `meta.keepAlive`、`meta.tabLabel` 控制缓存与标签名称。示例：
     ```js
     {
       path: 'model-training',
       name: 'ModelTraining',
       component: () => import('@/views/model-training/ModelTrainingIndex.vue'),
       meta: { keepAlive: true, tabLabel: '模型训练', permissions: ['train_models'] }
     }
     ```
   - 利用 `Suspense` + 骨架屏优化大型页面首载体验。

2. **权限导航**
   - 将权限判断移至导航配置（store + composable），侧边栏/标签栏共享同一份菜单源，减少重复校验。

3. **全局守卫**
   - `router.beforeEach`：校验登录、权限、初始化核心数据（场站列表、任务列表）。
   - `router.afterEach`：记录最近访问页面到会话 store，供标签栏恢复。

4. **快捷入口**
   - 首页展示核心模块卡片，使用统一的 `navigateToModule` 工具，确保 URL、状态同步。

## 状态管理方案

- 引入 **Pinia** 作为统一 store。
- Store 分类：
  - `useSessionStore`：用户信息、权限、令牌、当前标签。
  - `useWindFarmStore`：迁移并扩展现有场站逻辑（增加服务端缓存、错误状态、刷新策略）。
  - `useTaskCenterStore`：管理长任务列表（训练、预测、自动预测、上报等），支持推送、轮询、手动刷新。
  - 领域 store（如 `useTrainingStore`, `useForecastingStore`）：保持当前页面的查询条件、已上传文件、运行结果等。
- Store 规范：
  - 状态分为 `state`（原始数据）、`derived`（computed getters）、`actions`。
  - 明确持久化策略：会话级（`sessionStorage`）、长期（`localStorage`）、仅内存。
  - 引入 `pinia-plugin-persistedstate` 管理持久化字段。

### 任务中心设计

- `useTaskCenterStore` 结构示例：
  ```ts
  interface TaskItem {
    id: string;
    type: 'training' | 'forecasting' | 'autopredict' | 'reporting';
    title: string;
    status: 'pending' | 'running' | 'success' | 'failed';
    progress?: number;
    startedAt: string;
    finishedAt?: string;
    payload?: Record<string, any>;
    messages: Array<{ timestamp: string; level: 'info' | 'warn' | 'error'; text: string }>;
  }
  ```
- 数据来源：
  - 后端异步任务接口（待后端改造时提供统一 `/tasks` API`）。
  - 临时：保留现有同步调用，但前端将结果注册为任务，允许用户在其他页面查看历史记录。
- 展现：顶部导航提供任务图标，点击打开 `TaskCenterDrawer`，展示任务列表、详情、重试入口。

## 组件与逻辑拆分原则

- **容器组件 (`views/*Index.vue`)**：
  - 负责接入 store、调用 services、组合子组件。
  - 控制布局、路由参数、权限检查。

- **展示组件 (`components/`)**：
  - 只接收 Props、发出事件，不直接调用 API。
  - 体量控制 < 200 行，复杂逻辑放入 composable。

- **Composables (`composables/`)**：
  - 处理可复用逻辑：上传流程、表格分页、轮询、表单验证。
  - 命名 `useXxx`，明确输入输出（state、methods、lifecycle）。

- **Services (`modules/*/services/`)**：
  - 封装领域操作（如训练启动、模型列表、预测执行）。
  - 统一使用 `apiService` 或 `axiosInstance`，返回 Promise。

- **API 层 (`modules/*/api/`)**：
  - 定义和后端接口的直接交互，描述请求/响应结构。
  - 便于后续引入 TypeScript 或 OpenAPI 自动生成。

## 渐进式改造步骤

### 阶段 1：基础设施搭建（Sprint 1）
1. 引入 Pinia，创建 `stores/index.ts`、`useSessionStore`、迁移 `useWindFarmStore`。
2. 新建 `app-shell/AppShell.vue`，将原 `AppLayout` 拆分为 SideNav、TopBar 等组件。
3. 重构路由结构：`router/modules/*.js`，添加 `meta.keepAlive`、`tabLabel`、`permissions`。
4. 实现 `keep-alive` + 标签栏基础版本（使用 `router-view v-slot` + `KeepAlive`）。
5. 建立任务中心 store 与 UI 雏形（先记录同步任务结果）。

### 阶段 2：核心页面迁移（Sprint 2-3）
1. **模型训练（ModelTrain）**：
   - 拆分为容器 `ModelTrainingIndex` + `TrainingStepper` + `TrainingDatasetCard` 等。
   - 使用 Pinia store 存储上传文件、参数、进度，页面卸载不丢失。
   - 整合任务中心，训练启动后任务可后台查看。
2. **功率预测（PowerPredict）**：
   - 相同拆分思路，保留上传状态、预测结果。
   - 提供“再次查看上次结果”入口。
3. **自动预测（AutoPredict） / **上报管理（ReportManagement）**：
   - 将模块特有的列表、开关、日志接口拆到 `modules/autopredict` / `modules/reporting`。
   - 增加策略编辑弹窗与表格过滤的状态持久化。

### 阶段 3：体验优化与共性抽象（Sprint 4+）
1. 完成剩余页面迁移（PowerCompare、PhysicalSimulation、系统维护、用户管理等）。
2. 引入统一的 `FormDialog`、`DataTable`、`UploadCard` 等视觉组件。
3. 建立通用的轮询/订阅机制（配合后端任务订阅接口）。
4. 整合通知系统（任务完成通知、错误提示）。
5. 补全文档：《前端开发规范》《组件/模块目录说明》《任务中心接入指南》。

## 与后端的配合点

- 约定任务 API：
  - `GET /tasks?type=training&status=running`：分页查询任务。
  - `GET /tasks/{id}`：任务详情，包括日志、产物链接。
  - `POST /tasks/{id}/cancel`：取消运行中任务。
  - 长任务启动接口需返回 `task_id`，供前端注册。

- 事件推送（后续）：引入 WebSocket 或 SSE 推送任务状态，前端 `useTaskCenterStore` 监听并更新。

- 文件/模型列表接口：改造为可按场站、任务、时间筛选，方便前端持久化筛选条件。

## 验收与测试策略

- **组件级测试**：采用 Vitest + Testing Library 做关键组件单测（上传卡、步骤导航、任务中心）。
- **端到端测试**：使用 Playwright/ Cypress 脚本验证“训练任务启动 → 跳转页面 → 返回任务仍在进行”。
- **性能监测**：首屏加载 < 3s，主要页面懒加载；`bundle analyzer` 控制包体积。
- **可观察性**：为任务中心、关键 API 增加日志和错误上报，便于排查。

## 近期行动项

1. 完成 Pinia 引入与 AppShell 基础改造（包含 keep-alive、标签栏、任务中心占位）。
2. 选择 `ModelTrain` 作为示例页面进行拆分，沉淀模板与组件规范。
3. 根据拆分经验，扩展到 `PowerPredict`、`AutoPredict`，同步完善 store、composables。
4. 输出《组件拆分指南》《任务中心对接指南》，确保团队成员可以按规范输出新模块。


