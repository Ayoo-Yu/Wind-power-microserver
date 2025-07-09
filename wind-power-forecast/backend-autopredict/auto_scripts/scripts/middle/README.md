# 风电功率预测系统

该系统用于短期风电功率预测，基于历史数据和气象数据，使用机器学习方法进行预测。

## 文件结构

- `auto_pre_train.py`: 主脚本，负责自动化训练和预测流程
- `config.py`: 配置文件，包含各种路径和参数设置
- `data_processor.py`: 数据处理功能，包括特征工程、窗口创建等
- `models.py`: 定义模型参数，支持多版本参数管理
- `param_optimizer.py`: 参数优化器，用于定期优化模型参数
- `predict.py`: 模型预测功能
- `RandomizedSearchCV.py`: 参数随机搜索工具
- `scheduler_middle.py`: 定时调度脚本，管理训练、预测和参数优化任务
- `train.py`: 模型训练功能
- `utils.py`: 工具函数，包括评估、可视化等

## 新增功能: 自动参数优化

系统新增了自动参数优化功能，可以定期（默认每周一次）对模型超参数进行优化，提高预测精度。

### 功能特点

1. **定期优化**: 通过`scheduler_middle.py`配置，每周一2:00自动执行参数优化任务
2. **多模型支持**: 同时优化GBDT、DART和GOSS三种算法的参数
3. **版本管理**: 在`models.py`中实现参数版本管理，按日期命名和记录
4. **改进阈值**: 只有当所有算法性能均有显著改进（默认2%）时才更新参数
5. **完整日志**: 详细记录优化过程和结果，便于分析

### 配置参数

在`config.py`中可以调整以下参数:

- `PARAM_OPT_ITERATIONS`: 随机搜索迭代次数，默认30
- `PARAM_OPT_WEEKLY`: 是否启用每周参数优化，默认为True
- `PARAM_OPT_MIN_IMPROVEMENT`: 最小改进阈值，默认0.02（2%）

### 手动运行

除了定时运行外，也可以手动运行参数优化:

```bash
python param_optimizer.py
```

系统会自动获取最新数据，进行参数随机搜索，并在性能有显著提升时更新`models.py`文件。

### 调整优化策略

可以通过修改`param_optimizer.py`中的`find_best_params`调用来调整随机搜索的参数范围和策略，或者修改`RandomizedSearchCV.py`中的实现来完全自定义优化过程。 