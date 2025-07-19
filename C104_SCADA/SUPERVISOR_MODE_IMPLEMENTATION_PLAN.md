# SCADA客户端监管者模式实施计划

## 概述

将SCADA客户端改造为监管者模式，通过定期健康检查和自动重启机制解决长时间运行后连接僵死的问题，同时增加数据连续性保障机制，确保数据库上传和CSV写入操作不受断连影响。

## 修改策略

**目标文件**: `scada_c104.py`、`config.ini`、`data_persistence.py`(新增)、`Dockerfile`、`frontend-backend-compose.yaml`  
**修改原则**: 最小化变更，保持原有功能完整性，确保容器部署兼容性  
**核心思想**: 监督者模式 + 数据持久化 + 容器化部署优化

## 技术规范

### 1. 代码结构重构

#### 新增状态管理模块
```python
# data_persistence.py
class DataPersistence:
    """数据持久化和状态管理"""
    def __init__(self, state_dir="/app/state", data_dir="/app/data"):
        self.state_dir = state_dir
        self.data_dir = data_dir
        self.cache = DataCache(max_size=1000, max_hours=24)
    
    def save_state(self, state_data):
        """保存状态到文件"""
    
    def load_state(self):
        """从文件加载状态"""
    
    def get_missing_time_windows(self):
        """计算遗漏的时间窗口"""
```

#### 修改main函数为监管者模式
```python
def main():
    """监管者主循环"""
    persistence = DataPersistence()
    
    while not stop_event.is_set():
        # 恢复状态和处理积压数据
        persistence.restore_pending_operations()
        
        # 初始化并启动客户端
        client, connection, threads = initialize_and_start_client()
        
        # 健康检查循环
        while client.is_running and not stop_event.is_set():
            # 健康检查逻辑
            pass
        
        # 清理和重启准备
        cleanup_and_prepare_restart(client, persistence)
```

### 2. 关键参数设置

| 参数 | 值 | 说明 |
|------|----|----|
| 日志保留天数 | 365天 | 修改config.ini中的BACKUP_COUNT |
| 健康检查间隔 | 30秒 | 定期检查连接状态 |
| 确认检查间隔 | 30秒 | 再次确认无连接状态 |
| 重启等待间隔 | 15秒 | 避免快速重启循环 |
| 数据缓存大小 | 1000条 | 内存控制 |
| 缓存时间窗口 | 24小时 | 防止内存泄漏 |

### 3. 状态文件结构

#### 主状态文件 (`/app/state/status.json`)
```json
{
  "client_running": true,
  "last_database_upload_time": "2025-01-08T15:00:00+08:00",
  "last_csv_write_time": "2025-01-08T15:15:00+08:00", 
  "program_last_running_time": "2025-01-08T15:30:00+08:00",
  "cache_size": 0,
  "health_check_count": 1234
}
```

#### 数据缓存文件 (`/app/state/data_cache.json`)
```json
{
  "pending_database_uploads": [
    {
      "timestamp": "2025-01-08T15:00:00+08:00",
      "ioa": 1009,
      "value": 32.178,
      "quarter_minute": 45
    }
  ],
  "pending_csv_writes": [
    {
      "timestamp": "2025-01-08T15:15:00+08:00", 
      "data": {...}
    }
  ]
}
```

### 4. 容器部署配置

#### 更新后的Dockerfile
```dockerfile
# 使用官方的 Python 基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用文件
COPY scada_c104.py .
COPY logging_config.py .
COPY data_persistence.py .
COPY config.ini .

# 创建必要的目录
RUN mkdir -p logs data state && \
    chmod 755 logs data state

# 设置默认时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 添加健康检查脚本
COPY health_check.py .

# 运行应用
CMD ["python", "scada_c104.py"]
```

#### 健康检查脚本 (`health_check.py`)
```python
#!/usr/bin/env python3
import json
import sys
import os
from datetime import datetime, timedelta

def check_health():
    try:
        # 检查状态文件是否存在
        status_file = "/app/state/status.json"
        if not os.path.exists(status_file):
            return False
        
        # 读取状态
        with open(status_file, 'r') as f:
            status = json.load(f)
        
        # 检查客户端是否运行
        if not status.get('client_running', False):
            return False
        
        # 检查最后更新时间（5分钟内有更新认为健康）
        last_time = status.get('program_last_running_time')
        if last_time:
            last_dt = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
            if datetime.now().astimezone() - last_dt > timedelta(minutes=5):
                return False
        
        return True
    except Exception:
        return False

if __name__ == "__main__":
    sys.exit(0 if check_health() else 1)
```

