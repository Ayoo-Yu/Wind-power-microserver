# 运营数据CSV上传指南

## 概述

本指南将指导您如何使用 Postman 将 CSV 数据上传到风电功率预测系统的运营数据表中。系统支持 7 种不同类型的运营数据表。

## 支持的数据表

| 表名 | 中文描述 | 主要用途 |
|------|----------|----------|
| `wind_speed_data` | 单机风速数据 | 记录各风机的风速、风向等数据 |
| `turbine_power_data` | 单机功率数据 | 记录各风机的功率输出和运行状态 |
| `weather_data` | 气象信息数据 | 记录气象站的天气数据 |
| `installed_capacity_data` | 装机容量数据 | 记录风电场的装机容量信息 |
| `available_capacity_data` | 可用容量数据 | 记录风电场的可用容量和故障信息 |
| `theoretical_power_data` | 理论功率数据 | 记录理论功率计算相关数据 |
| `available_power_data` | 可用功率数据 | 记录可用功率和约束信息 |

## API 端点

### 基础 URL
```
http://localhost:5000/operational
```
（请根据实际部署情况调整 IP 地址和端口）

### 主要端点

1. **获取支持的表列表**
   - **URL**: `GET /operational/api/operational_tables`
   - **描述**: 获取所有支持的运营数据表名称和描述

2. **获取表结构信息**
   - **URL**: `GET /operational/api/operational_table_schema/{table_name}`
   - **描述**: 获取指定表的字段结构信息
   - **参数**: `table_name` - 表名（如 `wind_speed_data`）

3. **上传CSV数据**
   - **URL**: `POST /operational/api/upload_operational_csv`
   - **描述**: 上传CSV文件到指定的运营数据表

## Postman 使用步骤

### 步骤 1: 准备 CSV 文件

#### CSV 文件要求
- **编码**: UTF-8
- **分隔符**: 逗号（`,`）
- **必需列**: `timestamp` （时间戳列）
- **时间格式**: `YYYY-MM-DD HH:MM:SS` (如: `2025-01-15 14:30:00`)

#### 示例CSV格式

**单机风速数据 (wind_speed_data)**:
```csv
timestamp,turbine_id,farm_code,wind_speed,wind_direction,nacelle_position
2025-01-15 14:30:00,WT001,FARM001,8.5,180.0,185.2
2025-01-15 14:45:00,WT002,FARM001,9.2,175.5,180.1
```

**单机功率数据 (turbine_power_data)**:
```csv
timestamp,turbine_id,farm_code,active_power,reactive_power,power_factor,rotor_speed,generator_speed,blade_angle,turbine_status
2025-01-15 14:30:00,WT001,FARM001,1500.5,150.2,0.92,15.5,1650.0,8.5,运行
2025-01-15 14:45:00,WT002,FARM001,1750.8,200.1,0.89,18.2,1720.0,12.0,运行
```

### 步骤 2: 在 Postman 中设置请求

#### 2.1 创建新请求
1. 打开 Postman
2. 点击 "New" → "HTTP Request"
3. 设置请求方法为 `POST`

#### 2.2 设置请求 URL
```
http://localhost:5000/operational/api/upload_operational_csv
```

#### 2.3 设置请求头
- 通常不需要手动设置 `Content-Type`，Postman 会自动处理

#### 2.4 设置请求体 (Body)
1. 选择 `Body` 标签
2. 选择 `form-data` 选项
3. 添加以下字段：

| Key | Type | Value | 描述 |
|-----|------|-------|------|
| `file` | File | 选择您的 CSV 文件 | 要上传的 CSV 文件 |
| `table_name` | Text | 例如：`wind_speed_data` | 目标数据表名 |

#### 2.5 发送请求
点击 "Send" 按钮发送请求

### 步骤 3: 解读响应

#### 成功响应 (200)
```json
{
    "message": "成功处理表 wind_speed_data 的CSV数据",
    "inserted_count": 100,
    "updated_count": 0
}
```

