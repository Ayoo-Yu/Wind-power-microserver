# Meteorological Data Service

气象数据服务是风电功率预测系统的重要组成部分，负责收集、处理和分析气象数据。该服务集成多个气象数据源，提供天气预报、数据质量控制和气象预警功能。

## 功能特性

### 🌤️ 多数据源集成
- **OpenWeatherMap**: 全球天气数据API
- **WeatherAPI**: 详细天气预报服务
- **NOAA**: 美国国家海洋和大气管理局数据
- **传感器数据**: 支持本地气象传感器
- **手动数据**: 支持人工数据录入

### 📊 数据处理与质量控制
- **实时数据验证**: 多维度数据质量检查
- **异常检测**: 统计方法识别异常值
- **数据插值**: 缺失数据智能填补
- **单位转换**: 自动单位标准化

### 🔮 天气预报服务
- **多模型预报**: 集成多种预报算法
- **集合预报**: 多模型融合提高准确性
- **短期/长期预报**: 支持不同时效预报
- **预报评估**: 准确性评估和验证

### ⚠️ 气象预警
- **实时预警**: 自动获取气象部门预警
- **分级管理**: 按严重程度分级处理
- **影响评估**: 评估对风电场运营影响
- **智能推荐**: 提供运营建议

## 技术架构

### 核心技术栈
- **FastAPI**: 异步Web框架
- **PostgreSQL**: 关系型数据库
- **Redis**: 缓存和会话管理
- **Apache Kafka**: 消息队列
- **Scikit-learn**: 机器学习算法
- **Pandas/NumPy**: 数据处理
- **Docker**: 容器化部署

### 服务架构
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   OpenWeather   │    │   WeatherAPI    │    │      NOAA       │
│      Map        │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │ REST APIs            │ REST APIs            │ REST APIs
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Weather API Client    │
                    │  (Rate Limiting, Auth)  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Meteorological Manager │
                    │   (Orchestration Hub)   │
                    └────────────┬────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                    │
    ┌───────▼───────┐   ┌────────▼────────┐   ┌──────▼──────┐
    │ Data Processor│   │  Forecast Service│   │Alert Service│
    │ (Validation)  │   │  (ML Models)     │   │ (Monitoring)│
    └───────────────┘   └─────────────────┘   └─────────────┘
```

## API 端点

### 气象站点管理
- `POST /api/v1/weather-stations` - 创建气象站点
- `GET /api/v1/weather-stations/{station_id}` - 获取站点详情
- `PUT /api/v1/weather-stations/{station_id}` - 更新站点配置
- `POST /api/v1/weather-stations/{station_id}/activate` - 激活站点
- `GET /api/v1/weather-stations/by-wind-farm/{wind_farm_id}` - 按风电场获取站点

### 实时气象数据
- `GET /api/v1/weather-data/current` - 获取当前气象数据
- `GET /api/v1/weather-data/by-station/{station_id}` - 按站点获取数据
- `GET /api/v1/weather-data/by-wind-farm/{wind_farm_id}` - 按风电场获取数据
- `POST /api/v1/weather-data/simulate` - 生成模拟数据

### 天气预报
- `GET /api/v1/forecasts/current` - 获取当前预报
- `POST /api/v1/forecasts/generate` - 生成新预报
- `GET /api/v1/forecasts/by-station/{station_id}` - 按站点获取预报
- `GET /api/v1/forecasts/accuracy/{station_id}` - 获取预报准确性

### 气象预警
- `GET /api/v1/alerts/active` - 获取活跃预警
- `GET /api/v1/alerts/by-wind-farm/{wind_farm_id}` - 按风电场获取预警
- `GET /api/v1/alerts/summary` - 获取预警汇总
- `POST /api/v1/alerts/impact-assessment` - 评估预警影响

### 系统监控
- `GET /api/v1/monitoring/status` - 系统状态
- `GET /api/v1/monitoring/data-quality` - 数据质量监控
- `GET /api/v1/monitoring/forecast-accuracy` - 预报准确性
- `GET /api/v1/monitoring/api-health` - API健康状况

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

1. 克隆项目并进入气象服务目录：
```bash
cd wind-power-microservices/services/meteorological-service
```

2. 启动所有服务：
```bash
docker-compose up -d
```

3. 验证服务状态：
```bash
# 检查健康状态
curl http://localhost:8003/health

# 查看API文档
curl http://localhost:8003/api/docs
```

### 本地开发

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件配置API密钥等
```

3. 运行服务：
```bash
python -m src.main
```

## 配置说明

### 环境变量

#### 数据库配置
- `DATABASE_URL`: PostgreSQL连接字符串
- `REDIS_URL`: Redis连接字符串

#### 天气API配置
- `OPENWEATHERMAP_API_KEY`: OpenWeatherMap API密钥
- `WEATHERAPI_KEY`: WeatherAPI密钥
- `NOAA_API_KEY`: NOAA API密钥
- `WEATHER_API_ENABLED`: 启用天气API集成
- `WEATHER_API_SOURCES`: 启用的数据源列表

#### 预报设置
- `FORECAST_HOURS`: 预报时数（默认72小时）
- `FORECAST_UPDATE_INTERVAL`: 预报更新间隔（秒）

#### 数据收集设置
- `WEATHER_DATA_COLLECTION_INTERVAL`: 数据收集间隔（秒）
- `HISTORICAL_DATA_RETENTION_DAYS`: 历史数据保留天数

## 数据模型

