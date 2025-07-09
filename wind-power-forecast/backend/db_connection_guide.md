# 数据库连接自动管理指南

本指南介绍如何在应用程序中实现自动管理数据库连接，无需手动监控或关闭连接。

## 基本原则

在Flask/Python应用中，有以下几种方式确保数据库连接自动关闭：

1. **使用上下文管理器**：最推荐的方式，通过`with`语句自动管理连接生命周期
2. **请求结束时清理**：利用Flask的请求生命周期钩子自动清理资源
3. **连接池配置**：适当配置SQLAlchemy连接池，自动回收长时间空闲的连接

## 实现方式

### 1. 使用上下文管理器（推荐）

```python
from db_session import db_session

@app.route('/api/users')
def get_users():
    with db_session() as session:
        users = session.query(User).all()
        # 处理数据...
        return jsonify(result)
    # 连接已自动关闭，无需手动处理
```

### 2. 使用依赖注入并确保关闭

```python
from db_session import get_db

@app.route('/api/products')
def get_products():
    db = next(get_db())
    try:
        products = db.query(Product).all()
        # 处理数据...
        return jsonify(result)
    finally:
        db.close()  # 确保连接关闭
```

### 3. 利用Flask的请求钩子（自动处理）

系统已配置全局请求结束钩子，会自动清理未关闭的连接。但不要依赖这个作为主要关闭连接的方式。

## 连接池设置

我们已经优化了连接池配置：

```python
engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    pool_size=10,                # 初始连接池大小
    max_overflow=20,             # 允许的额外连接数
    pool_timeout=30,             # 等待连接的超时时间(秒)
    pool_recycle=1800,           # 连接回收时间(30分钟)
    pool_pre_ping=True,          # 使用前检查连接是否有效
    reset_on_return='commit',    # 连接归还时执行操作(提交或回滚)
    pool_disconnect_on_timeout=True  # 允许在空闲超时时自动断开连接
)
```

这些设置确保：
- 连接使用前会检查有效性 (`pool_pre_ping=True`)
- 连接归还时会自动提交或回滚未完成的事务 (`reset_on_return='commit'`)
- 长时间空闲的连接会自动关闭 (`pool_recycle=1800`)

## 典型问题及解决方案

1. **连接泄漏**
   - 症状：大量"idle in transaction"连接
   - 解决：使用上下文管理器或确保finally代码块中关闭连接

2. **事务未提交**
   - 症状：数据库操作无效果
   - 解决：确保`session.commit()`被调用或使用上下文管理器

3. **长事务**
   - 症状：连接长时间被占用
   - 解决：将大型操作拆分为多个小事务

## 示例代码

参考`routes/example_route.py`文件，其中展示了各种连接管理的最佳实践。

## 部署到Linux服务器

此机制与操作系统无关，在Linux上同样有效。无需额外的监控脚本或任务计划。 