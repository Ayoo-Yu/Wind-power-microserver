# 开发者快速参考指南

## 开发环境搭建

### 1. 前置要求
- Python 3.8+
- Node.js 14+
- Docker & Docker Compose
- Git

### 2. 快速启动命令
```bash
# 克隆项目
git clone [项目地址]
cd wind-power-forecast

# 启动开发环境
cd wind-power-microservices
docker-compose up -d

# 或者单独启动后端
cd wind-power-forecast/backend
pip install -r requirements.txt
python app.py

# 启动前端开发服务器
cd wind-power-forecast/frontend
npm install
npm run serve
```

### 3. 关键服务端口
- 前端开发服务器: http://localhost:8080
- 后端API服务: http://localhost:5000
- PostgreSQL数据库: localhost:5432
- Redis缓存: localhost:6379
- MinIO对象存储: http://localhost:9900
- Grafana监控: http://localhost:3000
- Prometheus: http://localhost:9090

### 4. 常用开发命令
```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f [service-name]

# 重启服务
docker-compose restart [service-name]

# 进入容器调试
docker-compose exec [service-name] bash

# 数据库连接
docker-compose exec postgres psql -U postgres -d windpower

# 运行测试
cd backend && python -m pytest
cd frontend && npm run test
```

### 5. API测试
```bash
# 健康检查
curl http://localhost:5000/health

# 用户登录
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 上传训练数据
curl -X POST http://localhost:5000/upload_train_csv \
  -H "Authorization: Bearer [token]" \
  -F "file=@train_data.csv"

# 创建预测任务
curl -X POST http://localhost:5000/predict \
  -H "Authorization: Bearer [token]" \
  -H "Content-Type: application/json" \
  -d '{"model_id":1,"start_time":"2024-01-16T00:00:00Z"}'
```

### 6. 代码结构
```
wind-power-forecast/
├── backend/                    # Python后端
│   ├── app.py                 # 主应用文件
│   ├── config.py              # 配置文件
│   ├── routes/                # API路由
│   ├── services/              # 业务逻辑
│   ├── models/                # 数据模型
│   └── utils/                 # 工具函数
├── frontend/                   # Vue.js前端
│   ├── src/
│   │   ├── components/        # Vue组件
│   │   ├── views/             # 页面视图
│   │   ├── services/          # API服务
│   │   ├── store/             # 状态管理
│   │   └── utils/             # 工具函数
│   └── public/                # 静态资源
├── wind-power-microservices/   # 微服务架构
│   ├── docker-compose.yml     # 服务编排
│   ├── services/              # 各个微服务
│   └── configs/               # 配置文件
└── monitoring/                 # 监控系统
    ├── prometheus/            # 指标收集
    ├── grafana/               # 可视化
    └── alertmanager/          # 告警管理
```

### 7. 开发调试技巧

#### 后端调试
```python
# 使用pdb调试
import pdb; pdb.set_trace()

# 日志调试
import logging
logger = logging.getLogger(__name__)
logger.info(f"Debug info: {variable}")

# 性能分析
import cProfile
profiler = cProfile.Profile()
profiler.enable()
# ... 代码 ...
profiler.disable()
profiler.print_stats()
```

#### 前端调试
```javascript
// Vue组件调试
console.log('Component data:', this.data)
console.table(this.predictions)

// API调用调试
const response = await api.getPredictions()
console.log('API Response:', response)
debugger; // 断点调试

// 性能监控
console.time('prediction')
// ... 代码 ...
console.timeEnd('prediction')
```

### 8. 数据库操作
```sql
-- 常用查询
-- 查看最近的预测结果
SELECT * FROM power_predictions
ORDER BY prediction_time DESC
LIMIT 10;

-- 统计预测精度
SELECT
    AVG(ABS(predicted_power - actual_power)) as mae,
    SQRT(AVG(POWER(predicted_power - actual_power, 2))) as rmse
FROM prediction_results
WHERE DATE(created_at) = CURRENT_DATE;

-- 查看训练任务状态
SELECT * FROM training_tasks
ORDER BY created_at DESC
LIMIT 5;
```

### 9. 环境配置
```bash
# 后端环境变量 (.env)
FLASK_ENV=development
FLASK_DEBUG=True
DB_HOST=localhost
DB_PORT=5432
DB_NAME=windpower
JWT_SECRET_KEY=your-secret-key

# 前端环境变量 (.env.development)
VUE_APP_API_BASE_URL=http://localhost:5000
VUE_APP_WS_URL=ws://localhost:5000
VUE_APP_TITLE=风功率预测系统(开发环境)
```

### 10. 常见问题快速解决

#### 端口被占用
```bash
# 查找占用进程
lsof -i :5000
# 或
netstat -tlnp | grep 5000

# 终止进程
kill -9 [PID]
```

#### 依赖安装失败
```bash
# 清理缓存
pip cache purge
npm cache clean --force

# 重新安装
pip install -r requirements.txt --no-cache-dir
npm install --registry https://registry.npmmirror.com
```

#### 数据库连接失败
```bash
# 检查PostgreSQL状态
docker-compose exec postgres pg_isready

# 重置数据库
docker-compose down
docker volume rm windpower_postgres_data
docker-compose up -d
```

---
**开发环境快速检查清单**:
- [ ] Docker服务正常运行
- [ ] 端口未被占用 (5000, 8080, 5432, 6379)
- [ ] 环境变量配置正确
- [ ] 依赖包安装完成
- [ ] 数据库初始化成功
- [ ] API服务响应正常
- [ ] 前端页面加载正常