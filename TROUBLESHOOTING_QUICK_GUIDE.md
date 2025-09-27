# 风功率预测系统 - 故障排除快速指南

## 🚨 紧急故障处理流程

### 系统完全不可用

**症状**: 所有服务都无法访问，用户无法登录

**立即处理步骤**:
1. **检查基础设施状态**
   ```bash
   docker-compose ps
   kubectl get nodes
   kubectl get pods -n wind-power
   ```

2. **检查系统资源**
   ```bash
   df -h  # 磁盘空间
   free -h  # 内存使用
   top  # CPU使用
   ```

3. **重启核心服务**
   ```bash
   # 单体架构
   docker-compose restart

   # 微服务架构
   kubectl rollout restart deployment -n wind-power
   ```

4. **检查网络连接**
   ```bash
   ping localhost:5000
   curl -I http://localhost:5000/health
   ```

**如果以上步骤无效**:
- 执行系统回滚: `./scripts/rollback-system.sh`
- 联系技术支持: `support@windpower.com`
- 启用备用系统

---

## 🔧 常见问题快速解决方案

### 1. 数据库连接失败

**错误信息**: `Connection refused`, `Database connection failed`

**快速解决**:
```bash
# 检查数据库服务状态
docker-compose ps | grep postgres

# 重启数据库服务
docker-compose restart postgres

# 检查数据库配置
cat backend/config.py | grep DATABASE

# 测试数据库连接
docker-compose exec postgres pg_isready
```

**详细排查**:
```bash
# 查看数据库日志
docker-compose logs postgres --tail 100

# 检查连接参数
docker-compose exec backend python -c "
import os
from config import DATABASE_CONFIG
print('Host:', DATABASE_CONFIG['host'])
print('Port:', DATABASE_CONFIG['port'])
print('Database:', DATABASE_CONFIG['database'])
"

# 手动连接测试
docker-compose exec postgres psql -U postgres -d wind_power -c "SELECT 1;"
```

### 2. API响应缓慢

**症状**: 响应时间 > 5秒，用户界面卡顿

**快速解决**:
```bash
# 检查系统资源
docker stats

# 重启API服务
docker-compose restart backend

# 清理缓存
curl -X POST http://localhost:5000/system/clear-cache
```

**性能优化**:
```bash
# 检查慢查询
kubectl exec -it postgres-pod -- psql -c "
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;"

# 检查API性能指标
curl -X GET http://localhost:5000/system/metrics
```

### 3. 模型训练失败

**错误信息**: `Training failed`, `Model training error`

**快速解决**:
```bash
# 检查训练服务状态
docker-compose logs ml-training --tail 50

# 检查训练数据完整性
curl -X GET "http://localhost:5000/api/data/quality?type=training"

# 重新启动训练任务
curl -X POST http://localhost:5000/modeltrain/restart/12345
```

**常见原因**:
- 训练数据格式错误
- 内存不足
- 特征列缺失
- 模型参数配置错误

### 4. 预测精度异常

**症状**: 预测精度 < 70%，MAPE > 30%

**快速诊断**:
```bash
# 检查最新预测结果
curl -X GET "http://localhost:5000/predict/accuracy?days=7"

# 检查数据质量
curl -X GET "http://localhost:5000/data/quality/report"

# 验证模型状态
curl -X GET "http://localhost:5000/model/status"
```

**自动修复**:
```bash
# 重新训练模型
curl -X POST http://localhost:5000/model/retrain

# 更新特征工程
curl -X POST http://localhost:5000/features/update
```

### 5. 文件上传失败

**错误信息**: `Upload failed`, `File processing error`

**快速解决**:
```bash
# 检查文件服务状态
docker-compose logs file-service --tail 50

# 检查磁盘空间
df -h /uploads

# 清理临时文件
find /tmp -name "*.tmp" -mtime +1 -delete
```

**文件格式验证**:
```bash
# 检查CSV格式
csvstat your_file.csv

# 验证列名
csvcut -n your_file.csv
```

### 6. 认证失败

**错误信息**: `401 Unauthorized`, `Token expired`

**快速解决**:
```bash
# 重新获取token
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# 刷新token
curl -X POST http://localhost:5000/auth/refresh \
  -H "Authorization: Bearer old_token_here"
```

### 7. 报告生成失败

**错误信息**: `Report generation failed`

**快速解决**:
```bash
# 检查报告服务
docker-compose logs report-service --tail 50

# 检查模板文件
ls -la backend/templates/

# 重新生成报告
curl -X POST http://localhost:5000/reports/regenerate/12345
```

---

## 📊 监控和告警

### 关键指标监控

**实时状态检查**:
```bash
# 系统健康检查
./scripts/health-check.sh

# 服务状态检查
./scripts/service-status.sh

# 资源使用监控
./scripts/resource-monitor.sh
```

**关键指标阈值**:
| 指标 | 警告阈值 | 严重阈值 |
|------|----------|----------|
| CPU使用率 | 70% | 85% |
| 内存使用率 | 80% | 90% |
| 磁盘使用率 | 75% | 85% |
| API响应时间 | 2秒 | 5秒 |
| 错误率 | 5% | 10% |
| 预测精度 | 75% | 70% |

### 日志分析

**快速日志查看**:
```bash
# 查看最近错误
docker-compose logs --tail 100 | grep -i error

# 查看特定服务日志
docker-compose logs backend --tail 50

# 查看系统日志
journalctl -u docker --since "1 hour ago"
```

