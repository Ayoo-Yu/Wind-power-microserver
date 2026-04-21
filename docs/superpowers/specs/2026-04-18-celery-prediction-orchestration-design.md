# Celery + Redis 预测任务编排方案设计

**日期**: 2026-04-18
**状态**: 待实施
**替代方案**: PM2 进程管理 + Python schedule 调度

## 背景与问题

当前风电预测系统使用 PM2 管理预测任务进程，存在四个核心问题：

1. **状态不透明**：进程启动了但状态显示"未启用"，PM2 查询不可靠
2. **运维繁琐**：增加新场站需要手动启动 PM2 进程，重启后状态丢失
3. **架构过度复杂**：Python schedule + PM2 + Flag 文件三层协调，容易出错
4. **缺乏可观测性**：训练/预测失败没有明确通知，只能看日志

## 约束条件

- 部署规模：5-10 个风电场
- 部署环境：单机 Docker Compose
- 不引入重量级新组件

## 整体架构

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Flask API   │────>│ Redis (Broker)│────>│ Celery Workers   │
│  (端口 5001) │     │              │     │ (预测执行进程)    │
└──────┬───────┘     └──────────────┘     └──────────────────┘
       │                    │                       │
       │           Celery Beat (定时调度)            │
       │           ┌──────────────┐                 │
       └──────────>│  Beat 进程    │─────────────────┘
                   │ (读取调度配置) │
                   └──────────────┘
                          │
                   ┌──────────────┐
                   │  PostgreSQL   │  (任务结果 + 调度配置)
                   └──────────────┘
```

### 四个进程

| 进程 | 职责 | 替代什么 |
|------|------|----------|
| **Flask API** | 接收前端请求，下发任务到队列 | 现有 Flask + PM2 命令转发 |
| **Celery Beat** | 定时触发训练/预测任务 | scheduler_*.py + schedule 库 |
| **Celery Worker** | 执行实际的训练和预测脚本 | PM2 管理的 scheduler 进程 |
| **Flower**（可选） | Web 监控面板，查看任务状态/历史 | pm2 list / pm2 logs |

### 关键数据流

1. **定时调度**：Beat 从数据库读取每个场站的调度配置（`prediction_tasks` 表），到时间自动发送任务消息到 Redis
2. **手动触发**：前端点击"启动"，Flask API 发一条 `apply_async` 消息到 Redis
3. **Worker 执行**：Worker 从 Redis 取任务，调用预测脚本，将结果状态写回数据库
4. **状态查询**：Flask API 查数据库获取每个场站的任务状态，不再查 PM2

## 数据模型

### prediction_tasks（任务配置）

每个场站的每种预测类型对应一条记录。5 场站 x 3 类型 = 15 条记录。

```sql
CREATE TABLE prediction_tasks (
    id                  SERIAL PRIMARY KEY,
    farm_code           VARCHAR(50) NOT NULL,
    task_type           VARCHAR(20) NOT NULL,  -- supershort / short / medium
    enabled             BOOLEAN DEFAULT FALSE,
    train_schedule      VARCHAR(20),           -- 训练时间 "03:00"
    predict_schedule    VARCHAR(100),          -- 预测 cron "*/15 * * * *" 或 "08:00"
    last_train_at       TIMESTAMP,
    last_predict_at     TIMESTAMP,
    last_train_status   VARCHAR(20),           -- success / failed / running
    last_predict_status VARCHAR(20),
    last_error          TEXT,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE(farm_code, task_type)
);
```

### prediction_runs（执行记录）

每次训练或预测的执行记录，取代 flag 文件和 task_history 表。

```sql
CREATE TABLE prediction_runs (
    id                  SERIAL PRIMARY KEY,
    task_id             INTEGER REFERENCES prediction_tasks(id),
    celery_task_id      VARCHAR(100),
    action              VARCHAR(20),  -- train / predict
    status              VARCHAR(20),  -- pending / running / success / failed
    started_at          TIMESTAMP,
    finished_at         TIMESTAMP,
    duration_sec        INTEGER,
    error_message       TEXT,
    result_summary      JSONB,        -- {"rmse": 0.12, "rows": 960}
    created_at          TIMESTAMP DEFAULT NOW()
);
```

### 状态查询简化

现有：`PM2 jlist -> 解析进程名 -> 匹配 {farm}_{type} -> 检查 status=="online"`

新：
```sql
SELECT farm_code, task_type, last_train_status, last_predict_status,
       last_train_at, last_predict_at
