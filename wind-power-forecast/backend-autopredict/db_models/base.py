from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime
import datetime

# 创建一个用于所有模型的共享Base类
Base = declarative_base()

# 定义一个通用的时间戳混入类，可以被其他模型继承使用
class TimeStampMixin:
    """所有模型共享的时间戳混入类，提供创建时间和更新时间字段"""
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow) 