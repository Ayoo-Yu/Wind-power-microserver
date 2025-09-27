# 运维人员快速参考指南

## 日常运维检查清单

### 🌅 每日检查 (08:00)

#### 系统状态检查
```bash
# 1. 检查所有服务运行状态
docker-compose ps

# 2. 查看系统资源使用情况
docker stats --no-stream

# 3. 检查数据库连接
docker-compose exec postgres pg_isready -U postgres

# 4. 验证API服务健康状态
curl -f http://localhost:5000/health && echo "API OK" || echo "API FAIL"

# 5. 检查Redis连接
docker-compose exec redis redis-cli ping
```

#### 数据质量检查 (09:00)
```bash
# 1. 检查数据收集状态
docker-compose logs --since="1 hour" scada-service

# 2. 验证气象数据完整性
curl -s http://localhost:5000/api/data/status | jq '.data.weather_data'

# 3. 检查预测精度
# 查看昨日预测精度
curl -s "http://localhost:5000/api/predictions/accuracy?date=$(date -d yesterday +%Y-%m-%d)" | jq '.data'

# 4. 确认无数据丢失
docker-compose exec postgres psql -U postgres -d windpower -c "
  SELECT COUNT(*) as record_count,
         MIN(timestamp) as earliest,
         MAX(timestamp) as latest
  FROM weather_data
  WHERE timestamp >= CURRENT_DATE - INTERVAL '1 day';"
```

#### 报告生成检查 (10:00)
```bash
# 1. 检查定时报告生成状态
docker-compose logs --since="1 hour" report-service | grep -i "report generated"

# 2. 验证报告文件完整性
ls -la /app/reports/$(date +%Y%m%d)/

# 3. 检查报告分发状态
curl -s http://localhost:5000/api/reports/status | jq '.data.delivery_status'
```

#### 监控告警检查 (每2小时)
```bash
# 1. 检查活跃告警
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts'

# 2. 查看系统告警日志
docker-compose logs --since="2 hours" | grep -i "error\|warn\|critical"

# 3. 检查Grafana仪表板状态
curl -s -u admin:admin http://localhost:3000/api/health
```

### 📅 每周检查 (周一)

#### 系统性能分析
```bash
# 1. 生成周性能报告
# CPU使用率
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}"

# 内存使用率
docker stats --no-stream --format "table {{.Name}}\t{{.MemPerc}}\t{{.MemUsage}}"

# 磁盘使用率
df -h /var/lib/docker

# 2. 分析API响应时间
curl -s http://localhost:9090/api/v1/query?query=http_request_duration_seconds_quantile | jq '.data.result'
```

#### 安全检查
```bash
# 1. 检查系统更新
apt list --upgradable | wc -l

# 2. 检查Docker镜像更新
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}" | grep windpower

# 3. 检查异常登录
last -n 50 | grep -v "reboot"

# 4. 检查文件权限
find /app -type f -perm /002 -ls
```

### 📊 每月维护任务

#### 数据备份验证
```bash
# 1. 检查备份文件完整性
ls -la /backup/postgres/
gunzip -t /backup/postgres/backup_*.sql.gz

# 2. 验证备份恢复测试
# 创建测试数据库
docker exec postgres createdb -U postgres test_restore
# 恢复备份
gunzip -c /backup/postgres/backup_latest.sql.gz | docker exec -i postgres psql -U postgres test_restore

# 3. 清理旧备份
find /backup -name "backup_*.sql.gz" -mtime +30 -delete
```

#### 系统优化
```bash
# 1. 清理Docker镜像
docker system prune -a -f --volumes

# 2. 清理日志文件
docker-compose logs --tail=1000 > /var/log/windpower-$(date +%Y%m).log
docker-compose exec api logrotate -f /etc/logrotate.conf

# 3. 数据库优化
docker-compose exec postgres vacuumdb -U postgres -d windpower -z
```

## 故障处理快速指南

