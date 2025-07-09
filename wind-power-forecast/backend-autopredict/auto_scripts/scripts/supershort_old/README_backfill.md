# wp_true 预测表回填功能说明

## 功能概述

本次更新为超短期模型的训练和预测流程增加了智能的wp_true空值处理功能。当遇到较长时间段的wp_true缺失时，系统会优先使用历史预测数据进行回填，提高数据质量。

## 处理逻辑

新的`interpolate_and_ffill_wp_true`函数按以下优先级处理wp_true空值：

### 1. 预测表回填（最高优先级）
从以下数据库表中按优先级获取历史预测值：

#### SupershortlPower表
- **直接匹配**: 对于时间戳T，优先使用SupershortlPower表中时间戳T的wp_pred2
- **时间偏移匹配**: 
  - 时间戳T-15min的wp_pred3 对应 时间戳T的预测
  - 时间戳T-30min的wp_pred4 对应 时间戳T的预测
  - 时间戳T-45min的wp_pred5 对应 时间戳T的预测
  - ...依此类推到wp_pred17

#### ShortlPower表
- 如果SupershortlPower表没有可用数据，使用ShortlPower表中对应时间戳的wp_pred

#### MidPower表
- 如果前两个表都没有可用数据，使用MidPower表中对应时间戳的wp_pred

### 2. 线性插值
对仍然存在的空值，如果前后有非空值，进行线性插值

### 3. 后向填充(bfill)
对序列开头的空值进行后向填充

### 4. 前向填充(ffill)
对序列末尾的空值进行前向填充

## 时间戳对应关系详解

SupershortlPower表中的预测值与时间戳的对应关系：

```
时间戳      wp_pred2  wp_pred3  wp_pred4  wp_pred5  ...  wp_pred17
10:00         ↓        ↓        ↓        ↓              ↓
预测目标     10:00    10:15    10:30    10:45    ...   14:00

反向查找目标时间10:00的预测值：
- 10:00时间戳的wp_pred2 → 预测10:00
- 09:45时间戳的wp_pred3 → 预测10:00  
- 09:30时间戳的wp_pred4 → 预测10:00
- 09:15时间戳的wp_pred5 → 预测10:00
- ...
```

## 使用的文件

### 修改的文件
1. **data_processor_supershort.py**
   - 添加了`get_backfill_value_from_prediction_tables()`函数
   - 增强了`interpolate_and_ffill_wp_true()`函数
   - 添加了预测表模型导入

2. **predict_supershort.py**
   - 添加了预测表模型导入
   - 简化了`handle_wp_true_missing()`函数

### 新增的文件
1. **test_backfill.py** - 测试脚本，验证新功能是否正常工作

## 测试

运行测试脚本验证功能：
```bash
cd wind-power-forecast/backend-autopredict/auto_scripts/scripts/supershort/
python test_backfill.py
```

## 日志记录

新功能会详细记录处理过程：
- 预测表回填的数量和来源
- 各个处理步骤的效果
- 最终的空值处理结果

示例日志输出：
```
INFO - 开始处理'wp_true'列的15个空值
INFO - 步骤1: 尝试使用预测表回填空值...
INFO - 从SupershortlPower表获取回填值: 时间戳=2024-01-15 10:00:00, wp_pred2=85.6
INFO - 预测表回填处理了8个空值，剩余7个空值
INFO - 步骤2: 进行线性插值...
INFO - 线性插值处理了5个空值，剩余2个空值
INFO - 步骤3: 进行后向填充...
INFO - 后向填充处理了1个空值，剩余1个空值
INFO - 步骤4: 进行前向填充...
INFO - 前向填充处理了1个空值，剩余0个空值
INFO - 'wp_true'列空值处理完成: 原始15个空值, 预测表回填8个, 线性插值5个, 后向填充1个, 前向填充1个, 最终剩余0个空值
```

## 优势

1. **智能回填**: 优先使用相关的历史预测值，比简单插值更准确
2. **多层次备选**: 三个预测表提供多种备选数据源
3. **时间对应精确**: 考虑了SupershortlPower表中各预测列的时间对应关系
4. **向下兼容**: 如果预测表没有数据，仍然使用传统插值方法
5. **详细日志**: 完整记录处理过程，便于调试和监控

## 注意事项

1. 需要确保数据库中有相应的预测表数据
2. 预测表的时间戳应该与实际数据对齐
3. 功能依赖数据库连接，如果数据库不可用会自动降级到传统插值方法 