# 风电功率预测系统生产部署指南

## 1. 发布包内容

正式发布目录应包含：

```text
01_database.tar
02_prediction_system.tar
03_seed_data.dump                    可选
VERSION
release-manifest.json
application-sbom.cdx.json
SHA256SUMS
SHA256SUMS.sig                       签名发布时存在
release-signing-public.pem           签名发布时存在
wind-power-forecast/deploy/
```

发布包必须来自受控构建机，镜像标签和 Git 提交记录在 `release-manifest.json`。场站服务器不执行在线构建，也不访问公网软件仓库。

发布包分为两类：

1. `full`：首次安装包，包含数据库镜像、业务镜像和可选种子数据。
2. `upgrade`：日常升级包，包含业务镜像、脚本、清单和 SBOM，不包含数据库种子数据。

## 2. 服务器要求

| 项目 | 最低要求 |
| --- | --- |
| 操作系统 | 受支持的 x86_64 Linux，建议银河麒麟 V10 或经验证的同类发行版 |
| Docker | 20.10 及以上，Docker Compose V2 |
| Python | Python 3，用于发布策略校验 |
| OpenSSL | 签名发布必须安装 |
| 内存 | 8 GB，实际容量根据模型并发测试调整 |
| 磁盘 | 20 GB 可用空间，历史数据和备份空间另行评估 |
| 对外端口 | 8080 前端，5000 仅在跨区接入确有需要时开放 |
| 本机端口 | 54321 数据库、6379 Redis 仅绑定 127.0.0.1 |

场站防火墙只放行已审批的来源地址、协议和端口。数据库不向业务网直接开放。

## 3. 校验发布包

```bash
cd /approved-media/release_2026.07.15
REQUIRE_RELEASE_SIGNATURE=true \
  bash wind-power-forecast/deploy/verify-release.sh .
```

该步骤会检查全部文件 SHA256、发布清单、Git 工作树状态、镜像固定标签、CycloneDX SBOM 和数字签名。任何检查失败都应停止安装并保留介质与日志。

## 4. 配置环境

```bash
cd wind-power-forecast/deploy
cp .env.example .env
vi .env
```

始终修改：

```text
DATA_ROOT
DB_PASSWORD
SECRET_KEY
FRONTEND_IMAGE
PREDICTION_IMAGE
DATABASE_IMAGE
```

启用 SCADA 时同时配置：

```text
SCADA_REALTIME_ENABLED=true
SCADA_REQUIRED=true
SCADA_WORKER_SECRET=<独立随机密钥>
SCADA_ALLOWED_NETWORKS=<现场 SCADA 精确网段>
```

启用 NWP 时同时配置：

```text
NWP_INGESTION_ENABLED=true
NWP_INGESTION_REQUIRED=true
NWP_DATA_STALE_AFTER_SECONDS=<现场确认阈值>
```

启用跨区 HTTP 接入时同时配置：

```text
INTEGRATION_API_ENABLED=true
INTEGRATION_API_REQUIRED=true
INTEGRATION_API_TOKEN=<独立随机令牌>
```

保持以下生产门禁：

```text
DEPLOYMENT_MODE=field
DB_SCHEMA_STRICT=true
MODEL_AUTO_APPROVAL_ENABLED=false
DB_SCHEMA_ACTION=prepare
```

`DATA_ROOT` 必须是发布包目录外的 Linux 绝对路径，例如 `/opt/wind-power/data`。后续升级继续复用该目录，避免换发布目录后重新生成空数据库和空模型目录。

校验配置：

```bash
bash validate-field-config.sh .env
```

示例值、弱密钥、`latest` 镜像、缺少 SCADA 网段或能力开关组合错误都会阻止启动。

## 5. 首次安装

```bash
chmod +x deploy.sh validate-field-config.sh verify-release.sh
./deploy.sh install
./deploy.sh start
./deploy.sh status
```

部署脚本依次执行：

1. 校验场站配置。
2. 导入离线镜像并创建 Docker 网络。
3. 创建数据库、Redis、模型、日志、归档和接入目录。
4. 启动 KingBase 并确认数据库可连接。
5. 由一次性 `deployment-init` 容器执行数据库迁移、基础角色初始化和严格结构检查。
6. 初始化成功后启动后端、SCADA Manager、NWP 接入处理器、Celery、Redis 和前端。