### 🔴 紧急故障处理

#### 1. 服务完全不可用
```bash
#!/bin/bash
# emergency-restart.sh

echo "开始紧急重启..."

# 1. 停止所有服务
docker-compose down

# 2. 检查系统资源
free -h
df -h

# 3. 清理临时文件
rm -rf /tmp/windpower-*

# 4. 重启基础服务
docker-compose up -d postgres redis
sleep 30

# 5. 重启应用服务
docker-compose up -d api frontend

# 6. 验证服务状态
sleep 10
curl -f http://localhost:5000/health

if [ $? -eq 0 ]; then
    echo "服务重启成功"
else
    echo "服务重启失败，需要人工干预"
    # 发送告警
    echo "WindPower系统故障，服务重启失败" | mail -s "紧急告警" admin@company.com
fi
```

#### 2. 数据库连接失败
```bash
# 检查数据库状态
docker-compose exec postgres pg_isready -U postgres

# 查看数据库日志
docker-compose logs --tail=50 postgres

# 重启数据库
docker-compose restart postgres

# 检查数据库连接池
docker-compose exec postgres psql -U postgres -d windpower -c "
SELECT count(*) as active_connections,
       max_conn,
       max_conn - count(*) as available_connections
FROM pg_stat_activity,
     (SELECT setting::int AS max_conn FROM pg_settings WHERE name='max_connections') AS mc
WHERE datname = 'windpower';"
```

#### 3. 高CPU/内存使用率
```bash
# 查看容器资源使用
docker stats --no-stream

# 查找高CPU使用的进程
docker-compose exec api top -b -n1 | head -20

# 重启高资源使用的容器
HIGH_CPU=$(docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}" | awk '$2 > 80 {print $1}')
for container in $HIGH_CPU; do
    docker restart $container
done
```

### 🟡 性能问题处理

#### API响应缓慢
```bash
# 1. 检查API响应时间
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:5000/api/status

# 2. 查看慢查询日志
docker-compose exec postgres tail -f /var/log/postgresql/slow.log

# 3. 检查数据库连接数
docker-compose exec postgres psql -U postgres -c "
SELECT count(*) as connections,
       state,
       application_name
FROM pg_stat_activity
GROUP BY state, application_name;"

# 4. 优化数据库查询
docker-compose exec postgres psql -U postgres -c "
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;"
```

#### 磁盘空间不足
```bash
# 1. 检查磁盘使用情况
df -h

# 2. 查找大文件
find /var/lib/docker -type f -size +100M -exec ls -lh {} \;

# 3. 清理Docker日志
docker-compose exec api truncate -s 0 /var/log/windpower/api.log

# 4. 清理旧镜像
docker image prune -a -f

# 5. 清理未使用的卷
docker volume prune -f
```

### 🟢 配置问题处理

#### 环境变量配置错误
```bash
# 1. 检查环境变量
docker-compose exec api env | grep -E "DB_|REDIS_|API_"

# 2. 验证配置文件
docker-compose exec api python -c "
import os
from app.config import Config
config = Config()
print('DB_HOST:', config.DB_HOST)
print('DB_PORT:', config.DB_PORT)
"

# 3. 重新加载配置
docker-compose restart api
```

#### 网络连接问题
```bash
# 1. 检查容器网络
docker network ls
docker network inspect windpower_default

# 2. 测试容器间通信
docker-compose exec api ping postgres
docker-compose exec api ping redis

# 3. 检查端口监听
netstat -tlnp | grep -E "5000|5432|6379"
```

## 监控告警配置

### 关键指标监控

#### 系统资源告警
```yaml
# 添加至prometheus-alerts.yml
groups:
- name: system-resources
  rules:
  - alert: HighCPUUsage
    expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "CPU使用率过高"
      description: "{{ $labels.instance }} CPU使用率超过85%"

  - alert: HighMemoryUsage
    expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "内存使用率过高"
      description: "{{ $labels.instance }} 内存使用率超过90%"

  - alert: DiskSpaceWarning
    expr: (1 - (node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"})) * 100 > 80
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "磁盘空间告警"
      description: "{{ $labels.instance }} 磁盘使用率超过80%"
```

