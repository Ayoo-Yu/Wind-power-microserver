# 风电功率预测系统 - 监控系统部署指南

## 📋 概述

本监控系统为风电功率预测系统提供完整的日志收集、性能监控和可视化分析能力。

## 🏗️ 系统架构

### 核心组件
- **ELK Stack**: 日志收集和分析
  - Elasticsearch: 日志存储和搜索
  - Logstash: 日志处理和转换
  - Kibana: 日志可视化

- **Prometheus + Grafana**: 性能监控
  - Prometheus: 指标收集和存储
  - Grafana: 监控仪表板
  - Node Exporter: 系统指标收集

## 🚀 快速启动

### 1. 启动监控系统
```bash
# 在项目根目录执行
docker-compose -f docker-compose.monitoring.yml up -d
```

### 2. 验证服务状态
```bash
# 检查所有服务状态
docker-compose -f docker-compose.monitoring.yml ps

# 查看服务日志
docker-compose -f docker-compose.monitoring.yml logs -f
```

### 3. 访问Web界面
- **Kibana**: http://localhost:5601
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090

## 📊 监控仪表板

### Grafana预配置仪表板
1. **系统总览** (`/grafana/provisioning/dashboards/json/system-overview.json`)
   - 系统状态监控
   - CPU/内存使用率
   - HTTP请求统计
   - 数据库连接状态
   - 错误率监控

### 自定义仪表板
1. 登录Grafana
2. 导入预配置仪表板
3. 根据需要调整面板配置

## 🔧 应用集成

### 1. 后端服务配置
应用已集成Prometheus指标收集器，提供以下指标：

- HTTP请求统计
- 数据库操作计数
- 预测任务执行状态
- 数据上传统计
- 系统资源使用率

**指标端点**: `http://localhost:5000/metrics`

### 2. 日志收集配置
应用日志已配置为结构化格式，支持以下输出方式：

- **Filebeat**: 文件日志收集
- **Logstash TCP**: 实时日志传输
- **HTTP API**: 程序化日志推送

## 📝 日志查询示例

### Kibana查询示例
```javascript
// 查询特定服务的错误日志
app_name: "backend" AND level: "ERROR"

// 查询预测任务相关日志
message: "prediction" AND farm_code: "DEFAULT_FARM"

// 查询数据库操作慢查询
message: "database" AND duration: >1000
```

### 常用搜索模式
- `app_name: "backend"` - 后端服务日志
- `level: "ERROR"` - 错误级别日志
- `farm_code: "DEFAULT_FARM"` - 特定风场日志
- `message: "upload"` - 数据上传相关日志

## 🎯 告警配置

### Prometheus告警规则
```yaml
# alerts.yml
groups:
  - name: wind_power_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
```

### 常用告警指标
- **服务可用性**: `up{job="backend_service"} == 0`
- **错误率**: `rate(http_requests_total{status=~"5.."}[5m]) > 0.05`
- **响应时间**: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1`
- **数据库连接**: `pg_stat_database_numbackends > 100`

## 🔍 故障排查

### 常见问题

#### 1. Elasticsearch无法启动
```bash
# 检查内存限制
docker logs elasticsearch

# 检查数据目录权限
ls -la elasticsearch_data/
```

#### 2. Logstash连接失败
```bash
# 检查Logstash配置
docker logs logstash

# 验证Elasticsearch连接
curl http://localhost:9200/_cluster/health
```

#### 3. Grafana数据源连接失败
```bash
# 检查Prometheus状态
curl http://localhost:9090/api/v1/query?query=up

# 检查Grafana配置
docker logs grafana
```

### 性能优化

#### Elasticsearch优化
```yaml
# docker-compose.monitoring.yml 中调整
environment:
  - "ES_JAVA_OPTS=-Xms2g -Xmx2g"  # 根据系统内存调整
```

#### Prometheus优化
```yaml
# 调整数据保留时间
command:
  - '--storage.tsdb.retention.time=200h'
```

## 📈 扩展功能

### 1. 添加更多监控指标
- 业务指标监控
- 用户行为分析
- 预测准确性追踪

### 2. 集成告警通知
- 邮件通知
- 钉钉/企业微信
- 短信通知

### 3. 日志分析增强
- 机器学习异常检测
- 日志模式识别
- 智能故障诊断

## 🛠️ 维护操作

### 数据备份
```bash
# 备份Elasticsearch数据
docker exec elasticsearch curl -X PUT "localhost:9200/_snapshot/backup/snapshot_1"

# 备份Grafana配置
docker cp grafana:/var/lib/grafana/grafana.db ./grafana-backup.db
```

### 系统更新
```bash
# 停止服务
docker-compose -f docker-compose.monitoring.yml down

# 更新镜像
docker-compose -f docker-compose.monitoring.yml pull

# 重新启动
docker-compose -f docker-compose.monitoring.yml up -d
```

### 清理数据
```bash
# 清理旧数据
docker volume prune

# 重置特定服务
docker-compose -f docker-compose.monitoring.yml restart elasticsearch
```

## 📞 技术支持

如遇到问题，请检查：
1. 服务日志: `docker-compose -f docker-compose.monitoring.yml logs [service]`
2. 系统资源: `docker stats`
3. 网络连接: `docker network ls`

---

**版本**: v1.0
**更新时间**: 2025-09-27
**维护团队**: Wind Power Forecast System Team