# 多场站适配使用指南

## 概述

本指南说明了如何使用多场站适配功能，将原有的单场站风电功率预测系统改造为支持多场站的系统。

## 改造内容

### 1. 数据库模型改造

#### 已支持多场站的模型（无需改造）
- ✅ 运行数据模型（operational_data.py）
  - WindSpeedData, TurbinePowerData, WeatherData等
  - 已包含farm_code字段

- ✅ 上报配置模型（report_config.py）
  - WindFarm, ReportConfig, ReportLog等
  - 已支持多场站

#### 新增场站支持的模型
- ✅ 功率预测结果（power.py）
  - ActualPower, SupershortlPower, ShortlPower, MidPower
  - 添加farm_code字段

- ✅ 训练相关模型（training.py）
  - Model, TrainingRecord, PredictionRecord等
  - 添加farm_code字段

- ✅ 天气数据获取（weather_fetch.py）
  - WeatherConnection, WeatherTask, WeatherLog等
  - 添加farm_code字段

### 2. 数据迁移策略

#### 迁移脚本
- `multi_station_migration.sql` - SQL迁移脚本
- `multi_station_migration.py` - Python迁移工具

#### 迁移步骤
1. 创建默认场站
2. 为相关表添加farm_code字段
3. 创建索引和外键约束
4. 移除原有unique约束
5. 创建复合唯一约束

### 3. 测试验证

#### 测试脚本
- `test_multi_station.py` - 多场站功能测试工具

#### 测试内容
- 创建测试场站
- 多场站数据存储
- 数据查询和统计
- 数据完整性检查
- 数据隔离性验证

## 使用方法

### 1. 执行数据迁移

```bash
# 进入backend目录
cd wind-power-forecast/backend

# 执行迁移脚本
python db_models/multi_station_migration.py
```

### 2. 验证迁移结果

```bash
# 执行功能测试
python db_models/test_multi_station.py
```

### 3. 手动验证

```sql
-- 查看场站列表
SELECT * FROM wind_farms;

-- 查看场站统计信息
SELECT * FROM station_summary_view;

-- 检查新字段是否存在
SELECT column_name FROM information_schema.columns
WHERE table_name = 'actual_power' AND column_name = 'farm_code';
```

## 业务影响

### 1. 数据查询影响

#### 原有查询（单场站）
```sql
SELECT * FROM actual_power WHERE timestamp > '2024-01-01';
```

#### 改造后查询（多场站）
```sql
-- 查询特定场站
SELECT * FROM actual_power
WHERE timestamp > '2024-01-01' AND farm_code = 'FARM_001';

-- 查询所有场站
SELECT * FROM actual_power WHERE timestamp > '2024-01-01';

-- 按场站统计
SELECT farm_code, AVG(wp_true) as avg_power
FROM actual_power
WHERE timestamp > '2024-01-01'
GROUP BY farm_code;
```

### 2. 业务逻辑影响

#### 数据插入
- 所有数据插入必须指定farm_code
- 默认值：DEFAULT_FARM

#### 预测服务
- 需要指定场站编码调用对应模型
- 每个场站独立的模型管理

#### 上报服务
- 按场站分别配置上报规则
- 每个场站独立的上报调度

## 注意事项

### 1. 向后兼容性
- 现有查询仍然可以工作
- 默认场站：DEFAULT_FARM
- 原有unique约束被移除

### 2. 性能考虑
- 新增farm_code索引
- 复合唯一约束
- 查询时建议使用farm_code条件

### 3. 数据安全
- 执行迁移前请备份数据库
- 测试环境验证后再在生产环境执行
- 保留回滚方案

## 常见问题

### Q1: 如何添加新场站？
```sql
INSERT INTO wind_farms (farm_code, farm_name, capacity, location, is_active)
VALUES ('FARM_002', '新风电场', 100.0, '北京市', true);
```

### Q2: 如何修改数据查询？
在WHERE条件中添加farm_code字段：
```sql
-- 原查询
SELECT * FROM actual_power WHERE timestamp > '2024-01-01';

-- 新查询（推荐）
SELECT * FROM actual_power
WHERE timestamp > '2024-01-01' AND farm_code = 'FARM_001';
```

### Q3: 如何验证数据迁移是否成功？
```sql
-- 检查字段是否存在
SELECT column_name FROM information_schema.columns
WHERE table_name = 'actual_power' AND column_name = 'farm_code';

-- 检查默认场站
SELECT * FROM wind_farms WHERE farm_code = 'DEFAULT_FARM';

-- 查看统计信息
SELECT * FROM station_summary_view;
```

## 下一步

1. **第二阶段**：改造数据采集逻辑
2. **第三阶段**：改造预测服务逻辑
3. **第四阶段**：改造上报服务逻辑
4. **第五阶段**：微服务架构迁移

## 技术支持

如遇到问题，请检查：
1. 迁移日志文件：multi_station_migration.log
2. 数据库连接配置
3. 数据库权限设置
4. 表结构和索引状态