# 风功率预测系统 - 运维手册

## 目录
1. [日常运维](#日常运维)
2. [监控和告警](#监控和告警)
3. [故障处理](#故障处理)
4. [备份和恢复](#备份和恢复)
5. [性能优化](#性能优化)
6. [安全管理](#安全管理)
7. [系统升级](#系统升级)
8. [应急处理](#应急处理)

## 日常运维

### 每日检查清单

#### 系统状态检查 (08:00)
- [ ] 检查所有服务运行状态
- [ ] 查看系统资源使用情况
- [ ] 检查数据库连接状态
- [ ] 验证API网关健康状态
- [ ] 检查消息队列状态

#### 数据质量检查 (09:00)
- [ ] 检查气象数据完整性
- [ ] 验证功率预测精度
- [ ] 检查数据收集状态
- [ ] 确认无数据丢失

#### 报告生成检查 (10:00)
- [ ] 检查定时报告生成状态
- [ ] 验证报告分发功能
- [ ] 检查报告模板更新
- [ ] 确认报告数据准确性

#### 监控告警检查 (每2小时)
- [ ] 检查活跃告警
- [ ] 处理新产生的告警
- [ ] 更新告警处理状态
- [ ] 记录异常事件

### 每周检查清单 (周一)

#### 系统性能分析
- [ ] 生成周性能报告
- [ ] 分析系统瓶颈
- [ ] 检查资源使用趋势
- [ ] 评估容量需求

#### 安全检查
- [ ] 检查安全日志
- [ ] 更新安全补丁
- [ ] 验证访问控制
- [ ] 检查SSL证书状态

#### 备份验证
- [ ] 检查备份完整性
- [ ] 验证备份恢复功能
- [ ] 测试灾难恢复流程
- [ ] 更新备份策略

### 每月检查清单 (月初)

#### 系统维护
- [ ] 执行数据库维护
- [ ] 更新系统配置
- [ ] 清理过期日志
- [ ] 优化系统性能

#### 容量规划
- [ ] 分析增长趋势
- [ ] 评估扩容需求
- [ ] 更新容量计划
- [ ] 准备硬件升级

## 监控和告警

### 监控指标

#### 系统指标
```yaml
# CPU使用率
metric: cpu_usage_percentage
threshold: > 85%
duration: 5m
severity: warning

# 内存使用率
metric: memory_usage_percentage
threshold: > 90%
duration: 5m
severity: critical

# 磁盘使用率
metric: disk_usage_percentage
threshold: > 80%
duration: 10m
severity: warning

# 网络I/O
metric: network_io_rate
threshold: > 100MB/s
duration: 5m
severity: info
```

#### 应用指标
```yaml
# API响应时间
metric: api_response_time
threshold: > 2000ms
duration: 5m
severity: warning

# 错误率
metric: error_rate_percentage
threshold: > 5%
duration: 5m
severity: critical

# 请求吞吐量
metric: requests_per_second
threshold: < 100
duration: 10m
severity: warning

# 数据库连接数
metric: database_connections
threshold: > 80%
duration: 5m
severity: warning
```

#### 业务指标
```yaml
# 预测精度
metric: prediction_accuracy
threshold: < 80%
duration: 1h
severity: critical

# 数据完整性
metric: data_completeness
threshold: < 90%
duration: 30m
severity: warning

# 报告生成时间
metric: report_generation_time
threshold: > 300s
duration: 1h
severity: warning

# 用户活跃度
metric: user_activity
threshold: < 10
duration: 24h
severity: info
```

### 告警处理流程

#### 告警级别
1. **Critical (P1)** - 立即处理
   - 系统完全不可用
   - 数据丢失
   - 安全事件

2. **Warning (P2)** - 2小时内处理
   - 性能下降
   - 部分功能异常
   - 资源告警

3. **Info (P3)** - 24小时内处理
   - 一般性通知
   - 统计信息
   - 维护提醒

#### 告警响应
```bash
# 告警响应时间
P1 - 15分钟内响应
P2 - 2小时内响应
P3 - 24小时内响应

# 告警升级机制
未响应时间: 30分钟 → 升级至主管
未响应时间: 2小时 → 升级至经理
未响应时间: 4小时 → 升级至总监
```

### 监控工具访问

#### Grafana监控面板
- URL: http://localhost:3001
- 用户名: admin
- 密码: 查看环境变量 `GRAFANA_PASSWORD`

#### Kibana日志分析
- URL: http://localhost:5601
- 用户名: elastic
- 密码: 查看环境变量 `ELASTIC_PASSWORD`

#### Prometheus指标
- URL: http://localhost:9090
- 查询语言: PromQL

#### Jaeger链路追踪
- URL: http://localhost:16686
- 服务选择: wind-power-*

## 故障处理

### 常见故障及处理

#### 1. 服务无法启动
**症状**: 容器启动失败，健康检查不通过
**处理步骤**:
```bash
# 检查容器状态
docker ps -a | grep wind-power

# 查看容器日志
docker logs wind-power-service-name

# 检查依赖服务
docker-compose ps

# 重新启动服务
docker-compose restart service-name
```

#### 2. 数据库连接失败
**症状**: 应用报数据库连接错误
**处理步骤**:
```bash
# 检查数据库服务
docker-compose exec postgres pg_isready

# 检查连接参数
docker-compose config | grep DATABASE_URL

# 测试连接
docker-compose exec postgres psql -U postgres -d wind_power

# 重启数据库
docker-compose restart postgres
```

#### 3. API响应缓慢
**症状**: 响应时间超过2秒
**处理步骤**:
```bash
# 检查系统资源
docker stats

# 检查数据库性能
docker-compose exec postgres psql -c "SELECT * FROM pg_stat_activity;"

# 检查慢查询
docker-compose exec postgres psql -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# 检查API网关
kubectl logs deployment/kong -n wind-power
```

#### 4. 预测精度下降
**症状**: 预测精度低于80%
**处理步骤**:
```bash
# 检查数据源
kubectl logs deployment/meteorological-service -n wind-power

# 检查模型状态
kubectl logs deployment/power-prediction-service -n wind-power

# 验证数据质量
curl -X GET "http://api-gateway:8000/api/v1/data/quality"

# 重新训练模型
kubectl apply -f k8s/ml-model-retrain-job.yaml
```

#### 5. 报告生成失败
**症状**: 定时报告未生成或生成错误
**处理步骤**:
```bash
# 检查报告服务状态
kubectl logs deployment/report-service -n wind-power

# 检查调度器
kubectl logs deployment/report-service -n wind-power | grep scheduler

# 检查邮件服务
docker-compose logs notification-service

# 手动触发报告
curl -X POST "http://api-gateway:8000/api/v1/reports/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "test-report", "type": "operational"}'
```

### 故障升级流程

#### 一级故障 (L1) - 运维团队处理
- 服务重启
- 配置调整
- 资源扩容
- 日志分析

#### 二级故障 (L2) - 开发团队处理
- 代码问题
- 数据库问题
- 性能优化
- 模型调整

#### 三级故障 (L3) - 架构团队处理
- 系统架构问题
- 基础设施问题
- 安全事件
- 重大故障

### 故障记录和报告

#### 故障记录模板
```yaml
故障编号: INC-2024-001
发生时间: 2024-01-15 14:30:00
报告人: 张三
故障级别: P1
影响范围: 全系统

症状描述:
- API响应时间超过5秒
- 数据库连接数达到上限
- 用户无法正常访问系统

处理过程:
14:35 - 发现问题，开始排查
14:40 - 确认数据库连接池耗尽
14:45 - 重启数据库服务
14:50 - 调整连接池配置
15:00 - 系统恢复正常

根因分析:
数据库连接池配置过小，在高并发情况下连接数耗尽

解决方案:
1. 增加连接池大小
2. 优化数据库查询
3. 添加连接监控

预防措施:
- 定期检查数据库连接使用情况
- 优化慢查询
- 添加连接池监控告警
```

## 备份和恢复

### 备份策略

#### 数据库备份
```bash
# 每日全量备份
0 2 * * * /scripts/backup-database-full.sh

# 每小时增量备份
0 * * * * /scripts/backup-database-incremental.sh

# 实时归档备份
archive_timeout = 5min
```

#### 应用数据备份
```bash
# 配置文件备份
0 3 * * * /scripts/backup-configs.sh

# 日志文件备份
0 4 * * * /scripts/backup-logs.sh

# 报告文件备份
0 5 * * * /scripts/backup-reports.sh
```

#### 系统状态备份
```bash
# Kubernetes配置备份
0 6 * * * /scripts/backup-k8s-configs.sh

# Docker Compose配置备份
0 7 * * * /scripts/backup-docker-configs.sh

# SSL证书备份
0 8 * * 1 /scripts/backup-certificates.sh
```

### 备份验证

#### 自动验证脚本
```bash
#!/bin/bash
# backup-validation.sh

# 检查备份文件完整性
for backup in /backups/*.sql; do
    if ! pg_restore --list "$backup" > /dev/null 2>&1; then
        echo "ERROR: Backup file $backup is corrupted"
        # 发送告警
    fi
done

# 检查备份文件大小
min_size=10485760  # 10MB
for backup in /backups/*.sql; do
    size=$(stat -c%s "$backup")
    if [ $size -lt $min_size ]; then
        echo "WARNING: Backup file $backup is too small"
    fi
done
```

### 灾难恢复

#### 数据库恢复
```bash
#!/bin/bash
# database-recovery.sh

# 停止相关服务
docker-compose stop meteorological-service power-prediction-service

# 恢复数据库
docker-compose exec -T postgres psql -U postgres -d wind_power \u003c /backups/latest-full-backup.sql

# 恢复增量备份
if [ -f "/backups/latest-incremental-backup.sql" ]; then
    docker-compose exec -T postgres psql -U postgres -d wind_power \u003c /backups/latest-incremental-backup.sql
fi

# 重启服务
docker-compose start meteorological-service power-prediction-service

# 验证恢复
./scripts/verify-recovery.sh
```

#### 完整系统恢复
```bash
#!/bin/bash
# system-recovery.sh

# 1. 恢复基础设施
docker-compose up -d postgres redis rabbitmq

# 2. 等待基础设施就绪
./scripts/wait-for-services.sh

# 3. 恢复数据库
./scripts/restore-database.sh

# 4. 恢复应用配置
cp -r /backups/configs/* ./config/

# 5. 启动应用服务
docker-compose up -d

# 6. 验证系统状态
./scripts/verify-system-status.sh

# 7. 更新监控配置
kubectl apply -f k8s/monitoring/
```

### 恢复时间目标 (RTO)

| 故障类型 | RTO | 恢复方法 |
|---------|-----|----------|
| 服务故障 | 5分钟 | 自动重启 |
| 数据库故障 | 30分钟 | 备份恢复 |
| 系统故障 | 2小时 | 完整恢复 |
| 灾难故障 | 24小时 | 异地恢复 |

### 恢复点目标 (RPO)

| 数据类型 | RPO | 备份频率 |
|---------|-----|----------|
| 业务数据 | 1小时 | 实时备份 |
| 配置数据 | 24小时 | 每日备份 |
| 日志数据 | 7天 | 每周备份 |
| 报告数据 | 24小时 | 每日备份 |

## 性能优化

### 数据库优化

#### 索引优化
```sql
-- 创建复合索引
CREATE INDEX CONCURRENTLY idx_weather_station_time
ON weather_data (station_id, measurement_time);

-- 创建部分索引
CREATE INDEX CONCURRENTLY idx_predictions_active
ON power_predictions (farm_id, prediction_time)
WHERE status = 'active';

-- 创建函数索引
CREATE INDEX CONCURRENTLY idx_weather_date
ON weather_data (DATE(measurement_time));
```

#### 查询优化
```sql
-- 分析查询计划
EXPLAIN ANALYZE SELECT * FROM weather_data
WHERE station_id = 'ST001'
AND measurement_time > CURRENT_DATE - INTERVAL '7 days';

-- 优化慢查询
-- 原查询 (执行时间: 2.3s)
SELECT * FROM weather_data w
JOIN power_predictions p ON w.station_id = p.station_id
WHERE w.measurement_time > CURRENT_DATE - INTERVAL '1 day';

-- 优化后 (执行时间: 0.2s)
SELECT w.*, p.* FROM weather_data w
JOIN power_predictions p ON w.station_id = p.station_id
WHERE w.measurement_time > CURRENT_DATE - INTERVAL '1 day'
AND w.station_id IN (SELECT station_id FROM active_stations);
```

#### 连接池优化
```javascript
// 数据库连接池配置
const pool = new Pool({
    host: process.env.DB_HOST,
    port: process.env.DB_PORT,
    database: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    max: 50,                    // 最大连接数
    min: 10,                    // 最小连接数
    acquire: 30000,             // 连接超时时间
    idle: 10000,                // 空闲超时时间
    evict: 1000,                // 淘汰间隔
    maxUses: 7500,              // 最大使用次数
    statementTimeout: 30000     // 查询超时时间
});
```

### 应用性能优化

#### 缓存策略
```javascript
// Redis缓存配置
const redis = require('redis');
const client = redis.createClient({
    host: process.env.REDIS_HOST,
    port: process.env.REDIS_PORT,
    password: process.env.REDIS_PASSWORD,
    retry_strategy: (options) => {
        if (options.error && options.error.code === 'ECONNREFUSED') {
            return new Error('Redis server connection refused');
        }
        if (options.total_retry_time > 1000 * 60 * 60) {
            return new Error('Redis retry time exhausted');
        }
        if (options.attempt > 10) {
            return undefined;
        }
        return Math.min(options.attempt * 100, 3000);
    }
});

// 缓存键命名规范
const cacheKeys = {
    weather: (stationId, date) => `weather:${stationId}:${date}`,
    predictions: (farmId, horizon) => `predictions:${farmId}:${horizon}`,
    reports: (reportId) => `reports:${reportId}`,
    system: (metric) => `system:${metric}`
};

// 缓存策略
const cacheStrategy = {
    weather: { ttl: 300 },      // 5分钟
    predictions: { ttl: 1800 }, // 30分钟
    reports: { ttl: 3600 },     // 1小时
    system: { ttl: 60 }         // 1分钟
};
```

#### 异步处理
```javascript
// 消息队列配置
const amqp = require('amqplib');

class MessageQueue {
    constructor() {
        this.connection = null;
        this.channel = null;
    }

    async connect() {
        try {
            this.connection = await amqp.connect(process.env.RABBITMQ_URL);
            this.channel = await this.connection.createChannel();

            // 声明队列
            await this.channel.assertQueue('weather-data', { durable: true });
            await this.channel.assertQueue('predictions', { durable: true });
            await this.channel.assertQueue('reports', { durable: true });

            // 设置预取计数
            await this.channel.prefetch(10);

            logger.info('Message queue connected successfully');
        } catch (error) {
            logger.error('Failed to connect to message queue:', error);
            throw error;
        }
    }

    async publishMessage(queue, message) {
        try {
            await this.channel.sendToQueue(
                queue,
                Buffer.from(JSON.stringify(message)),
                { persistent: true }
            );
            logger.info(`Message published to queue: ${queue}`);
        } catch (error) {
            logger.error(`Failed to publish message to ${queue}:`, error);
            throw error;
        }
    }

    async consumeMessages(queue, handler) {
        try {
            await this.channel.consume(queue, async (msg) => {
                if (msg) {
                    try {
                        const content = JSON.parse(msg.content.toString());
                        await handler(content);
                        this.channel.ack(msg);
                    } catch (error) {
                        logger.error(`Error processing message from ${queue}:`, error);
                        this.channel.nack(msg, false, true); // 重新排队
                    }
                }
            });
            logger.info(`Started consuming messages from queue: ${queue}`);
        } catch (error) {
            logger.error(`Failed to consume messages from ${queue}:`, error);
            throw error;
        }
    }
}
```

#### 数据库查询优化
```javascript
// 查询优化示例
class OptimizedQueries {
    // 使用分页和游标
    async getWeatherData(stationId, startDate, endDate, cursor = null, limit = 100) {
        const whereClause = {
            station_id: stationId,
            measurement_time: {
                [Op.between]: [startDate, endDate]
            }
        };

        if (cursor) {
            whereClause.id = { [Op.gt]: cursor };
        }

        return await WeatherData.findAll({
            where: whereClause,
            order: [['id', 'ASC']],
            limit: limit + 1, // 多取一条用于判断是否还有数据
            attributes: ['id', 'station_id', 'measurement_time', 'temperature', 'wind_speed']
        });
    }

    // 使用聚合查询
    async getDailyAggregates(stationId, date) {
        return await WeatherData.findAll({
            where: {
                station_id: stationId,
                measurement_time: {
                    [Op.gte]: date,
                    [Op.lt]: new Date(date.getTime() + 24 * 60 * 60 * 1000)
                }
            },
            attributes: [
                [sequelize.fn('DATE', sequelize.col('measurement_time')), 'date'],
                [sequelize.fn('AVG', sequelize.col('temperature')), 'avg_temperature'],
                [sequelize.fn('AVG', sequelize.col('wind_speed')), 'avg_wind_speed'],
                [sequelize.fn('MAX', sequelize.col('wind_speed')), 'max_wind_speed'],
                [sequelize.fn('MIN', sequelize.col('wind_speed')), 'min_wind_speed']
            ],
            group: [sequelize.fn('DATE', sequelize.col('measurement_time'))],
            order: [[sequelize.fn('DATE', sequelize.col('measurement_time')), 'ASC']]
        });
    }

    // 使用原始查询优化复杂查询
    async getComplexAnalysis(farmId, startDate, endDate) {
        const query = `
            SELECT
                f.name as farm_name,
                DATE(p.prediction_time) as date,
                AVG(p.predicted_power) as avg_predicted,
                AVG(a.actual_power) as avg_actual,
                AVG(ABS(p.predicted_power - a.actual_power)) as avg_error,
                (1 - AVG(ABS(p.predicted_power - a.actual_power)) / NULLIF(AVG(a.actual_power), 0)) * 100 as accuracy
            FROM power_predictions p
            JOIN farms f ON p.farm_id = f.id
            LEFT JOIN actual_power a ON p.farm_id = a.farm_id
                AND DATE(p.prediction_time) = DATE(a.measurement_time)
            WHERE p.farm_id = :farmId
                AND p.prediction_time BETWEEN :startDate AND :endDate
            GROUP BY f.name, DATE(p.prediction_time)
            ORDER BY date DESC
        `;

        return await sequelize.query(query, {
            type: sequelize.QueryTypes.SELECT,
            replacements: { farmId, startDate, endDate }
        });
    }
}
```

### 前端性能优化

#### 代码分割和懒加载
```javascript
// Vue Router 懒加载
const routes = [
    {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import(/* webpackChunkName: "dashboard" */ '@/views/Dashboard.vue')
    },
    {
        path: '/predictions',
        name: 'Predictions',
        component: () => import(/* webpackChunkName: "predictions" */ '@/views/Predictions.vue')
    },
    {
        path: '/reports',
        name: 'Reports',
        component: () => import(/* webpackChunkName: "reports" */ '@/views/Reports.vue')
    }
];

// 组件懒加载
export default {
    components: {
        ChartComponent: () => import('@/components/ChartComponent.vue'),
        DataTable: () => import('@/components/DataTable.vue')
    }
};
```

#### 数据缓存策略
```javascript
// Vuex 缓存管理
const store = new Vuex.Store({
    state: {
        cache: new Map(),
        cacheTimeout: 5 * 60 * 1000 // 5分钟
    },

    mutations: {
        SET_CACHE(state, { key, data, timestamp = Date.now() }) {
            state.cache.set(key, { data, timestamp });
        },

        CLEAR_CACHE(state, key) {
            state.cache.delete(key);
        },

        CLEAR_EXPIRED_CACHE(state) {
            const now = Date.now();
            for (const [key, value] of state.cache.entries()) {
                if (now - value.timestamp > state.cacheTimeout) {
                    state.cache.delete(key);
                }
            }
        }
    },

    actions: {
        async fetchDataWithCache({ state, commit }, { key, fetchFunction }) {
            const cached = state.cache.get(key);
            const now = Date.now();

            if (cached && (now - cached.timestamp < state.cacheTimeout)) {
                return cached.data;
            }

            const data = await fetchFunction();
            commit('SET_CACHE', { key, data, timestamp: now });
            return data;
        }
    }
});
```

## 安全管理

### 访问控制

#### 用户权限管理
```javascript
// 基于角色的访问控制 (RBAC)
const roles = {
    admin: {
        permissions: ['*'],
        description: '系统管理员'
    },
    operator: {
        permissions: [
            'read:weather',
            'read:predictions',
            'read:reports',
            'generate:reports',
            'update:settings'
        ],
        description: '运维操作员'
    },
    viewer: {
        permissions: [
            'read:weather',
            'read:predictions',
            'read:reports'
        ],
        description: '只读用户'
    }
};

// 权限检查中间件
function checkPermission(permission) {
    return (req, res, next) => {
        const user = req.user;
        const userRole = roles[user.role];

        if (!userRole) {
            return res.status(403).json({ error: 'Invalid user role' });
        }

        if (userRole.permissions.includes('*') ||
            userRole.permissions.includes(permission)) {
            return next();
        }

        return res.status(403).json({
            error: 'Insufficient permissions',
            required: permission
        });
    };
}
```

#### API安全
```javascript
// API限流配置
const rateLimit = require('express-rate-limit');

const securityConfig = {
    // 全局限流
    global: rateLimit({
        windowMs: 15 * 60 * 1000, // 15分钟
        max: 1000,
        message: 'Too many requests from this IP'
    }),

    // 严格限流 - 认证端点
    auth: rateLimit({
        windowMs: 15 * 60 * 1000,
        max: 5,
        skipSuccessfulRequests: true
    }),

    // 中等限流 - 数据查询
    data: rateLimit({
        windowMs: 15 * 60 * 1000,
        max: 300,
        keyGenerator: (req) => req.user?.id || req.ip
    }),

    // 宽松限流 - 只读接口
    readOnly: rateLimit({
        windowMs: 15 * 60 * 1000,
        max: 600,
        keyGenerator: (req) => req.user?.id || req.ip
    })
};

// 输入验证
const { body, validationResult } = require('express-validator');

const validationRules = {
    createReport: [
        body('name').isLength({ min: 1, max: 100 }).trim(),
        body('type').isIn(['operational', 'performance', 'financial', 'environmental']),
        body('format').isIn(['pdf', 'html', 'json', 'csv', 'xlsx']),
        body('parameters').optional().isObject()
    ],

    updateUser: [
        body('email').isEmail().normalizeEmail(),
        body('role').isIn(['admin', 'operator', 'viewer']),
        body('permissions').optional().isArray()
    ]
};
```

### 数据安全

#### 数据加密
```javascript
// 敏感数据加密
const crypto = require('crypto');

class DataEncryption {
    constructor() {
        this.algorithm = 'aes-256-gcm';
        this.key = Buffer.from(process.env.ENCRYPTION_KEY, 'hex');
        this.ivLength = 16;
        this.tagLength = 16;
    }

    encrypt(text) {
        const iv = crypto.randomBytes(this.ivLength);
        const cipher = crypto.createCipher(this.algorithm, this.key);
        cipher.setAAD(Buffer.from('wind-power-system'));

        let encrypted = cipher.update(text, 'utf8', 'hex');
        encrypted += cipher.final('hex');

        const tag = cipher.getAuthTag();

        return {
            iv: iv.toString('hex'),
            encrypted: encrypted,
            tag: tag.toString('hex')
        };
    }

    decrypt(encryptedData) {
        const decipher = crypto.createDecipher(this.algorithm, this.key);
        decipher.setAAD(Buffer.from('wind-power-system'));
        decipher.setAuthTag(Buffer.from(encryptedData.tag, 'hex'));

        let decrypted = decipher.update(encryptedData.encrypted, 'hex', 'utf8');
        decrypted += decipher.final('utf8');

        return decrypted;
    }
}

// 使用示例
const encryption = new DataEncryption();
const sensitiveData = encryption.encrypt('sensitive_information');
const decrypted = encryption.decrypt(sensitiveData);
```

#### 审计日志
```javascript
// 审计日志管理
class AuditLogger {
    constructor() {
        this.logger = winston.createLogger({
            level: 'info',
            format: winston.format.combine(
                winston.format.timestamp(),
                winston.format.json()
            ),
            transports: [
                new winston.transports.File({
                    filename: 'audit.log',
                    maxsize: 5242880, // 5MB
                    maxFiles: 5
                })
            ]
        });
    }

    logUserAction(userId, action, resource, result, details = {}) {
        this.logger.info('User Action', {
            userId,
            action,
            resource,
            result,
            details,
            timestamp: new Date().toISOString(),
            ip: details.ip || 'unknown',
            userAgent: details.userAgent || 'unknown'
        });
    }

    logSystemEvent(event, severity, details = {}) {
        this.logger.log({
            level: severity,
            message: 'System Event',
            event,
            details,
            timestamp: new Date().toISOString()
        });
    }
}
```

### 网络安全

#### 防火墙配置
```bash
#!/bin/bash
# firewall-setup.sh

# 清除现有规则
iptables -F
iptables -X

# 默认策略
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# 允许本地回环
iptables -A INPUT -i lo -j ACCEPT

# 允许已建立的连接
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# 允许SSH
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# 允许HTTP/HTTPS
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# 允许API网关
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
iptables -A INPUT -p tcp --dport 8443 -j ACCEPT

# 允许监控端口
iptables -A INPUT -p tcp --dport 3000 -j ACCEPT  # Grafana
iptables -A INPUT -p tcp --dport 5601 -j ACCEPT # Kibana
iptables -A INPUT -p tcp --dport 9090 -j ACCEPT # Prometheus

# 限制连接频率
iptables -A INPUT -p tcp --dport 80 -m limit --limit 25/minute --limit-burst 100 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -m limit --limit 25/minute --limit-burst 100 -j ACCEPT

# 防止DDoS
iptables -A INPUT -p tcp --dport 80 -m conntrack --ctstate NEW -m recent --set
iptables -A INPUT -p tcp --dport 80 -m conntrack --ctstate NEW -m recent --update --seconds 60 --hitcount 10 -j DROP

# 保存规则
iptables-save > /etc/iptables/rules.v4
```

#### SSL/TLS配置
```nginx
# Nginx SSL配置
server {
    listen 443 ssl http2;
    server_name api.windpower.com;

    ssl_certificate /etc/ssl/certs/windpower.crt;
    ssl_certificate_key /etc/ssl/private/windpower.key;

    # SSL安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;

    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;

    # 其他安全配置
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    location / {
        proxy_pass http://api-gateway:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 系统升级

### 升级策略

#### 滚动升级
```bash
#!/bin/bash
# rolling-update.sh

# 1. 备份当前版本
kubectl get deployments -n wind-power -o yaml > backup/deployments-backup.yaml

# 2. 更新镜像版本
for service in meteorological-service power-prediction-service data-service report-service notification-service; do
    echo "Updating $service..."
    kubectl set image deployment/$service $service=windpower/$service:v2.0.0 -n wind-power

    # 等待升级完成
    kubectl rollout status deployment/$service -n wind-power

    # 验证服务状态
    if ! kubectl get pods -n wind-power -l app=$service | grep -q "Running"; then
        echo "Error: $service failed to update"
        exit 1
    fi

    echo "$service updated successfully"
    sleep 30  # 等待服务稳定
done

# 3. 验证系统状态
./scripts/verify-system-status.sh

echo "Rolling update completed successfully"
```

#### 蓝绿部署
```yaml
# blue-green-deployment.yaml
apiVersion: v1
kind: Service
metadata:
  name: wind-power-service
spec:
  selector:
    app: wind-power
    version: green  # 切换blue/green
  ports:
  - port: 80
    targetPort: 3000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wind-power-green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: wind-power
      version: green
  template:
    metadata:
      labels:
        app: wind-power
        version: green
    spec:
      containers:
      - name: wind-power-app
        image: windpower/app:v2.0.0
        ports:
        - containerPort: 3000
```

### 升级检查清单

#### 升级前准备
- [ ] 完整系统备份
- [ ] 升级计划确认
- [ ] 回滚方案准备
- [ ] 测试环境验证
- [ ] 通知相关人员

#### 升级过程
- [ ] 监控系统状态
- [ ] 逐步执行升级
- [ ] 验证每个步骤
- [ ] 记录升级日志
- [ ] 处理升级问题

#### 升级后验证
- [ ] 功能测试
- [ ] 性能测试
- [ ] 安全检查
- [ ] 监控验证
- [ ] 用户通知

### 版本管理

#### 版本号规范
```
主版本号.次版本号.修订号 (如: 1.2.3)
- 主版本号: 不兼容的API修改
- 次版本号: 向下兼容的功能性新增
- 修订号: 向下兼容的问题修正
```

#### 版本发布流程
```bash
#!/bin/bash
# release-process.sh

# 1. 版本检查
CURRENT_VERSION=$(git describe --tags --abbrev=0)
echo "Current version: $CURRENT_VERSION"

# 2. 代码质量检查
npm run lint
npm run test
npm run security-check

# 3. 构建镜像
docker build -t windpower/app:$NEW_VERSION .
docker push windpower/app:$NEW_VERSION

# 4. 打标签
git tag -a $NEW_VERSION -m "Release version $NEW_VERSION"
git push origin $NEW_VERSION

# 5. 更新文档
./scripts/update-documentation.sh $NEW_VERSION

# 6. 发布通知
./scripts/send-release-notification.sh $NEW_VERSION
```

## 应急处理

### 应急预案

#### 系统完全不可用
**场景**: 所有服务都无法访问
**处理步骤**:
1. 立即通知应急小组
2. 启动备用系统
3. 检查基础设施状态
4. 执行紧急恢复程序
5. 通知相关用户

```bash
#!/bin/bash
# emergency-recovery.sh

echo "Starting emergency recovery..."

# 1. 检查基础设施
echo "Checking infrastructure..."
docker-compose ps
kubectl get nodes

# 2. 重启核心服务
echo "Restarting core services..."
docker-compose restart postgres redis rabbitmq
kubectl rollout restart deployment -n wind-power

# 3. 检查服务状态
echo "Checking service status..."
./scripts/health-check-all.sh

# 4. 恢复数据
echo "Restoring data if needed..."
./scripts/check-data-integrity.sh

# 5. 验证系统
echo "Validating system..."
./scripts/system-validation.sh

echo "Emergency recovery completed"
```

#### 数据丢失
**场景**: 重要业务数据丢失或损坏
**处理步骤**:
1. 立即停止相关服务
2. 评估数据丢失范围
3. 从备份恢复数据
4. 验证数据完整性
5. 恢复服务运行

#### 安全事件
**场景**: 系统遭受攻击或数据泄露
**处理步骤**:
1. 立即隔离受影响的系统
2. 收集攻击证据
3. 通知安全团队
4. 修复安全漏洞
5. 恢复系统服务
6. 进行安全审计

### 应急联系信息

#### 应急小组
- **组长**: 张三 (138-0000-0001)
- **副组长**: 李四 (138-0000-0002)
- **技术专家**: 王五 (138-0000-0003)
- **安全专家**: 赵六 (138-0000-0004)

#### 外部支持
- **云服务提供商**: 400-0000-0001
- **安全厂商**: 400-0000-0002
- **硬件厂商**: 400-0000-0003
- **网络运营商**: 400-0000-0004

### 应急演练

#### 演练计划
- **频率**: 每季度一次
- **时间**: 周末或非工作时间
- **范围**: 全体运维团队
- **类型**: 桌面演练 + 实战演练

#### 演练场景
1. 系统完全故障
2. 数据库损坏
3. 网络中断
4. 安全攻击
5. 自然灾害

#### 演练评估
- 响应时间评估
- 处理流程评估
- 团队协作评估
- 工具使用效果评估
- 改进建议收集

---

**手册版本**: 1.0.0
**更新日期**: 2024年
**维护团队**: 风功率预测系统运维团队
**下次更新**: 2024年Q2

**重要提醒**:
- 本手册应定期更新，确保内容准确性
- 新员工入职必须学习本手册
- 应急联系信息应保持最新
- 定期进行运维培训和演练