如果是全新演示库，并且确实需要导入发布包里的 `03_seed_data.dump`，在启动数据库后单独执行：

```bash
./deploy.sh init-seed
```

生产升级不要执行该命令。

## 6. 启动后检查

```bash
curl -fsS http://127.0.0.1:5000/health/ready
docker compose -f docker-compose.prod.yaml ps
docker compose -f docker-compose.db.yaml ps
docker compose -f docker-compose.prod.yaml logs --tail 100 scada-manager
docker compose -f docker-compose.prod.yaml logs --tail 100 integration-processor
```

浏览器访问：

```text
http://<服务器地址>:8080
```

登录后打开“运维与质量”中的“运行控制中心”，确认：

1. SCADA 每个启用场站的五类指标状态符合现场配置。
2. NWP 最近业务批次覆盖全部启用场站。
3. 预测输入快照能关联 SCADA、NWP 和已审批模型。
4. 上报队列没有未知死信。
5. 磁盘使用率位于安全范围。

未启用的数据能力应明确显示“未启用”或“待配置”。

## 7. 数据持久化

主要目录位于 `.env` 的 `DATA_ROOT` 下：

```text
DATA_ROOT/
├── kingbase-data/
├── backend-data/
│   ├── forecast_models/
│   ├── uploads/
│   ├── logs/
│   ├── weather/
│   ├── archives/
│   └── integration/
├── redis-data/
├── celery-beat-data/
├── datasets/
├── models/
├── predict_outputs/
└── 各预测尺度对应目录
```

数据库备份应使用 KingBase 的逻辑备份工具，并定期在隔离服务器执行恢复演练。复制正在运行的数据库数据目录无法替代一致性备份。

## 8. 常用运维命令

```bash
./deploy.sh start
./deploy.sh upgrade
./deploy.sh stop
./deploy.sh restart
./deploy.sh status
./deploy.sh logs
./deploy.sh logs backend
./deploy.sh logs scada-manager
./deploy.sh logs integration-processor
./deploy.sh db-only
```

单独重启：

```bash
docker compose -f docker-compose.prod.yaml restart backend
docker compose -f docker-compose.prod.yaml restart scada-manager
docker compose -f docker-compose.prod.yaml restart integration-processor
docker compose -f docker-compose.prod.yaml restart celery-worker
```

## 9. 更新与回滚

更新前：

1. 校验新发布包。
2. 完成数据库逻辑备份和恢复抽查。
3. 保存当前 `.env`、发布清单和镜像摘要。
4. 在生产副本执行数据库迁移和自动回归。
5. 确认业务窗口和回滚负责人。

更新步骤：

```bash
./deploy.sh install
./deploy.sh upgrade
./deploy.sh status
```

升级会保留数据库、Redis、模型、日志、气象输入和预测输出目录，只导入新镜像、执行迁移门禁并重建业务容器。应用回滚时切换到上一发布目录和上一组固定镜像标签，然后执行 `./deploy.sh upgrade`。数据库迁移采用向前兼容设计，出现问题时优先执行经过审核的修复迁移。未经演练不得直接删除新表或新列。

## 10. 故障排查

数据库结构问题：

```bash
docker compose -f docker-compose.prod.yaml logs --tail 200 backend
docker compose -f docker-compose.prod.yaml logs --tail 200 deployment-init
docker compose -f docker-compose.prod.yaml exec backend alembic current
docker compose -f docker-compose.prod.yaml exec backend alembic heads
```

SCADA 问题：

```bash
docker compose -f docker-compose.prod.yaml logs --tail 200 scada-manager
docker compose -f docker-compose.prod.yaml ps scada-manager
```

NWP 问题：

```bash
docker compose -f docker-compose.prod.yaml logs --tail 200 integration-processor
find "$DATA_ROOT/backend-data/integration" -maxdepth 3 -type f | head
```

上报问题：

```bash
docker compose -f docker-compose.prod.yaml logs --tail 200 celery-worker
```

磁盘问题：

```bash
df -h
du -sh "$DATA_ROOT"/backend-data/* "$DATA_ROOT"/redis-data "$DATA_ROOT"/celery-beat-data
```

归档、镜像清理和日志删除都应通过审批流程执行，避免清除仍需追溯的数据与当前回滚镜像。
