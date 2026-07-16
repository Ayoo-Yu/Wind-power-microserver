# API 身份认证与权限基线

## 基本原则

1. 业务接口由后端验证 JWT，前端菜单权限只负责交互展示。
2. 权限判断以令牌中的用户编号为入口，并再次读取数据库中的启用状态、角色和权限。
3. 请求参数和请求体中的用户名不能用于证明调用者身份。
4. 管理员角色、历史权限字典和当前权限列表统一经过 `utils.authorization` 解析。
5. 新增写接口必须声明 `jwt_required`、`permission_required`、受控蓝图前置校验或独立机器认证。

## 权限矩阵

| 业务域 | 权限 |
| --- | --- |
| 用户管理 | `manage_users` |
| 角色管理 | `manage_roles` |
| 实测和运行数据导入 | `upload_files` |
| 预测结果导入和执行 | `run_predictions` |
| 自动预测控制 | `auto_predictions` |
| 功率曲线和考核数据 | `view_all_data` |
| 场站、告警和系统参数 | `configure_system` |
| 上报配置、人工修正和统计 | `manage_reports` |
| 气象连接、任务和 E 文本流水线 | `manage_weather_data` |
| 文件下载 | `download_files` |

## 无用户 JWT 的入口

1. 登录接口用于换取 JWT。
2. `/health` 和 `/api/v1/health` 用于容器与运维探测。
3. `/api/v1/public/overview` 只返回登录页所需的非敏感概览。
4. SCADA Worker 状态和样本接入使用独立 Worker 密钥、来源网段和防重放规则。
5. 统一跨区接入使用独立接入令牌和消息摘要规则。

## 回归门禁

`backend/tests/test_route_authorization.py` 同时覆盖匿名拒绝、用户名伪造拒绝、普通角色越权、管理员放行、停用账户拒绝，以及写接口静态授权扫描。SCADA 和跨区机器接口继续由各自安全测试覆盖。
