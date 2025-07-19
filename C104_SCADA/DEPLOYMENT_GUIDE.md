# SCADA客户端监管者模式部署指南

## 概述

本指南说明如何将SCADA客户端更新为监管者模式，提供自动重启和数据连续性保障功能。

## 更新内容

### 核心功能
- **监管者模式**: 自动检测连接状态，发现问题时重启客户端
- **数据连续性**: 确保15分钟数据库上传和CSV写入操作不受断连影响
- **日志管理**: 日志保留期从30天延长到365天
- **健康检查**: Docker原生健康检查，支持外部监控

### 新增文件
- `data_persistence.py`: 数据持久化和状态管理模块
- `health_check.py`: Docker健康检查脚本
- `.dockerignore`: 构建优化配置

### 修改文件
- `scada_c104.py`: 重构为监管者模式
- `config.ini`: 日志保留天数更新
- `Dockerfile`: 添加新文件和健康检查
- `frontend-backend-compose.yaml`: 添加卷挂载和健康检查

## 部署步骤

### 1. 停止现有服务

```bash
cd wind-power-forecast
docker-compose -f frontend-backend-compose.yaml down
```

### 2. 备份当前数据 (可选但推荐)

```bash
# 备份当前日志
cp -r ../C104_SCADA/logs ../C104_SCADA/logs_backup_$(date +%Y%m%d_%H%M%S)

# 备份配置
cp ../C104_SCADA/config.ini ../C104_SCADA/config.ini.backup_$(date +%Y%m%d_%H%M%S)
```

### 3. 构建新镜像

```bash
# 构建SCADA客户端新镜像
docker-compose -f frontend-backend-compose.yaml build scada_client_service
```

### 4. 启动服务

```bash
# 启动所有服务
docker-compose -f frontend-backend-compose.yaml up -d

# 或仅启动SCADA服务
docker-compose -f frontend-backend-compose.yaml up -d scada_client_service
```

### 5. 验证部署

```bash
# 检查容器状态
docker ps | grep c104-scada-client

# 检查健康状态
docker inspect c104-scada-client | grep Health -A 10

# 查看日志
docker logs c104-scada-client --tail 50 -f

# 检查数据目录
ls -la ../C104_SCADA/data/
ls -la ../C104_SCADA/state/
```

## 监控要点

### 1. 关键日志信息

监控以下日志关键词：
- `SUPERVISOR`: 监管者模式相关日志
- `RESTART`: 客户端重启事件
- `HEALTH CHECK`: 健康检查结果
- `DATA PERSISTENCE`: 数据持久化操作

### 2. 健康检查

```bash
# 手动执行健康检查
docker exec c104-scada-client python health_check.py

# 查看健康检查历史
docker inspect c104-scada-client | jq '.[0].State.Health'
```

### 3. 状态文件监控

```bash
# 查看状态文件
docker exec c104-scada-client cat /app/state/status.json

# 监控状态文件变化
docker exec c104-scada-client tail -f /app/state/status.json
```

## 故障排除

### 常见问题

1. **健康检查失败**
   ```bash
   # 检查状态文件
   docker exec c104-scada-client ls -la /app/state/
   
   # 手动运行健康检查
   docker exec c104-scada-client python health_check.py
   ```

2. **数据目录权限问题**
   ```bash
   # 检查目录权限
   ls -la ../C104_SCADA/data/
   ls -la ../C104_SCADA/state/
   
   # 如需修复权限
   sudo chown -R 1000:1000 ../C104_SCADA/data/
   sudo chown -R 1000:1000 ../C104_SCADA/state/
   ```

3. **连接持续重启**
   ```bash
   # 查看详细日志
   docker logs c104-scada-client --tail 100
   
   # 检查网络连接
   docker exec c104-scada-client ping 192.121.0.122
   ```

### 回滚步骤

如果新版本出现问题：

```bash
# 1. 停止服务
docker-compose -f frontend-backend-compose.yaml down

# 2. 修改镜像版本为旧版本
# 编辑 frontend-backend-compose.yaml，将镜像版本改回 v250714_1.0

# 3. 重新启动
docker-compose -f frontend-backend-compose.yaml up -d scada_client_service

# 4. 恢复配置（如果需要）
cp ../C104_SCADA/config.ini.backup_* ../C104_SCADA/config.ini
```

## 性能指标

### 正常运行指标
- **健康检查**: 每2分钟成功
- **连接状态**: 无频繁重启（<1次/小时）
- **数据上传**: 15分钟间隔正常
- **CSV写入**: 15分钟间隔正常

### 异常告警阈值
- 健康检查连续失败3次
- 1小时内重启超过3次
- 数据上传中断超过30分钟
- 状态文件更新中断超过5分钟

## 维护建议

1. **定期检查**: 每日检查健康状态和日志
2. **空间监控**: 监控logs、data、state目录空间使用
3. **性能分析**: 每周分析重启频率和连接稳定性
4. **备份管理**: 定期清理状态文件备份（保留最近30天）

## 技术支持

如遇到问题，请提供以下信息：
1. 容器状态：`docker ps | grep scada`
2. 健康检查：`docker inspect c104-scada-client | grep Health -A 20`
3. 最近日志：`docker logs c104-scada-client --tail 200`
4. 状态文件：`docker exec c104-scada-client cat /app/state/status.json` 