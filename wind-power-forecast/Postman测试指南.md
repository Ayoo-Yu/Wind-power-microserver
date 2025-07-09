# Postman测试指南 - 风电功率自动上报

## 🎯 测试目标

使用Postman模拟数据接收端，测试风电功率自动上报功能的完整流程。

## 📋 测试准备

### 1. 启动模拟接收端服务器

在项目根目录运行：
```bash
python mock_receiver.py
```

服务启动后会显示：
```
==================================================
风电功率数据接收端模拟器
==================================================
服务地址: http://localhost:8081
接收接口: POST http://localhost:8081/receive-data
状态查询: GET http://localhost:8081/status
接收历史: GET http://localhost:8081/history
清空数据: POST http://localhost:8081/clear
==================================================
```

### 2. 确认风电后端服务运行

确保后端服务在 `http://localhost:5000` 运行。

### 3. 打开Postman

准备好Postman应用程序。

## 🧪 测试步骤

### 第一步：验证模拟接收端

#### 1.1 测试接收端状态
```
方法: GET
URL: http://localhost:8081/status
```

期望响应：
```json
{
  "status": "running",
  "total_received": 0,
  "last_receive_time": null,
  "server_time": "2025-01-07 15:30:00"
}
```

#### 1.2 测试首页信息
```
方法: GET
URL: http://localhost:8081/
```

### 第二步：测试调度器状态

#### 2.1 检查调度器状态
```
方法: GET
URL: http://localhost:5000/api/report/scheduler/status
```

期望响应：
```json
{
  "running": true,
  "next_report_times": ["15:44:30", "15:59:30"]
}
```

#### 2.2 重启调度器（如果需要）
```
方法: POST
URL: http://localhost:5000/api/report/scheduler/stop
```

```
方法: POST
URL: http://localhost:5000/api/report/scheduler/start
```

### 第三步：配置上报任务

#### 3.1 创建测试风电场
```
方法: POST
URL: http://localhost:5000/api/report/farms
Headers: Content-Type: application/json
Body:
{
  "farm_code": "TEST001",
  "farm_name": "测试风电场",
  "installed_capacity": 100.0,
  "location": "测试地点"
}
```

#### 3.2 创建上报配置
```
方法: POST
URL: http://localhost:5000/api/report/configs
Headers: Content-Type: application/json
Body:
{
  "farm_id": 1,
  "report_type": "actual",
  "target_ip": "127.0.0.1",
  "target_port": 8081,
  "target_path": "/receive-data",
  "report_interval": 15,
  "is_enabled": true
}
```

**注意**：`farm_id` 需要根据实际创建的风电场ID调整。

### 第四步：手动测试上报

#### 4.1 手动触发上报
```
方法: POST
URL: http://localhost:5000/api/report/configs/{config_id}/report
```

将 `{config_id}` 替换为实际的配置ID。

#### 4.2 检查接收端是否收到数据
```
方法: GET
URL: http://localhost:8081/history
```

期望看到接收到的数据记录。

### 第五步：等待自动上报

#### 5.1 观察时间
等待到下一个上报时间点：
- XX:14:30
- XX:29:30  
- XX:44:30
- XX:59:30

#### 5.2 实时监控接收端
每30秒查询一次接收端状态：
```
方法: GET
URL: http://localhost:8081/status
```

#### 5.3 查看详细接收历史
```
方法: GET
URL: http://localhost:8081/history
```

## 📊 监控和验证

### 1. Postman Collection 设置

创建一个Postman Collection包含以下请求：

1. **接收端监控**
   - `GET /status` - 接收端状态
   - `GET /history` - 接收历史
   - `POST /clear` - 清空数据

2. **调度器控制**
   - `GET /scheduler/status` - 调度器状态
   - `POST /scheduler/start` - 启动调度器
   - `POST /scheduler/stop` - 停止调度器

3. **配置管理**
   - `GET /farms` - 获取风电场列表
   - `GET /configs` - 获取配置列表
   - `POST /configs/{id}/report` - 手动上报

### 2. 环境变量设置

在Postman中设置环境变量：
```
backend_url = http://localhost:5000
receiver_url = http://localhost:8081
```

### 3. 自动化测试脚本

在Postman的Tests标签中添加验证脚本：

```javascript
// 验证调度器状态
pm.test("调度器运行正常", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.running).to.be.true;
});

// 验证接收端状态
pm.test("接收端正常工作", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.status).to.eql("running");
});

// 验证数据接收
pm.test("数据接收成功", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.total_received).to.be.above(0);
});
```

## 🔍 故障排除

### 常见问题及解决方案

#### 1. 接收端无法启动
- **问题**：端口8081被占用
- **解决**：修改 `mock_receiver.py` 中的端口号
- **修改位置**：最后一行 `app.run(host='0.0.0.0', port=8082, debug=True)`

#### 2. 调度器显示停止
- **解决**：使用Postman调用启动接口
- **请求**：`POST http://localhost:5000/api/report/scheduler/start`

#### 3. 没有收到自动上报数据
- **检查**：确认配置已启用 (`is_enabled: true`)
- **检查**：确认目标IP和端口正确指向接收端
- **检查**：确认当前时间接近上报时间点

#### 4. 上报失败
- **检查**：查看后端日志 `logs/app.log`
- **检查**：确认网络连接正常
- **检查**：使用Postman直接测试接收端接口

## 📝 测试记录模板

### 测试执行记录

| 时间 | 测试项目 | 期望结果 | 实际结果 | 状态 | 备注 |
|------|---------|----------|----------|------|------|
| 15:14:30 | 自动上报触发 | 接收到数据 | ✅ 成功 | 通过 | 数据量100条 |
| 15:29:30 | 自动上报触发 | 接收到数据 | ✅ 成功 | 通过 | 正常 |
| 15:44:30 | 自动上报触发 | 接收到数据 | ❌ 失败 | 失败 | 网络超时 |

### 性能指标记录

| 指标 | 数值 | 单位 | 备注 |
|------|------|------|------|
| 上报响应时间 | 150 | ms | 正常范围内 |
| 数据传输量 | 50 | KB | 包含100条记录 |
| 成功率 | 95 | % | 可接受范围 |

## 🎯 测试完成标准

✅ **基础功能测试**
- [ ] 接收端服务正常启动
- [ ] 调度器状态显示运行中
- [ ] 手动上报测试成功

✅ **自动上报测试**
- [ ] 在指定时间点自动触发上报
- [ ] 接收端成功接收数据
- [ ] 上报日志记录正常

✅ **异常处理测试**
- [ ] 接收端停止时上报失败但有重试
- [ ] 调度器重启后恢复正常
- [ ] 网络异常时有适当的错误处理

## 💡 测试技巧

1. **使用Collection Runner**：批量执行测试用例
2. **设置监控**：使用Monitor定期检查服务状态  
3. **数据驱动测试**：使用CSV文件提供测试数据
4. **环境隔离**：为不同环境设置不同的环境变量
5. **日志分析**：结合后端日志和接收端日志分析问题

测试愉快！🚀 