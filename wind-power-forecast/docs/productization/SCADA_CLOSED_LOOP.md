# SCADA 数据闭环

## 本分支完成的链路

当前开发环境已经形成一条可观测的数据链路：

```text
C104 仿真器或场站 SCADA
        ↓
生产 scada_worker.py
        ↓
POST /api/v1/scada/ingest
        ↓
连接校验、质量码校验、时钟校验、功率范围校验
        ↓
scada_ingest_records 来源审计
        ↓
actual_power 十五分钟幂等写入
        ↓
预测任务消费状态与实际上报发件箱状态
        ↓
/api/v1/scada/health 与前端运行状态
```

Worker 和后端在同一个请求事务中完成审计记录与实际功率写入。异常质量码、无效数值、过期源时间、超前源时间、场站编码不匹配和超容量功率都会留下拒绝记录，同时不会推进最后有效数据时间。

## 样本处理结果

| 结果 | 含义 | 是否写入实际功率 |
| --- | --- | --- |
| `observed` | 已收到有效实时样本，当前时间策略不要求生成十五分钟值 | 否 |
| `created` | 创建新的十五分钟实际功率记录 | 是 |
| `updated` | 更新同一场站、同一时刻的实际功率 | 是 |
| `duplicate` | 内容完全相同，完成幂等处理 | 不重复写入 |
| `rejected` | 样本未通过质量或数据校验 | 否 |

## 运行健康状态

`GET /api/v1/scada/health` 同时返回采集、预测和上报状态。主要状态如下：

| 状态 | 判断依据 |
| --- | --- |
| `healthy` | Worker 正常，最近有效样本未过期，最近质量结果正常 |
| `degraded` | 最近收到的样本被质量规则拒绝 |
| `stale` | 最后有效样本超过新鲜度阈值 |
| `no_data` | Worker 已运行，尚未收到有效样本 |
| `error` | Worker 报告异常或退出 |
| `disabled` | 当前连接已停用 |

每个场站还会返回：

1. 最后有效样本时间和数据年龄。
2. 最近实际功率值和十五分钟时间戳。
3. 已启用预测任务是否消费了最新实际功率。
4. 实际功率上报配置和最新发件箱状态。

本地测试环境未配置预测任务和实际功率上报时，会显示 `not_configured`。这个状态用于明确当前开发配置的边界。

## 开发验证

日常开发直接运行：

```bat
start-scada-dev.bat
```

启动脚本会启用五个场站连接，并将新鲜度阈值设置为 60 秒。启动后可检查：

```powershell
Invoke-RestMethod http://127.0.0.1:18080/api/v1/scada/health
Invoke-RestMethod http://127.0.0.1:18080/api/v1/system/capabilities
```

无效质量码演练：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:18082/scenario `
  -ContentType 'application/json' `
  -Body '{"name":"invalid_quality"}'
```

恢复正常场景：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:18082/scenario `
  -ContentType 'application/json' `
  -Body '{"name":"normal"}'
```

## 生产配置

至少需要明确设置以下配置：

| 配置 | 用途 |
| --- | --- |
| `SCADA_REALTIME_ENABLED` | 启用实时接入和连接管理 |
| `SCADA_REQUIRED` | 将 SCADA 异常纳入顶部运行告警 |
| `SCADA_WORKER_SECRET` | Worker 调用内部接口的共享密钥 |
| `SCADA_DATA_STALE_AFTER_SECONDS` | 最后有效样本的新鲜度阈值 |
| `SCADA_MAX_CLOCK_SKEW_SECONDS` | 允许的源时间超前量 |
| `SCADA_MAX_SOURCE_AGE_SECONDS` | 允许的最大源数据年龄 |
| `SCADA_POWER_MIN_MW` | 功率下限 |
| `SCADA_POWER_MAX_CAPACITY_FACTOR` | 相对装机容量的功率上限 |
| `SCADA_INGEST_RETENTION_DAYS` | SCADA 审计记录保留天数 |

生产环境应设置非空的 `SCADA_WORKER_SECRET`，并由发布流程生成和保管。HTTP 模拟轮询默认关闭，前端也不再提供该模式。

## 已有数据库升级

应用模型目前会通过 `Base.metadata.create_all` 补建缺失表。为了让生产变更可以审阅，当前分支同时提供显式脚本：

```text
database/migrations/20260715_scada_ingest_records.sql
```

升级前先备份生产数据库，在生产副本执行脚本并验证索引，再安排正式变更窗口。仓库目前缺少可直接使用的 Alembic 基线，正式场站试运行前需要完成版本化迁移体系，具体优先级见 `CODEBASE_INTEGRATION_AUDIT.md`。

## 当前业务边界

当前闭环覆盖场站实发功率。仿真点表中的风速、理论功率、可用功率和风机可用率已经可以通过 C104 验收，尚未映射到统一业务入库服务。NWP 数据也需要依据场站正式接口资料增加适配器。下一阶段应先完成这些输入契约，再启用依赖它们的预测任务。
