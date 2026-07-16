# NWP 生产影子环境

## 目标

该环境在开发电脑上复现当前生产 DQYC 输入形态，同时与生产服务器、生产数据库和生产目录完全隔离。开发人员可以验证 E 文本格式、五场站格点映射、当前算法输入和未来 240 小时时效扩展。

## 固定契约

契约文件位于 `config/nwp-etext-contract-v1.json`，当前版本包含以下约束：

1. 报表类型为 `DQYC`，实体为 `YN.ZhuYXDC`。
2. 数据间隔为 15 分钟。
3. 五个场站合计 55 个唯一格点。
4. 每个格点包含 19 个变量。
5. 特征列为 1045 列，加上 `Timestamp` 后共 1046 列。
6. 当前模型视图为 508 个时刻。
7. 240 小时业务目标为 960 个时刻。

适配器严格校验文件编码、起止标签、文件名时间、首行时间、列集合、重复列、连续时间、数值类型和有限值。违反契约的文件不会产生业务产物。

## 分层结构

```text
DQYC E 文本
    ↓
raw 原始层          原字节和 SHA256 保持不变
    ↓
model 模型层        固定取前 508 个时刻
    ↓
business 业务层     保留全部时效并拆分到五个场站
    ↓
现有 NWP 接入处理器
```

当输入仍为 508 个时刻时，模型层和业务层都使用 508 个时刻，清单中的 `regulatory_240h_ready` 为 `false`。当输入扩展到 960 个时刻时，模型层仍为 508 个时刻，业务层使用完整 960 个时刻，状态变为 `true`。这样可以先保存完整气象数据，再独立安排算法扩展。

## 日常启动

完整开发环境直接运行：

```bat
start-scada-dev.bat
```

默认模式为 `etext-shadow`。脚本优先读取：

```text
D:\Wind-power-microserver\data\YCSJ_YN.ZhuYXDC_DQYC_20260504_191500.dat
```

样本存在时会回放到当前最近的 15 分钟时刻。回放只改变影子模型层和业务层时间，原始层字节及摘要保持不变。样本不存在时会生成同契约的确定性 508 时刻文件，保证离线开发仍可启动。

仅启动影子适配器：

```bat
start-nwp-shadow-dev.bat
```

停止影子适配器：

```bat
stop-nwp-shadow-dev.bat
```

运行产物位于：

```text
D:\Wind-power-microserver\simulation\nwp-shadow\artifacts
```

该目录已从 Git 排除。

## 手工命令

校验真实文件：

```powershell
python scripts\nwp_shadow.py verify `
  --input ..\data\YCSJ_YN.ZhuYXDC_DQYC_20260504_191500.dat
```

生成隔离产物并回放到当前时间：

```powershell
python scripts\nwp_shadow.py prepare `
  --input ..\data\YCSJ_YN.ZhuYXDC_DQYC_20260504_191500.dat `
  --output-root ..\simulation\nwp-shadow\artifacts `
  --replay-now
```

生成 960 时刻测试文件：

```powershell
python scripts\nwp_shadow.py generate `
  --output ..\simulation\nwp-shadow\artifacts\generated `
  --steps regulatory
```

## 产物说明

1. `raw/<摘要>/` 保存不可变原始 E 文本。
2. `model/<生效时间>/` 保存当前算法兼容的 508 时刻 E 文本。
3. `business/<场站编码>/` 保存现有接入处理器可读取的长格式 CSV。
4. `manifests/` 保存来源摘要、有效时间、模型行数、业务行数、场站文件和 240 小时就绪状态。
5. `generated/` 保存离线合成样本。
6. `etext-inbox/` 接收开发人员临时放入的 DQYC 文件。

## 生产边界

影子适配器不会连接腾讯云服务器，也不会修改生产目录。云端 `/ECMWF/yunnan_test` 到 DQYC 的生成链路继续独立运行。远端服务维护脚本位于 `deploy/ecmwf/`，`run_yunnan_service_consolidation.sh` 默认仅执行预检，只有明确传入 `--apply` 才会进行服务收敛。每次变更都会先备份 systemd 单元和巡检脚本，并在验证失败时自动回滚。备份目录中同时保存独立 `rollback.sh`，后续发现问题时仍可按目录恢复原服务状态。

2026 年 7 月 16 日的生产收敛结果、校验摘要和回滚目录记录在 `ECMWF_YUNNAN_MAINTENANCE.md`。
