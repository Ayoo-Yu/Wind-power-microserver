from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from datetime import datetime
from .base import Base

class WindSpeedData(Base):
    """单机风速数据模型"""
    __tablename__ = "wind_speed_data"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    turbine_id = Column(String(50), nullable=False, index=True)  # 单机编号
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    wind_speed = Column(Float, nullable=True)  # 风速 (m/s)
    wind_direction = Column(Float, nullable=True)  # 风向 (度)
    nacelle_position = Column(Float, nullable=True)  # 机舱位置 (度)
    created_at = Column(DateTime, default=datetime.now)

class TurbinePowerData(Base):
    """单机功率数据模型"""
    __tablename__ = "turbine_power_data"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    turbine_id = Column(String(50), nullable=False, index=True)  # 单机编号
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    active_power = Column(Float, nullable=True)  # 有功功率 (kW)
    reactive_power = Column(Float, nullable=True)  # 无功功率 (kVar)
    power_factor = Column(Float, nullable=True)  # 功率因数
    rotor_speed = Column(Float, nullable=True)  # 转子转速 (rpm)
    generator_speed = Column(Float, nullable=True)  # 发电机转速 (rpm)
    blade_angle = Column(Float, nullable=True)  # 桨叶角度 (度)
    turbine_status = Column(String(20), nullable=True)  # 机组状态
    created_at = Column(DateTime, default=datetime.now)

class WeatherData(Base):
    """气象信息数据模型"""
    __tablename__ = "weather_data"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    temperature = Column(Float, nullable=True)  # 温度 (℃)
    humidity = Column(Float, nullable=True)  # 湿度 (%)
    pressure = Column(Float, nullable=True)  # 气压 (hPa)
    wind_speed_avg = Column(Float, nullable=True)  # 平均风速 (m/s)
    wind_speed_max = Column(Float, nullable=True)  # 最大风速 (m/s)
    wind_direction = Column(Float, nullable=True)  # 风向 (度)
    visibility = Column(Float, nullable=True)  # 能见度 (km)
    precipitation = Column(Float, nullable=True)  # 降水量 (mm)
    weather_condition = Column(String(50), nullable=True)  # 天气状况
    created_at = Column(DateTime, default=datetime.now)

class InstalledCapacityData(Base):
    """装机容量数据模型"""
    __tablename__ = "installed_capacity_data"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    total_capacity = Column(Float, nullable=False)  # 总装机容量 (MW)
    turbine_count = Column(Integer, nullable=True)  # 风机数量
    turbine_capacity = Column(Float, nullable=True)  # 单机容量 (MW)
    commissioning_date = Column(DateTime, nullable=True)  # 投运日期
    remarks = Column(Text, nullable=True)  # 备注
    created_at = Column(DateTime, default=datetime.now)

class AvailableCapacityData(Base):
    """可用容量数据模型"""
    __tablename__ = "available_capacity_data"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    available_capacity = Column(Float, nullable=False)  # 可用容量 (MW)
    maintenance_capacity = Column(Float, nullable=True)  # 检修容量 (MW)
    fault_capacity = Column(Float, nullable=True)  # 故障容量 (MW)
    limited_capacity = Column(Float, nullable=True)  # 受限容量 (MW)
    availability_rate = Column(Float, nullable=True)  # 可用率 (%)
    maintenance_turbines = Column(Integer, nullable=True)  # 检修风机数量
    fault_turbines = Column(Integer, nullable=True)  # 故障风机数量
    created_at = Column(DateTime, default=datetime.now)

class TheoreticalPowerData(Base):
    """理论功率数据模型"""
    __tablename__ = "theoretical_power_data"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    theoretical_power = Column(Float, nullable=False)  # 理论功率 (MW)
    wind_speed_hub = Column(Float, nullable=True)  # 轮毂高度风速 (m/s)
    air_density = Column(Float, nullable=True)  # 空气密度 (kg/m³)
    power_curve_factor = Column(Float, nullable=True)  # 功率曲线修正系数
    wake_loss_factor = Column(Float, nullable=True)  # 尾流损失系数
    availability_factor = Column(Float, nullable=True)  # 可用率系数
    created_at = Column(DateTime, default=datetime.now)

class AvailablePowerData(Base):
    """可用功率数据模型"""
    __tablename__ = "available_power_data"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    available_power = Column(Float, nullable=False)  # 可用功率 (MW)
    grid_constraint = Column(Float, nullable=True)  # 电网约束 (MW)
    environmental_constraint = Column(Float, nullable=True)  # 环境约束 (MW)
    maintenance_constraint = Column(Float, nullable=True)  # 检修约束 (MW)
    operational_constraint = Column(Float, nullable=True)  # 运行约束 (MW)
    grid_availability = Column(Float, nullable=True)  # 电网可用率 (%)
    constraint_reason = Column(Text, nullable=True)  # 约束原因
    created_at = Column(DateTime, default=datetime.now)
