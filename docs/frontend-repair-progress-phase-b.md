# 前端修复进展 Phase B

## 本轮目标

- 将【准确率/合格率报表】从静态占位页改为真实接口驱动页面。
- 将【人工修正工作台】从纯 mock 页面改为可加载真实上报配置、真实预览数据并调用手工上报接口的简化闭环页面。

## 已完成修复

### 1. 准确率/合格率报表接入真实统计数据

文件：
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\AccuracyReport.vue`

修复内容：
- 接入 `getReportFarms()` 动态加载场站下拉。
- 接入 `getReportStatistics()` 加载今日/本月质量统计和日明细。
- 移除本地静态 `rows` 假数据。
- 新增顶部 4 张统计卡片：
  - 今日完整率
  - 今日及时率
  - 本月完整率
  - 本月及时率
- 表格改为展示真实后端字段：
  - 场站
  - 日期
  - 日完整率
  - 日及时率
  - 各报文类型明细
  - 备注
- 新增导出报表能力，导出为本地 CSV 文件。
- 新增接口失败告警区和空表降级逻辑。

说明：
- 当前页面名称仍然是“准确率/合格率报表”，但实际后端已落地字段是“完整率/及时率”。本轮修复选择优先接入真实数据，而不是继续保留不真实的准确率假表。

### 2. 人工修正工作台接入真实预览与手工上报链路

文件：
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\ManualInterventionWorkspace.vue`

修复内容：
- 接入 `getReportFarms()` 动态加载场站。
- 接入 `getReportConfigs()` 动态加载指定场站的上报配置。
- 新增报文类型筛选，当前支持：
  - `forecast_long`
  - `forecast_short`
  - `actual`
- 接入 `previewReport(configId)` 加载真实预览数据。
- 将预览报文归一化为可编辑曲线点，支持：
  - 原始值对比线
  - 修正后曲线
  - 限高线
- 接入 `manualReport(payload)` 保存并提交人工修正结果。
- 新增可编辑点明细表，支持逐点调整数值。
- 支持消费路由 query 中的 `farm_code` 和 `report_type` 作为初始化上下文。
- 保留并改造原有修正工具：
  - 按比例调整
  - 整体平移
  - 限制上限

说明：
- 这次不是把页面做成完整的 `ReportManagement` 翻版，而是建立一个“可独立使用的轻量修正闭环”。
- `forecast_short` 的后端结构不是时间序列，而是单行 `wp_pred2 ~ wp_pred17`。本轮已做归一化显示和回写。

## 本轮未解决项

- “准确率/合格率”页面目前展示的是后端已提供的“完整率/及时率”，真正的预测准确率和合格率统计接口代码中仍未发现。
- 人工修正页目前仍依赖已有上报配置，代码中未发现专门的“人工修正版本管理/历史版本列表/审批流”接口。
- 人工修正页当前仍是单页轻量工具，不包含拖拽曲线编辑、批量区间编辑、版本对比等高级能力。

## 验证记录

执行命令：

```powershell
npm.cmd run lint -- src/components/AccuracyReport.vue src/components/ManualInterventionWorkspace.vue
```

验证结果：
- `No lint errors found`

## 涉及文件

- `D:\my-vue-project\wind-power-forecast\frontend\src\components\AccuracyReport.vue`
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\ManualInterventionWorkspace.vue`
- `D:\my-vue-project\docs\frontend-repair-progress-phase-b.md`

## 下一步建议

- 继续修复【统一告警中心】和【数据质量与限电标记】这类原型页，优先把静态数据替换为真实接口或明确的后端缺口提示。
- 梳理“准确率/合格率”真实业务口径，与【功率可视化对比】和后端统计模型统一。
- 评估是否将【人工修正工作台】进一步与【状态监控】、【上报配置与调度】打通为同一条人工干预流程。
