# 跨区数据契约 1.0

## 数据包组成

一个数据包由 `manifest.json` 和一个不可变载荷文件组成。正式 JSON Schema 位于 `backend/integration/schemas/manifest-v1.schema.json`。

| 字段 | 含义 | 规则 |
| --- | --- | --- |
| message_id | 全链路消息编号 | 128 字符以内，可安全用作 Linux 与 Windows 目录名 |
| source | 数据来源 | 建议使用 `区域.系统`，例如 `zone2.scada` |
| farm_code | 场站编码 | 与主数据保持一致 |
| data_type | 数据类型 | scada、actual_power、nwp、weather、operational、forecast、report_receipt |
| event_time | 业务发生时间 | ISO 8601，必须包含时区偏移 |
| created_at | 数据包创建时间 | ISO 8601，必须包含时区偏移 |
| payload_filename | 载荷文件名 | 仅允许安全基础文件名 |
| payload_sha256 | 载荷摘要 | 小写 SHA256 |
| payload_size | 载荷字节数 | 非负整数 |
| record_count | 记录数 | 可选 |
| sequence | 来源序号 | 可选，适合 SCADA 批次 |
| quality | 数据质量信息 | 可选 JSON 对象 |
| metadata | 扩展元数据 | 可选 JSON 对象 |

## 状态机

```text
inbox → processing → processed
   ↑         ↓
   └ retry   quarantine
```

`inbox` 表示已完整落盘。`processing` 表示某个工作进程已原子抢占。临时故障回到 `inbox` 并写入下一次尝试时间。契约错误、鉴权错误和同编号不同内容冲突进入 `quarantine`。

## 业务接入批次

可靠传输完成后，`python -m integration.processor` 抢占数据包并记录 `ingestion_batches`。当前生产适配器支持 `data_type=nwp` 的长格式 CSV，写入场站 ECMWF 格点表。处理结果包括：

1. `completed`，业务数据已提交，记录接受数、拒绝数和质量状态。
2. `retry`，数据库等临时依赖不可用，数据包回到待处理目录。
3. `quarantined`，数据类型、字段或时间格式不符合契约，数据包进入隔离目录。
4. `duplicate`，相同 `message_id` 已成功处理，不重复写入业务数据。

每个批次保存来源、场站、契约版本、业务时间、载荷摘要和错误原因。预测输入快照通过批次编号引用实际使用的 NWP 数据。

## SCADA 实时观测契约

实时样本使用 `scada-point-v2`，包含 `connection_id`、`farm_code`、`metric`、`value`、`unit`、`quality`、`source_timestamp`、`ioa` 和来源编号。必须支持以下五类规范指标：

| metric | 单位 | 业务投影 |
| --- | --- | --- |
| `active_power_mw` | MW | actual_power |
| `wind_speed_mps` | m/s | weather_data |
| `theoretical_power_mw` | MW | theoretical_power_data |
| `available_power_mw` | MW | available_power_data |
| `availability_pct` | % | available_capacity_data |

所有有效样本先写入 `source_observations`，随后更新业务投影。观测编号由来源、点位、时间、指标和值生成，重复投递保持幂等。

## 幂等规则

1. 相同 `message_id`、来源、场站、类型、业务时间、文件名、大小和摘要视为重复成功。
2. 相同 `message_id` 对应的任一身份字段不同均视为冲突，必须隔离并报警。
3. 目录扫描代理根据来源、场站、类型、文件名、文件修改时间和内容摘要生成稳定编号。
4. HTTP 传递同时发送 `Idempotency-Key` 请求头。

## 命令示例

```bash
python3 -m integration.cli ingest-once \
  --input-dir /data/incoming \
  --spool /var/lib/windpower-zone-agent/spool \
  --source zone3.nwp \
  --farm-code CF \
  --data-type nwp \
  --pattern '*.dat'

INTEGRATION_API_TOKEN='replace-with-secret' \
python3 -m integration.cli transfer-once \
  --spool /var/lib/windpower-zone-agent/spool \
  --target-url http://10.0.0.20:5000/api/v1/integration/packages
```

生产运行使用 `bridge` 子命令，它会持续扫描稳定文件并传递。只有超过最小文件年龄且读取前后大小与修改时间一致的文件才会入队。

## DQYC E 文本契约

生产气象输入使用版本化契约 `config/nwp-etext-contract-v1.json`。当前契约固定以下内容：

1. 文件类型为 `DQYC`，实体为 `YN.ZhuYXDC`。
2. 时间分辨率为 15 分钟。
3. 五个场站合计使用 55 个唯一格点和 19 个变量，共 1045 个特征列。
4. 第一列为 `Timestamp`，文件总列数为 1046。
5. 模型视图固定保留 508 个时刻，兼容当前预测算法。
6. 完整业务层目标为 960 个时刻，对应 240 小时。

适配器按三层保存数据：

1. `raw` 保存收到的原始 E 文本及原始摘要，内容不做改写。
2. `model` 固定输出前 508 个时刻，隔离后续时效扩展对现有算法的影响。
3. `business` 保存全部可用时效，并按五个场站生成现有接入服务可消费的长格式 CSV。

当前生产样本具有 508 个时刻，因此可以进入模型层，完整 240 小时就绪状态为否。未来上游提供完整 960 个时刻时，模型层仍维持 508 个时刻，业务层自动保留全部数据。
