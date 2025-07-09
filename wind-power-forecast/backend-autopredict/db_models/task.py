from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from .base import Base

class TaskHistory(Base):
    """任务历史记录模型，记录自动预测任务的操作历史"""
    __tablename__ = 'task_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(50), nullable=False, index=True)  # UUID
    task_type = Column(String(20), nullable=False, index=True)  # ultra_short, short, medium
    action = Column(String(20), nullable=False)  # start, stop, delete, schedule, etc.
    status = Column(String(20), nullable=False)  # success, failed
    created_at = Column(DateTime, default=datetime.now)
    details = Column(Text, nullable=True)  # 详细信息，如错误原因等
    user = Column(String(50), nullable=True)  # 操作用户，可选
    
    def __repr__(self):
        return f"<TaskHistory {self.task_type} {self.action} ({self.status})>" 