#### 应用服务告警
```yaml
- name: application-services
  rules:
  - alert: APIDown
    expr: up{job="windpower-api"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "API服务不可用"
      description: "API服务已停止响应"

  - alert: DatabaseConnectionFailed
    expr: up{job="postgres"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "数据库连接失败"
      description: "PostgreSQL数据库无法连接"

  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "高错误率告警"
      description: "错误率超过10%"
```

### 自动化响应脚本

#### 自动重启失败的服务
```bash
#!/bin/bash
# auto-heal.sh

SERVICES=$(docker-compose ps -q)
for service in $SERVICES; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' $service 2>/dev/null)

    if [ "$HEALTH" = "unhealthy" ]; then
        SERVICE_NAME=$(docker inspect --format='{{.Name}}' $service | sed 's/\///')
        echo "$(date): 重启不健康的服务 $SERVICE_NAME"
        docker restart $service

        # 发送告警
        echo "服务 $SERVICE_NAME 已自动重启" | mail -s "服务自动恢复" ops@company.com
    fi
done
```

#### 自动清理日志
```bash
#!/bin/bash
# cleanup-logs.sh

LOG_DIR="/var/log/windpower"
BACKUP_DIR="/backup/logs"

# 创建备份目录
mkdir -p $BACKUP_DIR

# 压缩旧日志
tar -czf $BACKUP_DIR/windpower-logs-$(date +%Y%m%d).tar.gz $LOG_DIR/*.log

# 清空当前日志
> $LOG_DIR/api.log
> $LOG_DIR/prediction.log
> $LOG_DIR/training.log

# 删除30天前的备份
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

## 性能优化建议

### 数据库优化
```sql
-- 1. 创建合适的索引
CREATE INDEX CONCURRENTLY idx_weather_data_timestamp ON weather_data(timestamp);
CREATE INDEX CONCURRENTLY idx_power_predictions_model_time ON power_predictions(model_id, prediction_time);

-- 2. 更新统计信息
ANALYZE weather_data;
ANALYZE power_predictions;

-- 3. 清理无用数据
DELETE FROM prediction_results WHERE created_at < CURRENT_DATE - INTERVAL '90 days';
VACUUM FULL prediction_results;
```

### 应用优化
```bash
# 1. 调整Gunicorn工作进程数
docker-compose exec api python -c "
import multiprocessing
print('Recommended workers:', multiprocessing.cpu_count() * 2 + 1)
"

# 2. 优化连接池配置
# 修改docker-compose.yml中的环境变量
DB_POOL_SIZE: 20
DB_MAX_OVERFLOW: 40
DB_POOL_TIMEOUT: 30

# 3. 启用查询缓存
# 在Redis中配置缓存策略
redis-cli config set maxmemory 512mb
redis-cli config set maxmemory-policy allkeys-lru
```

---

## 运维工具箱

### 常用命令汇总
```bash
# 系统状态速览
alias windpower-status='docker-compose ps && docker stats --no-stream'

# 日志查看
alias windpower-logs='docker-compose logs -f --tail=100'

# 重启所有服务
alias windpower-restart='docker-compose restart'

# 清理系统
alias windpower-clean='docker system prune -f && docker volume prune -f'

# 性能监控
alias windpower-top='docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"'

# 数据库查询
alias windpower-db='docker-compose exec postgres psql -U postgres -d windpower'
```

### 监控仪表板
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **系统监控**: http://localhost:9093

### 紧急联系方式
- **24小时热线**: 400-123-4567
- **技术负责人**: 138-0000-1234
- **运维邮箱**: ops@company.com

---
*运维人员应随身携带此快速参考指南，确保在紧急情况下能够快速响应和处理*