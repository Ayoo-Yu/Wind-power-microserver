# SCADA 独立测试环境

该目录提供风电预测系统的场站级开发测试床。测试床包含确定性 C104 仿真器、版本化点表、场景引擎、TCP 故障代理、模拟接收端和生产采集 Worker 验收工具。

完整操作说明见 [SCADA_TEST_ENVIRONMENT.md](../../wind-power-forecast/docs/productization/SCADA_TEST_ENVIRONMENT.md)。

Windows 快速启动：

```bat
cd wind-power-forecast
start-scada-test.bat
```

运行完整验收：

```bat
test-scada-test.bat
```

完整开发环境：

```bat
start-scada-dev.bat
```

仿真数据只允许接入本机开发后端。自动配置脚本默认拒绝非本机地址。