#### 部分成功响应 (207)
```json
{
    "warning": "处理表 wind_speed_data 的CSV数据时遇到 2 个错误",
    "inserted_count": 98,
    "updated_count": 0,
    "error_count": 2,
    "errors": [
        "第 50 行: 映射/验证行时出错 - 无法解析时间戳或时间戳缺失",
        "第 85 行: 映射/验证行时出错 - 无法转换字段 'wind_speed' 的值 'abc'"
    ]
}
```

#### 错误响应 (400/500)
```json
{
    "error": "无效或缺失的 'table_name'。必须是以下之一: ['wind_speed_data', 'turbine_power_data', ...]"
}
```

## 详细字段说明

### 1. 单机风速数据 (wind_speed_data)
| 字段名 | 类型 | 必需 | 描述 | 示例 |
|--------|------|------|------|------|
| timestamp | DateTime | ✓ | 时间戳 | 2025-01-15 14:30:00 |
| turbine_id | String(50) | ✓ | 风机编号 | WT001 |
| farm_code | String(50) | ✓ | 场站编码 | FARM001 |
| wind_speed | Float |  | 风速 (m/s) | 8.5 |
| wind_direction | Float |  | 风向 (度) | 180.0 |
| nacelle_position | Float |  | 机舱位置 (度) | 185.2 |

### 2. 单机功率数据 (turbine_power_data)
| 字段名 | 类型 | 必需 | 描述 | 示例 |
|--------|------|------|------|------|
| timestamp | DateTime | ✓ | 时间戳 | 2025-01-15 14:30:00 |
| turbine_id | String(50) | ✓ | 风机编号 | WT001 |
| farm_code | String(50) | ✓ | 场站编码 | FARM001 |
| active_power | Float |  | 有功功率 (kW) | 1500.5 |
| reactive_power | Float |  | 无功功率 (kVar) | 150.2 |
| power_factor | Float |  | 功率因数 | 0.92 |
| rotor_speed | Float |  | 转子转速 (rpm) | 15.5 |
| generator_speed | Float |  | 发电机转速 (rpm) | 1650.0 |
| blade_angle | Float |  | 桨叶角度 (度) | 8.5 |
| turbine_status | String(20) |  | 机组状态 | 运行 |

### 3. 气象信息数据 (weather_data)
| 字段名 | 类型 | 必需 | 描述 | 示例 |
|--------|------|------|------|------|
| timestamp | DateTime | ✓ | 时间戳 | 2025-01-15 14:30:00 |
| farm_code | String(50) | ✓ | 场站编码 | FARM001 |
| temperature | Float |  | 温度 (℃) | 25.5 |
| humidity | Float |  | 湿度 (%) | 65.0 |
| pressure | Float |  | 气压 (hPa) | 1013.2 |
| wind_speed_avg | Float |  | 平均风速 (m/s) | 8.5 |
| wind_speed_max | Float |  | 最大风速 (m/s) | 12.0 |
| wind_direction | Float |  | 风向 (度) | 180.0 |
| visibility | Float |  | 能见度 (km) | 20.0 |
| precipitation | Float |  | 降水量 (mm) | 0.0 |
| weather_condition | String(50) |  | 天气状况 | 晴 |

### 4. 装机容量数据 (installed_capacity_data)
| 字段名 | 类型 | 必需 | 描述 | 示例 |
|--------|------|------|------|------|
| timestamp | DateTime | ✓ | 时间戳 | 2025-01-15 14:30:00 |
| farm_code | String(50) | ✓ | 场站编码 | FARM001 |
| total_capacity | Float | ✓ | 总装机容量 (MW) | 100.0 |
| turbine_count | Integer |  | 风机数量 | 50 |
| turbine_capacity | Float |  | 单机容量 (MW) | 2.0 |
| commissioning_date | DateTime |  | 投运日期 | 2020-06-15 |
| remarks | Text |  | 备注 | 风电场相关信息 |

