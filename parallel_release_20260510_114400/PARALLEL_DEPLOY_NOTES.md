# 同机并行部署说明

本目录是 staging 并行版发布包，用于和旧生产系统在同一台机器上同时运行。

## 隔离项

- 网络：`wind-power-staging-network`
- 数据库容器：`wind-power-staging-kingbase`
- 后端 worker：`wind-power-staging-celery-worker`
- 定时任务：`wind-power-staging-celery-beat`
- Redis：`wind-power-staging-redis`
- pgAdmin：`wind-power-staging-pgadmin`
- SCADA 模拟器：`wind-power-staging-scada-simulator`

## 访问端口

- 前端：`http://<server-ip>:18080`
- 后端 API：`http://<server-ip>:15000`
- 数据库宿主机端口：`15432`
- Redis 宿主机端口：`127.0.0.1:16379`
- pgAdmin：`http://<server-ip>:15050`
- SCADA 模拟器宿主机端口：`12404`

容器内部端口保持不变，应用容器之间仍然使用内部服务名和内部端口通信。

## 安装

目录结构保持如下：

```text
parallel_release_20260510_114400/
  01_database.tar
  02_prediction_system.tar
  03_seed_data.dump
  04_scada_simulator.tar
  wind-power-forecast/
    deploy/
```

进入部署目录：

```bash
cd wind-power-forecast/deploy
bash deploy.sh install
bash deploy.sh start
```

如果需要启动 SCADA 模拟器：

```bash
bash scada-sim.sh install
bash scada-sim.sh start
```

如果需要写入模拟器连接配置：

```bash
bash scada-sim.sh seed
```

## 切换建议

先让旧系统继续对外服务，新系统通过 `18080` 单独验证。确认预测、E 文本、SCADA 和数据库都稳定后，再把外部访问入口切到新系统。