#### 更新docker-compose.yaml中的scada服务配置
```yaml
scada_client_service:
  build:
    context: ../C104_SCADA
    dockerfile: Dockerfile
  image: c104-scada-client:v250714_2.0  # 更新版本号
  container_name: c104-scada-client
  environment:
    - TZ=Asia/Shanghai
  networks:
    - wind-power-network              
  restart: unless-stopped
  volumes:
    - ../C104_SCADA/config.ini:/app/config.ini:ro  # 只读挂载
    - ../C104_SCADA/logs:/app/logs                 # 日志持久化
    - ../C104_SCADA/data:/app/data                 # 数据文件持久化
    - ../C104_SCADA/state:/app/state               # 状态文件持久化
  healthcheck:
    test: ["CMD", "python", "health_check.py"]
    interval: 60s
    timeout: 10s
    retries: 3
    start_period: 30s
  depends_on:
    - backend  # 确保数据库服务可用
```

## 实施检查清单

### 准备阶段
- [ ] **1. 备份所有相关文件** - 备份C104_SCADA目录和docker-compose文件
- [ ] **2. 创建宿主机目录** - 在C104_SCADA下创建data和state目录
- [ ] **3. 分析现有数据流** - 识别数据库上传和CSV写入的具体实现

### 配置修改阶段  
- [ ] **4. 修改config.ini** - 将BACKUP_COUNT改为365
- [ ] **5. 创建data_persistence.py** - 实现状态管理和数据缓存类
- [ ] **6. 创建health_check.py** - 实现容器健康检查脚本
- [ ] **7. 更新.dockerignore** - 排除不必要的文件和目录

### 代码重构阶段
- [ ] **8. 搜索数据操作函数** - 找到数据库上传和CSV写入代码位置
- [ ] **9. 创建initialize_and_start_client函数** - 提取客户端初始化逻辑
- [ ] **10. 修改数据操作函数** - 集成状态记录和错误恢复
- [ ] **11. 实现数据恢复函数** - 处理断连期间的遗漏操作
- [ ] **12. 重写main函数** - 实现监管者循环逻辑

### 内存管理优化
- [ ] **13. 实现DataCache类** - 包含大小限制和LRU清理机制
- [ ] **14. 添加内存监控** - 记录缓存使用情况到状态文件
- [ ] **15. 实现定期清理** - 清理过期数据和状态文件
- [ ] **16. 优化批量处理** - 提高积压数据处理效率

### 容器配置更新
- [ ] **17. 更新Dockerfile** - 添加新文件复制和目录创建
- [ ] **18. 修改docker-compose.yaml** - 更新scada服务配置
- [ ] **19. 创建持久化目录** - 在宿主机创建必要的数据目录
- [ ] **20. 设置目录权限** - 确保容器有正确的读写权限

### 测试验证阶段
- [ ] **21. 本地代码测试** - 验证修改后的代码功能正确
- [ ] **22. 构建新镜像** - 测试Docker镜像构建过程
- [ ] **23. 测试容器启动** - 验证容器正常启动和日志输出
- [ ] **24. 测试健康检查** - 验证健康检查机制工作正常
- [ ] **25. 测试数据持久化** - 验证容器重启后状态恢复
- [ ] **26. 测试断连恢复** - 模拟网络断连测试数据恢复功能
- [ ] **27. 长期运行测试** - 验证内存使用稳定性和数据连续性

### 生产部署
- [ ] **28. 停止现有容器** - 优雅停止当前运行的scada服务
- [ ] **29. 备份现有数据** - 备份logs目录中的历史数据
- [ ] **30. 部署新版本** - 使用docker-compose up --build重新部署
- [ ] **31. 验证服务状态** - 检查健康检查和日志输出
- [ ] **32. 配置监控告警** - 基于健康检查设置告警机制

## 目录结构