FROM prediction_tasks
WHERE farm_code IN (SELECT farm_code FROM wind_farms WHERE is_active = TRUE);
```

## Celery 任务定义

### 任务注册

```python
# tasks/prediction_tasks.py

@app.task(bind=True, max_retries=2, soft_time_limit=1800)
def train_model(self, farm_code, task_type):
    """训练模型 - 替代 auto_pre_train.py --mode train"""

@app.task(bind=True, max_retries=1, soft_time_limit=600)
def run_prediction(self, farm_code, task_type):
    """执行预测 - 替代 auto_pre_train.py --mode predict"""

@app.task(bind=True, max_retries=1, soft_time_limit=300)
def run_supershort_predict(self, farm_code):
    """超短期预测 - 替代 predict_supershort.py"""

@app.task
def merge_predictions(farm_code, date_str):
    """合并短期+中期预测 - 替代 scheduler_middle.py 的合并步骤"""
```

### 调度链（Canvas）

```python
# 短期每日链
short_chain = train_model.s(farm_code, 'short') | run_prediction.s('short')

# 中期每日链（含合并）
mid_chain = chain(
    group(train_model.s(farm_code, 'short'), train_model.s(farm_code, 'medium')),
    group(run_prediction.s('short'), run_prediction.s('medium')),
    merge_predictions.s(farm_code, today)
)

# 超短期（每15分钟）
run_supershort_predict.delay(farm_code)
```

### Beat 动态调度

从数据库读取调度配置，不使用静态 celerybeat-schedule 文件：

```python
def build_beat_schedule():
    tasks = db.query("SELECT * FROM prediction_tasks WHERE enabled = TRUE")
    schedule = {}
    for t in tasks:
        if t.task_type == 'supershort':
            schedule[f'{t.farm_code}_predict'] = {
                'task': 'run_supershort_predict',
                'args': (t.farm_code,),
                'schedule': crontab(minute='14,29,44,59'),
            }
        else:
            train_h, train_m = map(int, t.train_schedule.split(':'))
            schedule[f'{t.farm_code}_{t.task_type}_train'] = {
                'task': 'train_model',
                'args': (t.farm_code, t.task_type),
                'schedule': crontab(minute=train_m, hour=train_h),
            }
    return schedule