**日志搜索模式**:
```bash
# 搜索数据库错误
grep -r "database" logs/ | grep -i error

# 搜索认证失败
grep -r "401" logs/ | tail -20

# 搜索性能警告
grep -r "slow" logs/ | grep -v "INFO"
```

---

## 🔄 自动故障恢复

### 自动重启脚本

创建 `auto-recovery.sh`:
```bash
#!/bin/bash

# 自动故障恢复脚本

SERVICES=("backend" "frontend" "postgres" "redis")
LOG_FILE="/var/log/auto-recovery.log"

echo "$(date): 开始自动故障检查" >> $LOG_FILE

for service in "${SERVICES[@]}"; do
    if ! docker-compose ps | grep -q "$service.*Up"; then
        echo "$(date): $service 服务异常，尝试重启" >> $LOG_FILE
        docker-compose restart $service
        sleep 30

        if docker-compose ps | grep -q "$service.*Up"; then
            echo "$(date): $service 重启成功" >> $LOG_FILE
        else
            echo "$(date): $service 重启失败，需要人工干预" >> $LOG_FILE
            # 发送告警
            curl -X POST "http://alertmanager:9093/api/v1/alerts" \
              -H "Content-Type: application/json" \
              -d '{
                "alerts": [{
                  "labels": {
                    "alertname": "ServiceDown",
                    "service": "'$service'",
                    "severity": "critical"
                  },
                  "annotations": {
                    "summary": "Service '$service' failed to restart"
                  }
                }]
              }'
        fi
    fi
done

echo "$(date): 自动故障检查完成" >> $LOG_FILE
```

### 设置定时任务
```bash
# 每5分钟执行一次自动检查
crontab -e
# 添加:
*/5 * * * * /path/to/auto-recovery.sh
```

---

## 🛠️ 高级故障诊断

### 网络连接诊断

**端口检查**:
```bash
# 检查服务端口
netstat -tulpn | grep -E ":5000|:5432|:6379"

# 测试端口连通性
telnet localhost 5000

# 检查防火墙状态
ufw status
iptables -L
```

**DNS解析检查**:
```bash
# 检查DNS解析
nslookup localhost
dig localhost

# 检查hosts文件
cat /etc/hosts
```

### 数据库诊断

**连接池诊断**:
```bash
# 查看当前连接
kubectl exec -it postgres-pod -- psql -c "
SELECT count(*), state
FROM pg_stat_activity
GROUP BY state;"

# 查看慢查询
kubectl exec -it postgres-pod -- psql -c "
SELECT query, mean_time, calls
FROM pg_stat_statements
WHERE mean_time > 1000
ORDER BY mean_time DESC
LIMIT 10;"
```

**表空间使用**:
```bash
# 检查数据库大小
kubectl exec -it postgres-pod -- psql -c "
SELECT pg_size_pretty(pg_database_size('wind_power'));"

# 检查表大小
kubectl exec -it postgres-pod -- psql -c "
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;"
```

### 内存泄漏检测

**内存使用分析**:
```bash
# 查看内存使用
ps aux --sort=-%mem | head -20

# 检查容器内存
docker stats --no-stream

# 检查内存泄漏
valgrind --tool=memcheck --leak-check=full python app.py
```

---

## 📞 联系支持

### 内部支持
- **运维团队**: `ops@windpower.com`
- **开发团队**: `dev@windpower.com`
- **架构团队**: `arch@windpower.com`

### 外部支持
- **云服务提供商**: `cloud-support@provider.com`
- **数据库厂商**: `db-support@vendor.com`
- **监控系统**: `monitoring-support@grafana.com`

### 紧急联系
- **24小时热线**: `400-1234-5678`
- **紧急邮箱**: `urgent@windpower.com`
- **值班手机**: `138-0000-1234`

---

## 📝 故障记录模板

### 故障报告模板
```yaml
故障编号: INC-2024-001
发生时间: 2024-01-15 14:30:00
报告人: 张三
故障级别: P1 (Critical)
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

验证结果:
- 系统恢复正常运行
- 监控显示连接数稳定
- 用户反馈正常
```

---

## 🔗 相关资源

### 文档链接
- [完整使用手册](COMPREHENSIVE_USAGE_MANUAL.md)
- [运维手册](OPERATIONS_MANUAL.md)
- [API使用示例](API_USAGE_EXAMPLES.md)
- [项目交付清单](PROJECT_DELIVERY_CHECKLIST.md)

### 工具链接
- [Grafana监控](http://localhost:3000)
- [Kibana日志](http://localhost:5601)
- [API文档](http://localhost:5000/api-docs)
- [系统状态](http://localhost:5000/health)

### 脚本位置
```
scripts/
├── health-check.sh          # 健康检查
├── auto-recovery.sh         # 自动恢复
├── backup-system.sh         # 系统备份
├── restore-system.sh        # 系统恢复
├── performance-monitor.sh   # 性能监控
└── log-analyzer.sh          # 日志分析
```

---

**最后更新**: 2024年
**维护团队**: 风功率预测系统运维团队
**下次更新**: 根据实际故障情况持续更新

**⚠️ 重要提醒**:
- 本指南应定期更新，确保包含最新的故障案例
- 所有故障处理过程都应详细记录
- 定期进行故障演练，提高响应速度
- 保持联系信息的及时更新