from sqlalchemy import Column, Integer, String, DateTime, Float
from datetime import datetime
from .base import Base

class ActualPower(Base):
    """实际功率数据模型"""
    __tablename__ = "actual_power"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    wp_true = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class SupershortlPower(Base):
    """超短期预测功率数据模型"""
    __tablename__ = "supershortl_power"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    wp_pred2 = Column(Float, nullable=False)
    wp_pred3 = Column(Float, nullable=False)
    wp_pred4 = Column(Float, nullable=False)
    wp_pred5 = Column(Float, nullable=False)
    wp_pred6 = Column(Float, nullable=False)
    wp_pred7 = Column(Float, nullable=False)
    wp_pred8 = Column(Float, nullable=False)
    wp_pred9 = Column(Float, nullable=False)
    wp_pred10 = Column(Float, nullable=False)
    wp_pred11 = Column(Float, nullable=False)
    wp_pred12 = Column(Float, nullable=False)
    wp_pred13 = Column(Float, nullable=False)
    wp_pred14 = Column(Float, nullable=False)
    wp_pred15 = Column(Float, nullable=False)
    wp_pred16 = Column(Float, nullable=False)
    wp_pred17 = Column(Float, nullable=False)
    # 预测区间列（shift 2~17）
    wp_pred2_lower = Column(Float, nullable=True)
    wp_pred2_upper = Column(Float, nullable=True)
    wp_pred3_lower = Column(Float, nullable=True)
    wp_pred3_upper = Column(Float, nullable=True)
    wp_pred4_lower = Column(Float, nullable=True)
    wp_pred4_upper = Column(Float, nullable=True)
    wp_pred5_lower = Column(Float, nullable=True)
    wp_pred5_upper = Column(Float, nullable=True)
    wp_pred6_lower = Column(Float, nullable=True)
    wp_pred6_upper = Column(Float, nullable=True)
    wp_pred7_lower = Column(Float, nullable=True)
    wp_pred7_upper = Column(Float, nullable=True)
    wp_pred8_lower = Column(Float, nullable=True)
    wp_pred8_upper = Column(Float, nullable=True)
    wp_pred9_lower = Column(Float, nullable=True)
    wp_pred9_upper = Column(Float, nullable=True)
    wp_pred10_lower = Column(Float, nullable=True)
    wp_pred10_upper = Column(Float, nullable=True)
    wp_pred11_lower = Column(Float, nullable=True)
    wp_pred11_upper = Column(Float, nullable=True)
    wp_pred12_lower = Column(Float, nullable=True)
    wp_pred12_upper = Column(Float, nullable=True)
    wp_pred13_lower = Column(Float, nullable=True)
    wp_pred13_upper = Column(Float, nullable=True)
    wp_pred14_lower = Column(Float, nullable=True)
    wp_pred14_upper = Column(Float, nullable=True)
    wp_pred15_lower = Column(Float, nullable=True)
    wp_pred15_upper = Column(Float, nullable=True)
    wp_pred16_lower = Column(Float, nullable=True)
    wp_pred16_upper = Column(Float, nullable=True)
    wp_pred17_lower = Column(Float, nullable=True)
    wp_pred17_upper = Column(Float, nullable=True)


class ShortlPower(Base):
    """短期预测功率数据模型"""
    __tablename__ = "shortl_power"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    wp_pred = Column(Float, nullable=False)
    wp_pred_lower = Column(Float, nullable=True)   # 90% 预测区间下限
    wp_pred_upper = Column(Float, nullable=True)   # 90% 预测区间上限
    created_at = Column(DateTime, default=datetime.now)
    pre_at = Column(DateTime, nullable=False)
    pre_num = Column(Integer, nullable=False)

class MidPower(Base):
    """中期预测功率数据模型"""
    __tablename__ = "mid_power"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    farm_code = Column(String(50), nullable=False, index=True)  # 场站编码
    wp_pred = Column(Float, nullable=False)
    wp_pred_lower = Column(Float, nullable=True)   # 90% 预测区间下限
    wp_pred_upper = Column(Float, nullable=True)   # 90% 预测区间上限
    created_at = Column(DateTime, default=datetime.now)
    pre_at = Column(DateTime, nullable=False)
    pre_num = Column(Integer, nullable=False)