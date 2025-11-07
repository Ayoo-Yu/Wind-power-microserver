# 风电场可视化管理页 - 需求梳理

## 目标

- 为运维/管理人员提供单一入口，集中查看与管理系统内所有风电场。
- 将风电场基础信息、运行状态、数据准备度、模型覆盖等指标在一个页面可视化呈现。
- 提供快捷操作（如跳转至上传、调度、报表、仿真等子模块），减少跨页面切换。
- 与现有 `windFarmStore`、`/report/farms` 接口等数据源保持一致，避免重复实现。

## 信息模块草案

1. **概览总览 (Summary Cards)**
   - 场站总数、在线场站、离线/停运场站数量。
   - 累计装机容量、当日预测任务、数据上传次数等关键 KPI（依赖后端接口支持）。

2. **风电场列表 (Table / Data Grid)**
   - 字段：`farm_name`、`farm_code`、`capacity`、`region`、`is_active`、`latest_upload_at`、`model_count` 等。
   - 支持搜索/筛选/排序，可跳转对应详情页面。

3. **地理分布 (Map / Scatter)**
   - 基于经纬度显示风电场位置，可用 ECharts / Mapbox / 高德 JS。
   - Hover 时展示场站名称与关键指标。

4. **数据准备度面板**
   - 展示各风电场数据上传覆盖率（训练集、预测集、仿真数据等）。
   - 可视化形式：进度条、雷达图或柱状图。

5. **快捷操作区**
   - 按场站触发的按钮：跳转上传 CSV、查看报表配置、打开仿真页面、执行调度任务等。
   - 可结合 `router.push` + 预选场站参数，实现一键跳转。

## 前端任务分解

1. **路由与结构**
   - 在 `src/router` 中新增路由 `/windfarms/overview`（或 `/windfarm-management`）。
   - 新建组件目录：`src/views/WindFarmManagement/`（或 `src/pages` 视项目结构决定）。
   - 页面基于 `AppLayout`，使用 `useWindFarmStore` 获取全量场站数据。

2. **数据层**
   - 复用 `/report/farms` 接口获取基础信息。
   - 若需额外指标（如模型数、任务数、最新上传时间），评估后端是否已有接口：
     - 模型/训练：`/jobs`、`/modeltrain` 相关 API；
     - 数据上传：`/operational/api/operational_tables` 等。
   - 若后端暂缺统一接口，先在前端仅展示现有字段，并预留扩展位。

3. **可视化与组件**
   - 表格：Element Plus `el-table`，支持分页、筛选。
   - 地图：首版可使用 ECharts 地图或 Plotly Scatter Mapbox；如暂时缺经纬度，可置灰。
   - KPI 卡片：自定义卡片组件或 Element Plus `el-card`。

4. **交互**
   - 支持选择某一场站后触发：设置全局场站、跳转详情、展开更多信息。
   - 可考虑在页面中提供“设为默认场站”操作，调用 `setSelectedWindFarm`。

5. **导航集成**
   - 在 `AppLayout` 的菜单中添加入口。
   - 与现有 `windFarmStore` 配合，保证切换时各页面同步更新。

## 后续步骤

1. 验证 `/report/farms` 响应结构，确认可用字段。
2. 评估是否需要新增后端接口；若是，整理数据需求交付后端。
3. 完成路由与页面骨架，实现表格 + KPI 卡片首版。
4. 迭代添加地图、可视化模块。
5. 更新文档与用户指南。


