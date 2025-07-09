from sqlalchemy import Column, Integer, String, Float, Boolean, TIMESTAMP, DECIMAL, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base

class Condition(Base):
    __tablename__ = 'conditions'
    
    condition_id = Column(Integer, primary_key=True, autoincrement=True, comment="全局唯一的工况ID，主键")
    farm_name = Column(String(255), nullable=False, comment="所属风电场站名称")
    wind_speed = Column(Float, nullable=False, comment="环境风速 (m/s)")
    wind_direction = Column(Float, nullable=False, comment="环境风向 (°)")
    is_interpolated = Column(Boolean, nullable=False, default=False, comment="是否为插值数据 (0=仿真原始数据, 1=插值数据)")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="记录创建时间")
    
    # 添加唯一约束：同一风电场的同一风速和风向组合应该是唯一的
    __table_args__ = (
        UniqueConstraint('farm_name', 'wind_speed', 'wind_direction', name='uq_condition_farm_wind'),
    )
    
    readings = relationship("Reading", back_populates="condition")

class Turbine(Base):
    __tablename__ = 'turbines'
    
    turbine_id = Column(Integer, primary_key=True, autoincrement=True, comment="全局唯一的风机ID，主键")
    farm_name = Column(String(255), nullable=False, comment="风电场站")
    turbine_number = Column(String(255), nullable=False, comment="风机标号 (在场站内唯一)")
    longitude = Column(DECIMAL(9, 6), nullable=False, comment="经度")
    latitude = Column(DECIMAL(9, 6), nullable=False, comment="纬度")
    hub_height = Column(Float, comment="叶轮高度/轮毂高度 (m)")
    rotor_diameter = Column(Float, comment="叶轮直径 (m)")
    turbine_model = Column(String(255), comment="风机型号")

    # 添加唯一约束：同一风电场的风机标号应该是唯一的
    __table_args__ = (
        UniqueConstraint('farm_name', 'turbine_number', name='uq_turbine_farm_number'),
    )

    readings = relationship("Reading", back_populates="turbine")

class Reading(Base):
    __tablename__ = 'readings'
    
    reading_id = Column(Integer, primary_key=True, autoincrement=True, comment="唯一的读数ID，主键")
    condition_id = Column(Integer, ForeignKey('conditions.condition_id'), comment="关联到特定工况")
    turbine_id = Column(Integer, ForeignKey('turbines.turbine_id'), comment="关联到特定风机")
    turbine_wind_speed = Column(Float, nullable=False, comment="该风机处的实际风速")
    power_output = Column(Float, comment="功率")
    
    # 添加唯一约束：同一工况下的同一风机应该只有一条读数记录
    __table_args__ = (
        UniqueConstraint('condition_id', 'turbine_id', name='uq_reading_condition_turbine'),
    )
    
    condition = relationship("Condition", back_populates="readings")
    turbine = relationship("Turbine", back_populates="readings") 