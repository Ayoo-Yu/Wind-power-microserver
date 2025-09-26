# SCADA Data Service

SCADA数据服务是风电功率预测系统的核心微服务之一，负责实时SCADA数据的采集、处理和监控。该服务支持多风电场并发连接，提供IEC 60870-5-104协议适配，并集成了实时数据处理和异常检测功能。

## 功能特性

### 🔌 协议支持
- **IEC 60870-5-104协议**: 支持标准SCADA通信协议
- **多协议适配**: 可扩展的协议适配器架构
- **实时连接管理**: 支持多风电场并发连接

### 📊 数据处理
- **实时数据流**: WebSocket支持实时数据推送
- **数据验证**: 智能数据质量检查和范围验证
- **异常检测**: 基于统计方法的异常值检测
- **数据聚合**: 支持多时间窗口的数据聚合

### 🚨 报警管理
- **智能报警**: 基于阈值的自动报警生成
- **报警生命周期**: 完整的报警状态管理
- **批量操作**: 支持批量报警确认和处理
- **实时通知**: Kafka事件发布

### 📈 监控分析
- **系统健康**: 全面的系统状态监控
- **性能指标**: 实时性能指标收集
- **数据质量**: 数据质量分析和报告
- **设备状态**: 风机状态实时监控

## 技术架构

### 核心技术栈
- **FastAPI**: 异步Web框架
- **PostgreSQL**: 关系型数据库
- **InfluxDB**: 时序数据库
- **Redis**: 缓存和会话管理
- **Apache Kafka**: 消息队列和事件流
- **Docker**: 容器化部署

### 微服务架构
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Wind Farm     │    │   Wind Farm     │    │   Wind Farm     │
│   SCADA System  │    │   SCADA System  │    │   SCADA System  │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │ IEC 104              │ IEC 104              │ IEC 104
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    SCADA Data Service   │
                    │  (Protocol Adapters)    │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Connection Manager    │
                    │  (Multi-connection)     │
                    └────────────┬────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                    │
    ┌───────▼───────┐   ┌────────▼────────┐   ┌──────▼──────┐
    │   InfluxDB    │   │  Data Processor │   │   Kafka     │
    │ (Time Series) │   │ (Real-time)     │   │ (Events)    │
    └───────────────┘   └─────────────────┘   └─────────────┘
```

## API 端点

### 连接管理
- `POST /api/v1/connections` - 创建SCADA连接
- `GET /api/v1/connections/{connection_id}` - 获取连接详情
- `PUT /api/v1/connections/{connection_id}` - 更新连接配置
- `POST /api/v1/connections/{connection_id}/start` - 启动连接
- `POST /api/v1/connections/{connection_id}/stop` - 停止连接

### 数据点管理
- `POST /api/v1/data-points` - 创建数据点配置
- `GET /api/v1/data-points` - 获取数据点列表
- `PUT /api/v1/data-points/{data_point_id}` - 更新数据点
- `POST /api/v1/data-points/{data_point_id}/test-alarm` - 测试报警配置

### 实时数据
- `GET /api/v1/realtime-data/current` - 获取当前实时数据
- `GET /api/v1/realtime-data/by-connection/{connection_id}` - 按连接获取数据
- `GET /api/v1/realtime-data/by-turbine/{turbine_id}` - 按风机获取数据
- `POST /api/v1/realtime-data/aggregate` - 数据聚合
- `WS /api/v1/realtime-data/ws/{wind_farm_id}` - WebSocket实时数据流

### 报警管理
- `POST /api/v1/alarms` - 创建报警
- `GET /api/v1/alarms` - 获取报警列表
- `PUT /api/v1/alarms/{alarm_id}` - 更新报警
- `POST /api/v1/alarms/{alarm_id}/acknowledge` - 确认报警
- `POST /api/v1/alarms/{alarm_id}/resolve` - 解决报警

### 系统监控
- `GET /api/v1/monitoring/status` - 系统状态
- `GET /api/v1/monitoring/connections/health` - 连接健康状态
- `GET /api/v1/monitoring/performance/metrics` - 性能指标
- `GET /api/v1/monitoring/turbines/status` - 风机状态概览

### 健康检查
- `GET /health` - 基础健康检查
- `GET /health/detailed` - 详细健康检查
- `GET /health/ready` - 就绪检查
- `GET /health/live` - 存活检查

## 快速开始

### 环境要求
- Docker 20.10+
- Docker Compose 1.29+
- Python 3.11+ (用于本地开发)

### Docker部署

1. 克隆项目并进入SCADA服务目录：
```bash
cd wind-power-microservices/services/scada-service
```

2. 启动所有服务：
```bash
docker-compose up -d
```

3. 验证服务状态：
```bash
# 检查健康状态
curl http://localhost:8002/health

# 查看API文档
curl http://localhost:8002/api/docs
```

### 本地开发

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件配置数据库等连接信息
```

3. 运行服务：
```bash
python -m src.main
```

