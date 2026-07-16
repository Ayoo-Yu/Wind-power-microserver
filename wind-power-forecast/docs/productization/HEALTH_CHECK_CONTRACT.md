# 应用健康检查契约

## 存活与就绪

`GET /health/live` 只表示 Web 进程仍能响应，不访问数据库，成功时返回 HTTP 200。编排平台可以将它用作存活探针。

`GET /health/ready` 同时执行数据库 `SELECT 1` 和 Alembic 迁移版本检查。数据库不可连接、迁移待执行、结构漂移或结构检查失败时返回 HTTP 503。检查全部通过时返回 HTTP 200。`GET /health` 保留为同一就绪检查的兼容路径。

`/api/v1/health/live`、`/api/v1/health/ready` 和 `/api/v1/health` 使用统一 API 响应结构。未就绪时 HTTP 状态为 503，业务码为 `1503`。

## 编排行为

生产和全容器开发 Compose 使用 `/health/ready` 作为后端健康检查。数据库未完成初始化或迁移时，后端容器保持运行但标记为 `unhealthy`，依赖 `service_healthy` 的 SCADA Manager 和跨区数据处理器不会提前启动。数据库恢复且结构检查通过后，下一次探针会自动恢复为 `healthy`。

Docker 不会因容器被标记为 `unhealthy` 自动重启仍在运行的进程。这样可以保留后端的自动重连能力，并防止数据库短时中断触发无意义的重启循环。

前端数据库故障恢复轮询继续请求 `/health`。503 表示仍未就绪，恢复到 200 且 `database=ok` 后清除故障状态。