### 宿主机目录结构
```
C104_SCADA/
├── scada_c104.py              # 主程序
├── logging_config.py          # 日志配置
├── data_persistence.py        # 状态管理模块（新增）
├── health_check.py            # 健康检查脚本（新增）
├── config.ini                 # 配置文件
├── Dockerfile                 # 容器构建文件
├── requirements.txt           # Python依赖
├── logs/                      # 日志目录（挂载）
│   ├── scada_client.log
│   └── scada_client.log.2025-01-*
├── data/                      # 数据文件目录（新增，挂载）
│   └── csv_exports/
└── state/                     # 状态文件目录（新增，挂载）
    ├── status.json
    ├── data_cache.json
    └── backup/
```

### 容器内目录结构
```
/app/
├── scada_c104.py
├── logging_config.py
├── data_persistence.py
├── health_check.py
├── config.ini
├── logs/          -> 挂载到宿主机
├── data/          -> 挂载到宿主机
└── state/         -> 挂载到宿主机
```

## 预期效果

### 问题解决
- ✅ 解决客户端长时间运行后连接僵死问题
- ✅ 保证15分钟数据库上传操作不受断连影响
- ✅ 保证CSV文件写入操作不受断连影响  
- ✅ 断连期间遗漏的时间窗口自动补偿
- ✅ 程序重启后数据操作无缝恢复
- ✅ 日志保留期延长到365天

### 运行特征
- 🔄 **自动重启**：检测到连接问题时自动重启客户端
- 📊 **健康监控**：容器级健康检查，支持外部监控
- 💾 **数据持久化**：关键状态和数据持久保存
- 🛡️ **内存保护**：严格的缓存大小和时间限制
- 📝 **详细日志**：365天日志保留，完整的操作记录
- ⚡ **快速恢复**：重启后立即恢复到中断前状态

### 容器化优势
- 🐳 **容器健康检查**：Docker原生健康监控
- 📁 **数据卷持久化**：logs、data、state目录独立持久化
- 🔄 **自动重启策略**：unless-stopped策略确保高可用
- 🌐 **网络集成**：与现有wind-power-network无缝集成
- 🕐 **时区一致性**：统一的Asia/Shanghai时区设置

## 风险控制和回滚方案

### 风险缓解
1. **渐进式部署**：先在测试环境验证所有功能
2. **完整备份**：部署前备份所有现有数据和配置
3. **监控就绪**：部署时密切监控日志和健康状态
4. **快速回滚**：保留原版本镜像，支持快速回滚

### 回滚方案
如果新版本出现问题：
1. **立即回滚**：`docker-compose down && docker-compose up -d` 使用旧镜像
2. **恢复数据**：从备份恢复logs目录
3. **问题分析**：检查新版本的日志和状态文件
4. **修复验证**：在测试环境修复问题后重新部署

这个完整的实施计划确保了在现有docker-compose环境中平滑集成监管者模式和数据连续性保障功能。

## 实施进度

### ✅ 已完成 (2025-01-15)

- [x] **代码备份**: 备份原始scada_c104.py、config.ini和docker-compose.yaml
- [x] **目录结构**: 创建data、state、state/backup目录
- [x] **配置修改**: 日志保留天数从30天延长到365天
- [x] **核心模块**: 创建data_persistence.py状态管理模块
- [x] **健康检查**: 创建health_check.py Docker健康检查脚本
- [x] **代码重构**: 创建initialize_and_start_client()客户端初始化函数
- [x] **监管者模式**: 重写main()函数实现监管者主循环
- [x] **数据连续性**: 增强upload_to_api()和write_to_csv()函数支持状态记录
- [x] **容器配置**: 更新Dockerfile添加新文件和健康检查
- [x] **编排配置**: 更新docker-compose.yaml添加卷挂载和健康检查
- [x] **构建优化**: 创建.dockerignore文件
- [x] **语法验证**: 所有Python文件通过编译检查

### 🔄 待部署

- [ ] **容器构建**: 构建新的Docker镜像
- [ ] **功能测试**: 在测试环境验证监管者模式
- [ ] **生产部署**: 更新生产环境
- [ ] **监控验证**: 确认系统稳定运行

### 📋 部署后验证

- [ ] **连接健康**: 验证SCADA连接自动重启功能
- [ ] **数据连续性**: 确认数据库上传和CSV写入不中断
- [ ] **健康检查**: 验证Docker健康状态正常
- [ ] **日志质量**: 检查日志记录和轮转功能
- [ ] **状态持久化**: 验证状态文件正确保存和恢复 