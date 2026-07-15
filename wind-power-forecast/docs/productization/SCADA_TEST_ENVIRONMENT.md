# SCADA 独立测试环境

## 目标

该环境用于在无法连接场站内网和真实 SCADA 的条件下，持续验证协议接入、点表、数据语义、异常场景和断线恢复。开发环境与现场环境使用同一份 `scada_worker.py`，仅切换 C104 端点和时间策略。

生产 Compose 文件没有被引用，测试环境使用独立 Compose 项目、网络、端口和可选数据卷。

## 架构

```text
确定性场景引擎
        ↓
C104 仿真服务器 2404
        ↓
TCP 故障代理 2405
        ↓
生产 scada_worker.py
        ↓
SCADA 样本接入接口或验收模拟接收端
        ↓
质量审计、实际功率入库或自动验收报告
```

测试环境划分了场站仿真网络、采集测试网络和控制网络。开发程序默认连接故障代理暴露到本机的 `127.0.0.1:12404`。调试时可以通过 `127.0.0.1:12405` 绕过故障代理直连仿真器。

## 快速使用

在 Windows 上启动核心测试床：

```bat
cd D:\Wind-power-microserver\wind-power-forecast
start-scada-test.bat
```

启动业务系统并自动配置五个场站的 SCADA Worker：

```bat
start-scada-dev.bat
```

该命令依次启动仿真器、故障代理、本地 KingBase、Redis、Flask、Celery、Vue，并通过本地后端 API 写入版本化点表。Worker 在开发模式下使用 `floor_quarter` 时间策略，同一十五分钟内的数据更新同一条本地记录。每个样本会先进入 `/api/v1/scada/ingest`，完成质量校验和来源审计。运行状态可通过 `/api/v1/scada/health` 查询。

业务闭环、状态含义和生产配置详见 `SCADA_CLOSED_LOOP.md`。

停止完整开发环境：

```bat
stop-scada-dev.bat
```

Linux 上可以使用：

```bash
./wind-power-forecast/scripts/scada-test.sh up
./wind-power-forecast/scripts/scada-test.sh test
./wind-power-forecast/scripts/scada-test.sh down
```

## 自动验收

Windows：

```bat
test-scada-test.bat
```

PowerShell：

```powershell
.\wind-power-forecast\scripts\scada-test.ps1 -Action test
```

验收套件当前检查八项能力：

1. 仿真器、故障代理和接收端健康状态。
2. CASDU、25 个 IOA 和正常质量码。
3. 五个真实生产 `scada_worker.py` 进程的端到端上送。
4. C104 无效质量码注入与读取。
5. TCP 延迟注入是否真实生效。
6. 链路断开后 Worker 是否自动重连并继续上送。
7. 限功率场景中风速、理论功率、可用功率与实发功率的一致性。
8. 陈旧数据场景是否冻结序号并停止主动发送。

报告生成在：

```text
simulation/scada-test/artifacts/acceptance-report.json
```

该目录中的运行产物不会进入 Git。

## 场景控制

查看可用场景：

```powershell
Invoke-RestMethod http://127.0.0.1:18082/scenarios
```

切换场景：

```powershell
.\wind-power-forecast\scripts\scada-test.ps1 -Action scenario -Name curtailment
```

当前场景包括：

1. `normal`，确定性正常运行。
2. `ramp_up`，风速和功率逐步爬升。
3. `curtailment`，高风速下限功率。
4. `turbine_trip`，指定场站停机。
5. `invalid_quality`，全部点位携带无效质量码。
6. `stale`，三个周期后停止更新。
7. `zero_output`，低于切入风速。
8. `clock_skew`，源时间向前偏移五分钟。

每个场景都有固定随机种子。重置场景后会生成完全相同的数据序列，适合回归测试。

场景定义位于：

```text
simulation/scada-test/config/scenarios.json
```

## 网络故障控制

增加 500 毫秒延迟和 100 毫秒抖动：

```powershell
.\wind-power-forecast\scripts\scada-test.ps1 -Action fault -LatencyMs 500 -JitterMs 100
```

限制带宽：

```powershell
.\wind-power-forecast\scripts\scada-test.ps1 -Action fault -BandwidthKbps 32
```

断开链路：

```powershell
.\wind-power-forecast\scripts\scada-test.ps1 -Action fault -Disable
```

恢复正常链路和正常场景：

```powershell
.\wind-power-forecast\scripts\scada-test.ps1 -Action reset
```

故障代理还支持 `close_after_bytes`，可以在指定传输量后主动关闭连接。

## 点表契约

版本化点表位于：

```text
simulation/scada-test/config/point-catalog.json
```

五个场站共包含以下指标：

1. 实发功率。
2. 风速。
3. 理论功率。
4. 可用功率。
5. 风机可用率。

当前实发功率 IOA 与已有系统保持一致，CASDU 为 1，Type ID 为 `M_ME_NC_1`。该类型没有 C104 源时间标签，因此点表明确声明 `reception_time` 时间语义。接入真实场站前必须根据正式点表核对 CASDU、IOA、Type ID、单位、倍率、质量位和时间类型。

## 数据隔离保护

1. Compose 项目名固定为 `wind-power-scada-test`。
2. 所有宿主机端口仅绑定到 `127.0.0.1`。
3. 场站仿真网络和采集网络独立创建。
4. 自动配置脚本默认拒绝非本机后端地址。
5. `start-scada-dev.bat` 只连接现有本地开发数据库。
6. `infra` profile 可启动额外的 KingBase 和 Redis，端口分别为 15433 和 6380，数据卷与本地开发环境分离。

启动隔离基础设施：

```powershell
.\wind-power-forecast\scripts\scada-test.ps1 -Action up-infra
```

## 端口

1. `12404`，经过故障代理的 C104 开发入口。
2. `12405`，直连 C104 仿真器。
3. `18081`，故障代理控制接口。
4. `18082`，仿真场景控制接口。
5. `18083`，验收期间使用的模拟接收端。
6. `15433`，可选隔离 KingBase。
7. `6380`，可选隔离 Redis。

端口可以通过 `simulation/scada-test/scada-test.env.example` 中的同名环境变量覆盖。

## 离线构建

测试镜像以 `wind-power-scada-simulator:v1` 为基础。管理脚本发现该镜像不存在时，会从仓库已有的 `wind-power-forecast/04_scada_simulator.tar` 加载。整个测试床无需在线安装 Python 包。