## 配置说明

### 环境变量

#### 数据库配置
- `DATABASE_URL`: PostgreSQL连接字符串
- `INFLUXDB_URL`: InfluxDB服务器地址
- `INFLUXDB_TOKEN`: InfluxDB认证令牌
- `INFLUXDB_ORG`: InfluxDB组织名称
- `INFLUXDB_BUCKET`: InfluxDB存储桶名称

#### 消息队列配置
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka服务器地址
- `KAFKA_TOPICS_SCADA_REALTIME`: 实时数据主题
- `KAFKA_TOPICS_SCADA_ALARMS`: 报警数据主题
- `KAFKA_TOPICS_SCADA_EVENTS`: 事件数据主题

#### SCADA协议配置
- `IEC104_PORT`: IEC 104协议默认端口
- `MAX_CONNECTIONS_PER_WIND_FARM`: 每风电场最大连接数
- `CONNECTION_TIMEOUT`: 连接超时时间
- `RECONNECT_DELAY`: 重连延迟时间

## 数据模型

### SCADA连接
```json
{
  "id": "conn-001",
  "name": "Wind Farm A SCADA",
  "protocol": "iec104",
  "host": "192.168.1.100",
  "port": 2404,
  "status": "connected",
  "wind_farm_id": "wf-001",
  "configuration": {
    "connection_timeout": 30,
    "max_reconnect_attempts": 5,
    "reconnect_delay": 10
  }
}
```

### 数据点
```json
{
  "id": "dp-001",
  "point_id": "WT001.Power",
  "point_name": "风机1功率",
  "connection_id": "conn-001",
  "wind_farm_id": "wf-001",
  "turbine_id": "WT001",
  "point_type": "analog",
  "unit": "MW",
  "scaling_factor": 0.001,
  "alarm_thresholds": {
    "high_alarm": 2.8,
    "high_high_alarm": 3.0,
    "low_alarm": 0.1
  }
}
```

### 实时数据
```json
{
  "point_id": "WT001.Power",
  "value": 2.35,
  "quality": "good",
  "timestamp": "2024-01-15T10:30:00Z",
  "wind_farm_id": "wf-001",
  "turbine_id": "WT001",
  "connection_id": "conn-001"
}
```

### 报警
```json
{
  "id": "alarm-001",
  "alarm_code": "HIGH_POWER",
  "severity": "warning",
  "description": "风机功率超过阈值",
  "wind_farm_id": "wf-001",
  "turbine_id": "WT001",
  "triggered_at": "2024-01-15T10:30:00Z",
  "status": "active",
  "is_acknowledged": false
}
```

## 监控和运维

### 健康检查
服务提供多层次的健康检查端点：
- `/health`: 基础健康检查
- `/health/detailed`: 详细组件状态
- `/health/ready`: Kubernetes就绪探针
- `/health/live`: Kubernetes存活探针

### 日志管理
- 结构化日志输出
- 支持日志级别配置
- 集成日志聚合系统

### 性能监控
- 实时性能指标收集
- 数据质量监控
- 连接状态监控
- 自定义仪表板支持

## 安全特性

### 认证授权
- JWT令牌认证
- 基于角色的访问控制
- API速率限制

### 数据安全
- 数据传输加密
- 敏感信息脱敏
- 审计日志记录

## 扩展性

### 水平扩展
- 无状态服务设计
- 支持容器编排
- 负载均衡支持

### 协议扩展
- 插件化协议适配器
- 支持Modbus TCP、DNP3等协议
- 自定义协议开发

## 故障排除

### 常见问题

1. **连接失败**
   - 检查网络连通性
   - 验证SCADA服务器配置
   - 查看连接日志

2. **数据质量问题**
   - 检查数据源状态
   - 验证数据点配置
   - 查看质量统计

3. **性能问题**
   - 监控系统资源使用
   - 优化数据处理参数
   - 调整并发连接数

### 调试工具
- API测试界面 (Swagger UI)
- WebSocket测试工具
- 实时监控仪表板
- 日志分析工具

## 开发指南

### 编码规范
- 遵循PEP 8规范
- 类型注解完整
- 异步编程模式
- 错误处理完善

### 测试策略
- 单元测试覆盖
- 集成测试验证
- 性能测试评估
- 端到端测试

### 贡献指南
1. Fork项目仓库
2. 创建功能分支
3. 提交代码变更
4. 发起Pull Request

## 许可证

本项目采用MIT许可证 - 详见 [LICENSE](../../LICENSE) 文件

## 支持

如有问题或建议，请通过以下方式联系：
- 创建Issue
- 发送邮件
- 技术文档

## 更新日志

### v1.0.0 (2024-01-15)
- ✨ 初始版本发布
- ✨ IEC 60870-5-104协议支持
- ✨ 多风电场连接管理
- ✨ 实时数据处理引擎
- ✨ 完整的API接口
- ✨ Docker容器化
- ✨ 监控和报警系统