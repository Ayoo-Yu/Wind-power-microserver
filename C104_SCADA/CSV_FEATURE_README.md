# CSV数据写入功能说明

## 功能概述

在SCADA客户端中已添加CSV数据写入功能，在**第一个时机**（总召唤GI成功后上传刻钟数据）后将数据写入CSV文件。

## 实现细节

### 触发时机
- **时间点**: 在每个整15分钟（0, 15, 30, 45分钟）
- **触发条件**: 
  1. 总召唤(GI)成功执行
  2. API上传成功
  3. 数据质量为GOOD
  4. 当前15分钟整点与上次上传的15分钟整点不同

### CSV文件特性
- **文件位置**: `csv_data/scada_data_YYYYMMDD.csv`
- **文件格式**: 
  - 表头: `timestamp,value`
  - 数据格式: `YYYY-MM-DD HH:MM:SS,数值`
- **时间**: 使用北京时间
- **时间戳**: 取15分钟整点（例如: 14:15:00, 14:30:00, 14:45:00, 15:00:00）
- **编码**: UTF-8

### 文件管理
- 按日期自动生成新文件
- 文件名示例: `scada_data_20240115.csv`
- 自动创建`csv_data`目录
- 新文件自动添加表头

## 代码修改

### 1. 导入模块
```python
import csv
```

### 2. 添加CSV写入函数
```python
def write_to_csv(timestamp_beijing, value, logger):
    """将时间戳和数据写入CSV文件"""
```

### 3. 集成到上传流程
在`check_and_perform_quarter_upload()`函数中，API上传成功后调用：
```python
if upload_success:
    last_upload_quarter_minute = current_target_quarter_minute_beijing
    logger.info(f"GI QUARTER UPLOAD: Successfully uploaded...")
    
    # 在API上传成功后，将数据写入CSV文件
    write_to_csv(beijing_timestamp_for_api, value_for_upload, logger)
```

## 示例CSV文件内容

```csv
timestamp,value
2024-01-15 14:15:00,123.45
2024-01-15 14:30:00,124.12
2024-01-15 14:45:00,125.67
2024-01-15 15:00:00,126.34
```

## 日志输出

成功写入CSV时会在日志中看到类似信息：
```
CSV WRITE: Successfully wrote data to csv_data/scada_data_20240115.csv: 2024-01-15 14:15:00, 123.45
```

## 注意事项

1. 只有在API上传成功后才会写入CSV文件
2. 时间戳自动调整为15分钟整点
3. 文件按日期分割，便于数据管理
4. 所有操作都有完整的日志记录
5. 异常处理确保CSV写入失败不影响主要SCADA功能 