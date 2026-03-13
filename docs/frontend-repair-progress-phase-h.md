# 前后端联动修复进展（阶段 H）

## 本轮目标

- 准确率/合格率报表真实统计化

## 已完成内容

### 1. 后端新增准确率统计接口

- 在报表路由中新增 `GET /report/accuracy-statistics`
- 同时兼容 `/api/v1/report/accuracy-statistics`
- 统计逻辑基于真实功率对比数据：
  - `ActualPower`
  - `ShortlPower`
  - `SupershortlPower`

### 2. 报表口径从“完整率/及时率占位”切换为“准确率/合格率”

- 旧版页面虽然名为“准确率/合格率报表”，实际调用的是 `report/statistics`
- 本轮已切换为新的 `accuracy-statistics`
- 页面顶部数据源标签、统计卡片、表格列和导出字段都已改为准确率/合格率口径

### 3. 质量标记正式进入报表统计视图

- 后端会统计当月 `exclude_from_score = true` 的质量标记重叠时长
- 前端在表格中展示“免考时长(小时)”
- 若存在免考时段，会写入备注字段，便于审计和核验

## 影响文件

- `backend/routes/report_management_router.py`
- `frontend/src/api/reportApi.js`
- `frontend/src/components/AccuracyReport.vue`

## 当前统计规则说明

- 短期准确率、超短期准确率：
  - 由 RMSE 与场站装机容量换算得出
  - 公式沿用此前功率对比页的前端规则
- 合格率：
  - 仍沿用现有规则
  - 即 `rmse / capacity <= 0.2` 记为 100，否则记为 0
- 综合准确率、综合合格率：
  - 为短期与超短期两个口径的均值

## 当前仍需后续优化的点

- 统计规则目前仍然沿用历史前端公式，若业务希望调整准确率/合格率定义，需再和后端统一标准
- 免考时段目前只作为统计展示字段，尚未反向剔除 RMSE 计算样本
- 页面当前按月汇总到场站，不提供日级拆分和趋势视图

## 下一步建议

- 告警中心真正业务化
- 人工修正版本化与历史追踪
- 准确率报表继续细化到日级/类型级统计
