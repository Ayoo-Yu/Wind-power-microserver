# 前端修复进展 Phase D

## 本轮目标

- 修复【系统基础配置】完全不可保存的问题。
- 修复【操作日志审计】在来源区分、容错与导出方面的不足。

## 已完成修复

### 1. 系统基础配置改为本地持久化

文件：
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\SystemSettings.vue`
- `D:\my-vue-project\wind-power-forecast\frontend\src\utils\systemSettingsStore.js`

修复内容：
- 新增 `systemSettingsStore`，提供：
  - `getDefaultSystemSettings()`
  - `readSystemSettings()`
  - `saveSystemSettings()`
- 页面初始化时从本地存储回填：
  - 节假日配置
  - 字典配置
  - 保留策略
- “保存配置”按钮已真正可用，点击后写入 `localStorage`。
- 新增“恢复默认”能力，支持确认后还原默认配置。
- 节假日列表支持新增和删除，并立即持久化。
- 页面顶部明确标注：当前代码中未发现系统基础配置后端接口，本页仍为本地持久化过渡方案。

说明：
- 这次修复的目标不是虚构一个后端接口，而是把页面从“改了即丢”的状态修到“最少可保存、可回显、可恢复默认”的可用态。

### 2. 操作日志审计增强

文件：
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\AuditLog.vue`

修复内容：
- 保留并继续使用：
  - 本地日志源 `listAuditLogs()`
  - 远端日志源 `getSystemLogs()`
- 新增日志来源字段：
  - `local`
  - `remote`
- 页面增加来源筛选器，可按本地审计 / 系统日志筛选。
- 操作人筛选由“完全匹配”改为“模糊匹配”。
- 拉取远端系统日志失败时，页面会明确提示“已降级为仅展示本地审计日志”。
- 合并日志后按时间倒序排序。
- 新增 CSV 导出能力。
- 统一标准化远端系统日志结构，兼容字符串日志与对象日志。

说明：
- 这次修复后，审计页已经更接近真正的“审计汇总页”，虽然筛选仍然主要在前端完成，但至少数据来源、降级行为和导出链路都更清晰了。

## 本轮未解决项

- 系统基础配置后端保存接口代码中仍未发现，所以当前仍是本地持久化，不是服务端配置中心。
- 审计日志页仍然没有远端分页、服务端过滤、服务端排序能力。
- 本地审计日志仍然来自前端页面自行写入，未和后端统一审计中心打通。

## 验证记录

执行命令：

```powershell
npm.cmd run lint -- src/components/SystemSettings.vue src/components/AuditLog.vue src/utils/systemSettingsStore.js
```

验证结果：
- `No lint errors found`

## 涉及文件

- `D:\my-vue-project\wind-power-forecast\frontend\src\components\SystemSettings.vue`
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\AuditLog.vue`
- `D:\my-vue-project\wind-power-forecast\frontend\src\utils\systemSettingsStore.js`
- `D:\my-vue-project\docs\frontend-repair-progress-phase-d.md`

## 下一步建议

- 开始统一梳理前端还在使用 `localStorage` 过渡存储的模块，形成“去本地化改造清单”。
- 进一步推进页面口径统一，特别是：
  - 准确率 / 完整率 / 及时率 的业务定义
  - 告警 / 日志 / 质量标记 的边界划分
  - 前端本地审计与后端系统日志的归档策略