```

### 容错与重试

| 场景 | 现有处理 | Celery 处理 |
|------|---------|-------------|
| 训练失败 | flag 文件不会写，下次重跑 | `max_retries=2`，自动重试，记录错误到 DB |
| Worker 崩溃 | PM2 自动重启，但任务状态丢失 | 任务回到队列，其他 Worker 接手 |
| 重复执行 | flag 文件防重 | Celery `acks_late=True` + 幂等设计 |
| 超时 | 无控制 | `soft_time_limit` 自动终止 |
| 结果通知 | 只能看日志 | 写入 `prediction_runs` + 可扩展邮件/钉钉通知 |

## API 改造

### 保留的端点（改造实现）

| 端点 | 现有行为（PM2） | 新行为（Celery） |
|------|----------------|-----------------|
| `GET /status_all` | 查 `pm2 jlist` 解析进程状态 | 查 `prediction_tasks` 表 |
| `POST /start` | `pm2 start` 启动进程 | `UPDATE enabled=TRUE` |
| `POST /stop` | `pm2 stop` 停止进程 | `UPDATE enabled=FALSE` + 撤销待执行任务 |
| `POST /control_all` | 批量 pm2 操作 | 批量更新 `prediction_tasks.enabled` |
| `GET /logs` | 读 PM2 日志文件 | 查 `prediction_runs` 表 + worker 日志 |
| `GET /history` | 查 `task_history` | 查 `prediction_runs` 表 |

### 删除的端点

`POST /delete`、`POST /schedule`、`POST /save`、`POST /clearsave`、`POST /resurrect`、`GET /script_info`、`GET /task_status` — 这些都是 PM2 专有操作，不再需要。

### 新增的端点

| 端点 | 用途 |
|------|------|
| `POST /trigger` | 手动触发一次训练或预测（不等 Beat） |
| `GET /runs` | 查询执行历史（分页） |
| `PUT /schedule_config` | 修改某个场站某种类型的调度时间 |

### 响应格式变更

前端不再需要 `normalizeBizState` 猜测逻辑。后端直接返回结构化状态：

```json
{
  "farm_code": "BNJ",
  "status": {
    "supershort": {
      "enabled": true,
      "last_predict_at": "2026-04-18T14:29:00",
      "last_predict_status": "success",
      "next_predict_at": "2026-04-18T14:44:00"
    },
    "short": {
      "enabled": true,
      "last_train_at": "2026-04-18T03:00:00",
      "last_train_status": "success",
      "last_predict_at": "2026-04-18T08:00:00",
      "last_predict_status": "success"
    },
    "medium": { "..." }
  }
}
```

## Docker 部署

### 新的 docker-compose 服务

```yaml
autopredict-api:      # Flask API（端口 5001）
  depends_on: [redis, kingbase]

autopredict-worker:   # Celery Worker（新增）
  command: celery -A tasks.worker worker -c 4 --loglevel=info
  depends_on: [redis, kingbase]

autopredict-beat:     # Celery Beat 定时调度（新增）
  command: celery -A tasks.worker beat --loglevel=info
  depends_on: [redis, kingbase]

autopredict-flower:   # 可选监控面板（新增）
  command: celery -A tasks.worker flower --port=5555
  ports: ["5555:5555"]
  depends_on: [redis]
```

### 组件变更总结

| 组件 | 现在 | 改造后 |
|------|------|--------|
| Flask API | 直接调 PM2 | 发 Celery 任务 + 查 DB |
| PM2 + npm | 进程管理器 | **移除** |
| scheduler_*.py (3个) | Python schedule 轮询 | **移除**，Beat 替代 |
| auto_pre_train.py | 被 scheduler subprocess 调用 | **保留**，被 Celery Worker 调用 |
| Flag 文件 | 防重复执行 | **移除**，Celery 去重机制替代 |
| Redis | 已有但未给 autopredict 用 | 作为 Celery Broker |
| Flower | 无 | **新增**，5555 端口监控 |

## 迁移路径

### 阶段 1：基础设施（不破坏现有功能）

1. docker-compose 加入 Redis 连接配置
2. 创建 `prediction_tasks` 和 `prediction_runs` 表
3. 为现有 5 个场站初始化 15 条 `prediction_tasks` 记录
4. 编写 Celery 任务函数（调用现有 `auto_pre_train.py`）

### 阶段 2：并行运行

1. 启动 Celery Worker + Beat
2. 前端新增"查看 Celery 状态"入口
3. 新旧系统并行，Celery 写 `prediction_runs`，PM2 继续工作
4. 对比两边结果，确认一致

### 阶段 3：切换

1. 前端 `/status_all` 改为查 `prediction_tasks` 表
2. 停止 PM2 scheduler 进程
3. 移除 PM2 依赖和 scheduler_*.py
4. 全量回归测试

### 阶段 4：清理

1. 删除旧端点（delete/schedule/save/clearsave/resurrect）
2. 移除 Dockerfile 中的 npm/PM2 安装
3. 前端移除 `normalizeBizState` 兼容逻辑
