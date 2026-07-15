# 功能真实性矩阵

后端接口 `/api/v1/system/capabilities` 返回当前部署的能力事实表。前端顶部只提示当前部署明确要求且运行异常的数据能力。能力状态分为 `available`、`degraded`、`config_required` 和 `unavailable`。

| 能力 | 当前成熟度 | 默认状态 | 启用条件 |
| --- | --- | --- | --- |
| 功率预测与模型调度 | production | available | 数据库、已审批模型和预测 Worker 可用 |
| 可靠数据上报 | production | available | Celery Worker 和 Redis 可用 |
| 统一跨区数据接入 | production | config_required | 配置独立令牌并启用接口 |
| SCADA 实时数据 | production | config_required | 五指标点表、时钟、链路和数据质量验收完成，部署开关已启用 |
| NWP 数据接入 | production | config_required | 内网数据通道和 CSV 适配验收完成，最近业务批次覆盖全部启用场站 |
| 预测输入追溯 | production | available | 数据血缘迁移完成 |
| 模型审批与回滚 | production | available | 模型制品与训练数据摘要可生成 |
| 运行控制中心 | production | available | 用户具有统一告警查看权限 |
| 极端天气实时检测 | placeholder | unavailable | 实时输入与历史事件存储完成 |

## 展示规则

1. 数据源缺失显示“未接入”或“未知”。
2. API 异常显示“接口不可用”。
3. 数据为空与数据源不可用使用不同状态。
4. 仅有静态界面、模拟数据或占位返回的功能不得标记为 production。
5. 能力开关只在依赖验收完成后修改，修改记录进入发布清单和变更单。
6. SCADA 能力启用后使用 Worker 状态、最后有效样本和最近质量结果动态判断，不再只依赖静态开关。
7. NWP 能力启用后仍需检查每个启用场站的最新完成批次、新鲜度和质量，只有开关不足以判定可用。
8. 新模型注册成功只代表候选制品已生成，现场模式必须完成审批后才显示为运行模型。

极端天气接口已按此规则修正。实时数据未接通时返回 `data_available: false`、`current_condition.type: unknown` 和明确原因。系统日志文件缺失时也会提示观测缺口，不再生成正常运行记录。
