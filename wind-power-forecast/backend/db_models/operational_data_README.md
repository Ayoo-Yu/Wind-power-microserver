# 风电运行数据模型说明

## 概述

本文档介绍了新增的风电运行数据模型，这些模型扩展了原有的上报系统，支持更多类型的运行数据上报。

## 新增数据模型

### 1. 单机数据

#### WindSpeedData - 单机风速数据
存储每台风机的风速、风向等信息。

**字段说明：**
- `turbine_id`: 单机编号
- `farm_code`: 场站编码
- `wind_speed`: 风速 (m/s)
- `wind_direction`: 风向 (度)
- `nacelle_position`: 机舱位置 (度)

#### TurbinePowerData - 单机功率数据
存储每台风机的功率运行参数。

**字段说明：**
- `turbine_id`: 单机编号
- `farm_code`: 场站编码
- `active_power`: 有功功率 (kW)
- `reactive_power`: 无功功率 (kVar)
- `power_factor`: 功率因数
- `rotor_speed`: 转子转速 (rpm)
- `generator_speed`: 发电机转速 (rpm)
- `blade_angle`: 桨叶角度 (度)
- `turbine_status`: 机组状态

### 2. 气象信息

#### WeatherData - 气象信息数据
存储风电场的气象观测数据。

**字段说明：**
- `farm_code`: 场站编码
- `temperature`: 温度 (℃)
- `humidity`: 湿度 (%)
- `pressure`: 气压 (hPa)
- `wind_speed_avg`: 平均风速 (m/s)
- `wind_speed_max`: 最大风速 (m/s)
- `wind_direction`: 风向 (度)
- `visibility`: 能见度 (km)
- `precipitation`: 降水量 (mm)
- `weather_condition`: 天气状况

### 3. 容量信息

#### InstalledCapacityData - 装机容量数据
存储风电场的装机容量信息。

**字段说明：**
- `farm_code`: 场站编码
- `total_capacity`: 总装机容量 (MW)
- `turbine_count`: 风机数量
- `turbine_capacity`: 单机容量 (MW)
- `commissioning_date`: 投运日期
- `remarks`: 备注

#### AvailableCapacityData - 可用容量数据
存储风电场的实时可用容量信息。

**字段说明：**
- `farm_code`: 场站编码
- `available_capacity`: 可用容量 (MW)
- `maintenance_capacity`: 检修容量 (MW)
- `fault_capacity`: 故障容量 (MW)
- `limited_capacity`: 受限容量 (MW)
- `availability_rate`: 可用率 (%)
- `maintenance_turbines`: 检修风机数量
- `fault_turbines`: 故障风机数量

### 4. 功率数据

#### TheoreticalPowerData - 理论功率数据
存储基于气象条件计算的理论功率。

**字段说明：**
- `farm_code`: 场站编码
- `theoretical_power`: 理论功率 (MW)
- `wind_speed_hub`: 轮毂高度风速 (m/s)
- `air_density`: 空气密度 (kg/m³)
- `power_curve_factor`: 功率曲线修正系数
- `wake_loss_factor`: 尾流损失系数
- `availability_factor`: 可用率系数

#### AvailablePowerData - 可用功率数据
存储考虑各种约束后的可用功率。

**字段说明：**
- `farm_code`: 场站编码
- `available_power`: 可用功率 (MW)
- `grid_constraint`: 电网约束 (MW)
- `environmental_constraint`: 环境约束 (MW)
- `maintenance_constraint`: 检修约束 (MW)
- `operational_constraint`: 运行约束 (MW)
- `grid_availability`: 电网可用率 (%)
- `constraint_reason`: 约束原因

## 上报类型说明

新增的上报类型包括：

1. **wind_speed**: 单机风速上报
2. **turbine_power**: 单机功率上报
3. **weather**: 气象信息上报
4. **installed_capacity**: 装机容量上报
5. **available_capacity**: 可用容量上报
6. **theoretical_power**: 理论功率上报
7. **available_power**: 可用功率上报

## 数据库表创建

使用提供的脚本创建数据表：

```bash
cd wind-power-forecast/backend
python create_operational_tables.py
```

**注意：**
1. 运行前请先修改脚本中的数据库连接配置
2. 确保数据库用户有创建表的权限
3. 建议先在开发环境测试

## 使用说明

### 1. 配置上报

在前端的"上报配置管理"中：
1. 选择风电场站
2. 选择对应的上报类型
3. 配置目标IP和端口
4. 设置上报周期
5. 启用配置

### 2. 数据预览和手动上报

1. 在配置列表中点击"预览上报"
2. 查看当前时刻的数据
3. 可以修改数据内容
4. 点击"手动上报"执行上报

### 3. 监控上报状态

1. 查看"上报日志"了解上报历史
2. 查看"上报数据质量统计"了解数据完整性
3. 使用过滤条件筛选特定类型的日志

## 数据完整性检查

系统会根据不同的数据类型检查关键字段的完整性：

- **单机风速**: 检查风速、风向、机舱位置
- **单机功率**: 检查有功功率、无功功率、功率因数
- **气象信息**: 检查温度、湿度、气压、平均风速
- **装机容量**: 检查总容量、风机数量、单机容量
- **可用容量**: 检查可用容量、可用率
- **理论功率**: 检查理论功率、轮毂风速、空气密度
- **可用功率**: 检查可用功率、电网可用率

## 注意事项

1. **数据时间戳**: 所有数据都使用timestamp字段作为时间标识
2. **场站编码**: farm_code字段用于关联风电场站
3. **数据来源**: data_source字段标识数据来源（database/template/manual）
4. **单机数据**: 需要turbine_id字段标识具体的风机
5. **数据完整性**: 系统会自动计算和统计数据完整率 