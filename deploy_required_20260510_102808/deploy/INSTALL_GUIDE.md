# 风电功率预测系统 — 生产环境部署安装指南

## 1. 交付物清单

| 文件 | 说明 |
|------|------|
| `01_database.tar` | 金仓数据库 Docker 镜像 (约 710MB) |
| `02_prediction_system.tar` | 预测系统全部镜像 (约 2.7GB) |
| `deploy/` 目录 | 部署配置文件（compose、脚本、环境变量模板） |

`deploy/` 目录结构：

```
deploy/
├── docker-compose.db.yaml      # 数据库编排
├── docker-compose.prod.yaml    # 预测系统编排
├── deploy.sh                   # 部署管理脚本
├── .env.example                # 环境变量模板
└── INSTALL_GUIDE.md            # 本文件
```

## 2. 服务器要求

| 项目 | 要求 |
|------|------|
| 操作系统 | CentOS 7+ / 华为银河麒麟 V10 (x86_64) |
| Docker | >= 20.10（含 Docker Compose V2） |
| 磁盘 | 至少 20GB 可用空间 |
| 内存 | 至少 8GB |
| 端口 | 8080（前端）、5000（后端 API）、54321（数据库）、5050（pgAdmin）开放 |

## 3. 安装步骤

### 3.1 上传文件

将以下文件/目录上传到服务器的同一部署目录（如 `/opt/wind-power/`）：

```
/opt/wind-power/
├── 01_database.tar
├── 02_prediction_system.tar
└── deploy/
```

### 3.2 加载镜像

```bash
cd /opt/wind-power

# 加载数据库镜像
docker load -i 01_database.tar

# 加载预测系统镜像（包含 frontend、backend、celery、redis、pgadmin）
docker load -i 02_prediction_system.tar

# 验证镜像是否加载成功
docker images | grep -E "kingbase|wind-power|redis|pgadmin"
```

预期输出应包含以下镜像：

```
kingbase_v009r001c002b0014_single_x86   v1         ...   1.52GB
wind-power-frontend                      v250715_1.0  ...   110MB
wind-power-backend                       v250714_1.0  ...   4.44GB
wind-power-celery-worker                 latest     ...   4.47GB
redis                                    7-alpine   ...   60.7MB
dpage/pgadmin4                          latest     ...   1.14GB
```

### 3.3 配置环境变量

```bash
cd /opt/wind-power/deploy

# 从模板创建 .env 文件
cp .env.example .env

# 编辑 .env，修改以下项（必改）：
vi .env
```

`.env` 内容：

```bash
# 数据库密码（kingbase 和 backend 共用，必须修改）
DB_PASSWORD=你的数据库密码

# Flask JWT 密钥（必须修改，建议随机生成）
SECRET_KEY=你的密钥字符串

# Flower 监控面板（可选）
FLOWER_USER=admin
FLOWER_PASSWORD=你的监控面板密码
```

> **安全提示**：`SECRET_KEY` 建议使用 `openssl rand -hex 32` 生成随机字符串。

### 3.4 创建网络并启动

**方式 A：使用部署脚本（推荐）**

```bash
cd /opt/wind-power/deploy
chmod +x deploy.sh

# 首次安装（创建网络和目录）
./deploy.sh install

# 启动全部服务
./deploy.sh start
```

**方式 B：手动操作**

```bash
cd /opt/wind-power/deploy

# 创建 Docker 网络
docker network create wind-power-network

# 创建数据目录
mkdir -p kingbase-data && chmod 777 kingbase-data
mkdir -p backend-data/{forecast_models,uploads,forecasts,logs,saved_models,saved_scalers,saved_metrics,data_etext,archives}
mkdir -p redis-data celery-beat-data pgadmin-data
chmod 777 pgadmin-data

# 启动数据库
docker compose -f docker-compose.db.yaml up -d

# 等待数据库就绪（约 10-30 秒）
echo "等待数据库启动..."
sleep 15

# 启动预测系统
docker compose -f docker-compose.prod.yaml up -d
```

### 3.5 验证服务

