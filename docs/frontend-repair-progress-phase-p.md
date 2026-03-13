# 前后端联动修复进展 - Phase P

## 本轮目标

收口上一个剩余清单里的两个页面治理项：

- 人工修正工作台补齐版本比对 / 回滚能力
- 功率可视化对比补齐页面 query 联动

## 已完成内容

### 1. 人工修正工作台补齐版本比对与回滚

涉及文件：
- [frontend/src/components/ManualInterventionWorkspace.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/ManualInterventionWorkspace.vue)
- [frontend/src/api/reportApi.js](D:/my-vue-project/wind-power-forecast/frontend/src/api/reportApi.js)

新增能力：
- 版本列表支持 `Compare`
- 版本列表支持 `Rollback`
- 页面新增版本对比区
- 对比区展示：
  - 对比版本名称
  - 变更点数
  - 最大偏差
  - 平均偏差
  - 逐点差异表

实现方式：
- 前端调用已有的 `getManualInterventionVersion(versionId)` 拉取目标版本
- 用当前工作区点位和目标版本点位做前端逐点 diff
- 回滚复用已有 `applyManualInterventionVersion(versionId)` 能力

结果：
- 人工修正不再只有“保存版本”和“应用版本”
- 用户现在可以先比较，再决定是否回滚到指定版本

### 2. 功率可视化对比补齐 query 联动

涉及文件：
- [frontend/src/components/PowerCompare.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/PowerCompare.vue)
- 上游跳转来源：[frontend/src/components/AutoPredict.vue](D:/my-vue-project/wind-power-forecast/frontend/src/components/AutoPredict.vue)

新增能力：
- 页面初始化时读取路由 query
- 支持消费：
  - `mode`
  - `farm_code`
  - `farm_codes`
  - `start`
  - `end`
  - `prediction_type`
  - `view`
- 页面状态变化时自动回写 query

效果：
- 从状态监控跳转到功率对比后，场站上下文不再丢失
- 单站 / 多站模式、时间范围、曲线 / 散点视图能在 URL 上保留
- 页面刷新后可以恢复主要筛选状态

## 当前计划状态

到 Phase P 为止，上一版剩余清单里的代码级闭环项已经全部补齐：

- 审计日志后端分页 / 过滤 / 排序
- 告警规则与通知策略配置化
- 人工修正版本比对 / 回滚
- 页面 query 联动统一中的关键缺口

仍可能继续演进的内容：
- 文案层面的统一口径优化
- 更复杂的告警规则引擎
- 更细的人工修正版本差异可视化

这三项更偏持续优化，不再属于当前计划里的核心“未完成闭环”。

## 验证结果

### 前端

执行：

```bash
npm.cmd run lint -- src/components/AlarmCenter.vue src/api/systemApi.js src/components/ManualInterventionWorkspace.vue src/components/PowerCompare.vue
```

结果：
- 通过，无 lint 报错

### 后端

执行：

```bash
python -m py_compile backend/db_models/alarm.py backend/routes/alarm_router.py backend/db_models/__init__.py
```

结果：
- 通过，无语法错误
