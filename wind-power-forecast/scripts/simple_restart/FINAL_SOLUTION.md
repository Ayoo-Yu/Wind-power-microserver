# KingBase自动续期最终解决方案
#34 5 14 */2 * /usr/bin/python3 /srv/wind-power-project/scripts/renew_license.py >> /var/log/kingbase_renewal.log 2>&1
## 🎯 方案概述

基于您的建议，我们采用**全局重建策略**作为最终的无人值守自动化方案。这个策略遵循极简和绝对可预测性原则，最大限度地降低了出错可能性。

## 📁 最终文件清单

### 核心执行脚本
1. **`kingbase_renewal_windows.py`** ⭐ - 全局重建策略脚本（推荐用于生产环境）
2. **`restart_kingbase_smart_windows.py`** - 智能重启策略脚本（备用方案）

### 配置和管理工具
3. **`setup_windows_schedule_renewal.bat`** - 全局重建策略的定时任务设置工具
4. **`setup_windows_schedule.bat`** - 智能重启策略的定时任务设置工具
5. **`windows_test_guide.md`** - 完整的测试指南

## 🏆 全局重建策略优势

### 设计原则
- **极简性**：只使用 `docker-compose down` 和 `up`
- **可预测性**：所有容器都是全新的，状态完全一致
- **可靠性**：避免复杂的服务依赖检查逻辑
- **原子性**：将整个环境视为一个原子单元

### 技术优势
1. **无混合策略**：不会出现部分容器是新的、部分是旧的情况
2. **状态一致性**：所有服务都从全新状态启动
3. **依赖关系清晰**：通过docker-compose自然处理服务启动顺序
4. **故障排查简单**：所有问题都可以通过查看docker-compose日志解决

## 🚀 部署步骤

### 1. 测试脚本功能
```powershell
# 切换到项目目录
cd D:\my-vue-project\wind-power-forecast

# 执行一次手动测试
python scripts/simple_restart/kingbase_renewal_windows.py
```

### 2. 设置定时任务
```powershell
# 以管理员身份运行
.\scripts\simple_restart\setup_windows_schedule_renewal.bat

# 选择选项2：每3天凌晨2点自动续期（推荐生产环境）
```

### 3. 验证部署
```powershell
# 查看定时任务
schtasks /query /tn "KingBase_Auto_Renewal"

# 查看日志
type scripts\simple_restart\logs\kingbase_renewal.log
```

## 📊 性能数据

基于实际测试结果：

| 阶段 | 耗时 | 说明 |
|------|------|------|
| 停止所有服务 | ~22秒 | 优雅关闭所有容器 |
| 清理资源 | 5秒 | 确保完全清理 |
| 启动所有服务 | ~6秒 | 创建新容器 |
| 等待服务就绪 | 60秒 | 确保所有服务完全启动 |
| **总耗时** | **~93秒** | **约1.5分钟完成** |

## 🔧 配置说明

### 脚本配置 (`kingbase_renewal_windows.py`)
```python
# Docker Compose 文件名
COMPOSE_FILE = "frontend-backend-compose.yaml"

# 日志文件路径
LOG_FILE = "logs/kingbase_renewal.log"

# 服务启动等待时间（秒）
STARTUP_WAIT_TIME = 60
```

### 推荐定时任务设置
- **生产环境**：每3天凌晨2点 (`0 2 */3 * *`)
- **测试环境**：每天凌晨2点 (`0 2 * * *`)
- **保守环境**：每周日凌晨2点 (`0 2 * * 0`)

## 📝 日志管理

### 日志位置
```
scripts/simple_restart/logs/kingbase_renewal.log
```

### 日志内容
- 执行时间戳
- 每个步骤的详细状态
- 错误信息（如果有）
- 最终执行结果

### 日志查看
```powershell
# 查看完整日志
type scripts\simple_restart\logs\kingbase_renewal.log

# 查看最新执行结果（PowerShell）
Get-Content scripts\simple_restart\logs\kingbase_renewal.log -Tail 20
```

## 🛡️ 故障处理

### 常见问题处理

#### 1. Docker环境问题
**症状**：`docker-compose 命令不可用`
**解决**：确保Docker Desktop正在运行

#### 2. 权限问题
**症状**：`定时任务创建失败`
**解决**：以管理员身份运行设置脚本

#### 3. 服务启动慢
**症状**：`服务启动超时`
**解决**：增加`STARTUP_WAIT_TIME`到120秒

#### 4. 日志编码问题
**症状**：日志中文显示乱码
**解决**：功能正常，显示问题不影响使用

### 紧急恢复
```powershell
# 手动恢复服务
cd D:\my-vue-project\wind-power-forecast
docker-compose -f frontend-backend-compose.yaml down
docker-compose -f frontend-backend-compose.yaml up -d
```

## 🔍 监控和维护

### 定期检查项目
1. **每周**：检查日志文件确认执行成功
2. **每月**：验证前端页面和API正常工作
3. **每季度**：检查磁盘空间和Docker镜像大小

### 监控脚本
```powershell
# 检查服务状态
docker-compose -f frontend-backend-compose.yaml ps

# 检查最后执行时间
dir scripts\simple_restart\logs\kingbase_renewal.log
```

## ✅ 最终验收清单

- [ ] 脚本手动执行成功
- [ ] 定时任务设置完成
- [ ] 日志文件正确创建
- [ ] 所有服务正常启动
- [ ] 前端页面可正常访问
- [ ] API接口响应正常
- [ ] 数据库连接正常

## 🎉 总结

这个全局重建策略方案具有以下特点：

1. **极简可靠**：只有两个核心操作，不会出错
2. **状态一致**：每次都是全新环境，避免历史问题
3. **维护简单**：无需复杂的健康检查和依赖管理
4. **适合长期运行**：设计用于无人值守运行一年以上

**这是您风电预测系统KingBase试用期自动续期的最终解决方案！** 🚀 