```bash
# 查看所有容器状态
cd /opt/wind-power/deploy
./deploy.sh status

# 或手动查看
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

预期所有容器状态为 `Up`：

| 容器名 | 端口映射 |
|--------|---------|
| wind-power-kingbase | 54321:54321 |
| wind-power-redis | 127.0.0.1:6379 |
| wind-power-backend | 5000:5000 |
| wind-power-celery-worker | — |
| wind-power-celery-beat | — |
| wind-power-frontend | 8080:80 |
| wind-power-pgadmin | 5050:80 |

访问验证：

- 前端界面：`http://<服务器IP>:8080`
- 后端 API：`http://<服务器IP>:5000/health`（应返回 `{"status": "healthy"}`）
- pgAdmin：`http://<服务器IP>:5050`（账号 admin@admin.com / admin）

## 4. 数据持久化

所有数据通过 bind mount 存储在宿主机，**容器删除重建不丢数据**：

```
deploy/
├── kingbase-data/          # 数据库数据（最关键）
├── backend-data/
│   ├── forecast_models/    # 训练好的 ML 模型
│   ├── uploads/            # 上传的 CSV 文件
│   ├── forecasts/          # 预测结果下载
│   ├── logs/               # 应用日志
│   ├── saved_models/       # 模型存储
│   ├── saved_scalers/      # 归一化器
│   ├── saved_metrics/      # 模型指标
│   ├── data_etext/         # E文本管道配置
│   └── archives/           # 数据归档
├── redis-data/             # Redis AOF 持久化
├── celery-beat-data/       # 调度状态
├── pgadmin-data/           # pgAdmin 配置
├── datasets/               # 中期预测数据集
├── models/                 # 中期模型
├── predict_outputs/        # 中期预测结果
└── ...                     # 其他预测管道目录
```

> **重要**：备份时只需备份整个 `deploy/` 目录即可保留全部数据。

## 5. 数据库许可证续期（每 2 个月）

金仓数据库许可证到期需要卸载重装容器。由于使用 bind mount，**数据不会丢失**：

```bash
cd /opt/wind-power/deploy

# 1. 停止数据库容器
docker compose -f docker-compose.db.yaml down

# 2. 删除旧镜像（保留 kingbase-data/ 目录不动）
docker rmi kingbase_v009r001c002b0014_single_x86:v1

# 3. 加载新许可证镜像
docker load -i 新的01_database.tar

# 4. 重新启动数据库
docker compose -f docker-compose.db.yaml up -d

# 5. 验证数据库就绪
docker exec wind-power-kingbase ls /home/kingbase/userdata/data
```

> **注意**：整个过程中 **不要删除 `kingbase-data/` 目录**，否则数据会丢失。

数据库重启后，预测系统会自动重连（已实现断线重连机制）。

## 6. 日常运维

### 常用命令

```bash
cd /opt/wind-power/deploy

./deploy.sh start     # 启动全部服务
./deploy.sh stop      # 停止全部服务
./deploy.sh restart   # 重启全部服务
./deploy.sh status    # 查看服务状态
./deploy.sh logs      # 查看全部日志
./deploy.sh logs backend  # 只看后端日志
./deploy.sh db-only   # 仅启动数据库
```

### 单独重启某个服务

```bash
# 重启后端
docker compose -f docker-compose.prod.yaml restart backend

# 重启 Celery Worker
docker compose -f docker-compose.prod.yaml restart celery-worker
```

### 数据备份

```bash
# 备份整个部署目录（含数据）
tar czf wind-power-backup-$(date +%Y%m%d).tar.gz \
    --exclude='*.log' \
    --exclude='logs/*' \
    /opt/wind-power/deploy/
```

### 系统更新

当有新版本镜像时：

```bash
# 1. 停止预测系统（数据库不停）
docker compose -f docker-compose.prod.yaml down

# 2. 加载新镜像
docker load -i 新的02_prediction_system.tar

# 3. 重新启动
docker compose -f docker-compose.prod.yaml up -d
```

## 7. 故障排查

### 容器启动失败

```bash
# 查看容器日志
docker logs wind-power-backend --tail 50
docker logs wind-power-kingbase --tail 50
```

### 数据库连接失败

```bash
# 检查数据库是否就绪
docker exec wind-power-kingbase ls /home/kingbase/userdata/data

# 测试连接
docker exec wind-power-backend python -c "
from sqlalchemy import create_engine, text
e = create_engine('postgresql://system:你的密码@kingbase:54321/windpower')
with e.connect() as c:
    print(c.execute(text('SELECT 1')).scalar())
"
```

### 磁盘空间不足

```bash
# 查看磁盘占用
du -sh /opt/wind-power/deploy/*/

# 清理 Docker 无用资源
docker system prune -f
```
