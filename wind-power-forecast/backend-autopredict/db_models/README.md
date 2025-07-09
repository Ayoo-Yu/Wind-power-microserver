# 数据库模型目录 (db_models)

本目录包含风电预测系统的所有SQLAlchemy数据库模型定义。

## 目录结构

- `__init__.py` - 导入并导出所有模型
- `base.py` - 定义Base和通用混入类
- `dataset.py` - 数据集相关模型
- `power.py` - 功率数据相关模型
- `training.py` - 训练相关模型
- `user.py` - 用户相关模型
- `task.py` - 任务历史相关模型
- `training_history.py` - 训练历史记录模型
- `user_roles.py` - 用户角色模型

## 关于命名

我们将此目录命名为`db_models`而不是`models`，是为了避免与机器学习模型存储的目录名冲突：
- `db_models/` - 存放数据库模型定义（SQLAlchemy模型）
- `models/` - 存放机器学习模型文件

## 使用方法

在您的代码中，请使用以下导入语法：

```python
from db_models import Base, User, Model  # 导入特定模型
```

或者：

```python
from db_models.user import User  # 从特定模块导入
```

## 说明

原来的`models.py`文件仍然可以使用，但会显示弃用警告。建议直接从`db_models`包导入模型。 