# 预测运行追踪与并发契约

## 运行身份

每次训练、预测、校准和合并都必须关联已有的 `prediction_tasks` 配置，并拥有唯一的 `prediction_runs` 记录。缺少任务配置时 Worker 直接拒绝执行，系统不再产生无法追溯的算法运行。

运行状态按以下顺序变化：

```text
queued -> running -> success | failed | skipped | interrupted
```

手工触发接口会先写入 `queued` 记录，再向 Celery 发送任务。接口返回 `prediction_run_id` 和 `celery_task_id`，因此消息队列不可用时也能查询发送失败记录。

`prediction_runs` 同时记录操作人、触发来源、请求编号、尝试次数和最近心跳时间。运行列表和运行控制中心返回这些字段。

## 幂等与并发

手工触发支持 `Idempotency-Key`。相同用户、场站、尺度、动作和幂等键会得到同一个 Celery 任务编号，重复请求只返回原运行记录。

数据库对 `celery_task_id` 建立唯一约束。Celery 重试沿用同一运行记录并增加 `attempt_count`，重复投递不会再次执行相同尝试，较早尝试也不能覆盖较新尝试的终态。

同一场站和预测尺度在任意时刻只允许一个活动动作。训练、预测、校准或合并已经处于 `queued` 或 `running` 时，新的手工请求返回 HTTP 409，Worker 收到的重复调度会保存为 `skipped`。不同场站或不同预测尺度仍可并行运行。

互斥由 `prediction_tasks` 行锁和 `uq_prediction_runs_active_task` 部分唯一索引共同保证，适用于多进程 Flask 和多 Worker 部署。

## 输入与输出完整性

`prediction_input_snapshots.prediction_run_id` 引用 `prediction_runs.id`，模型版本引用 `model_versions.id`。创建快照前会锁定运行记录并确认该记录属于预测动作。

`forecast_output_points` 引用运行、输入快照和模型版本。写入前会校验快照所属运行、场站、预测尺度和模型版本，随后在同一运行行锁下执行不可变内容校验。相同运行的重复写入只有在 SHA256 完全一致时才被接受。

保留策略按输出点、输入快照、运行记录的顺序归档并删除，避免破坏外键链。

## 审计来源

`operation_audit_logs.source` 取值如下：

| 值 | 含义 |
| --- | --- |
| `server` | 后端在真实业务事务中生成的可信记录 |
| `client` | 前端提交的补充说明，身份和 IP 仍由后端确定 |
| `legacy` | 迁移前的历史记录 |

手工排队、消息发送失败、任务启停、调度配置和模型治理操作会产生服务端审计。客户端审计接口不再接受自定义操作人和 IP，原始申报值只保存在详情中供核对。

本契约只调整运行编排、数据完整性和审计，预测算法、特征、模型公式与评估公式均未修改。
