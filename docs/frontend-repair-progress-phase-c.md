# 前端修复进展 Phase C

## 本轮目标

- 修复【统一告警中心】的纯静态告警列表问题。
- 修复【数据质量与限电标记】的纯静态质量卡片与硬编码标记问题。
- 顺带修正上一轮人工修正页面中的按钮权限判断调用错误。

## 已完成修复

### 1. 统一告警中心接入系统日志与实时消息

文件：
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\AlarmCenter.vue`

修复内容：
- 接入 `getSystemLogs()`，页面初始加载和手工刷新时读取系统日志快照。
- 接入 `websocketService`，尝试建立实时连接并订阅当前场站。
- 监听事件：
  - `log:received`
  - `farm:alert:received`
  - `connection:connected`
  - `connection:reconnected`
  - `connection:disconnected`
- 新增连接状态标识：
  - `实时连接已建立`
  - `仅展示日志快照`
- 将日志/实时消息统一归一化为告警表结构：
  - 时间
  - 场站
  - 级别
  - 模块
  - 内容
  - 通知动作
- 保留提示音逻辑，但只对严重告警触发。

说明：
- 当前后端代码里未发现真正稳定的 `farm:alert` 推送链路，已确认最稳定的实时源仍然是 `log` 事件。
- 因此本轮修复属于“系统日志 + 实时日志流”的告警过渡方案，不是完整的告警规则引擎。

### 2. 数据质量与限电标记接入真实质量统计

文件：
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\DataQualityManagement.vue`

修复内容：
- 接入 `getReportFarms()` 动态加载场站。
- 接入 `getReportStatistics()` 加载质量统计。
- 将顶部质量卡片改为基于 `daily_stats` 按场站聚合的真实月完整率/月及时率。
- 新增月份与场站筛选。
- 新增接口失败告警和空卡片降级逻辑。

说明：
- 当前仓库中未发现专门的数据质量接口，所以本轮以“上报质量统计”作为最接近的真实数据源。
- 因此页面现在展示的是“上报完整率/及时率”，不是独立的 SCADA 原始采集质量接口结果。

### 3. 数据质量标记改为可追溯本地存储

文件：
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\DataQualityManagement.vue`
- `D:\my-vue-project\wind-power-forecast\frontend\src\utils\dataQualityStore.js`

修复内容：
- 移除页面内硬编码 `markers` 初始数组。
- 新增 `dataQualityStore`：
  - `listDataQualityMarkers()`
  - `saveDataQualityMarkers()`
  - `appendDataQualityMarker()`
- 新增标记弹窗保存后写入 `localStorage`。
- 表格改为读取本地持久化标记，并支持按当前场站筛选。
- 在页面头部明确标注：这是等待后端接口补齐前的过渡方案。

说明：
- 这比原来的硬编码假数据更可追溯，但依然不是最终态。
- 后续如果后端补齐质量标记接口，需要优先把这部分迁移到服务端持久化。

### 4. 修正人工修正页面权限判断调用

文件：
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\ManualInterventionWorkspace.vue`

修复内容：
- 将 `hasAnyPermission()` 的调用改为传入真实 `user` 对象。
- 避免按钮权限被错误判断为始终不生效或行为异常。

## 本轮未解决项

- 告警中心仍未接到成熟的“告警规则 + 告警确认 + 告警关闭 + 告警通知记录”后端接口。
- 数据质量页仍未接到真正的“异常标记/限电标记”后端持久化接口。
- 数据质量卡片当前复用了上报统计，不代表仓库里已经存在独立的 SCADA/测风质量服务。

## 验证记录

执行命令：

```powershell
npm.cmd run lint -- src/components/AlarmCenter.vue src/components/DataQualityManagement.vue src/components/ManualInterventionWorkspace.vue src/utils/dataQualityStore.js
```

验证结果：
- `No lint errors found`

## 涉及文件

- `D:\my-vue-project\wind-power-forecast\frontend\src\components\AlarmCenter.vue`
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\DataQualityManagement.vue`
- `D:\my-vue-project\wind-power-forecast\frontend\src\components\ManualInterventionWorkspace.vue`
- `D:\my-vue-project\wind-power-forecast\frontend\src\utils\dataQualityStore.js`
- `D:\my-vue-project\docs\frontend-repair-progress-phase-c.md`

## 下一步建议

- 继续修复【系统基础配置】和【操作日志审计】之外的“静态占位能力缺口”，尤其是告警闭环和质量标记后端接口。
- 统一梳理哪些页面仍然依赖 `localStorage` 过渡数据，优先替换为后端持久化。
- 开始处理更深层的一致性问题，例如页面口径不一致、日志/告警/质量定义不统一等。