### 气象站点
```json
{
  "id": "station-001",
  "name": "Wind Farm A Weather Station",
  "code": "WF-A-WS-01",
  "wind_farm_id": "wf-001",
  "latitude": 39.9042,
  "longitude": 116.4074,
  "elevation": 50,
  "source": "weatherapi",
  "is_active": true,
  "description": "Primary weather station for Wind Farm A"
}
```

### 气象数据
```json
{
  "id": "data-001",
  "station_id": "station-001",
  "wind_farm_id": "wf-001",
  "parameter": "wind_speed",
  "value": 8.5,
  "unit": "m/s",
  "timestamp": "2024-01-15T10:30:00Z",
  "source": "weatherapi",
  "quality": "good"
}
```

### 天气预报
```json
{
  "id": "forecast-001",
  "station_id": "station-001",
  "wind_farm_id": "wf-001",
  "forecast_time": "2024-01-16T12:00:00Z",
  "forecast_hours": 24,
  "parameters": {
    "temperature": 15.2,
    "wind_speed": 7.8,
    "wind_direction": 245,
    "pressure": 1013.2,
    "humidity": 65
  },
  "source": "ensemble",
  "model_version": "ml_regression"
}
```

### 气象预警
```json
{
  "id": "alert-001",
  "alert_id": "NOAA-WIND-001",
  "title": "High Wind Warning",
  "description": "Sustained winds of 40+ mph expected",
  "severity": "severe",
  "wind_farm_id": "wf-001",
  "effective_time": "2024-01-15T18:00:00Z",
  "expires_time": "2024-01-16T06:00:00Z",
  "areas": ["Northern Region"],
  "source": "noaa",
  "status": "active"
}
```

## 预报算法

### 1. 持续性模型 (Persistence)
- 基于最近观测值的简单外推
- 适用于短期预报（0-6小时）
- 置信度随时间递减

### 2. 气候学模型 (Climatology)
- 基于历史同期数据的统计模型
- 适用于长期趋势预报
- 考虑季节性变化

### 3. 机器学习回归模型
- 使用历史数据训练回归模型
- 集成多种气象参数
- 支持特征工程和时间序列分析

### 4. 集合预报 (Ensemble)
- 融合多个模型的预报结果
- 加权平均提高准确性
- 提供置信区间估计

## 质量控制

### 数据验证
- **范围检查**: 参数值是否在合理范围内
- **变化率检查**: 参数变化是否过快
- **持续性检查**: 数据是否长时间不变
- **统计异常检测**: 基于Z-score的异常值识别

### 空间一致性
- **邻近站点比较**: 与周边站点数据对比
- **梯度检查**: 空间变化是否合理
- **插值验证**: 使用空间插值验证数据

## 监控和运维

### 系统健康
- **API连通性**: 外部API服务状态监控
- **数据收集**: 数据收集成功率统计
- **预报准确性**: 预报误差跟踪
- **系统性能**: 响应时间和吞吐量监控

### 数据质量
- **完整性**: 数据缺失率统计
- **准确性**: 与观测数据对比验证
- **及时性**: 数据更新延迟监控
- **一致性**: 多数据源一致性检查

## 安全特性

### 认证授权
- **JWT令牌**: 无状态身份认证
- **角色权限**: 基于角色的访问控制
- **API限流**: 防止API滥用
- **数据加密**: 敏感数据传输加密

### 数据保护
- **输入验证**: 严格的数据输入验证
- **SQL注入防护**: 参数化查询
- **XSS防护**: 输出编码
- **审计日志**: 操作记录追踪

## 扩展性

### 水平扩展
- **无状态设计**: 支持多实例部署
- **负载均衡**: 自动负载分发
- **容器编排**: Kubernetes支持
- **自动扩缩容**: 基于负载自动调整

### 数据源扩展
- **插件架构**: 支持新数据源插件
- **配置驱动**: 数据源配置化管理
- **API适配器**: 统一API接口
- **数据标准化**: 统一数据格式

## 故障排除

### 常见问题

1. **API连接失败**
   - 检查API密钥配置
   - 验证网络连通性
   - 查看API服务状态
   - 检查速率限制

2. **数据质量问题**
   - 检查数据源状态
   - 验证传感器校准
   - 查看质量控制日志
   - 分析历史数据趋势

3. **预报准确性低**
   - 增加训练数据量
   - 调整模型参数
   - 检查特征工程
   - 验证数据完整性

### 调试工具
- **API测试界面**: Swagger UI
- **数据可视化**: 实时图表展示
- **日志分析**: 结构化日志查询
- **性能监控**: 系统指标仪表板

## 性能优化

### 缓存策略
- **Redis缓存**: 热点数据缓存
- **预报缓存**: 预报结果缓存
- **API响应缓存**: 外部API响应缓存
- **数据库查询优化**: 索引和查询优化

### 并发处理
- **异步IO**: 异步数据收集
- **连接池**: 数据库连接复用
- **批量处理**: 批量数据操作
- **并行计算**: 多模型并行预报

## 更新日志

### v1.0.0 (2024-01-15)
- ✨ 初始版本发布
- ✨ 多数据源集成（OpenWeatherMap, WeatherAPI, NOAA）
- ✨ 实时数据质量控制
- ✨ 多模型天气预报
- ✨ 气象预警系统
- ✨ 完整API接口
- ✨ Docker容器化
- ✨ 机器学习预报算法

### 开发路线图
- **v1.1.0**: 雷达数据集成
- **v1.2.0**: 卫星数据融合
- **v1.3.0**: 高级机器学习模型
- **v1.4.0**: 实时数据流处理
- **v1.5.0**: 多语言支持