### 5. 可用容量数据 (available_capacity_data)
| 字段名 | 类型 | 必需 | 描述 | 示例 |
|--------|------|------|------|------|
| timestamp | DateTime | ✓ | 时间戳 | 2025-01-15 14:30:00 |
| farm_code | String(50) | ✓ | 场站编码 | FARM001 |
| available_capacity | Float | ✓ | 可用容量 (MW) | 95.0 |
| maintenance_capacity | Float |  | 检修容量 (MW) | 4.0 |
| fault_capacity | Float |  | 故障容量 (MW) | 1.0 |
| limited_capacity | Float |  | 受限容量 (MW) | 0.0 |
| availability_rate | Float |  | 可用率 (%) | 95.0 |
| maintenance_turbines | Integer |  | 检修风机数量 | 2 |
| fault_turbines | Integer |  | 故障风机数量 | 1 |

### 6. 理论功率数据 (theoretical_power_data)
| 字段名 | 类型 | 必需 | 描述 | 示例 |
|--------|------|------|------|------|
| timestamp | DateTime | ✓ | 时间戳 | 2025-01-15 14:30:00 |
| farm_code | String(50) | ✓ | 场站编码 | FARM001 |
| theoretical_power | Float | ✓ | 理论功率 (MW) | 85.5 |
| wind_speed_hub | Float |  | 轮毂高度风速 (m/s) | 8.5 |
| air_density | Float |  | 空气密度 (kg/m³) | 1.225 |
| power_curve_factor | Float |  | 功率曲线修正系数 | 1.0 |
| wake_loss_factor | Float |  | 尾流损失系数 | 0.9 |
| availability_factor | Float |  | 可用率系数 | 0.95 |

### 7. 可用功率数据 (available_power_data)
| 字段名 | 类型 | 必需 | 描述 | 示例 |
|--------|------|------|------|------|
| timestamp | DateTime | ✓ | 时间戳 | 2025-01-15 14:30:00 |
| farm_code | String(50) | ✓ | 场站编码 | FARM001 |
| available_power | Float | ✓ | 可用功率 (MW) | 80.0 |
| grid_constraint | Float |  | 电网约束 (MW) | 5.0 |
| environmental_constraint | Float |  | 环境约束 (MW) | 0.0 |
| maintenance_constraint | Float |  | 检修约束 (MW) | 4.0 |
| operational_constraint | Float |  | 运行约束 (MW) | 1.0 |
| grid_availability | Float |  | 电网可用率 (%) | 98.0 |
| constraint_reason | Text |  | 约束原因 | 电网调度 |

## 常见问题

### Q1: 如何处理中文编码问题？
**A**: 确保您的 CSV 文件使用 UTF-8 编码保存。在 Excel 中可以选择"CSV UTF-8（逗号分隔）"格式。

### Q2: 时间戳格式不正确怎么办？
**A**: 时间戳必须使用格式 `YYYY-MM-DD HH:MM:SS`，例如 `2025-01-15 14:30:00`。

### Q3: 上传大文件时超时怎么办？
**A**: 系统支持分块处理，建议将大文件分割成较小的文件（建议每个文件不超过10000行）。

### Q4: 如何处理重复数据？
**A**: 系统会自动检测相同时间戳的记录并进行更新，不会创建重复记录。

### Q5: 支持哪些数据格式？
**A**: 目前仅支持 CSV 格式，暂不支持 Excel (.xlsx) 或其他格式。

## 使用命令行工具上传

您也可以使用项目中提供的 `generic_csv_uploader.py` 工具：

```bash
python generic_csv_uploader.py your_data.csv http://localhost:5000/operational/api/upload_operational_csv --form-data table_name=wind_speed_data
```

## 技术支持

如遇到问题，请检查：
1. 服务器是否正常运行
2. 网络连接是否正常
3. CSV 文件格式是否正确
4. 表名是否在支持列表中

有关更多技术细节，请参考系统日志或联系技术支持团队。 