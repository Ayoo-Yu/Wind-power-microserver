# wp_true 预测表回填功能说明

## 功能概述

本次更新为超短期模型的训练和预测流程增加了智能的wp_true空值处理功能。当遇到较长时间段的wp_true缺失时，系统会优先使用历史预测数据进行回填，提高数据质量。

## 处理逻辑

新的`interpolate_and_ffill_wp_true`函数按以下优先级处理wp_true空值：

### 1. 预测表回填（最高优先级）
从以下数据库表中按优先级获取历史预测值：

#### SupershortlPower表
- 表中包含的预测列为 `wp_pred2` 到 `wp_pred17`。
- 对于目标时间戳 `target_T`，系统会查找 `wp_predS` (其中 `S` 从 2 到 17)。
- 该 `wp_predS` 值来自于 `source_T` 的记录，其中 `source_T = target_T - (S-2)*15分钟`。
- 例如：
    - 要回填 `target_T = 10:00` 的 `wp_true`：
        - 使用 `wp_pred2`：查找 `source_T = 10:00 - (2-2)*15min = 10:00` 记录的 `wp_pred2`。
        - 使用 `wp_pred3`：查找 `source_T = 10:00 - (3-2)*15min = 09:45` 记录的 `wp_pred3`。
        - ...
        - 使用 `wp_pred17`：查找 `source_T = 10:00 - (17-2)*15min = 10:00 - 225min = 06:15` 记录的 `wp_pred17`。

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

`SupershortlPower`表中的每一行代表一个预测的 "发起时间戳"（我们称之为 `record_timestamp`）。
该行中的 `wp_predS` (其中 `S` 的范围是 2 到 17) 是对未来某个时间点的预测。
具体来说，`wp_predS` 是对 `record_timestamp + (S-2)*15分钟` 这个目标时间点的预测。

**示例：**
`SupershortlPower` 表中有一条记录，其 `timestamp` (即 `record_timestamp`) 是 `10:00`：
- `wp_pred2` 是对 `10:00 + (2-2)*15min = 10:00` 的预测。
- `wp_pred3` 是对 `10:00 + (3-2)*15min = 10:15` 的预测。
- `wp_pred4` 是对 `10:00 + (4-2)*15min = 10:30` 的预测。
- ...
- `wp_pred17` 是对 `10:00 + (17-2)*15min = 10:00 + 225min = 13:45` 的预测。

**反向查找（用于回填 `wp_true`）：**
当我们需要为 `target_timestamp` (例如 `10:00`) 找到一个历史预测值进行回填时：
我们会遍历 `S` 从 2 到 17：
1.  **目标：使用 `wp_predS` 回填 `target_timestamp`。**
2.  这个 `wp_predS` 值应该来自于哪个记录的 `timestamp` 呢？
    我们知道 `wp_predS` 预测的是其所在记录 `timestamp` 之后的 `(S-2)*15分钟`。
    所以，如果 `wp_predS` 要预测 `target_timestamp`，那么它所在的记录的 `timestamp` 必须是 `target_timestamp - (S-2)*15分钟`。

    - 对于 `S=2` (`wp_pred2`)：
        源记录时间戳 = `10:00 - (2-2)*15min = 10:00`。
        我们查找 `timestamp = 10:00` 的记录，并使用其 `wp_pred2` 列。
    - 对于 `S=3` (`wp_pred3`)：
        源记录时间戳 = `10:00 - (3-2)*15min = 09:45`。
        我们查找 `timestamp = 09:45` 的记录，并使用其 `wp_pred3` 列。
    - 对于 `S=17` (`wp_pred17`)：
        源记录时间戳 = `10:00 - (17-2)*15min = 06:15`。
        我们查找 `timestamp = 06:15` 的记录，并使用其 `wp_pred17` 列。

## 使用的文件

### 修改的文件
1. **data_processor_supershort.py**
   - `get_backfill_value_from_prediction_tables()` 函数逻辑更新，以适配 `SupershortlPower` 表中的 `wp_pred2` 到 `wp_pred17` 列及相应的时间偏移。

2. **predict_supershort.py**
   - 内部模型训练和预测仍基于 `shift` 1到16。
   - 输出到宽格式CSV (`supershortl_wide_...csv`) 时，列名从 `wp_pred1..16` 调整为 `wp_pred2..17`。
     (例如，内部 `shift_1` 的结果保存为 `wp_pred2`，`shift_16` 的结果保存为 `wp_pred17`)

3. **train_supershort.py**
    - 训练逻辑仍基于 `MIN_SHIFT=1` 和 `MAX_SHIFT=16`。

### 新增的文件
1. **test_backfill.py** - 测试脚本，验证新功能是否正常工作 (此文件内容未提供，假设用户会自行调整或创建)

## 测试

运行测试脚本验证功能 (路径可能需要根据实际情况调整)：
```bash
cd wind-power-forecast/backend/auto_scripts/scripts/supershort/
python test_backfill.py
```

## 日志记录

新功能会详细记录处理过程：
- 预测表回填的数量和来源 (例如 `源时间戳=2024-01-15 09:45:00, 使用列 wp_pred3=...`)
- 各个处理步骤的效果
- 最终的空值处理结果

示例日志输出：
```
INFO - 开始处理'wp_true'列的15个空值
INFO - 步骤1: 尝试使用预测表回填空值...
INFO - 从SupershortlPower表获取回填值: 源时间戳=2024-01-15 09:45:00, 使用列 wp_pred3=85.6 (目标时间戳=2024-01-15 10:00:00)
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
3. **时间对应精确**: 考虑了SupershortlPower表中各预测列 (`wp_pred2` 到 `wp_pred17`) 的时间对应关系
4. **向下兼容**: 如果预测表没有数据，仍然使用传统插值方法
5. **详细日志**: 完整记录处理过程，便于调试和监控

## 注意事项

1. 需要确保数据库中的 `SupershortlPower` 表（或其他相关表）已更新为包含 `wp_pred2` 到 `wp_pred17` 的列。
2. 预测表的时间戳应该与实际数据对齐
3. 功能依赖数据库连接，如果数据库不可用会自动降级到传统插值方法 
