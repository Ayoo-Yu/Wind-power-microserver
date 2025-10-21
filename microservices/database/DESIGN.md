# 微服务数据库垂直拆分设计

## 数据库架构概述

### 1. 拆分策略
采用垂直拆分策略，将原有单体数据库按业务领域拆分为多个独立的数据库：

- **auth_db**: 用户认证和权限管理
- **data_db**: 数据采集和存储管理
- **prediction_db**: 预测模型和结果管理
- **report_db**: 上报和统计管理
- **simulation_db**: 物理仿真管理

### 2. 数据库配置

#### 2.1 认证数据库 (auth_db)
```sql
-- 数据库: windpower_auth
-- 用途: 用户管理、角色权限、会话管理

CREATE DATABASE windpower_auth;
```

**表结构**:
- `users` - 用户基本信息
- `roles` - 角色定义
- `permissions` - 权限定义
- `user_roles` - 用户角色关联
- `role_permissions` - 角色权限关联
- `sessions` - 会话管理
- `audit_logs` - 审计日志

#### 2.2 数据管理数据库 (data_db)
```sql
-- 数据库: windpower_data
-- 用途: 原始数据存储、数据处理、数据质量控制

CREATE DATABASE windpower_data;
```

**表结构**:
- `farms` - 风场信息
- `turbines` - 风机信息
- `wind_speed_data` - 风速数据
- `turbine_power_data` - 风机功率数据
- `weather_data` - 气象数据
- `data_quality_logs` - 数据质量日志
- `data_processing_tasks` - 数据处理任务

#### 2.3 预测数据库 (prediction_db)
```sql
-- 数据库: windpower_prediction
-- 用途: 预测模型、预测结果、模型训练

CREATE DATABASE windpower_prediction;
```

**表结构**:
- `prediction_models` - 预测模型
- `model_versions` - 模型版本
- `training_tasks` - 训练任务
- `prediction_results` - 预测结果
- `model_metrics` - 模型性能指标
- `hyperparameters` - 超参数

#### 2.4 上报数据库 (report_db)
```sql
-- 数据库: windpower_report
-- 用途: 上报数据、统计信息、调度任务

CREATE DATABASE windpower_report;
```

**表结构**:
- `report_tasks` - 上报任务
- `report_data` - 上报数据
- `report_templates` - 上报模板
- `schedules` - 调度配置
- `statistics` - 统计数据
- `error_logs` - 错误日志

#### 2.5 仿真数据库 (simulation_db)
```sql
-- 数据库: windpower_simulation
-- 用途: 物理仿真、场景模拟、参数优化

CREATE DATABASE windpower_simulation;
```

**表结构**:
- `simulation_scenarios` - 仿真场景
- `simulation_runs` - 仿真运行
- `simulation_results` - 仿真结果
- `physical_parameters` - 物理参数
- `optimization_tasks` - 优化任务

### 3. 数据同步策略

#### 3.1 共享数据表
对于需要在多个服务间共享的数据，采用以下策略：

1. **风场和风机信息**: 在 data_db 中维护，其他服务通过 API 获取
2. **用户会话**: 在 auth_db 中维护，通过 JWT token 进行验证
3. **配置信息**: 各服务独立维护，通过配置中心同步

#### 3.2 数据同步机制
- **实时同步**: 通过消息队列 (RabbitMQ) 实现跨服务数据更新
- **批量同步**: 定时任务批量同步数据
- **缓存同步**: 通过 Redis 缓存共享数据

### 4. 数据库连接配置

#### 4.1 连接池配置
```yaml
# 通用连接池配置
pool:
  max_connections: 20
  min_connections: 5
  max_idle_time: 300
  connection_timeout: 30
  connection_recycle_time: 3600
```

#### 4.2 读写分离
对于读多写少的表，配置读写分离：

- **主库**: 负责写操作
- **从库**: 负责读操作
- **中间件**: 使用 ProxySQL 或 MaxScale

### 5. 数据安全策略

#### 5.1 访问控制
- 每个微服务使用独立的数据库用户
- 严格限制数据库权限 (GRANT SELECT, INSERT, UPDATE, DELETE)
- 定期轮换数据库密码

#### 5.2 数据加密
- 敏感数据存储加密
- 数据库连接 SSL/TLS 加密
- 备份数据加密存储

#### 5.3 审计日志
- 记录所有数据库操作
- 定期审计访问日志
- 异常操作告警

### 6. 备份和恢复策略

#### 6.1 备份策略
- **全量备份**: 每天凌晨 2 点
- **增量备份**: 每小时
- **日志备份**: 每 15 分钟

#### 6.2 恢复策略
- **RTO**: 30 分钟内恢复
- **RPO**: 15 分钟内数据丢失
- **定期演练**: 每月进行恢复演练

### 7. 监控和性能优化

#### 7.1 性能监控
- 查询响应时间监控
- 连接池使用率监控
- 磁盘空间监控
- 慢查询分析

#### 7.2 索引优化
- 定期分析查询模式
- 优化索引策略
- 定期重建索引

### 8. 迁移计划

#### 8.1 阶段1: 数据库创建和表结构设计
- 创建 5 个独立的数据库
- 设计各数据库表结构
- 配置数据库连接

#### 8.2 阶段2: 数据迁移
- 从原数据库导出数据
- 按垂直拆分策略导入数据
- 验证数据完整性

#### 8.3 阶段3: 应用适配
- 修改微服务数据库连接配置
- 更新数据库操作代码
- 测试数据访问功能

#### 8.4 阶段4: 切换和验证
- 逐步切换流量到新数据库
- 监控系统性能
- 验证数据一致性